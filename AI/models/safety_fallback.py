"""Inference-time safety wrapper kept outside the learned routing model."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from baselines.policies import choose_decision, predicted_max_backbone_utilization
from env.paths import path_is_available


@dataclass(frozen=True)
class FallbackDecision:
    candidate_paths: tuple[tuple[str, ...], ...]
    q_values: np.ndarray
    chosen_index: int | None
    chosen_path: tuple[str, ...] | None
    fallback_used: bool
    reason: str
    attention_weights: np.ndarray | None


def _path_available(env: Any, path: tuple[str, ...]) -> bool:
    if env.flow is None:
        return False
    return bool(path_is_available(env.graph, path, env.flow.source,
                                  env.flow.destination))


def _fallback_path(env: Any, rng: np.random.Generator) -> tuple[str, ...] | None:
    decision = choose_decision("dijkstra_load_aware", env, rng, alpha=4.0)
    return tuple(decision.explicit_path) if decision.explicit_path is not None else None


def choose_with_fallback(agent: Any, env: Any, state: Any,
                         rng: np.random.Generator, *,
                         enabled: bool = True,
                         action_override: int | None = None) -> FallbackDecision:
    """Choose a candidate, applying the registered fallback rules if enabled.

    Reason codes are `none`, `invalid_action`, `failed_path`, `non_finite_q`,
    `no_valid_candidate`, and `overloaded_candidate`.
    """
    paths = tuple(tuple(path) for path in env._paths.paths)
    with __import__("torch").no_grad():
        q_tensor, attention_tensor = agent.online(state)
    q_values = q_tensor[0].detach().cpu().numpy().astype(np.float64, copy=True)
    attention = (attention_tensor[0].detach().cpu().numpy().copy()
                 if attention_tensor is not None else None)
    mask = np.asarray(state.action_mask, dtype=bool)
    valid = np.flatnonzero(mask[:len(q_values)])
    chosen = (int(action_override) if action_override is not None else
              (int(valid[np.argmax(q_values[valid])]) if len(valid) else None))

    reason = "none"
    chosen_path: tuple[str, ...] | None = None
    if not len(valid):
        reason = "no_valid_candidate"
    elif not np.all(np.isfinite(q_values[valid])):
        reason = "non_finite_q"
    elif chosen is None or chosen < 0 or chosen >= len(mask) or not mask[chosen]:
        reason = "invalid_action"
    elif chosen >= len(paths) or chosen >= len(q_values):
        reason = "invalid_action"
    else:
        chosen_path = paths[chosen]
        if not _path_available(env, chosen_path):
            reason = "failed_path"
        else:
            selected_util = predicted_max_backbone_utilization(env, chosen_path)
            alternatives = [
                predicted_max_backbone_utilization(env, paths[index])
                for index in valid if index != chosen and index < len(paths)
                and _path_available(env, paths[index])
            ]
            if selected_util > 1.0 and any(util < 0.9 for util in alternatives):
                reason = "overloaded_candidate"

    if reason != "none" and enabled:
        chosen_path = _fallback_path(env, rng)
        return FallbackDecision(paths, q_values, None, chosen_path, True,
                                reason, attention)

    if reason != "none":
        # Preserve the model's original action for the no-wrapper comparison.
        if chosen is not None and 0 <= chosen < len(paths):
            chosen_path = paths[chosen]
        return FallbackDecision(paths, q_values, chosen, chosen_path, False,
                                reason, attention)

    return FallbackDecision(paths, q_values, chosen, chosen_path, False,
                            "none", attention)
