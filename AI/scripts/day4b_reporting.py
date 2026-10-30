"""Repair Day 4 validation ECMP naming and append corrected static ECMP runs."""
from __future__ import annotations

import csv
import json
import statistics
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from baselines import evaluation as day3
from baselines.evaluation import load_graph
from baselines.policies import Decision, choose_decision as original_choose
from models.data_guard import guard_graph_request, read_partitions
from models.harness import capture_flow_latencies
from scripts.evaluate_day4 import aggregate, write_csv

DATA = ROOT / "data"
OUT = ROOT / "outputs" / "day4"
SEEDS = tuple(range(1000, 1005))
METRICS = (
    ("median_path_latency_ms", "Median path latency (ms)"),
    ("p95_path_latency_ms", "P95 path latency (ms)"),
    ("fraction_flows_at_link_latency_cap", "Fraction flows at latency cap"),
    ("flapping_rate", "Same-OD route flapping rate"),
)


def static_ecmp(env, rng: np.random.Generator) -> Decision:
    paths = tuple(tuple(path) for path in env._paths.paths)
    if not paths:
        return Decision(env.config.k_paths)
    costs = [sum(float(env.graph[u][v].get("latency", 0.0))
                 for u, v in zip(path, path[1:])) for path in paths]
    best = min(costs)
    eligible = [i for i, cost in enumerate(costs)
                if cost <= best * 1.01 + 1e-12]
    return Decision(int(rng.choice(eligible)), ecmp_tie=len(eligible) > 1)


def run_policy(entry: dict, graph, intensity: float, scenario: str,
               policy: str, seed: int, alpha: float) -> dict:
    previous = day3.choose_decision

    def chooser(policy_name, env, rng, alpha=1.0, rf_model=None,
                time_since_last_failure=10_000):
        if policy_name == "ecmp":
            return static_ecmp(env, rng)
        if policy_name == "ties_on_queue_latency":
            return original_choose("ecmp", env, rng, alpha=alpha,
                                   rf_model=rf_model,
                                   time_since_last_failure=time_since_last_failure)
        return original_choose(policy_name, env, rng, alpha=alpha,
                               rf_model=rf_model,
                               time_since_last_failure=time_since_last_failure)

    day3.choose_decision = chooser
    try:
        with capture_flow_latencies(warmup=100) as capture:
            result = day3.run_episode(
                entry, graph, "poisson", intensity, policy, seed, scenario,
                alpha, rf_model=None, max_steps=500, warmup=100, data_root=DATA)
        result = dict(result)
        result.update(median_path_latency_ms=capture.median_latency_ms,
                      fraction_flows_at_link_latency_cap=capture.fraction_capped,
                      latency_observations=len(capture.routed_latencies_ms),
                      measured_decisions=capture.measured_decisions)
        return result
    finally:
        day3.choose_decision = previous


def print_metric_tables(summary: list[dict], policies: list[str]) -> None:
    for scenario in ("normal", "link_failures"):
        selected = [row for row in summary if row["scenario"] == scenario]
        for metric, label in METRICS:
            print(f"\nValidation {scenario}: {label} (mean ± SD over five seeds)")
            print("| Graph | " + " | ".join(policies) + " |")
            print("|---|" + "---:|" * len(policies))
            by_graph = {row["graph"]: row for row in selected}
            for graph in sorted(by_graph):
                row = by_graph[graph]
                cells = []
                for policy in policies:
                    mean = float(row[f"{metric}_mean"])
                    # Summary rows are keyed by graph+scenario+policy, so look
                    # up each policy row instead of reusing the current row.
                    match = next(item for item in selected
                                 if item["graph"] == graph and item["policy"] == policy)
                    mean = float(match[f"{metric}_mean"])
                    std = float(match[f"{metric}_std"])
                    cells.append(f"{mean:.3f} ± {std:.3f}")
                print(f"| {graph} | " + " | ".join(cells) + " |")


def main() -> None:
    partitions = read_partitions(DATA / "splits.json")
    intensity_cfg = json.loads((DATA / "eval_intensity.json").read_text(encoding="utf-8"))
    eval_cfg = json.loads((ROOT / "configs" / "evaluation.json").read_text(encoding="utf-8"))
    alpha = float(eval_cfg["dijkstra_load_aware_alpha"])
    metrics_path = OUT / "validation_episode_metrics.csv"
    with metrics_path.open(encoding="utf-8", newline="") as handle:
        existing = list(csv.DictReader(handle))
    for row in existing:
        if row["policy"] == "ecmp":
            row["policy"] = "ties_on_queue_latency"

    corrected_rows = []
    entries = partitions["val"]
    for graph_no, raw_entry in enumerate(entries, 1):
        entry = {**raw_entry, "split": "val"}
        guard_graph_request(entry, "val", partitions)
        graph = load_graph(entry, DATA)
        intensity = float(intensity_cfg[entry["name"]]["generators"]["poisson"]["intensity"])
        for scenario in ("normal", "link_failures"):
            for policy in ("ecmp", "ties_on_queue_latency"):
                for seed in SEEDS:
                    corrected_rows.append(run_policy(
                        entry, graph, intensity, scenario, policy, seed, alpha))
        print(f"ECMP reporting repair: graph {graph_no} / {len(entries)} | "
              f"{entry['name']} | normal + link_failures | 5 seeds", flush=True)

    write_csv(OUT / "validation_ecmp_repair_raw.csv", corrected_rows)
    # Existing Day 4 ECMP records are the queue-latency variant. Remove those
    # rows and replace them with explicitly named queue-latency records before
    # appending the corrected static-propagation ECMP episodes.
    rows = [row for row in existing if row["policy"] != "ties_on_queue_latency"]
    rows.extend(corrected_rows)
    write_csv(metrics_path, rows)
    policies = sorted({row["policy"] for row in rows})
    summary = aggregate(rows, ("graph", "scenario", "policy"))
    write_csv(OUT / "validation_summary.csv", summary)
    print_metric_tables(summary, policies)
    print(f"\nSaved {len(corrected_rows)} rerun ECMP episodes; validation table now "
          f"contains {len(rows)} episodes and policies: {', '.join(policies)}.", flush=True)


if __name__ == "__main__":
    main()
