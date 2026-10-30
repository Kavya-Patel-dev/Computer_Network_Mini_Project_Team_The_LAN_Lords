"""Supported inference and lightweight simulation API for the frozen Day 5 model."""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path
import time
from typing import Any, Mapping, Sequence

import networkx as nx
import numpy as np
import torch

from baselines.evaluation import graph_failure_plan, _apply_scenario_change
from baselines.explicit_path import step_explicit_path
from baselines.policies import choose_decision
from baselines.policies import Decision
from baselines.evaluation import (canonical_flow, observe_od_route_change,
                                  rolling_recovery)
from env.events import BandwidthDrop
from env.network_env import NetworkEnvConfig, NetworkRoutingEnv
from env.qos import QoSClass
from env.traffic import Flow, PoissonTrafficGenerator, TrafficGenerator, TrafficSpike
from models.day5_variants import VariantDQNAgent
from models.obs import ObservationWrapper
from models.safety_fallback import choose_with_fallback

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "runs" / "day5" / "final_routing_model.pt"
MODEL_SHA256 = "45957597F56CF163C5AE5D69F6FE6959DDB638601C7ADE97B865A848151FFF28"
_AGENT: VariantDQNAgent | None = None
PRESET_INTENSITY = {
    "latency_focused": 0.025,
    "light": 0.05,
    "medium": 0.10,
    "heavy": 0.20,
}


def _read_json(value: str | Path | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return json.loads(Path(value).read_text(encoding="utf-8"))


def topology_graph(topology_json: str | Path | Mapping[str, Any]) -> nx.Graph:
    """Validate Day 1 JSON and create an undirected graph in Mbps/ms units."""
    data = _read_json(topology_json)
    if not isinstance(data.get("nodes"), list) or not isinstance(data.get("links"), list):
        raise ValueError("topology JSON must contain nodes[] and links[]")
    graph = nx.Graph(name=str(data.get("name", "user-topology")))
    seen: set[str] = set()
    for row in data["nodes"]:
        if not isinstance(row, dict) or not row.get("id"):
            raise ValueError("each node needs a non-empty id and type")
        node_id, node_type = str(row["id"]), row.get("type")
        if node_id in seen:
            raise ValueError(f"duplicate node id {node_id!r}")
        if node_type not in {"router", "host"}:
            raise ValueError(f"node {node_id!r} type must be 'router' or 'host'")
        seen.add(node_id)
        graph.add_node(node_id, type=node_type, label=str(row.get("label", node_id)), up=True)
    routers = [n for n, a in graph.nodes(data=True) if a["type"] == "router"]
    if not 5 <= len(routers) <= 50:
        raise ValueError(f"topology must contain 5-50 routers; got {len(routers)}")
    if not data["links"]:
        raise ValueError("topology must contain at least one link")
    for row in data["links"]:
        if not isinstance(row, dict):
            raise ValueError("each link must be a JSON object")
        u, v = str(row.get("src", "")), str(row.get("dst", ""))
        if not u or not v or u == v or u not in graph or v not in graph:
            raise ValueError(f"link endpoints must be distinct declared nodes: {u!r}-{v!r}")
        if graph.has_edge(u, v):
            raise ValueError(f"duplicate link {u!r}-{v!r}")
        try:
            capacity = float(row.get("bandwidth", row.get("capacity_mbps")))
            latency = float(row.get("latency", row.get("latency_ms")))
            loss_percent = float(row.get("loss_percent", row.get("loss", 0.0)))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"link {u!r}-{v!r} needs numeric bandwidth, latency, and loss") from exc
        if not math.isfinite(capacity) or capacity <= 0:
            raise ValueError(f"link {u!r}-{v!r} bandwidth must be positive Mbps")
        if not math.isfinite(latency) or latency <= 0:
            raise ValueError(f"link {u!r}-{v!r} latency must be positive milliseconds")
        if not math.isfinite(loss_percent) or not 0 <= loss_percent <= 100:
            raise ValueError(f"link {u!r}-{v!r} loss must be a percentage in [0, 100]")
        graph.add_edge(u, v, bandwidth=capacity, base_capacity=capacity,
                       capacity=capacity, latency=latency,
                       loss=loss_percent / 100.0, up=True)
    if not nx.is_connected(graph):
        raise ValueError("topology must be connected")
    for node, attrs in graph.nodes(data=True):
        if attrs["type"] == "host" and graph.degree(node) != 1:
            raise ValueError(f"host {node!r} must be a leaf with exactly one link")
    return graph


