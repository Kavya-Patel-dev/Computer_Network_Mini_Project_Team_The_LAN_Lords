"""Readiness rules for the Day 5.5–5.6 final study.

This module only describes and validates the study.  Importing it never loads
topology files or starts training.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import statistics
from typing import Any, Iterable

import numpy as np


SEEDS = (20_101, 20_102, 20_103)
SELECTION_SEEDS = (30_000, 30_001)
EVALUATION_SEEDS = (1_000, 1_001, 1_002, 1_003, 1_004)
MAIN_STEPS = 12_967
GRU_STEPS = 11_515
MAX_WORKERS = 12
CONTROLS = ("Arpanet19728", "Compuserve", "EliBackbone")


def _flags(*, dueling: bool = False, noisy: bool = False,
           gru: bool = False, mlp: bool = False,
           auxiliary: bool = False) -> dict[str, Any]:
    return {
        "dueling": dueling,
        "noisy_net": noisy,
        "gru_history": gru,
        "mlp_encoder": mlp,
        "auxiliary_utilization": auxiliary,
        "noisy_sigma0": 0.1,
        "compact_history": gru,
    }


def _job(variant: str, seed: int, *, flags: dict[str, Any], n_step: int,
         prioritized: bool, load_bc: bool = True,
         auxiliary_bc_weight: float = 0.1) -> dict[str, Any]:
    is_gru = variant == "L6_GRU_T2"
    return {
        "run_id": f"{variant}_seed{seed}",
        "variant": variant,
        "seed": seed,
        "steps": GRU_STEPS if is_gru else MAIN_STEPS,
        "history_length": 2 if is_gru else 4,
        "flags": dict(flags),
        "n_step": n_step,
        "prioritized_replay": prioritized,
        "load_bc": load_bc,
        "auxiliary_bc_weight": auxiliary_bc_weight if load_bc else 0.0,
        "replay_capacity": 25_000,
        "batch_size": 64,
        "learning_starts": 2_000,
        "update_every": 4,
    }


def build_manifest() -> dict[str, Any]:
    """Build the exact 36-run paired-seed manifest and its -Aux reuse alias."""
    specs = {
        "L0": (_flags(), 1, False, True, 0.1),
        "L1": (_flags(dueling=True), 1, False, True, 0.1),
        "L2": (_flags(dueling=True), 3, False, True, 0.1),
        "L3": (_flags(dueling=True), 3, True, True, 0.1),
        "L4": (_flags(dueling=True, noisy=True), 3, True, True, 0.1),
        "FULL": (_flags(dueling=True, noisy=True, auxiliary=True),
                 3, True, True, 0.1),
        "ABL_no_dueling": (_flags(noisy=True, auxiliary=True),
                           3, True, True, 0.1),
        "ABL_no_per_nstep": (_flags(dueling=True, noisy=True, auxiliary=True),
                             1, False, True, 0.1),
        "ABL_mlp": (_flags(dueling=True, noisy=True, mlp=True, auxiliary=True),
                    3, True, True, 0.1),
        "ABL_no_imitation": (_flags(dueling=True, noisy=True, auxiliary=True),
                             3, True, False, 0.0),
        "ABL_no_noisy": (_flags(dueling=True, auxiliary=True),
                         3, True, True, 0.1),
        "L6_GRU_T2": (_flags(dueling=True, noisy=True, gru=True, auxiliary=True),
                      3, True, True, 0.1),
    }
    jobs = []
    # Ladder includes L0..L4 plus FULL (the user's L5 label).
    for variant in ("L0", "L1", "L2", "L3", "L4", "FULL"):
        flags, n_step, prioritized, load_bc, bc_weight = specs[variant]
        for seed in SEEDS:
            jobs.append(_job(variant, seed, flags=flags, n_step=n_step,
                             prioritized=prioritized, load_bc=load_bc,
                             auxiliary_bc_weight=bc_weight))
    # Five non-Aux ablations.  -Aux is explicitly an alias for the L4 runs.
    for variant in ("ABL_no_dueling", "ABL_no_per_nstep", "ABL_mlp",
                    "ABL_no_imitation", "ABL_no_noisy", "L6_GRU_T2"):
        flags, n_step, prioritized, load_bc, bc_weight = specs[variant]
        for seed in SEEDS:
            jobs.append(_job(variant, seed, flags=flags, n_step=n_step,
                             prioritized=prioritized, load_bc=load_bc,
                             auxiliary_bc_weight=bc_weight))
    manifest = {
        "schema_version": 1,
        "design": "Day 5.5-5.6; paired three-seed; final study not launched",
        "main_steps": MAIN_STEPS,
        "gru_steps": GRU_STEPS,
        "selection_seeds": list(SELECTION_SEEDS),
        "evaluation_seeds": list(EVALUATION_SEEDS),
        "training_seeds": list(SEEDS),
        "jobs": jobs,
        "labels": {"L5": "FULL"},
        "reuse": {"ABL_no_aux": {"variant": "L4", "run_ids": [
            f"L4_seed{seed}" for seed in SEEDS]}},
        "stages": {
            "safety": [f"FULL_seed{seed}" for seed in SEEDS],
            "ladder_and_gru": [
                job["run_id"] for job in jobs
                if job["variant"] in {"L0", "L1", "L2", "L3", "L4", "L6_GRU_T2"}
            ],
            "ablations": [
                job["run_id"] for job in jobs
                if job["variant"].startswith("ABL_")
            ],
        },
        "safety_gates": {
            "all_losses_and_q_finite": True,
            "max_huber_over_median_below": 100.0,
            "q_abs_p999_below": 60.0,
            "q_abs_max_below": 100.0,
            "validation_trend_last_evaluations": 3,
            "validation_trend_must_not_increase": True,
        },
    }
    validate_manifest(manifest)
    return manifest


def canonical_signature(job: dict[str, Any]) -> str:
    keys = ("run_id", "variant", "seed", "steps", "history_length", "flags",
            "n_step", "prioritized_replay", "load_bc", "auxiliary_bc_weight",
            "replay_capacity", "batch_size", "learning_starts", "update_every")
    payload = json.dumps({key: job[key] for key in keys}, sort_keys=True,
                         separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("main_steps") != MAIN_STEPS or manifest.get("gru_steps") != GRU_STEPS:
        raise ValueError("preflight-derived non-GRU/GRU budgets changed")
    jobs = manifest.get("jobs", [])
    if len(jobs) != 36:
        raise ValueError(f"manifest must contain 36 jobs, got {len(jobs)}")
    ids = [job.get("run_id") for job in jobs]
    if len(set(ids)) != 36 or any(not run_id for run_id in ids):
        raise ValueError("run IDs must be present and unique")
    expected = {
        "L0": 3, "L1": 3, "L2": 3, "L3": 3, "L4": 3, "FULL": 3,
        "ABL_no_dueling": 3, "ABL_no_per_nstep": 3, "ABL_mlp": 3,
        "ABL_no_imitation": 3, "ABL_no_noisy": 3, "L6_GRU_T2": 3,
    }
    counts: dict[str, int] = {}
    combos = set()
    expected_configs = {
        "L0": (_flags(), 1, False, True, 0.1),
        "L1": (_flags(dueling=True), 1, False, True, 0.1),
        "L2": (_flags(dueling=True), 3, False, True, 0.1),
        "L3": (_flags(dueling=True), 3, True, True, 0.1),
        "L4": (_flags(dueling=True, noisy=True), 3, True, True, 0.1),
        "FULL": (_flags(dueling=True, noisy=True, auxiliary=True),
                 3, True, True, 0.1),
        "ABL_no_dueling": (_flags(noisy=True, auxiliary=True),
                           3, True, True, 0.1),
        "ABL_no_per_nstep": (_flags(dueling=True, noisy=True, auxiliary=True),
                             1, False, True, 0.1),
        "ABL_mlp": (_flags(dueling=True, noisy=True, mlp=True, auxiliary=True),
                    3, True, True, 0.1),
        "ABL_no_imitation": (_flags(dueling=True, noisy=True, auxiliary=True),
                             3, True, False, 0.0),
        "ABL_no_noisy": (_flags(dueling=True, auxiliary=True),
                         3, True, True, 0.1),
        "L6_GRU_T2": (_flags(dueling=True, noisy=True, gru=True, auxiliary=True),
                      3, True, True, 0.1),
    }
    for job in jobs:
        variant = job["variant"]
        if variant not in expected_configs:
            raise ValueError(f"unknown study variant: {variant}")
        if job.get("run_id") != f"{variant}_seed{job.get('seed')}":
            raise ValueError(f"run ID does not encode variant and seed: {job.get('run_id')}")
        counts[variant] = counts.get(variant, 0) + 1
        if int(job["seed"]) not in SEEDS:
            raise ValueError(f"unexpected training seed {job['seed']}")
        if int(job["seed"]) < 20_000:
            raise ValueError("training seed must be >= 20000")
        if bool(job["flags"].get("gru_history")) != (variant == "L6_GRU_T2"):
            raise ValueError(f"GRU flag mismatch in {job['run_id']}")
        expected_flags, expected_n_step, expected_per, expected_bc, expected_bc_weight = expected_configs[variant]
        if job["flags"] != expected_flags:
            raise ValueError(f"unexpected configuration flags in {job['run_id']}")
        if (job["n_step"] != expected_n_step
                or job["prioritized_replay"] is not expected_per
                or job["load_bc"] is not expected_bc
                or job["auxiliary_bc_weight"] != expected_bc_weight):
            raise ValueError(f"unexpected algorithm configuration in {job['run_id']}")
        if job["history_length"] != (2 if variant == "L6_GRU_T2" else 4):
            raise ValueError(f"history length mismatch in {job['run_id']}")
        if job["steps"] != (GRU_STEPS if variant == "L6_GRU_T2" else MAIN_STEPS):
            raise ValueError(f"step budget mismatch in {job['run_id']}")
        if job["replay_capacity"] != 25_000:
            raise ValueError("replay capacity must remain 25000")
        if job["load_bc"] and job["auxiliary_bc_weight"] != 0.1:
            raise ValueError(f"BC weight mismatch in {job['run_id']}")
        if not job["load_bc"] and job["auxiliary_bc_weight"] != 0.0:
            raise ValueError(f"random-init ablation has BC loss in {job['run_id']}")
        config = {key: value for key, value in job.items()
                  if key not in {"run_id", "variant", "seed"}}
        combination = (job["seed"], json.dumps(config, sort_keys=True,
                                               separators=(",", ":")))
        if combination in combos:
            raise ValueError(f"duplicate run configuration: {job['run_id']}")
        combos.add(combination)
    if counts != expected:
        raise ValueError(f"configuration coverage mismatch: {counts}")
    reuse = manifest.get("reuse", {}).get("ABL_no_aux", {})
    if manifest.get("labels", {}).get("L5") != "FULL":
        raise ValueError("the ladder label L5 must point to FULL")
    if reuse.get("variant") != "L4" or reuse.get("run_ids") != [
            f"L4_seed{seed}" for seed in SEEDS]:
        raise ValueError("-Aux must reuse the three L4 jobs")
    if tuple(manifest.get("selection_seeds", ())) != SELECTION_SEEDS:
        raise ValueError("checkpoint selection must use seeds 30000 and 30001")
    if set(manifest.get("selection_seeds", ())) & set(EVALUATION_SEEDS):
        raise ValueError("evaluation seeds cannot be used for selection")
    if set(manifest.get("evaluation_seeds", ())) != set(EVALUATION_SEEDS):
        raise ValueError("evaluation seed list changed")
    if len(manifest["stages"]["safety"]) != 3:
        raise ValueError("the first safety stage must be exactly three FULL runs")
    expected_safety = [f"FULL_seed{seed}" for seed in SEEDS]
    expected_ladder = {f"{variant}_seed{seed}"
                       for variant in ("L0", "L1", "L2", "L3", "L4", "L6_GRU_T2")
                       for seed in SEEDS}
    expected_ablations = {f"{variant}_seed{seed}"
                          for variant in ("ABL_no_dueling", "ABL_no_per_nstep",
                                          "ABL_mlp", "ABL_no_imitation", "ABL_no_noisy")
                          for seed in SEEDS}
    if manifest["stages"]["safety"] != expected_safety:
        raise ValueError("safety stage must be the three FULL seed jobs in seed order")
    if set(manifest["stages"]["ladder_and_gru"]) != expected_ladder:
        raise ValueError("ladder/GRU stage has incorrect run coverage")
    if set(manifest["stages"]["ablations"]) != expected_ablations:
        raise ValueError("ablation stage has incorrect run coverage")
    all_ids = set(ids)
    stage_ids = [*manifest["stages"]["safety"],
                 *manifest["stages"]["ladder_and_gru"],
                 *manifest["stages"]["ablations"]]
    if len(stage_ids) != len(set(stage_ids)) or set(stage_ids) != all_ids:
        raise ValueError("stages must partition all 36 run IDs exactly once")
    if set(manifest.get("training_seeds", ())) != set(SEEDS):
        raise ValueError("manifest training seed roster changed")


def checkpoint_steps(total_steps: int, *, extra_steps: Iterable[int] = ()) -> list[int]:
    """Step zero plus six evenly spaced checkpoints and explicitly requested steps."""
    total_steps = int(total_steps)
    if total_steps <= 0:
        raise ValueError("step budget must be positive")
    points = {0, total_steps}
    points.update(math.ceil(total_steps * k / 6) for k in range(1, 7))
    points.update(int(step) for step in extra_steps)
    if any(step < 0 or step > total_steps for step in points):
        raise ValueError("extra checkpoint lies outside the run")
    return sorted(points)


def selection_entries(partitions: dict[str, list[dict[str, Any]]]) -> tuple[list[dict], list[dict]]:
    """Return the complete validation set and three val-only control rows."""
    val = [dict(row, split="val") for row in partitions["val"]]
    by_name = {row["name"]: row for row in val}
    missing = set(CONTROLS) - set(by_name)
    if missing:
        raise ValueError(f"required controls are not validation graphs: {sorted(missing)}")
    return val, [by_name[name] for name in CONTROLS]


def load_validation_graphs(partitions: dict[str, list[dict[str, Any]]], loader):
    """Load only guarded validation entries using the caller's safe loader."""
    entries, _controls = selection_entries(partitions)
    return {entry["name"]: loader(entry, "val", partitions) for entry in entries}


