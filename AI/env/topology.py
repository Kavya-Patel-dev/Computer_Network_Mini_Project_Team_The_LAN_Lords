"""Topology loaders and stable graph utilities for the routing model."""
from __future__ import annotations

import hashlib
import itertools
import json
import logging
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Literal

import networkx as nx
import numpy as np
from pydantic import BaseModel

LOGGER = logging.getLogger(__name__)
_BANDWIDTHS = (100.0, 200.0, 500.0, 1000.0)
_SOURCE = {"zoo", "sndlib", "repetita", "synthetic", "user"}


class NodeModel(BaseModel):
    id: str
    type: Literal["router", "host"]


class LinkModel(BaseModel):
    src: str
    dst: str
    bandwidth: float
    latency: float
    loss: float


class TopologyModel(BaseModel):
    name: str
    nodes: list[NodeModel]
    links: list[LinkModel]


def _rng(rng: np.random.Generator | int | None) -> np.random.Generator:
    return rng if isinstance(rng, np.random.Generator) else np.random.default_rng(rng)


def _largest_component(graph: nx.Graph) -> nx.Graph:
    if not graph:
        raise ValueError("topology contains no nodes")
    nodes = max(nx.connected_components(graph), key=len)
    return graph.subgraph(nodes).copy()


def _relabel(graph: nx.Graph) -> nx.Graph:
    """Normalize ids to Rn/Hn while retaining source ids as labels."""
    graph = nx.Graph(graph)
    mapping: dict[Any, str] = {}
    routers, hosts = [], []
    for node, attrs in graph.nodes(data=True):
        (hosts if attrs.get("type") == "host" else routers).append(node)
    for idx, node in enumerate(sorted(routers, key=str)):
        mapping[node] = f"R{idx}"
    for idx, node in enumerate(sorted(hosts, key=str)):
        mapping[node] = f"H{idx}"
    graph = nx.relabel_nodes(graph, mapping, copy=True)
    for old, new in mapping.items():
        graph.nodes[new].setdefault("type", "host" if new.startswith("H") else "router")
        graph.nodes[new].setdefault("label", str(old))
    return graph


def _distance_latency(a: dict[str, Any], b: dict[str, Any]) -> float | None:
    if a.get("_coordinates_geographical") is False or b.get("_coordinates_geographical") is False:
        return None
    try:
        lat1, lon1 = float(a.get("y", a.get("lat"))), float(a.get("x", a.get("lon")))
        lat2, lon2 = float(b.get("y", b.get("lat"))), float(b.get("x", b.get("lon")))
        if not all(map(math.isfinite, (lat1, lon1, lat2, lon2))):
            return None
    except (TypeError, ValueError):
        return None
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    km = 6371.0 * 2 * math.asin(min(1.0, math.sqrt(h)))
    return km / 200.0 + 0.1


def assign_link_attributes(
    graph: nx.Graph,
    rng: np.random.Generator | int | None,
    overwrite: bool = False,
) -> nx.Graph:
    """Fill missing link metrics, re-derive suspect latency, then clip globally."""
    gen = _rng(rng)
    clipped = {key: {"clipped_low": 0, "clipped_high": 0} for key in ("bandwidth", "latency", "loss")}
    rederived_missing = 0
    for u, v, attrs in graph.edges(data=True):
        if overwrite or _missing_number(attrs.get("bandwidth")):
            attrs["bandwidth"] = float(gen.choice(_BANDWIDTHS))
        latency_missing = _missing_number(attrs.get("latency")) or _number_below(attrs.get("latency"), 0.1)
        if overwrite or latency_missing:
            if not overwrite and latency_missing:
                rederived_missing += 1
            latency = _distance_latency(graph.nodes[u], graph.nodes[v])
            attrs["latency"] = float(latency if latency is not None else gen.uniform(1, 20))
        if overwrite or _missing_number(attrs.get("loss")):
            attrs["loss"] = float(gen.uniform(0, 0.5))
        for key, low, high in (("bandwidth", 1e-9, float("inf")), ("latency", 0.1, 20.0), ("loss", 0.0, 100.0)):
            try:
                value = float(attrs[key])
                if math.isfinite(value):
                    bounded = min(max(value, low), high)
                    if bounded < value:
                        clipped[key]["clipped_high"] += 1
                    elif bounded > value:
                        clipped[key]["clipped_low"] += 1
                    attrs[key] = bounded
            except (TypeError, ValueError):
                pass
    totals = graph.graph.setdefault("_attribute_clip_counts", {
        key: {"clipped_low": 0, "clipped_high": 0} for key in ("bandwidth", "latency", "loss")
    })
    for key, sides in clipped.items():
        for side, count in sides.items():
            totals.setdefault(key, {}).setdefault(side, 0)
            totals[key][side] += count
    graph.graph["_latency_rederived_missing"] = graph.graph.get("_latency_rederived_missing", 0) + rederived_missing
    graph.graph["_attribute_edge_count"] = graph.graph.get("_attribute_edge_count", 0) + graph.number_of_edges()
    if any(clipped[key][side] for key in clipped for side in ("clipped_low", "clipped_high")):
        LOGGER.info(
            "source=%s clipped values: %s",
            graph.graph.get("source", "unknown"), clipped,
        )
    return graph


