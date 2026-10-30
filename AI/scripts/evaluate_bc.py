"""Evaluate Day 5.2 BC on validation/control only; test topologies stay locked."""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import contextmanager
from pathlib import Path

import joblib
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from baselines import evaluation as day3
from baselines.evaluation import load_graph
from baselines.policies import Decision, POLICIES
from env.network_env import NetworkEnvConfig, NetworkRoutingEnv
from models.data_guard import guard_graph_request, read_partitions
from models.dqn import DoubleDQNAgent
from models.harness import capture_flow_latencies
from models.obs import ObservationWrapper

DATA = ROOT / "data"
OUT = ROOT / "outputs" / "day5"
CHECKPOINT = ROOT / "runs" / "day5" / "bc_init.pt"
SEEDS = tuple(range(1000, 1005))
CONTROLS = ("Arpanet19728", "Compuserve", "EliBackbone")
BASELINE_NAMES = {
    "random": "random",
    "dijkstra_static": "dijkstra_static",
    "ecmp": "corrected_ecmp",
    "greedy_min_util": "greedy_min_util",
    "dijkstra_load_aware_k": "dijkstra_load_aware_k",
    "dijkstra_load_aware": "dijkstra_load_aware",
    "rf_routing": "rf_routing",
}

_PARTITIONS = None
_AGENT = None
_RF_MODEL = None
_INTENSITIES = None
_ALPHA = None


def init_worker(checkpoint: str) -> None:
    global _PARTITIONS, _AGENT, _RF_MODEL, _INTENSITIES, _ALPHA
    torch.set_num_threads(1)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass
    _PARTITIONS = read_partitions(DATA / "splits.json")
    _AGENT = DoubleDQNAgent(actions=4, seed=0, use_custom_collate=True)
    metadata = _AGENT.load(checkpoint)
    _AGENT.online.eval()
    if metadata.get("stage") != "day5.2_bc":
        raise ValueError("checkpoint is not a Day 5.2 BC checkpoint")
    _RF_MODEL = joblib.load(ROOT / "outputs" / "rf_routing.joblib")
    _INTENSITIES = json.loads((DATA / "eval_intensity.json").read_text(encoding="utf-8"))
    eval_cfg = json.loads((ROOT / "configs" / "evaluation.json").read_text(encoding="utf-8"))
    _ALPHA = float(eval_cfg["dijkstra_load_aware_alpha"])


@contextmanager
def capture_scaled_rewards(warmup: int = 100):
    """Measure the mean per-step reward after the frozen Day 4 wrapper clip."""
    values: list[float] = []
    original = NetworkRoutingEnv.step

    def wrapped(env: NetworkRoutingEnv, action: int):
        measured = int(getattr(env, "_steps", 0)) >= warmup
        result = original(env, action)
        if measured:
            values.append(float(np.clip(result[1], -5.0, 2.0)))
        return result

    NetworkRoutingEnv.step = wrapped
    try:
        yield values
    finally:
        NetworkRoutingEnv.step = original


class ControlDiagnosticAdapter:
    """BC adapter that also records DLAK Q gaps and latency-min choices."""

    def __init__(self, agent):
        self.agent = agent
        self.original = None
        self.env = None
        self.wrapper = None
        self.gaps: list[float] = []
        self.agreements: list[float] = []
        self.lowest_latency: list[float] = []

    def __enter__(self):
        self.original = day3.choose_decision

        def choose(policy, env, rng, alpha=1.0, rf_model=None,
                   time_since_last_failure=10_000):
            if policy != "agent_ddqn":
                return self.original(policy, env, rng, alpha=alpha,
                                     rf_model=rf_model,
                                     time_since_last_failure=time_since_last_failure)
            if self.env is not env:
                self.env = env
                self.wrapper = ObservationWrapper(env, "bc-control")
            state = self.wrapper.process(env._observation())
            valid = np.flatnonzero(state.action_mask)
            if not len(valid):
                return Decision(env.config.k_paths)
            q_values = self.agent.q_values(state)
            action = int(valid[np.argmax(q_values[valid])])
            expert = self.original("dijkstra_load_aware_k", env, rng, alpha=alpha,
                                   rf_model=rf_model,
                                   time_since_last_failure=time_since_last_failure)
            expert_action = int(expert.action)
            costs = []
            for candidate in valid:
                path = env._paths.paths[int(candidate)]
                costs.append(sum(float(env.latencies.get(
                    env._key(u, v), env.graph[u][v].get("latency", 0.0)))
                                  for u, v in zip(path, path[1:])))
            lowest_action = int(valid[int(np.argmin(costs))])
            if int(env._steps) >= 100:
                self.gaps.append(float(q_values[expert_action] - q_values[action]))
                self.agreements.append(float(expert_action == action))
                self.lowest_latency.append(float(lowest_action == action))
            return Decision(action)

        day3.choose_decision = choose
        return self

    def __exit__(self, _exc_type, _exc, _tb):
        day3.choose_decision = self.original
        self.env = None
        self.wrapper = None


