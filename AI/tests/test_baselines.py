import json
from pathlib import Path

import networkx as nx
import numpy as np
import pytest

from baselines.evaluation import (graph_failure_plan, load_graph,
                                  observe_od_route_change, rolling_recovery,
                                  run_episode)
from baselines.explicit_path import step_explicit_path
from baselines.features import FEATURE_NAMES, candidate_features
from baselines.leakage import guard_fit_and_tuning
from baselines.policies import choose_decision, dijkstra_path, dynamic_link_cost
from env.network_env import NetworkEnvConfig, NetworkRoutingEnv
from env.traffic import Flow, PoissonTrafficGenerator

ROOT = Path(__file__).resolve().parents[1]


def test_flapping_rate_compares_only_repeated_od_pairs():
    history = {}
    assert observe_od_route_change(history, "s", "t", ("s", "a", "t")) is None
    assert observe_od_route_change(history, "x", "y", ("x", "a", "y")) is None
    assert observe_od_route_change(history, "s", "t", ("s", "a", "t")) is False
    assert observe_od_route_change(history, "s", "t", ("s", "b", "t")) is True


def diamond(k=1):
    graph = nx.Graph()
    for node in ("s", "a", "b", "t"):
        graph.add_node(node, type="router", up=True)
    graph.add_edge("s", "a", bandwidth=100.0, capacity=100.0, latency=1.0)
    graph.add_edge("a", "t", bandwidth=100.0, capacity=100.0, latency=1.0)
    graph.add_edge("s", "b", bandwidth=100.0, capacity=100.0, latency=2.0)
    graph.add_edge("b", "t", bandwidth=100.0, capacity=100.0, latency=2.0)
    gen = PoissonTrafficGenerator(("s", "a", "b", "t"), demand_mbps=1.0)
    return NetworkRoutingEnv(
        graph,
        NetworkEnvConfig(k_paths=k, hosts_per_router_fraction=None, minimum_hosts=0),
        gen)


def test_full_graph_static_dijkstra_matches_networkx():
    env = diamond(k=1)
    env.reset(seed=55)
    env.flow = Flow("s", "t", 1.0)
    env._refresh_paths()
    path = dijkstra_path(env, lambda _u, _v, attrs: float(attrs["latency"]))
    expected = tuple(nx.shortest_path(env.graph, "s", "t", weight="latency"))
    assert path == expected == ("s", "a", "t")


def test_explicit_path_hook_does_not_change_day2_candidate_action_behavior():
    env = diamond(k=1)
    env.reset(seed=19)
    assert len(env._paths.paths) == 1
    candidate = env._paths.paths[0]
    outside = ("s", "b", "t") if candidate != ("s", "b", "t") else ("s", "a", "t")
    env.flow = Flow("s", "t", 1.0)
    # Make the candidate generator prefer the longer B path while the full
    # static Dijkstra reference continues to use the shortest A path.
    env.loads[env._key("s", "a")] = 500.0
    env.loads[env._key("a", "t")] = 500.0
    env._refresh_paths()
    decision = choose_decision("dijkstra_static", env, np.random.default_rng(1))
    assert decision.explicit_path == ("s", "a", "t")
    assert decision.full_path_not_in_k
    assert len(env._paths.paths) == 1 and decision.explicit_path not in env._paths.paths
    # The ordinary Day 2 interface still accepts only its current K candidate.
    _, _, _, _, invalid = env.step(1)
    assert invalid["invalid_action"]
    env.reset(seed=19)
    env.flow = Flow("s", "t", 1.0)
    _, _, _, _, info = step_explicit_path(env, decision.explicit_path)
    assert info["selected_path"] == decision.explicit_path
    assert not info["invalid_action"]
    # A raw out-of-candidate action remains invalid through the public API.
    env.reset(seed=21)
    if env.flow is not None and env._paths.paths:
        _, _, _, _, info = env.step(1)
        assert info["invalid_action"]


def test_recovery_time_on_synthetic_loss_series():
    losses = [0.02] * 20 + [0.20] * 12 + [0.02] * 20
    elapsed, censored = rolling_recovery(losses, failure_step=20, window=10)
    assert elapsed == 22
    assert censored is False
    zero_baseline = [0.0] * 15 + [0.03] * 15
    elapsed, censored = rolling_recovery(zero_baseline, failure_step=15, window=10)
    assert elapsed == 15
    assert censored is True


def test_deterministic_request_hashes_and_shared_policy_sequence():
    splits = json.loads((ROOT / "data" / "splits.json").read_text(encoding="utf-8"))
    entry = {**splits["val"][0], "split": "val"}
    graph = load_graph(entry, ROOT / "data")
    results = [run_episode(entry, graph, "poisson", 0.1, policy, 1000,
                           "normal", 1.0, max_steps=35, warmup=5,
                           data_root=ROOT / "data")
               for policy in ("random", "dijkstra_static", "greedy_min_util")]
    assert len({row["request_sequence_sha256"] for row in results}) == 1
    repeated = run_episode(entry, graph, "poisson", 0.1, "random", 1000,
                           "normal", 1.0, max_steps=35, warmup=5,
                           data_root=ROOT / "data")
    assert results[0]["request_sequence_sha256"] == repeated["request_sequence_sha256"]
    for key in ("mean_packet_loss", "fraction_steps_over_0_9",
                "mean_path_latency_ms", "delivered_throughput_mbps"):
        assert results[0][key] == pytest.approx(repeated[key])


