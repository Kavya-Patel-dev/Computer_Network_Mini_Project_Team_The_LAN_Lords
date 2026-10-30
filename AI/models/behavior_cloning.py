"""Behavior cloning utilities for the Day 5.2 expert pretraining stage.

This module is deliberately separate from the Day 4 environment and learner
semantics. It consumes the existing train-only expert observation shards and
uses the same Day 4 observation wrapper and GATv2 path scorer.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import torch
from torch.nn import functional as F

from .obs import ModelState


EXPERT_POLICY = "dijkstra_load_aware_k"
DEFAULT_HOLDOUT_FRACTION = 0.125
DEFAULT_SPLIT_SEED = 20_525


@dataclass(frozen=True, slots=True)
class ExpertIndex:
    graph: str
    seed: int
    shard: str
    row: int
    action: int


@dataclass(frozen=True, slots=True)
class ExpertExample:
    state: ModelState
    action: int
    graph: str
    seed: int


def split_graph_seed_blocks(
    blocks: Iterable[tuple[str, int]],
    train_graphs: Iterable[str],
    test_graphs: Iterable[str],
    holdout_fraction: float = DEFAULT_HOLDOUT_FRACTION,
    seed: int = DEFAULT_SPLIT_SEED,
) -> tuple[set[tuple[str, int]], set[tuple[str, int]]]:
    """Deterministically hold out whole graph/seed blocks within train graphs."""
    if not 0.10 <= holdout_fraction <= 0.15:
        raise ValueError("holdout_fraction must be between 0.10 and 0.15")
    train_names, test_names = set(map(str, train_graphs)), set(map(str, test_graphs))
    unique = set((str(graph), int(block_seed)) for graph, block_seed in blocks)
    outside_train = {graph for graph, _block_seed in unique} - train_names
    if outside_train:
        raise ValueError(f"expert blocks outside train split: {sorted(outside_train)}")
    if {graph for graph, _block_seed in unique} & test_names:
        raise ValueError("locked test graph present in expert blocks")

    rng = np.random.default_rng(int(seed))
    holdout: set[tuple[str, int]] = set()
    for graph in sorted(train_names):
        graph_blocks = sorted(block for block in unique if block[0] == graph)
        if len(graph_blocks) < 2:
            raise ValueError(f"train graph {graph!r} has fewer than two expert blocks")
        count = max(1, int(round(len(graph_blocks) * holdout_fraction)))
        count = min(count, len(graph_blocks) - 1)
        order = rng.permutation(len(graph_blocks))
        holdout.update(graph_blocks[int(index)] for index in order[:count])
    training = unique - holdout
    if not training or not holdout or training & holdout:
        raise AssertionError("invalid graph-seed block split")
    return training, holdout


def masked_bc_loss(
    q_values: torch.Tensor,
    action_mask: torch.Tensor,
    expert_actions: torch.Tensor,
    margin: float = 0.8,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Return total, cross-entropy, and DQfD large-margin losses.

    Invalid actions are removed from both the softmax and the margin maximum.
    The margin is zero for the expert action and ``margin`` for every other
    valid action, matching the large-margin DQfD classification objective.
    """
    if q_values.ndim != 2 or action_mask.shape != q_values.shape:
        raise ValueError("q_values and action_mask must have matching (B, A) shapes")
    if expert_actions.shape != (q_values.shape[0],):
        raise ValueError("expert_actions must have shape (B,)")
    valid = action_mask.to(dtype=torch.bool, device=q_values.device)
    actions = expert_actions.to(dtype=torch.long, device=q_values.device)
    if not bool(valid.any(dim=1).all()):
        raise ValueError("every BC example must have at least one valid action")
    if bool((actions < 0).any()) or bool((actions >= q_values.shape[1]).any()):
        raise ValueError("expert action index is outside the action dimension")
    row = torch.arange(q_values.shape[0], device=q_values.device)
    if not bool(valid[row, actions].all()):
        raise ValueError("expert action is masked as invalid")

    masked_q = q_values.masked_fill(~valid, -torch.inf)
    cross_entropy = F.cross_entropy(masked_q, actions)
    expert_q = masked_q[row, actions]
    margin_cost = torch.full_like(q_values, float(margin))
    margin_cost[row, actions] = 0.0
    margin_scores = (q_values + margin_cost).masked_fill(~valid, -torch.inf)
    margin_loss = (margin_scores.max(dim=1).values - expert_q).clamp_min(0.0).mean()
    return cross_entropy + margin_loss, cross_entropy, margin_loss


