"""Gymnasium environment for QoS-aware routing on a Day 1 topology.

Actions select one of K currently valid paths; action K is the explicit
no-route/idle sentinel. The observation carries a K-entry action mask.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from dataclasses import replace
from typing import Any, Iterable

import gymnasium as gym
from gymnasium import spaces
import networkx as nx
import numpy as np

from .events import BandwidthDrop, EventManager, LinkFailure, NetworkEvent, RouterFailure
from .latency import LatencyConfig, link_latency_ms, utilization
from .monitor import HistoryBuffer, NetworkMonitor, NetworkSnapshot
from .paths import PathResult, candidate_paths, path_is_available
from .qos import QoSClass, QoSProfile, profiles_with_overrides
from .reward import RewardConfig, route_reward
from .traffic import (DiurnalPattern, Flow, PoissonTrafficGenerator,
                      TrafficGenerator, TrafficSpike)


@dataclass(frozen=True)
class NetworkEnvConfig:
    k_paths: int = 4
    history_length: int = 4
    max_steps: int = 1000
    event_probability: float = 0.0
    bandwidth_drop_factor: float = 0.5
    congestion_loss_slope: float = 0.25
    loss_epsilon: float = 1e-6
    max_loss: float = 0.95
    max_queue_ms: float = 10_000.0
    intensity: float = 0.05
    demand_min_fraction: float = 0.05
    demand_max_fraction: float = 0.20
    hosts_per_router_fraction: float | None = 0.5
    minimum_hosts: int = 4
    render_mode: str | None = None

    def __post_init__(self) -> None:
        if not all(math.isfinite(x) for x in (self.event_probability,
                                               self.bandwidth_drop_factor, self.congestion_loss_slope,
                                               self.loss_epsilon, self.max_loss, self.max_queue_ms,
                                               self.intensity,
                                               self.demand_min_fraction, self.demand_max_fraction)) or self.k_paths <= 0 or self.history_length <= 0 or self.max_steps <= 0:
            raise ValueError("K, history, and max_steps must be positive")
        if (self.intensity < 0
                or self.demand_min_fraction < 0
                or self.demand_max_fraction < self.demand_min_fraction):
            raise ValueError("intensity or demand fractions are out of range")
        if self.minimum_hosts < 0 or (self.hosts_per_router_fraction is not None and
                (not math.isfinite(self.hosts_per_router_fraction) or self.hosts_per_router_fraction < 0)):
            raise ValueError("host fraction and minimum host count must be nonnegative")
        if not 0 <= self.event_probability <= 1 or not 0 < self.bandwidth_drop_factor < 1:
            raise ValueError("event_probability must be [0,1] and drop factor (0,1)")
        if not 0 <= self.max_loss <= 1 or self.congestion_loss_slope < 0 or self.loss_epsilon <= 0:
            raise ValueError("loss parameters out of range")


@dataclass
class ActiveFlow:
    flow: Flow
    path: tuple[str, ...]
    remaining_steps: int


def congestion_loss(util: float, slope: float = 0.25, max_loss: float = 0.95,
                    epsilon: float = 1e-6) -> float:
    """Deterministic monotonic overflow loss, zero below capacity and bounded."""
    if not all(math.isfinite(v) for v in (util, slope, max_loss, epsilon)) or util < 0 or slope < 0 or not 0 <= max_loss <= 1 or epsilon <= 0:
        raise ValueError("utilization/slope/loss parameters invalid")
    if util < 1.0 or max_loss == 0: return 0.0
    return min(max_loss, slope * (util - 1.0) + min(slope * epsilon, max_loss))


class NetworkRoutingEnv(gym.Env):
    metadata = {"render_modes": ["human", "ansi"], "render_fps": 1}

    def __init__(self, graph: nx.Graph, config: NetworkEnvConfig | None = None,
                 traffic_generator: TrafficGenerator | None = None,
                 events: Iterable[NetworkEvent] = (),
                 traffic_spikes: Iterable[TrafficSpike] = (),
                 diurnal_pattern: DiurnalPattern | None = None,
                 qos_profiles: dict[QoSClass | str, QoSProfile] | None = None,
                 reward_config: RewardConfig | None = None):
        super().__init__()
        if graph.is_directed() or graph.is_multigraph() or graph.number_of_nodes() < 2:
            raise ValueError("environment requires a simple undirected graph with at least two nodes")
        self.config = config or NetworkEnvConfig()
        self.graph = nx.Graph(graph)
        self.router_nodes = tuple(n for n in self.graph if self.graph.nodes[n].get("type", "router") == "router")
        if len(self.router_nodes) < 2: raise ValueError("routing requires at least two router nodes")
        self._ensure_host_count()
        self.host_nodes = tuple(n for n in self.graph if self.graph.nodes[n].get("type") == "host")
        self.nodes = tuple(sorted(self.graph.nodes, key=str)); self.node_index = {n: i for i, n in enumerate(self.nodes)}
        for _, attrs in self.graph.nodes(data=True): attrs.setdefault("up", True)
        for _, _, attrs in self.graph.edges(data=True):
            cap = float(attrs.get("bandwidth", attrs.get("capacity", 0.0)))
            latency = float(attrs.get("latency", 0.0))
            if not math.isfinite(cap) or cap <= 0 or not math.isfinite(latency) or latency < 0:
                raise ValueError("topology links need finite positive bandwidth and finite nonnegative latency")
            attrs.setdefault("base_capacity", cap); attrs.setdefault("capacity", cap); attrs.setdefault("up", True)
            attrs.setdefault("loss", 0.0)
        self.base_nodes = {n: dict(a) for n, a in self.graph.nodes(data=True)}
        self.base_edges = {(u, v): dict(a) for u, v, a in self.graph.edges(data=True)}
        if traffic_generator is None:
            self.traffic_nodes = self.host_nodes or self.router_nodes
            self.traffic = PoissonTrafficGenerator(self.traffic_nodes, demand_mbps=1.0,
                                                   intensity=self.config.intensity)
            self.traffic.configure_for_network(
                self.graph, self.router_nodes, self.config.intensity,
                (self.config.demand_min_fraction, self.config.demand_max_fraction))
        else:
            if not set(traffic_generator.nodes) <= set(self.graph.nodes):
                raise ValueError("traffic generator endpoints must exist in the topology")
            self.traffic = traffic_generator
            self.traffic_nodes = tuple(traffic_generator.nodes)
            if not self.traffic.network_calibrated:
                self.traffic.configure_for_network(
                    self.graph, self.router_nodes, self.config.intensity,
                    (self.config.demand_min_fraction, self.config.demand_max_fraction))
        self.events = EventManager(events)
        self.traffic_spikes = tuple(traffic_spikes); self.diurnal_pattern = diurnal_pattern
        self.profiles = profiles_with_overrides(qos_profiles)
        self.reward_config = reward_config or RewardConfig()
        self.latency_config = LatencyConfig(max_queue_ms=self.config.max_queue_ms)
        self.monitor = NetworkMonitor(self.graph, self.config.max_queue_ms)
        self.edge_index = np.asarray(
            [[self.node_index[u] for u, _ in self.monitor.edges],
             [self.node_index[v] for _, v in self.monitor.edges]], dtype=np.int32
        ).reshape(2, len(self.monitor.edges))
        self._node_static_features = np.asarray(
            [[float(self.graph.nodes[n].get("type") == "host"),
              self.graph.degree(n) / max(1, max(dict(self.graph.degree()).values(), default=0))]
             for n in self.nodes], dtype=np.float32
        ).reshape(len(self.nodes), 2)
        self.history = HistoryBuffer(self.config.history_length,
                                     (len(self.nodes), 6), (len(self.monitor.edges), 5))
        self.action_space = spaces.Discrete(self.config.k_paths + 1)
        n, e, k, t = len(self.nodes), len(self.monitor.edges), self.config.k_paths, self.config.history_length
        self.observation_space = spaces.Dict({
            "node_features": spaces.Box(0.0, np.finfo(np.float32).max, (n, 6), np.float32),
            "edge_features": spaces.Box(0.0, np.finfo(np.float32).max, (e, 5), np.float32),
            "flow_features": spaces.Box(0.0, np.finfo(np.float32).max, (7,), np.float32),
            "edge_index": spaces.Box(0, max(0, n - 1), (2, e), np.int32),
            "candidate_paths": spaces.Box(-1, n - 1, (k, n), np.int32),
            "action_mask": spaces.MultiBinary(k + 1),
            "history_nodes": spaces.Box(0.0, np.finfo(np.float32).max, (t, n, 6), np.float32),
            "history_edges": spaces.Box(0.0, np.finfo(np.float32).max, (t, e, 5), np.float32),
        })
        self.loads: dict[tuple[str, str], float] = {}; self.latencies: dict[tuple[str, str], float] = {}
        self.losses: dict[tuple[str, str], float] = {}; self._paths: PathResult = PathResult((), True)
        self.flow: Flow | None = None; self.time = 0; self._steps = 0
        self.active_flows: list[ActiveFlow] = []
        self._last_path: tuple[str, ...] | None = None; self._last_quality: float | None = None
        self._last_flow_id: str | None = None
        self._np_random = np.random.default_rng()

    def _ensure_host_count(self) -> None:
        fraction = self.config.hosts_per_router_fraction
        proportional = math.ceil(len(self.router_nodes) * fraction) if fraction is not None else 0
        desired = max(self.config.minimum_hosts, proportional)
        existing = [n for n, attrs in self.graph.nodes(data=True) if attrs.get("type") == "host"]
        routers = sorted(self.router_nodes, key=str)
        rng = np.random.default_rng(0)
        next_id = 0
        while len(existing) < desired:
            host = f"H{next_id}"
            next_id += 1
            if host in self.graph:
                continue
            router = routers[int(rng.integers(len(routers)))]
            self.graph.add_node(host, type="host", label=host, up=True)
            self.graph.add_edge(host, router, bandwidth=1000.0, latency=0.5,
                                loss=0.0, base_capacity=1000.0, capacity=1000.0,
                                up=True)
            existing.append(host)

    @staticmethod
    def _key(u: str, v: str) -> tuple[str, str]:
        return tuple(sorted((u, v), key=str))

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
        super().reset(seed=seed)
        self._np_random = np.random.default_rng(seed)
        for n, attrs in self.base_nodes.items(): self.graph.nodes[n].clear(); self.graph.nodes[n].update(attrs)
        for (u, v), attrs in self.base_edges.items(): self.graph[u][v].clear(); self.graph[u][v].update(attrs)
        self.events.reset(); self.traffic.reset(int(self._np_random.integers(0, 2**32 - 1)))
        self.time = 0; self._steps = 0; self._last_path = None; self._last_quality = None; self._last_flow_id = None
        self.active_flows.clear()
        self._rebuild_loads()
        self._refresh_link_metrics()
        self.flow = self._scheduled_flow(self.traffic.sample_flow(), 0.0)
        self._refresh_paths()
        snapshot = self.monitor.snapshot(self.graph, self.loads, self.latencies, self.losses)
        self.history.reset(self._history_snapshot(snapshot))
        return self._observation(snapshot), {"time": self.time, "flow_id": self.flow.flow_id,
                                            "edge_index": self.edge_index.copy()}

    def _rebuild_loads(self) -> None:
        """Rebuild aggregate offered load from currently active routed flows."""
        self.loads = {self._key(u, v): 0.0 for u, v in self.graph.edges}
        for active in self.active_flows:
            for u, v in zip(active.path, active.path[1:]):
                key = self._key(u, v)
                if key in self.loads:
                    self.loads[key] += active.flow.demand_mbps

    def _refresh_link_metrics(self) -> None:
        self.latencies = {}
        self.losses = {}
        for u, v, attrs in self.graph.edges(data=True):
            key = self._key(u, v)
            capacity = float(attrs.get("capacity", 0.0))
            if capacity > 0 and attrs.get("up", True):
                _, latency, loss = self._link_metrics(key, self.loads.get(key, 0.0))
            else:
                latency = float(attrs.get("latency", 0.0))
                loss = 0.0
                self.loads[key] = 0.0
            self.latencies[key] = latency
            self.losses[key] = loss

    def _expire_active_flows(self) -> list[str]:
        expired = []
        retained = []
        for active in self.active_flows:
            active.remaining_steps -= 1
            if active.remaining_steps <= 0:
                expired.append(active.flow.flow_id)
            else:
                retained.append(active)
        self.active_flows = retained
        self._rebuild_loads()
        return expired

    def _invalidate_broken_active_flows(self) -> list[str]:
        """Drop complete active flows whose installed path is no longer up."""
        invalidated = [active.flow.flow_id for active in self.active_flows
                       if not path_is_available(self.graph, active.path,
                                                active.flow.source,
                                                active.flow.destination)]
        if invalidated:
            invalidated_set = set(invalidated)
            self.active_flows = [active for active in self.active_flows
                                 if active.flow.flow_id not in invalidated_set]
            self._rebuild_loads()
        return invalidated

    def _refresh_paths(self) -> None:
        if self.flow is None:
            self._paths = PathResult((), True); return
        result = candidate_paths(self.graph, self.flow.source, self.flow.destination,
                                 self.config.k_paths, self.loads)
        if len(result.paths) > 1:
            order = self._np_random.permutation(len(result.paths))
            result = PathResult(tuple(result.paths[int(i)] for i in order), result.no_route)
        self._paths = result

    def _scheduled_flow(self, flow: Flow, time: float) -> Flow:
        multiplier = self.diurnal_pattern.multiplier(time) if self.diurnal_pattern else 1.0
        for spike in self.traffic_spikes:
            if spike.applies(time, flow): multiplier *= spike.multiplier
        return replace(flow, demand_mbps=flow.demand_mbps * multiplier)

    def _observation(self, snapshot=None) -> dict[str, np.ndarray]:
        if snapshot is None: snapshot = self.monitor.snapshot(self.graph, self.loads, self.latencies, self.losses)
        nodes = np.zeros(self.observation_space["flow_features"].shape, dtype=np.float32)
        if self.flow is not None:
            qos_order = list(QoSClass)
            nodes[0] = self.flow.demand_mbps
            nodes[1 + qos_order.index(self.flow.qos_class)] = 1.0
            nodes[5] = self.flow.priority; nodes[6] = self.flow.duration_steps
        node_features = self._node_features(snapshot)
        path_array = np.full((self.config.k_paths, len(self.nodes)), -1, dtype=np.int32)
        for i, path in enumerate(self._paths.paths):
            path_array[i, :len(path)] = [self.node_index[n] for n in path]
        mask = self._action_mask()
        hist_nodes, hist_edges = self.history.arrays()
        result = {"node_features": node_features, "edge_features": snapshot.edge_features.copy(),
                  "flow_features": nodes, "candidate_paths": path_array, "action_mask": mask,
                  "edge_index": self.edge_index.copy(),
                  "history_nodes": hist_nodes.astype(np.float32, copy=False),
                  "history_edges": hist_edges.astype(np.float32, copy=False)}
        if not self.observation_space.contains(result): raise ValueError("internal observation violates observation_space")
        return result

    def _node_features(self, snapshot: NetworkSnapshot) -> np.ndarray:
        features = np.column_stack((snapshot.node_features,
                                    self._node_static_features[:, 0],
                                    np.zeros(len(self.nodes), dtype=np.float32),
                                    np.zeros(len(self.nodes), dtype=np.float32),
                                    self._node_static_features[:, 1])).astype(np.float32)
        if self.flow is not None:
            features[self.node_index[self.flow.source], 3] = 1.0
            features[self.node_index[self.flow.destination], 4] = 1.0
        return features

    def _history_snapshot(self, snapshot: NetworkSnapshot) -> NetworkSnapshot:
        return NetworkSnapshot(self._node_features(snapshot), snapshot.edge_features.copy())

    def _action_mask(self) -> np.ndarray:
        mask = np.zeros(self.config.k_paths + 1, dtype=np.int8)
        mask[:len(self._paths.paths)] = 1
        mask[-1] = int(self.flow is None or not self._paths.paths)
        return mask

    def _link_metrics(self, key: tuple[str, str], load: float) -> tuple[float, float, float]:
        u, v = key; attrs = self.graph[u][v]
        cap = float(attrs["capacity"]); rho = utilization(load, cap)
        latency = link_latency_ms(float(attrs["latency"]), load, cap, self.latency_config)
        loss = congestion_loss(rho, self.config.congestion_loss_slope, self.config.max_loss,
                               self.config.loss_epsilon)
        return rho, latency, loss

    def _utilization_summary(self) -> dict[str, float]:
        backbone = []
        backbone_load = 0.0
        backbone_capacity = 0.0
        access = []
        all_links = []
        routers = set(self.router_nodes)
        for u, v, attrs in self.graph.edges(data=True):
            capacity = float(attrs.get("capacity", 0.0))
            if capacity <= 0 or not attrs.get("up", True):
                continue
            rho = self.loads.get(self._key(u, v), 0.0) / capacity
            all_links.append(rho)
            if u in routers and v in routers:
                backbone.append(rho)
                backbone_load += self.loads.get(self._key(u, v), 0.0)
                backbone_capacity += capacity
            else:
                access.append(rho)
        return {
            "max_backbone": max(backbone, default=0.0),
            "mean_backbone": (backbone_load / backbone_capacity
                              if backbone_capacity > 0 else 0.0),
            "max_access": max(access, default=0.0),
            "max_all": max(all_links, default=0.0),
        }

    def set_link_load(self, edge: tuple[str, str], load_mbps: float) -> tuple[float, float, float]:
        """Set a diagnostic load and return (utilization, total latency ms, loss)."""
        key = self._key(*edge)
        if key not in self.loads: raise KeyError(f"unknown link {edge}")
        if not math.isfinite(load_mbps) or load_mbps < 0: raise ValueError("load must be finite and nonnegative")
        rho, latency, loss = self._link_metrics(key, load_mbps)
        self.loads[key] = load_mbps; self.latencies[key] = latency; self.losses[key] = loss
        return rho, latency, loss

    def fail_link(self, edge: tuple[str, str]) -> None:
        u, v = edge
        if not self.graph.has_edge(u, v): raise KeyError(f"unknown link {edge}")
        self.graph[u][v]["up"] = False; self.graph[u][v]["capacity"] = 0.0
        self._invalidate_broken_active_flows()
        self._refresh_link_metrics(); self._refresh_paths()

    def fail_router(self, router: str) -> None:
        if router not in self.graph: raise KeyError(f"unknown router {router}")
        self.graph.nodes[router]["up"] = False
        for _, v in self.graph.edges(router):
            self.graph[router][v]["up"] = False; self.graph[router][v]["capacity"] = 0.0
        self._invalidate_broken_active_flows()
        self._refresh_link_metrics(); self._refresh_paths()

    def step(self, action: int):
        if not self.action_space.contains(action):
            raise ValueError(f"action must be an integer in [0,{self.config.k_paths}]")
        action_mask = self._action_mask()
        valid = bool(action_mask[action])
        chosen = self._paths.paths[action] if valid and action < len(self._paths.paths) else None
        candidate_count = len(self._paths.paths)
        reward = 0.0
        info: dict[str, Any] = {
            "time": self.time,
            "no_route": bool(self.flow is not None and self._paths.no_route),
            "invalid_action": not valid,
            "selected_path": chosen,
        }
        if self.flow is None and not valid:
            reward = -self.reward_config.failure_penalty

        routed_flow_id = self.flow.flow_id if self.flow is not None else None
        if self.flow is not None:
            if chosen is None or not path_is_available(
                    self.graph, chosen, self.flow.source, self.flow.destination):
                info["selected_path"] = None
                if chosen is None:
                    info["no_route"] = not bool(self._paths.paths)
                else:
                    info["no_route"] = not path_is_available(
                        self.graph, chosen, self.flow.source, self.flow.destination)
                if action == self.config.k_paths and candidate_count:
                    info["failure_cause"] = "idle_action"
                elif not valid:
                    info["failure_cause"] = "masked_or_invalid_action"
                else:
                    info["failure_cause"] = "no_route_due_to_failures"
                reward, parts = route_reward(
                    self.flow.qos_class, 0.0, 0.0, 0.0, self.flow.demand_mbps,
                    self.profiles[self.flow.qos_class], self.reward_config, failed=True)
                info["reward_components"] = parts
                info["no_route"] = True
            else:
                preexisting_loads = dict(self.loads)
                self.active_flows.append(ActiveFlow(
                    self.flow, chosen, self.flow.duration_steps))
                self._rebuild_loads()
                previous_path = (self._last_path if self._last_flow_id == self.flow.flow_id
                                 and self._last_path is not None
                                 and path_is_available(self.graph, self._last_path,
                                                       self.flow.source, self.flow.destination)
                                 else None)
                path_latency = 0.0
                path_survival = 1.0
                delivered = self.flow.demand_mbps
                maximum_utilization = 0.0
                maximum_backbone_utilization = 0.0
                routers = set(self.router_nodes)
                for u, v in zip(chosen, chosen[1:]):
                    key = self._key(u, v)
                    capacity = float(self.graph[u][v]["capacity"])
                    rho, latency, loss = self._link_metrics(key, self.loads[key])
                    maximum_utilization = max(maximum_utilization, rho)
                    if u in routers and v in routers:
                        maximum_backbone_utilization = max(maximum_backbone_utilization, rho)
                    path_latency += latency
                    path_survival *= 1.0 - loss
                    delivered = min(delivered,
                                    max(0.0, capacity - preexisting_loads.get(key, 0.0)))
                path_loss = 1.0 - path_survival
                reward, parts = route_reward(
                    self.flow.qos_class, path_latency, path_loss, delivered,
                    self.flow.demand_mbps, self.profiles[self.flow.qos_class],
                    self.reward_config, previous_path=previous_path,
                    current_path=chosen, previous_quality=self._last_quality,
                    priority=self.flow.priority,
                    max_utilization=maximum_backbone_utilization)
                self._last_path = chosen
                self._last_flow_id = self.flow.flow_id
                self._last_quality = parts["quality_cost"]
                info.update(path_latency_ms=path_latency, path_loss=path_loss,
                            delivered_mbps=delivered,
                            path_max_utilization=maximum_utilization,
                            path_max_backbone_utilization=maximum_backbone_utilization,
                            reward_components=parts)

        utilization_summary = self._utilization_summary()
        expired_flows = self._expire_active_flows()
        self.time += 1
        self._steps += 1
        self.events.apply_due(self.graph, int(self.time))
        if self.config.event_probability and self._np_random.random() < self.config.event_probability:
            up_edges = [(u, v) for u, v, attrs in self.graph.edges(data=True)
                        if attrs.get("up", True)]
            if up_edges:
                u, v = up_edges[int(self._np_random.integers(len(up_edges)))]
                if self._np_random.random() < 0.5:
                    self.graph[u][v]["up"] = False
                    self.graph[u][v]["capacity"] = 0.0
                else:
                    self.graph[u][v]["capacity"] = (
                        float(self.graph[u][v]["base_capacity"])
                        * self.config.bandwidth_drop_factor)

        invalidated_flows = self._invalidate_broken_active_flows()
        self._rebuild_loads()
        self._refresh_link_metrics()
        if self._steps < self.config.max_steps:
            next_flow = self.traffic.step()[0]
            if (next_flow.source not in self.traffic_nodes
                    or next_flow.destination not in self.traffic_nodes):
                raise ValueError("traffic generator produced endpoints outside its configured endpoint set")
            self.flow = self._scheduled_flow(next_flow, self.time)
        else:
            self.flow = None
        self._refresh_paths()
        snapshot = self.monitor.snapshot(self.graph, self.loads, self.latencies, self.losses)
        self.history.append(self._history_snapshot(snapshot))
        observation = self._observation(snapshot)
        terminated = False
        truncated = self._steps >= self.config.max_steps
        info.update(time=self.time, flow_id=self.flow.flow_id if self.flow else None,
                    available_paths=len(self._paths.paths),
                    step_max_utilization=utilization_summary["max_all"],
                    step_max_access_utilization=utilization_summary["max_access"],
                    step_max_backbone_utilization=utilization_summary["max_backbone"],
                    step_mean_backbone_utilization=utilization_summary["mean_backbone"],
                    active_flow_count=len(self.active_flows),
                    expired_flows=expired_flows,
                    invalidated_flows=invalidated_flows,
                    routed_flow_id=routed_flow_id)
        return observation, float(reward), terminated, truncated, info

    def render(self):
        line = f"t={self.time:g} nodes_up={sum(bool(a.get('up', True)) for _, a in self.graph.nodes(data=True))}/{len(self.nodes)} flow={self.flow} paths={len(self._paths.paths)}"
        if self.render_mode == "human": print(line); return None
        return line

    def close(self) -> None:
        return None