def _load_agent() -> VariantDQNAgent:
    global _AGENT
    if _AGENT is not None:
        return _AGENT
    digest = hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest().upper()
    if digest != MODEL_SHA256:
        raise RuntimeError(f"frozen model SHA-256 mismatch: got {digest}")
    payload = torch.load(MODEL_PATH, map_location="cpu", weights_only=False)
    torch.set_num_threads(1)
    agent = VariantDQNAgent(flags=payload["flags"], actions=4, seed=0)
    agent.load(str(MODEL_PATH))
    agent.online.eval()
    _AGENT = agent
    return agent


def _apply_link_state(graph: nx.Graph, link_state: Any) -> None:
    if link_state is None:
        return
    if isinstance(link_state, Mapping):
        items = []
        for key, value in link_state.items():
            if not isinstance(value, Mapping):
                raise ValueError("link_state values must be JSON objects")
            if isinstance(key, str) and ("|" in key or "," in key):
                delimiter = "|" if "|" in key else ","
                u, v = key.split(delimiter, 1)
                items.append({**value, "src": u, "dst": v})
            else:
                items.append(dict(value))
    elif isinstance(link_state, list):
        items = link_state
    else:
        raise ValueError("link_state must be an edge-keyed object or a list")
    for row in items:
        if not isinstance(row, Mapping):
            raise ValueError("each link_state entry must be an object")
        u, v = str(row.get("src", row.get("u", ""))), str(row.get("dst", row.get("v", "")))
        if not graph.has_edge(u, v):
            raise ValueError(f"link_state references unknown link {u!r}-{v!r}")
        attrs = graph[u][v]
        if "capacity_mbps" in row or "bandwidth" in row:
            capacity = float(row.get("capacity_mbps", row.get("bandwidth")))
            if not math.isfinite(capacity) or capacity < 0:
                raise ValueError(f"link_state capacity for {u}-{v} must be finite and nonnegative")
            attrs["capacity"] = capacity
        if "load_mbps" in row:
            load = float(row["load_mbps"])
            if not math.isfinite(load) or load < 0:
                raise ValueError(f"link_state load for {u}-{v} must be finite and nonnegative")
            attrs["_initial_load_mbps"] = load
        if "utilization" in row:
            utilization = float(row["utilization"])
            if not math.isfinite(utilization) or utilization < 0:
                raise ValueError(f"link_state utilization for {u}-{v} must be finite and nonnegative")
            attrs["_initial_load_mbps"] = utilization * float(attrs["capacity"])
        if "latency_ms" in row:
            latency = float(row["latency_ms"])
            if not math.isfinite(latency) or latency <= 0:
                raise ValueError(f"link_state latency for {u}-{v} must be positive ms")
            attrs["latency"] = latency
        if "loss_percent" in row:
            loss_percent = float(row["loss_percent"])
            if not math.isfinite(loss_percent) or not 0 <= loss_percent <= 100:
                raise ValueError(f"link_state loss for {u}-{v} must be in [0, 100] percent")
            attrs["loss"] = loss_percent / 100.0
        if "up" in row:
            attrs["up"] = bool(row["up"])
            if not attrs["up"]:
                attrs["capacity"] = 0.0


def _include_base_loss(env: NetworkRoutingEnv) -> None:
    """Apply the user JSON's independent per-link loss in this API instance."""
    original = env._link_metrics

    def metric(key: tuple[str, str], load: float):
        utilization, latency, congestion_loss = original(key, load)
        u, v = key
        base_loss = float(env.graph[u][v].get("loss", 0.0))
        combined = 1.0 - (1.0 - base_loss) * (1.0 - congestion_loss)
        return utilization, latency, combined

    env._link_metrics = metric


