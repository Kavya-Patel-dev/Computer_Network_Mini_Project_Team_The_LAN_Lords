import numpy as np
import networkx as nx
import pytest
from pathlib import Path

from env.qos import QoSClass, QoSProfile, profiles_with_overrides
from env.traffic import (DiurnalPattern, GravityTrafficGenerator, HotspotTrafficGenerator,
                        PoissonTrafficGenerator, SNDlibReplay, TrafficSpike)


def test_one_request_per_decision_step_is_seeded():
    g = PoissonTrafficGenerator(["a", "b", "c"])
    g.reset(44); a = [g.step()[0] for _ in range(30)]
    g.reset(44); b = [g.step()[0] for _ in range(30)]
    assert a == b and len(a) == 30
    assert all(flow.source != flow.destination for flow in a)


def test_geometric_flow_lifetimes_and_network_intensity_calibration():
    graph = nx.Graph()
    graph.add_edge("a", "b", bandwidth=100.0, latency=1.0)
    graph.add_edge("b", "c", bandwidth=200.0, latency=1.0)
    graph.add_edge("a", "c", bandwidth=300.0, latency=3.0)
    traffic = PoissonTrafficGenerator(["a", "b", "c"], demand_mbps=1.0)
    settings = traffic.configure_for_network(graph, ["a", "b", "c"], 0.6)
    assert settings["median_router_capacity_mbps"] == pytest.approx(200.0)
    assert settings["mean_demand_mbps"] == pytest.approx(25.0)
    assert settings["mean_router_path_hops"] == pytest.approx(4 / 3)
    assert traffic.arrival_rate == 1.0
    assert settings["mean_duration_steps"] == pytest.approx(
        settings["requested_duration_steps"])
    assert (traffic.mean_duration_steps * settings["mean_demand_mbps"]
            * settings["mean_router_path_hops"]
            / settings["total_router_capacity_mbps"]) == pytest.approx(
                settings["achievable_intensity"])
    assert settings["achievable_intensity"] == pytest.approx(0.6)

    traffic.reset(183)
    flows = [traffic.sample_flow() for _ in range(5000)]
    assert all(10.0 <= flow.demand_mbps <= 40.0 for flow in flows)
    assert np.mean([flow.duration_steps for flow in flows]) == pytest.approx(
        settings["mean_duration_steps"], abs=0.5)
    traffic.reset(183)
    assert [flow.duration_steps for flow in flows[:30]] == [
        traffic.sample_flow().duration_steps for _ in range(30)]


def test_sndlib_configured_replay_samples_matrix_proportions_concurrently():
    graph = nx.Graph()
    graph.add_edge("a", "b", bandwidth=100.0, latency=1.0)
    graph.add_edge("b", "c", bandwidth=100.0, latency=1.0)
    graph.add_edge("a", "c", bandwidth=100.0, latency=3.0)
    replay = SNDlibReplay(["a", "b", "c"],
                          [("a", "b", 1.0), ("a", "c", 3.0)])
    settings = replay.configure_for_network(graph, ["a", "b", "c"], 0.9)
    assert settings["target_intensity"] == pytest.approx(0.9)
    replay.reset(291)
    batches = [replay.step() for _ in range(5000)]
    sampled = [flow for batch in batches for flow in batch]
    assert all(len(batch) == 1 for batch in batches)
    a_b = sum((flow.source, flow.destination) == ("a", "b") for flow in sampled)
    a_c = sum((flow.source, flow.destination) == ("a", "c") for flow in sampled)
    assert a_c / a_b == pytest.approx(3.0, rel=0.08)
    assert any(flow.duration_steps > 1 for flow in sampled)