@dataclass(frozen=True)
class SelectionState:
    best_loss: float = math.inf
    best_step: int | None = None

    def consider(self, step: int, mean_validation_loss: float) -> "SelectionState":
        value = float(mean_validation_loss)
        if not math.isfinite(value):
            raise ValueError("selection loss must be finite")
        if value < self.best_loss:
            return SelectionState(value, int(step))
        return self


def effective_workers(requested: int, job_count: int) -> int:
    if int(requested) <= 0 or int(job_count) <= 0:
        raise ValueError("worker count and job count must be positive")
    return min(MAX_WORKERS, int(requested), int(job_count))


def safety_stage_allows_next(passed: bool) -> bool:
    """The orchestrator may queue later stages only after the FULL gate passes."""
    return bool(passed)


def control_passes(agent_loss: float, agent_median_latency_ms: float,
                   static_loss: float, static_median_latency_ms: float) -> bool:
    """Day 4 low-load control: loss no worse and median latency within 10%."""
    values = (agent_loss, agent_median_latency_ms,
              static_loss, static_median_latency_ms)
    if any(not math.isfinite(float(value)) for value in values):
        return False
    return (agent_loss <= static_loss + 1e-12
            and agent_median_latency_ms <= static_median_latency_ms * 1.10 + 1e-12)


