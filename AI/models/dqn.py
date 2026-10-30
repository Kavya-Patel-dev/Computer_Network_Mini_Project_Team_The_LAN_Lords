"""Double DQN learner and compact replay for variable-size topologies."""
from __future__ import annotations

from dataclasses import dataclass
import random
import time
from typing import Sequence

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from .gnn import PathScoringGATv2
from .obs import ModelState
from .fast_replay import TensorModelState, tensorize_state, unique_state_batch


@dataclass(slots=True)
class Transition:
    state: ModelState
    action: int
    reward: float
    next_state: ModelState
    terminated: bool
    truncated: bool


class ReplayBuffer:
    def __init__(self, capacity: int = 50_000, seed: int = 0,
                 store_tensors: bool = False) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self.capacity = int(capacity)
        self.items: list[Transition | None] = [None] * self.capacity
        self.position = 0
        self.size = 0
        self.rng = random.Random(seed)
        self.store_tensors = bool(store_tensors)
        self._edge_tensors: dict[str, torch.Tensor] = {}
        self._edge_owners: dict[str, list[np.ndarray]] = {}

    def add(self, transition: Transition) -> None:
        if self.store_tensors:
            state = self._tensor_state(transition.state)
            next_state = self._tensor_state(transition.next_state)
        else:
            state = transition.state.replay_copy()
            next_state = transition.next_state.replay_copy()
        self.items[self.position] = Transition(
            state, int(transition.action), float(transition.reward), next_state,
            bool(transition.terminated), bool(transition.truncated))
        self.position = (self.position + 1) % self.capacity
        self.size = min(self.size + 1, self.capacity)

    def _tensor_state(self, state: ModelState) -> TensorModelState:
        edge_index = self._edge_tensors.get(state.graph_id)
        if edge_index is None:
            edge_index = torch.tensor(state.edge_index, dtype=torch.long, device="cpu")
            self._edge_tensors[state.graph_id] = edge_index
            self._edge_owners[state.graph_id] = [state.edge_index]
        else:
            owners = self._edge_owners[state.graph_id]
            if not any(owner is state.edge_index for owner in owners):
                if not np.array_equal(owners[0], state.edge_index):
                    raise ValueError(f"edge index changed for graph_id={state.graph_id!r}")
                owners.append(state.edge_index)
        return tensorize_state(state, edge_index)

    def sample(self, count: int) -> list[Transition]:
        if count > self.size:
            raise ValueError("not enough replay entries")
        selected = self.rng.sample(range(self.size), count)
        return [self.items[i] for i in selected if self.items[i] is not None]

    def __len__(self) -> int:
        return self.size


def double_dqn_targets(rewards: torch.Tensor, terminated: torch.Tensor,
                       online_next_q: torch.Tensor, target_next_q: torch.Tensor,
                       next_action_mask: torch.Tensor, gamma: float) -> torch.Tensor:
    """Masked Double-DQN targets; truncation is intentionally not terminal."""
    if online_next_q.shape != target_next_q.shape or online_next_q.shape != next_action_mask.shape:
        raise ValueError("next Q values and masks must have matching shapes")
    bootstrap = torch.zeros_like(rewards)
    valid_rows = next_action_mask.any(dim=1)
    if bool(valid_rows.any()):
        valid_online = online_next_q[valid_rows].masked_fill(
            ~next_action_mask[valid_rows], -torch.inf)
        selected = valid_online.argmax(dim=1, keepdim=True)
        valid_target = target_next_q[valid_rows].gather(1, selected).squeeze(1)
        bootstrap[valid_rows] = valid_target
    return rewards + float(gamma) * bootstrap * (~terminated.bool()).to(rewards.dtype)


def learning_done(terminated: bool, truncated: bool) -> bool:
    """Gymnasium timeout is bootstrapped; only true termination stops learning."""
    del truncated
    return bool(terminated)


