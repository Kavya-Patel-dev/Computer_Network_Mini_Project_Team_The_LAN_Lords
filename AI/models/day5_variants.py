"""Opt-in Day 5.3 learner mechanics; Day 4 modules remain the default path."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
import math
import random
from typing import Any, Sequence

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from .dqn import double_dqn_targets
from .fast_replay import TensorModelState
from .gnn import PathScoringGATv2
from .obs import ModelState


@dataclass(slots=True)
class VariantTransition:
    state: ModelState | TensorModelState
    action: int
    reward: float
    next_state: ModelState | TensorModelState
    terminated: bool
    truncated: bool
    n_steps: int = 1


class NStepAccumulator:
    """Aggregate consecutive stored decisions within each episode."""

    def __init__(self, n: int = 3, gamma: float = 0.95) -> None:
        if n <= 0 or not 0.0 <= gamma <= 1.0:
            raise ValueError("invalid n-step settings")
        self.n, self.gamma = int(n), float(gamma)
        self._queue: deque[VariantTransition] = deque()
        self._episode_id: Any = None

    def _aggregate(self, count: int) -> VariantTransition:
        rows = list(self._queue)[:count]
        first = rows[0]
        total = 0.0
        last = rows[-1]
        used = 0
        for index, row in enumerate(rows):
            total += (self.gamma ** index) * float(row.reward)
            last, used = row, index + 1
            if row.terminated or row.truncated:
                break
        return VariantTransition(first.state, first.action, total, last.next_state,
                                 last.terminated, last.truncated, used)

    def append(self, transition: VariantTransition, episode_id: Any
               ) -> list[VariantTransition]:
        if self._queue and episode_id != self._episode_id:
            raise ValueError("episode changed before its n-step queue was flushed")
        if not self._queue:
            self._episode_id = episode_id
        self._queue.append(transition)
        emitted: list[VariantTransition] = []
        if len(self._queue) >= self.n:
            emitted.append(self._aggregate(self.n))
            self._queue.popleft()
        if transition.terminated or transition.truncated:
            while self._queue:
                emitted.append(self._aggregate(min(self.n, len(self._queue))))
                self._queue.popleft()
            self._episode_id = None
        return emitted

    def flush(self, episode_id: Any, final_state: ModelState | TensorModelState,
              *, terminated: bool = False, truncated: bool = True
              ) -> list[VariantTransition]:
        """Flush a partial tail when the last environment action was unstored."""
        if not self._queue:
            self._episode_id = None
            return []
        if episode_id != self._episode_id:
            raise ValueError("episode changed before its n-step queue was flushed")
        final = self._queue[-1]
        self._queue[-1] = VariantTransition(
            final.state, final.action, final.reward, final_state,
            bool(terminated), bool(truncated), final.n_steps)
        emitted = []
        while self._queue:
            emitted.append(self._aggregate(min(self.n, len(self._queue))))
            self._queue.popleft()
        self._episode_id = None
        return emitted


class SumTree:
    """Compact proportional-sampling tree with a power-of-two leaf base."""

    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self.capacity = int(capacity)
        self.leaf_count = 1 << (self.capacity - 1).bit_length()
        self.tree = np.zeros(2 * self.leaf_count, dtype=np.float64)

    @property
    def total(self) -> float:
        return float(self.tree[1])

    def update(self, index: int, value: float) -> None:
        if not 0 <= index < self.capacity or value < 0:
            raise ValueError("invalid sum-tree update")
        node = self.leaf_count + index
        delta = float(value) - self.tree[node]
        while node:
            self.tree[node] += delta
            node //= 2

    def get(self, mass: float) -> tuple[int, float]:
        if not 0.0 <= mass < self.total:
            if math.isclose(mass, self.total) and self.total > 0:
                mass = np.nextafter(self.total, 0.0)
            else:
                raise ValueError("sample mass is outside the sum tree")
        node = 1
        while node < self.leaf_count:
            left = 2 * node
            if mass < self.tree[left]:
                node = left
            else:
                mass -= self.tree[left]
                node = left + 1
        index = node - self.leaf_count
        return index, float(self.tree[node])


class VariantReplay:
    """Uniform or proportional replay, with normalized importance weights."""

    def __init__(self, capacity: int = 25_000, prioritized: bool = False,
                 alpha: float = 0.6, seed: int = 0,
                 compact_history: bool = False) -> None:
        self.capacity = int(capacity)
        self.items: list[VariantTransition | None] = [None] * self.capacity
        self.prioritized = bool(prioritized)
        self.alpha = float(alpha)
        self.compact_history = bool(compact_history)
        self.tree = SumTree(self.capacity) if prioritized else None
        self.position = 0
        self.size = 0
        self.max_priority = 1.0
        self.rng = random.Random(int(seed))

    def add(self, transition: VariantTransition) -> None:
        index = self.position
        if self.compact_history:
            transition = VariantTransition(
                self._compact(transition.state), transition.action,
                transition.reward, self._compact(transition.next_state),
                transition.terminated, transition.truncated, transition.n_steps)
        self.items[index] = transition
        if self.tree is not None:
            self.tree.update(index, self.max_priority ** self.alpha)
        self.position = (self.position + 1) % self.capacity
        self.size = min(self.size + 1, self.capacity)

    @staticmethod
    def _compact(state: ModelState | TensorModelState
                 ) -> ModelState | TensorModelState:
        if isinstance(state, TensorModelState):
            return replace(
                state,
                history_node_features=(None if state.history_node_features is None
                                       else state.history_node_features.to(torch.float16)),
                history_edge_attr=(None if state.history_edge_attr is None
                                   else state.history_edge_attr.to(torch.float16)),
            )
        return replace(
            state,
            history_node_features=(None if state.history_node_features is None
                                   else np.asarray(state.history_node_features).astype(
                                       np.float16, copy=True)),
            history_edge_attr=(None if state.history_edge_attr is None
                               else np.asarray(state.history_edge_attr).astype(
                                   np.float16, copy=True)),
        )

    def sample(self, batch_size: int, beta: float = 0.4
               ) -> tuple[list[VariantTransition], np.ndarray, np.ndarray, np.ndarray]:
        if batch_size > self.size:
            raise ValueError("not enough replay entries")
        if self.tree is None:
            indices = self.rng.sample(range(self.size), batch_size)
            weights = np.ones(batch_size, dtype=np.float32)
            probabilities = np.full(batch_size, 1.0 / self.size, dtype=np.float64)
        else:
            total = self.tree.total
            if total <= 0:
                raise RuntimeError("prioritized replay has zero total priority")
            segment = total / batch_size
            indices, probabilities = [], []
            for row in range(batch_size):
                mass = self.rng.uniform(segment * row, segment * (row + 1))
                index, priority = self.tree.get(mass)
                if index >= self.size:
                    # Unused leaves have zero weight; numerical endpoint only.
                    index = self.rng.randrange(self.size)
                    priority = float(self.tree.tree[self.tree.leaf_count + index])
                indices.append(index)
                probabilities.append(priority / total)
            probabilities = np.asarray(probabilities, dtype=np.float64)
            weights = np.power(self.size * probabilities, -float(beta))
            weights /= max(float(weights.max()), 1e-12)
            weights = weights.astype(np.float32)
        selected = [self.items[index] for index in indices]
        if any(item is None for item in selected):
            raise AssertionError("replay sampled an empty slot")
        return selected, np.asarray(indices), weights, np.asarray(probabilities)

    def update_priorities(self, indices: Sequence[int], td_errors: Sequence[float],
                          epsilon: float = 1e-3) -> None:
        if self.tree is None:
            return
        if len(indices) != len(td_errors):
            raise ValueError("priority indices and errors differ in length")
        for index, td_error in zip(indices, td_errors):
            priority = abs(float(td_error)) + float(epsilon)
            if not math.isfinite(priority):
                raise ValueError("priority must be finite")
            self.max_priority = max(self.max_priority, priority)
            self.tree.update(int(index), priority ** self.alpha)

    def __len__(self) -> int:
        return self.size


def beta_at(update: int, total_updates: int, beta_start: float = 0.4) -> float:
    progress = min(1.0, max(0.0, update / max(1, total_updates)))
    return float(beta_start + progress * (1.0 - beta_start))


def planned_update_count(total_steps: int, learning_starts: int = 2_000,
                        update_every: int = 4) -> int:
    """Return the PER annealing horizon after learning-start and update cadence."""
    if update_every <= 0:
        raise ValueError("update_every must be positive")
    return max(1, max(0, int(total_steps) - int(learning_starts))
               // int(update_every))


def auxiliary_utilization_targets(
    state: ModelState | TensorModelState,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Return observation utilization values and its router-backbone mask.

    During training this helper is called on the transition's next state. The
    predictor itself is evaluated on the corresponding current state.
    """
    edge_attr = state.edge_attr
    nodes = state.node_features
    edge_index = state.edge_index
    if not isinstance(edge_attr, torch.Tensor):
        edge_attr = torch.tensor(np.asarray(edge_attr).copy(), dtype=torch.float32)
    if not isinstance(nodes, torch.Tensor):
        nodes = torch.tensor(np.asarray(nodes).copy(), dtype=torch.float32)
    if not isinstance(edge_index, torch.Tensor):
        edge_index = torch.tensor(np.asarray(edge_index).copy(), dtype=torch.long)
    left, right = edge_index[0], edge_index[1]
    mask = (nodes[left, 2] < 0.5) & (nodes[right, 2] < 0.5)
    return edge_attr[:, 0].clamp(0.0, 2.0), mask


