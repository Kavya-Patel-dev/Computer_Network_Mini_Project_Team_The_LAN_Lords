import networkx as nx
import numpy as np
import pytest

from env.events import BandwidthDrop, LinkFailure, RouterFailure
from env.network_env import NetworkEnvConfig, NetworkRoutingEnv
from env.paths import PathResult, path_is_available
from env.qos import QoSClass
from env.reward import route_reward
from env.topology import generate_synthetic
from env.traffic import DiurnalPattern, PoissonTrafficGenerator, TrafficSpike
from env.traffic import Flow, TrafficSpike


def make_env(seed=1, **kwargs):
    graph = generate_synthetic("ba", 10, seed)
    traffic = PoissonTrafficGenerator(sorted(graph.nodes), demand_mbps=5)
    cfg = NetworkEnvConfig(k_paths=3, history_length=3, max_steps=kwargs.pop("max_steps", 6000), **kwargs)
    return NetworkRoutingEnv(graph, cfg, traffic)


def make_diamond(events=()):
    graph = nx.Graph()
    graph.add_nodes_from(["s", "a", "b", "t"])
    graph.add_edge("s", "a", bandwidth=100.0, latency=1.0)
    graph.add_edge("a", "t", bandwidth=100.0, latency=1.0)
    graph.add_edge("s", "b", bandwidth=1000.0, latency=2.0)
    graph.add_edge("b", "t", bandwidth=1000.0, latency=2.0)
    traffic = PoissonTrafficGenerator(["s", "a", "b", "t"], demand_mbps=1)
    env = NetworkRoutingEnv(
        graph,
        NetworkEnvConfig(k_paths=2, hosts_per_router_fraction=None, minimum_hosts=0),
        traffic, events=events)
    env.reset(seed=91)
    return env


def route_for(env, path):
    return next(index for index, candidate in enumerate(env._paths.paths)
                if candidate == tuple(path))


def route_max_utilization(env):
    return max((load / env.graph[u][v]["capacity"]
                for (u, v), load in env.loads.items()
                if env.graph[u][v]["capacity"] > 0), default=0.0)


def test_gym_api_seed_failure_mask_and_reset():
    env = make_env(); obs1, _ = env.reset(seed=77); obs2, _ = env.reset(seed=77)
    assert env.observation_space.contains(obs1) and env.observation_space.contains(obs2)
    for key in obs1: np.testing.assert_array_equal(obs1[key], obs2[key])
    # Reset history contains only copies of the initial/current network state.
    for i in range(env.config.history_length):
        np.testing.assert_array_equal(obs1["history_edges"][i], obs1["edge_features"])
    assert env.action_space.n == 4
    if env._paths.paths:
        path = env._paths.paths[0]; env.fail_link((path[0], path[1]))
        assert all(path_is_available(env.graph, p) for p in env._paths.paths)
    obs, reward, terminated, truncated, info = env.step(int(np.flatnonzero(obs2["action_mask"])[0]))
    assert env.observation_space.contains(obs) and np.isfinite(reward) and isinstance(terminated, bool) and not truncated
    assert "invalid_action" in info


def test_environment_host_fraction_default_attaches_hosts_and_uses_host_pairs():
    graph = generate_synthetic("ba", 12, 220)
    env = NetworkRoutingEnv(graph, NetworkEnvConfig(hosts_per_router_fraction=0.5,
                                                    minimum_hosts=4))
    assert len(env.host_nodes) == 6
    assert len(env.router_nodes) == 12
    env.reset(seed=221)
    assert env.flow.source in env.host_nodes
    assert env.flow.destination in env.host_nodes
    assert env.flow.source != env.flow.destination


def test_environment_host_fraction_honors_minimum_host_count():
    graph = generate_synthetic("ba", 12, 222)
    env = NetworkRoutingEnv(graph, NetworkEnvConfig(hosts_per_router_fraction=0.1,
                                                    minimum_hosts=4))
    assert len(env.host_nodes) == 4


