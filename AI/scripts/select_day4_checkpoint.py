"""Apply the Day 4 top-3 validation-loss then uncongested-control rule."""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from pathlib import Path
from shutil import copy2

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from baselines import evaluation as day3
from baselines.evaluation import load_graph
from models.data_guard import guard_graph_request, read_partitions
from models.dqn import DoubleDQNAgent
from models.harness import capture_flow_latencies, run_agent_episode

DATA = ROOT / "data"
RUNS = ROOT / "runs" / "day4"
OUT = ROOT / "outputs" / "day4"
CONTROL_GRAPHS = ("Arpanet19728", "Compuserve", "EliBackbone")
SEEDS = tuple(range(1000, 1005))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("\n", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--top3", type=Path, default=OUT / "stage_b_top3.json")
    args = parser.parse_args()
    if not args.top3.exists():
        parser.error(f"top-3 manifest not found: {args.top3}")
    candidates = json.loads(args.top3.read_text(encoding="utf-8"))
    if not candidates:
        parser.error("top-3 manifest has no checkpoint candidates")

    torch.set_num_threads(1)
    partitions = read_partitions(DATA / "splits.json")
    val_entries = {row["name"]: dict(row, split="val")
                   for row in partitions["val"]}
    graphs = {}
    for name in CONTROL_GRAPHS:
        entry = val_entries[name]
        guard_graph_request(entry, "val", partitions)
        graphs[name] = load_graph(entry, DATA)

    raw_rows: list[dict] = []
    static_results = {}
    for name in CONTROL_GRAPHS:
        entry = val_entries[name]
        for seed in SEEDS:
            with capture_flow_latencies(warmup=100) as capture:
                result = day3.run_episode(
                    entry, graphs[name], "poisson", 0.025,
                    "dijkstra_static", seed, "normal", 4.0,
                    rf_model=None, max_steps=500, warmup=100, data_root=DATA)
            static_results[name, seed] = {
                "mean_loss": float(result["mean_packet_loss"]),
                "median_latency_ms": capture.median_latency_ms,
                "fraction_cap": capture.fraction_capped,
            }

    candidate_summaries = []
    for candidate in candidates:
        candidate_path = Path(candidate["path"])
        if not candidate_path.exists():
            raise FileNotFoundError(candidate_path)
        agent = DoubleDQNAgent(actions=4, seed=0)
        agent.load(str(candidate_path))
        agent.online.eval()
        per_graph = {}
        for name in CONTROL_GRAPHS:
            entry = val_entries[name]
            candidate_rows = []
            for seed in SEEDS:
                with capture_flow_latencies(warmup=100) as capture:
                    result, _stats = run_agent_episode(
                        entry, graphs[name], "poisson", 0.025,
                        seed=seed, scenario="normal", alpha=4.0, rf_model=None,
                        max_steps=500, warmup=100, data_root=DATA, agent=agent)
                row = {
                    "step": int(candidate["step"]),
                    "val_loss": float(candidate["val_loss"]),
                    "checkpoint": str(candidate_path),
                    "graph": name,
                    "seed": seed,
                    "policy": "agent_ddqn",
                    "mean_loss": float(result["mean_packet_loss"]),
                    "median_latency_ms": capture.median_latency_ms,
                    "fraction_cap": capture.fraction_capped,
                }
                candidate_rows.append(row)
                raw_rows.append(row)
                raw_rows.append({**static_results[name, seed],
                                 "step": int(candidate["step"]),
                                 "val_loss": float(candidate["val_loss"]),
                                 "checkpoint": str(candidate_path),
                                 "graph": name, "seed": seed,
                                 "policy": "dijkstra_static"})
            agent_loss = statistics.mean(row["mean_loss"] for row in candidate_rows)
            agent_latency = statistics.mean(row["median_latency_ms"] for row in candidate_rows)
            static_loss = statistics.mean(static_results[name, seed]["mean_loss"]
                                          for seed in SEEDS)
            static_latency = statistics.mean(static_results[name, seed]["median_latency_ms"]
                                             for seed in SEEDS)
            within_ten = (static_latency > 0 and
                          abs(agent_latency - static_latency) <= 0.10 * static_latency)
            loss_not_worse = agent_loss <= static_loss + 1e-12
            passes = within_ten and loss_not_worse
            per_graph[name] = passes
            candidate_summaries.append({
                "step": int(candidate["step"]),
                "val_loss": float(candidate["val_loss"]),
                "checkpoint": str(candidate_path),
                "graph": name,
                "agent_mean_median_latency_ms": agent_latency,
                "static_mean_median_latency_ms": static_latency,
                "latency_within_10_percent": within_ten,
                "agent_mean_loss": agent_loss,
                "static_mean_loss": static_loss,
                "loss_no_worse": loss_not_worse,
                "control_pass": passes,
            })
            print(f"control candidate step {candidate['step']} | {name} | "
                  f"median {agent_latency:.3f}/{static_latency:.3f} ms | "
                  f"loss {agent_loss:.6f}/{static_loss:.6f} | "
                  f"pass={passes}", flush=True)

    passing_steps = {row["step"] for row in candidate_summaries
                     if row["control_pass"]}
    candidate_steps = {int(item["step"]) for item in candidates}
    step_pass = {step: all(
        next(row["control_pass"] for row in candidate_summaries
             if row["step"] == step and row["graph"] == name)
        for name in CONTROL_GRAPHS) for step in candidate_steps}
    eligible = [item for item in candidates if step_pass[int(item["step"])] ]
    selected = min(eligible, key=lambda item: float(item["val_loss"])) if eligible else None
    diagnostic = (selected if selected is not None else
                  min(candidates, key=lambda item: float(item["val_loss"])))

    OUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUT / "checkpoint_control_selection.csv", candidate_summaries)
    write_csv(OUT / "checkpoint_control_raw.csv", raw_rows)
    report = {
        "selection_rule": "among the top three by validation loss, select the lowest-loss checkpoint that passes all three intensity-0.025 controls",
        "control_graphs": list(CONTROL_GRAPHS),
        "seeds": list(SEEDS),
        "candidate_control_pass": {str(step): bool(passed)
                                   for step, passed in step_pass.items()},
        "selected": selected,
        "diagnostic_candidate_if_none_pass": diagnostic if selected is None else None,
    }
    (OUT / "checkpoint_selection.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")
    if selected is not None:
        selected_path = Path(selected["path"])
        copy2(selected_path, RUNS / "stage_b_selected.pt")
        copy2(selected_path, RUNS / "stage_b_best.pt")
        print(f"Selected checkpoint: step {selected['step']} "
              f"(val loss {float(selected['val_loss']):.6f}); passed all controls.",
              flush=True)
    else:
        print("No top-3 checkpoint passed all three uncongested controls; "
              f"no checkpoint selected. Lowest-val-loss diagnostic candidate: "
              f"step {diagnostic['step']} (val loss {float(diagnostic['val_loss']):.6f}).",
              flush=True)
    print(f"Control-pass candidate steps: {sorted(passing_steps)}", flush=True)


if __name__ == "__main__":
    main()
