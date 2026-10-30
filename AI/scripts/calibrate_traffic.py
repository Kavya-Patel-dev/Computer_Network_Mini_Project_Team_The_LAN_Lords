"""Calibrate decision-based concurrent traffic on static and greedy routes."""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

import networkx as nx
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUTPUT = ROOT / "outputs" / "calibration_v2.csv"
sys.path.insert(0, str(ROOT))

from env.network_env import NetworkEnvConfig, NetworkRoutingEnv
from env.paths import PathResult
from env.topology import load_repetita, load_sndlib, load_zoo, path_diversity
from env.traffic import (GravityTrafficGenerator, HotspotTrafficGenerator,
                         PoissonTrafficGenerator, SNDlibReplay)

EPISODES = 3
STEPS = 500
WARMUP = 100
SEED = 20261010
INTENSITIES = (0.05, 0.1, 0.15, 0.2, 0.3, 0.45)
DEMAND_FRACTIONS = (0.05, 0.20)


def selected_graphs() -> list[dict]:
    splits = json.loads((DATA / "splits.json").read_text(encoding="utf-8"))
    by_name = {entry["name"]: {**entry, "split": split}
               for split, entries in splits.items() for entry in entries}
    names = ("abilene", "Nsfnet", "Peer1", "newyork", "geant", "Renater2004",
             "nobel-eu", "DeutscheTelekom")
    return [by_name[name] for name in names]


def load_graph(entry: dict) -> nx.Graph:
    path = DATA / entry["path"]
    if entry["source"] == "sndlib":
        return load_sndlib(path)[0]
    if entry["source"] == "zoo":
        return load_zoo(path)
    return load_repetita(path)[0]


def topology_diagnostics(graph: nx.Graph) -> tuple[int, float]:
    routers = [node for node, attrs in graph.nodes(data=True)
               if attrs.get("type", "router") == "router"]
    backbone = graph.subgraph(routers)
    return len(list(nx.bridges(backbone))), path_diversity(graph)


def make_traffic(kind: str, entry: dict, topology: NetworkRoutingEnv,
                 intensity: float):
    common = dict(demand_mbps=1.0, intensity=intensity)
    if kind == "sndlib":
        traffic = SNDlibReplay.from_sndlib(
            list(topology.router_nodes), DATA / entry["path"], **common)
    elif kind == "poisson":
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
    else:
        raise ValueError(f"unknown traffic generator {kind}")
    settings = traffic.configure_for_network(
        topology.graph, topology.router_nodes, intensity, DEMAND_FRACTIONS)
    return traffic, settings


def choose_action(policy: str, env: NetworkRoutingEnv) -> int:
    if env.flow is None:
        return env.config.k_paths
    if policy == "static_latency_shortest":
        path = tuple(nx.shortest_path(
            env.graph, env.flow.source, env.flow.destination, weight="latency"))
        # Keep the static policy independent of current loads.
        env._paths = PathResult((path,), False)
        return 0
    if not env._paths.paths:
        return env.config.k_paths

    routers = set(env.router_nodes)

    def predicted_max_backbone_utilization(path):
        values = [(env.loads.get(env._key(u, v), 0.0)
                   + env.flow.demand_mbps) / float(env.graph[u][v]["capacity"])
                  for u, v in zip(path, path[1:]) if u in routers and v in routers]
        return max(values, default=0.0)

    return min(range(len(env._paths.paths)),
               key=lambda index: (predicted_max_backbone_utilization(
                   env._paths.paths[index]), index))


def run_episode(entry: dict, graph: nx.Graph, config: NetworkEnvConfig,
                traffic, policy: str, episode: int) -> dict[str, float]:
    seed = SEED + 100_000 * episode + sum(map(ord, str(entry["name"])))
    env = NetworkRoutingEnv(graph, config, traffic_generator=traffic)
    env.reset(seed=seed)
    max_backbone = []
    mean_backbone = []
    max_access = []
    path_latencies = []
    flow_losses = []
    for step in range(STEPS):
        flow_attempted = env.flow is not None
        action = choose_action(policy, env)
        _observation, _reward, _terminated, _truncated, info = env.step(action)
        if step >= WARMUP:
            max_backbone.append(float(info["step_max_backbone_utilization"]))
            mean_backbone.append(float(info["step_mean_backbone_utilization"]))
            max_access.append(float(info["step_max_access_utilization"]))
            if flow_attempted:
                if "path_loss" in info:
                    path_loss = float(info["path_loss"])
                    path_latencies.append(float(info["path_latency_ms"]))
                else:
                    path_loss = 1.0
                flow_losses.append(path_loss)
    losses = np.asarray(flow_losses, dtype=float)
    return {
        "max_backbone_sum": float(np.sum(max_backbone)),
        "mean_backbone_sum": float(np.sum(mean_backbone)),
        "max_access_sum": float(np.sum(max_access)),
        "measured_steps": float(len(max_backbone)),
        "steps_max_backbone_gt_0_9": float(np.sum(np.asarray(max_backbone) > 0.9 + 1e-9)),
        "path_latency_sum_ms": float(np.sum(path_latencies)),
        "routed_flows": float(len(path_latencies)),
        "packet_loss_sum": float(np.sum(losses)),
        "flow_attempts": float(len(flow_losses)),
        "flows_with_loss": float(np.sum(losses > 0.0)),
    }