def initialize_from_checkpoint(model: PathScoringGATv2, checkpoint: str,
                                *, load_bc: bool = True) -> dict[str, Any]:
    """Copy shape-compatible Day 4/BC weights and identify fresh parameters."""
    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    source = payload["online"] if load_bc else {}
    target = model.state_dict()
    copied: dict[str, torch.Tensor] = {}
    for key, value in target.items():
        source_key = key
        if key.endswith(".weight_mu"):
            source_key = key[:-len("weight_mu")] + "weight"
        elif key.endswith(".bias_mu"):
            source_key = key[:-len("bias_mu")] + "bias"
        if source_key in source and tuple(source[source_key].shape) == tuple(value.shape):
            copied[key] = source[source_key]
    model.load_state_dict(copied, strict=False)
    fresh = sorted(set(target) - set(copied))
    return {"copied_tensors": len(copied), "fresh_parameter_tensors": fresh,
            "source": "bc_init.pt" if load_bc else "random initialization"}


class VariantDQNAgent:
    """DQN update path for optional Day 5 flags; no changes to Day 4 agent."""

    def __init__(self, *, flags: dict[str, Any] | None = None,
                 actions: int = 4, learning_rate: float = 1e-4,
                 gamma: float = 0.95, tau: float = 0.002,
                 replay_capacity: int = 25_000, batch_size: int = 64,
                 learning_starts: int = 2_000, seed: int = 0,
                 n_step: int = 1, prioritized: bool = False,
                 total_updates: int = 1_000, auxiliary_bc_weight: float = 0.0,
                 gradient_clip_norm: float = 10.0) -> None:
        torch.manual_seed(int(seed))
        self.flags = dict(flags or {})
        self.gamma, self.tau = float(gamma), float(tau)
        self.batch_size, self.learning_starts = int(batch_size), int(learning_starts)
        self.n_step = int(n_step)
        self.total_updates = int(total_updates)
        self.auxiliary_bc_weight = float(auxiliary_bc_weight)
        self.gradient_clip_norm = float(gradient_clip_norm)
        self.online = PathScoringGATv2(
            actions=actions, use_custom_collate=True,
            dueling=bool(self.flags.get("dueling", False)),
            noisy_net=bool(self.flags.get("noisy_net", False)),
            gru_history=bool(self.flags.get("gru_history", False)),
            use_mlp_encoder=bool(self.flags.get("mlp_encoder", False)),
            auxiliary_utilization=bool(self.flags.get("auxiliary_utilization", False)),
            noisy_sigma0=float(self.flags.get("noisy_sigma0", 0.1)),
        )
        self.target = PathScoringGATv2(
            actions=actions, use_custom_collate=True,
            dueling=bool(self.flags.get("dueling", False)),
            noisy_net=bool(self.flags.get("noisy_net", False)),
            gru_history=bool(self.flags.get("gru_history", False)),
            use_mlp_encoder=bool(self.flags.get("mlp_encoder", False)),
            auxiliary_utilization=bool(self.flags.get("auxiliary_utilization", False)),
            noisy_sigma0=float(self.flags.get("noisy_sigma0", 0.1)),
        )
        self.target.load_state_dict(self.online.state_dict())
        self.target.eval()  # target NoisyLinear layers use mu parameters only
        self.optimizer = torch.optim.Adam(self.online.parameters(), lr=learning_rate)
        compact_history = bool(self.flags.get(
            "compact_history", self.flags.get("gru_history", False)))
        self.replay = VariantReplay(replay_capacity, prioritized, 0.6, seed,
                                    compact_history=compact_history)
        self.n_step_accumulator = NStepAccumulator(self.n_step, self.gamma)
        self.updates = 0
        self.last_loss = math.nan
        self.last_q_abs_max = 0.0

    @property
    def noisy_net(self) -> bool:
        return bool(self.flags.get("noisy_net", False))

    @torch.no_grad()
    def q_values(self, state: ModelState | TensorModelState) -> np.ndarray:
        self.online.eval()
        values, _attention = self.online(state)
        return values[0].cpu().numpy()

    def select_action(self, state: ModelState | TensorModelState, epsilon: float,
                      rng: np.random.Generator) -> int:
        valid = np.flatnonzero(state.action_mask)
        if not len(valid):
            return len(state.action_mask)
        if not self.noisy_net and rng.random() < float(epsilon):
            return int(rng.choice(valid))
        if self.noisy_net:
            self.online.train()
            self.online.reset_noise()
            with torch.no_grad():
                values, _ = self.online(state)
            self.online.eval()
            return int(np.argmax(values[0].cpu().numpy()))
        return int(np.argmax(self.q_values(state)))

    def add_transition(self, transition: VariantTransition,
                       episode_id: Any) -> int:
        emitted = self.n_step_accumulator.append(transition, episode_id)
        for item in emitted:
            self.replay.add(item)
        return len(emitted)

    def end_episode(self, episode_id: Any,
                    final_state: ModelState | TensorModelState,
                    *, terminated: bool = False, truncated: bool = True) -> int:
        emitted = self.n_step_accumulator.flush(
            episode_id, final_state, terminated=terminated, truncated=truncated)
        for item in emitted:
            self.replay.add(item)
        return len(emitted)

    def update(self, expert_batch: Sequence[Any] | None = None) -> float | None:
        if len(self.replay) < max(self.batch_size, self.learning_starts):
            return None
        beta = beta_at(self.updates, self.total_updates)
        sample, indices, weights_np, _probabilities = self.replay.sample(
            self.batch_size, beta)
        states = [row.state for row in sample]
        next_states = [row.next_state for row in sample]
        actions = torch.as_tensor([row.action for row in sample], dtype=torch.long)
        rewards = torch.as_tensor([row.reward for row in sample], dtype=torch.float32)
        terminated = torch.as_tensor([row.terminated for row in sample], dtype=torch.bool)
        n_steps = torch.as_tensor([row.n_steps for row in sample], dtype=torch.float32)
        next_masks = torch.stack([
            row.next_state.action_mask if isinstance(row.next_state, TensorModelState)
            else torch.as_tensor(row.next_state.action_mask, dtype=torch.bool)
            for row in sample]).bool()
        importance = torch.as_tensor(weights_np, dtype=torch.float32)
        self.online.train()
        if self.noisy_net:
            self.online.reset_noise()
        q_values, _attention = self.online(states)
        chosen_q = q_values.gather(1, actions.unsqueeze(1)).squeeze(1)
        finite_q = q_values[torch.isfinite(q_values)]
        self.last_q_abs_max = float(finite_q.detach().abs().max().cpu())
        with torch.no_grad():
            online_next, _ = self.online(next_states)
            target_next, _ = self.target(next_states)
            valid_rows = next_masks.any(dim=1)
            bootstrap = torch.zeros_like(rewards)
            if bool(valid_rows.any()):
                selected = online_next[valid_rows].masked_fill(
                    ~next_masks[valid_rows], -torch.inf).argmax(dim=1)
                selected_target = target_next[valid_rows].gather(
                    1, selected.unsqueeze(1)).squeeze(1)
                bootstrap[valid_rows] = selected_target
            targets = rewards + (self.gamma ** n_steps) * bootstrap * (~terminated).float()
        td_errors = targets - chosen_q
        per_item = F.smooth_l1_loss(chosen_q, targets, reduction="none")
        loss = (per_item * importance).mean()

        if bool(self.flags.get("auxiliary_utilization", False)):
            aux_rows = []
            # Predict next-state utilization from current-state observations.
            # Both snapshots use the same static directed edge row order; guard
            # that invariant so targets cannot silently align to other edges.
            predictions_batch = self.online.auxiliary_predictions(states)
            for current_state, next_state, (pred, router_mask) in zip(
                    states, next_states, predictions_batch):
                current_edge_index = (
                    current_state.edge_index.to(device="cpu", dtype=torch.long)
                    if isinstance(current_state.edge_index, torch.Tensor) else
                    torch.tensor(np.asarray(current_state.edge_index).copy(),
                                 dtype=torch.long))
                next_edge_index = (
                    next_state.edge_index.to(device="cpu", dtype=torch.long)
                    if isinstance(next_state.edge_index, torch.Tensor) else
                    torch.tensor(np.asarray(next_state.edge_index).copy(),
                                 dtype=torch.long))
                if (current_edge_index.shape != next_edge_index.shape
                        or not torch.equal(current_edge_index, next_edge_index)):
                    raise ValueError(
                        "auxiliary utilization requires matching current/next "
                        "static edge order")
                targets_edge, target_mask = auxiliary_utilization_targets(next_state)
                if pred.shape != targets_edge.shape:
                    raise ValueError(
                        "auxiliary prediction and next-state target edge rows "
                        "do not align")
                router_mask = router_mask & target_mask
                aux_rows.append((pred, targets_edge, router_mask))
            edge_losses = []
            for pred, target_edge, router_mask in aux_rows:
                if bool(router_mask.any()):
                    edge_losses.append(F.smooth_l1_loss(
                        pred[router_mask], target_edge[router_mask]))
            aux_loss = (torch.stack(edge_losses).mean() if edge_losses
                        else loss.new_zeros(()))
            loss = loss + float(self.flags.get("auxiliary_weight", 0.1)) * aux_loss

        if self.auxiliary_bc_weight and expert_batch:
            from .behavior_cloning import masked_bc_loss
            expert_states = [example.state for example in expert_batch]
            expert_actions = torch.as_tensor([example.action for example in expert_batch],
                                             dtype=torch.long)
            expert_masks = torch.as_tensor(
                np.stack([example.state.action_mask for example in expert_batch]),
                dtype=torch.bool)
            q_expert, _ = self.online(expert_states)
            bc_loss, _ce, _margin = masked_bc_loss(
                q_expert, expert_masks, expert_actions)
            loss = loss + self.auxiliary_bc_weight * bc_loss

        if not torch.isfinite(loss):
            raise FloatingPointError("nonfinite Day 5.3 loss")
        self.optimizer.zero_grad(set_to_none=True)
        loss.backward()
        nn.utils.clip_grad_norm_(self.online.parameters(), self.gradient_clip_norm)
        if any(parameter.grad is not None
               and not bool(torch.isfinite(parameter.grad).all())
               for parameter in self.online.parameters()):
            raise FloatingPointError("nonfinite Day 5.3 gradient")
        self.optimizer.step()
        with torch.no_grad():
            for target, online in zip(self.target.parameters(), self.online.parameters()):
                target.mul_(1.0 - self.tau).add_(online, alpha=self.tau)
        self.target.eval()
        self.replay.update_priorities(indices, td_errors.detach().cpu().numpy())
        self.updates += 1
        self.last_loss = float(loss.detach().cpu())
        return self.last_loss

    def save(self, path: str, metadata: dict[str, Any] | None = None) -> None:
        torch.save({"online": self.online.state_dict(),
                    "target": self.target.state_dict(),
                    "metadata": metadata or {}, "flags": self.flags}, path)

    def load(self, path: str) -> dict[str, Any]:
        payload = torch.load(path, map_location="cpu", weights_only=False)
        self.online.load_state_dict(payload["online"])
        self.target.load_state_dict(payload.get("target", payload["online"]))
        self.target.eval()
        return payload.get("metadata", {})


def masked_double_dqn_nstep_targets(
    rewards: torch.Tensor, n_steps: torch.Tensor, terminated: torch.Tensor,
    online_next_q: torch.Tensor, target_next_q: torch.Tensor,
    next_action_mask: torch.Tensor, gamma: float,
) -> torch.Tensor:
    """N-step Double-DQN targets; truncations bootstrap and terminations do not."""
    if not (online_next_q.shape == target_next_q.shape == next_action_mask.shape):
        raise ValueError("next Q values and masks must have matching shapes")
    bootstrap = torch.zeros_like(rewards)
    valid_rows = next_action_mask.any(dim=1)
    if bool(valid_rows.any()):
        online_valid = online_next_q[valid_rows].masked_fill(
            ~next_action_mask[valid_rows], -torch.inf)
        actions = online_valid.argmax(dim=1)
        bootstrap[valid_rows] = target_next_q[valid_rows].gather(
            1, actions.unsqueeze(1)).squeeze(1)
    return rewards + torch.pow(torch.as_tensor(gamma, dtype=rewards.dtype), n_steps) * bootstrap * (~terminated.bool()).to(rewards.dtype)
