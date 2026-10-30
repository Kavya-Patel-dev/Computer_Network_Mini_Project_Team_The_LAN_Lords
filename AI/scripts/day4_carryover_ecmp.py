"""Day 3 ECMP carry-over diagnostic; touches only ECMP val/test episodes."""
from __future__ import annotations

import csv
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from baselines import evaluation as day3
from baselines.evaluation import load_graph
from baselines.policies import Decision, choose_decision as original_choose

DATA = ROOT / "data"
OUT = ROOT / "outputs" / "day4"
SEEDS = (1000, 1001, 1002, 1003, 1004)


def _path_for(decision: Decision, env):
    if decision.explicit_path is not None:
        return tuple(decision.explicit_path)
    if 0 <= decision.action < len(env._paths.paths):
        return tuple(env._paths.paths[decision.action])
    return None


def _static_ecmp(env, rng, alpha, rf_model, time_since_last_failure):
    paths = tuple(tuple(path) for path in env._paths.paths)
    if not paths:
        return Decision(env.config.k_paths)
    # The ECMP tie set uses propagation latency only, independent of current load.
    costs = [sum(float(env.graph[u][v].get("latency", 0.0))
                 for u, v in zip(path, path[1:])) for path in paths]
    best = min(costs)
    eligible = [i for i, cost in enumerate(costs)
                if cost <= best * 1.01 + 1e-12]
    action = int(rng.choice(eligible))
    return Decision(action, ecmp_tie=len(eligible) > 1)


def run_one(entry, graph, generator, intensity, seed, criterion):
    state = {"compared": 0, "different": 0}

    def chooser(policy, env, rng, alpha=1.0, rf_model=None,
                time_since_last_failure=10_000):
        if policy != "ecmp":
            return original_choose(policy, env, rng, alpha=alpha,
                                  rf_model=rf_model,
                                  time_since_last_failure=time_since_last_failure)
        static = original_choose("dijkstra_static", env, np.random.default_rng(0),
                                 alpha=alpha, rf_model=rf_model,
                                 time_since_last_failure=time_since_last_failure)
        if criterion == "queue_latency":
            choice = original_choose("ecmp", env, rng, alpha=alpha,
                                     rf_model=rf_model,
                                     time_since_last_failure=time_since_last_failure)
        else:
            choice = _static_ecmp(env, rng, alpha, rf_model,
                                  time_since_last_failure)
        if env._steps >= 100:
            state["compared"] += 1
            state["different"] += int(_path_for(choice, env) != _path_for(static, env))
        return choice

    previous = day3.choose_decision
    day3.choose_decision = chooser
    try:
        row = day3.run_episode(
            entry, graph, generator, intensity, "ecmp", seed, "normal", 4.0,
            max_steps=500, warmup=100, data_root=DATA)
    finally:
        day3.choose_decision = previous
    row["ecmp_static_disagreement_fraction"] = (
        state["different"] / max(1, state["compared"]))
    return row


def main() -> None:
    partitions = json.loads((DATA / "splits.json").read_text(encoding="utf-8"))
    intensity_config = json.loads((DATA / "eval_intensity.json").read_text(encoding="utf-8"))
    gate_report = json.loads((ROOT / "outputs" / "gate_report.json").read_text(encoding="utf-8"))
    cohort = set(gate_report["G1"]["eligible_graphs"])
    old_csv = list(csv.DictReader((ROOT / "outputs" / "baselines.csv").open(encoding="utf-8")))
    old_rows = [r for r in old_csv if r["split"] in {"val", "test"}
                and r["scenario"] == "normal" and r["policy"] == "ecmp"]
    active_rows = []
    total_graphs = sum(len(partitions[s]) for s in ("val", "test"))
    graph_no = 0
    for split in ("val", "test"):
        for raw_entry in partitions[split]:
            graph_no += 1
            entry = {**raw_entry, "split": split}
            graph = load_graph(entry, DATA)
            generators = ("gravity", "hotspot") if entry["name"] in cohort else ("poisson",)
            for generator in generators:
                intensity = float(intensity_config[entry["name"]]["generators"][generator]["intensity"])
                for seed in SEEDS:
                    for criterion in ("queue_latency", "static_latency"):
                        row = run_one(entry, graph, generator, intensity, seed, criterion)
                        row["criterion"] = criterion
                        active_rows.append(row)
            print(f"ECMP carry-over: graph {graph_no} / {total_graphs} | {split} {entry['name']} | "
                  f"generators={','.join(generators)} seeds=5", flush=True)

    OUT.mkdir(parents=True, exist_ok=True)
    raw_path = OUT / "ecmp_static_ties.csv"
    fields = list(active_rows[0])
    with raw_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader(); writer.writerows(active_rows)

    def summarize(records, metric, criterion=None):
        selected = [r for r in records if criterion is None or r.get("criterion") == criterion]
        return statistics.mean(float(r[metric]) for r in selected) if selected else math.nan

    old_map = {(r["split"], r["graph"], r["generator"]): r for r in old_rows}
    grouped = defaultdict(list)
    for row in active_rows:
        grouped[(row["split"], row["graph"], row["criterion"])].append(row)
    comparison = []
    for split in ("val", "test"):
        for entry in partitions[split]:
            name = entry["name"]
            run_gens = ("gravity", "hotspot") if name in cohort else ("poisson",)
            old_graph = [old_map[(split, name, gen)] for gen in run_gens]
            row = {"split": split, "graph": name,
                   "old_queue_loss": statistics.mean(float(x["mean_packet_loss_mean"]) for x in old_graph),
                   "old_queue_over_0_9": statistics.mean(float(x["fraction_steps_over_0_9_mean"]) for x in old_graph),
                   "old_queue_latency_ms": statistics.mean(float(x["mean_path_latency_ms_mean"]) for x in old_graph)}
            for criterion, prefix in (("queue_latency", "rerun_old"),
                                      ("static_latency", "new_static_ties")):
                records = grouped[(split, name, criterion)]
                for metric, label in (("mean_packet_loss", "loss"),
                                      ("fraction_steps_over_0_9", "over_0_9"),
                                      ("mean_path_latency_ms", "latency_ms"),
                                      ("ecmp_static_disagreement_fraction", "diff_static_fraction")):
                    row[f"{prefix}_{label}"] = summarize(records, metric)
            comparison.append(row)
    comp_path = OUT / "ecmp_comparison.csv"
    with comp_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(comparison[0]))
        writer.writeheader(); writer.writerows(comparison)

    print("| Split | Graph | Saved old loss | Re-run old loss | Static-tie loss | "
          "Saved old >.9 | Re-run old >.9 | Static-tie >.9 | "
          "Old differs from static | New differs from static |", flush=True)
    print("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|", flush=True)
    for row in comparison:
        print(f"| {row['split']} | {row['graph']} | {row['old_queue_loss']:.5f} | "
              f"{row['rerun_old_loss']:.5f} | {row['new_static_ties_loss']:.5f} | "
              f"{row['old_queue_over_0_9']:.3f} | {row['rerun_old_over_0_9']:.3f} | "
              f"{row['new_static_ties_over_0_9']:.3f} | "
              f"{row['rerun_old_diff_static_fraction']:.3f} | "
              f"{row['new_static_ties_diff_static_fraction']:.3f} |", flush=True)
    print(f"Wrote {raw_path} and {comp_path}", flush=True)


if __name__ == "__main__":
    main()
