"""Bounded process runner and merger for independent Day 5.1 jobs."""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = ROOT / "runs" / "day5_1"
OUT_ROOT = ROOT / "outputs" / "day5_1"


def smoke_specs(steps: int = 2_000) -> list[dict]:
    common = {
        "batch_size": 64,
        "update_every": 4,
        "learning_starts": 64,
        "replay_capacity": 25_000,
    }
    base = {**common, "store_tensor_replay": False,
            "use_custom_collate": False, "reuse_duplicate_states": False}
    fast = {**common, "store_tensor_replay": True,
            "use_custom_collate": True, "reuse_duplicate_states": True}
    return [
        {"name": "smoke_base_seed20501_a", "seed": 20_501,
         "stage": "B", "steps": steps, "overrides": base},
        {"name": "smoke_base_seed20501_b", "seed": 20_501,
         "stage": "B", "steps": steps, "overrides": base},
        {"name": "smoke_fast_seed20502_a", "seed": 20_502,
         "stage": "B", "steps": steps, "overrides": fast},
        {"name": "smoke_fast_seed20502_b", "seed": 20_502,
         "stage": "B", "steps": steps, "overrides": fast},
    ]


def load_specs(path: Path | None, quick: bool) -> list[dict]:
    if path is None:
        specs = smoke_specs()
    else:
        payload = json.loads(path.read_text(encoding="utf-8"))
        specs = payload["jobs"] if isinstance(payload, dict) else payload
    normalized = []
    for raw in specs:
        spec = dict(raw)
        spec.setdefault("stage", "B")
        spec.setdefault("steps", 2_000)
        spec.setdefault("overrides", {})
        if quick:
            spec["steps"] = min(2_000, int(spec["steps"]))
        if int(spec["seed"]) < 20_000:
            raise ValueError(f"training seed must be >=20000: {spec['name']}")
        if int(spec["overrides"].get("replay_capacity", 25_000)) != 25_000:
            raise ValueError("all Day 5.1 runner configs must use replay_capacity=25000")
        normalized.append(spec)
    return normalized


def merge(root: Path = OUT_ROOT, *, require_determinism: bool = True
          ) -> tuple[list[dict], bool]:
    summaries = []
    for summary_path in sorted(root.glob("*/summary.json")):
        summaries.append(json.loads(summary_path.read_text(encoding="utf-8")))
    print("| run | seed | steps | updates | steps/s | val loss | peak RSS MiB |",
          flush=True)
    print("|---|---:|---:|---:|---:|---:|---:|", flush=True)
    for row in summaries:
        val = "" if row.get("last_val_loss") is None else f"{row['last_val_loss']:.6f}"
        rss = row.get("peak_rss_mib")
        rss_text = "n/a" if rss is None else f"{rss:.1f}"
        print(f"| {row['name']} | {row['seed']} | {row['steps']} | {row['updates']} | "
              f"{row['steps_per_second']:.2f} | {val} | {rss_text} |", flush=True)
    groups: dict[tuple[str, int], list[dict]] = {}
    for row in summaries:
        groups.setdefault((row["signature"], row["seed"]), []).append(row)
    determ = True
    pairs = 0
    print("\nDeterminism check (exact first-1,000-step loss sequence):", flush=True)
    for (_signature, seed), group in groups.items():
        if len(group) < 2:
            continue
        pairs += 1
        traces = [json.loads(Path(item["loss_trace_path"]).read_text(encoding="utf-8"))
                  for item in group]
        matched = all(trace == traces[0] for trace in traces[1:])
        determ &= matched
        print(f"  seed={seed}: {len(group)} parallel copies; "
              f"{len(traces[0])} losses; {'PASS' if matched else 'FAIL'}", flush=True)
    if pairs == 0:
        determ = not require_determinism
        print("  no duplicate config/seed pair found" +
              (" (not requested)" if not require_determinism else ""), flush=True)
    csv_path = root / "merged_summary.csv"
    if summaries:
        fields = ("name", "seed", "steps", "updates", "steps_per_second",
                  "last_val_loss", "losses_first_1000", "peak_rss_mib")
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows({key: row.get(key) for key in fields}
                             for row in summaries)
    print(f"Merged {len(summaries)} runs to {csv_path}", flush=True)
    return summaries, determ


def process_tree_rss_bytes(process_id: int, psutil_module) -> int:
    """Sum the Windows Python launcher and its Python child RSS values."""
    try:
        root_process = psutil_module.Process(process_id)
        processes = [root_process, *root_process.children(recursive=True)]
    except (psutil_module.NoSuchProcess, psutil_module.AccessDenied):
        return 0
    total = 0
    for child in processes:
        try:
            total += child.memory_info().rss
        except (psutil_module.NoSuchProcess, psutil_module.AccessDenied):
            continue
    return total