def test_node_features_encode_node_type_endpoints_and_normalized_degree():
    env = make_env(seed=223)
    obs, _ = env.reset(seed=224)
    source, destination = env.flow.source, env.flow.destination
    for node, row in zip(env.nodes, obs["node_features"]):
        assert row[2] == float(env.graph.nodes[node].get("type") == "host")
        assert row[3] == float(node == source)
        assert row[4] == float(node == destination)
        assert row[5] == pytest.approx(env.graph.degree(node) / max(dict(env.graph.degree()).values()))


def test_edge_index_matches_edge_feature_and_history_row_order():
    env = make_env(seed=225)
    obs, info = env.reset(seed=226)
    expected = np.asarray([[env.node_index[u] for u, _ in env.monitor.edges],
                           [env.node_index[v] for _, v in env.monitor.edges]], dtype=np.int32)
    np.testing.assert_array_equal(env.edge_index, expected)
    np.testing.assert_array_equal(obs["edge_index"], expected)
    np.testing.assert_array_equal(info["edge_index"], expected)
    np.testing.assert_array_equal(obs["history_edges"][-1], obs["edge_features"])


def test_flow_feature_size_is_fixed_across_topology_sizes():
    small = NetworkRoutingEnv(generate_synthetic("ba", 8, 227))
    large = NetworkRoutingEnv(generate_synthetic("ba", 30, 228))
    small_obs, _ = small.reset(seed=229)
    large_obs, _ = large.reset(seed=230)
    assert small_obs["flow_features"].shape == large_obs["flow_features"].shape == (7,)
    assert small.observation_space["flow_features"].shape == large.observation_space["flow_features"].shape


def test_max_steps_truncates_without_termination():
    env = make_env(seed=231, max_steps=1)
    obs, _ = env.reset(seed=232)
    action = int(np.flatnonzero(obs["action_mask"])[0])
    _, _, terminated, truncated, _ = env.step(action)
    assert terminated is False
    assert truncated is True


def test_idle_action_masked_with_route_and_allowed_without_one():
    env = make_env(seed=233)
    obs, _ = env.reset(seed=234)
    assert len(env._paths.paths) > 0
    assert obs["action_mask"][-1] == 0
    env.flow = None
    env._refresh_paths()
    assert env._observation()["action_mask"][-1] == 1
    env.flow = env.traffic.sample_flow()
    for edge in list(env.graph.edges): env.fail_link(edge)
    assert not env._paths.paths
    assert env._observation()["action_mask"][-1] == 1


def test_router_failure_no_route_and_masking():
    env = make_env(); env.reset(seed=2)
    env.fail_router(env.flow.source)
    assert not env.graph.nodes[env.flow.source]["up"]
    assert all(not env.graph[u][v]["up"] for u, v in env.graph.edges(env.flow.source))
    assert env._paths.no_route and env._paths.paths == ()
    obs, reward, _, _, info = env.step(env.config.k_paths)
    assert info["no_route"] and np.isfinite(reward)


def test_all_routes_blocked_and_invalid_action_controlled():
    env = make_env(); env.reset(seed=3)
    for u, v in list(env.graph.edges): env.fail_link((u, v))
    assert env._paths.no_route
    _, reward, _, _, info = env.step(env.config.k_paths)
    assert info["no_route"] and reward < 0
    with pytest.raises(ValueError): env.step(env.config.k_paths + 2)


def test_bandwidth_drop_and_spike_diurnal_schedule():
    env = make_env(); flow = env.traffic.sample_flow(source="R0", destination="R1")
    spike = TrafficSpike(0, 3, 3)
    env.traffic_spikes = (spike,); env.diurnal_pattern = DiurnalPattern(baseline=1, amplitude=0, period=24)
    assert env._scheduled_flow(flow, 1).demand_mbps == flow.demand_mbps * 3


