"""Day 4 validation-only agent/baseline, K, and uncongested diagnostics."""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import joblib
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from baselines import evaluation as day3
from baselines.evaluation import load_graph, make_traffic
from baselines.explicit_path import step_explicit_path
from baselines.policies import POLICIES, choose_decision
from env.network_env import NetworkEnvConfig, NetworkRoutingEnv
from env.traffic import PoissonTrafficGenerator
from models.data_guard import guard_graph_request, read_partitions
from models.dqn import DoubleDQNAgent
from models.harness import (AgentActionStats, AgentPolicyAdapter,
                            capture_flow_latencies)

DATA = ROOT / "data"
OUT = ROOT / "outputs" / "day4"
EVAL_SEEDS = tuple(range(1000, 1005))
VAL_POLICY_SET = (*POLICIES, "agent_ddqn")


def safe_load(entry: dict, split: str, partitions: dict):
    guard_graph_request(entry, split, partitions)
    return load_graph({**entry, "split": split}, DATA)


def load_agent(path: Path) -> DoubleDQNAgent:
    agent = DoubleDQNAgent(actions=4, seed=0)
    agent.load(str(path))
    agent.online.eval()
    return agent


def evaluate_val(agent: DoubleDQNAgent, partitions: dict) -> list[dict]:
    intensity_cfg = json.loads((DATA / "eval_intensity.json").read_text(encoding="utf-8"))
    eval_cfg = json.loads((ROOT / "configs" / "evaluation.json").read_text(encoding="utf-8"))
    alpha = float(eval_cfg["dijkstra_load_aware_alpha"])
    rf_model = joblib.load(ROOT / "outputs" / "rf_routing.joblib")
    rows = []
    action_stats = []
    for graph_no, raw_entry in enumerate(partitions["val"], start=1):
        entry = {**raw_entry, "split": "val"}
        graph = safe_load(entry, "val", partitions)
        intensity = float(intensity_cfg[entry["name"]]["generators"]["poisson"]["intensity"])
        for scenario in ("normal", "link_failures"):
            for policy in VAL_POLICY_SET:
                for seed in EVAL_SEEDS:
                    adapter = AgentPolicyAdapter(agent) if policy == "agent_ddqn" else None
                    with capture_flow_latencies(warmup=100) as capture:
                        if adapter is None:
                            result = day3.run_episode(
                                entry, graph, "poisson", intensity, policy, seed,
                                scenario, alpha, rf_model=rf_model, max_steps=500,
                                warmup=100, data_root=DATA)
                        else:
                            with adapter:
                                result = day3.run_episode(
                                    entry, graph, "poisson", intensity, policy, seed,
                                    scenario, alpha, rf_model=rf_model, max_steps=500,
                                    warmup=100, data_root=DATA)
                            action_stats.append({"graph": entry["name"],
                                                 "scenario": scenario,
                                                 "seed": seed,
                                                 **adapter.stats.summary()})
                    result = dict(result)
                    result.update(median_path_latency_ms=capture.median_latency_ms,
                                  fraction_flows_at_link_latency_cap=capture.fraction_capped,
                                  latency_observations=len(capture.routed_latencies_ms),
                                  measured_decisions=capture.measured_decisions)
                    rows.append(result)
        print(f"validation graph {graph_no} / {len(partitions['val'])}: "
              f"{entry['name']} complete (normal + link_failures, 5 seeds)", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUT / "validation_episode_metrics.csv", rows)
    write_csv(OUT / "validation_agent_action_stats.csv", action_stats)
    summary = aggregate(rows, ("graph", "scenario", "policy"))
    write_csv(OUT / "validation_summary.csv", summary)
    print_validation_tables(summary)
    print_a5_table(summary)
    print_action_table(action_stats)
    print_a7_table(rows)
    print_decision_times(rows)
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("\n", encoding="utf-8")
        return
    fields = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


METRICS = ("mean_packet_loss", "fraction_steps_over_0_9",
           "median_path_latency_ms", "p95_path_latency_ms",
           "fraction_flows_at_link_latency_cap", "flapping_rate",
           "mean_decision_time_ms")


