"""Agent-only observation features; the Day 2 environment remains untouched."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True, slots=True)
class ModelState:
    """Compact state required by the encoder and path scorer.

    History is optional so existing Day 4 callers retain the same state and
    forward path. Temporal Day 5 variants populate the two history fields.
    """

    graph_id: str
    node_features: np.ndarray
    edge_index: np.ndarray
    edge_attr: np.ndarray
    flow_features: np.ndarray
    candidate_paths: np.ndarray
    candidate_features: np.ndarray
    action_mask: np.ndarray
    history_node_features: np.ndarray | None = None
    history_edge_attr: np.ndarray | None = None

    @property
    def num_nodes(self) -> int:
        return int(self.node_features.shape[0])

    def replay_copy(self) -> "ModelState":
        """Copy mutable state while sharing the graph's immutable edge_index."""
        return ModelState(
            self.graph_id,
            self.node_features.copy(),
            self.edge_index,
            self.edge_attr.copy(),
            self.flow_features.copy(),
            self.candidate_paths.copy(),
            self.candidate_features.copy(),
            self.action_mask.copy(),
            (None if self.history_node_features is None
             else self.history_node_features.copy()),
            (None if self.history_edge_attr is None
             else self.history_edge_attr.copy()),
        )


class ObservationWrapper:
    """Convert a Day 2 observation into fixed-scale Day 4 model inputs."""

    def __init__(self, env: Any, graph_id: str = "graph") -> None:
        self.graph_id = str(graph_id)
        self.env = env
        # The source edge order is the same order used by edge_features.
        base = np.asarray(env.edge_index, dtype=np.int64)
        self.edge_index = np.concatenate((base, base[::-1]), axis=1).copy()
        self.edge_index.setflags(write=False)
        self.edge_lookup = {
            env._key(u, v): i for i, (u, v) in enumerate(env.monitor.edges)
        }
        routers = set(env.router_nodes)
        backbone_caps = [
            float(attrs.get("base_capacity", attrs.get("capacity", 0.0)))
            for u, v, attrs in env.graph.edges(data=True)
            if u in routers and v in routers
            and float(attrs.get("base_capacity", attrs.get("capacity", 0.0))) > 0
        ]
        self.median_backbone_capacity = (
            float(np.median(backbone_caps)) if backbone_caps else 1.0
        )
        all_caps = [
            float(attrs.get("base_capacity", attrs.get("capacity", 0.0)))
            for _, _, attrs in env.graph.edges(data=True)
            if float(attrs.get("base_capacity", attrs.get("capacity", 0.0))) > 0
        ]
        self.max_capacity = max(all_caps, default=1.0)
        # This denominator and normalized capacity column are static for an
        # episode in the common case. Recompute only when a scheduled
        # bandwidth drop changes the capacities exposed by the environment.
        self._capacity_denominator = max(self.max_capacity, 1e-12)
        self._capacity_raw = np.asarray(
            [float(env.graph[u][v].get("capacity", 0.0))
             for u, v in env.monitor.edges], dtype=np.float32)
        self._capacity_normalized = (
            np.maximum(self._capacity_raw, 0.0) / self._capacity_denominator
        ).astype(np.float32, copy=False)
        self._capacity_normalized.setflags(write=False)
        self.num_actions = int(env.config.k_paths)

    def process(self, observation: dict[str, np.ndarray]) -> ModelState:
        nodes = np.asarray(observation["node_features"], dtype=np.float32).copy()
        raw_edges = np.asarray(observation["edge_features"], dtype=np.float32)
        active_capacity = raw_edges[:, 4]
        if not np.array_equal(active_capacity, self._capacity_raw):
            self._capacity_raw = active_capacity.copy()
            self._capacity_normalized = (
                np.maximum(self._capacity_raw, 0.0) / self._capacity_denominator
            ).astype(np.float32, copy=False)
            self._capacity_normalized.setflags(write=False)
        # Day 2 edge feature columns: utilization, measured latency, loss, up, capacity.
        edge_attr_oneway = np.column_stack((
            np.clip(raw_edges[:, 0], 0.0, 2.0),
            np.log1p(np.maximum(raw_edges[:, 1], 0.0)) / np.log1p(10_000.0),
            np.clip(raw_edges[:, 2], 0.0, 1.0),
            np.clip(raw_edges[:, 3], 0.0, 1.0),
            self._capacity_normalized,
        )).astype(np.float32, copy=False)
        # Match bidirectional edge order: all source-order edges, then reverses.
        edge_attr = np.concatenate((edge_attr_oneway, edge_attr_oneway), axis=0)

        raw_flow = np.asarray(observation["flow_features"], dtype=np.float32)
        flow = np.concatenate((
            np.asarray([raw_flow[0] / max(self.median_backbone_capacity, 1e-12)], dtype=np.float32),
            raw_flow[1:6],
            np.asarray([raw_flow[6] / 200.0], dtype=np.float32),
        )).astype(np.float32, copy=False)

        path_array = np.asarray(observation["candidate_paths"], dtype=np.int32)
        candidate_features = np.zeros((self.num_actions, 6), dtype=np.float32)
        host = nodes[:, 2] > 0.5 if nodes.shape[1] > 2 else np.zeros(len(nodes), bool)
        demand = max(float(raw_flow[0]), 1e-12)
        for i, padded_path in enumerate(path_array):
            path = [int(x) for x in padded_path if x >= 0]
            if len(path) < 2:
                continue
            link_ids: list[int] = []
            backbones: list[int] = []
            for a, b in zip(path, path[1:]):
                u, v = self.env.nodes[a], self.env.nodes[b]
                edge_id = self.edge_lookup.get(self.env._key(u, v))
                if edge_id is None:
                    continue
                link_ids.append(edge_id)
                if not host[a] and not host[b]:
                    backbones.append(edge_id)
            if not link_ids:
                continue
            util = raw_edges[link_ids, 0]
            latency = raw_edges[link_ids, 1]
            capacity = raw_edges[link_ids, 4]
            residual_share = np.clip(
                np.min(capacity * (1.0 - util)) / demand, 0.0, 5.0
            )
            backbone_max = float(np.max(raw_edges[backbones, 0])) if backbones else 0.0
            candidate_features[i] = (
                len(path) - 1,
                np.log1p(float(np.sum(latency))),
                float(residual_share),
                float(np.max(util)),
                float(np.mean(util)),
                backbone_max,
            )

        mask = np.asarray(observation["action_mask"][:self.num_actions], dtype=np.bool_).copy()
        return ModelState(
            graph_id=self.graph_id,
            node_features=nodes,
            edge_index=self.edge_index,
            edge_attr=edge_attr,
            flow_features=flow,
            candidate_paths=path_array.copy(),
            candidate_features=candidate_features,
            action_mask=mask,
        )

    @staticmethod
    def scale_reward(raw_reward: float) -> tuple[float, bool]:
        """Wrapper-only reward scaling; returns scaled reward and clip flag."""
        clipped = float(np.clip(raw_reward, -5.0, 2.0))
        return clipped, clipped != float(raw_reward)
