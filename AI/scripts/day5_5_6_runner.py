"""Staged, resumable Day 5.5–5.6 runner. Final execution needs explicit approval."""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from models.day5_study import (GRU_STEPS, MAX_WORKERS, build_manifest,
                               canonical_signature, effective_workers,
                               full_safety_gate, resolve_attempt_dir,
                               validate_manifest)

DEFAULT_MANIFEST = ROOT / "configs" / "day5_5_6_manifest.json"
DEFAULT_ROOT = ROOT / "outputs" / "day5_5_6" / "runs"
CONTROL_DIR = ROOT / "outputs" / "day5_5_6"


def load_manifest(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_manifest(manifest)
    return manifest


def completed_summary(root: Path, job: dict[str, Any]) -> dict[str, Any] | None:
    folder, completed = resolve_attempt_dir(
        root, job["run_id"], canonical_signature(job))
    if not completed:
        return None
    return json.loads((folder / "output" / "summary.json").read_text(encoding="utf-8"))


def _launch_one(job: dict[str, Any], root: Path, worker: Path):
    signature = canonical_signature(job)
    folder, already_done = resolve_attempt_dir(root, job["run_id"], signature)
    if already_done:
        return None
    folder.mkdir(parents=True, exist_ok=False)
    run_dir = folder / "checkpoint"
    output_dir = folder / "output"
    run_dir.mkdir()
    output_dir.mkdir()
    spec = {**job, "signature": signature,
            "run_dir": str(run_dir), "output_dir": str(output_dir),
            "gru_comparison_step": GRU_STEPS}
    spec_path = output_dir / "job_spec.json"
    spec_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    log_path = output_dir / "run.log"
    log_handle = log_path.open("x", encoding="utf-8")
    environment = os.environ.copy()
    environment.update({"OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
                        "OPENBLAS_NUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1"})
    command = [sys.executable, str(worker), "--spec", str(spec_path)]
    process = subprocess.Popen(command, cwd=ROOT, env=environment,
                               stdout=log_handle, stderr=subprocess.STDOUT)
    return {"process": process, "job": job, "folder": folder,
            "output_dir": output_dir, "log_path": log_path,
            "log_handle": log_handle, "offset": 0,
            "started": time.perf_counter(), "signature": signature,
            "peak_rss_bytes": 0, "step_progress": "not started"}


def _process_tree_rss(pid: int) -> int:
    import psutil
    try:
        process = psutil.Process(pid)
        return sum(proc.memory_info().rss for proc in [process, *process.children(recursive=True)]
                   if proc.is_running())
    except (psutil.Error, OSError, ProcessLookupError):
        return 0


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
    temporary.replace(path)


def _stage_jobs(manifest: dict[str, Any]) -> list[tuple[str, list[dict[str, Any]]]]:
    by_id = {job["run_id"]: job for job in manifest["jobs"]}
    stages = manifest["stages"]
    return [
        ("FULL safety stage", [by_id[item] for item in stages["safety"]]),
        ("ladder and GRU", [by_id[item] for item in stages["ladder_and_gru"]]),
        ("ablations", [by_id[item] for item in stages["ablations"]]),
    ]


def run_stage(jobs: list[dict[str, Any]], *, stage_name: str, root: Path,
              max_workers: int, completed_ids: set[str], total: int,
              completed_elapsed: list[float], worker: Path,
              state_path: Path | None = None) -> bool:
    pending = list(jobs)
    running: list[dict[str, Any]] = []
    worker_limit = effective_workers(max_workers, max(1, len(pending)))
    failure_seen = False
    print(f"stage={stage_name}; queued={len(pending)}; worker_limit={worker_limit}",
          flush=True)

    def save_state():
        if state_path is None:
            return
        active = []
        for item in running:
            active.append({"run_id": item["job"]["run_id"],
                           "step_progress": item["step_progress"],
                           "peak_rss_bytes": item["peak_rss_bytes"],
                           "log": str(item["log_path"])})
        remaining = max(0, total - len(completed_ids))
        if completed_elapsed:
            average = statistics.mean(completed_elapsed)
        elif running:
            average = statistics.mean(max(0.0, time.perf_counter() - item["started"])
                                      for item in running)
        else:
            average = 0.0
        eta_seconds = average * ((remaining + worker_limit - 1) // worker_limit)
        _atomic_json(state_path, {
            "stage": stage_name, "completed": len(completed_ids), "total": total,
            "active": active, "pending": [job["run_id"] for job in pending],
            "eta_minutes": round(eta_seconds / 60.0, 2),
            "updated_at": time.time(),
        })

    while pending or running:
        while pending and len(running) < worker_limit and not failure_seen:
            job = pending.pop(0)
            summary = completed_summary(root, job)
            if summary is not None:
                completed_ids.add(job["run_id"])
                if summary.get("elapsed_seconds"):
                    completed_elapsed.append(float(summary["elapsed_seconds"]))
                print(f"skip completed {job['run_id']} (matching signature)", flush=True)
                remaining = total - len(completed_ids)
                average = statistics.mean(completed_elapsed) if completed_elapsed else 0.0
                eta = average * ((remaining + worker_limit - 1) // worker_limit)
                print(f"runs done {len(completed_ids)} / {total} | stage {stage_name} | "
                      f"workers busy {len(running)}/{worker_limit} | ETA {eta / 60:.2f} min | "
                      f"selection=restored from completed summary", flush=True)
                continue
            state = _launch_one(job, root, worker)
            if state is None:
                completed_ids.add(job["run_id"])
                continue
            running.append(state)
            print(f"started {job['run_id']} stage={stage_name}; "
                  f"workers={len(running)}/{worker_limit}", flush=True)
            save_state()
        time.sleep(0.25)
        for state in list(running):
            state["peak_rss_bytes"] = max(
                state["peak_rss_bytes"], _process_tree_rss(state["process"].pid))
            try:
                with state["log_path"].open("r", encoding="utf-8") as handle:
                    handle.seek(state["offset"])
                    text = handle.read()
                    state["offset"] = handle.tell()
                for line in text.splitlines():
                    print(f"[{state['job']['run_id']}] {line}", flush=True)
                    match = re.search(r"step\s+(\d+)\s*/\s*(\d+)", line)
                    if match:
                        state["step_progress"] = f"{match.group(1)} / {match.group(2)}"
                save_state()
            except (FileNotFoundError, PermissionError):
                pass
            code = state["process"].poll()
            if code is None:
                continue
            state["log_handle"].close()
            elapsed = time.perf_counter() - state["started"]
            completed_elapsed.append(elapsed)
            if code == 0:
                summary_path = state["output_dir"] / "summary.json"
                if not summary_path.exists():
                    code = 91
                else:
                    summary = json.loads(summary_path.read_text(encoding="utf-8"))
                    if (summary.get("run_id") != state["job"]["run_id"]
                            or summary.get("signature") != state["signature"]
                            or summary.get("completed") is not True):
                        code = 92
                    else:
                        completed_ids.add(state["job"]["run_id"])
                        summary["runner_peak_rss_bytes"] = state["peak_rss_bytes"]
                        _atomic_json(summary_path, summary)
                        print(f"finished {state['job']['run_id']} in {elapsed:.1f}s; "
                              f"selected step={summary.get('selected_step')}; "
                              f"val={summary.get('best_validation_loss')}; "
                              f"peak process-tree RSS={state['peak_rss_bytes'] / (1024**2):.1f} MiB",
                              flush=True)
            if code:
                failure_seen = True
                print(f"FAILED run={state['job']['run_id']} stage={stage_name} "
                      f"exit={code}; evidence={state['log_path']}", flush=True)
            running.remove(state)
            remaining = total - len(completed_ids)
            average = statistics.mean(completed_elapsed) if completed_elapsed else 0.0
            eta = average * ((remaining + worker_limit - 1) // worker_limit)
            print(f"runs done {len(completed_ids)} / {total} | stage {stage_name} | "
                  f"workers busy {len(running)}/{worker_limit} | ETA {eta / 60:.2f} min | "
                  f"selection={'recorded per completed run' if code == 0 else 'failed run stopped'}",
                  flush=True)
            save_state()
        if failure_seen:
            # Do not schedule more. Any workers already running in this stage
            # are allowed to finish and their artifacts remain intact.
            pending.clear()
    return not failure_seen


def execute(manifest: dict[str, Any], *, root: Path = DEFAULT_ROOT,
            max_workers: int = MAX_WORKERS) -> int:
    validate_manifest(manifest)
    root.mkdir(parents=True, exist_ok=True)
    worker = ROOT / "scripts" / "day5_5_6_worker.py"
    completed_ids: set[str] = set()
    elapsed: list[float] = []
    total = len(manifest["jobs"])
    safety_summaries = []
    (CONTROL_DIR / "runner.pid").parent.mkdir(parents=True, exist_ok=True)
    (CONTROL_DIR / "runner.pid").write_text(str(os.getpid()), encoding="utf-8")
    _atomic_json(CONTROL_DIR / "runner_state.json", {
        "stage": "starting", "completed": 0, "total": total, "active": [],
        "pending": [job["run_id"] for job in manifest["jobs"]], "updated_at": time.time(),
    })

    for index, (stage_name, jobs) in enumerate(_stage_jobs(manifest)):
        ok = run_stage(jobs, stage_name=stage_name, root=root,
                       max_workers=max_workers, completed_ids=completed_ids,
                       total=total, completed_elapsed=elapsed, worker=worker,
                       state_path=CONTROL_DIR / "runner_state.json")
        if not ok:
            print(f"STOP: a worker failed during {stage_name}; later stages not scheduled.",
                  flush=True)
            return 1
        if index == 0:
            for job in jobs:
                summary = completed_summary(root, job)
                if summary is None:
                    print(f"STOP: FULL safety run missing: {job['run_id']}", flush=True)
                    return 1
                safety_summaries.append(summary)
            passed, report = full_safety_gate(safety_summaries)
            (root / "full_safety_gate.json").write_text(
                json.dumps({"passed": passed, "runs": report}, indent=2),
                encoding="utf-8")
            print("FULL safety gate evidence:", json.dumps(report, indent=2), flush=True)
            if not passed:
                print("STOP: at least one FULL safety gate failed; no later stage was scheduled.",
                      flush=True)
                return 1
        _atomic_json(CONTROL_DIR / "runner_state.json", {
            "stage": stage_name, "completed": len(completed_ids), "total": total,
            "active": [], "pending": [], "updated_at": time.time(),
        })
    print(f"all {len(completed_ids)} / {total} manifest runs complete", flush=True)
    _atomic_json(CONTROL_DIR / "runner_state.json", {
        "stage": "complete", "completed": len(completed_ids), "total": total,
        "active": [], "pending": [], "updated_at": time.time(),
    })
    return 0


def status(manifest: dict[str, Any], root: Path = DEFAULT_ROOT) -> None:
    done = []
    for job in manifest["jobs"]:
        if completed_summary(root, job) is not None:
            done.append(job["run_id"])
    state_path = CONTROL_DIR / "runner_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    print(f"runs done {len(done)} / {len(manifest['jobs'])} | current stage: "
          f"{state.get('stage', 'not running')}")
    print("ETA: " + str(state.get("eta_minutes", "unavailable")) + " min")
    active = state.get("active", [])
    if active:
        for item in active:
            print(f"{item['run_id']}: step {item['step_progress']}")
    else:
        print("per-run step progress: no active worker")
    log_path = CONTROL_DIR / "runner.log"
    if log_path.exists():
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        print("last log line: " + (lines[-1] if lines else "<empty>"))
    else:
        print("last log line: <runner.log missing>")


def stop_runner() -> None:
    pid_path = CONTROL_DIR / "runner.pid"
    if not pid_path.exists():
        print("no runner.pid; nothing to stop")
        return
    pid = int(pid_path.read_text(encoding="utf-8").strip())
    try:
        import psutil
        root = psutil.Process(pid)
        descendants = root.children(recursive=True)
        for child in descendants:
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
        root.terminate()
        _gone, alive = psutil.wait_procs([*descendants, root], timeout=5)
        for process in alive:
            process.kill()
        print(f"stopped runner process tree rooted at PID {pid}")
    except (ImportError, OSError, ProcessLookupError) as exc:
        print(f"runner PID {pid} is not running or cannot be stopped: {exc}")


def launch_detached(manifest_path: Path, root: Path, max_workers: int) -> int:
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    log = (CONTROL_DIR / "runner.log").open("a", encoding="utf-8", buffering=1)
    command = [sys.executable, str(Path(__file__).resolve()), "--manifest", str(manifest_path),
               "--root", str(root), "--max-workers", str(max_workers),
               "--execute", "--confirm-final-study"]
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    process = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL,
                               stdout=log, stderr=subprocess.STDOUT,
                               creationflags=flags, close_fds=True)
    (CONTROL_DIR / "runner.pid").write_text(str(process.pid), encoding="utf-8")
    log.close()
    print(f"detached runner PID {process.pid}; log={CONTROL_DIR / 'runner.log'}")
    return process.pid


def print_plan(manifest: dict[str, Any]) -> None:
    validate_manifest(manifest)
    counts = {}
    for job in manifest["jobs"]:
        counts[job["variant"]] = counts.get(job["variant"], 0) + 1
    print(f"manifest valid: {len(manifest['jobs'])} jobs; "
          f"33 non-GRU + 3 GRU; max workers={MAX_WORKERS}")
    print(f"seeds={manifest['training_seeds']}; main_steps={manifest['main_steps']}; "
          f"GRU_steps={manifest['gru_steps']}; variant counts={counts}")
    print("-Aux reuses:", json.dumps(manifest["reuse"]["ABL_no_aux"]))
    for stage, jobs in _stage_jobs(manifest):
        print(f"{stage}: {len(jobs)} runs")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--max-workers", type=int, default=MAX_WORKERS)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--plan", action="store_true", help="validate and print only")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--launch-detached", action="store_true",
                        help="start the approved runner detached with runner.log/pid")
    parser.add_argument("--status", action="store_true", help="show runner progress")
    parser.add_argument("--stop", action="store_true", help="stop runner and worker processes")
    parser.add_argument("--confirm-final-study", action="store_true",
                        help="explicit approval safeguard; required with --execute")
    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    if args.status:
        status(manifest, args.root)
        return
    if args.stop:
        stop_runner()
        return
    if args.plan:
        print_plan(manifest)
        return
    if not args.execute or not args.confirm_final_study:
        parser.error("execution is disabled without both --execute and --confirm-final-study")
    if args.max_workers > MAX_WORKERS:
        print(f"requested {args.max_workers} workers; enforcing {MAX_WORKERS} maximum",
              flush=True)
    if args.launch_detached:
        launch_detached(args.manifest.resolve(), args.root.resolve(),
                        effective_workers(args.max_workers, len(manifest["jobs"])))
        return
    raise SystemExit(execute(manifest, root=args.root,
                             max_workers=effective_workers(args.max_workers, 36)))


if __name__ == "__main__":
    main()
