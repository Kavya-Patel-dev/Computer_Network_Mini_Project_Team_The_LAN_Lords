"""Ready-tensor replay states and a PyG-order-compatible custom graph collate."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Sequence

import numpy as np
import torch

from .obs import ModelState


@dataclass(frozen=True, slots=True)
class TensorModelState:
    """Replay representation; all dynamic state arrays are CPU tensors."""

    graph_id: str
    node_features: torch.Tensor
    edge_index: torch.Tensor
    edge_attr: torch.Tensor
    flow_features: torch.Tensor
    candidate_paths: torch.Tensor
    candidate_features: torch.Tensor
    action_mask: torch.Tensor
    fingerprint: bytes
    history_node_features: torch.Tensor | None = None
    history_edge_attr: torch.Tensor | None = None

    @property
    def num_nodes(self) -> int:
        return int(self.node_features.shape[0])


def _fingerprint(state: ModelState) -> bytes:
    digest = hashlib.blake2b(digest_size=16)
    digest.update(state.graph_id.encode("utf-8"))
    for array in (state.node_features, state.edge_attr, state.flow_features,
                  state.candidate_paths, state.candidate_features,
                  state.action_mask):
        contiguous = np.ascontiguousarray(array)
        digest.update(str(contiguous.dtype).encode("ascii"))
        digest.update(np.asarray(contiguous.shape, dtype=np.int64).tobytes())
        digest.update(contiguous.tobytes())
    for array in (state.history_node_features, state.history_edge_attr):
        if array is not None:
            contiguous = np.ascontiguousarray(array)
            digest.update(str(contiguous.dtype).encode("ascii"))
            digest.update(np.asarray(contiguous.shape, dtype=np.int64).tobytes())
            digest.update(contiguous.tobytes())
    return digest.digest()


def tensorize_state(state: ModelState, edge_index: torch.Tensor) -> TensorModelState:
    """Copy mutable state into replay-owned tensors; edge index is shared."""
    def tensor(array: np.ndarray, dtype: torch.dtype) -> torch.Tensor:
        # Copy once so a following environment observation cannot mutate replay.
        return torch.tensor(np.asarray(array), dtype=dtype, device="cpu")

    return TensorModelState(
        graph_id=state.graph_id,
        node_features=tensor(state.node_features, torch.float32),
        edge_index=edge_index,
        edge_attr=tensor(state.edge_attr, torch.float32),
        flow_features=tensor(state.flow_features, torch.float32),
        candidate_paths=tensor(state.candidate_paths, torch.long),
        candidate_features=tensor(state.candidate_features, torch.float32),
        action_mask=tensor(state.action_mask, torch.bool),
        fingerprint=_fingerprint(state),
        history_node_features=(None if state.history_node_features is None
                               else tensor(state.history_node_features, torch.float32)),
        history_edge_attr=(None if state.history_edge_attr is None
                           else tensor(state.history_edge_attr, torch.float32)),
    )


@dataclass(frozen=True, slots=True)
class CollatedGraphStates:
    x: torch.Tensor
    edge_index: torch.Tensor
    edge_attr: torch.Tensor
    ptr: torch.Tensor


def _tensor_fields(state: ModelState | TensorModelState) -> tuple[
        torch.Tensor, torch.Tensor, torch.Tensor]:
    if isinstance(state, TensorModelState):
        return state.node_features, state.edge_index, state.edge_attr
    return (torch.as_tensor(state.node_features, dtype=torch.float32),
            torch.tensor(np.asarray(state.edge_index), dtype=torch.long),
            torch.as_tensor(state.edge_attr, dtype=torch.float32))


def custom_collate(states: Sequence[ModelState | TensorModelState]
                   ) -> CollatedGraphStates:
    """Concatenate graphs in the same order/offset convention as PyG Batch."""
    if not states:
        raise ValueError("cannot collate an empty state sequence")
    node_parts: list[torch.Tensor] = []
    edge_index_parts: list[torch.Tensor] = []
    edge_attr_parts: list[torch.Tensor] = []
    ptr_values = [0]
    offset = 0
    for state in states:
        x, edge_index, edge_attr = _tensor_fields(state)
        node_parts.append(x)
        edge_index_parts.append(edge_index + offset)
        edge_attr_parts.append(edge_attr)
        offset += int(x.shape[0])
        ptr_values.append(offset)
    return CollatedGraphStates(
        x=torch.cat(node_parts, dim=0),
        edge_index=torch.cat(edge_index_parts, dim=1),
        edge_attr=torch.cat(edge_attr_parts, dim=0),
        ptr=torch.tensor(ptr_values, dtype=torch.long),
    )


def unique_state_batch(states: Sequence[TensorModelState]
                       ) -> tuple[list[TensorModelState], torch.Tensor]:
    """Deduplicate exact feature-identical states, retaining first-seen order."""
    unique: list[TensorModelState] = []
    indices: dict[bytes, int] = {}
    mapping: list[int] = []
    for state in states:
        index = indices.get(state.fingerprint)
        if index is None:
            index = len(unique)
            indices[state.fingerprint] = index
            unique.append(state)
        mapping.append(index)
    return unique, torch.tensor(mapping, dtype=torch.long)
