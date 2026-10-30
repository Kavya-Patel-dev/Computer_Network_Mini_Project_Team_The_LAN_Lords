import networkx as nx
import pytest

from env.events import BandwidthDrop, EventManager, LinkFailure, RouterFailure


def _graph():
    g = nx.cycle_graph(4)
    for n in g: g.nodes[n].update(up=True)
    for u, v in g.edges: g[u][v].update(up=True, base_capacity=100.0, capacity=100.0)
    return g


def test_link_router_failure_and_temporary_bandwidth_drop():
    g = _graph()
    manager = EventManager([LinkFailure(1, (0, 1)), RouterFailure(1, 2), BandwidthDrop(0, (0, 3), .25, 2)])
    assert manager.apply_due(g, 0)[0].time == 0
    assert g[0][3]["capacity"] == 25
    manager.apply_due(g, 1)
    assert not g[0][1]["up"] and g[0][1]["capacity"] == 0
    assert not g.nodes[2]["up"] and not g[1][2]["up"] and g[1][2]["capacity"] == 0
    assert g[0][3]["up"] and g[0][3]["capacity"] == 25
    assert g[0][3]["capacity"] < g[0][3]["base_capacity"]
    manager.apply_due(g, 2); assert g[0][3]["up"] and g[0][3]["capacity"] == 100


def test_invalid_event_bandwidth_factor():
    with pytest.raises(ValueError): BandwidthDrop(0, ("a", "b"), 1.2)
    with pytest.raises(ValueError): BandwidthDrop(-1, ("a", "b"), .5)


def test_overlapping_temporary_drops_restore_in_layers():
    g = _graph()
    manager = EventManager([BandwidthDrop(0, (0, 1), .5, 10), BandwidthDrop(2, (0, 1), .25, 3)])
    manager.apply_due(g, 0); assert g[0][1]["capacity"] == 50
    manager.apply_due(g, 2); assert g[0][1]["capacity"] == 25
    manager.apply_due(g, 5); assert g[0][1]["capacity"] == 50
    manager.apply_due(g, 10); assert g[0][1]["capacity"] == 100
