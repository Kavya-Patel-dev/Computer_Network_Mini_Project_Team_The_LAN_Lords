"""Validation fallback comparison and one-shot, explicitly gated test evaluation."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from baselines import evaluation as day3
from baselines.policies import Decision, choose_decision
from env.topology import cyclomatic_number, path_diversity
from models.api import MODEL_PATH, MODEL_SHA256, _load_agent
from models.data_guard import read_partitions
from models.obs import ObservationWrapper
from models.safety_fallback import choose_with_fallback

DATA = ROOT / "data"
OUTPUT = ROOT / "outputs" / "day6_7_lite"
SCENARIOS = ("normal", "link_failures", "router_failure", "traffic_spike", "bandwidth_drop")
TEST_INTENSITIES = (0.05, 0.10, 0.20)
EVAL_SEEDS = tuple(range(1000, 1005))
ALL_BASELINES = ("random", "dijkstra_static", "ecmp", "greedy_min_util",
                 "dijkstra_load_aware_k", "dijkstra_load_aware", "rf_routing")
TEST_POLICIES = (*ALL_BASELINES, "ai_fallback")


class _AgentEvaluation:
    def __init__(self, *, fallback: bool, rf_model=None):
        self.fallback = fallback
        self.rf_model = rf_model
        self.agent = _load_agent()
        self.original_chooser = None
        self.original_config = None
        self.active_env = None
        self.wrapper = None
        self.reason_counts: dict[str, int] = {}
        self.steps = 0
        self.expert_matches = 0
        self.expert_count = 0
        self.nonfinite_q_count = 0

    def __enter__(self):
        self.original_chooser = day3.choose_decision
        self.original_config = day3.NetworkEnvConfig
        original = self.original_chooser
        history_length = 4

        def config_factory(**kwargs):
            return self.original_config(history_length=history_length, **kwargs)

        def chooser(policy, env, rng, alpha=1.0, rf_model=None,
                    time_since_last_failure=10_000):
            if policy not in {"ai_fallback", "ai_unwrapped"}:
                return original(policy, env, rng, alpha=alpha,
                                rf_model=self.rf_model if policy == "rf_routing" else rf_model,
                                time_since_last_failure=time_since_last_failure)
            if env is not self.active_env:
                self.active_env = env
                self.wrapper = ObservationWrapper(env, str(env.graph.graph.get("name", "eval")))
            state = self.wrapper.process(env._observation())
            checked = choose_with_fallback(self.agent, env, state, rng,
                                           enabled=self.fallback)
            self.nonfinite_q_count += int(not np.all(np.isfinite(
                checked.q_values[np.asarray(state.action_mask, dtype=bool)[:len(checked.q_values)]])))
            self.steps += 1
            self.reason_counts[checked.reason] = self.reason_counts.get(checked.reason, 0) + 1
            expert = original("dijkstra_load_aware_k", env, rng, alpha=4.0)
            expert_path = (tuple(expert.explicit_path) if expert.explicit_path is not None
                           else (tuple(env._paths.paths[expert.action])
                                 if expert.action < len(env._paths.paths) else None))
            self.expert_count += 1
            self.expert_matches += int(expert_path is not None
                                       and checked.chosen_path == expert_path)
            if checked.fallback_used:
                if checked.chosen_path is None:
                    return Decision(env.config.k_paths)
                return Decision(env.config.k_paths, explicit_path=checked.chosen_path)
            return Decision(checked.chosen_index if checked.chosen_index is not None
                            else env.config.k_paths)

        day3.NetworkEnvConfig = config_factory
        day3.choose_decision = chooser
        return self

    def __exit__(self, _exc_type, _exc, _tb):
        day3.choose_decision = self.original_chooser
        day3.NetworkEnvConfig = self.original_config
        self.active_env = None
        self.wrapper = None

    def details(self) -> dict[str, Any]:
        return {"reason_counts": dict(self.reason_counts),
                "agent_decisions": self.steps,
                "fallback_decisions": (sum(count for reason, count in self.reason_counts.items()
                                            if reason != "none") if self.fallback else 0),
                "expert_agreement_count": self.expert_matches,
                "expert_decision_count": self.expert_count,
                "nonfinite_valid_q_decisions": self.nonfinite_q_count,
                "expert_top1_agreement": (self.expert_matches / self.expert_count
                                           if self.expert_count else None)}


def _graph_for_validation(entry: dict, partitions: dict) -> Any:
    from train import safe_graph_load
    return safe_graph_load({**entry, "split": "val"}, "val", partitions)


def run_validation(output_dir: Path | None = None) -> dict[str, Any]:
    """Compare model-only and safety-wrapped policy on validation only."""
    partitions = read_partitions(DATA / "splits.json")
    entries = [dict(row, split="val") for row in partitions["val"]]
    if len(entries) != 5:
        raise RuntimeError(f"expected five validation graphs, found {len(entries)}")
    intensities = json.loads((DATA / "eval_intensity.json").read_text(encoding="utf-8"))
    out = output_dir or (OUTPUT / "validation_corrected_eta")
    out.mkdir(parents=True, exist_ok=False)
    progress_path = out / "progress.jsonl"
    progress_path.touch(exist_ok=False)
    rows = []
    total = len(entries) * len(EVAL_SEEDS) * len(SCENARIOS) * 2
    started = time.perf_counter()
    for entry in entries:
        graph = _graph_for_validation(entry, partitions)
        intensity = float(intensities[entry["name"]]["generators"]["poisson"]["intensity"])
        for scenario in SCENARIOS:
            for seed in EVAL_SEEDS:
                for fallback in (False, True):
                    with _AgentEvaluation(fallback=fallback) as adapter:
                        row = day3.run_episode(
                            entry, graph, "poisson", intensity,
                            "ai_fallback" if fallback else "ai_unwrapped",
                            seed, scenario, 4.0, max_steps=500, warmup=100,
                            data_root=DATA)
                        row.update(adapter.details())
                    row["fallback_enabled"] = fallback
                    rows.append(row)
                    with progress_path.open("a", encoding="utf-8") as handle:
                        handle.write(json.dumps(row, allow_nan=False) + "\n")
                    done = len(rows)
                    elapsed = time.perf_counter() - started
                    eta = (total - done) * elapsed / max(done, 1)
                    print(f"validation {done}/{total} graph={entry['name']} scenario={scenario} "
                          f"seed={seed} fallback={fallback} | elapsed {elapsed/60:.1f} min "
                          f"ETA {eta/60:.1f} min", flush=True)
    summary = _validation_summary(rows)
    summary["elapsed_seconds"] = time.perf_counter() - started
    _write_results(out, rows, summary)
    return summary


def _validation_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    per_scenario = []
    fallback_reasons = []
    for scenario in SCENARIOS:
        for enabled in (False, True):
            group = [r for r in rows if r["scenario"] == scenario
                     and r["fallback_enabled"] is enabled]
            mean_loss = float(np.mean([r["mean_packet_loss"] for r in group])) if group else math.nan
            per_scenario.append({"scenario": scenario, "fallback_enabled": enabled,
                                 "episodes": len(group), "mean_packet_loss": mean_loss})
        wrapped = [r for r in rows if r["scenario"] == scenario and r["fallback_enabled"]]
        counts: dict[str, int] = {}
        decisions = 0
        for row in wrapped:
            decisions += int(row["agent_decisions"])
            for reason, count in row["reason_counts"].items():
                counts[reason] = counts.get(reason, 0) + int(count)
        for reason in ("none", "invalid_action", "failed_path", "non_finite_q",
                       "no_valid_candidate", "overloaded_candidate"):
            count = counts.get(reason, 0)
            fallback_reasons.append({"scenario": scenario, "reason": reason,
                                     "decisions": count, "total_decisions": decisions,
                                     "rate": count / decisions if decisions else 0.0})
    worse = []
    for scenario in SCENARIOS:
        vals = {r["fallback_enabled"]: r["mean_packet_loss"]
                for r in per_scenario if r["scenario"] == scenario}
        relative = (vals[True] - vals[False]) / max(vals[False], 1e-12)
        if relative > 0.05:
            worse.append({"scenario": scenario, "relative_loss_increase": relative})
    return {"split": "val", "graphs": sorted({r["graph"] for r in rows}),
            "seeds": list(EVAL_SEEDS), "scenarios": list(SCENARIOS),
            "generator": "poisson at transferred per-graph intensity",
            "per_scenario_loss": per_scenario,
            "fallback_rate_by_reason": fallback_reasons,
            "scenarios_over_5_percent_worse": worse,
            "passes_loss_nonregression": not worse}


def _criteria_committed() -> str:
    status = subprocess.run(["git", "status", "--porcelain", "--", "docs/test_criteria.md"],
                            cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    if status:
        raise RuntimeError("docs/test_criteria.md has uncommitted changes")
    result = subprocess.run(["git", "log", "-1", "--format=%H %cI %s", "--",
                             "docs/test_criteria.md"], cwd=ROOT, check=True,
                            capture_output=True, text=True).stdout.strip()
    if not result:
        raise RuntimeError("pre-registered test criteria is not committed")
    return result


def _write_results(out: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(rows, indent=2, allow_nan=False), encoding="utf-8")
    (out / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
    if rows:
        # Policies may add policy-specific diagnostics (the AI fallback row has
        # reason counts and expert agreement fields). Keep the CSV rectangular
        # by taking the stable union of keys across every policy row.
        fieldnames = list(dict.fromkeys(key for row in rows for key in row))
        with (out / "results.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({key: (json.dumps(value) if isinstance(value, (dict, list)) else value)
                                 for key, value in row.items()})


def run_final_test(command: list[str]) -> dict[str, Any]:
    """The only test topology load path; called only with --allow-test-final."""
    criteria_commit = _criteria_committed()
    out = OUTPUT / "test_final"
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(f"refusing to overwrite existing one-time test output: {out}")
    out.mkdir(parents=True, exist_ok=True)
    marker = out / "test_run_started.json"
    digest = __import__("hashlib").sha256(MODEL_PATH.read_bytes()).hexdigest().upper()
    if digest != MODEL_SHA256:
        raise RuntimeError(f"frozen model SHA-256 mismatch before test access: {digest}")
    record = {"command": " ".join(command),
              "timestamp_utc": datetime.now(timezone.utc).isoformat(),
              "criteria_commit": criteria_commit,
              "model_sha256": digest,
              "status": "started"}
    try:
        fd = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise RuntimeError(f"one-time test evaluation already started; refusing rerun: {marker}") from exc
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2)

    # Import/read the locked partition only after the one-shot marker and
    # explicit CLI gate are both established.
    partitions = read_partitions(DATA / "splits.json")
    entries = [dict(row, split="test") for row in partitions["test"]]
    if len(entries) != 5:
        raise RuntimeError(f"expected five locked test graphs, found {len(entries)}")
    rf_path = OUTPUT / "rf_routing.joblib"
    source_rf = ROOT / "outputs" / "rf_routing.joblib"
    if source_rf.exists():
        rf_path.write_bytes(source_rf.read_bytes())
        import joblib
        rf_model = joblib.load(rf_path)
    else:
        raise FileNotFoundError(f"required frozen RF baseline artifact missing: {source_rf}")
    results: list[dict[str, Any]] = []
    graph_diagnostics = {}
    total_jobs = len(entries) * len(TEST_INTENSITIES) * len(SCENARIOS) * len(EVAL_SEEDS) * len(TEST_POLICIES)
    started = time.perf_counter()
    for entry in entries:
        # This intentionally bypasses the train/validation-only Day 4 guard,
        # solely in this explicit one-time test evaluation function.
        graph = day3.load_graph(entry, DATA)
        routers = [node for node, attrs in graph.nodes(data=True)
                   if attrs.get("type", "router") == "router"]
        backbone = graph.subgraph(routers)
        graph_diagnostics[entry["name"]] = {
            "nodes": len(routers), "edges": backbone.number_of_edges(),
            "bridges": len(list(__import__("networkx").bridges(backbone))),
            "cyclomatic_number": cyclomatic_number(graph),
            "path_diversity": path_diversity(graph),
        }
        for intensity in TEST_INTENSITIES:
            for scenario in SCENARIOS:
                for seed in EVAL_SEEDS:
                    for policy in TEST_POLICIES:
                        if policy == "ai_fallback":
                            with _AgentEvaluation(fallback=True, rf_model=rf_model) as adapter:
                                row = day3.run_episode(
                                    entry, graph, "poisson", intensity, "ai_fallback",
                                    seed, scenario, 4.0, rf_model=rf_model,
                                    max_steps=500, warmup=100, data_root=DATA)
                                row.update(adapter.details())
                        else:
                            row = day3.run_episode(
                                entry, graph, "poisson", intensity, policy,
                                seed, scenario, 4.0, rf_model=rf_model,
                                max_steps=500, warmup=100, data_root=DATA)
                        row["policy"] = policy
                        row["fallback_enabled"] = policy == "ai_fallback"
                        results.append(row)
                        done = len(results)
                        if done % 25 == 0 or done == total_jobs:
                            elapsed = time.perf_counter() - started
                            eta = (total_jobs - done) * elapsed / max(done, 1) / 60.0
                            print(f"test-eval {done}/{total_jobs} graph={entry['name']} "
                                  f"intensity={intensity:.2f} scenario={scenario} policy={policy} "
                                  f"seed={seed} | ETA {eta:.1f} min", flush=True)
                        # Keep durable partial evidence during the sole run.
                        if done % 25 == 0:
                            with (out / "progress.jsonl").open("a", encoding="utf-8") as f:
                                f.write(json.dumps(row, allow_nan=False) + "\n")
    summary = _test_summary(results, graph_diagnostics)
    summary.update({"split": "test", "seeds": list(EVAL_SEEDS),
                    "intensities": list(TEST_INTENSITIES), "scenarios": list(SCENARIOS),
                    "generator": "Poisson", "episode_count": len(results),
                    "elapsed_seconds": time.perf_counter() - started,
                    "command": " ".join(command), "timestamp_utc": record["timestamp_utc"],
                    "criteria_commit": criteria_commit,
                    "model_sha256": record["model_sha256"],
                    "graph_diagnostics": graph_diagnostics})
    _write_results(out, results, summary)
    record["status"] = "completed"
    record["elapsed_seconds"] = summary["elapsed_seconds"]
    marker.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return summary


RETRY_TEST_DIR = OUTPUT / "test_final_retry"
RETRY_PROTOCOL_VERSION = "same-criteria-recovery-v1"


def _test_job_plan(entries: list[dict[str, Any]]) -> list[tuple[dict[str, Any], float, str, int, str]]:
    """Return the exact registered test-evaluation order, without loading graphs."""
    return [(entry, intensity, scenario, seed, policy)
            for entry in entries
            for intensity in TEST_INTENSITIES
            for scenario in SCENARIOS
            for seed in EVAL_SEEDS
            for policy in TEST_POLICIES]


def _load_retry_journal(path: Path, jobs: list[tuple[dict[str, Any], float, str, int, str]]) -> list[dict[str, Any]]:
    """Load a complete, ordered result prefix for crash-safe exact resumption."""
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"retry journal has invalid JSON on line {line_no}") from exc
            rows.append(row)
    if len(rows) > len(jobs):
        raise RuntimeError("retry journal has more rows than the registered job plan")
    for index, row in enumerate(rows):
        entry, intensity, scenario, seed, policy = jobs[index]
        expected = (entry["name"], float(intensity), scenario, int(seed), policy)
        actual = (row.get("graph"), float(row.get("intensity", float("nan"))),
                  row.get("scenario"), int(row.get("seed", -1)), row.get("policy"))
        if actual != expected:
            raise RuntimeError(f"retry journal is not an exact job-plan prefix at row {index + 1}: "
                               f"expected {expected}, found {actual}")
    return rows


def _write_jsonl_durable(path: Path, row: dict[str, Any]) -> None:
    """Append one finished episode and flush it before another job starts."""
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, allow_nan=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def run_retry_test(command: list[str], output_dir: Path, *, resume: bool = False) -> dict[str, Any]:
    """Run the exact same registered test matrix in a separate, resumable output tree.

    This recovery path exists only because the original one-shot run was interrupted
    after 1,475 jobs and had no complete per-episode journal. It does not change any
    evaluation setting or acceptance criterion and never overwrites the original run.
    """
    out = output_dir.resolve()
    if out != RETRY_TEST_DIR.resolve():
        raise ValueError(f"recovery output must be exactly {RETRY_TEST_DIR}")
    criteria_commit = _criteria_committed()
    digest = __import__("hashlib").sha256(MODEL_PATH.read_bytes()).hexdigest().upper()
    if digest != MODEL_SHA256:
        raise RuntimeError(f"frozen model SHA-256 mismatch before test access: {digest}")

    marker = out / "test_run_started.json"
    protocol_path = out / "run_protocol.json"
    journal = out / "results.jsonl"
    progress_path = out / "progress.jsonl"
    diagnostics_path = out / "graph_diagnostics.json"
    expected_protocol = {
        "version": RETRY_PROTOCOL_VERSION,
        "reason": "Original test run was interrupted at 1475/3000 by laptop shutdown; user authorized a fresh same-settings run.",
        "retry_of": "outputs/day6_7_lite/test_final",
        "prior_durable_jobs": 1475,
        "criteria_commit": criteria_commit,
        "model_sha256": digest,
        "test_intensities": list(TEST_INTENSITIES),
        "scenarios": list(SCENARIOS),
        "seeds": list(EVAL_SEEDS),
        "policies": list(TEST_POLICIES),
        "max_steps": 500,
        "warmup": 100,
        "generator": "poisson",
        "traffic_scale": "unchanged",
    }
    if resume:
        if not out.is_dir() or not marker.is_file() or not protocol_path.is_file():
            raise FileNotFoundError("retry output or run metadata is missing; cannot resume")
        protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
        if protocol != expected_protocol:
            raise RuntimeError("retry protocol metadata differs from the registered run")
        record = json.loads(marker.read_text(encoding="utf-8"))
        if record.get("status") == "completed":
            raise RuntimeError("retry run is already complete; refusing to rerun")
        if record.get("model_sha256") != digest or record.get("criteria_commit") != criteria_commit:
            raise RuntimeError("retry checkpoint model or criteria commit does not match")
    else:
        if out.exists():
            raise FileExistsError(f"refusing to overwrite retry output: {out}")
        out.mkdir(parents=True, exist_ok=False)
        protocol_path.write_text(json.dumps(expected_protocol, indent=2), encoding="utf-8")
        record = {
            "command": " ".join(command),
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "criteria_commit": criteria_commit,
            "model_sha256": digest,
            "status": "started",
            "protocol": RETRY_PROTOCOL_VERSION,
            "completed_jobs": 0,
            "resume_count": 0,
        }
        fd = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(record, handle, indent=2)
        journal.touch(exist_ok=False)
        progress_path.touch(exist_ok=False)

    # Build and validate the ordered plan before graph loading. Test graph access
    # still occurs only after the explicit retry flag and durable marker exist.
    partitions = read_partitions(DATA / "splits.json")
    entries = [dict(row, split="test") for row in partitions["test"]]
    if len(entries) != 5:
        raise RuntimeError(f"expected five locked test graphs, found {len(entries)}")
    jobs = _test_job_plan(entries)
    results = _load_retry_journal(journal, jobs) if resume else []
    graph_diagnostics = (json.loads(diagnostics_path.read_text(encoding="utf-8"))
                         if resume and diagnostics_path.exists() else {})
    if not resume and journal.stat().st_size:
        raise RuntimeError("fresh retry journal must be empty")
    record["status"] = "running"
    record["completed_jobs"] = len(results)
    if resume:
        record["resume_count"] = int(record.get("resume_count", 0)) + 1
        record.setdefault("resume_timestamps_utc", []).append(datetime.now(timezone.utc).isoformat())
    marker.write_text(json.dumps(record, indent=2), encoding="utf-8")

    rf_path = out / "rf_routing.joblib"
    source_rf = ROOT / "outputs" / "rf_routing.joblib"
    if rf_path.exists():
        import joblib
        rf_model = joblib.load(rf_path)
    elif source_rf.exists():
        import joblib
        rf_path.write_bytes(source_rf.read_bytes())
        rf_model = joblib.load(rf_path)
    else:
        raise FileNotFoundError(f"required frozen RF baseline artifact missing: {source_rf}")

    graph_by_name: dict[str, Any] = {}
    start_index = len(results)
    started = time.perf_counter()
    total_jobs = len(jobs)
    try:
        for index in range(start_index, total_jobs):
            entry, intensity, scenario, seed, policy = jobs[index]
            graph = graph_by_name.get(entry["name"])
            if graph is None:
                # Sole explicit test-read location, after the retry run marker.
                graph = day3.load_graph(entry, DATA)
                graph_by_name[entry["name"]] = graph
                routers = [node for node, attrs in graph.nodes(data=True)
                           if attrs.get("type", "router") == "router"]
                backbone = graph.subgraph(routers)
                graph_diagnostics[entry["name"]] = {
                    "nodes": len(routers), "edges": backbone.number_of_edges(),
                    "bridges": len(list(__import__("networkx").bridges(backbone))),
                    "cyclomatic_number": cyclomatic_number(graph),
                    "path_diversity": path_diversity(graph),
                }
                diagnostics_path.write_text(json.dumps(graph_diagnostics, indent=2),
                                            encoding="utf-8")
            if policy == "ai_fallback":
                with _AgentEvaluation(fallback=True, rf_model=rf_model) as adapter:
                    row = day3.run_episode(
                        entry, graph, "poisson", intensity, "ai_fallback", seed,
                        scenario, 4.0, rf_model=rf_model, max_steps=500,
                        warmup=100, data_root=DATA)
                    row.update(adapter.details())
            else:
                row = day3.run_episode(
                    entry, graph, "poisson", intensity, policy, seed, scenario,
                    4.0, rf_model=rf_model, max_steps=500, warmup=100,
                    data_root=DATA)
            row["policy"] = policy
            row["fallback_enabled"] = policy == "ai_fallback"
            results.append(row)
            _write_jsonl_durable(journal, row)
            done = index + 1
            status_row = {"done": done, "total": total_jobs, "graph": entry["name"],
                          "intensity": intensity, "scenario": scenario,
                          "policy": policy, "seed": seed,
                          "elapsed_seconds_this_session": time.perf_counter() - started}
            _write_jsonl_durable(progress_path, status_row)
            record["completed_jobs"] = done
            record["status"] = "running"
            marker.write_text(json.dumps(record, indent=2), encoding="utf-8")
            if done % 25 == 0 or done == total_jobs:
                elapsed = time.perf_counter() - started
                eta = (total_jobs - done) * elapsed / max(done - start_index, 1) / 60.0
                print(f"test-eval {done}/{total_jobs} graph={entry['name']} "
                      f"intensity={intensity:.2f} scenario={scenario} policy={policy} "
                      f"seed={seed} | ETA {eta:.1f} min", flush=True)
    except KeyboardInterrupt:
        record["status"] = "interrupted"
        record["completed_jobs"] = len(results)
        record["interrupted_at_utc"] = datetime.now(timezone.utc).isoformat()
        marker.write_text(json.dumps(record, indent=2), encoding="utf-8")
        raise
    except Exception as exc:
        record["status"] = "failed"
        record["completed_jobs"] = len(results)
        record["failure"] = f"{type(exc).__name__}: {exc}"
        marker.write_text(json.dumps(record, indent=2), encoding="utf-8")
        raise

    summary = _test_summary(results, graph_diagnostics)
    summary.update({"split": "test", "seeds": list(EVAL_SEEDS),
                    "intensities": list(TEST_INTENSITIES), "scenarios": list(SCENARIOS),
                    "generator": "Poisson", "episode_count": len(results),
                    "elapsed_seconds_this_session": time.perf_counter() - started,
                    "command": " ".join(command), "timestamp_utc": record["timestamp_utc"],
                    "criteria_commit": criteria_commit,
                    "model_sha256": record["model_sha256"],
                    "graph_diagnostics": graph_diagnostics,
                    "recovery_protocol": RETRY_PROTOCOL_VERSION})
    _write_results(out, results, summary)
    record["status"] = "completed"
    record["completed_jobs"] = len(results)
    record["elapsed_seconds_this_session"] = summary["elapsed_seconds_this_session"]
    marker.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return summary


def _test_summary(rows: list[dict[str, Any]], graph_diagnostics: dict[str, Any]) -> dict[str, Any]:
    policy_map = {row["policy"]: row for row in rows}
    ai_rows = [r for r in rows if r["policy"] == "ai_fallback"]
    static_rows = [r for r in rows if r["policy"] == "dijkstra_static"]
    la_rows = [r for r in rows if r["policy"] == "dijkstra_load_aware"]
    t1 = []
    for intensity in TEST_INTENSITIES:
        ai = [r["mean_packet_loss"] for r in ai_rows
              if r["scenario"] == "normal" and r["intensity"] == intensity]
        static = [r["mean_packet_loss"] for r in static_rows
                  if r["scenario"] == "normal" and r["intensity"] == intensity]
        ai_mean, static_mean = float(np.mean(ai)), float(np.mean(static))
        applicable = static_mean > 0.005
        t1.append({"intensity": intensity, "ai_mean_loss": ai_mean,
                   "static_mean_loss": static_mean,
                   "threshold": 0.5 * static_mean if applicable else None,
                   "applicable": applicable,
                   "pass": ai_mean <= 0.5 * static_mean if applicable else None})
    t2 = []
    for scenario in SCENARIOS:
        for intensity in TEST_INTENSITIES:
            ai = float(np.mean([r["mean_packet_loss"] for r in ai_rows
                                if r["scenario"] == scenario and r["intensity"] == intensity]))
            la = float(np.mean([r["mean_packet_loss"] for r in la_rows
                                if r["scenario"] == scenario and r["intensity"] == intensity]))
            threshold = max(1.15 * la, la + 0.002)
            t2.append({"scenario": scenario, "intensity": intensity,
                       "ai_mean_loss": ai, "load_aware_mean_loss": la,
                       "threshold": threshold, "pass": ai <= threshold})
    t3_reasons = []
    for row in ai_rows:
        if row.get("invalid_actions_accepted", 0):
            t3_reasons.append(f"{row['graph']}/{row['scenario']}/{row['seed']}: invalid action")
        if row.get("nonfinite_valid_q_decisions", 0):
            t3_reasons.append(f"{row['graph']}/{row['scenario']}/{row['seed']}: nonfinite valid Q")
        for field, value in row.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                if not math.isfinite(float(value)):
                    t3_reasons.append(f"{row['graph']}/{row['scenario']}/{row['seed']}: nonfinite {field}")
    t3 = {"pass": not t3_reasons, "issues": t3_reasons[:50],
          "invalid_actions_accepted": sum(int(r.get("invalid_actions_accepted", 0)) for r in ai_rows)}
    per_graph = []
    for graph_name in sorted(graph_diagnostics):
        for scenario in SCENARIOS:
            for intensity in TEST_INTENSITIES:
                grouped = {policy: [r for r in rows if r["graph"] == graph_name
                                    and r["scenario"] == scenario and r["intensity"] == intensity
                                    and r["policy"] == policy]
                           for policy in TEST_POLICIES}
                ai_loss = float(np.mean([r["mean_packet_loss"] for r in grouped["ai_fallback"]]))
                comparisons = {}
                for policy in ALL_BASELINES:
                    vals = [r["mean_packet_loss"] for r in grouped[policy]]
                    mean_loss = float(np.mean(vals))
                    comparisons[policy] = {"mean_packet_loss": mean_loss,
                                           "ai_mean_packet_loss": ai_loss,
                                           "result": "win" if ai_loss < mean_loss else
                                           "tie" if ai_loss == mean_loss else "loss"}
                per_graph.append({"graph": graph_name, "scenario": scenario,
                                  "intensity": intensity, "ai_mean_packet_loss": ai_loss,
                                  "full_path_not_in_k": _full_path_not_in_k_report(
                                      grouped["dijkstra_load_aware"]),
                                  "baselines": comparisons})
    agreement_values = [r["expert_top1_agreement"] for r in ai_rows]
    agreement_num = sum(int(r.get("expert_agreement_count", 0)) for r in ai_rows)
    agreement_den = sum(int(r.get("expert_decision_count", 0)) for r in ai_rows)
    return {"T1": {"pass": all(row["pass"] is not False for row in t1), "rows": t1},
            "T2": {"pass": all(row["pass"] for row in t2), "rows": t2},
            "T3": t3,
            "T4": {"per_graph_scenario_intensity": per_graph},
            "T5": {"top1_agreement": agreement_num / agreement_den if agreement_den else None,
                   "matches": agreement_num, "decisions": agreement_den,
                   "per_episode_agreement_mean": float(np.mean(agreement_values))},
            "all_baseline_policy_counts": {policy: sum(1 for r in rows if r["policy"] == policy)
                                           for policy in TEST_POLICIES}}


def _full_path_not_in_k_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize candidate misses from the full-graph load-aware policy only.

    Other policies serialize a zero for this field when they do not measure it;
    using those rows would turn an unmeasured value into an apparent 0% rate.
    """
    measured = [row for row in rows if row.get("policy") == "dijkstra_load_aware"]
    denominator = sum(int(row.get("measured_steps", 0)) for row in measured)
    misses = sum(float(row.get("full_path_not_in_k_fraction", 0.0))
                 * int(row.get("measured_steps", 0)) for row in measured)
    return {
        "measured_by": "dijkstra_load_aware",
        "misses": misses,
        "decisions": denominator,
        "fraction": misses / denominator if denominator else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--validation-only", action="store_true")
    group.add_argument("--allow-test-final", action="store_true")
    group.add_argument("--allow-test-retry", action="store_true",
                       help="authorized fresh same-settings recovery run in a new output directory")
    group.add_argument("--resume-test-retry", action="store_true",
                       help="resume the authorized recovery run from its per-episode journal")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if args.validation_only:
        print(json.dumps(run_validation(args.output_dir), indent=2))
    elif args.allow_test_retry or args.resume_test_retry:
        if args.output_dir is None:
            parser.error("retry mode requires --output-dir")
        try:
            summary = run_retry_test(sys.argv, args.output_dir,
                                     resume=args.resume_test_retry)
        except KeyboardInterrupt:
            print("retry evaluation interrupted safely; use --resume-test-retry with the same output directory",
                  flush=True)
            raise SystemExit(130)
        print(json.dumps(summary, indent=2))
    else:
        try:
            summary = run_final_test(sys.argv)
        except Exception as exc:
            marker = OUTPUT / "test_final" / "test_run_started.json"
            if marker.exists():
                record = json.loads(marker.read_text(encoding="utf-8"))
                record["status"] = "failed"
                record["failure"] = f"{type(exc).__name__}: {exc}"
                marker.write_text(json.dumps(record, indent=2), encoding="utf-8")
            raise
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
