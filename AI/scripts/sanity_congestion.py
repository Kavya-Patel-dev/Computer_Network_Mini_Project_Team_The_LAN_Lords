"""Show congestion separation on a diamond and one real topology."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import networkx as nx
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from baselines.evaluation import load_graph
from baselines.explicit_path import step_explicit_path
from baselines.policies import choose_decision
from env.network_env import NetworkEnvConfig, NetworkRoutingEnv
from env.traffic import Flow, TrafficGenerator

DATA = ROOT / "data"
ALPHA_PATH = ROOT / "configs" / "evaluation.json"


class RepeatingFlow(TrafficGenerator):
    def __init__(self, nodes, source, destination, demand, duration=5):
        super().__init__(nodes, demand_mbps=demand, intensity=0.0,
                         duration_mean_steps=float(duration))
        self.source, self.destination = source, destination
        self.demand, self.duration = float(demand), int(duration)
        self.network_calibrated = True

    def sample_flow(self, **kwargs):
        return self._flow(source=self.source, destination=self.destination,
                          demand=self.demand, duration=self.duration)


def diamond_graph():
    graph = nx.Graph()
    for node in ("s", "a", "b", "t"):
        graph.add_node(node, type="router")
    for u, v, latency in (("s", "a", 10.0), ("a", "t", 10.0),
                          ("s", "b", 12.0), ("b", "t", 12.0)):
        graph.add_edge(u, v, bandwidth=100.0, capacity=100.0,
                       latency=latency, loss=0.0)
    return graph, "s", "t", 25.0


def find_real_pair(graph):
    routers = sorted((node for node, attrs in graph.nodes(data=True)
                      if attrs.get("type", "router") == "router"), key=str)
    for i, source in enumerate(routers):
        for destination in routers[i + 1:]:
            paths = []
            try:
                for path in nx.shortest_simple_paths(graph, source, destination,
                                                     weight="latency"):
                    paths.append(tuple(path))
                    if len(paths) >= 5:
                        break
            except nx.NetworkXNoPath:
                continue
            if len(paths) < 2:
                continue
            first = paths[0]
            for alternate in paths[1:]:
                edges0 = {frozenset(edge) for edge in zip(first, first[1:])}
                edges1 = {frozenset(edge) for edge in zip(alternate, alternate[1:])}
                if edges0.isdisjoint(edges1):
                    capacity = min(float(graph[u][v].get("capacity",
                                                        graph[u][v].get("bandwidth", 0.0)))
                                   for u, v in zip(first, first[1:]))
                    first_latency = sum(float(graph[u][v]["latency"])
                                        for u, v in zip(first, first[1:]))
                    alt_latency = sum(float(graph[u][v]["latency"])
                                      for u, v in zip(alternate, alternate[1:]))
                    if capacity > 0 and alt_latency <= first_latency * 1.6:
                        return source, destination, 0.25 * capacity, first, alternate
    raise RuntimeError("could not find a short pair with edge-disjoint alternatives")


def run_case(name, graph, source, destination, demand, alpha,
             alternate_path=None):
    graph = nx.Graph(graph)
    for _, attrs in graph.nodes(data=True):
        attrs.setdefault("type", "router")
    envs = {}
    for policy in ("dijkstra_static", "dijkstra_load_aware",
                   "dijkstra_load_aware_k", "greedy_min_util"):
        gen = RepeatingFlow(list(graph.nodes), source, destination, demand)
        env = NetworkRoutingEnv(
            graph, NetworkEnvConfig(k_paths=4, max_steps=80, intensity=0.0,
                                    hosts_per_router_fraction=None, minimum_hosts=0),
            gen)
        env.reset(seed=812)
        max_utils, losses, chosen_paths = [], [], []
        for _step in range(80):
            decision = choose_decision(policy, env, np.random.default_rng(1), alpha=alpha)
            if decision.explicit_path is not None:
                _obs, _reward, _term, _trunc, info = step_explicit_path(env, decision.explicit_path)
            else:
                _obs, _reward, _term, _trunc, info = env.step(decision.action)
            max_utils.append(float(info.get("step_max_backbone_utilization", 0.0)))
            losses.append(float(info.get("path_loss", 1.0)))
            chosen_paths.append(info.get("selected_path"))
        max_utils = np.asarray(max_utils)
        losses = np.asarray(losses)
        alternative_util = None
        if policy == "dijkstra_static" and alternate_path is not None:
            alternative_util = max((env.loads.get(env._key(u, v), 0.0)
                                    / max(float(env.graph[u][v].get("capacity", 0.0)), 1e-12)
                                    for u, v in zip(alternate_path, alternate_path[1:])),
                                   default=0.0)
        envs[policy] = {"overload_fraction": float(np.mean(max_utils > 0.9),),
                        "mean_loss": float(np.mean(losses)),
                        "mean_max_backbone_utilization": float(np.mean(max_utils)),
                        "static_unused_alternative_max_util": alternative_util,
                        "last_path": chosen_paths[-1]}
    print(f"\n{name}: OD {source}->{destination}, demand={demand:.4f} Mbps")
    for policy in ("dijkstra_static", "dijkstra_load_aware",
                   "dijkstra_load_aware_k", "greedy_min_util"):
        row = envs[policy]
        print(f"{policy:24s} overload_fraction={row['overload_fraction']:.4f} "
              f"mean_loss={row['mean_loss']:.6f} "
              f"mean_max_backbone_util={row['mean_max_backbone_utilization']:.4f} "
              f"last_path={row['last_path']}")
        if policy == "dijkstra_static" and row["static_unused_alternative_max_util"] is not None:
            print(f"  static unused edge-disjoint alternative max util="
                  f"{row['static_unused_alternative_max_util']:.6f}")
    return envs


def main():
    alpha_config = json.loads(ALPHA_PATH.read_text(encoding="utf-8"))
    alpha = float(alpha_config["dijkstra_load_aware_alpha"])
    graph, source, destination, demand = diamond_graph()
    diamond = run_case("synthetic diamond", graph, source, destination, demand, alpha,
                       alternate_path=("s", "b", "t"))
    if diamond["dijkstra_static"]["overload_fraction"] <= diamond["greedy_min_util"]["overload_fraction"]:
        raise AssertionError("static policy did not overload the diamond's shortest route")

    splits = json.loads((DATA / "splits.json").read_text(encoding="utf-8"))
    entry = next(row for row in splits["train"] if row["name"] == "newyork")
    graph = load_graph({**entry, "split": "train"}, DATA)
    source, destination, demand, first_path, alternate = find_real_pair(graph)
    print(f"Real topology paths: static={first_path}; alternate={alternate}")
    real = run_case("real New York", graph, source, destination, demand, alpha,
                    alternate_path=alternate)
    if real["dijkstra_static"]["overload_fraction"] <= real["greedy_min_util"]["overload_fraction"]:
        raise AssertionError("chosen real-graph scenario failed to distinguish static from greedy")


if __name__ == "__main__":
    main()
