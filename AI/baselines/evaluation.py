"""Deterministic shared-scenario evaluation utilities for routing policies."""
from __future__ import annotations

from collections import deque
import hashlib
import json
import math
import time
from typing import Any

import networkx as nx
import numpy as np

from env.events import BandwidthDrop
from env.network_env import NetworkEnvConfig, NetworkRoutingEnv
from env.paths import PathResult
from env.traffic import (GravityTrafficGenerator, HotspotTrafficGenerator,
                         PoissonTrafficGenerator, SNDlibReplay)
from .explicit_path import step_explicit_path
from .policies import POLICIES, Decision, choose_decision

WARMUP = 100
SCENARIOS = ("normal", "link_failures", "router_failure", "traffic_spike", "bandwidth_drop")
EVAL_SEEDS = tuple(range(1000, 1010))
TRAIN_SEEDS = (20000, 20001, 20002)
INTENSITY_PATH = None


def load_graph(entry: dict, data_root):
    from env.topology import load_repetita, load_sndlib, load_zoo
    path = data_root / entry["path"]
    if entry["source"] == "sndlib":
        return load_sndlib(path)[0]
    if entry["source"] == "zoo":
        return load_zoo(path)
    return load_repetita(path)[0]


def make_traffic(kind: str, entry: dict, topology: NetworkRoutingEnv,
                 intensity: float, data_root):
    common = dict(demand_mbps=1.0, intensity=float(intensity))
    if kind == "poisson":
        traffic = PoissonTrafficGenerator(topology.host_nodes, **common)
    elif kind == "gravity":
        costs = {}
        for source in topology.host_nodes:
            lengths = nx.single_source_dijkstra_path_length(
                topology.graph, source, weight="latency")
            for destination in topology.host_nodes:
                if destination != source:
                    costs[source, destination] = float(lengths[destination])
        traffic = GravityTrafficGenerator(
            topology.host_nodes, {node: 1.0 for node in topology.host_nodes},
            costs, **common)
    elif kind == "hotspot":
        hotspots = topology.host_nodes[:max(1, math.ceil(len(topology.host_nodes) / 4))]
        traffic = HotspotTrafficGenerator(
            topology.host_nodes, hotspots, hotspot_multiplier=4.0, **common)
    elif kind == "sndlib":
        if entry["source"] != "sndlib":
            raise ValueError("SNDlib replay is only available on SNDlib source graphs")
        traffic = SNDlibReplay.from_sndlib(
            list(topology.router_nodes), data_root / entry["path"], **common)
    else:
        raise ValueError(f"unknown traffic generator {kind!r}")
    traffic.configure_for_network(
        topology.graph, topology.router_nodes, float(intensity), (0.05, 0.20))
    return traffic


def graph_failure_plan(graph: nx.Graph, entry: dict) -> dict[str, Any]:
    routers = [node for node, attrs in graph.nodes(data=True)
               if attrs.get("type", "router") == "router"]
    backbone = graph.subgraph(routers)
    bridge_set = {frozenset(edge) for edge in nx.bridges(backbone)}
    nonbridges = [tuple(sorted(edge, key=str)) for edge in backbone.edges
                  if frozenset(edge) not in bridge_set]
    rng = np.random.default_rng(1777 + sum(map(ord, entry["name"])))
    nonbridges = sorted(nonbridges, key=lambda e: (str(e[0]), str(e[1])))
    if len(nonbridges) >= 2:
        selected_indices = rng.choice(len(nonbridges), size=2, replace=False)
        failed_links = [nonbridges[int(i)] for i in selected_indices]
    else:
        failed_links = []
    articulation = set(nx.articulation_points(backbone)) if backbone.number_of_nodes() else set()
    safe_routers = sorted((node for node in routers if node not in articulation), key=str)
    failed_router = (safe_routers[int(rng.integers(len(safe_routers)))]
                     if safe_routers else None)
    all_backbone_edges = [tuple(sorted(edge, key=str)) for edge in backbone.edges]
    if len(all_backbone_edges) >= 3:
        selected = rng.choice(len(all_backbone_edges), size=3, replace=False)
        dropped_links = [all_backbone_edges[int(i)] for i in selected]
    else:
        dropped_links = all_backbone_edges
    return {"link_failures": failed_links, "router_failure": failed_router,
            "bandwidth_drop": dropped_links, "failure_step": 200,
            "restore_step": 260, "bandwidth_restore_step": 300,
            "link_failure_times": [200, 220], "link_restore_times": [260, 280],
            "spike_start_step": 200, "spike_duration_steps": 50}


def _restore_link(env: NetworkRoutingEnv, edge: tuple[str, str]) -> None:
    u, v = edge
    attrs = env.graph[u][v]
    attrs["up"] = True
    attrs["capacity"] = float(attrs.get("base_capacity", attrs.get("bandwidth", 0.0)))


