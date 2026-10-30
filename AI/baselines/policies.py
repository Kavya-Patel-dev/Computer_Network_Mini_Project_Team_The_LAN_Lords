"""Policy definitions used by the Day 3 evaluation harness."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import networkx as nx
import numpy as np

from env.qos import QoSClass
from .features import candidate_features

POLICIES = (
    "random", "dijkstra_static", "dijkstra_load_aware",
    "dijkstra_load_aware_k", "ecmp", "greedy_min_util", "rf_routing",
)


@dataclass(frozen=True)
class Decision:
    action: int
    explicit_path: tuple[str, ...] | None = None
    full_path_not_in_k: bool = False
    ecmp_tie: bool = False


def routers(env) -> set[str]:
    return set(env.router_nodes)


def _active_graph(env, weight_function):
    graph = nx.Graph()
    for node, attrs in env.graph.nodes(data=True):
        if attrs.get("up", True):
            graph.add_node(node)
    for u, v, attrs in env.graph.edges(data=True):
        if (attrs.get("up", True) and float(attrs.get("capacity", 0.0)) > 0
                and u in graph and v in graph):
            graph.add_edge(u, v, weight=float(weight_function(u, v, attrs)))
    return graph


def dynamic_link_cost(env, u: str, v: str, alpha: float) -> float:
    key = env._key(u, v)
    attrs = env.graph[u][v]
    capacity = float(attrs.get("capacity", 0.0))
    if not attrs.get("up", True) or capacity <= 0:
        return math.inf
    utilization = max(0.0, env.loads.get(key, 0.0) / capacity)
    latency = float(env.latencies.get(key, attrs.get("latency", 0.0)))
    cost = latency * (1.0 + alpha * utilization / (1.0 - min(utilization, 0.95)))
    return max(cost, 1e-12)


def dijkstra_path(env, weight_function) -> tuple[str, ...] | None:
    if env.flow is None:
        return None
    active = _active_graph(env, weight_function)
    try:
        return tuple(nx.shortest_path(active, env.flow.source,
                                      env.flow.destination, weight="weight"))
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None


def candidate_dynamic_cost(env, path: tuple[str, ...], alpha: float) -> float:
    return sum(dynamic_link_cost(env, u, v, alpha)
               for u, v in zip(path, path[1:]))


def predicted_max_backbone_utilization(env, path: tuple[str, ...]) -> float:
    if env.flow is None:
        return 0.0
    backbone = routers(env)
    values = []
    for u, v in zip(path, path[1:]):
        if u not in backbone or v not in backbone:
            continue
        attrs = env.graph[u][v]
        capacity = float(attrs.get("capacity", 0.0))
        if not attrs.get("up", True) or capacity <= 0:
            continue
        values.append((env.loads.get(env._key(u, v), 0.0)
                       + env.flow.demand_mbps) / capacity)
    return max(values, default=0.0)


def choose_decision(policy: str, env, rng: np.random.Generator,
                    alpha: float = 1.0, rf_model=None,
                    time_since_last_failure: int = 10_000) -> Decision:
    if policy not in POLICIES:
        raise ValueError(f"unknown policy {policy!r}")
    if env.flow is None or not env._paths.paths:
        return Decision(env.config.k_paths)
    paths = tuple(tuple(path) for path in env._paths.paths)
    if policy == "random":
        return Decision(int(rng.integers(len(paths))))
    if policy == "greedy_min_util":
        index = min(range(len(paths)),
                    key=lambda i: (predicted_max_backbone_utilization(env, paths[i]), i))
        return Decision(index)
    if policy == "dijkstra_static":
        path = dijkstra_path(env, lambda _u, _v, attrs: float(attrs.get("latency", 0.0)))
        if path is None:
            return Decision(env.config.k_paths)
        return Decision(0, path, path not in paths)
    if policy == "dijkstra_load_aware":
        path = dijkstra_path(env, lambda u, v, _attrs: dynamic_link_cost(env, u, v, alpha))
        if path is None:
            return Decision(env.config.k_paths)
        return Decision(0, path, path not in paths)
    if policy == "dijkstra_load_aware_k":
        index = min(range(len(paths)),
                    key=lambda i: (candidate_dynamic_cost(env, paths[i], alpha), i))
        return Decision(index)
    if policy == "ecmp":
        costs = [sum(float(env.latencies.get(env._key(u, v),
                                             env.graph[u][v].get("latency", 0.0)))
                        for u, v in zip(path, path[1:])) for path in paths]
        best = min(costs)
        eligible = [i for i, value in enumerate(costs)
                    if value <= best * 1.01 + 1e-12]
        index = int(rng.choice(eligible))
        return Decision(index, ecmp_tie=len(eligible) > 1)
    # RF chooses the lowest predicted congestion probability, then latency.
    if rf_model is None:
        raise ValueError("rf_routing requires a fitted random-forest model")
    features = np.stack([candidate_features(env, path, time_since_last_failure)
                         for path in paths])
    predicted = rf_model.predict_proba(features)
    positive_columns = np.flatnonzero(np.asarray(rf_model.classes_) == 1)
    probabilities = (predicted[:, int(positive_columns[0])] if len(positive_columns)
                     else np.zeros(len(features), dtype=float))
    latencies = [sum(float(env.latencies.get(env._key(u, v),
                                             env.graph[u][v].get("latency", 0.0)))
                        for u, v in zip(path, path[1:])) for path in paths]
    index = min(range(len(paths)), key=lambda i: (float(probabilities[i]), latencies[i], i))
    return Decision(index)

