"""Finite numeric state snapshots and a fixed-length past/current history."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math

import networkx as nx
import numpy as np


@dataclass(frozen=True)
class NetworkSnapshot:
    node_features: np.ndarray  # columns: normalized incident load, UP flag
    edge_features: np.ndarray  # utilization, latency ms, loss probability, UP flag, capacity Mbps


class NetworkMonitor:
    def __init__(self, graph: nx.Graph, max_latency_ms: float = 10_000.0):
        if not math.isfinite(max_latency_ms) or max_latency_ms <= 0:
            raise ValueError("max_latency_ms must be finite and positive")
        self.nodes = tuple(sorted(graph.nodes, key=str))
        self.edges = tuple(sorted((tuple(sorted((u, v), key=str)) for u, v in graph.edges), key=lambda e: (str(e[0]), str(e[1]))))
        self.max_latency_ms = float(max_latency_ms)

    def snapshot(self, graph: nx.Graph, loads: dict[tuple[str, str], float],
                 latencies: dict[tuple[str, str], float], losses: dict[tuple[str, str], float]) -> NetworkSnapshot:
        incident = {n: 0.0 for n in self.nodes}
        for (u, v), load in loads.items(): incident[u] += load; incident[v] += load
        node_rows = []
        for n in self.nodes:
            capacity = sum(float(graph[n][v].get("capacity", 0)) for v in graph.neighbors(n))
            if not math.isfinite(capacity) or capacity < 0: raise ValueError(f"invalid incident capacity at node {n}")
            node_rows.append([incident[n] / max(capacity, 1e-12), float(graph.nodes[n].get("up", True))])
        edge_rows = []
        for u, v in self.edges:
            key = tuple(sorted((u, v), key=str)); attrs = graph[u][v]
            cap = float(attrs.get("capacity", 0)); load = float(loads.get(key, 0.0))
            latency = float(latencies.get(key, attrs.get("latency", 0)))
            loss = float(losses.get(key, 0.0))
            if not math.isfinite(cap) or cap < 0 or not math.isfinite(load) or load < 0:
                raise ValueError(f"invalid capacity/load on link {u}-{v}")
            if not math.isfinite(latency) or latency < 0 or not math.isfinite(loss) or not 0 <= loss <= 1:
                raise ValueError(f"invalid latency/loss on link {u}-{v}")
            edge_rows.append([load / cap if cap > 0 else 0.0,
                              min(latency, self.max_latency_ms), loss,
                              float(attrs.get("up", True)), max(0.0, cap)])
        node_arr = np.asarray(node_rows, dtype=np.float32).reshape(len(self.nodes), 2)
        edge_arr = np.asarray(edge_rows, dtype=np.float32).reshape(len(self.edges), 5)
        if not np.isfinite(node_arr).all() or not np.isfinite(edge_arr).all(): raise FloatingPointError("monitor produced non-finite features")
        return NetworkSnapshot(node_arr, edge_arr)


class HistoryBuffer:
    def __init__(self, length: int, node_shape: tuple[int, ...], edge_shape: tuple[int, ...]):
        if length <= 0: raise ValueError("history length must be positive")
        self.length = length; self.node_shape = node_shape; self.edge_shape = edge_shape
        self._items: deque[NetworkSnapshot] = deque(maxlen=length)

    def reset(self, initial: NetworkSnapshot) -> None:
        self._items.clear()
        for _ in range(self.length): self._items.append(NetworkSnapshot(initial.node_features.copy(), initial.edge_features.copy()))

    def append(self, snapshot: NetworkSnapshot) -> None:
        if snapshot.node_features.shape != self.node_shape or snapshot.edge_features.shape != self.edge_shape:
            raise ValueError("snapshot shape changed")
        self._items.append(NetworkSnapshot(snapshot.node_features.copy(), snapshot.edge_features.copy()))

    def arrays(self) -> tuple[np.ndarray, np.ndarray]:
        if not self._items: raise RuntimeError("history has not been initialized")
        return (np.stack([s.node_features for s in self._items]),
                np.stack([s.edge_features for s in self._items]))