def format_progress(run_id: str, step: int, total: int, val_loss: float,
                    eta_minutes: float, selection_status: str) -> str:
    if not math.isfinite(float(val_loss)):
        raise ValueError("progress requires a real finite validation loss")
    return (f"{run_id} | step {step} / {total} | val loss {val_loss:.6f} | "
            f"ETA {eta_minutes:.2f} min | selection={selection_status}")


def full_safety_gate(summaries: list[dict[str, Any]]) -> tuple[bool, list[dict[str, Any]]]:
    """Apply the documented K2 gate to exactly the three FULL safety jobs."""
    expected_ids = {f"FULL_seed{seed}" for seed in SEEDS}
    by_id = {row.get("run_id"): row for row in summaries}
    if set(by_id) != expected_ids:
        return False, [{"gate": "three_full_runs", "pass": False,
                        "evidence": f"expected {sorted(expected_ids)}, got {sorted(by_id)}"}]
    reports = []
    for run_id in sorted(expected_ids):
        row = by_id[run_id]
        losses = [float(value) for value in row.get("loss_trace", [])]
        q_values = [float(value) for value in row.get("q_abs_trace", [])]
        validation = [float(item["mean_loss"]) for item in row.get("validation_history", [])]
        finite = (bool(losses) and bool(q_values) and bool(validation)
                  and all(math.isfinite(value) for value in losses + q_values + validation))
        median_loss = statistics.median(losses) if losses else math.nan
        loss_ratio = max(losses) / median_loss if losses and median_loss > 0 else math.inf
        q_p999 = float(np.percentile(q_values, 99.9)) if q_values else math.inf
        q_max = max(q_values, default=math.inf)
        tail = validation[-3:]
        trend_ok = False
        if len(tail) == 3:
            # A nonpositive least-squares slope across the three latest scores.
            mean_x = 1.0
            mean_y = sum(tail) / 3
            slope = sum((index - mean_x) * (value - mean_y)
                        for index, value in enumerate(tail)) / 2.0
            trend_ok = slope <= 1e-12
        checks = {
            "finite_losses_q_and_validation": finite,
            "max_huber_over_median_below_100": loss_ratio < 100.0,
            "q_abs_p999_below_60": q_p999 < 60.0,
            "q_abs_max_below_100": q_max < 100.0,
            "validation_last_three_nonincreasing_trend": trend_ok,
        }
        reports.append({"run_id": run_id, "pass": all(checks.values()),
                        "checks": checks, "loss_ratio": loss_ratio,
                        "q_abs_p999": q_p999, "q_abs_max": q_max,
                        "last_validation_losses": tail})
    return all(row["pass"] for row in reports), reports