def _flow_from_json(value: Mapping[str, Any]) -> Flow:
    try:
        flow = Flow(
            source=str(value["source"]), destination=str(value["destination"]),
            demand_mbps=float(value.get("demand_mbps", value.get("demand", 1.0))),
            qos_class=QoSClass(value.get("qos_class", value.get("qos", "BULK"))),
            priority=int(value.get("priority", 2)),
            duration_steps=int(value.get("duration_steps", 20)),
            flow_id=str(value.get("flow_id", "api-flow")),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid manual flow: {exc}") from exc
    if flow.demand_mbps <= 0:
        raise ValueError("manual flow demand_mbps must be positive")
    return flow


def _make_route_env(graph: nx.Graph, flow: Mapping[str, Any], link_state: Any = None):
    if not isinstance(flow, Mapping):
        raise ValueError("flow must be an object")
    chosen_flow = _flow_from_json(flow)
    if chosen_flow.source not in graph or chosen_flow.destination not in graph:
        raise ValueError("flow source and destination must be declared nodes")
    if chosen_flow.source == chosen_flow.destination:
        raise ValueError("flow source and destination must differ")
    _apply_link_state(graph, link_state)
    generator = PoissonTrafficGenerator(sorted(graph.nodes), demand_mbps=1.0)
    config = NetworkEnvConfig(history_length=4, k_paths=4,
                              hosts_per_router_fraction=0.0, minimum_hosts=0)
    env = NetworkRoutingEnv(graph, config, traffic_generator=generator)
    _include_base_loss(env)
    observation, _ = env.reset(seed=0)
    env.flow = chosen_flow
    for u, v, attrs in env.graph.edges(data=True):
        load = float(attrs.pop("_initial_load_mbps", 0.0))
        if not attrs.get("up", True):
            attrs["capacity"] = 0.0
            load = 0.0
        env.loads[env._key(u, v)] = load
    env._refresh_link_metrics()
    env._refresh_paths()
    observation = env._observation()
    return env, observation


def route(topology_json: str | Path | Mapping[str, Any], link_state: Any,
          history: Any, flow: Mapping[str, Any]) -> dict[str, Any]:
    """Route one flow through the frozen checkpoint and safety wrapper."""
    graph = topology_graph(topology_json)
    env, observation = _make_route_env(graph, flow, link_state)
    try:
        wrapper = ObservationWrapper(env, graph.graph.get("name", "user-topology"))
        state = wrapper.process(observation)
        # The frozen checkpoint has no GRU. History is accepted for forward
        # compatibility; the current feed-forward model does not consume it.
        _ = history
        decision = choose_with_fallback(_load_agent(), env, state,
                                        np.random.default_rng(0), enabled=True)
        return {
            "candidate_paths": [list(path) for path in decision.candidate_paths],
            "q_values": [float(q) if math.isfinite(float(q)) else None
                         for q in decision.q_values],
            "chosen_index": decision.chosen_index,
            "chosen_path": list(decision.chosen_path) if decision.chosen_path else None,
            "fallback_used": decision.fallback_used,
            "reason": decision.reason,
            "attention_weights": (None if decision.attention_weights is None
                                  else decision.attention_weights.tolist()),
        }
    finally:
        env.close()


class _ManualTraffic(TrafficGenerator):
    def __init__(self, nodes: Sequence[str], flows: Sequence[Flow]):
        super().__init__(nodes, demand_mbps=1.0, intensity=0.05)
        self.flows = tuple(flows)
        self.index = 0

    def reset(self, seed: int | None = None) -> None:
        super().reset(seed)
        self.index = 0

    def sample_flow(self, **kwargs) -> Flow:
        flow = self.flows[self.index % len(self.flows)]
        self.index += 1
        return replace(flow, flow_id=f"manual-{self.index}")

    def od_pair_weights(self) -> list[tuple[str, str, float]]:
        return [(flow.source, flow.destination, 1.0) for flow in self.flows]


def _calibrate_user_traffic(env: NetworkRoutingEnv, intensity: float) -> dict[str, Any] | None:
    """Keep generated endpoint demands within access-link scale, preserving backbone load.

    The environment's general-purpose generator bases each flow on median
    router-router capacity. That is appropriate for backbone endpoints but can
    oversubscribe a much slower host access link before a routing decision can
    help. For API preset traffic, use the median router-host capacity for the
    per-flow demand range, then recompute lifetime with the same Little's-law
    backbone intensity target. Explicit manual flows remain untouched.
    """
    generator = env.traffic
    if not isinstance(generator, PoissonTrafficGenerator):
        return None

    backbone = generator.configure_for_network(
        env.graph, env.router_nodes, intensity,
        (env.config.demand_min_fraction, env.config.demand_max_fraction),
    )
    router_nodes = set(env.router_nodes)
    access_capacities = [
        float(attrs["capacity"])
        for u, v, attrs in env.graph.edges(data=True)
        if ((u in router_nodes and env.graph.nodes[v].get("type") == "host")
            or (v in router_nodes and env.graph.nodes[u].get("type") == "host"))
        and float(attrs.get("capacity", 0.0)) > 0
    ]
    if not access_capacities:
        return {"basis": "backbone_only", **backbone}

    median_access = float(np.median(access_capacities))
    low_fraction = env.config.demand_min_fraction
    high_fraction = env.config.demand_max_fraction
    demand_range = (low_fraction * median_access,
                    high_fraction * median_access)
    mean_demand = sum(demand_range) / 2.0
    mean_hops = float(backbone["mean_router_path_hops"])
    total_capacity = float(backbone["total_router_capacity_mbps"])
    requested_duration = intensity * total_capacity / (mean_demand * mean_hops)
    duration = float(np.clip(requested_duration, 3.0, 200.0))

    generator._set_demand_range(demand_range)
    generator.demand_mbps = mean_demand
    generator.duration_mean_steps = duration
    generator.intensity = float(intensity)
    generator.network_calibrated = True
    return {
        "basis": "median_router_host_access_capacity",
        "median_access_capacity_mbps": median_access,
        "demand_min_mbps": demand_range[0],
        "demand_max_mbps": demand_range[1],
        "mean_demand_mbps": mean_demand,
        "mean_duration_steps": duration,
        "requested_duration_steps": requested_duration,
        "duration_clamp": ("low" if requested_duration < 3.0 else
                            "high" if requested_duration > 200.0 else "none"),
        "mean_router_path_hops": mean_hops,
        "total_router_capacity_mbps": total_capacity,
        "target_backbone_intensity": float(intensity),
        "achievable_backbone_intensity": (
            duration * mean_demand * mean_hops / total_capacity
        ),
    }


def _run_sim_policy(graph: nx.Graph, flows: Sequence[Flow] | None,
                    intensity: float, scenario: str, policy: str,
                    seed: int, max_steps: int) -> dict[str, Any]:
    entry = {"name": graph.graph.get("name", "user-topology"), "source": "user"}
    plan = graph_failure_plan(graph, entry)
    if scenario not in {"normal", "link_failures", "router_failure", "traffic_spike", "bandwidth_drop"}:
        raise ValueError(f"unsupported scenario {scenario!r}")
    warmup = min(100, max_steps // 5)
    if max_steps < 400:
        failure = max(warmup + 5, max_steps // 3)
        restore = min(max_steps - 1, failure + max(10, max_steps // 8))
        second_failure = min(restore - 1, failure + max(2, max_steps // 16))
        plan.update(failure_step=failure, restore_step=restore,
                    link_failure_times=[failure, second_failure],
                    link_restore_times=[restore, min(max_steps - 1, restore + max(2, max_steps // 16))],
                    bandwidth_restore_step=min(max_steps - 1, restore + 10),
                    spike_start_step=failure,
                    spike_duration_steps=max(1, restore - failure))
    spikes = ((TrafficSpike(plan["spike_start_step"], plan["spike_duration_steps"], 4.0),)
              if scenario == "traffic_spike" else ())
    events = (tuple(BandwidthDrop(plan["failure_step"], edge, 0.5, duration=100)
                    for edge in plan["bandwidth_drop"])
              if scenario == "bandwidth_drop" else ())
    if flows:
        generator: TrafficGenerator = _ManualTraffic(
            sorted({node for flow in flows for node in (flow.source, flow.destination)}), flows)
    else:
        stub_nodes = [n for n, attrs in graph.nodes(data=True) if attrs.get("type") == "host"]
        generator = PoissonTrafficGenerator(stub_nodes or list(graph.nodes), demand_mbps=1.0,
                                            intensity=intensity)
    config = NetworkEnvConfig(max_steps=max_steps, intensity=intensity,
                              history_length=4)
    env = NetworkRoutingEnv(graph, config, traffic_generator=generator,
                            events=events, traffic_spikes=spikes)
    traffic_calibration = _calibrate_user_traffic(env, intensity)
    _include_base_loss(env)
    observation, _ = env.reset(seed=seed)
    rng = np.random.default_rng(seed ^ (sum(map(ord, policy)) << 8))
    agent = _load_agent() if policy == "ai" else None
    obs_wrapper: ObservationWrapper | None = None
    loss_values: list[float] = []
    latencies: list[float] = []
    throughput: list[float] = []
    max_backbone: list[float] = []
    max_access: list[float] = []
    invalid = 0
    decision_ms: list[float] = []
    request_digest = hashlib.sha256()
    previous_paths: dict[tuple[str, str], tuple[str, ...]] = {}
    flap_count = flap_comparisons = 0
    post_failure_routed = 0
    full_path_not_in_k = measured_full_path_decisions = 0
    ecmp_ties = 0
    fallback_reason_counts: dict[str, int] = {}
    decision_trace: list[dict[str, Any]] = []
    failure_start = plan["failure_step"] if scenario != "normal" else None
    try:
        for step in range(max_steps):
            _apply_scenario_change(env, scenario, plan, step)
            flow = env.flow
            if flow is None:
                raise RuntimeError("environment produced no flow for an API simulation decision")
            request_digest.update(json.dumps(canonical_flow(flow), sort_keys=True,
                                             separators=(",", ":")).encode("utf-8"))
            start_ns = time.perf_counter_ns()
            checked = None
            if policy == "static":
                decision = choose_decision("dijkstra_static", env, rng)
            elif policy == "load_aware":
                decision = choose_decision("dijkstra_load_aware", env, rng, alpha=4.0)
            else:
                if obs_wrapper is None:
                    obs_wrapper = ObservationWrapper(env, entry["name"])
                state = obs_wrapper.process(env._observation())
                checked = choose_with_fallback(agent, env, state, rng, enabled=True)
                fallback_reason_counts[checked.reason] = (
                    fallback_reason_counts.get(checked.reason, 0) + 1)
                if checked.fallback_used and checked.chosen_path is not None:
                    decision = Decision(env.config.k_paths,
                                        explicit_path=checked.chosen_path)
                else:
                    decision = Decision(checked.chosen_index if checked.chosen_index is not None
                                        else env.config.k_paths)
            decision_ms.append((time.perf_counter_ns() - start_ns) / 1e6)
            if step >= warmup:
                full_path_not_in_k += int(bool(decision.full_path_not_in_k))
                if policy in {"static", "load_aware"}:
                    measured_full_path_decisions += 1
                ecmp_ties += int(bool(decision.ecmp_tie))
            if decision.explicit_path is not None:
                next_obs, _reward, terminated, truncated, info = step_explicit_path(env, decision.explicit_path)
            else:
                next_obs, _reward, terminated, truncated, info = env.step(decision.action)
            invalid += int(bool(info.get("invalid_action", False)))
            path = info.get("selected_path")
            loss_values.append(float(info.get("path_loss", 1.0)) if path else 1.0)
            if policy == "ai" and checked is not None:
                q_values = [
                    float(value) if math.isfinite(float(value)) else None
                    for value in checked.q_values
                ]
                path_latency = info.get("path_latency_ms") if path else None
                path_loss = info.get("path_loss") if path else None
                backbone_util = info.get("step_max_backbone_utilization")
                access_util = info.get("step_max_access_utilization")
                decision_trace.append({
                    "step": int(step),
                    "measured": bool(step >= warmup),
                    "flow_id": str(flow.flow_id),
                    "source": str(flow.source),
                    "destination": str(flow.destination),
                    "candidate_paths": [list(candidate) for candidate in checked.candidate_paths],
                    "q_values": q_values,
                    "chosen_candidate_index": checked.chosen_index,
                    "chosen_path": list(path) if path else None,
                    "fallback_used": bool(checked.fallback_used),
                    "fallback_reason": checked.reason,
                    "path_latency_ms": (
                        float(path_latency) if path_latency is not None
                        and math.isfinite(float(path_latency)) else None
                    ),
                    "path_loss": (
                        float(path_loss) if path_loss is not None
                        and math.isfinite(float(path_loss)) else None
                    ),
                    "step_max_backbone_utilization": (
                        float(backbone_util) if backbone_util is not None
                        and math.isfinite(float(backbone_util)) else None
                    ),
                    "step_max_access_utilization": (
                        float(access_util) if access_util is not None
                        and math.isfinite(float(access_util)) else None
                    ),
                })
            if path:
                if failure_start is not None and step >= failure_start:
                    post_failure_routed += 1
                changed = observe_od_route_change(previous_paths, flow.source,
                                                  flow.destination, tuple(path))
                if step >= warmup and changed is not None:
                    flap_comparisons += 1
                    flap_count += int(changed)
            if step >= warmup:
                if path:
                    latencies.append(float(info.get("path_latency_ms", 0.0)))
                    throughput.append(float(info.get("delivered_mbps", 0.0)))
                else:
                    latencies.append(0.0)
                    throughput.append(0.0)
                max_backbone.append(float(info.get("step_max_backbone_utilization", 0.0)))
                max_access.append(float(info.get("step_max_access_utilization", 0.0)))
            if terminated or truncated:
                break
    finally:
        env.close()
    measured_loss = loss_values[warmup:]
    recovery, censored = (rolling_recovery(loss_values, int(failure_start))
                          if failure_start is not None else (None, None))
    return {
        "split": "user", "graph": entry["name"], "source": "user",
        "generator": "manual" if flows else "poisson",
        "intensity": float(intensity), "scenario": scenario, "policy": policy,
        "seed": int(seed), "request_sequence_sha256": request_digest.hexdigest(),
        "request_sequence_length": len(loss_values),
        "mean_packet_loss": float(np.mean(measured_loss)) if measured_loss else 0.0,
        "mean_path_latency_ms": float(np.mean(latencies)) if latencies else 0.0,
        "p95_path_latency_ms": float(np.percentile(latencies, 95)) if latencies else 0.0,
        "delivered_throughput_mbps": float(np.mean(throughput)) if throughput else 0.0,
        "mean_max_backbone_utilization": float(np.mean(max_backbone)) if max_backbone else 0.0,
        "p95_max_backbone_utilization": float(np.percentile(max_backbone, 95)) if max_backbone else 0.0,
        "fraction_steps_over_0_9": float(np.mean(np.asarray(max_backbone) > 0.9)) if max_backbone else 0.0,
        "mean_max_access_utilization": float(np.mean(max_access)) if max_access else 0.0,
        "fraction_steps_access_over_0_9": float(np.mean(np.asarray(max_access) > 0.9)) if max_access else 0.0,
        "flapping_rate": float(flap_count / max(1, flap_comparisons)),
        "flapping_comparisons": flap_comparisons,
        "mean_decision_time_ms": float(np.mean(decision_ms)) if decision_ms else 0.0,
        "recovery_time_steps": recovery, "recovery_censored": censored,
        "invalid_actions_accepted": invalid,
        "fallback_reason_counts": fallback_reason_counts,
        "fallback_rate_by_reason": {
            reason: count / max(1, len(loss_values))
            for reason, count in fallback_reason_counts.items()
        },
        # Persist the actual inference-time decisions so a saved run can show
        # which route was executed and whether the safety wrapper replaced it.
        "decision_trace": decision_trace if policy == "ai" else [],
        "post_failure_routed_flows": post_failure_routed,
        "full_path_not_in_k_fraction": full_path_not_in_k / max(1, measured_full_path_decisions),
        "ecmp_tie_fraction": ecmp_ties / max(1, len(loss_values) - warmup) if policy == "ecmp" else 0.0,
        "measured_steps": len(measured_loss),
        "event_schedule_json": json.dumps(plan, sort_keys=True, separators=(",", ":")),
        "traffic_calibration": traffic_calibration,
    }


def simulate(topology_json: str | Path | Mapping[str, Any],
             flows_or_preset: Sequence[Mapping[str, Any]] | str,
             scenario: str = "normal", *, seed: int = 1000,
             max_steps: int = 500) -> dict[str, Any]:
    """Compare static, load-aware, and fallback-wrapped AI routing."""
    graph = topology_graph(topology_json)
    if isinstance(flows_or_preset, str):
        try:
            intensity = PRESET_INTENSITY[flows_or_preset.lower()]
        except KeyError as exc:
            raise ValueError(
                "traffic preset must be latency_focused, light, medium, or heavy"
            ) from exc
        manual_flows = None
        preset = flows_or_preset.lower()
    elif isinstance(flows_or_preset, Sequence):
        manual_flows = [_flow_from_json(row) for row in flows_or_preset]
        if not manual_flows:
            raise ValueError("manual flow list cannot be empty")
        if any(flow.source not in graph or flow.destination not in graph
               for flow in manual_flows):
            raise ValueError("manual flow endpoints must be declared nodes")
        intensity, preset = 0.10, "manual"
    else:
        raise ValueError("flows_or_preset must be a preset name or a list of flows")
    if max_steps <= 0:
        raise ValueError("max_steps must be positive")
    metrics = {}
    for policy in ("static", "load_aware", "ai"):
        metrics[policy] = _run_sim_policy(graph.copy(), manual_flows, intensity,
                                          scenario, policy, seed, max_steps)
    traffic_calibration = metrics["static"].pop("traffic_calibration")
    for policy in ("load_aware", "ai"):
        metrics[policy].pop("traffic_calibration")
    static_loss = metrics["static"]["mean_packet_loss"]
    ai_loss = metrics["ai"]["mean_packet_loss"]
    la_loss = metrics["load_aware"]["mean_packet_loss"]
    delta_static, delta_load = static_loss - ai_loss, la_loss - ai_loss
    if abs(delta_static) <= 1e-6 and abs(delta_load) <= 1e-6:
        verdict = "AI made little difference in mean loss versus either baseline."
    else:
        def comparison(delta: float) -> str:
            direction = "reduced" if delta > 0 else "increased"
            return f"{direction} mean loss by {abs(delta):.4f}"
        verdict = (f"AI {comparison(delta_static)} versus static Dijkstra and "
                   f"{comparison(delta_load)} versus load-aware Dijkstra.")
    return {"topology": graph.graph.get("name", "user-topology"),
            "traffic_preset": preset, "intensity": intensity,
            "scenario": scenario, "seed": seed, "metrics": metrics,
            "traffic_calibration": (traffic_calibration or {
                "basis": "explicit_manual_flow_demands",
                "note": "Manual flow demands are used as supplied.",
            }),
            "verdict": verdict}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sim = sub.add_parser("simulate", help="compare baseline and AI routing")
    sim.add_argument("topology", type=Path)
    sim.add_argument("--traffic", default="medium",
                     choices=(*PRESET_INTENSITY.keys(), "flows"))
    sim.add_argument("--scenario", default="normal",
                     choices=("normal", "link_failures", "router_failure", "traffic_spike", "bandwidth_drop"))
    sim.add_argument("--flows", type=Path)
    sim.add_argument("--seed", type=int, default=1000)
    sim.add_argument("--steps", type=int, default=500)
    args = parser.parse_args()
    if args.command == "simulate":
        traffic: Any = (json.loads(args.flows.read_text(encoding="utf-8"))
                        if args.traffic == "flows" and args.flows else args.traffic)
        if args.traffic == "flows" and not args.flows:
            parser.error("--traffic flows requires --flows FILE")
        print(json.dumps(simulate(args.topology, traffic, args.scenario,
                                  seed=args.seed, max_steps=args.steps), indent=2))


if __name__ == "__main__":
    main()