def test_flows_accumulate_on_same_link_and_release_at_expiry():
    graph = nx.Graph()
    graph.add_edge("a", "b", bandwidth=100.0, latency=1.0)
    traffic = PoissonTrafficGenerator(["a", "b"], demand_mbps=1)
    env = NetworkRoutingEnv(
        graph,
        NetworkEnvConfig(k_paths=1, hosts_per_router_fraction=None, minimum_hosts=0),
        traffic)
    env.reset(seed=401)
    edge = env._key("a", "b")

    env.flow = Flow("a", "b", 20.0, duration_steps=2, flow_id="first")
    env._refresh_paths()
    _, _, _, _, first_info = env.step(0)
    assert first_info["path_max_utilization"] == pytest.approx(0.2)
    assert env.loads[edge] == pytest.approx(20.0)

    env.flow = Flow("a", "b", 20.0, duration_steps=2, flow_id="second")
    env._refresh_paths()
    _, _, _, _, second_info = env.step(0)
    assert second_info["path_max_utilization"] == pytest.approx(0.4)
    # The first flow expires at this step boundary; the second remains.
    assert env.loads[edge] == pytest.approx(20.0)
    assert [active.flow.flow_id for active in env.active_flows] == ["second"]

    env.step(env.config.k_paths)
    assert env.loads[edge] == 0.0
    assert env.active_flows == []


def test_persistent_flow_on_path_a_makes_path_b_better():
    env_a = make_diamond(); env_b = make_diamond()
    for env in (env_a, env_b):
        env.flow = Flow("s", "t", 60.0, duration_steps=10, flow_id="first-a")
        env._refresh_paths()
        path_a = ("s", "a", "t")
        env.step(route_for(env, path_a))
        env.flow = Flow("s", "t", 60.0, duration_steps=5, flow_id="second")
        env._refresh_paths()

    path_a = ("s", "a", "t")
    path_b = ("s", "b", "t")
    _, _, _, _, info_a = env_a.step(route_for(env_a, path_a))
    _, _, _, _, info_b = env_b.step(route_for(env_b, path_b))
    assert info_a["path_latency_ms"] > info_b["path_latency_ms"]
    assert info_a["path_loss"] > info_b["path_loss"]
    assert info_b["path_loss"] == 0.0


def test_greedy_path_choice_beats_static_on_concurrent_max_utilization():
    env_static = make_diamond(); env_greedy = make_diamond()
    path_a = ("s", "a", "t")
    for env in (env_static, env_greedy):
        env.flow = Flow("s", "t", 60.0, duration_steps=10, flow_id="first-a")
        env._refresh_paths()
        env.step(route_for(env, path_a))
        env.flow = Flow("s", "t", 60.0, duration_steps=5, flow_id="second")
        env._refresh_paths()

    # Static latency-shortest uses A. Greedy evaluates current aggregate loads.
    static_action = route_for(env_static, path_a)
    greedy_action = min(
        range(len(env_greedy._paths.paths)),
        key=lambda index: max(
            (env_greedy.loads.get(env_greedy._key(u, v), 0.0)
             + env_greedy.flow.demand_mbps)
            / env_greedy.graph[u][v]["capacity"]
            for u, v in zip(env_greedy._paths.paths[index],
                             env_greedy._paths.paths[index][1:])))
    _, _, _, _, static_info = env_static.step(static_action)
    _, _, _, _, greedy_info = env_greedy.step(greedy_action)
    assert greedy_info["selected_path"] == ("s", "b", "t")
    assert route_max_utilization(env_greedy) < route_max_utilization(env_static)
    assert static_info["path_max_utilization"] > greedy_info["path_max_utilization"]


def test_unrouted_flow_occupies_no_capacity():
    env = make_diamond()
    env.flow = Flow("s", "t", 25.0, duration_steps=10, flow_id="unrouted")
    for edge in list(env.graph.edges):
        env.fail_link(edge)
    assert not env._paths.paths
    _, _, _, _, info = env.step(env.config.k_paths)
    assert info["no_route"]
    assert env.active_flows == []
    assert all(load == 0.0 for load in env.loads.values())


