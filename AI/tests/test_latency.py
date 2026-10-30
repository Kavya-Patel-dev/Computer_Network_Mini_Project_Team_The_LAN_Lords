import math
import pytest

from env.latency import LatencyConfig, link_latency_ms, queueing_latency_ms, utilization
from env.network_env import NetworkEnvConfig, congestion_loss


def test_congestion_metrics_are_finite_monotonic():
    caps = [10, 50, 90, 99, 100, 110]
    rho = [utilization(x, 100) for x in caps]
    delay = [queueing_latency_ms(x, 100) for x in caps]
    loss = [congestion_loss(r) for r in rho]
    assert rho == sorted(rho) and delay == sorted(delay) and loss == sorted(loss)
    assert all(math.isfinite(x) for x in delay)
    assert loss[3] == 0 and loss[4] > 0
    assert link_latency_ms(2.0, 0, 100) > 2.0


def test_mm1_zero_subcritical_near_saturation_and_overload():
    cfg = LatencyConfig(max_queue_ms=500, congestion_epsilon=1e-4)
    zero = queueing_latency_ms(0, 100, cfg)
    half = queueing_latency_ms(50, 100, cfg)
    near = queueing_latency_ms(99.99, 100, cfg)
    saturated = queueing_latency_ms(100, 100, cfg)
    overloaded = queueing_latency_ms(120, 100, cfg)
    assert zero == pytest.approx(0.12) and half == pytest.approx(0.24)
    assert 0 <= zero < half <= near == saturated == overloaded == 500
    assert all(math.isfinite(x) and x >= 0 for x in (zero, half, near, saturated, overloaded))
    assert link_latency_ms(7.0, 0, 100, cfg) == pytest.approx(7.12)
    with pytest.raises(ValueError): NetworkEnvConfig(loss_epsilon=0)