def _apply_scenario_change(env: NetworkRoutingEnv, scenario: str,
                           plan: dict[str, Any], step: int) -> None:
    if scenario == "link_failures":
        changed = False
        for i, edge in enumerate(plan["link_failures"]):
            if step == plan["link_failure_times"][i]:
                env.fail_link(edge)
                changed = True
            if step == plan["link_restore_times"][i]:
                _restore_link(env, edge)
                changed = True
        if changed:
            env._rebuild_loads(); env._refresh_link_metrics(); env._refresh_paths()
    elif scenario == "router_failure":
        router = plan["router_failure"]
        if router is None:
            return
        if step == plan["failure_step"]:
            env.fail_router(router)
        if step == plan["restore_step"]:
            env.graph.nodes[router]["up"] = True
            for _, neighbor in env.graph.edges(router):
                _restore_link(env, (router, neighbor))
            env._rebuild_loads(); env._refresh_link_metrics(); env._refresh_paths()


def canonical_flow(flow) -> dict[str, Any]:
    return {"source": str(flow.source), "destination": str(flow.destination),
            "demand_mbps": float(flow.demand_mbps), "qos": str(flow.qos_class.value),
            "priority": int(flow.priority), "duration_steps": int(flow.duration_steps),
            "flow_id": str(flow.flow_id)}


def rolling_recovery(losses: list[float], failure_step: int,
                     window: int = 10) -> tuple[float, bool]:
    """Return elapsed steps to loss recovery and whether it was censored.

    Baseline is the mean of the ten new-flow losses immediately before failure.
    For baseline <= 0.001, recovery is within 0.001 absolute; otherwise the
    tolerance is 10% of the baseline. A full post-failure rolling window is
    required before declaring recovery.
    """
    before = losses[max(0, failure_step - window):failure_step]
    if not before:
        return float(max(0, len(losses) - failure_step)), True
    baseline = float(np.mean(before))
    tolerance = 0.001 if baseline <= 0.001 else 0.1 * baseline
    for end in range(failure_step + window, len(losses) + 1):
        current = float(np.mean(losses[end - window:end]))
        if abs(current - baseline) <= tolerance:
            return float(end - failure_step), False
    return float(len(losses) - failure_step), True


def observe_od_route_change(previous_paths: dict[tuple[str, str], tuple[str, ...]],
                            source: Any, destination: Any,
                            path: tuple[str, ...]) -> bool | None:
    """Track route changes only when the same OD pair is requested again.

    The environment makes one new-flow decision per step; comparing paths
    across unrelated OD pairs would measure traffic variation, not route
    flapping. None marks an OD pair's first observation.
    """
    key = (str(source), str(destination))
    path = tuple(path)
    previous = previous_paths.get(key)
    previous_paths[key] = path
    return None if previous is None else previous != path