def _missing_number(value: Any) -> bool:
    """Return whether a value is absent, nonnumeric, or nonfinite."""
    if value is None:
        return True
    try:
        return not math.isfinite(float(value))
    except (TypeError, ValueError):
        return True


def _number_below(value: Any, threshold: float) -> bool:
    """Safely compare a numeric value with a missing-data threshold."""
    try:
        return float(value) < threshold
    except (TypeError, ValueError):
        return False


def load_zoo(path: str | Path | bytes) -> nx.Graph:
    """Load Topology Zoo GraphML; select its largest connected component."""
    source = Path(path) if not isinstance(path, bytes) else None
    raw = nx.read_graphml(source, force_multigraph=True) if source is not None else nx.parse_graphml(path.decode("utf-8", "replace"), force_multigraph=True)
    g = nx.Graph()
    g.graph.update(name=str(raw.graph.get("label", raw.graph.get("Network", source.stem if source else "Topology Zoo"))), source="zoo")
    for node, attrs in raw.nodes(data=True):
        label = str(attrs.get("label", node))
        nd = {"type": "router", "label": label}
        for dest, candidates in (("x", ("Longitude", "longitude", "lon")), ("y", ("Latitude", "latitude", "lat"))):
            value = next((attrs[k] for k in candidates if k in attrs), None)
            if value is not None:
                try: nd[dest] = float(value)
                except (TypeError, ValueError): pass
        g.add_node(str(node), **nd)
    edges = raw.edges(data=True, keys=True) if raw.is_multigraph() else ((u, v, None, d) for u, v, d in raw.edges(data=True))
    for u, v, _key, attrs in edges:
        if u == v: continue
        raw_speed = attrs.get("LinkSpeedRaw")
        bw = None
        try:
            if raw_speed is not None:
                # Topology Zoo LinkSpeedRaw is stored as bits per second.
                bw = float(raw_speed) / 1_000_000.0
            else:
                parsed = float(attrs.get("LinkSpeed"))
                units = str(attrs.get("LinkSpeedUnits", "m")).lower()
                factor = 1000.0 if units.startswith("g") else (0.001 if units.startswith("k") else 1.0)
                bw = parsed * factor
            if not math.isfinite(bw) or bw <= 0: bw = None
        except (TypeError, ValueError): pass
        latency = _distance_latency(g.nodes[str(u)], g.nodes[str(v)])
        candidate = {"bandwidth": bw, "latency": latency, "loss": 0.0}
        if g.has_edge(str(u), str(v)):
            old = g[str(u)][str(v)]
            if (candidate["bandwidth"] or 0) > (old.get("bandwidth") or 0): old.update(candidate)
        else:
            g.add_edge(str(u), str(v), **candidate)
    g = _largest_component(g)
    g = _relabel(g)
    return assign_link_attributes(g, np.random.default_rng(0))


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def load_sndlib(path: str | Path) -> tuple[nx.Graph, list[tuple[str, str, float]]]:
    """Load namespace-qualified SNDlib XML and relative demands."""
    path = Path(path)
    root = ET.parse(path).getroot()
    g = nx.Graph(name=path.stem, source="sndlib")
    coordinate_type = "" 
    for elem in root.iter():
        if _local(elem.tag) == "nodes":
            coordinate_type = str(elem.get("coordinatesType", "")).lower()
            break
    for elem in root.iter():
        if _local(elem.tag) != "node": continue
        node = elem.get("id")
        if not node: continue
        attrs: dict[str, Any] = {"type": "router", "label": node}
        attrs["_coordinates_geographical"] = coordinate_type == "geographical"
        coords = next((child for child in elem if _local(child.tag) == "coordinates"), None)
        if coords is not None:
            for c in coords:
                if _local(c.tag) in {"x", "y"} and c.text:
                    attrs[_local(c.tag)] = float(c.text)
        g.add_node(node, **attrs)
    for elem in root.iter():
        if _local(elem.tag) != "link": continue
        fields = {_local(c.tag): c for c in elem}
        src, dst = fields.get("source"), fields.get("target")
        if src is None or dst is None or not src.text or not dst.text: continue
        u, v = src.text.strip(), dst.text.strip()
        installed = fields.get("preInstalledModule")
        raw_cap = next((float(c.text) for c in installed.iter() if _local(c.tag) == "capacity" and c.text), None) if installed is not None else None
        additional = fields.get("additionalModules")
        extra_caps = [float(c.text) for c in additional.iter() if _local(c.tag) == "capacity" and c.text] if additional is not None else []
        attrs = {"raw_capacity": raw_cap, "additional_capacities": extra_caps, "bandwidth": None, "latency": _distance_latency(g.nodes[u], g.nodes[v]) if u in g and v in g else None, "loss": 0.0}
        if u != v:
            if g.has_edge(u, v):
                previous = g[u][v]
                if (raw_cap or 0) > (previous.get("raw_capacity") or 0): previous.update(attrs)
            else: g.add_edge(u, v, **attrs)
    demands = []
    for elem in root.iter():
        if _local(elem.tag) != "demand": continue
        fields = {_local(c.tag): c.text for c in elem}
        if fields.get("source") and fields.get("target") and fields.get("demandValue"):
            demands.append((fields["source"].strip(), fields["target"].strip(), float(fields["demandValue"])))
    g = _relabel(_largest_component(g))
    relabel = {data["label"]: node for node, data in g.nodes(data=True)}
    demands = [(relabel[s], relabel[t], value) for s, t, value in demands if s in relabel and t in relabel]
    return assign_link_attributes(g, np.random.default_rng(0)), demands


