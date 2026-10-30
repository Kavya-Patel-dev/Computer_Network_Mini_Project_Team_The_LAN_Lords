"""Seedable traffic arrival and demand models; rates/demands use Mbps."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Sequence

import numpy as np
import networkx as nx

from .qos import QoSClass


@dataclass(frozen=True)
class Flow:
    source: str
    destination: str
    demand_mbps: float
    qos_class: QoSClass = QoSClass.BULK
    priority: int = 2
    duration_steps: int = 1
    flow_id: str = "flow"

    def __post_init__(self) -> None:
        object.__setattr__(self, "qos_class", QoSClass(self.qos_class))
        if self.source == self.destination:
            raise ValueError("flow source and destination must differ")
        if not np.isfinite(self.demand_mbps) or self.demand_mbps < 0:
            raise ValueError("flow demand must be finite and nonnegative Mbps")
        if self.duration_steps <= 0 or self.priority < 0:
            raise ValueError("flow duration_steps must be positive and priority nonnegative")


class TrafficGenerator:
    """One request per decision step, with topology-independent OD models."""
    def __init__(self, nodes: Sequence[str], demand_mbps: float = 1.0,
                 qos_class: QoSClass = QoSClass.BULK,
                 intensity: float = 0.05, duration_mean_steps: float = 20.0,
                 duration_mean_by_qos: dict[QoSClass | str, float] | None = None,
                 demand_range_mbps: tuple[float, float] | None = None):
        if len(set(nodes)) < 2:
            raise ValueError("traffic generation requires at least two distinct nodes")
        if not all(np.isfinite(x) for x in (demand_mbps, intensity, duration_mean_steps)) or demand_mbps < 0 or intensity < 0 or duration_mean_steps < 1:
            raise ValueError("demand and intensity must be nonnegative; duration mean must be at least one step")
        self.nodes = tuple(map(str, nodes)); self.arrival_rate = 1.0
        self.demand_mbps = float(demand_mbps)
        self.intensity = float(intensity)
        self.qos_class = QoSClass(qos_class); self.rng = np.random.default_rng()
        self.duration_mean_steps = float(duration_mean_steps)
        self.duration_mean_by_qos = {
            QoSClass(key): float(value)
            for key, value in (duration_mean_by_qos or {}).items()
        }
        if any(not np.isfinite(value) or value < 1 for value in self.duration_mean_by_qos.values()):
            raise ValueError("QoS flow-duration means must be finite and at least one step")
        self.demand_range_mbps: tuple[float, float] | None = None
        if demand_range_mbps is not None:
            self._set_demand_range(demand_range_mbps)
        self.network_calibrated = False
        self._flow_counter = 0

    def _set_demand_range(self, demand_range_mbps: tuple[float, float]) -> None:
        if len(demand_range_mbps) != 2:
            raise ValueError("demand_range_mbps must have lower and upper bounds")
        low, high = map(float, demand_range_mbps)
        if not np.isfinite(low) or not np.isfinite(high) or low < 0 or high < low:
            raise ValueError("demand range must be finite and satisfy 0 <= low <= high")
        self.demand_range_mbps = (low, high)

    @property
    def mean_duration_steps(self) -> float:
        """Configured geometric mean for the generator's default QoS class."""
        return self.duration_mean_by_qos.get(self.qos_class, self.duration_mean_steps)

    def od_pair_weights(self) -> list[tuple[str, str, float]]:
        """Unnormalized OD sampling weights used to calibrate mean path length."""
        return [(source, destination, 1.0)
                for source in self.nodes for destination in self.nodes
                if source != destination]

    def configure_for_network(self, graph: nx.Graph, router_nodes: Sequence[str],
                              target_intensity: float,
                              demand_fraction_range: tuple[float, float] = (0.05, 0.20)
                              ) -> dict[str, float | str]:
        """Set modest flow demand and lifetime for a target mean link load.

        Arrival rate is fixed at one request per decision step. Little's law
        sets duration to intensity * total capacity / (mean demand * mean hops).
        Path hops count router-to-router links only; OD expectations use this
        generator's sampling distribution and latency-weighted shortest paths.
        """
        if not np.isfinite(target_intensity) or target_intensity < 0:
            raise ValueError("target_intensity must be finite and nonnegative")
        routers = set(map(str, router_nodes))
        capacities = [float(attrs.get("capacity", attrs.get("bandwidth", 0.0)))
                      for u, v, attrs in graph.edges(data=True)
                      if str(u) in routers and str(v) in routers]
        if not capacities or any(not np.isfinite(value) or value <= 0 for value in capacities):
            raise ValueError("network calibration requires positive router-router capacities")
        total_capacity = float(sum(capacities))
        median_capacity = float(np.median(capacities))
        low_fraction, high_fraction = map(float, demand_fraction_range)
        if (not np.isfinite(low_fraction) or not np.isfinite(high_fraction)
                or low_fraction < 0 or high_fraction < low_fraction):
            raise ValueError("demand fractions must satisfy 0 <= low <= high")
        self._set_demand_range((low_fraction * median_capacity,
                                high_fraction * median_capacity))
        mean_demand = (sum(self.demand_range_mbps) / 2.0)
        self.demand_mbps = mean_demand

        weighted_hops = 0.0
        total_weight = 0.0
        for source, destination, weight in self.od_pair_weights():
            if weight <= 0:
                continue
            try:
                path = nx.shortest_path(graph, source, destination, weight="latency")
            except (nx.NetworkXNoPath, nx.NodeNotFound) as exc:
                raise ValueError(f"traffic OD pair {source}->{destination} is not routable") from exc
            hops = sum(1 for u, v in zip(path, path[1:])
                       if str(u) in routers and str(v) in routers)
            weighted_hops += float(weight) * hops
            total_weight += float(weight)
        mean_path_hops = weighted_hops / total_weight if total_weight else 0.0
        if mean_path_hops <= 0 or mean_demand <= 0:
            raise ValueError("cannot calibrate traffic with zero mean demand or path length")
        self.intensity = float(target_intensity)
        requested_duration = (self.intensity * total_capacity /
                              (mean_demand * mean_path_hops))
        calibrated_duration = float(np.clip(requested_duration, 3.0, 200.0))
        self.duration_mean_steps = calibrated_duration
        if self.qos_class in self.duration_mean_by_qos:
            self.duration_mean_by_qos[self.qos_class] = calibrated_duration
        achieved_intensity = (calibrated_duration * mean_demand * mean_path_hops
                              / total_capacity)
        self.network_calibrated = True
        return {"median_router_capacity_mbps": median_capacity,
                "total_router_capacity_mbps": total_capacity,
                "mean_demand_mbps": mean_demand,
                "mean_duration_steps": self.mean_duration_steps,
                "mean_router_path_hops": mean_path_hops,
                "arrival_rate": 1.0,
                "requested_duration_steps": requested_duration,
                "duration_clamp": ("low" if requested_duration < 3.0 else
                                    "high" if requested_duration > 200.0 else "none"),
                "target_intensity": self.intensity,
                "achievable_intensity": achieved_intensity}

    def reset(self, seed: int | None = None) -> None:
        self.rng = np.random.default_rng(seed); self._flow_counter = 0

    def _flow(self, source: str | None = None, destination: str | None = None,
              demand: float | None = None, qos: QoSClass | None = None,
              duration: int | None = None) -> Flow:
        src = source if source is not None else self.nodes[int(self.rng.integers(len(self.nodes)))]
        if destination is None:
            choices = [n for n in self.nodes if n != src]
            dst = choices[int(self.rng.integers(len(choices)))]
        else:
            dst = destination
        self._flow_counter += 1
        flow_qos = qos or self.qos_class
        if demand is not None:
            offered = float(demand)
        elif self.demand_range_mbps is not None:
            low, high = self.demand_range_mbps
            offered = float(self.rng.uniform(low, high))
        else:
            offered = self.demand_mbps
        if duration is None:
            mean_duration = self.duration_mean_by_qos.get(flow_qos, self.duration_mean_steps)
            duration = int(self.rng.geometric(1.0 / mean_duration))
        return Flow(str(src), str(dst), offered,
                    flow_qos, self._priority(flow_qos), duration,
                    f"flow-{self._flow_counter}")

    @staticmethod
    def _priority(qos: QoSClass) -> int:
        return {QoSClass.REAL_TIME: 4, QoSClass.STREAMING: 3,
                QoSClass.BULK: 2, QoSClass.BACKGROUND: 1}[qos]

    def sample_flow(self, **kwargs) -> Flow:
        return self._flow(**kwargs)

    def step(self) -> list[Flow]:
        """Generate exactly one new request for this decision step."""
        self.arrival_rate = 1.0
        return [self.sample_flow()]


