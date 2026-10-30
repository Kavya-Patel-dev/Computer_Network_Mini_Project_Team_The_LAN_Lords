"""K-shortest candidate routes with load-aware ranking and strict availability checks."""
from __future__ import annotations

from dataclasses import dataclass
from itertools import islice
import math
from typing import Any, Iterable

import networkx as nx


@dataclass(frozen=True)
class PathResult:
    paths: tuple[tuple[Any, ...], ...]
    no_route: bool


def _usable_graph(graph: nx.Graph, load_mbps: dict[tuple[str, str], float] | None = None,
                  load_weight: float = 1.0) -> nx.Graph:
    if not math.isfinite(load_weight) or load_weight < 0:
        raise ValueError("load_weight must be finite and nonnegative")
    normalized_loads = {tuple(sorted((str(u), str(v)))): value for (u, v), value in (load_mbps or {}).items()}
    usable = nx.Graph()
    for node, attrs in graph.nodes(data=True):
        if attrs.get("up", True): usable.add_node(node, **attrs)
    for u, v, attrs in graph.edges(data=True):
        if u not in usable or v not in usable or not attrs.get("up", True): continue
        cap = float(attrs.get("capacity", attrs.get("bandwidth", 0.0)))
        prop = float(attrs.get("latency", 0.1))
        if not math.isfinite(cap) or cap < 0 or not math.isfinite(prop) or prop < 0:
            raise ValueError(f"invalid capacity/latency on link {u}-{v}")
        if cap == 0: continue
        key = tuple(sorted((str(u), str(v))))
        load = float(normalized_loads.get(key, 0.0))
        if not math.isfinite(load) or load < 0: raise ValueError(f"invalid load on link {u}-{v}")
        edge_attrs = dict(attrs)
        edge_attrs["weight"] = prop + load_weight * load / cap
        usable.add_edge(u, v, **edge_attrs)
    return usable


def candidate_paths(graph: nx.Graph, source: str, destination: str, k: int = 4,
                    load_mbps: dict[tuple[str, str], float] | None = None,
                    load_weight: float = 1.0, edge_disjoint: bool = False) -> PathResult:
    if k <= 0: raise ValueError("k must be positive")
    if source not in graph or destination not in graph or source == destination:
        raise ValueError("source/destination must be distinct valid graph nodes")
    usable = _usable_graph(graph, load_mbps, load_weight)
    if source not in usable or destination not in usable or not nx.has_path(usable, source, destination):
        return PathResult((), True)
    paths: list[tuple[Any, ...]] = []
    if edge_disjoint:
        try:
            for path in nx.edge_disjoint_paths(usable, source, destination):
                paths.append(tuple(path))
                if len(paths) >= k: break
        except (nx.NetworkXError, nx.NetworkXNoPath):
            pass
        paths = [p for p in paths if path_is_available(graph, p, source, destination)]
        return PathResult(tuple(paths[:k]), not bool(paths))
    # Yen's K-shortest simple paths; the NetworkX generator is Yen-based.
    try:
        for path in islice(nx.shortest_simple_paths(usable, source, destination, weight="weight"), k * 3):
            item = tuple(path)
            if item not in paths: paths.append(item)
            if len(paths) >= k: break
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        pass
    paths = [p for p in paths if path_is_available(graph, p, source, destination)]
    return PathResult(tuple(paths[:k]), not bool(paths))


def path_is_available(graph: nx.Graph, path: Iterable[Any], source: Any = None,
                      destination: Any = None) -> bool:
    nodes = tuple(path)
    if len(nodes) < 2 or (source is not None and nodes[0] != source) or (destination is not None and nodes[-1] != destination):
        return False
    if any(n not in graph or not graph.nodes[n].get("up", True) for n in nodes): return False
    return all(graph.has_edge(u, v) and graph[u][v].get("up", True)
               and float(graph[u][v].get("capacity", graph[u][v].get("bandwidth", 0))) > 0
               for u, v in zip(nodes, nodes[1:]))