def _router_subgraph(graph: nx.Graph) -> nx.Graph:
    routers = [n for n, attrs in graph.nodes(data=True) if attrs.get("type", "router") == "router"]
    return graph.subgraph(routers)


def cyclomatic_number(graph: nx.Graph) -> int:
    """Return E-N+1 for the connected router-only subgraph."""
    routers = _router_subgraph(graph)
    return routers.number_of_edges() - routers.number_of_nodes() + (1 if routers else 0)


def path_diversity(graph: nx.Graph) -> float:
    """Fraction of router pairs joined by at least two edge-disjoint paths."""
    routers = _router_subgraph(graph)
    pairs = list(itertools.combinations(routers.nodes, 2))
    if not pairs:
        return 0.0
    resilient = routers.copy()
    resilient.remove_edges_from(nx.bridges(resilient))
    component_sizes = [len(c) for c in nx.connected_components(resilient)]
    resilient_pairs = sum(size * (size - 1) // 2 for size in component_sizes)
    return resilient_pairs / len(pairs)


def load_repetita(graph_path: str | Path, demands_path: str | Path | None = None) -> tuple[nx.Graph, list[tuple[str, str, float]]]:
    """Load REPETITA topology (bandwidth kbps, delay microseconds) and demands."""
    path = Path(graph_path)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if len(lines) < 4 or not lines[0].startswith("NODES "):
        raise ValueError(f"invalid REPETITA graph header in {path}")
    n = int(lines[0].split()[1]); g = nx.Graph(name=path.stem, source="repetita")
    if lines[1].strip() != "label x y": raise ValueError("unexpected REPETITA node columns")
    for idx, line in enumerate(lines[2:2+n]):
        cols = line.split()
        if len(cols) < 3: raise ValueError(f"invalid node row: {line}")
        g.add_node(str(idx), type="router", label=cols[0], source_index=idx, x=float(cols[1]), y=float(cols[2]))
    pos = 2+n
    while pos < len(lines) and not lines[pos].strip(): pos += 1
    if pos + 1 >= len(lines) or not lines[pos].startswith("EDGES ") or lines[pos+1].strip() != "label src dest weight bw delay":
        raise ValueError("unexpected REPETITA edge header")
    for line in lines[pos+2:]:
        cols = line.split()
        if not cols: break
        if len(cols) != 6: raise ValueError(f"invalid edge row: {line}")
        _, src, dst, _weight, bw, delay = cols
        u, v = str(int(src)), str(int(dst))
        if u == v: continue
        # REPETITA stores bandwidth in kbps and delay in microseconds.
        attrs = {"bandwidth": float(bw) / 1000.0, "latency": float(delay) / 1000.0,
                 "raw_delay_us": float(delay), "loss": 0.0}
        if g.has_edge(u, v):
            if attrs["bandwidth"] > g[u][v]["bandwidth"]: g[u][v].update(attrs)
        else: g.add_edge(u, v, **attrs)
    g = _relabel(_largest_component(g))
    # Demand endpoints in this format are numeric node indices.
    old_to_new = {str(data["source_index"]): node for node, data in g.nodes(data=True)}
    demands: list[tuple[str, str, float]] = []
    if demands_path is not None:
        dlines = Path(demands_path).read_text(encoding="utf-8", errors="replace").splitlines()
        if len(dlines) < 2 or not dlines[0].startswith("DEMANDS ") or dlines[1].strip() != "label src dest bw":
            raise ValueError("unexpected REPETITA demands header")
        for line in dlines[2:]:
            cols = line.split()
            if len(cols) != 4: continue
            _, src, dst, value = cols
            s, t = old_to_new.get(src), old_to_new.get(dst)
            # Demand bw shares the topology's kbps unit; normalize it to Mbps.
            if s and t: demands.append((s, t, float(value) / 1000.0))
    return assign_link_attributes(g, np.random.default_rng(0)), demands


def generate_synthetic(kind: str, n: int, seed: int) -> nx.Graph:
    """Generate a connected router graph using a local deterministic seed."""
    if not 5 <= n <= 50: raise ValueError("router count must be between 5 and 50")
    gen = np.random.default_rng(seed)
    if kind not in {"ba", "waxman", "er"}: raise ValueError("kind must be ba, waxman, or er")
    for attempt in range(100):
        s = int(gen.integers(0, 2**31-1)); py = np.random.RandomState(s)
        if kind == "ba": g = nx.barabasi_albert_graph(n, min(2, n-1), seed=py)
        elif kind == "er": g = nx.erdos_renyi_graph(n, min(0.25, max(0.12, 2.5/n)), seed=py)
        else: g = nx.waxman_graph(n, beta=0.5, alpha=0.5, seed=py)
        if nx.is_connected(g): break
    else: g = nx.complete_graph(n)
    g.graph.update(name=f"{kind}-{n}-seed{seed}", source="synthetic")
    g = _relabel(g)
    for idx, node in enumerate(sorted(g.nodes, key=lambda v: int(v[1:]))):
        # Coordinates are stable and give Waxman-style layouts a distance metric.
        angle = 2 * math.pi * idx / n
        g.nodes[node].update(type="router", label=node, x=100 * math.cos(angle), y=50 * math.sin(angle))
    return assign_link_attributes(g, np.random.default_rng(seed))


def attach_hosts(graph: nx.Graph, num_hosts: int, rng: np.random.Generator | int | None) -> nx.Graph:
    """Attach leaf hosts to randomly selected router nodes."""
    gen = _rng(rng); routers = sorted(n for n, d in graph.nodes(data=True) if d.get("type") == "router")
    if not routers and num_hosts: raise ValueError("cannot attach hosts without routers")
    start = sum(1 for n in graph if str(n).startswith("H"))
    for i in range(num_hosts):
        host = f"H{start+i}"; router = routers[int(gen.integers(0, len(routers)))]
        graph.add_node(host, type="host", label=host)
        graph.add_edge(host, router, bandwidth=1000.0, latency=0.5, loss=0.0)
    return graph


def validate(graph: nx.Graph) -> list[str]:
    """Return all detected topology invariant violations."""
    errors: list[str] = []
    if graph.is_directed() or graph.is_multigraph(): errors.append("graph must be simple and undirected")
    routers = [n for n, d in graph.nodes(data=True) if d.get("type") == "router"]
    hosts = [n for n, d in graph.nodes(data=True) if d.get("type") == "host"]
    if len(routers) < 2: errors.append("at least two routers are required")
    if any(d.get("type") not in {"router", "host"} for _, d in graph.nodes(data=True)): errors.append("invalid node type")
    if nx.number_of_selfloops(graph): errors.append("self-loops are not allowed")
    if graph and not nx.is_connected(graph): errors.append("graph must be connected")
    if len(routers) >= 2 and not nx.is_connected(graph.subgraph(routers)): errors.append("router subgraph must be connected")
    for node in hosts:
        if graph.degree(node) < 1: errors.append(f"host {node} is isolated")
        if graph.degree(node) != 1: errors.append(f"host {node} must have degree one")
        if any(graph.nodes[v].get("type") != "router" for v in graph.neighbors(node)): errors.append(f"host {node} must connect only to routers")
    for u, v, a in graph.edges(data=True):
        for key in ("bandwidth", "latency", "loss"):
            if key not in a: errors.append(f"edge {u}-{v} missing {key}"); continue
            try: value = float(a[key])
            except (TypeError, ValueError): errors.append(f"edge {u}-{v} has invalid {key}"); continue
            if not math.isfinite(value): errors.append(f"edge {u}-{v} has non-finite {key}")
            elif key in {"bandwidth", "latency"} and value <= 0: errors.append(f"edge {u}-{v} {key} must be positive")
            elif key == "loss" and not 0 <= value <= 100: errors.append(f"edge {u}-{v} loss must be between 0 and 100")
    if graph.graph.get("source") not in _SOURCE: errors.append("invalid graph source")
    return errors


def to_json(graph: nx.Graph) -> dict[str, Any]:
    """Serialize using the stable shared topology schema."""
    return {"name": str(graph.graph.get("name", "unnamed")),
            "nodes": [{"id": str(n), "type": d.get("type", "router")} for n, d in sorted(graph.nodes(data=True), key=lambda x: str(x[0]))],
            "links": [{"src": str(u), "dst": str(v), **{k: float(d[k]) for k in ("bandwidth", "latency", "loss")}} for u, v, d in sorted(graph.edges(data=True), key=lambda x: tuple(sorted((str(x[0]), str(x[1])))))]}


def from_json(data: dict[str, Any]) -> nx.Graph:
    """Validate and restore the stable shared topology schema."""
    model = TopologyModel.model_validate(data)
    g = nx.Graph(name=model.name, source="user")
    for node in model.nodes: g.add_node(node.id, type=node.type)
    for link in model.links: g.add_edge(link.src, link.dst, bandwidth=link.bandwidth, latency=link.latency, loss=link.loss)
    return g


def fingerprint(graph: nx.Graph) -> str:
    """Hash graph size and sorted degree sequence, independent of labels."""
    payload = (graph.number_of_nodes(), graph.number_of_edges(), tuple(sorted(dict(graph.degree()).values())))
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()


def family_key(name: str) -> str:
    """Normalize a network name to lowercase ASCII letters."""
    return re.sub(r"[^a-z]", "", re.sub(r"\d+", "", name.lower()))