class PoissonTrafficGenerator(TrafficGenerator):
    """Uniform random OD selection with one request per decision step."""


class GravityTrafficGenerator(TrafficGenerator):
    """Gravity OD model: intensity is wi*wj/(cost**distance_exponent)."""
    def __init__(self, nodes: Sequence[str], weights: dict[str, float], costs: dict[tuple[str, str], float],
                 distance_exponent: float = 1.0, **kwargs):
        super().__init__(nodes, **kwargs)
        if any(n not in self.nodes or w < 0 or not np.isfinite(w) for n, w in weights.items()):
            raise ValueError("gravity weights must be finite, nonnegative, and refer to known nodes")
        self.weights = {n: float(weights.get(n, 1.0)) for n in self.nodes}
        self.costs = {}
        for a in self.nodes:
            for b in self.nodes:
                if a != b:
                    raw_cost = costs.get((a, b), costs.get((b, a)))
                    if raw_cost is None: raise ValueError(f"gravity cost missing for OD pair {a}->{b}")
                    cost = float(raw_cost)
                    if cost <= 0 or not np.isfinite(cost): raise ValueError("gravity costs must be positive finite")
                    self.costs[a, b] = cost
        self.distance_exponent = float(distance_exponent)
        if not np.isfinite(self.distance_exponent) or self.distance_exponent < 0: raise ValueError("distance_exponent must be finite and nonnegative")

    def sample_flow(self, **kwargs) -> Flow:
        pairs = [(a, b) for a in self.nodes for b in self.nodes if a != b]
        intensity = np.array([self.weights[a] * self.weights[b] / self.costs[a, b] ** self.distance_exponent
                              for a, b in pairs], dtype=float)
        if intensity.sum() == 0: raise ValueError("gravity model has zero total OD intensity")
        a, b = pairs[int(self.rng.choice(len(pairs), p=intensity / intensity.sum()))]
        kwargs.setdefault("source", a); kwargs.setdefault("destination", b)
        return self._flow(**kwargs)

    def od_pair_weights(self) -> list[tuple[str, str, float]]:
        return [(a, b, self.weights[a] * self.weights[b] /
                 self.costs[a, b] ** self.distance_exponent)
                for a in self.nodes for b in self.nodes if a != b]


