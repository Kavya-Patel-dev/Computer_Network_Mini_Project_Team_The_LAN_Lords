from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import csv
import tempfile

import networkx as nx
import numpy as np
import pytest
import torch

from env.network_env import NetworkEnvConfig, NetworkRoutingEnv
from env.traffic import Flow, PoissonTrafficGenerator
from models.api import _calibrate_user_traffic, route, simulate, topology_graph
from models.obs import ObservationWrapper
from models.safety_fallback import choose_with_fallback
from scripts.day6_7_lite_eval import (
    EVAL_SEEDS,
    SCENARIOS,
    TEST_INTENSITIES,
    TEST_POLICIES,
    _full_path_not_in_k_report,
    _load_retry_journal,
    _test_job_plan,
    _write_results,
)

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "topology.json"


class _FakeOnline:
    def __init__(self, q_values):
        self.q_values = np.asarray(q_values, dtype=np.float32)

    def __call__(self, state):
        q = torch.as_tensor(self.q_values).reshape(1, -1)
        attn = torch.zeros((1, q.shape[1], state.num_nodes), dtype=torch.float32)
        return q, attn


class _FakeAgent:
    def __init__(self, q_values):
        self.online = _FakeOnline(q_values)


def _decision_env():
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    graph = topology_graph(data)
    traffic = PoissonTrafficGenerator(sorted(graph.nodes), demand_mbps=1.0)
    env = NetworkRoutingEnv(
        graph,
        NetworkEnvConfig(k_paths=4, history_length=4,
                         hosts_per_router_fraction=0.0, minimum_hosts=0),
        traffic_generator=traffic,
    )
    observation, _ = env.reset(seed=11)
    env.flow = Flow("H0", "H2", 10.0, duration_steps=10)
    env._refresh_paths()
    observation = env._observation()
    state = ObservationWrapper(env, "fixture").process(observation)
    return env, state


def test_fallback_invalid_action_uses_full_graph_route():
    env, state = _decision_env()
    try:
        result = choose_with_fallback(_FakeAgent([1, 0, 0, 0]), env, state,
                                      np.random.default_rng(1), action_override=99)
        assert result.fallback_used
        assert result.reason == "invalid_action"
        assert result.chosen_path is not None
    finally:
        env.close()


def test_fallback_failed_path_uses_healthy_route():
    env, state = _decision_env()
    try:
        failed_path = tuple(env._paths.paths[0])
        u, v = next((a, b) for a, b in zip(failed_path, failed_path[1:])
                    if env.graph.nodes[a].get("type") == "router"
                    and env.graph.nodes[b].get("type") == "router")
        env.graph[u][v]["up"] = False
        env.graph[u][v]["capacity"] = 0.0
        result = choose_with_fallback(_FakeAgent([10, 0, 0, 0]), env, state,
                                      np.random.default_rng(2))
        assert result.fallback_used
        assert result.reason == "failed_path"
        assert result.chosen_path != failed_path
    finally:
        env.close()


def test_fallback_nonfinite_valid_q_triggers():
    env, state = _decision_env()
    try:
        result = choose_with_fallback(_FakeAgent([float("nan"), 1, 0, 0]), env, state,
                                      np.random.default_rng(3))
        assert result.fallback_used
        assert result.reason == "non_finite_q"
        assert result.chosen_path is not None
    finally:
        env.close()


def test_fallback_when_no_valid_candidate_exists():
    env, state = _decision_env()
    try:
        empty = replace(state, action_mask=np.zeros_like(state.action_mask, dtype=bool))
        result = choose_with_fallback(_FakeAgent([0, 0, 0, 0]), env, empty,
                                      np.random.default_rng(4))
        assert result.fallback_used
        assert result.reason == "no_valid_candidate"
        assert result.chosen_path is not None
    finally:
        env.close()


def test_fallback_overload_rule_uses_alternative_below_point_nine():
    env, state = _decision_env()
    try:
        paths = env._paths.paths
        selected = 0
        backbone_edges = lambda path: {
            env._key(a, b) for a, b in zip(path, path[1:])
            if a in env.router_nodes and b in env.router_nodes
        }
        alternative = next(i for i, path in enumerate(paths) if i != selected)
        unique_backbone = backbone_edges(paths[selected]) - backbone_edges(paths[alternative])
        assert unique_backbone
        key = next(iter(unique_backbone))
        env.loads[key] = 2.0 * float(env.graph[key[0]][key[1]]["capacity"])
        env.flow = replace(env.flow, demand_mbps=1.0)
        result = choose_with_fallback(_FakeAgent([10, 0, 0, 0]), env, state,
                                      np.random.default_rng(5))
        assert result.fallback_used
        assert result.reason == "overloaded_candidate"
    finally:
        env.close()


def test_route_example_returns_valid_path():
    result = route(EXAMPLE, {}, [], {"source": "H0", "destination": "H2",
                                     "demand_mbps": 5.0, "duration_steps": 10})
    assert result["chosen_path"]
    assert result["chosen_path"][0] == "H0"
    assert result["chosen_path"][-1] == "H2"
    assert result["reason"] == "none"