def full_run_safety_check(row: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """Evaluate the same numerical FULL gates for one smoke summary."""
    losses = [float(value) for value in row.get("loss_trace", [])]
    q_values = [float(value) for value in row.get("q_abs_trace", [])]
    validation = [float(item["mean_loss"]) for item in row.get("validation_history", [])]
    finite = (bool(losses) and bool(q_values) and bool(validation)
              and all(math.isfinite(value) for value in losses + q_values + validation))
    median_loss = statistics.median(losses) if losses else math.nan
    loss_ratio = max(losses) / median_loss if losses and median_loss > 0 else math.inf
    q_p999 = float(np.percentile(q_values, 99.9)) if q_values else math.inf
    q_max = max(q_values, default=math.inf)
    tail = validation[-3:]
    trend_ok = False
    if len(tail) == 3:
        mean_y = sum(tail) / 3
        slope = sum((index - 1) * (value - mean_y)
                    for index, value in enumerate(tail)) / 2.0
        trend_ok = slope <= 1e-12
    checks = {
        "finite_losses_q_and_validation": finite,
        "max_huber_over_median_below_100": loss_ratio < 100.0,
        "q_abs_p999_below_60": q_p999 < 60.0,
        "q_abs_max_below_100": q_max < 100.0,
        "validation_last_three_nonincreasing_trend": trend_ok,
    }
    report = {"run_id": row.get("run_id"), "pass": all(checks.values()),
              "checks": checks, "loss_ratio": loss_ratio,
              "q_abs_p999": q_p999, "q_abs_max": q_max,
              "last_validation_losses": tail}
    return bool(report["pass"]), report


def resolve_attempt_dir(root: Path, run_id: str, signature: str) -> tuple[Path, bool]:
    """Reuse a valid completed attempt; otherwise choose a new, empty attempt.

    Existing partial and mismatched directories are preserved.  A restarted
    partial job starts from its seed in a new attempt; it never overwrites a
    checkpoint or counts as an additional completed manifest run.
    """
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    candidates = sorted(root.glob(f"{run_id}*"))
    completed = []
    for directory in candidates:
        summary = directory / "output" / "summary.json"
        if summary.exists():
            row = json.loads(summary.read_text(encoding="utf-8"))
            if row.get("signature") == signature and row.get("completed") is True:
                completed.append(directory)
            else:
                raise FileExistsError(f"existing completed attempt conflicts: {directory}")
    if len(completed) > 1:
        raise FileExistsError(f"duplicate completed attempts for {run_id}")
    if completed:
        return completed[0], True
    if not candidates:
        return root / run_id, False
    attempt = 2
    while True:
        candidate = root / f"{run_id}.attempt{attempt:02d}"
        if not candidate.exists():
            return candidate, False
        attempt += 1
