"""Evaluation-only support for installing a path outside the K candidates."""
from __future__ import annotations

from typing import Any

from env.paths import PathResult, path_is_available


def step_explicit_path(env, path: tuple[str, ...]):
    """Run one evaluation decision on an explicit full-graph path.

    This temporarily installs a singleton path result immediately before the
    ordinary Day 2 ``step(0)`` call. The environment validates and accounts for
    the route through its existing code, then refreshes its regular K candidates
    for the returned observation. No agent-facing API or default behavior is
    changed.
    """
    path = tuple(path)
    if env.flow is None or not path_is_available(
            env.graph, path, env.flow.source, env.flow.destination):
        raise ValueError("explicit evaluation path is unavailable for the current flow")
    original = env._paths
    env._paths = PathResult((path,), False)
    try:
        return env.step(0)
    except Exception:
        # Preserve the original decision state if the underlying Day 2 step
        # raises before it completes. On success Day 2 refreshes candidates.
        env._paths = original
        raise

