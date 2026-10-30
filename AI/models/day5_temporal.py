"""Optional temporal observation adapter; leaves the Day 4 wrapper untouched."""
from __future__ import annotations

from typing import Any

import numpy as np

from .obs import ModelState, ObservationWrapper


class TemporalObservationWrapper:
    """Day 4 model state plus transformed oldest-first history snapshots."""

    def __init__(self, env: Any, graph_id: str = "graph") -> None:
        self.base = ObservationWrapper(env, graph_id)
        self.env = env
        self.graph_id = str(graph_id)
        self.edge_index = self.base.edge_index
        self.num_actions = self.base.num_actions

    def process(self, observation: dict[str, np.ndarray]) -> ModelState:
        state = self.base.process(observation)
        history_nodes = np.asarray(observation.get("history_nodes"),
                                   dtype=np.float32)
        history_edges = np.asarray(observation.get("history_edges"),
                                   dtype=np.float32)
        if history_nodes.ndim != 3 or history_edges.ndim != 3:
            # Supports synthetic hand-built states without history while still
            # giving the GRU a well-defined one-snapshot sequence.
            history_nodes = state.node_features[None, ...]
            history_edges = np.asarray(observation["edge_features"],
                                       dtype=np.float32)[None, ...]

        transformed: list[np.ndarray] = []
        for raw_edges in history_edges:
            normalized_capacity = (
                np.maximum(raw_edges[:, 4], 0.0)
                / max(self.base._capacity_denominator, 1e-12)
            )
            one_way = np.column_stack((
                np.clip(raw_edges[:, 0], 0.0, 2.0),
                np.log1p(np.maximum(raw_edges[:, 1], 0.0))
                / np.log1p(10_000.0),
                np.clip(raw_edges[:, 2], 0.0, 1.0),
                np.clip(raw_edges[:, 3], 0.0, 1.0),
                normalized_capacity,
            )).astype(np.float32, copy=False)
            transformed.append(np.concatenate((one_way, one_way), axis=0))
        return ModelState(
            graph_id=state.graph_id,
            node_features=state.node_features,
            edge_index=state.edge_index,
            edge_attr=state.edge_attr,
            flow_features=state.flow_features,
            candidate_paths=state.candidate_paths,
            candidate_features=state.candidate_features,
            action_mask=state.action_mask,
            history_node_features=history_nodes.copy(),
            history_edge_attr=np.stack(transformed).astype(np.float32, copy=False),
        )

    @staticmethod
    def scale_reward(raw_reward: float) -> tuple[float, bool]:
        return ObservationWrapper.scale_reward(raw_reward)
