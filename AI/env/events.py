"""Scheduled link/router failures and bandwidth degradation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import networkx as nx


@dataclass(frozen=True)
class NetworkEvent:
    time: int

    def __post_init__(self) -> None:
        if self.time < 0: raise ValueError("event time must be nonnegative")


@dataclass(frozen=True)
class LinkFailure(NetworkEvent):
    edge: tuple[str, str]


@dataclass(frozen=True)
class RouterFailure(NetworkEvent):
    router: str


@dataclass(frozen=True)
class BandwidthDrop(NetworkEvent):
    edge: tuple[str, str]
    factor: float
    duration: int | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if not 0 < self.factor < 1: raise ValueError("bandwidth drop factor must be in (0,1)")
        if self.duration is not None and self.duration <= 0: raise ValueError("duration must be positive")


class EventManager:
    def __init__(self, events: Iterable[NetworkEvent] = ()):
        self.events = tuple(sorted(events, key=lambda e: e.time)); self.applied: set[int] = set()
        self.degradations: dict[tuple[str, str], list[tuple[int | None, float]]] = {}

    def reset(self) -> None:
        self.applied.clear(); self.degradations.clear()

    @staticmethod
    def _edge(graph: nx.Graph, edge: tuple[str, str]) -> dict:
        u, v = edge
        if not graph.has_edge(u, v): raise KeyError(f"event references unknown link {u}-{v}")
        return graph[u][v]

    def apply_due(self, graph: nx.Graph, time: int) -> list[NetworkEvent]:
        applied = []
        for idx, event in enumerate(self.events):
            if event.time > time: break
            if idx in self.applied: continue
            if isinstance(event, LinkFailure):
                attrs = self._edge(graph, event.edge)
                attrs["up"] = False; attrs["capacity"] = 0.0
            elif isinstance(event, RouterFailure):
                if event.router not in graph: raise KeyError(f"event references unknown router {event.router}")
                if graph.nodes[event.router].get("type", "router") != "router":
                    raise ValueError(f"event target {event.router} is not a router")
                graph.nodes[event.router]["up"] = False
                for _, _, attrs in graph.edges(event.router, data=True):
                    attrs["up"] = False; attrs["capacity"] = 0.0
            elif isinstance(event, BandwidthDrop):
                attrs = self._edge(graph, event.edge)
                restore_at = None if event.duration is None else time + event.duration
                self.degradations.setdefault(event.edge, []).append((restore_at, event.factor))
            else:
                raise TypeError(f"unsupported network event {type(event).__name__}")
            self.applied.add(idx); applied.append(event)
        for edge, factors in list(self.degradations.items()):
            active = [(expiry, factor) for expiry, factor in factors if expiry is None or expiry > time]
            attrs = self._edge(graph, edge)
            if attrs.get("up", True):
                attrs["capacity"] = float(attrs["base_capacity"]) * min((factor for _, factor in active), default=1.0)
            if active: self.degradations[edge] = active
            else: del self.degradations[edge]
        return applied


def restore_network(graph: nx.Graph, base_nodes: dict, base_edges: dict) -> None:
    for node, attrs in base_nodes.items(): graph.nodes[node].update(attrs)
    for edge, attrs in base_edges.items(): graph[edge[0]][edge[1]].update(attrs)
