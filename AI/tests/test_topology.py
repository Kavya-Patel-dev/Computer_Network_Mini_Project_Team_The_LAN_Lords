from __future__ import annotations

import hashlib
import json
import tarfile
import xml.etree.ElementTree as ET
from pathlib import Path

import networkx as nx
import numpy as np
import pytest

from env.topology import (
    assign_link_attributes, attach_hosts, cyclomatic_number, family_key, fingerprint, from_json,
    generate_synthetic, load_repetita, load_sndlib, load_zoo, to_json, validate,
    path_diversity,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


@pytest.mark.parametrize("kind", ["ba", "waxman", "er"])
@pytest.mark.parametrize("n,seed", [(5, 1), (12, 2), (25, 3), (50, 4)])
def test_synthetic_connected_valid_deterministic(kind, n, seed):
    first = generate_synthetic(kind, n, seed)
    second = generate_synthetic(kind, n, seed)
    assert nx.is_connected(first)
    assert sum(d["type"] == "router" for _, d in first.nodes(data=True)) == n
    assert validate(first) == []
    assert to_json(first) == to_json(second)


def test_attributes_fill_ranges_and_keep_existing():
    graph = nx.path_graph(3)
    graph.graph.update(name="attrs", source="synthetic")
    nx.set_node_attributes(graph, "router", "type")
    graph[0][1]["bandwidth"] = 333.0
    assign_link_attributes(graph, np.random.default_rng(44))
    assert graph[0][1]["bandwidth"] == 333.0
    for _, _, attrs in graph.edges(data=True):
        assert set(("bandwidth", "latency", "loss")) <= attrs.keys()
        assert all(np.isfinite(attrs[k]) for k in ("bandwidth", "latency", "loss"))
        assert attrs["bandwidth"] > 0 and 0.1 <= attrs["latency"] <= 20 and 0 <= attrs["loss"] <= 100


def test_json_round_trip_and_validation_errors():
    graph = generate_synthetic("ba", 8, 9)
    restored = from_json(to_json(graph))
    assert nx.is_isomorphic(graph, restored, node_match=lambda a, b: a["type"] == b["type"], edge_match=lambda a, b: a == b)
    broken = graph.copy(); u, v = next(iter(broken.edges)); del broken[u][v]["bandwidth"]
    assert any("missing bandwidth" in e for e in validate(broken))
    broken = graph.copy(); u, v = next(iter(broken.edges)); broken[u][v]["bandwidth"] = -1
    assert any("bandwidth must be positive" in e for e in validate(broken))
    broken = graph.copy(); broken.add_node("R99", type="router")
    assert any("connected" in e for e in validate(broken))
    broken = graph.copy(); broken.add_node("H0", type="host"); broken.add_node("H1", type="host"); broken.add_edge("H0", "H1", bandwidth=10, latency=1, loss=0)
    assert any("only to routers" in e for e in validate(broken))
    broken = graph.copy(); u, v = next(iter(broken.edges)); broken[u][v]["loss"] = float("nan")
    assert any("non-finite loss" in e for e in validate(broken))


def test_attach_hosts_are_leaves():
    graph = generate_synthetic("er", 9, 10)
    attach_hosts(graph, 4, np.random.default_rng(4))
    assert validate(graph) == []
    assert all(graph.degree(n) == 1 for n, d in graph.nodes(data=True) if d["type"] == "host")


def test_family_key():
    assert family_key("Geant2012") == family_key("geant") == family_key("GEANT")


def test_zoo_fixture(tmp_path):
    path = tmp_path / "tiny.graphml"
    path.write_text('''<?xml version="1.0"?><graphml xmlns="http://graphml.graphdrawing.org/xmlns">
      <key id="lab" for="node" attr.name="label" attr.type="string"/><key id="lat" for="node" attr.name="Latitude" attr.type="double"/><key id="lon" for="node" attr.name="Longitude" attr.type="double"/><key id="bw" for="edge" attr.name="LinkSpeedRaw" attr.type="double"/>
      <graph edgedefault="undirected"><node id="a"><data key="lab">A</data><data key="lat">0</data><data key="lon">0</data></node><node id="b"><data key="lab">B</data><data key="lat">0</data><data key="lon">1</data></node><node id="c"/><edge source="a" target="b"><data key="bw">500000000</data></edge><edge source="b" target="a"><data key="bw">800000000</data></edge><edge source="c" target="c"/></graph></graphml>''', encoding="utf-8")
    graph = load_zoo(path)
    assert graph.number_of_nodes() == 2 and graph.number_of_edges() == 1
    assert next(iter(graph.edges(data=True)))[2]["bandwidth"] == 800
    assert validate(graph) == []


def test_sndlib_fixture(tmp_path):
    path = tmp_path / "tiny.xml"
    path.write_text('''<network xmlns="http://sndlib.zib.de/network"><meta><unit>MBITPERSEC</unit></meta><networkStructure><nodes coordinatesType="geographical"><node id="A"><coordinates><x>0</x><y>0</y></coordinates></node><node id="B"><coordinates><x>1</x><y>0</y></coordinates></node></nodes><links><link id="AB"><source>A</source><target>B</target><preInstalledModule><capacity>100</capacity></preInstalledModule><additionalModules><addModule><capacity>200</capacity></addModule></additionalModules></link></links></networkStructure><demands><demand id="d"><source>A</source><target>B</target><demandValue>12.5</demandValue></demand></demands></network>''')
    graph, demands = load_sndlib(path)
    assert validate(graph) == [] and len(demands) == 1 and demands[0][2] == 12.5
    assert graph["R0"]["R1"]["raw_capacity"] == 100
    assert graph["R0"]["R1"]["additional_capacities"] == [200]


def test_repetita_fixture(tmp_path):
    graphfile, demandfile = tmp_path / "mini.graph", tmp_path / "mini.demands"
    graphfile.write_text("NODES 3\nlabel x y\na 0 0\nb 1 0\nc 0 1\n\nEDGES 4\nlabel src dest weight bw delay\ne0 0 1 10 2400000 7000\ne1 1 0 10 2300000 8000\ne2 1 2 10 10000000 1000\ne3 2 1 10 10000000 1000\n")
    demandfile.write_text("DEMANDS 1\nlabel src dest bw\nd0 0 2 14\n")
    graph, demands = load_repetita(graphfile, demandfile)
    assert graph.number_of_edges() == 2 and validate(graph) == []
    assert graph["R0"]["R1"]["bandwidth"] == 2400
    assert graph["R0"]["R1"]["latency"] == 7
    assert demands == [("R0", "R2", 0.014)]


def test_repetita_arpanet_wiki_units(tmp_path):
    graphfile = tmp_path / "Arpanet.graph"
    graphfile.write_text("NODES 2\nlabel x y\na 0 0\nb 1 0\n\nEDGES 1\nlabel src dest weight bw delay\ne0 0 1 10 1000000 678\n")
    graph, _ = load_repetita(graphfile)
    assert graph["R0"]["R1"]["bandwidth"] == 1000.0
    assert graph["R0"]["R1"]["latency"] == pytest.approx(0.678)
    assert graph["R0"]["R1"]["raw_delay_us"] == 678


def test_latency_below_0_1_ms_is_rederived_and_all_sources_clip_at_0_1():
    for source in ("zoo", "sndlib", "repetita"):
        graph = nx.Graph(name=source, source=source)
        graph.add_node("R0", type="router", x=0.0, y=0.0)
        graph.add_node("R1", type="router", x=0.0, y=0.0)
        graph.add_edge("R0", "R1", bandwidth=100.0, latency=0.05, loss=0.0)
        assign_link_attributes(graph, np.random.default_rng(1))
        assert graph["R0"]["R1"]["latency"] == 0.1
        assert graph.graph["_latency_rederived_missing"] == 1
        assert graph.graph["_attribute_clip_counts"]["latency"]["clipped_low"] == 0
        assert graph.graph["_attribute_clip_counts"]["latency"]["clipped_high"] == 0


def test_missing_low_latency_without_coordinates_uses_uniform_fallback():
    graph = nx.Graph(name="no-coordinates", source="user")
    graph.add_node("R0", type="router")
    graph.add_node("R1", type="router")
    graph.add_edge("R0", "R1", bandwidth=100.0, latency=0.0, loss=0.0)
    assign_link_attributes(graph, np.random.default_rng(7))
    assert 1.0 <= graph["R0"]["R1"]["latency"] <= 20.0
    assert graph.graph["_latency_rederived_missing"] == 1


def test_cyclomatic_and_path_diversity_tree_and_ring():
    tree = nx.path_graph(6)
    nx.set_node_attributes(tree, "router", "type")
    ring = nx.cycle_graph(6)
    nx.set_node_attributes(ring, "router", "type")
    assert cyclomatic_number(tree) == 0
    assert path_diversity(tree) == 0.0
    assert cyclomatic_number(ring) == 1
    assert path_diversity(ring) == 1.0


def test_sndlib_geographic_city_pair_latency():
    graph, _ = load_sndlib(DATA / "sndlib-networks-xml" / "abilene.xml")
    labels = {d["label"]: n for n, d in graph.nodes(data=True)}
    latency = graph[labels["ATLAng"]][labels["WASHng"]]["latency"]
    assert 4.0 <= latency <= 5.2


def test_zoo_longitude_latitude_city_pair(tmp_path):
    path = tmp_path / "cities.graphml"
    path.write_text('''<graphml xmlns="http://graphml.graphdrawing.org/xmlns"><key id="lat" for="node" attr.name="Latitude" attr.type="double"/><key id="lon" for="node" attr.name="Longitude" attr.type="double"/><graph edgedefault="undirected"><node id="sunny"><data key="lat">37.45</data><data key="lon">-122.18</data></node><node id="sea"><data key="lat">47.6</data><data key="lon">-122.3</data></node><edge source="sunny" target="sea"/></graph></graphml>''')
    graph = load_zoo(path)
    latency = next(iter(graph.edges(data=True)))[2]["latency"]
    assert 5.0 <= latency <= 6.5


def test_repetita_longitude_latitude_city_pair(tmp_path):
    path = tmp_path / "cities.graph"
    path.write_text("NODES 2\nlabel x y\nsunny -122.18 37.45\nsea -122.3 47.6\n\nEDGES 1\nlabel src dest weight bw delay\ne0 0 1 10 1000000 6000\n")
    graph, _ = load_repetita(path)
    latency = next(iter(graph.edges(data=True)))[2]["latency"]
    assert 5.0 <= latency <= 6.5


def test_real_sndlib_samples_and_demand_totals():
    files = sorted((DATA / "sndlib-networks-xml").glob("*.xml"))
    if not files: pytest.skip("SNDlib data folder is missing")
    for path in files[:3]:
        graph, demands = load_sndlib(path)
        assert validate(graph) == []
        root = ET.parse(path).getroot()
        independent = sum(float(e.text) for e in root.iter() if e.tag.rsplit("}", 1)[-1] == "demandValue")
        assert sum(d[2] for d in demands) == pytest.approx(independent)


def test_real_zoo_archive_sample():
    archive = DATA / "30153949" / "graphml.tar.gz"
    direct = sorted((DATA / "30153949" / "graphml").rglob("*.graphml"))
    if direct: graph = load_zoo(direct[0])
    elif archive.exists():
        with tarfile.open(archive, "r:gz") as tf:
            member = next(m for m in tf.getmembers() if m.name.endswith(".graphml"))
            graph = load_zoo(tf.extractfile(member).read())
    else: pytest.skip("Topology Zoo data folder and archive are missing")
    assert validate(graph) == []


def test_real_repetita_sample():
    files = sorted((DATA / "Repetita-master" / "data").rglob("*.graph"))
    if not files: pytest.skip("REPETITA data folder is missing")
    path = next((p for p in files if 8 <= int(p.read_text(errors="replace").splitlines()[0].split()[1]) <= 40), files[0])
    graph, _ = load_repetita(path)
    assert validate(graph) == []


def test_splits_are_family_and_fingerprint_disjoint_and_locked():
    splits_file, lock_file = DATA / "splits.json", DATA / "splits.lock"
    if not splits_file.exists() or not lock_file.exists(): pytest.skip("split files have not been generated")
    splits = json.loads(splits_file.read_text(encoding="utf-8"))
    seen: dict[str, set[str]] = {k: set() for k in ("name", "family", "fingerprint")}
    for items in splits.values():
        for key, values in seen.items():
            current = {str(item[key]).lower() for item in items}
            assert not (values & current), f"{key} leakage between splits"
            values.update(current)
    test_entries = json.dumps(sorted(splits["test"], key=lambda x: json.dumps(x, sort_keys=True)), sort_keys=True, separators=(",", ":")).encode()
    assert hashlib.sha256(test_entries).hexdigest() == lock_file.read_text().strip()


def test_every_saved_split_graph_is_valid():
    splits_file = DATA / "splits.json"
    if not splits_file.exists(): pytest.skip("data/splits.json has not been generated")
    splits = json.loads(splits_file.read_text(encoding="utf-8"))
    for entries in splits.values():
        for entry in entries:
            source, relpath = entry["source"], entry["path"]
            if source == "zoo" and "::" in relpath:
                archive_rel, member_name = relpath.split("::", 1)
                with tarfile.open(DATA / archive_rel, "r:gz") as tf:
                    graph = load_zoo(tf.extractfile(member_name).read())
            elif source == "zoo": graph = load_zoo(DATA / relpath)
            elif source == "sndlib": graph, _ = load_sndlib(DATA / relpath)
            else: graph, _ = load_repetita(DATA / relpath)
            assert validate(graph) == [], f"invalid split graph {relpath}"
            assert sum(d["type"] == "router" for _, d in graph.nodes(data=True)) in range(8, 41)


def test_splits_have_required_size_strata_and_density_limits():
    splits_file = DATA / "splits.json"
    if not splits_file.exists(): pytest.skip("data/splits.json has not been generated")
    splits = json.loads(splits_file.read_text(encoding="utf-8"))
    for split in ("train", "val", "test"):
        large = [e for e in splits[split] if 20 <= e["num_nodes"] <= 40]
        assert len(large) >= (2 if split == "test" else 1)
    for split in ("val", "test"):
        assert all(2 * e["num_edges"] / e["num_nodes"] <= 5 for e in splits[split])
    assert sum(2 * e["num_edges"] / e["num_nodes"] > 5 for e in splits["train"]) <= 1