def test_router_failure_invalidates_entire_active_flow():
    env = make_diamond()
    env.flow = Flow("s", "t", 20.0, duration_steps=10, flow_id="route-through-a")
    env._refresh_paths()
    env.step(route_for(env, ("s", "a", "t")))
    assert env.active_flows
    env.fail_router("a")
    assert env.active_flows == []
    assert all(load == 0.0 for load in env.loads.values())


def test_scheduled_link_failure_invalidates_entire_active_flow():
    failed_edge = ("s", "a")
    env = make_diamond(events=(LinkFailure(1, failed_edge),))
    env.flow = Flow("s", "t", 20.0, duration_steps=10, flow_id="scheduled-failure")
    env._refresh_paths()
    env.step(route_for(env, ("s", "a", "t")))
    assert env.active_flows == []
    assert env.loads[env._key("a", "t")] == 0.0
    assert env.loads[env._key("s", "a")] == 0.0


def test_bandwidth_drop_preserves_active_flow_load_and_restores_capacity():
    edge = ("s", "a")
    env = make_diamond(events=(BandwidthDrop(1, edge, 0.5, duration=3),))
    env.flow = Flow("s", "t", 20.0, duration_steps=10, flow_id="bandwidth-drop")
    env._refresh_paths()
    env.step(route_for(env, ("s", "a", "t")))
    assert len(env.active_flows) == 1
    assert env.loads[env._key(*edge)] == 20.0
    assert env.graph[edge[0]][edge[1]]["capacity"] == 50.0

    env.step(env.config.k_paths)
    env.step(env.config.k_paths)
    env.step(env.config.k_paths)
    assert env.graph[edge[0]][edge[1]]["capacity"] == 100.0
    assert len(env.active_flows) == 1
    assert env.loads[env._key(*edge)] == 20.0


def test_one_request_per_step_without_backlog():
    graph = nx.cycle_graph(8)
    nx.set_edge_attributes(graph, 100.0, "bandwidth")
    nx.set_edge_attributes(graph, 1.0, "latency")
    traffic = PoissonTrafficGenerator(list(map(str, graph.nodes)), demand_mbps=1.0)
    graph = nx.relabel_nodes(graph, str)
    env = NetworkRoutingEnv(
        graph,
        NetworkEnvConfig(max_steps=1000, hosts_per_router_fraction=None,
                         minimum_hosts=0),
        traffic)
    obs, _ = env.reset(seed=401)
    assert traffic._flow_counter == 1  # Request for decision step zero.
    assert not hasattr(env, "_traffic_queue")
    for _ in range(1000):
        action = int(np.flatnonzero(obs["action_mask"])[0])
        obs, _, _, truncated, _ = env.step(action)
    assert truncated
    assert traffic._flow_counter == 1000
    assert env.flow is None
    assert not hasattr(env, "_traffic_queue")


def test_backbone_utilization_excludes_host_access_links():
    graph = nx.Graph()
    graph.add_node("r0", type="router"); graph.add_node("r1", type="router")
    graph.add_node("h0", type="host"); graph.add_node("h1", type="host")
    graph.add_edge("h0", "r0", bandwidth=10.0, latency=1.0)
    graph.add_edge("r0", "r1", bandwidth=100.0, latency=1.0)
    graph.add_edge("r1", "h1", bandwidth=10.0, latency=1.0)
    traffic = PoissonTrafficGenerator(["h0", "h1"])
    env = NetworkRoutingEnv(
        graph,
        NetworkEnvConfig(k_paths=1, hosts_per_router_fraction=None, minimum_hosts=0),
        traffic)
    env.reset(seed=401)
    env.flow = Flow("h0", "h1", 5.0, duration_steps=5, flow_id="access-check")
    env._refresh_paths()
    _, _, _, _, info = env.step(0)
    assert info["step_max_backbone_utilization"] == pytest.approx(0.05)
    assert info["step_mean_backbone_utilization"] == pytest.approx(0.05)
    assert info["step_max_access_utilization"] == pytest.approx(0.5)
    assert info["step_max_utilization"] == pytest.approx(0.5)
    profile = env.profiles[QoSClass.BULK]
    priority_factor = 1.0 + 0.05 * (2 - 1)
    expected_utilization_cost = (
        -env.reward_config.utilization_weight * 0.05
        * profile.reward_weight * priority_factor)
    assert info["reward_components"]["utilization"] == pytest.approx(
        expected_utilization_cost)