def run_episode(entry: dict, graph: nx.Graph, kind: str, intensity: float,
                policy: str, seed: int, scenario: str, alpha: float,
                rf_model=None, max_steps: int = 500, warmup: int = WARMUP,
                data_root=None) -> dict[str, Any]:
    if scenario not in SCENARIOS:
        raise ValueError(scenario)
    if data_root is None:
        raise ValueError("data_root is required")
    plan = graph_failure_plan(graph, entry)
    if max_steps < 400:
        failure = max(warmup + 5, max_steps // 3)
        restore = min(max_steps - 1, failure + max(10, max_steps // 8))
        plan["failure_step"] = failure
        plan["restore_step"] = restore
        second_failure = min(restore - 1, failure + max(2, max_steps // 16))
        plan["link_failure_times"] = [failure, second_failure]
        plan["link_restore_times"] = [restore, min(max_steps - 1, restore + max(2, max_steps // 16))]
        plan["bandwidth_restore_step"] = min(max_steps - 1, restore + 10)
        plan["spike_start_step"] = failure
        plan["spike_duration_steps"] = max(1, restore - failure)
    spikes = ()
    events = ()
    if scenario == "traffic_spike":
        from env.traffic import TrafficSpike
        spikes = (TrafficSpike(plan["spike_start_step"],
                               plan["spike_duration_steps"], 4.0),)
    if scenario == "bandwidth_drop":
        events = tuple(BandwidthDrop(plan["failure_step"], edge, 0.5, duration=100)
                       for edge in plan["bandwidth_drop"])
    config = NetworkEnvConfig(max_steps=max_steps, intensity=float(intensity))
    stub = PoissonTrafficGenerator(sorted(graph.nodes), demand_mbps=1.0)
    topology = NetworkRoutingEnv(graph, config, traffic_generator=stub)
    traffic = make_traffic(kind, entry, topology, intensity, data_root)
    env = NetworkRoutingEnv(graph, config, traffic_generator=traffic,
                            events=events, traffic_spikes=spikes)
    env.reset(seed=int(seed))
    rng = np.random.default_rng(seed ^ (sum(map(ord, policy)) << 8))
    request_digest = hashlib.sha256()
    flow_hash_items = []
    losses: list[float] = []
    latencies: list[float] = []
    delivered: list[float] = []
    max_backbone: list[float] = []
    flap_count = 0
    previous_paths_by_od: dict[tuple[str, str], tuple[str, ...]] = {}
    routed_count = 0
    flapping_comparisons = 0
    post_failure_routed_count = 0
    invalid_count = 0
    noncandidate_count = 0
    measured_ecmp_ties = 0
    measured_full_dijkstra_count = 0
    decision_times_ms = []
    time_since_failure = 10_000
    failure_start = plan["failure_step"] if scenario != "normal" else None

    for step in range(max_steps):
        _apply_scenario_change(env, scenario, plan, step)
        if failure_start is not None and step >= failure_start:
            time_since_failure = step - failure_start
        flow = env.flow
        if flow is None:
            raise RuntimeError(f"missing request before decision {step} on {entry['name']}")
        canonical = canonical_flow(flow)
        flow_hash_items.append(canonical)
        request_digest.update(json.dumps(canonical, sort_keys=True,
                                         separators=(",", ":")).encode("utf-8"))
        decision_start = time.perf_counter_ns()
        decision: Decision = choose_decision(
            policy, env, rng, alpha=alpha, rf_model=rf_model,
            time_since_last_failure=time_since_failure)
        decision_times_ms.append((time.perf_counter_ns() - decision_start) / 1e6)
        if step >= warmup:
            if decision.full_path_not_in_k:
                noncandidate_count += 1
            if policy in {"dijkstra_static", "dijkstra_load_aware"}:
                measured_full_dijkstra_count += 1
            if decision.ecmp_tie:
                measured_ecmp_ties += 1
        if decision.explicit_path is not None:
            obs, reward, terminated, truncated, info = step_explicit_path(
                env, decision.explicit_path)
        else:
            obs, reward, terminated, truncated, info = env.step(decision.action)
        if info.get("invalid_action", False):
            invalid_count += 1
        routed_path = info.get("selected_path")
        if routed_path is None:
            flow_loss = 1.0
            flow_latency = None
            flow_delivered = 0.0
        else:
            flow_loss = float(info.get("path_loss", 1.0))
            flow_latency = float(info.get("path_latency_ms", 0.0))
            flow_delivered = float(info.get("delivered_mbps", 0.0))
            routed_count += 1
            if failure_start is not None and step >= failure_start:
                post_failure_routed_count += 1
            route_changed = observe_od_route_change(
                previous_paths_by_od, flow.source, flow.destination,
                tuple(routed_path))
            if step >= warmup and route_changed is not None:
                flapping_comparisons += 1
                flap_count += int(route_changed)
        losses.append(flow_loss)
        if step >= warmup:
            if flow_latency is not None:
                latencies.append(flow_latency)
            delivered.append(flow_delivered)
            max_backbone.append(float(info["step_max_backbone_utilization"]))
        if terminated or truncated:
            break

    measured_losses = np.asarray(losses[warmup:], dtype=float)
    max_array = np.asarray(max_backbone, dtype=float)
    recovery_time = None
    recovery_censored = None
    if scenario != "normal":
        recovery_time, recovery_censored = rolling_recovery(losses, int(failure_start))
    fail_denominator = max_steps - warmup
    return {
        "split": entry["split"], "graph": entry["name"], "source": entry["source"],
        "generator": kind, "intensity": float(intensity), "scenario": scenario,
        "policy": policy, "seed": int(seed),
        "request_sequence_sha256": request_digest.hexdigest(),
        "request_sequence_length": len(flow_hash_items),
        "mean_path_latency_ms": float(np.mean(latencies)) if latencies else 0.0,
        "p95_path_latency_ms": float(np.percentile(latencies, 95)) if latencies else 0.0,
        "mean_packet_loss": float(np.mean(measured_losses)) if measured_losses.size else 0.0,
        "delivered_throughput_mbps": float(np.mean(delivered)) if delivered else 0.0,
        "mean_max_backbone_utilization": float(np.mean(max_array)) if max_array.size else 0.0,
        "p95_max_backbone_utilization": float(np.percentile(max_array, 95)) if max_array.size else 0.0,
        "fraction_steps_over_0_9": float(np.mean(max_array > 0.9 + 1e-9)) if max_array.size else 0.0,
        "flapping_rate": float(flap_count / max(1, flapping_comparisons)),
        "flapping_comparisons": flapping_comparisons,
        "mean_decision_time_ms": float(np.mean(decision_times_ms)) if decision_times_ms else 0.0,
        "recovery_time_steps": recovery_time,
        "recovery_censored": recovery_censored,
        "invalid_actions_accepted": invalid_count,
        "post_failure_routed_flows": post_failure_routed_count,
        "full_path_not_in_k_fraction": (noncandidate_count / measured_full_dijkstra_count
                                         if measured_full_dijkstra_count else 0.0),
        "ecmp_tie_fraction": measured_ecmp_ties / max(1, max_steps - warmup) if policy == "ecmp" else 0.0,
        "measured_steps": fail_denominator,
        "event_schedule_json": json.dumps(plan, sort_keys=True, separators=(",", ":")),
    }