def test_hotspot_gravity_spike_diurnal_and_sndlib_replay():
    hot = HotspotTrafficGenerator(["a", "b", "c"], ["a"], hotspot_multiplier=8)
    hot.reset(2); flows = [hot.sample_flow() for _ in range(200)]
    assert sum("a" in (f.source, f.destination) for f in flows) > 100
    gravity = GravityTrafficGenerator(["a", "b", "c"], {"a": 10, "b": 1, "c": 1},
                                      {("a", "b"): 1, ("a", "c"): 1, ("b", "c"): 10})
    gravity.reset(1); pairs = [(f.source, f.destination) for f in (gravity.sample_flow() for _ in range(3000))]
    rare_pairs = sum(pair in {("b", "c"), ("c", "b")} for pair in pairs)
    assert rare_pairs < 20  # Their configured gravity intensity is 0.1 each versus 10 for a-b/a-c.
    with pytest.raises(ValueError, match="cost missing"):
        GravityTrafficGenerator(["a", "b", "c"], {"a": 1, "b": 1, "c": 1}, {("a", "b"): 1})
    spike = TrafficSpike(5, 2, 4, frozenset({"a"}), frozenset({QoSClass.BULK}))
    flow = hot._flow(source="a", destination="b")
    assert spike.applies(5, flow) and not spike.applies(7, flow)
    # Applied demand rises only inside the configured half-open spike window.
    from env.network_env import NetworkRoutingEnv
    from env.topology import generate_synthetic
    env = NetworkRoutingEnv(generate_synthetic("ba", 6, 4), traffic_spikes=[spike])
    assert env._scheduled_flow(flow, 4).demand_mbps < env._scheduled_flow(flow, 5).demand_mbps
    assert env._scheduled_flow(flow, 5).demand_mbps > env._scheduled_flow(flow, 7).demand_mbps
    diurnal = DiurnalPattern(period=24, baseline=1, amplitude=0.5, peak_time=12)
    env.diurnal_pattern = diurnal
    cycle = [diurnal.multiplier(hour) for hour in range(24)]
    assert max(cycle) == pytest.approx(1.5) and min(cycle) == pytest.approx(0.5)
    assert diurnal.multiplier(0) == pytest.approx(diurnal.multiplier(24))
    assert env._scheduled_flow(flow, 12).demand_mbps > env._scheduled_flow(flow, 0).demand_mbps
    replay = SNDlibReplay(["a", "b"], [("old-a", "old-b", 4.5)], {"old-a": "a", "old-b": "b"})
    replay.reset(1); assert replay.sample_flow().demand_mbps == 4.5
    with pytest.raises(ValueError): SNDlibReplay(["a", "b"], [("x", "y", 1)])
    data = Path(__file__).resolve().parents[1] / "data" / "sndlib-networks-xml" / "abilene.xml"
    from env.topology import load_sndlib
    graph, _ = load_sndlib(data)
    replay_from_file = SNDlibReplay.from_sndlib(list(graph.nodes), data)
    assert list(replay_from_file.demands) == [(s, d, amount) for s, d, amount in load_sndlib(data)[1]]
    assert all(s in graph and d in graph and s != d for s, d, _ in replay_from_file.demands)
    assert sum(v for _, _, v in replay_from_file.demands) == pytest.approx(sum(v for _, _, v in load_sndlib(data)[1]))
    scaled = SNDlibReplay.from_sndlib(list(graph.nodes), data, scale_to_max_util=0.9)
    original = load_sndlib(data)[1]
    assert scaled.demands[0][2] / scaled.demands[1][2] == pytest.approx(original[0][2] / original[1][2])
    link_loads = {tuple(sorted((u, v))): 0.0 for u, v in graph.edges}
    for source, destination, demand in scaled.demands:
        route = nx.shortest_path(graph, source, destination, weight="latency")
        for u, v in zip(route, route[1:]):
            link_loads[tuple(sorted((u, v)))] += demand
    max_util = max(link_loads[tuple(sorted((u, v)))] / attrs["bandwidth"]
                   for u, v, attrs in graph.edges(data=True))
    assert max_util == pytest.approx(0.9, rel=0.01)
    with pytest.raises(ValueError): SNDlibReplay.from_sndlib(["missing"], data)
    partial = SNDlibReplay(["a", "b"], [("missing", "node", 1.0), ("a", "b", 2.0)], incompatible="skip")
    assert partial.demands == (("a", "b", 2.0),)


def test_sndlib_scale_to_max_util_hits_target_and_preserves_proportions():
    graph = nx.Graph()
    graph.add_edge("a", "b", latency=1.0, bandwidth=10.0)
    graph.add_edge("b", "c", latency=1.0, bandwidth=10.0)
    graph.add_edge("a", "c", latency=3.0, bandwidth=10.0)
    demands = [("a", "c", 8.0), ("a", "b", 4.0), ("c", "a", 2.0)]
    replay = SNDlibReplay(["a", "b", "c"], demands,
                          scale_to_max_util=0.9, topology_graph=graph)
    assert replay.demands[0][2] / replay.demands[1][2] == pytest.approx(2.0)
    assert replay.demands[2][2] / replay.demands[1][2] == pytest.approx(0.5)
    loads = {tuple(sorted(edge)): 0.0 for edge in graph.edges}
    for source, destination, demand in replay.demands:
        path = nx.shortest_path(graph, source, destination, weight="latency")
        for u, v in zip(path, path[1:]): loads[tuple(sorted((u, v)))] += demand
    maximum = max(loads[tuple(sorted((u, v)))] / attrs["bandwidth"]
                  for u, v, attrs in graph.edges(data=True))
    assert maximum == pytest.approx(0.9, rel=0.01)


def test_qos_profiles_have_intended_differentiation():
    profiles = profiles_with_overrides()
    assert set(profiles) == set(QoSClass)
    assert profiles[QoSClass.REAL_TIME].priority > profiles[QoSClass.STREAMING].priority > profiles[QoSClass.BULK].priority > profiles[QoSClass.BACKGROUND].priority
    assert profiles[QoSClass.REAL_TIME].latency_sensitivity > profiles[QoSClass.STREAMING].latency_sensitivity > profiles[QoSClass.BULK].latency_sensitivity
    assert profiles[QoSClass.REAL_TIME].loss_sensitivity > profiles[QoSClass.BULK].loss_sensitivity
    assert profiles[QoSClass.STREAMING].target_bandwidth_mbps > profiles[QoSClass.BACKGROUND].target_bandwidth_mbps
    assert profiles[QoSClass.BULK].target_bandwidth_mbps > profiles[QoSClass.STREAMING].target_bandwidth_mbps
    assert profiles[QoSClass.REAL_TIME].reward_weight > profiles[QoSClass.BACKGROUND].reward_weight
    assert profiles_with_overrides({"BULK": QoSProfile(5, 0.1, 0.1, 0, 2, 1)})[QoSClass.BULK].priority == 5