def test_failure_scenario_keeps_request_sequence_equal_and_recovers():
    splits = json.loads((ROOT / "data" / "splits.json").read_text(encoding="utf-8"))
    entry = {**splits["test"][1], "split": "test"}
    graph = load_graph(entry, ROOT / "data")
    rows = [run_episode(entry, graph, "poisson", 0.1, policy, 1000,
                        "link_failures", 1.0, max_steps=100, warmup=10,
                        data_root=ROOT / "data")
            for policy in ("dijkstra_static", "dijkstra_load_aware",
                           "dijkstra_load_aware_k", "greedy_min_util")]
    assert len({row["request_sequence_sha256"] for row in rows}) == 1
    assert all(row["invalid_actions_accepted"] == 0 for row in rows)
    assert all(row["post_failure_routed_flows"] > 0 for row in rows)
    assert all(row["recovery_time_steps"] is not None for row in rows)


def test_failure_schedule_uses_nonbridge_links_and_nonarticulation_router():
    splits = json.loads((ROOT / "data" / "splits.json").read_text(encoding="utf-8"))
    entry = {**splits["test"][1], "split": "test"}
    graph = load_graph(entry, ROOT / "data")
    plan = graph_failure_plan(graph, entry)
    backbone = graph.subgraph([n for n, a in graph.nodes(data=True)
                               if a.get("type", "router") == "router"])
    bridges = {frozenset(edge) for edge in nx.bridges(backbone)}
    assert len(plan["link_failures"]) == 2
    assert all(frozenset(edge) not in bridges for edge in plan["link_failures"])
    assert plan["router_failure"] not in set(nx.articulation_points(backbone))
    assert plan["link_failure_times"] == [200, 220]
    assert plan["link_restore_times"] == [260, 280]


def test_evaluation_intensities_for_test_are_validation_transfers():
    selected = json.loads((ROOT / "data" / "eval_intensity.json").read_text(encoding="utf-8"))
    splits = json.loads((ROOT / "data" / "splits.json").read_text(encoding="utf-8"))
    for entry in splits["test"]:
        for value in selected[entry["name"]]["generators"].values():
            assert value["source"] == "median selected validation intensity"
            assert value["status"] == "validation_transfer"


def test_split_leakage_guard_rejects_test_graph_in_fit_or_tuning():
    train, val, test = {"a", "b"}, {"c"}, {"d"}
    guard_fit_and_tuning({"a"}, {"c"}, train, val, test)
    with pytest.raises(AssertionError, match="train graphs only"):
        guard_fit_and_tuning({"d"}, {"c"}, train, val, test)
    with pytest.raises(AssertionError, match="validation graphs only"):
        guard_fit_and_tuning({"a"}, {"d"}, train, val, test)


def test_test_split_guard_rejects_overlapping_graph_partitions():
    with pytest.raises(AssertionError, match="must be disjoint"):
        guard_fit_and_tuning({"a"}, {"b"}, {"a"}, {"b"}, {"a"})


def test_dynamic_dijkstra_cost_uses_the_configured_utilization_formula():
    env = diamond(k=1)
    env.reset(seed=23)
    env.flow = Flow("s", "t", 10.0)
    key = env._key("s", "a")
    env.loads[key] = 50.0
    utilization = env.loads[key] / env.graph["s"]["a"]["capacity"]
    expected = env.latencies[key] * (1 + 2.0 * utilization / (1 - min(utilization, 0.95)))
    assert dynamic_link_cost(env, "s", "a", alpha=2.0) == pytest.approx(expected)


def test_rf_candidate_feature_vector_matches_documented_order():
    env = diamond(k=2)
    env.reset(seed=29)
    env.flow = Flow("s", "t", 10.0)
    vector = candidate_features(env, ("s", "a", "t"), time_since_last_failure=17)
    assert vector.shape == (len(FEATURE_NAMES),)
    assert vector[0] == pytest.approx(0.0)  # path max backbone util before install
    assert vector[1] == pytest.approx(0.0)  # path mean backbone util
    assert vector[2] == pytest.approx(2.0)  # hop count
    expected_latency = sum(env.latencies[env._key(u, v)]
                           for u, v in zip(("s", "a", "t"), ("a", "t")))
    assert vector[3] == pytest.approx(expected_latency)  # current total latency
    assert vector[4] == pytest.approx(100.0)  # min residual capacity
    assert vector[5] == pytest.approx(0.1)  # demand / residual
    assert vector[8] == 1.0  # BULK one-hot in QoS enum order
    assert vector[-1] == 17.0

