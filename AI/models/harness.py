"""Runtime adapter that exposes agent_ddqn through the Day 3 run_episode API."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

import numpy as np

from baselines import evaluation as day3
from baselines.policies import Decision, choose_decision as day3_choose
from env.network_env import NetworkRoutingEnv
from .obs import ObservationWrapper


@dataclass
class AgentActionStats:
    decisions: int = 0
    idle_decisions: int = 0
    agreement_greedy: int = 0
    agreement_load_aware_k: int = 0
    lowest_latency: int = 0
    valid_q_values: list[float] = field(default_factory=list)
    action_counts: dict[int, int] = field(default_factory=dict)

    def summary(self) -> dict[str, Any]:
        q = np.asarray(self.valid_q_values, dtype=np.float64)
        n = self.decisions
        return {
            "decisions": n,
            "idle_decisions": self.idle_decisions,
            "agreement_greedy_min_util": self.agreement_greedy / max(1, n),
            "agreement_dijkstra_load_aware_k": self.agreement_load_aware_k / max(1, n),
            "lowest_latency_candidate": self.lowest_latency / max(1, n),
            "action_counts": dict(sorted(self.action_counts.items())),
            "q_count": int(q.size),
            "q_mean": float(q.mean()) if q.size else 0.0,
            "q_std": float(q.std()) if q.size else 0.0,
            "q_min": float(q.min()) if q.size else 0.0,
            "q_max": float(q.max()) if q.size else 0.0,
        }


class AgentPolicyAdapter:
    """Install an agent-only chooser without changing Day 3 policy modules."""

    def __init__(self, agent) -> None:
        self.agent = agent
        self.stats = AgentActionStats()
        self._original = None
        self._env = None
        self._wrapper = None

    def __enter__(self) -> "AgentPolicyAdapter":
        self._original = day3.choose_decision

        def choose(policy, env, rng, alpha=1.0, rf_model=None,
                   time_since_last_failure=10_000):
            if policy != "agent_ddqn":
                return self._original(policy, env, rng, alpha=alpha,
                                      rf_model=rf_model,
                                      time_since_last_failure=time_since_last_failure)
            if env is not self._env:
                self._env = env
                self._wrapper = ObservationWrapper(env, "agent-evaluation")
            observation = env._observation()
            state = self._wrapper.process(observation)
            valid = np.flatnonzero(state.action_mask)
            if len(valid) == 0:
                self.stats.idle_decisions += 1
                return Decision(env.config.k_paths)
            q_values = self.agent.q_values(state)
            action = int(np.argmax(q_values))
            self.stats.decisions += 1
            self.stats.action_counts[action] = self.stats.action_counts.get(action, 0) + 1
            self.stats.valid_q_values.extend(float(q_values[i]) for i in valid)
            greedy = self._original("greedy_min_util", env, rng, alpha=alpha,
                                    rf_model=rf_model,
                                    time_since_last_failure=time_since_last_failure)
            load_aware = self._original("dijkstra_load_aware_k", env, rng,
                                        alpha=alpha, rf_model=rf_model,
                                        time_since_last_failure=time_since_last_failure)
            self.stats.agreement_greedy += int(action == greedy.action)
            self.stats.agreement_load_aware_k += int(action == load_aware.action)
            paths = env._paths.paths
            if paths:
                costs = [sum(float(env.latencies.get(env._key(u, v),
                                                     env.graph[u][v].get("latency", 0.0)))
                                for u, v in zip(path, path[1:]))
                         for path in paths]
                self.stats.lowest_latency += int(action == int(np.argmin(costs)))
            return Decision(action)

        day3.choose_decision = choose
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        day3.choose_decision = self._original
        self._env = None
        self._wrapper = None


@dataclass
class FlowLatencyCapture:
    routed_latencies_ms: list[float] = field(default_factory=list)
    measured_decisions: int = 0
    routed_flows: int = 0
    capped_flows: int = 0

    @property
    def median_latency_ms(self) -> float:
        return float(np.median(self.routed_latencies_ms)) if self.routed_latencies_ms else 0.0

    @property
    def fraction_capped(self) -> float:
        return self.capped_flows / max(1, self.routed_flows)


@contextmanager
def capture_flow_latencies(warmup: int = 100) -> Iterator[FlowLatencyCapture]:
    """Instrument decisions to recover per-flow median and per-hop cap hits."""
    capture = FlowLatencyCapture()
    original_step = NetworkRoutingEnv.step

    def step_with_capture(env: NetworkRoutingEnv, action: int):
        measured = env._steps >= warmup
        path = None
        cap_hit = False
        if (env.flow is not None and 0 <= int(action) < len(env._paths.paths)
                and env._action_mask()[int(action)]):
            path = tuple(env._paths.paths[int(action)])
            for u, v in zip(path, path[1:]):
                key = env._key(u, v)
                existing = env.loads.get(key, 0.0)
                _util, latency, _loss = env._link_metrics(
                    key, existing + env.flow.demand_mbps)
                cap_hit = cap_hit or latency >= env.config.max_queue_ms - 1e-6
        result = original_step(env, action)
        if measured:
            capture.measured_decisions += 1
            info = result[4]
            if path is not None and info.get("selected_path") is not None:
                capture.routed_latencies_ms.append(float(info.get("path_latency_ms", 0.0)))
                capture.routed_flows += 1
                capture.capped_flows += int(cap_hit)
        return result

    NetworkRoutingEnv.step = step_with_capture
    try:
        yield capture
    finally:
        NetworkRoutingEnv.step = original_step


def run_agent_episode(*args, agent, **kwargs):
    """Run policy ``agent_ddqn`` through the unchanged Day 3 harness function."""
    adapter = AgentPolicyAdapter(agent)
    with adapter:
        result = day3.run_episode(*args, policy="agent_ddqn", **kwargs)
    return result, adapter.stats.summary()