def run_episode_row(entry: dict, graph, scenario: str, seed: int, policy: str,
                    intensity: float, control: bool = False,
                    diagnostics: bool = False) -> dict:
    guard_graph_request(entry, "val", _PARTITIONS)
    agent_policy = policy == "agent_ddqn"
    adapter = ControlDiagnosticAdapter(_AGENT) if agent_policy else None
    rewards = None
    capture = None
    started = time.perf_counter()
    with capture_scaled_rewards(warmup=100) as rewards_list:
        with capture_flow_latencies(warmup=100) as flow_capture:
            if adapter is not None:
                with adapter:
                    result = day3.run_episode(
                        entry, graph, "poisson", intensity, policy, seed, scenario,
                        _ALPHA, rf_model=_RF_MODEL, max_steps=500, warmup=100,
                        data_root=DATA)
            else:
                result = day3.run_episode(
                    entry, graph, "poisson", intensity, policy, seed, scenario,
                    _ALPHA, rf_model=_RF_MODEL, max_steps=500, warmup=100,
                    data_root=DATA)
        capture = flow_capture
        rewards = rewards_list
    row = {
        "split": "val", "graph": entry["name"], "source": entry["source"],
        "run_type": "control" if control else "validation", "scenario": scenario,
        "policy": "bc_only" if agent_policy else BASELINE_NAMES[policy],
        "seed": int(seed), "intensity": float(intensity),
        "mean_packet_loss": float(result["mean_packet_loss"]),
        "fraction_steps_over_0_9": float(result["fraction_steps_over_0_9"]),
        "median_path_latency_ms": float(capture.median_latency_ms),
        "p95_path_latency_ms": float(result["p95_path_latency_ms"]),
        "fraction_flows_at_link_latency_cap": float(capture.fraction_capped),
        "flapping_rate": float(result["flapping_rate"]),
        "mean_scaled_reward": float(np.mean(rewards)) if rewards else math.nan,
        "mean_path_latency_ms": float(result["mean_path_latency_ms"]),
        "mean_decision_time_ms": float(result["mean_decision_time_ms"]),
        "elapsed_seconds": time.perf_counter() - started,
    }
    if adapter is not None:
        row.update(mean_q_expert_minus_chosen=float(np.mean(adapter.gaps))
                   if adapter.gaps else math.nan,
                   expert_action_agreement=float(np.mean(adapter.agreements))
                   if adapter.agreements else math.nan,
                   fraction_lowest_latency_candidate=float(np.mean(adapter.lowest_latency))
                   if adapter.lowest_latency else math.nan)
    return row


def run_job(job: tuple[dict, str, int, bool]) -> list[dict]:
    entry, scenario, seed, control = job
    guard_graph_request(entry, "val", _PARTITIONS)
    graph = load_graph(entry, DATA)
    if control:
        policies = ("dijkstra_static", "agent_ddqn")
        intensity = 0.025
    else:
        policies = (*POLICIES, "agent_ddqn")
        intensity = float(_INTENSITIES[entry["name"]]["generators"]["poisson"]["intensity"])
    return [run_episode_row(entry, graph, scenario, seed, policy, intensity, control,
                             diagnostics=control and policy == "agent_ddqn")
            for policy in policies]