def test_realized_static_backbone_load_tracks_target_on_ring():
    graph = nx.cycle_graph(8)
    graph = nx.relabel_nodes(graph, str)
    nx.set_edge_attributes(graph, 100.0, "bandwidth")
    nx.set_edge_attributes(graph, 1.0, "latency")
    traffic = PoissonTrafficGenerator(sorted(graph.nodes))
    settings = traffic.configure_for_network(graph, list(graph.nodes), 0.2)
    env = NetworkRoutingEnv(
        graph,
        NetworkEnvConfig(max_steps=3000, intensity=0.2,
                         hosts_per_router_fraction=None, minimum_hosts=0),
        traffic)
    observation, _ = env.reset(seed=305)
    measured = []
    for step in range(3000):
        path = tuple(nx.shortest_path(
            env.graph, env.flow.source, env.flow.destination, weight="latency"))
        env._paths = PathResult((path,), False)
        observation, _, _, _, info = env.step(0)
        if step >= 100:
            measured.append(info["step_mean_backbone_utilization"])
    realized = float(np.mean(measured))
    assert realized == pytest.approx(settings["achievable_intensity"], rel=0.25)


def test_route_change_for_failed_previous_path_is_not_flapping():
    env = make_env(); env.reset(seed=811)
    previous = env._paths.paths[0]; env._last_path = previous; env._last_flow_id = env.flow.flow_id
    env._last_quality = 0.0
    env.fail_link((previous[0], previous[1]))
    if not env._paths.paths: pytest.skip("topology has no alternate route for sampled flow")
    observation = env._observation()
    action = int(np.flatnonzero(observation["action_mask"][:-1])[0])
    _, _, _, _, info = env.step(action)
    assert info["reward_components"]["flap"] == 0.0


def test_action_mask_invalid_indices_and_manual_failed_path_guard():
    env = make_env(); obs, _ = env.reset(seed=91)
    valid_count = len(env._paths.paths)
    assert obs["action_mask"][-1] == 0
    assert np.all(obs["action_mask"][:valid_count] == 1)
    assert np.all(obs["action_mask"][valid_count:-1] == 0)
    if valid_count < env.config.k_paths:
        invalid = valid_count
        _, reward, _, _, info = env.step(invalid)
        assert info["invalid_action"] and info["selected_path"] is None and reward < 0
    env.reset(seed=92); path = env._paths.paths[0]
    env.fail_link((path[0], path[1]))
    env._paths = type(env._paths)(((path),), False)  # Simulate a stale/malicious candidate cache.
    _, reward, _, _, info = env.step(0)
    assert info["no_route"] and info["selected_path"] is None and reward < 0
    assert all(load == 0 for load in env.loads.values())


def test_idle_sentinel_is_not_reported_as_no_route():
    env = make_env(); env.reset(seed=112)
    env.flow = None; env._refresh_paths()
    obs = env._observation()
    _, reward, _, _, info = env.step(env.config.k_paths)
    assert reward == 0 and not info["no_route"] and not info["invalid_action"]
    assert obs["action_mask"][-1] == 1