class HotspotTrafficGenerator(TrafficGenerator):
    """Bias OD endpoint selection toward configured hotspots by a multiplier."""
    def __init__(self, nodes: Sequence[str], hotspots: Iterable[str], hotspot_multiplier: float = 3.0, **kwargs):
        super().__init__(nodes, **kwargs)
        self.hotspots = set(map(str, hotspots)); self.multiplier = float(hotspot_multiplier)
        if not self.hotspots <= set(self.nodes) or self.multiplier < 1 or not np.isfinite(self.multiplier):
            raise ValueError("hotspots must be valid nodes and multiplier finite >= 1")

    def sample_flow(self, **kwargs) -> Flow:
        w = np.array([self.multiplier if n in self.hotspots else 1.0 for n in self.nodes], dtype=float)
        src = self.nodes[int(self.rng.choice(len(self.nodes), p=w / w.sum()))]
        choices = [n for n in self.nodes if n != src]
        dw = np.array([self.multiplier if n in self.hotspots else 1.0 for n in choices], dtype=float)
        dst = choices[int(self.rng.choice(len(choices), p=dw / dw.sum()))]
        kwargs.setdefault("source", src); kwargs.setdefault("destination", dst)
        return self._flow(**kwargs)

    def od_pair_weights(self) -> list[tuple[str, str, float]]:
        weights = {node: self.multiplier if node in self.hotspots else 1.0
                   for node in self.nodes}
        total_weight = sum(weights.values())
        return [(source, destination,
                 weights[source] * weights[destination] / (total_weight - weights[source]))
                for source in self.nodes for destination in self.nodes
                if source != destination]


@dataclass(frozen=True)
class TrafficSpike:
    start_time: float
    duration: float
    multiplier: float
    affected_nodes: frozenset[str] = frozenset()
    affected_classes: frozenset[QoSClass] = frozenset()

    def __post_init__(self) -> None:
        if not all(np.isfinite(x) for x in (self.start_time, self.duration, self.multiplier)) or self.start_time < 0 or self.duration <= 0 or self.multiplier < 1:
            raise ValueError("spike start >= 0, duration > 0, multiplier >= 1 required")
        object.__setattr__(self, "affected_nodes", frozenset(map(str, self.affected_nodes)))
        object.__setattr__(self, "affected_classes", frozenset(QoSClass(c) for c in self.affected_classes))

    def applies(self, time: float, flow: Flow) -> bool:
        active = self.start_time <= time < self.start_time + self.duration
        nodes_match = not self.affected_nodes or flow.source in self.affected_nodes or flow.destination in self.affected_nodes
        class_match = not self.affected_classes or flow.qos_class in self.affected_classes
        return active and nodes_match and class_match


@dataclass(frozen=True)
class DiurnalPattern:
    period: float = 24.0
    baseline: float = 1.0
    amplitude: float = 0.5
    peak_time: float = 15.0

    def multiplier(self, time: float) -> float:
        if not all(np.isfinite(x) for x in (time, self.period, self.baseline, self.amplitude, self.peak_time)) or self.period <= 0 or self.baseline < abs(self.amplitude):
            raise ValueError("period must be positive and baseline >= |amplitude|")
        phase = 2 * np.pi * ((time - self.peak_time) % self.period) / self.period
        return float(self.baseline + self.amplitude * np.cos(phase))


