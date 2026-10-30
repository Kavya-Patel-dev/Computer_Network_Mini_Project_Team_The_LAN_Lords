"""Candidate-level feature definition shared by RF training and routing."""
from __future__ import annotations

import numpy as np

from env.qos import QoSClass


def candidate_features(env, path: tuple[str, ...], time_since_last_failure: int = 10_000) -> np.ndarray:
    if env.flow is None:
        raise ValueError("candidate features require an active flow")
    routers = set(env.router_nodes)
    all_backbone_util = []
    for u, v, attrs in env.graph.edges(data=True):
        if u not in routers or v not in routers:
            continue
        capacity = float(attrs.get("capacity", 0.0))
        if attrs.get("up", True) and capacity > 0:
            all_backbone_util.append(env.loads.get(env._key(u, v), 0.0) / capacity)
    path_backbone_util = []
    residual = []
    path_latency = 0.0
    for u, v in zip(path, path[1:]):
        key = env._key(u, v)
        attrs = env.graph[u][v]
        capacity = float(attrs.get("capacity", 0.0))
        load = env.loads.get(key, 0.0)
        path_latency += float(env.latencies.get(key, attrs.get("latency", 0.0)))
        residual.append(capacity - load)
        if u in routers and v in routers and capacity > 0 and attrs.get("up", True):
            path_backbone_util.append(load / capacity)
    max_util = max(path_backbone_util, default=0.0)
    mean_util = float(np.mean(path_backbone_util)) if path_backbone_util else 0.0
    min_residual = min(residual, default=0.0)
    demand_over_residual = (env.flow.demand_mbps / max(min_residual, 1e-9))
    qos = [float(env.flow.qos_class == cls) for cls in QoSClass]
    return np.asarray([
        max_util, mean_util, float(len(path) - 1), path_latency,
        min_residual, demand_over_residual, *qos,
        max(all_backbone_util, default=0.0),
        float(np.mean(all_backbone_util)) if all_backbone_util else 0.0,
        float(len(env.active_flows)), float(time_since_last_failure),
    ], dtype=np.float32)


FEATURE_NAMES = (
    "path_max_backbone_util", "path_mean_backbone_util", "hop_count",
    "total_latency_ms", "minimum_residual_capacity_mbps",
    "flow_demand_over_residual", "qos_real_time", "qos_streaming",
    "qos_bulk", "qos_background", "network_max_backbone_util",
    "network_mean_backbone_util", "active_flow_count", "time_since_last_failure",
)

