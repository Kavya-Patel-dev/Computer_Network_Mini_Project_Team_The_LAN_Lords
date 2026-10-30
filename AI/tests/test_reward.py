import pytest

from env.qos import QoSClass
from env.qos import QoSProfile, profiles_with_overrides
from env.reward import RewardConfig, route_reward


def test_realtime_more_latency_sensitive_and_flapping_penalty():
    rt = route_reward(QoSClass.REAL_TIME, 100, 0, 1, 1)[0] - route_reward(QoSClass.REAL_TIME, 10, 0, 1, 1)[0]
    bulk = route_reward(QoSClass.BULK, 100, 0, 1, 1)[0] - route_reward(QoSClass.BULK, 10, 0, 1, 1)[0]
    assert rt < bulk
    stable, _ = route_reward(QoSClass.BULK, 10, 0, 1, 1, previous_path=("a", "b"), current_path=("a", "c"))
    assert stable < route_reward(QoSClass.BULK, 10, 0, 1, 1)[0]


def test_reward_uses_minimum_bandwidth_utilization_and_priority():
    profile = QoSProfile(4, 1, 1, 5, 10, 1)
    low, parts = route_reward(QoSClass.STREAMING, 1, 0, 1, 5, profile, priority=4, max_utilization=1.0)
    higher, _ = route_reward(QoSClass.STREAMING, 1, 0, 1, 5, profile, priority=4, max_utilization=0.1)
    assert higher > low and parts["minimum_bandwidth"] < 0 and parts["utilization"] < 0


def test_loss_failure_and_reward_decomposition_and_flapping_sequence():
    # First selected route has no flapping penalty.
    first, first_parts = route_reward(QoSClass.BULK, 10, 0, 5, 5, previous_path=None,
                                      current_path=("s", "a"))
    assert first_parts["flap"] == 0
    prior_cost = first_parts["quality_cost"]
    route = ("s", "a")
    for next_route in (("s", "b"), ("s", "a"), ("s", "b")):
        reward, parts = route_reward(QoSClass.BULK, 10, 0.2, 2, 5,
                                     previous_path=route, current_path=next_route,
                                     previous_quality=prior_cost)
        assert parts["loss"] < 0 and parts["flap"] < 0
        assert sum(v for key, v in parts.items() if key != "quality_cost") == pytest.approx(reward)
        prior_cost = parts["quality_cost"]; route = next_route
    failure, parts = route_reward(QoSClass.REAL_TIME, 0, 0, 0, 1, failed=True)
    assert failure == parts["failure"] < 0
    with_loss, _ = route_reward(QoSClass.BULK, 10, 0.2, 5, 5)
    no_loss, _ = route_reward(QoSClass.BULK, 10, 0, 5, 5)
    assert with_loss < no_loss


def test_all_class_profiles_affect_rewards_and_priority():
    profiles = profiles_with_overrides()
    latency_penalties = {}
    loss_penalties = {}
    for qos, profile in profiles.items():
        latency_penalties[qos] = route_reward(qos, 100, 0, 5, 5, profile)[0] - route_reward(qos, 0, 0, 5, 5, profile)[0]
        loss_penalties[qos] = route_reward(qos, 0, 0.1, 5, 5, profile)[0] - route_reward(qos, 0, 0, 5, 5, profile)[0]
    assert abs(latency_penalties[QoSClass.REAL_TIME]) > abs(latency_penalties[QoSClass.STREAMING]) > abs(latency_penalties[QoSClass.BULK])
    assert abs(loss_penalties[QoSClass.REAL_TIME]) > abs(loss_penalties[QoSClass.STREAMING]) > abs(loss_penalties[QoSClass.BULK])
    low_priority, _ = route_reward(QoSClass.BULK, 200, 0, 1, 5, priority=1)
    high_priority, _ = route_reward(QoSClass.BULK, 200, 0, 1, 5, priority=4)
    assert high_priority < low_priority


def test_flapping_penalty_requires_unnecessary_change():
    config = RewardConfig(meaningful_improvement=0.04)
    prior_quality = route_reward(QoSClass.BULK, 10, 0, 5, 5)[1]["quality_cost"]
    same_quality, parts = route_reward(QoSClass.BULK, 10, 0, 5, 5,
                                       previous_path=("s", "a"), current_path=("s", "b"),
                                       previous_quality=prior_quality, config=config)
    assert parts["flap"] < 0
    improved, improved_parts = route_reward(QoSClass.BULK, 1, 0, 5, 5,
                                            previous_path=("s", "a"), current_path=("s", "b"),
                                            previous_quality=prior_quality, config=config)
    assert improved > same_quality and improved_parts["flap"] == 0
