import networkx as nx

from env.paths import candidate_paths, path_is_available
from env.network_env import NetworkEnvConfig, NetworkRoutingEnv
from env.traffic import Flow, PoissonTrafficGenerator


def graph():
    g = nx.cycle_graph(5)
    for n in g: g.nodes[n]["up"] = True
    for u, v in g.edges: g[u][v].update(up=True, capacity=10, latency=1)
    return g


def test_k_shortest_edge_disjoint_and_failed_link_masking():
    g = graph(); result = candidate_paths(g, 0, 2, k=4, edge_disjoint=True)
    assert len(result.paths) == 2 and all(path_is_available(g, p, 0, 2) for p in result.paths)
    path_edges = [set(frozenset(edge) for edge in zip(p, p[1:])) for p in result.paths]
    assert path_edges[0].isdisjoint(path_edges[1])
    g[0][1]["up"] = False; g[0][1]["capacity"] = 0
    result = candidate_paths(g, 0, 2, k=4)
    assert all((0, 1) not in tuple(zip(p, p[1:])) and (1, 0) not in tuple(zip(p, p[1:])) for p in result.paths)


def test_no_route_after_router_failure():
    g = graph()
    for u, v in list(g.edges(1)): g[u][v]["up"] = False; g[u][v]["capacity"] = 0
    g.nodes[1]["up"] = False
    result = candidate_paths(g, 0, 2)
    assert not result.no_route and all(1 not in p for p in result.paths)
    g[4][3]["up"] = False; g[4][3]["capacity"] = 0
    result = candidate_paths(g, 0, 2)
    assert result.no_route and result.paths == ()


def test_k_paths_and_load_aware_ranking():
    g = nx.Graph()
    for n in ("s", "a", "b", "t"): g.add_node(n, up=True)
    for u, v in (("s", "a"), ("a", "t"), ("s", "b"), ("b", "t")):
        g.add_edge(u, v, up=True, capacity=10.0, latency=1.0)
    base = candidate_paths(g, "s", "t", k=3)
    assert len(base.paths) == 2
    loads = {("a", "s"): 9.0, ("a", "t"): 9.0}
    ranked = candidate_paths(g, "s", "t", k=2, load_mbps=loads)
    assert ranked.paths[0][1] == "b" and ranked.paths[0] != base.paths[0]
    complete = nx.complete_graph(5)
    for u, v in complete.edges: complete[u][v].update(up=True, capacity=1, latency=1)
    assert len(candidate_paths(complete, 0, 1, k=3).paths) == 3
    try:
        candidate_paths(g, "s", "t", load_mbps={("s", "a"): float("nan")})
    except ValueError: pass
    else: raise AssertionError("non-finite link loads must be rejected")


def test_environment_randomizes_ranked_path_action_indices_seededly():
    g = nx.Graph()
    for n in ("s", "a", "b", "t"): g.add_node(n, type="router")
    for u, v in (("s", "a"), ("a", "t"), ("s", "b"), ("b", "t")):
        g.add_edge(u, v, bandwidth=10.0, latency=1.0, loss=0.0)
    gen = PoissonTrafficGenerator(["s", "a", "b", "t"])
    env = NetworkRoutingEnv(g, NetworkEnvConfig(k_paths=2), gen)
    first_by_seed = []
    for seed in range(12):
        env.reset(seed=seed)
        env.flow = Flow("s", "t", 1, duration_steps=50)
        env._refresh_paths()
        first_by_seed.append(env._paths.paths[0])
    assert len(set(first_by_seed)) == 2
    env.reset(seed=41); env.flow = Flow("s", "t", 1, duration_steps=50)
    env._refresh_paths(); obs = env._observation()
    expected = env._paths.paths[0]
    _, _, _, _, info = env.step(0)
    assert info["selected_path"] == expected
