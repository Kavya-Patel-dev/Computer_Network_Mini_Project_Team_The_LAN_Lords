"""Run the real worker for the approved tiny FULL and L6 smoke jobs."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from models.day5_study import (CONTROLS, SELECTION_SEEDS, build_manifest,
                               full_run_safety_check)
from scripts.day5_5_6_runner import run_stage


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path,
                        default=ROOT / "outputs" / "day5_5_6" / "smoke" / "runs")
    args = parser.parse_args()
    manifest = build_manifest()
    by_id = {job["run_id"]: job for job in manifest["jobs"]}
    val_noncontrols = [row["name"] for row in json.loads(
        (ROOT / "data" / "splits.json").read_text(encoding="utf-8"))["val"]
        if row["name"] not in CONTROLS]
    if len(val_noncontrols) != 2:
        raise RuntimeError(f"expected exactly two non-control validation graphs; got {val_noncontrols}")
    jobs = []
    for run_id in ("FULL_seed20101", "L6_GRU_T2_seed20101"):
        job = dict(by_id[run_id])
        job.update({
            "steps": 1_200,
            "learning_starts": 200,
            "checkpoint_interval": 200,
            "selection_graph_names": val_noncontrols,
            "selection_seeds": list(SELECTION_SEEDS),
            "selection_eval_max_steps": 500,
            "final_eval_max_steps": 500,
            "smoke": True,
        })
        jobs.append(job)
    worker = ROOT / "scripts" / "day5_5_6_worker.py"
    done: set[str] = set()
    success = run_stage(
        jobs, stage_name="real worker smoke", root=args.root,
        max_workers=2, completed_ids=done, total=2,
        completed_elapsed=[], worker=worker)
    if not success or len(done) != 2:
        raise SystemExit("real worker smoke did not complete cleanly")
    full_summary = json.loads((args.root / "FULL_seed20101" / "output" / "summary.json")
                              .read_text(encoding="utf-8"))
    safety_pass, safety_report = full_run_safety_check(full_summary)
    corrupted = json.loads(json.dumps(full_summary))
    trace = corrupted.get("loss_trace", [])
    if not trace:
        raise RuntimeError("FULL smoke summary has no training loss trace")
    trace[0] = float("nan")
    corrupted_pass, corrupted_report = full_run_safety_check(corrupted)
    gate = {"healthy_full_smoke_pass": safety_pass,
            "healthy_report": safety_report,
            "nan_corrupted_copy_rejected": not corrupted_pass,
            "corrupted_report": corrupted_report}
    output = ROOT / "outputs" / "day5_5_6" / "smoke" / "smoke_safety_gate.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(gate, indent=2), encoding="utf-8")
    print("validation smoke graphs:", ", ".join(val_noncontrols),
          "+ controls:", ", ".join(CONTROLS))
    print("smoke FULL safety:", json.dumps(gate, indent=2))
    print("summary outputs:")
    for job in jobs:
        summary_path = args.root / job["run_id"] / "output" / "summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        print(json.dumps({"run_id": job["run_id"],
                          "summary": str(summary_path),
                          "steps_per_second": summary["steps_per_second"],
                          "selected_step": summary["selected_step"],
                          "selected_reload_q_max_abs_diff": summary["selected_reload_q_max_abs_diff"],
                          "final_reload_q_max_abs_diff": summary["final_reload_q_max_abs_diff"],
                          "runner_peak_rss_bytes": summary["runner_peak_rss_bytes"],
                          "final_evaluation": summary["final_evaluation"]}, indent=2))
    if not safety_pass or corrupted_pass:
        raise SystemExit("smoke safety checker failed its required acceptance/rejection cases")


if __name__ == "__main__":
    main()
