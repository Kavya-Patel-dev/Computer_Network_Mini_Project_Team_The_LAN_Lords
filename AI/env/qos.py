"""Configurable QoS classes for network flows.

Defaults are deliberately exposed as profiles, not hidden policy constants:
latency is measured in ms, loss as a probability, and bandwidth in Mbps.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math


class QoSClass(str, Enum):
    REAL_TIME = "REAL_TIME"
    STREAMING = "STREAMING"
    BULK = "BULK"
    BACKGROUND = "BACKGROUND"


@dataclass(frozen=True)
class QoSProfile:
    priority: int
    latency_sensitivity: float
    loss_sensitivity: float
    min_bandwidth_mbps: float
    target_bandwidth_mbps: float
    reward_weight: float

    def __post_init__(self) -> None:
        values = (self.latency_sensitivity, self.loss_sensitivity, self.reward_weight,
                  self.min_bandwidth_mbps, self.target_bandwidth_mbps)
        if self.priority < 0 or not all(math.isfinite(x) for x in values) or min(values) < 0:
            raise ValueError("QoS priorities and weights must be nonnegative")
        if self.min_bandwidth_mbps < 0 or self.target_bandwidth_mbps < self.min_bandwidth_mbps:
            raise ValueError("QoS target bandwidth must be >= nonnegative minimum bandwidth")


# Relative defaults, documented as policy choices and fully replaceable by users.
DEFAULT_QOS_PROFILES: dict[QoSClass, QoSProfile] = {
    QoSClass.REAL_TIME: QoSProfile(4, 4.0, 3.0, 0.1, 1.0, 1.0),
    QoSClass.STREAMING: QoSProfile(3, 2.0, 2.0, 1.0, 5.0, 0.8),
    QoSClass.BULK: QoSProfile(2, 0.5, 0.5, 1.0, 10.0, 0.6),
    QoSClass.BACKGROUND: QoSProfile(1, 0.25, 0.25, 0.0, 1.0, 0.4),
}


def profiles_with_overrides(overrides: dict[QoSClass | str, QoSProfile] | None = None) -> dict[QoSClass, QoSProfile]:
    profiles = dict(DEFAULT_QOS_PROFILES)
    for key, value in (overrides or {}).items():
        profiles[QoSClass(key)] = value
    return profiles