def test_simulate_small_topology_returns_three_policies():
    result = simulate(EXAMPLE, "light", "normal", seed=17, max_steps=10)
    assert set(result["metrics"]) == {"static", "load_aware", "ai"}
    for row in result["metrics"].values():
        assert "mean_packet_loss" in row
        assert "mean_path_latency_ms" in row
        assert "delivered_throughput_mbps" in row
    ai = result["metrics"]["ai"]
    assert "fallback_reason_counts" in ai
    assert len(ai["decision_trace"]) == 10
    first = ai["decision_trace"][0]
    assert first["source"] and first["destination"]
    assert first["chosen_path"][0] == first["source"]
    assert first["chosen_path"][-1] == first["destination"]
    assert len(first["candidate_paths"]) == len(first["q_values"]) == 4
    assert first["fallback_reason"] in {
        "none", "invalid_action", "failed_path", "non_finite_q",
        "no_valid_candidate", "overloaded_candidate",
    }
    assert ai["invalid_actions_accepted"] == 0
    assert result["metrics"]["static"]["decision_trace"] == []
    assert result["traffic_calibration"]["basis"] == "median_router_host_access_capacity"
    assert result["traffic_calibration"]["target_backbone_intensity"] == 0.05
    assert "mean_max_access_utilization" in ai
    assert "fraction_steps_access_over_0_9" in ai
    assert "step_max_access_utilization" in first


def test_generated_traffic_respects_access_capacity_and_keeps_backbone_target():
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    for link in data["links"]:
        if link["src"].startswith("H") or link["dst"].startswith("H"):
            link["bandwidth"] = 100.0
    graph = topology_graph(data)
    endpoints = [node for node, attrs in graph.nodes(data=True)
                 if attrs.get("type") == "host"]
    traffic = PoissonTrafficGenerator(endpoints, demand_mbps=1.0, intensity=0.1)
    env = NetworkRoutingEnv(
        graph,
        NetworkEnvConfig(intensity=0.1, hosts_per_router_fraction=0.0,
                         minimum_hosts=0),
        traffic_generator=traffic,
    )
    try:
        calibration = _calibrate_user_traffic(env, 0.1)
        traffic.reset(seed=20261024)
        samples = [traffic.sample_flow() for _ in range(100)]

        assert calibration is not None
        assert calibration["median_access_capacity_mbps"] == 100.0
        assert calibration["demand_min_mbps"] == 5.0
        assert calibration["demand_max_mbps"] == 20.0
        assert 0.1 == pytest.approx(calibration["achievable_backbone_intensity"])
        assert all(5.0 <= flow.demand_mbps <= 20.0 for flow in samples)
        assert all(flow.duration_steps > 0 for flow in samples)
    finally:
        env.close()


def test_retry_job_plan_covers_exact_registered_matrix():
    entries = [{"name": f"g{i}"} for i in range(5)]
    plan = _test_job_plan(entries)
    assert len(plan) == 3000
    assert plan[0] == (entries[0], TEST_INTENSITIES[0], SCENARIOS[0],
                       EVAL_SEEDS[0], TEST_POLICIES[0])
    assert plan[-1] == (entries[-1], TEST_INTENSITIES[-1], SCENARIOS[-1],
                        EVAL_SEEDS[-1], TEST_POLICIES[-1])
    assert len({(e["name"], intensity, scenario, seed, policy)
                for e, intensity, scenario, seed, policy in plan}) == 3000


def test_retry_journal_accepts_only_an_exact_job_prefix():
    entries = [{"name": "example"}]
    plan = _test_job_plan(entries)
    first = plan[0]
    entry, intensity, scenario, seed, policy = first
    row = {"graph": entry["name"], "intensity": intensity,
           "scenario": scenario, "seed": seed, "policy": policy}
    journal = ROOT / ".day6_7_retry_journal_test.tmp"
    try:
        journal.write_text(json.dumps(row) + "\n", encoding="utf-8")
        assert _load_retry_journal(journal, plan) == [row]

        bad = dict(row, scenario="unexpected")
        journal.write_text(json.dumps(row) + "\n" + json.dumps(bad) + "\n",
                           encoding="utf-8")
        with pytest.raises(RuntimeError, match="exact job-plan prefix"):
            _load_retry_journal(journal, plan)
    finally:
        journal.unlink(missing_ok=True)


def test_results_csv_uses_union_of_policy_specific_fields():
    rows = [
        {"graph": "fixture", "policy": "baseline", "mean_packet_loss": 0.1},
        {"graph": "fixture", "policy": "ai_fallback", "mean_packet_loss": 0.05,
         "reason_counts": {"none": 10}, "expert_top1_agreement": 0.7},
    ]
    with tempfile.TemporaryDirectory(prefix="day6_results_writer_") as directory:
        _write_results(Path(directory), rows, {"T1": {"pass": True}})
        with (Path(directory) / "results.csv").open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            parsed = list(reader)
        assert "reason_counts" in reader.fieldnames
        assert "expert_top1_agreement" in reader.fieldnames
        assert parsed[0]["reason_counts"] == ""
        assert json.loads(parsed[1]["reason_counts"]) == {"none": 10}


def test_candidate_miss_report_uses_measured_full_dijkstra_rows_only():
    rows = [
        {"policy": "ai_fallback", "full_path_not_in_k_fraction": 0.0,
         "measured_steps": 400},
        {"policy": "dijkstra_load_aware", "full_path_not_in_k_fraction": 0.22,
         "measured_steps": 400},
        {"policy": "dijkstra_static", "full_path_not_in_k_fraction": 0.0,
         "measured_steps": 400},
    ]
    report = _full_path_not_in_k_report(rows)
    assert report == {"measured_by": "dijkstra_load_aware", "misses": 88.0,
                      "decisions": 400, "fraction": 0.22}