def test_history_evolves_on_scheduled_failure_and_reset_clears_it():
    graph = generate_synthetic("ba", 10, 15); edge = next(iter(graph.edges))
    traffic = PoissonTrafficGenerator(sorted(graph.nodes), demand_mbps=2)
    env = NetworkRoutingEnv(graph, NetworkEnvConfig(k_paths=3, history_length=4), traffic,
                            events=(LinkFailure(1, edge),))
    initial, _ = env.reset(seed=33)
    rows = sorted((tuple(sorted((u, v), key=str)), i) for i, (u, v) in enumerate(env.monitor.edges))
    edge_key = tuple(sorted(edge, key=str)); edge_idx = dict((e, i) for e, i in rows)[edge_key]
    action = int(np.flatnonzero(initial["action_mask"])[0])
    next_obs, *_ = env.step(action)
    assert initial["edge_features"][edge_idx, 3] == 1
    assert next_obs["edge_features"][edge_idx, 3] == 0
    assert np.all(next_obs["history_edges"][:3, edge_idx, 3] == 1)
    assert next_obs["history_edges"][-1, edge_idx, 3] == 0
    reset_obs, _ = env.reset(seed=33)
    assert reset_obs["edge_features"][edge_idx, 3] == 1
    assert np.all(reset_obs["history_edges"][:, edge_idx, 3] == 1)


def test_environment_random_events_and_trajectory_reproduce():
    graph = generate_synthetic("ba", 10, 25)
    traffic = PoissonTrafficGenerator(sorted(graph.nodes), demand_mbps=2)
    config = NetworkEnvConfig(k_paths=3, history_length=2, max_steps=20, event_probability=0.2)
    trajectories = []
    for _ in range(2):
        env = NetworkRoutingEnv(graph, config, traffic)
        obs, _ = env.reset(seed=303)
        run = []
        for _ in range(12):
            action = int(np.flatnonzero(obs["action_mask"])[0])
            obs, reward, term, trunc, info = env.step(action)
            run.append((obs, reward, term, trunc, info))
        trajectories.append(run)
    for left, right in zip(*trajectories):
        for key in left[0]: np.testing.assert_array_equal(left[0][key], right[0][key])
        assert left[1:4] == right[1:4]
        assert left[4] == right[4]


def test_5000_step_stability_gate():
    graph = generate_synthetic("ba", 10, 5000)
    traffic = PoissonTrafficGenerator(sorted(graph.nodes), demand_mbps=5)
    edges = list(graph.edges)
    config = NetworkEnvConfig(k_paths=3, history_length=3, max_steps=6000)
    event_router = next(n for n in sorted(graph.nodes) if all(n not in edge for edge in edges[:4]))
    env = NetworkRoutingEnv(graph, config, traffic,
                            events=(LinkFailure(15, edges[0]),
                                    LinkFailure(250, edges[2]),
                                    BandwidthDrop(75, edges[1], 0.5, duration=25),
                                    BandwidthDrop(300, edges[3], 0.25, duration=50),
                                    RouterFailure(150, event_router)),
                            traffic_spikes=(TrafficSpike(200, 30, 2.0),))
    obs, _ = env.reset(seed=5000)
    for _ in range(5000):
        action = int(np.flatnonzero(obs["action_mask"])[0])
        obs, reward, terminated, truncated, info = env.step(action)
        assert env.observation_space.contains(obs) and np.isfinite(reward)
        assert all(np.isfinite(x).all() for x in obs.values())
        assert obs["action_mask"].any()
        assert all(path_is_available(env.graph, path) for path in env._paths.paths)
        for u, v, attrs in env.graph.edges(data=True):
            assert np.isfinite(attrs["capacity"]) and attrs["capacity"] >= 0
            if not attrs["up"]: assert attrs["capacity"] == 0
        assert not truncated and not terminated
    assert not env.graph[edges[0][0]][edges[0][1]]["up"]
    assert not env.graph[edges[2][0]][edges[2][1]]["up"]
    assert not env.graph.nodes[event_router]["up"]
    assert env.graph[edges[3][0]][edges[3][1]]["capacity"] == env.graph[edges[3][0]][edges[3][1]]["base_capacity"]