class DoubleDQNAgent:
    def __init__(self, actions: int = 4, lr: float = 5e-4,
                 gamma: float = 0.95, tau: float = 0.005,
                 batch_size: int = 64, replay_capacity: int = 50_000,
                 learning_starts: int = 2_000, seed: int = 0,
                 use_third_layer: bool = False,
                 store_tensor_replay: bool = False,
                 use_custom_collate: bool = False,
                 reuse_duplicate_states: bool = False) -> None:
        self.device = torch.device("cpu")
        torch.manual_seed(seed)
        self.online = PathScoringGATv2(actions=actions,
                                       use_third_layer=use_third_layer,
                                       use_custom_collate=use_custom_collate).to(self.device)
        self.target = PathScoringGATv2(actions=actions,
                                       use_third_layer=use_third_layer,
                                       use_custom_collate=use_custom_collate).to(self.device)
        self.target.load_state_dict(self.online.state_dict())
        self.target.eval()
        self.optimizer = torch.optim.Adam(self.online.parameters(), lr=lr)
        self.gamma, self.tau = float(gamma), float(tau)
        self.batch_size, self.learning_starts = int(batch_size), int(learning_starts)
        self.replay = ReplayBuffer(replay_capacity, seed,
                                  store_tensors=store_tensor_replay)
        self.reuse_duplicate_states = bool(reuse_duplicate_states)
        self.last_update_timings_ms = {
            "replay_sample_and_scalars": 0.0, "batch_collation": 0.0,
            "online_current_forward": 0.0,
            "online_next_forward": 0.0, "target_forward": 0.0,
            "loss_and_checks": 0.0, "backward": 0.0,
            "optimizer_step": 0.0, "update_total": 0.0,
        }
        self.updates = 0
        self.last_q_mean = 0.0
        self.last_q_abs_max = 0.0

    @torch.no_grad()
    def q_values(self, state: ModelState) -> np.ndarray:
        self.online.eval()
        values, _weights = self.online(state)
        return values[0].cpu().numpy()

    def select_action(self, state: ModelState, epsilon: float,
                      rng: np.random.Generator) -> int:
        valid = np.flatnonzero(state.action_mask)
        if len(valid) == 0:
            return len(state.action_mask)  # environment's idle sentinel K
        if rng.random() < epsilon:
            return int(rng.choice(valid))
        q_values = self.q_values(state)
        return int(np.argmax(q_values))

    def update(self) -> float | None:
        if len(self.replay) < max(self.batch_size, self.learning_starts):
            return None
        update_started = time.perf_counter()
        sample_started = time.perf_counter()
        sample = self.replay.sample(self.batch_size)
        states = [item.state for item in sample]
        next_states = [item.next_state for item in sample]
        actions = torch.tensor([item.action for item in sample], dtype=torch.long)
        rewards = torch.tensor([item.reward for item in sample], dtype=torch.float32)
        terminated = torch.tensor([item.terminated for item in sample], dtype=torch.bool)
        next_masks = torch.stack([
            item.next_state.action_mask if isinstance(item.next_state, TensorModelState)
            else torch.as_tensor(item.next_state.action_mask, dtype=torch.bool)
            for item in sample])
        sample_elapsed = (time.perf_counter() - sample_started) * 1000.0
        self.online.train()
        times = {key: 0.0 for key in self.last_update_timings_ms}
        times["replay_sample_and_scalars"] = sample_elapsed
        if self.reuse_duplicate_states:
            if not all(isinstance(state, TensorModelState)
                       for state in (*states, *next_states)):
                raise RuntimeError("duplicate-state reuse requires tensor replay")
            unique_current, current_map = unique_state_batch(states)
            current_t0 = time.perf_counter()
            q_current_unique, _ = self.online(unique_current)
            current_total = (time.perf_counter() - current_t0) * 1000.0
            current_collate = self.online.last_collate_ms
            times["batch_collation"] += current_collate
            times["online_current_forward"] += max(0.0, current_total - current_collate)
            q_values = q_current_unique.index_select(0, current_map)
            chosen_q = q_values.gather(1, actions.unsqueeze(1)).squeeze(1)
            finite_q = q_values[torch.isfinite(q_values)]
            self.last_q_mean = float(finite_q.detach().mean().cpu())
            self.last_q_abs_max = float(finite_q.detach().abs().max().cpu())

            current_by_fingerprint = {
                state.fingerprint: index
                for index, state in enumerate(unique_current)}
            next_unique: list[TensorModelState] = []
            next_index: dict[bytes, int] = {}
            next_sources: list[tuple[str, int]] = []
            for state in next_states:
                current_index = current_by_fingerprint.get(state.fingerprint)
                if current_index is not None:
                    next_sources.append(("current", current_index))
                    continue
                local_index = next_index.get(state.fingerprint)
                if local_index is None:
                    local_index = len(next_unique)
                    next_index[state.fingerprint] = local_index
                    next_unique.append(state)
                next_sources.append(("next", local_index))
            with torch.no_grad():
                if next_unique:
                    next_t0 = time.perf_counter()
                    q_next_unique, _ = self.online(next_unique)
                    next_total = (time.perf_counter() - next_t0) * 1000.0
                    next_collate = self.online.last_collate_ms
                    times["batch_collation"] += next_collate
                    times["online_next_forward"] += max(0.0, next_total - next_collate)
                else:
                    q_next_unique = torch.empty((0, self.online.actions))
                online_next = torch.stack([
                    q_current_unique[index].detach() if source == "current"
                    else q_next_unique[index]
                    for source, index in next_sources])
                target_states, target_map = unique_state_batch(next_states)
                target_t0 = time.perf_counter()
                target_unique, _ = self.target(target_states)
                target_total = (time.perf_counter() - target_t0) * 1000.0
                target_collate = self.target.last_collate_ms
                times["batch_collation"] += target_collate
                times["target_forward"] += max(0.0, target_total - target_collate)
                target_next = target_unique.index_select(0, target_map)
                targets = double_dqn_targets(rewards, terminated, online_next,
                                             target_next, next_masks, self.gamma)
        else:
            current_t0 = time.perf_counter()
            q_values, _attention = self.online(states)
            current_total = (time.perf_counter() - current_t0) * 1000.0
            current_collate = self.online.last_collate_ms
            times["batch_collation"] += current_collate
            times["online_current_forward"] += max(0.0, current_total - current_collate)
            chosen_q = q_values.gather(1, actions.unsqueeze(1)).squeeze(1)
            finite_q = q_values[torch.isfinite(q_values)]
            self.last_q_mean = float(finite_q.detach().mean().cpu())
            self.last_q_abs_max = float(finite_q.detach().abs().max().cpu())
            with torch.no_grad():
                next_t0 = time.perf_counter()
                online_next, _ = self.online(next_states)
                next_total = (time.perf_counter() - next_t0) * 1000.0
                next_collate = self.online.last_collate_ms
                times["batch_collation"] += next_collate
                times["online_next_forward"] += max(0.0, next_total - next_collate)
                target_t0 = time.perf_counter()
                target_next, _ = self.target(next_states)
                target_total = (time.perf_counter() - target_t0) * 1000.0
                target_collate = self.target.last_collate_ms
                times["batch_collation"] += target_collate
                times["target_forward"] += max(0.0, target_total - target_collate)
                targets = double_dqn_targets(rewards, terminated, online_next,
                                             target_next, next_masks, self.gamma)
        loss_started = time.perf_counter()
        loss = F.smooth_l1_loss(chosen_q, targets)
        if not torch.isfinite(loss):
            raise FloatingPointError("nonfinite Double-DQN Huber loss")
        times["loss_and_checks"] = (time.perf_counter() - loss_started) * 1000.0
        backward_t0 = time.perf_counter()
        self.optimizer.zero_grad(set_to_none=True)
        loss.backward()
        nn.utils.clip_grad_norm_(self.online.parameters(), 10.0)
        times["backward"] = (time.perf_counter() - backward_t0) * 1000.0
        if any(p.grad is not None and not torch.isfinite(p.grad).all()
               for p in self.online.parameters()):
            raise FloatingPointError("nonfinite gradient")
        optim_t0 = time.perf_counter()
        self.optimizer.step()
        with torch.no_grad():
            for target, online in zip(self.target.parameters(), self.online.parameters()):
                target.mul_(1.0 - self.tau).add_(online, alpha=self.tau)
        self.target.eval()
        times["optimizer_step"] = (time.perf_counter() - optim_t0) * 1000.0
        self.last_update_timings_ms = times
        self.updates += 1
        times["update_total"] = (time.perf_counter() - update_started) * 1000.0
        return float(loss.detach().cpu())

    def save(self, path: str, metadata: dict | None = None) -> None:
        torch.save({"online": self.online.state_dict(),
                    "target": self.target.state_dict(),
                    "metadata": metadata or {}}, path)

    def load(self, path: str) -> dict:
        payload = torch.load(path, map_location="cpu", weights_only=False)
        self.online.load_state_dict(payload["online"])
        self.target.load_state_dict(payload.get("target", payload["online"]))
        self.target.eval()
        return payload.get("metadata", {})