def bc_optimizer_step(model, optimizer, examples: Sequence[ExpertExample],
                     margin: float = 0.8,
                     max_grad_norm: float = 10.0) -> dict[str, float]:
    """Apply one deterministic minibatch BC update and return real losses."""
    if not examples:
        raise ValueError("cannot update on an empty BC minibatch")
    model.train()
    q_values, _attention = model([row.state for row in examples])
    masks = torch.as_tensor(np.stack([row.state.action_mask for row in examples]),
                            dtype=torch.bool)
    actions = torch.as_tensor([row.action for row in examples], dtype=torch.long)
    loss, ce, margin_loss = masked_bc_loss(q_values, masks, actions, margin)
    optimizer.zero_grad(set_to_none=True)
    loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), float(max_grad_norm))
    if any(parameter.grad is not None and not torch.isfinite(parameter.grad).all()
           for parameter in model.parameters()):
        raise FloatingPointError("nonfinite BC gradient")
    optimizer.step()
    return {"loss": float(loss.detach().cpu()),
            "cross_entropy": float(ce.detach().cpu()),
            "margin_loss": float(margin_loss.detach().cpu())}


def read_expert_indices(
    expert_root: str | Path,
    train_graphs: Iterable[str],
    test_graphs: Iterable[str],
    expert_policy: str = EXPERT_POLICY,
) -> tuple[dict[str, object], list[ExpertIndex]]:
    """Index only requested expert labels and reject non-train shard graphs."""
    root = Path(expert_root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    train_names, test_names = set(map(str, train_graphs)), set(map(str, test_graphs))
    shard_graphs = {str(row["graph"]) for row in manifest["shards"]}
    if not shard_graphs <= train_names:
        raise ValueError(f"expert manifest includes non-train graphs: {sorted(shard_graphs - train_names)}")
    if shard_graphs & test_names:
        raise ValueError("locked test graph present in the expert manifest")

    indices: list[ExpertIndex] = []
    for shard in manifest["shards"]:
        shard_path = str(shard["path"])
        with np.load(root / shard_path, allow_pickle=False) as data:
            if len(data["action"]) != len(data["expert"]):
                raise ValueError(f"expert/action row count mismatch in {shard_path}")
            graph_values = data["graph_name"]
            seeds = data["seed"]
            experts = data["expert"]
            actions = data["action"]
            for row in np.flatnonzero(experts == expert_policy):
                graph = str(graph_values[row])
                if graph != str(shard["graph"]):
                    raise ValueError(f"graph label mismatch in expert shard {shard_path}")
                if graph not in train_names or graph in test_names:
                    raise ValueError(f"non-train graph {graph!r} in expert shard")
                indices.append(ExpertIndex(graph, int(seeds[row]), shard_path,
                                           int(row), int(actions[row])))
    if not indices:
        raise ValueError(f"no expert rows found for policy {expert_policy!r}")
    if any(index.action < 0 or index.action >= 4 for index in indices):
        raise ValueError("expert action index is outside K=4")
    return manifest, indices


def build_examples(
    expert_root: str | Path,
    indices: Sequence[ExpertIndex],
    graph_contexts: dict[str, tuple[object, object]],
    progress=None,
) -> list[ExpertExample]:
    """Apply the Day 4 wrapper to selected rows from existing raw shards."""
    root = Path(expert_root)
    by_shard: dict[str, list[ExpertIndex]] = {}
    for index in indices:
        by_shard.setdefault(index.shard, []).append(index)
    examples: list[ExpertExample] = []
    ordered_shards = sorted(by_shard)
    for shard_no, shard_path in enumerate(ordered_shards, start=1):
        with np.load(root / shard_path, allow_pickle=False) as data:
            static_edge_index = np.asarray(data["edge_index_static"], dtype=np.int64)
            for index in by_shard[shard_path]:
                if index.graph not in graph_contexts:
                    raise ValueError(f"missing train graph context for {index.graph!r}")
                env, wrapper = graph_contexts[index.graph]
                if not np.array_equal(static_edge_index, np.asarray(env.edge_index)):
                    raise ValueError(f"expert edge order changed for graph {index.graph!r}")
                raw_observation = {
                    key: data[f"obs_{key}"][index.row]
                    for key in ("node_features", "edge_features", "flow_features",
                                "candidate_paths", "action_mask", "edge_index",
                                "history_nodes", "history_edges")
                }
                if not np.array_equal(raw_observation["edge_index"], static_edge_index):
                    raise ValueError(f"row edge order changed in {shard_path}")
                state = wrapper.process(raw_observation)
                if index.action >= len(state.action_mask) or not state.action_mask[index.action]:
                    raise ValueError(f"invalid expert action in {shard_path} row {index.row}")
                examples.append(ExpertExample(state, index.action,
                                              index.graph, index.seed))
        if progress is not None:
            progress(shard_no, len(ordered_shards), len(examples))
    return examples


def example_block_split(
    examples: Sequence[ExpertExample],
    training_blocks: set[tuple[str, int]],
    holdout_blocks: set[tuple[str, int]],
) -> tuple[list[ExpertExample], list[ExpertExample]]:
    """Partition examples while enforcing whole-block separation."""
    if training_blocks & holdout_blocks:
        raise ValueError("train and holdout graph-seed blocks overlap")
    train_examples, val_examples = [], []
    seen: set[tuple[str, int]] = set()
    for example in examples:
        block = (example.graph, int(example.seed))
        seen.add(block)
        if block in training_blocks:
            train_examples.append(example)
        elif block in holdout_blocks:
            val_examples.append(example)
        else:
            raise ValueError(f"example belongs to an unassigned block: {block}")
    if seen - (training_blocks | holdout_blocks):
        raise AssertionError("unassigned graph-seed block")
    if not train_examples or not val_examples:
        raise ValueError("graph-seed split produced an empty partition")
    return train_examples, val_examples


@torch.no_grad()
def evaluate_bc(model, examples: Sequence[ExpertExample], batch_size: int = 64,
                max_examples: int | None = None) -> dict[str, float]:
    """Evaluate loss and top-1 agreement in stable input order."""
    model.eval()
    selected = examples if max_examples is None else examples[:max_examples]
    totals: list[float] = []
    ce_values: list[float] = []
    margin_values: list[float] = []
    correct = 0
    q_gaps: list[float] = []
    count = 0
    for start in range(0, len(selected), batch_size):
        batch = selected[start:start + batch_size]
        q_values, _attention = model([row.state for row in batch])
        masks = torch.as_tensor(np.stack([row.state.action_mask for row in batch]),
                                dtype=torch.bool)
        actions = torch.as_tensor([row.action for row in batch], dtype=torch.long)
        total, ce, margin_loss = masked_bc_loss(q_values, masks, actions)
        n = len(batch)
        totals.append(float(total.cpu()) * n)
        ce_values.append(float(ce.cpu()) * n)
        margin_values.append(float(margin_loss.cpu()) * n)
        chosen = q_values.argmax(dim=1)
        correct += int((chosen == actions).sum().item())
        rows = torch.arange(len(batch))
        q_gaps.extend((q_values[rows, actions] - q_values[rows, chosen]).cpu().tolist())
        count += n
    denom = max(1, count)
    return {"loss": sum(totals) / denom,
            "cross_entropy": sum(ce_values) / denom,
            "margin_loss": sum(margin_values) / denom,
            "top1_agreement": correct / denom,
            "mean_q_expert_minus_chosen": float(np.mean(q_gaps)) if q_gaps else float("nan"),
            "examples": float(count)}
