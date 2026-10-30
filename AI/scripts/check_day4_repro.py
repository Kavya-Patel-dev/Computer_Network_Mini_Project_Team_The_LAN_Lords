"""Run two identical Stage A prefixes and compare the first 1,000 updates."""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from models.data_guard import read_partitions
import train


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=202604)
    parser.add_argument("--steps", type=int, default=5996,
                        help="must produce at least 1,000 optimizer updates")
    args = parser.parse_args()
    partitions = read_partitions(ROOT / "data" / "splits.json")
    artifacts = ROOT / "outputs" / "day4" / "repro"
    train.RUNS = artifacts / "run1" / "runs"
    train.OUTPUTS = artifacts / "run1" / "outputs"
    first = train.run_training("A", args.steps, args.seed, partitions)
    train.RUNS = artifacts / "run2" / "runs"
    train.OUTPUTS = artifacts / "run2" / "outputs"
    second = train.run_training("A", args.steps, args.seed, partitions)
    a = np.asarray(first["history"]["losses"][:1000], dtype="<f8")
    b = np.asarray(second["history"]["losses"][:1000], dtype="<f8")
    if len(a) != 1000 or len(b) != 1000:
        raise RuntimeError(f"expected 1,000 updates per run, got {len(a)} and {len(b)}")
    max_abs_diff = float(np.max(np.abs(a - b)))
    digest_a = hashlib.sha256(a.tobytes()).hexdigest()
    digest_b = hashlib.sha256(b.tobytes()).hexdigest()
    print(f"A8: updates compared=1000; exact_equal={bool(np.array_equal(a, b))}; "
          f"max_abs_diff={max_abs_diff:.12g}; sha256_run1={digest_a}; "
          f"sha256_run2={digest_b}", flush=True)
    if not np.array_equal(a, b):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
