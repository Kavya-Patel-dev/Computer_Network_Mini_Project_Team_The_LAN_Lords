"""Diagnose uncongested candidate scoring for a saved Day 4 checkpoint."""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from baselines import evaluation as day3
from baselines.evaluation import load_graph
from baselines.policies import Decision
from env.reward import route_reward
from models.data_guard import guard_graph_request, read_partitions
from models.dqn import DoubleDQNAgent
from models.harness import capture_flow_latencies
from models.obs import ObservationWrapper

DATA = ROOT / "data"
OUT = ROOT / "outputs" / "day4"
CONTROL_GRAPHS = ("Arpanet19728", "Compuserve", "EliBackbone")
SEEDS = tuple(range(1000, 1005))
COMPONENTS = ("latency", "loss", "bandwidth", "minimum_bandwidth",
              "utilization", "flap", "quality_cost")


def expected_components(env, path: tuple[str, ...]) -> dict[str, float]:
    flow = env.flow
    demand = float(flow.demand_mbps)
    survival = 1.0
    latency_sum = 0.0
    delivered = demand
    max_backbone_util = 0.0
    routers = set(env.router_nodes)
    for u, v in zip(path, path[1:]):
        key = env._key(u, v)
        existing = float(env.loads.get(key, 0.0))
        capacity = float(env.graph[u][v]["capacity"])
        rho, latency, loss = env._link_metrics(key, existing + demand)
        latency_sum += latency
        survival *= 1.0 - loss
        delivered = min(delivered, max(0.0, capacity - existing))
        if u in routers and v in routers:
            max_backbone_util = max(max_backbone_util, rho)
    path_loss = 1.0 - survival
    previous_path = (env._last_path if env._last_flow_id == flow.flow_id
                     and env._last_path is not None else None)
    _reward, parts = route_reward(
        flow.qos_class, latency_sum, path_loss, delivered, demand,
        env.profiles[flow.qos_class], env.reward_config,
        previous_path=previous_path, current_path=path,
        previous_quality=env._last_quality,
        priority=flow.priority, max_utilization=max_backbone_util)
    return {key: float(parts.get(key, 0.0)) for key in COMPONENTS}


def run_episode(entry: dict, graph, agent: DoubleDQNAgent, seed: int,
                epsilon: float) -> tuple[dict, dict]:
    state = {"env": None, "wrapper": None, "chosen": [], "lowest": [],
             "q_gaps": [], "lowest_action": [], "chosen_action": []}
    original = day3.choose_decision

    def chooser(policy, env, rng, alpha=1.0, rf_model=None,
                time_since_last_failure=10_000):
        if policy != "agent_ddqn":
            return original(policy, env, rng, alpha=alpha, rf_model=rf_model,
                            time_since_last_failure=time_since_last_failure)
        if state["env"] is not env:
            state["env"] = env
            state["wrapper"] = ObservationWrapper(env, entry["name"])
        model_state = state["wrapper"].process(env._observation())
        valid = np.flatnonzero(model_state.action_mask)
        if len(valid) == 0:
            return Decision(env.config.k_paths)
        q_values = agent.q_values(model_state)
        greedy_action = int(valid[np.argmax(q_values[valid])])
        if epsilon > 0 and rng.random() < epsilon:
            action = int(rng.choice(valid))
        else:
            action = greedy_action
        path_costs = [sum(float(env.latencies.get(
            env._key(u, v), env.graph[u][v].get("latency", 0.0)))
                           for u, v in zip(env._paths.paths[i], env._paths.paths[i][1:]))
                      for i in valid]
        lowest_action = int(valid[int(np.argmin(path_costs))])
        if env._steps >= 100:
            chosen_path = tuple(env._paths.paths[action])
            lowest_path = tuple(env._paths.paths[lowest_action])
            chosen_parts = expected_components(env, chosen_path)
            lowest_parts = expected_components(env, lowest_path)
            state["chosen"].append(chosen_parts)
            state["lowest"].append(lowest_parts)
            state["q_gaps"].append(float(q_values[lowest_action] - q_values[action]))
            state["lowest_action"].append(lowest_action)
            state["chosen_action"].append(action)
        return Decision(action)

    day3.choose_decision = chooser
    try:
        with capture_flow_latencies(warmup=100) as capture:
            result = day3.run_episode(
                entry, graph, "poisson", 0.025, "agent_ddqn", seed,
                "normal", 4.0, rf_model=None, max_steps=500,
                warmup=100, data_root=DATA)
        aggregate = {
            "mean_loss": float(result["mean_packet_loss"]),
            "median_latency_ms": capture.median_latency_ms,
            "p95_latency_ms": float(result["p95_path_latency_ms"]),
            "fraction_cap": capture.fraction_capped,
        }
        diagnostics = {"state": state, "capture": capture}
        return aggregate, diagnostics
    finally:
        day3.choose_decision = original


