"""Propagation plus M/M/1 queue delay; link rates are Mbps, delays are ms."""
from __future__ import annotations

from dataclasses import dataclass
import math
import sys


@dataclass(frozen=True)
class LatencyConfig:
    packet_size_bits: float = 12_000.0
    max_queue_ms: float = 10_000.0
    congestion_epsilon: float = 1e-6

    def __post_init__(self) -> None:
        if not all(math.isfinite(x) for x in (self.packet_size_bits, self.max_queue_ms, self.congestion_epsilon)) or self.packet_size_bits <= 0 or self.max_queue_ms <= 0 or not 0 < self.congestion_epsilon < 1:
            raise ValueError("latency parameters must be positive and epsilon in (0,1)")


def utilization(load_mbps: float, capacity_mbps: float) -> float:
    if not math.isfinite(load_mbps) or load_mbps < 0 or not math.isfinite(capacity_mbps) or capacity_mbps <= 0:
        raise ValueError("load must be finite >=0 and capacity finite >0")
    rho = load_mbps / capacity_mbps
    return rho if math.isfinite(rho) else sys.float_info.max


def queueing_latency_ms(load_mbps: float, capacity_mbps: float, config: LatencyConfig | None = None) -> float:
    """M/M/1 mean system time W=1/(mu-lambda), capped at max_queue_ms.

    Convert Mbps to packets/s using packet_size_bits; at rho>=1 return the
    configured finite congestion cap. The epsilon margin avoids near-singular
    arithmetic while preserving monotonic increase up to saturation.
    """
    cfg = config or LatencyConfig(); rho = utilization(load_mbps, capacity_mbps)
    if rho >= 1.0 - cfg.congestion_epsilon: return cfg.max_queue_ms
    service_packets_s = capacity_mbps * 1_000_000 / cfg.packet_size_bits
    arrival_packets_s = load_mbps * 1_000_000 / cfg.packet_size_bits
    denominator = service_packets_s - arrival_packets_s
    if denominator <= 0: return cfg.max_queue_ms
    delay_ms = min(1000.0 / denominator, cfg.max_queue_ms)
    return float(delay_ms if math.isfinite(delay_ms) else cfg.max_queue_ms)


def link_latency_ms(propagation_ms: float, load_mbps: float, capacity_mbps: float,
                    config: LatencyConfig | None = None) -> float:
    if not math.isfinite(propagation_ms) or propagation_ms < 0:
        raise ValueError("propagation latency must be finite and nonnegative ms")
    return propagation_ms + queueing_latency_ms(load_mbps, capacity_mbps, config)
