import networkx as nx
import numpy as np

from env.monitor import HistoryBuffer, NetworkMonitor


def test_monitor_features_finite_and_history_fixed_length():
    g = nx.path_graph(3)
    for n in g: g.nodes[n]["up"] = True
    for u, v in g.edges: g[u][v].update(up=True, capacity=10, latency=1)
    mon = NetworkMonitor(g); loads = {(0, 1): 2, (1, 2): 1}; lat = {(0, 1): 2, (1, 2): 3}; loss = {}
    first = mon.snapshot(g, loads, lat, loss)
    edge_idx = mon.edges.index((0, 1))
    np.testing.assert_allclose(first.edge_features[edge_idx], [0.2, 2.0, 0.0, 1.0, 10.0])
    np.testing.assert_allclose(first.node_features[0], [0.2, 1.0])
    g[0][1].update(up=False, capacity=0.0)
    down = mon.snapshot(g, loads, lat, loss)
    assert down.edge_features[edge_idx, 3] == 0 and down.edge_features[edge_idx, 4] == 0
    hist = HistoryBuffer(3, first.node_features.shape, first.edge_features.shape); hist.reset(first)
    hist.append(first); nodes, edges = hist.arrays()
    assert nodes.shape == (3, 3, 2) and edges.shape == (3, 2, 5)
    assert np.isfinite(nodes).all() and np.isfinite(edges).all()
