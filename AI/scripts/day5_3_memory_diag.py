"""Measure replay payload sizes and float16 history fidelity on a train graph."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import train
from models.data_guard import read_partitions
from models.day5_temporal import TemporalObservationWrapper
from models.gnn import PathScoringGATv2
from models.obs import ObservationWrapper, ModelState


def payload_bytes(state: ModelState, include_history: bool = True) -> int:
    arrays = [state.node_features, state.edge_attr, state.flow_features,
              state.candidate_paths, state.candidate_features, state.action_mask]
    if include_history:
        arrays.extend([state.history_node_features, state.history_edge_attr])
    return sum(int(array.nbytes) for array in arrays if array is not None)


def main() -> None:
    torch.set_num_threads(1)
    partitions = read_partitions(ROOT / "data" / "splits.json")
    entry = dict(partitions["train"][0], split="train")
    graph = train.safe_graph_load(entry, "train", partitions)
    env = train.make_training_env(entry, graph, "poisson", 0.05, 500)
    observation, _info = env.reset(seed=20_543)
    base_state = ObservationWrapper(env, entry["name"]).process(observation)
    temporal_state = TemporalObservationWrapper(env, entry["name"]).process(observation)
    directed_edge_bytes = int(temporal_state.history_edge_attr.nbytes)
    history_node_bytes = int(temporal_state.history_node_features.nbytes)
    with_history = 2 * payload_bytes(temporal_state, True)
    without_history = 2 * payload_bytes(base_state, False)
    float16_history = without_history + directed_edge_bytes + history_node_bytes
    replay_capacity = 25_000
    for name, transition_bytes in (
        ("without_history", without_history),
        ("float32_history", with_history),
        ("float16_history", float16_history),
    ):
        payload = transition_bytes * replay_capacity
        print(f"{name}: {transition_bytes} bytes/transition; "
              f"25k payload={payload / (1024**2):.2f} MiB; "
              f"12 workers payload={12 * payload / (1024**3):.2f} GiB")

    model = PathScoringGATv2(actions=4, gru_history=True)
    model.eval()
    half_state = ModelState(
        temporal_state.graph_id, temporal_state.node_features,
        temporal_state.edge_index, temporal_state.edge_attr,
        temporal_state.flow_features, temporal_state.candidate_paths,
        temporal_state.candidate_features, temporal_state.action_mask,
        temporal_state.history_node_features.astype(np.float16),
        temporal_state.history_edge_attr.astype(np.float16),
    )
    with torch.no_grad():
        q32, _ = model(temporal_state)
        q16, _ = model(half_state)
    valid = torch.isfinite(q32) & torch.isfinite(q16)
    max_diff = float((q32[valid] - q16[valid]).abs().max()) if valid.any() else 0.0
    print(f"float16 history Q max absolute difference={max_diff:.8f} "
          f"(tolerance=0.001): {'PASS' if max_diff < 1e-3 else 'FAIL'}")
    env.close()


if __name__ == "__main__":
    main()
