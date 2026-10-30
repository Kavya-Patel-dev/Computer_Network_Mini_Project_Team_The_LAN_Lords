"""One isolated Day 5.1 training job, launched by run_experiments.py."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from models.data_guard import read_partitions
import train


def canonical_signature(spec: dict) -> str:
    identity = {key: spec[key] for key in ("stage", "seed", "steps", "overrides")}
    payload = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, required=True)
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    run_dir = Path(spec["run_dir"])
    output_dir = Path(spec["output_dir"])
    config_path = ROOT / "configs" / "day5_1.json"
    train.CONFIG = json.loads(config_path.read_text(encoding="utf-8"))
    train.CONFIG.update(spec["overrides"])
    train.RUNS = run_dir
    train.OUTPUTS = output_dir
    train.configure_reproducibility(int(spec["seed"]))
    partitions = read_partitions(ROOT / "data" / "splits.json")
    started = time.perf_counter()
    result = train.run_training(
        str(spec["stage"]), int(spec["steps"]), int(spec["seed"]), partitions,
        quick=True)
    elapsed = time.perf_counter() - started
    loss_trace = [
        {"step": int(step), "loss": float(loss)}
        for step, loss in zip(result["history"]["loss_steps"],
                              result["history"]["losses"])
        if int(step) <= 1_000
    ]
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "first_1000_step_losses.json").write_text(
        json.dumps(loss_trace, separators=(",", ":")), encoding="utf-8")
    summary = {
        "name": spec["name"],
        "signature": canonical_signature(spec),
        "seed": int(spec["seed"]),
        "steps": int(spec["steps"]),
        "updates": int(result["updates"]),
        "best_val_loss": (float(result["best_val_loss"])
                          if result["best_val_loss"] != float("inf") else None),
        "last_val_loss": result["last_val_loss"],
        "elapsed_seconds": elapsed,
        "steps_per_second": float(result["steps"]) / max(1e-9, elapsed),
        "losses_first_1000": len(loss_trace),
        "loss_trace_path": str(output_dir / "first_1000_step_losses.json"),
        "run_dir": str(run_dir),
        "output_dir": str(output_dir),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