def summarize(episodes: list[dict[str, float]]) -> dict[str, float]:
    totals = {key: sum(episode[key] for episode in episodes)
              for key in episodes[0]}
    steps = totals["measured_steps"]
    attempts = totals["flow_attempts"]
    routed = totals["routed_flows"]
    return {
        "mean_max_backbone_utilization": totals["max_backbone_sum"] / steps,
        "fraction_steps_max_backbone_gt_0_9": totals["steps_max_backbone_gt_0_9"] / steps,
        "mean_backbone_utilization": totals["mean_backbone_sum"] / steps,
        "mean_max_access_utilization": totals["max_access_sum"] / steps,
        "mean_path_latency_ms": totals["path_latency_sum_ms"] / routed if routed else 0.0,
        "mean_packet_loss": totals["packet_loss_sum"] / attempts if attempts else 0.0,
        "fraction_flows_loss_gt_0": totals["flows_with_loss"] / attempts if attempts else 0.0,
    }


def main() -> None:
    rows = []
    graph_entries = selected_graphs()
    for entry in graph_entries:
        graph = load_graph(entry)
        bridges, diversity = topology_diagnostics(graph)
        config = NetworkEnvConfig(
            max_steps=STEPS, intensity=0.05,
            demand_min_fraction=DEMAND_FRACTIONS[0],
            demand_max_fraction=DEMAND_FRACTIONS[1])
        # Use a zero-load stub only to attach the standard host set once.
        stub = PoissonTrafficGenerator(sorted(graph.nodes), demand_mbps=1.0)
        topology = NetworkRoutingEnv(graph, config, traffic_generator=stub)
        generator_kinds = ["poisson", "gravity", "hotspot"]
        if entry["source"] == "sndlib":
            generator_kinds.append("sndlib")
        clamp_rows = []
        deviation_rows = []
        for kind in generator_kinds:
            for intensity in INTENSITIES:
                traffic, settings = make_traffic(kind, entry, topology, intensity)
                if settings["duration_clamp"] != "none":
                    clamp_rows.append((kind, intensity, settings["duration_clamp"],
                                       settings["achievable_intensity"]))
                policy_summaries = {}
                for policy in ("static_latency_shortest", "greedy_min_max_util"):
                    episodes = [run_episode(entry, graph, config, traffic, policy, episode)
                                for episode in range(EPISODES)]
                    policy_summaries[policy] = summarize(episodes)
                static_realized = policy_summaries["static_latency_shortest"][
                    "mean_backbone_utilization"]
                relative_error = abs(static_realized - intensity) / max(intensity, 1e-12)
                within_20 = relative_error <= 0.20
                if not within_20:
                    deviation_rows.append((kind, intensity, static_realized, relative_error))
                for policy, metrics in policy_summaries.items():
                    rows.append({
                        "split": entry["split"], "name": entry["name"],
                        "source": entry["source"], "nodes": entry["num_nodes"],
                        "edges": entry["num_edges"], "backbone_bridges": bridges,
                        "router_path_diversity": diversity,
                        "generator": kind, "target_intensity": intensity,
                        "duration_mean_steps": settings["mean_duration_steps"],
                        "duration_clamp": settings["duration_clamp"],
                        "achievable_intensity": settings["achievable_intensity"],
                        "realized_static_mean_backbone_utilization": static_realized,
                        "static_realization_within_20pct": within_20,
                        "policy": policy,
                        **metrics,
                    })
        print(f"Completed {entry['split']} graph {entry['name']} ({entry['source']}); "
              f"{len(rows)} rows accumulated", flush=True)
        for kind, intensity, bound, achieved in clamp_rows:
            print(f"  duration clamp: {kind}, target={intensity:g}, bound={bound}, "
                  f"achievable intensity={achieved:.4f}", flush=True)
        for kind, intensity, realized, error in deviation_rows:
            print(f"  >20% realization difference: {kind}, target={intensity:g}, "
                  f"realized static mean={realized:.4f}, relative error={error:.1%}",
                  flush=True)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} policy-setting rows to {OUTPUT}", flush=True)
    print("Metrics average steps 100-499 of each 500-step episode; "
          "the static realized mean backbone utilization is repeated for both policy rows.",
          flush=True)


if __name__ == "__main__":
    main()
