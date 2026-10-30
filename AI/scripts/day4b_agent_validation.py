"""Replace stale Day 4 agent rows with validation for the selected checkpoint."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from baselines import evaluation as day3
from baselines.evaluation import load_graph
from models.data_guard import guard_graph_request, read_partitions
from models.dqn import DoubleDQNAgent
from models.harness import capture_flow_latencies, run_agent_episode
from scripts.evaluate_day4 import aggregate, write_csv

DATA = ROOT / "data"
OUT = ROOT / "outputs" / "day4"
SEEDS = tuple(range(1000, 1005))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path,
                        default=ROOT / "runs" / "day4" / "stage_b_selected.pt")
    args = parser.parse_args()
    if not args.checkpoint.exists():
        parser.error(f"selected checkpoint not found: {args.checkpoint}")

    torch.set_num_threads(1)
    agent = DoubleDQNAgent(actions=4, seed=0)
    agent.load(str(args.checkpoint))
    agent.online.eval()
    partitions = read_partitions(DATA / "splits.json")
    intensity_cfg = json.loads((DATA / "eval_intensity.json").read_text(encoding="utf-8"))
    eval_cfg = json.loads((ROOT / "configs" / "evaluation.json").read_text(encoding="utf-8"))
    alpha = float(eval_cfg["dijkstra_load_aware_alpha"])
    new_rows: list[dict] = []
    action_rows: list[dict] = []

    for graph_no, raw_entry in enumerate(partitions["val"], 1):
        entry = {**raw_entry, "split": "val"}
        guard_graph_request(entry, "val", partitions)
        graph = load_graph(entry, DATA)
        intensity = float(intensity_cfg[entry["name"]]["generators"]["poisson"]["intensity"])
        for scenario in ("normal", "link_failures"):
            for seed in SEEDS:
                with capture_flow_latencies(warmup=100) as capture:
                    result, stats = run_agent_episode(
                        entry, graph, "poisson", intensity, seed=seed,
                        scenario=scenario, alpha=alpha, rf_model=None,
                        max_steps=500, warmup=100, data_root=DATA, agent=agent)
                row = dict(result)
                row.update(median_path_latency_ms=capture.median_latency_ms,
                           fraction_flows_at_link_latency_cap=capture.fraction_capped,
                           latency_observations=len(capture.routed_latencies_ms),
                           measured_decisions=capture.measured_decisions)
                new_rows.append(row)
                action_rows.append({"graph": entry["name"], "scenario": scenario,
                                    "seed": seed, **stats})
        print(f"agent validation: graph {graph_no} / {len(partitions['val'])} | "
              f"{entry['name']} | normal + link_failures | 5 seeds", flush=True)

    metrics_path = OUT / "validation_episode_metrics.csv"
    with metrics_path.open(encoding="utf-8", newline="") as handle:
        existing = list(csv.DictReader(handle))
    rows = [row for row in existing if row["policy"] != "agent_ddqn"]
    rows.extend(new_rows)
    # Keep the existing stable column order, and reject missing fields early.
    columns = list(existing[0])
    missing = set(columns) - set(new_rows[0])
    if missing:
        raise ValueError(f"new agent episode records lack columns: {sorted(missing)}")
    write_csv(metrics_path, [{key: row.get(key, "") for key in columns}
                             for row in rows])
    write_csv(OUT / "validation_agent_action_stats.csv", action_rows)
    summary = aggregate(rows, ("graph", "scenario", "policy"))
    write_csv(OUT / "validation_summary.csv", summary)
    print("Selected-agent validation summary (mean over five seeds):")
    print("| Graph | Scenario | Loss | >0.9 | Median ms | P95 ms | Cap fraction | Flapping |")
    print("|---|---|---:|---:|---:|---:|---:|---:|")
    for row in summary:
        if row["policy"] != "agent_ddqn":
            continue
        print(f"| {row['graph']} | {row['scenario']} | "
              f"{float(row['mean_packet_loss_mean']):.6f} | "
              f"{float(row['fraction_steps_over_0_9_mean']):.4f} | "
              f"{float(row['median_path_latency_ms_mean']):.3f} | "
              f"{float(row['p95_path_latency_ms_mean']):.3f} | "
              f"{float(row['fraction_flows_at_link_latency_cap_mean']):.4f} | "
              f"{float(row['flapping_rate_mean']):.4f} |")
    print(f"Saved {len(new_rows)} selected-agent validation episodes.", flush=True)


if __name__ == "__main__":
    main()