def aggregate(rows: list[dict], keys: tuple[str, ...]) -> list[dict]:
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[k] for k in keys)].append(row)
    result = []
    for key, values in sorted(groups.items(), key=lambda x: tuple(map(str, x[0]))):
        out = dict(zip(keys, key))
        for metric in METRICS:
            vals = [float(row[metric]) for row in values if row.get(metric) is not None]
            out[f"{metric}_mean"] = statistics.mean(vals) if vals else math.nan
            out[f"{metric}_std"] = statistics.stdev(vals) if len(vals) > 1 else 0.0
        out["n_seeds"] = len(values)
        result.append(out)
    return result


def print_validation_tables(summary: list[dict]) -> None:
    for scenario in ("normal", "link_failures"):
        print(f"\nValidation {scenario}: mean ± SD over 5 seeds; "
              "latency values are ms; cap is fraction of requests with at least one capped link.",
              flush=True)
        print("| Graph | Policy | Loss | >0.9 | Median latency | P95 latency | At cap | Flapping | Decision ms |", flush=True)
        print("|---|---|---:|---:|---:|---:|---:|---:|---:|", flush=True)
        for row in (r for r in summary if r["scenario"] == scenario):
            print(f"| {row['graph']} | {row['policy']} | "
                  f"{row['mean_packet_loss_mean']:.5f}±{row['mean_packet_loss_std']:.5f} | "
                  f"{row['fraction_steps_over_0_9_mean']:.3f}±{row['fraction_steps_over_0_9_std']:.3f} | "
                  f"{row['median_path_latency_ms_mean']:.2f}±{row['median_path_latency_ms_std']:.2f} | "
                  f"{row['p95_path_latency_ms_mean']:.2f}±{row['p95_path_latency_ms_std']:.2f} | "
                  f"{row['fraction_flows_at_link_latency_cap_mean']:.3f}±{row['fraction_flows_at_link_latency_cap_std']:.3f} | "
                  f"{row['flapping_rate_mean']:.3f}±{row['flapping_rate_std']:.3f} | "
                  f"{row['mean_decision_time_ms_mean']:.4f}±{row['mean_decision_time_ms_std']:.4f} |", flush=True)


def print_a5_table(summary: list[dict]) -> None:
    print("\nA5 normal-scenario loss comparison on validation graphs:", flush=True)
    print("| Graph | Agent | random | static | greedy | LA-K | LA full | RF | Agent wins vs random/static |", flush=True)
    print("|---|---:|---:|---:|---:|---:|---:|---:|---|", flush=True)
    by = {(r["graph"], r["policy"]): r for r in summary if r["scenario"] == "normal"}
    for graph in sorted({r["graph"] for r in summary if r["scenario"] == "normal"}):
        agent_loss = by[graph, "agent_ddqn"]["mean_packet_loss_mean"]
        names = ("random", "dijkstra_static", "greedy_min_util",
                 "dijkstra_load_aware_k", "dijkstra_load_aware", "rf_routing")
        losses = [by[graph, name]["mean_packet_loss_mean"] for name in names]
        wins = ("W" if agent_loss < losses[0] else "L") + "/" + ("W" if agent_loss < losses[1] else "L")
        print("| " + graph + " | " + f"{agent_loss:.5f} | "
              + " | ".join(f"{value:.5f}" for value in losses)
              + f" | {wins} |", flush=True)


def print_action_table(rows: list[dict]) -> None:
    print("\nAgent action analysis (all validation normal + link-failure decisions):", flush=True)
    print("| Graph | vs greedy_min_util | vs dijkstra_load_aware_k | lowest-latency candidate | Q min..max |", flush=True)
    print("|---|---:|---:|---:|---:|", flush=True)
    graphs = sorted({r["graph"] for r in rows})
    for graph in graphs:
        group = [r for r in rows if r["graph"] == graph]
        decisions = sum(r["decisions"] for r in group)
        greedy = sum(r["agreement_greedy_min_util"] * r["decisions"] for r in group)
        load = sum(r["agreement_dijkstra_load_aware_k"] * r["decisions"] for r in group)
        low = sum(r["lowest_latency_candidate"] * r["decisions"] for r in group)
        qmins = [r["q_min"] for r in group if r["q_count"]]
        qmaxs = [r["q_max"] for r in group if r["q_count"]]
        print(f"| {graph} | {greedy/max(1,decisions):.3%} | {load/max(1,decisions):.3%} | "
              f"{low/max(1,decisions):.3%} | {min(qmins,default=0):.3f}..{max(qmaxs,default=0):.3f} |",
              flush=True)