def mean_component(rows: list[dict[str, float]], key: str) -> float:
    values = [row[key] for row in rows]
    return float(statistics.mean(values)) if values else 0.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path,
                        default=ROOT / "runs" / "day4" / "stage_b_best.pt")
    args = parser.parse_args()
    if not args.checkpoint.exists():
        parser.error(f"checkpoint not found: {args.checkpoint}")
    torch.set_num_threads(1)
    partitions = read_partitions(DATA / "splits.json")
    val_entries = {row["name"]: dict(row, split="val")
                   for row in partitions["val"]}
    agent = DoubleDQNAgent(actions=4, seed=0)
    metadata = agent.load(str(args.checkpoint))
    agent.online.eval()
    episode_rows = []
    candidate_rows = []

    for graph_no, name in enumerate(CONTROL_GRAPHS, 1):
        entry = val_entries[name]
        guard_graph_request(entry, "val", partitions)
        graph = load_graph(entry, DATA)
        for epsilon in (0.0, 0.05):
            group = []
            chosen_components = []
            lowest_components = []
            gaps = []
            non_lowest = 0
            decisions = 0
            for seed in SEEDS:
                metrics, diagnostic = run_episode(entry, graph, agent, seed, epsilon)
                group.append(metrics)
                state = diagnostic["state"]
                chosen_components.extend(state["chosen"])
                lowest_components.extend(state["lowest"])
                gaps.extend(state["q_gaps"])
                non_lowest += sum(a != b for a, b in zip(
                    state["chosen_action"], state["lowest_action"]))
                decisions += len(state["chosen_action"])
                episode_rows.append({
                    "checkpoint": str(args.checkpoint),
                    "checkpoint_step": metadata.get("step", ""),
                    "graph": name, "seed": seed, "epsilon": epsilon, **metrics,
                })

            row = {
                "checkpoint": str(args.checkpoint),
                "checkpoint_step": metadata.get("step", ""),
                "graph": name, "epsilon": epsilon,
                "episodes": len(group),
                "mean_loss": statistics.mean(item["mean_loss"] for item in group),
                "mean_median_latency_ms": statistics.mean(
                    item["median_latency_ms"] for item in group),
                "mean_p95_latency_ms": statistics.mean(
                    item["p95_latency_ms"] for item in group),
                "mean_fraction_cap": statistics.mean(
                    item["fraction_cap"] for item in group),
                "decisions": decisions,
                "not_lowest_latency_fraction": non_lowest / max(1, decisions),
                "q_gap_lowest_minus_chosen_mean": statistics.mean(gaps) if gaps else 0.0,
                "q_gap_lowest_minus_chosen_p95": float(np.percentile(gaps, 95)) if gaps else 0.0,
            }
            candidate_row = {**row}
            for component in COMPONENTS:
                candidate_row[f"chosen_{component}_mean"] = mean_component(
                    chosen_components, component)
                candidate_row[f"lowest_latency_{component}_mean"] = mean_component(
                    lowest_components, component)
                candidate_row[f"lowest_minus_chosen_{component}_mean"] = (
                    candidate_row[f"lowest_latency_{component}_mean"]
                    - candidate_row[f"chosen_{component}_mean"])
            candidate_rows.append(candidate_row)
            print(f"control diagnosis: graph {graph_no}/3 | {name} | "
                  f"epsilon={epsilon:.2f} | loss={row['mean_loss']:.6f} | "
                  f"median={row['mean_median_latency_ms']:.3f} ms | "
                  f"not-lowest={row['not_lowest_latency_fraction']:.3f}",
                  flush=True)

    OUT.mkdir(parents=True, exist_ok=True)
    fields = list(episode_rows[0])
    with (OUT / "control_diagnosis_episodes.csv").open(
            "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(episode_rows)
    fields = list(candidate_rows[0])
    with (OUT / "control_diagnosis_summary.csv").open(
            "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(candidate_rows)
    print("Saved control diagnosis; this run uses the supplied saved checkpoint "
          "and does not tune or retrain it.", flush=True)


if __name__ == "__main__":
    main()