def aggregate(rows: list[dict]) -> list[dict]:
    fields = ("mean_packet_loss", "fraction_steps_over_0_9",
              "median_path_latency_ms", "p95_path_latency_ms",
              "fraction_flows_at_link_latency_cap", "flapping_rate",
              "mean_scaled_reward", "mean_path_latency_ms",
              "mean_decision_time_ms")
    groups: dict[tuple, list[dict]] = {}
    for row in rows:
        key = (row["run_type"], row["graph"], row["scenario"], row["policy"])
        groups.setdefault(key, []).append(row)
    summary = []
    for key, values in sorted(groups.items()):
        out = dict(zip(("run_type", "graph", "scenario", "policy"), key))
        for field in fields:
            data = [float(row[field]) for row in values if math.isfinite(float(row[field]))]
            out[f"{field}_mean"] = statistics.mean(data) if data else math.nan
            out[f"{field}_std"] = statistics.stdev(data) if len(data) > 1 else 0.0
        out["n_seeds"] = len(values)
        summary.append(out)
    return summary


def print_validation_table(summary: list[dict]) -> None:
    print("\nValidation results (mean +/- SD over seeds; reward is per-step clipped to [-5, 2]):",
          flush=True)
    print("| Graph | Scenario | Policy | Loss | >0.9 | Median latency | P95 latency | At cap | Flapping | Scaled reward |",
          flush=True)
    print("|---|---|---|---:|---:|---:|---:|---:|---:|---:|", flush=True)
    for row in summary:
        print(f"| {row['graph']} | {row['scenario']} | {row['policy']} | "
              f"{row['mean_packet_loss_mean']:.5f}+/-{row['mean_packet_loss_std']:.5f} | "
              f"{row['fraction_steps_over_0_9_mean']:.3f}+/-{row['fraction_steps_over_0_9_std']:.3f} | "
              f"{row['median_path_latency_ms_mean']:.2f}+/-{row['median_path_latency_ms_std']:.2f} | "
              f"{row['p95_path_latency_ms_mean']:.2f}+/-{row['p95_path_latency_ms_std']:.2f} | "
              f"{row['fraction_flows_at_link_latency_cap_mean']:.3f}+/-{row['fraction_flows_at_link_latency_cap_std']:.3f} | "
              f"{row['flapping_rate_mean']:.3f}+/-{row['flapping_rate_std']:.3f} | "
              f"{row['mean_scaled_reward_mean']:.4f}+/-{row['mean_scaled_reward_std']:.4f} |",
              flush=True)


def print_validation_action_diagnostics(rows: list[dict]) -> None:
    groups: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        if (row["run_type"] == "validation" and row["policy"] == "bc_only"
                and row["scenario"] in {"normal", "link_failures"}):
            groups.setdefault((row["graph"], row["scenario"]), []).append(row)
    print("\nBC action diagnostics on validation graphs (expert = dijkstra_load_aware_k):",
          flush=True)
    print("| Graph | Scenario | Q(expert)-Q(chosen) | Expert agreement | Lowest-latency candidate |",
          flush=True)
    print("|---|---|---:|---:|---:|", flush=True)
    for (graph, scenario), values in sorted(groups.items()):
        gaps = [float(row["mean_q_expert_minus_chosen"]) for row in values]
        agreements = [float(row["expert_action_agreement"]) for row in values]
        lowest = [float(row["fraction_lowest_latency_candidate"]) for row in values]
        print(f"| {graph} | {scenario} | {statistics.mean(gaps):.5f} | "
              f"{statistics.mean(agreements):.3f} | {statistics.mean(lowest):.3f} |",
              flush=True)