def print_a7_table(rows: list[dict]) -> None:
    print("\nA7 link-failure safety:", flush=True)
    print("| Graph | Invalid accepted | Post-failure routed flows (min across 5 seeds) |", flush=True)
    print("|---|---:|---:|", flush=True)
    for graph in sorted({r["graph"] for r in rows}):
        group = [r for r in rows if r["scenario"] == "link_failures"
                 and r["graph"] == graph and r["policy"] == "agent_ddqn"]
        print(f"| {graph} | {sum(r['invalid_actions_accepted'] for r in group)} | "
              f"{min((r['post_failure_routed_flows'] for r in group), default=0)} |", flush=True)


def print_decision_times(rows: list[dict]) -> None:
    print("\nDay 4 validation mean decision time across graph/scenario/seeds:", flush=True)
    print("| Policy | Mean ms / decision |", flush=True)
    print("|---|---:|", flush=True)
    for policy in VAL_POLICY_SET:
        values = [r["mean_decision_time_ms"] for r in rows if r["policy"] == policy]
        print(f"| {policy} | {statistics.mean(values):.5f} |", flush=True)


def run_k_diagnostic(partitions: dict) -> list[dict]:
    intensity_cfg = json.loads((DATA / "eval_intensity.json").read_text(encoding="utf-8"))
    selected = (("val", "EliBackbone"), ("train", "Internet2"), ("train", "geant"))
    rows = []
    for split, name in selected:
        raw_entry = next(row for row in partitions[split] if row["name"] == name)
        entry = {**raw_entry, "split": split}
        graph = safe_load(entry, split, partitions)
        intensity = float(intensity_cfg[name]["generators"]["poisson"]["intensity"])
        for label, k, policy in (("K=4", 4, "dijkstra_load_aware_k"),
                                 ("K=6", 6, "dijkstra_load_aware_k"),
                                 ("full_graph", 4, "dijkstra_load_aware")):
            for seed in EVAL_SEEDS:
                config = NetworkEnvConfig(k_paths=k, max_steps=500, intensity=intensity)
                stub = PoissonTrafficGenerator(sorted(graph.nodes), demand_mbps=1.0)
                topology = NetworkRoutingEnv(graph, config, traffic_generator=stub)
                traffic = make_traffic("poisson", entry, topology, intensity, DATA)
                env = NetworkRoutingEnv(graph, config, traffic_generator=traffic)
                env.reset(seed=seed)
                rng = np.random.default_rng(seed ^ (sum(map(ord, policy)) << 8))
                losses, overloads, latencies = [], [], []
                for step in range(500):
                    decision = choose_decision(policy, env, rng, alpha=4.0)
                    if decision.explicit_path is not None:
                        _obs, _reward, _term, _trunc, info = step_explicit_path(env, decision.explicit_path)
                    else:
                        _obs, _reward, _term, _trunc, info = env.step(decision.action)
                    if step >= 100:
                        losses.append(float(info.get("path_loss", 1.0)))
                        overloads.append(float(info.get("step_max_backbone_utilization", 0.0) > 0.9))
                        if info.get("path_latency_ms") is not None:
                            latencies.append(float(info["path_latency_ms"]))
                rows.append({"split": split, "graph": name, "approach": label,
                             "seed": seed, "intensity": intensity,
                             "mean_loss": float(np.mean(losses)),
                             "fraction_over_0_9": float(np.mean(overloads)),
                             "mean_latency_ms": float(np.mean(latencies)) if latencies else 0.0})
        print(f"K diagnostic complete: {split} {name}", flush=True)
    summary = aggregate_k(rows)
    write_csv(OUT / "k_diagnostic.csv", rows)
    write_csv(OUT / "k_diagnostic_summary.csv", summary)
    print("\nK diagnostic, mean ± SD over five seeds:", flush=True)
    print("| Split | Graph | Approach | Loss | >0.9 | Mean latency ms |", flush=True)
    print("|---|---|---|---:|---:|---:|", flush=True)
    for r in summary:
        print(f"| {r['split']} | {r['graph']} | {r['approach']} | "
              f"{r['mean_loss_mean']:.5f}±{r['mean_loss_std']:.5f} | "
              f"{r['fraction_over_0_9_mean']:.3f}±{r['fraction_over_0_9_std']:.3f} | "
              f"{r['mean_latency_ms_mean']:.2f}±{r['mean_latency_ms_std']:.2f} |", flush=True)
    return rows