def run(specs: list[dict], max_workers: int) -> int:
    if not specs:
        raise ValueError("no jobs configured")
    run_root = Path(specs[0].get("run_root", RUN_ROOT))
    out_root = Path(specs[0].get("output_root", OUT_ROOT))
    if any(Path(spec.get("run_root", run_root)) != run_root
           or Path(spec.get("output_root", out_root)) != out_root
           for spec in specs):
        raise ValueError("all jobs in a runner invocation must share output roots")
    run_root.mkdir(parents=True, exist_ok=True)
    out_root.mkdir(parents=True, exist_ok=True)
    max_workers = max(1, min(12, int(max_workers), len(specs)))
    pending = list(specs)
    running: dict[subprocess.Popen, dict] = {}
    durations: list[float] = []
    completed = 0
    failed = 0
    total = len(specs)
    try:
        import psutil
    except ImportError:
        psutil = None
    while pending or running:
        while pending and len(running) < max_workers:
            spec = pending.pop(0)
            run_dir = run_root / spec["name"]
            output_dir = out_root / spec["name"]
            summary_path = output_dir / "summary.json"
            if summary_path.exists():
                old = json.loads(summary_path.read_text(encoding="utf-8"))
                from day5_1_worker import canonical_signature
                identity = {**spec, "run_dir": str(run_dir), "output_dir": str(output_dir)}
                if old.get("signature") == canonical_signature(identity):
                    print(f"skip completed job {spec['name']} (preserved outputs)", flush=True)
                    completed += 1
                    continue
                raise FileExistsError(f"completed run exists with different config: {spec['name']}")
            if run_dir.exists() or output_dir.exists():
                raise FileExistsError(f"partial run exists; preserved, choose a new id: {spec['name']}")
            run_dir.mkdir(parents=True)
            output_dir.mkdir(parents=True)
            spec = {**spec, "run_dir": str(run_dir), "output_dir": str(output_dir)}
            spec_path = output_dir / "job_spec.json"
            spec_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")
            log_file = (output_dir / "run.log").open("w", encoding="utf-8")
            environment = os.environ.copy()
            environment.update({"OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
                                "OPENBLAS_NUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1"})
            worker_name = str(spec.get("worker", "day5_1_worker.py"))
            if Path(worker_name).name != worker_name:
                raise ValueError("worker must be a script name under scripts/")
            command = [sys.executable, str(ROOT / "scripts" / worker_name),
                       "--spec", str(spec_path)]
            started = time.perf_counter()
            process = subprocess.Popen(command, cwd=ROOT, env=environment,
                                       stdout=log_file, stderr=subprocess.STDOUT)
            running[process] = {"spec": spec, "log_file": log_file,
                                "log_path": Path(spec["output_dir"]) / "run.log",
                                "log_offset": 0,
                                "started": started, "peak_rss": 0}
            print(f"started {spec['name']} pid={process.pid} workers="
                  f"{len(running)}/{max_workers}", flush=True)
        time.sleep(0.25)
        for process, state in list(running.items()):
            try:
                with state["log_path"].open("r", encoding="utf-8") as live_log:
                    live_log.seek(state["log_offset"])
                    new_text = live_log.read()
                    state["log_offset"] = live_log.tell()
                for line in new_text.splitlines():
                    print(f"[{state['spec']['name']}] {line}", flush=True)
            except (FileNotFoundError, PermissionError):
                pass
            if psutil is not None and process.poll() is None:
                state["peak_rss"] = max(
                    state["peak_rss"],
                    process_tree_rss_bytes(process.pid, psutil))
            code = process.poll()
            if code is None:
                continue
            state["log_file"].close()
            elapsed = time.perf_counter() - state["started"]
            durations.append(elapsed)
            completed += 1
            if code:
                failed += 1
                print(f"job {state['spec']['name']} failed exit={code}; "
                      f"log={state['spec']['output_dir']}\\run.log", flush=True)
            else:
                summary_path = Path(state["spec"]["output_dir"]) / "summary.json"
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
                summary["peak_rss_bytes"] = (state["peak_rss"] or None)
                summary["peak_rss_mib"] = (state["peak_rss"] / (1024 * 1024)
                                           if state["peak_rss"] else None)
                summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
                print(f"finished {state['spec']['name']} in {elapsed:.1f}s; "
                      f"peak RSS {summary['peak_rss_mib'] if summary['peak_rss_mib'] is not None else 'n/a'} MiB",
                      flush=True)
            del running[process]
            unfinished = len(pending) + len(running)
            eta = (statistics.mean(durations)
                   * math.ceil(unfinished / max_workers)
                   if unfinished and durations else 0.0)
            print(f"done {completed} / {total} jobs, ETA {eta / 60.0:.2f} min",
                  flush=True)
    rows, deterministic = merge(
        out_root,
        require_determinism=any(bool(spec.get("check_determinism", True))
                                for spec in specs))
    print(f"Runner summary: {len(rows)}/{total} complete; "
          f"deterministic={deterministic}; failures={failed}", flush=True)
    return 1 if failed or len(rows) < total or not deterministic else 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--configs", type=Path,
                        help="JSON list of isolated jobs (default: four smoke jobs)")
    parser.add_argument("--max-workers", type=int, default=12)
    parser.add_argument("--quick", action="store_true",
                        help="cap configured jobs at 2,000 training steps")
    parser.add_argument("--merge", action="store_true",
                        help="merge already completed run directories only")
    parser.add_argument("--root", type=Path, default=OUT_ROOT,
                        help="output directory used by --merge")
    args = parser.parse_args()
    if args.merge:
        _rows, _deterministic = merge(args.root)
        return
    specs = load_specs(args.configs, args.quick)
    raise SystemExit(run(specs, args.max_workers))


if __name__ == "__main__":
    main()