def print_control_tables(rows: list[dict]) -> None:
    groups = {}
    for row in rows:
        groups.setdefault((row["graph"], row["policy"]), []).append(row)
    seed_count = max((len(values) for values in groups.values()), default=0)
    print(f"\nUncongested controls (intensity 0.025; mean +/- SD over {seed_count} seeds):",
          flush=True)
    print("| Graph | Policy | Loss | Median latency ms | Fraction at cap |", flush=True)
    print("|---|---|---:|---:|---:|", flush=True)
    for key, values in sorted(groups.items()):
        loss = [float(row["mean_packet_loss"]) for row in values]
        latency = [float(row["median_path_latency_ms"]) for row in values]
        cap = [float(row["fraction_flows_at_link_latency_cap"]) for row in values]
        print(f"| {key[0]} | {key[1]} | {statistics.mean(loss):.6f}+/-{statistics.stdev(loss) if len(loss) > 1 else 0.0:.6f} | "
              f"{statistics.mean(latency):.3f}+/-{statistics.stdev(latency) if len(latency) > 1 else 0.0:.3f} | "
              f"{statistics.mean(cap):.4f}+/-{statistics.stdev(cap) if len(cap) > 1 else 0.0:.4f} |", flush=True)
    print("\nControl diagnostics for the BC agent (expert action = dijkstra_load_aware_k):", flush=True)
    print("| Graph | Q(expert)-Q(chosen) | BC agrees with expert | Chooses lowest-latency candidate |", flush=True)
    print("|---|---:|---:|---:|", flush=True)
    present_graphs = sorted({row["graph"] for row in rows if row["policy"] == "bc_only"})
    for graph in present_graphs:
        values = [row for row in rows if row["graph"] == graph and row["policy"] == "bc_only"]
        print(f"| {graph} | {statistics.mean(r['mean_q_expert_minus_chosen'] for r in values):.5f} | "
              f"{statistics.mean(r['expert_action_agreement'] for r in values):.3f} | "
              f"{statistics.mean(r['fraction_lowest_latency_candidate'] for r in values):.3f} |",
              flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, default=CHECKPOINT)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--quick", action="store_true",
                        help="evaluate one validation graph and one seed for smoke testing")
    args = parser.parse_args()
    if not args.checkpoint.exists():
        parser.error(f"checkpoint not found: {args.checkpoint}")
    partitions = read_partitions(DATA / "splits.json")
    val_entries = [{**row, "split": "val"} for row in partitions["val"]]
    if any(row["name"] in {item["name"] for item in partitions["test"]}
           for row in val_entries):
        raise RuntimeError("validation/test graph overlap detected")
    if args.quick:
        val_entries = val_entries[:1]
        seeds = SEEDS[:1]
    else:
        seeds = SEEDS
    jobs = [(entry, scenario, seed, False)
            for entry in val_entries
            for scenario in ("normal", "link_failures")
            for seed in seeds]
    control_entries = [entry for entry in val_entries if entry["name"] in CONTROLS]
    control_jobs = [(entry, "normal", seed, True)
                    for entry in control_entries for seed in seeds]
    jobs.extend(control_jobs)
    all_rows: list[dict] = []
    worker_count = max(1, min(int(args.workers), (os.cpu_count() or 1) - 1, len(jobs)))
    print(f"BC evaluation jobs: {len(jobs)}; worker processes: {worker_count}; "
          "topology loads limited to validation graphs", flush=True)
    started = time.perf_counter()
    with ProcessPoolExecutor(max_workers=worker_count,
                             initializer=init_worker,
                             initargs=(str(args.checkpoint.resolve()),)) as pool:
        futures = {pool.submit(run_job, job): job for job in jobs}
        completed = 0
        for future in as_completed(futures):
            job_rows = future.result()
            all_rows.extend(job_rows)
            completed += 1
            entry, scenario, seed, control = futures[future]
            kind = "control" if control else "val"
            elapsed = time.perf_counter() - started
            eta = elapsed / max(1, completed) * (len(jobs) - completed) / 60.0
            print(f"done {completed} / {len(jobs)} jobs | {kind} {entry['name']} "
                  f"{scenario} seed={seed} | ETA {eta:.1f} min", flush=True)
    summary = aggregate(all_rows)
    OUT.mkdir(parents=True, exist_ok=True)
    write_rows(OUT / "bc_evaluation_episodes.csv", all_rows)
    write_rows(OUT / "bc_evaluation_summary.csv", summary)
    controls = [row for row in all_rows if row["run_type"] == "control"]
    write_rows(OUT / "bc_control_episodes.csv", controls)
    print_validation_table([row for row in summary
                            if row["run_type"] == "validation"])
    print_validation_action_diagnostics(all_rows)
    print_control_tables(controls)
    print(f"Evaluation elapsed: {(time.perf_counter() - started) / 60:.1f} min", flush=True)


def write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("\n", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as file:
        fields = list(dict.fromkeys(key for row in rows for key in row))
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