def aggregate_k(rows: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for r in rows:
        groups[(r["split"], r["graph"], r["approach"])].append(r)
    out = []
    for key, values in sorted(groups.items()):
        row = dict(zip(("split", "graph", "approach"), key))
        for metric in ("mean_loss", "fraction_over_0_9", "mean_latency_ms"):
            vals = [r[metric] for r in values]
            row[f"{metric}_mean"] = statistics.mean(vals)
            row[f"{metric}_std"] = statistics.stdev(vals)
        out.append(row)
    return out


def uncongested_control(agent: DoubleDQNAgent, partitions: dict) -> list[dict]:
    selected = ("Arpanet19728", "Compuserve", "EliBackbone")
    rf_model = joblib.load(ROOT / "outputs" / "rf_routing.joblib")
    eval_cfg = json.loads((ROOT / "configs" / "evaluation.json").read_text(encoding="utf-8"))
    alpha = float(eval_cfg["dijkstra_load_aware_alpha"])
    rows = []
    for name in selected:
        raw_entry = next(row for row in partitions["val"] if row["name"] == name)
        entry = {**raw_entry, "split": "val"}
        graph = safe_load(entry, "val", partitions)
        for policy in ("dijkstra_static", "agent_ddqn"):
            for seed in EVAL_SEEDS:
                adapter = AgentPolicyAdapter(agent) if policy == "agent_ddqn" else None
                with capture_flow_latencies(warmup=100) as capture:
                    if adapter is None:
                        result = day3.run_episode(
                            entry, graph, "poisson", 0.025, policy, seed, "normal",
                            alpha, rf_model=rf_model, max_steps=500, warmup=100,
                            data_root=DATA)
                    else:
                        with adapter:
                            result = day3.run_episode(
                                entry, graph, "poisson", 0.025, policy, seed, "normal",
                                alpha, rf_model=rf_model, max_steps=500, warmup=100,
                                data_root=DATA)
                rows.append({"graph": name, "policy": policy, "seed": seed,
                             "mean_loss": result["mean_packet_loss"],
                             "median_latency_ms": capture.median_latency_ms,
                             "fraction_cap": capture.fraction_capped})
        print(f"uncongested control complete: {name}", flush=True)
    write_csv(OUT / "uncongested_control.csv", rows)
    groups = defaultdict(dict)
    for r in rows:
        groups[r["graph"]].setdefault(r["policy"], []).append(r)
    print("\nUncongested control (intensity 0.025; medians averaged over five seeds):", flush=True)
    print("| Graph | Agent median ms | Static median ms | Difference | Agent loss | Static loss | A6 |", flush=True)
    print("|---|---:|---:|---:|---:|---:|---|", flush=True)
    for graph, by_policy in groups.items():
        a, s = by_policy["agent_ddqn"], by_policy["dijkstra_static"]
        am = statistics.mean(r["median_latency_ms"] for r in a)
        sm = statistics.mean(r["median_latency_ms"] for r in s)
        al = statistics.mean(r["mean_loss"] for r in a)
        sl = statistics.mean(r["mean_loss"] for r in s)
        pct = 100.0 * (am / sm - 1.0) if sm else math.inf
        passed = abs(am - sm) <= 0.1 * sm and al <= sl
        print(f"| {graph} | {am:.2f} | {sm:.2f} | {pct:+.1f}% | {al:.5f} | {sl:.5f} | {passed} |", flush=True)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path,
                        default=ROOT / "runs" / "day4" / "stage_b_best.pt")
    args = parser.parse_args()
    partitions = read_partitions(DATA / "splits.json")
    if not args.checkpoint.exists():
        parser.error(f"checkpoint not found: {args.checkpoint}")
    torch.set_num_threads(min(4, torch.get_num_threads()))
    agent = load_agent(args.checkpoint)
    results = evaluate_val(agent, partitions)
    uncongested_control(agent, partitions)
    run_k_diagnostic(partitions)
    print(f"Saved {len(results)} validation episodes. No holdout topology requested.", flush=True)


if __name__ == "__main__":
    main()