class SNDlibReplay(TrafficGenerator):
    """Replay parsed SNDlib demand matrix values with explicit node mapping.

    Parsed values can be calibrated by one global factor so the busiest link
    under latency-weighted static shortest paths reaches ``scale_to_max_util``.
    """
    def __init__(self, nodes: Sequence[str], demands: Sequence[tuple[str, str, float]],
                 node_mapping: dict[str, str] | None = None, incompatible: str = "raise",
                 scale_to_max_util: float | None = None,
                 topology_graph: nx.Graph | None = None, **kwargs):
        super().__init__(nodes, **kwargs)
        if incompatible not in {"raise", "skip"}: raise ValueError("incompatible must be 'raise' or 'skip'")
        mapping = node_mapping or {n: n for n in self.nodes}
        rows = []
        for source, destination, demand in demands:
            src, dst = mapping.get(source), mapping.get(destination)
            valid = src in self.nodes and dst in self.nodes and src != dst and np.isfinite(demand) and demand >= 0
            if not valid:
                if incompatible == "raise": raise ValueError(f"SNDlib demand cannot map to valid pair: {source}->{destination}")
                continue
            rows.append((str(src), str(dst), float(demand)))
        if not rows: raise ValueError("SNDlib replay has no compatible demands")
        if scale_to_max_util is not None:
            if (not np.isfinite(scale_to_max_util) or scale_to_max_util <= 0
                    or topology_graph is None):
                raise ValueError("scale_to_max_util must be positive and requires topology_graph")
            if topology_graph.is_directed() or topology_graph.is_multigraph():
                raise ValueError("SNDlib scaling requires a simple undirected topology_graph")
            edge_loads = {self._edge_key(u, v): 0.0 for u, v in topology_graph.edges}
            for source, destination, demand in rows:
                try:
                    path = nx.shortest_path(topology_graph, source, destination, weight="latency")
                except (nx.NetworkXNoPath, nx.NodeNotFound) as exc:
                    raise ValueError(f"cannot statically route SNDlib demand {source}->{destination}") from exc
                for u, v in zip(path, path[1:]):
                    edge_loads[self._edge_key(u, v)] += demand
            utilizations = []
            for u, v in topology_graph.edges:
                capacity = float(topology_graph[u][v].get("capacity", topology_graph[u][v].get("bandwidth", 0.0)))
                if not np.isfinite(capacity) or capacity <= 0:
                    raise ValueError(f"invalid link capacity on {u}-{v} for SNDlib scaling")
                utilizations.append(edge_loads[self._edge_key(u, v)] / capacity)
            current_max = max(utilizations, default=0.0)
            if current_max <= 0:
                raise ValueError("cannot scale zero aggregate SNDlib demand")
            factor = float(scale_to_max_util) / current_max
            rows = [(src, dst, demand * factor) for src, dst, demand in rows]
        self.demands = tuple(rows); self._cursor = 0

    @staticmethod
    def _edge_key(u, v):
        return tuple(sorted((u, v), key=str))

    @classmethod
    def from_sndlib(cls, nodes: Sequence[str], path, node_mapping: dict[str, str] | None = None,
                    incompatible: str = "raise", scale_to_max_util: float | None = None,
                    topology_graph: nx.Graph | None = None,
                    **kwargs) -> "SNDlibReplay":
        """Read demands through the Day 1 SNDlib loader, then validate/map them."""
        from .topology import load_sndlib
        graph, demands = load_sndlib(path)
        scale_graph = topology_graph if topology_graph is not None else graph
        return cls(nodes, demands, node_mapping=node_mapping, incompatible=incompatible,
                   scale_to_max_util=scale_to_max_util,
                   topology_graph=scale_graph if scale_to_max_util is not None else None,
                   **kwargs)

    def reset(self, seed: int | None = None) -> None:
        super().reset(seed); self._cursor = 0

    def od_pair_weights(self) -> list[tuple[str, str, float]]:
        return list(self.demands)

    def sample_flow(self, **kwargs) -> Flow:
        if self.demand_range_mbps is not None:
            weights = np.asarray([max(0.0, demand) for _, _, demand in self.demands], dtype=float)
            if not weights.sum():
                weights[:] = 1.0
            index = int(self.rng.choice(len(self.demands), p=weights / weights.sum()))
            source, destination, _demand = self.demands[index]
            return self._flow(source=source, destination=destination, **kwargs)
        source, destination, demand = self.demands[self._cursor % len(self.demands)]
        self._cursor += 1
        return self._flow(source=source, destination=destination, demand=demand, **kwargs)
