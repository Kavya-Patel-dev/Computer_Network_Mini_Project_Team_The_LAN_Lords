"""QoS-weighted routing reward and path-flapping penalty."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

from .qos import QoSClass, QoSProfile, profiles_with_overrides


@dataclass(frozen=True)
class RewardConfig:
    latency_scale_ms: float = 100.0
    loss_scale: float = 0.1
    failure_penalty: float = 10.0
    flap_penalty: float = 0.5
    meaningful_improvement: float = 0.05
    utilization_weight: float = 0.1

    def __post_init__(self) -> None:
        values = (self.latency_scale_ms, self.loss_scale, self.failure_penalty,
                  self.flap_penalty, self.meaningful_improvement, self.utilization_weight)
        if not all(math.isfinite(v) for v in values) or self.latency_scale_ms <= 0 or self.loss_scale <= 0 or min(values[2:]) < 0:
            raise ValueError("reward scales must be positive and penalties/weights finite nonnegative")


def route_reward(qos_class: QoSClass, latency_ms: float, loss_probability: float,
                 delivered_mbps: float, demand_mbps: float, profile: QoSProfile | None = None,
                 config: RewardConfig | None = None, failed: bool = False,
                 previous_path: Iterable[str] | None = None, current_path: Iterable[str] | None = None,
                 previous_quality: float | None = None, priority: int | None = None,
                 max_utilization: float = 0.0) -> tuple[float, dict[str, float]]:
    cfg = config or RewardConfig(); p = profile or profiles_with_overrides()[QoSClass(qos_class)]
    values = (latency_ms, loss_probability, delivered_mbps, demand_mbps, max_utilization)
    if not all(math.isfinite(x) for x in values) or latency_ms < 0 or not 0 <= loss_probability <= 1 or delivered_mbps < 0 or demand_mbps < 0 or max_utilization < 0:
        raise ValueError("reward metrics must be finite and within physical ranges")
    if failed: return -cfg.failure_penalty * p.reward_weight, {"failure": -cfg.failure_penalty * p.reward_weight, "flap": 0.0}
    latency_cost = p.latency_sensitivity * latency_ms / max(cfg.latency_scale_ms, 1e-12)
    loss_cost = p.loss_sensitivity * loss_probability / max(cfg.loss_scale, 1e-12)
    served = 1.0 if demand_mbps <= 0 else min(1.0, delivered_mbps / demand_mbps)
    bandwidth_credit = served * min(delivered_mbps / max(p.target_bandwidth_mbps, 1e-12), 1.0)
    min_bandwidth_cost = max(0.0, p.min_bandwidth_mbps - delivered_mbps) / max(p.target_bandwidth_mbps, 1e-12)
    utilization_cost = cfg.utilization_weight * min(max(max_utilization, 0.0), 2.0)
    priority_factor = 1.0 + 0.05 * max(0, (p.priority if priority is None else priority) - 1)
    value = p.reward_weight * priority_factor * (bandwidth_credit - latency_cost - loss_cost
                                                  - min_bandwidth_cost - utilization_cost)
    quality_cost = latency_cost + loss_cost + min_bandwidth_cost + utilization_cost - bandwidth_credit
    flap = 0.0
    if previous_path is not None and current_path is not None and tuple(previous_path) != tuple(current_path):
        improvement = 0.0 if previous_quality is None else previous_quality - quality_cost
        if improvement < cfg.meaningful_improvement: flap = cfg.flap_penalty * p.reward_weight * priority_factor
    return value - flap, {"latency": -p.reward_weight * priority_factor * latency_cost,
                          "loss": -p.reward_weight * priority_factor * loss_cost,
                          "bandwidth": p.reward_weight * priority_factor * bandwidth_credit,
                          "minimum_bandwidth": -p.reward_weight * priority_factor * min_bandwidth_cost,
                          "utilization": -p.reward_weight * priority_factor * utilization_cost,
                          "quality_cost": quality_cost,
                          "flap": -flap}
