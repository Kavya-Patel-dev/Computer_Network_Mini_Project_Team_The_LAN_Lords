"""Create the fixed Day 5.3 ladder and ablation smoke job specs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BASE = {
    "dueling": False,
    "noisy_net": False,
    "gru_history": False,
    "mlp_encoder": False,
    "auxiliary_utilization": False,
    "noisy_sigma0": 0.1,
}


def variants() -> list[tuple[str, dict, int, bool, bool, float]]:
    rows: list[tuple[str, dict, int, bool, bool, float]] = []

    def add(name: str, **kwargs) -> None:
        settings = {**BASE, **kwargs}
        n_step = 3 if settings.pop("n_step_enabled", False) else 1
        per = bool(settings.pop("per_enabled", False))
        load_bc = bool(settings.pop("load_bc", True))
        bc_weight = float(settings.pop("auxiliary_bc_weight",
                                        0.1 if load_bc else 0.0))
        if settings.get("gru_history", False):
            settings["compact_history"] = True
        rows.append((name, settings, n_step, per, load_bc, bc_weight))

    # Cumulative ladder: each row adds one mechanic.
    add("L0_base", n_step_enabled=False, per_enabled=False)
    add("L1_dueling", dueling=True, n_step_enabled=False, per_enabled=False)
    add("L2_nstep", dueling=True, n_step_enabled=True, per_enabled=False)
    add("L3_prioritized", dueling=True, n_step_enabled=True, per_enabled=True)
    add("L4_noisy", dueling=True, n_step_enabled=True, per_enabled=True,
        noisy_net=True)
    add("L5_gru_aux", dueling=True, n_step_enabled=True, per_enabled=True,
        noisy_net=True, gru_history=True, auxiliary_utilization=True)
    add("MLP_encoder", mlp_encoder=True, n_step_enabled=False, per_enabled=False)

    # Full-system ablations, each removing only the named mechanism(s).
    add("ablate_no_dueling", n_step_enabled=True, per_enabled=True,
        noisy_net=True, gru_history=True, auxiliary_utilization=True)
    add("ablate_no_per_nstep", dueling=True, noisy_net=True,
        gru_history=True, auxiliary_utilization=True)
    add("ablate_no_gru", dueling=True, n_step_enabled=True, per_enabled=True,
        noisy_net=True, auxiliary_utilization=True)
    add("ablate_no_aux", dueling=True, n_step_enabled=True, per_enabled=True,
        noisy_net=True, gru_history=True)
    add("ablate_no_gat", dueling=True, n_step_enabled=True, per_enabled=True,
        noisy_net=True, gru_history=True, auxiliary_utilization=True,
        mlp_encoder=True)
    add("ablate_no_imitation", dueling=True, n_step_enabled=True, per_enabled=True,
        noisy_net=True, gru_history=True, auxiliary_utilization=True,
        load_bc=False, auxiliary_bc_weight=0.0)
    add("ablate_no_noisy", dueling=True, n_step_enabled=True, per_enabled=True,
        gru_history=True, auxiliary_utilization=True)
    return rows


def create_specs(l5_only: bool = False, only: str | None = None) -> list[dict]:
    all_variants = variants()
    specs = []
    for index, (name, flags, n_step, per, load_bc, bc_weight) in enumerate(all_variants):
        if l5_only and name != "L5_gru_aux":
            continue
        if only and name != only:
            continue
        specs.append({
            "name": name,
            "worker": "day5_3_worker.py",
            "stage": "Day 5.3-5.4",
            "seed": 20_530 + index,
            "steps": 3_000,
            "run_root": str(ROOT / "runs" / "day5_3"),
            "output_root": str(ROOT / "outputs" / "day5_3"),
            "check_determinism": False,
            "overrides": {
                "flags": flags,
                "n_step": n_step,
                "prioritized_replay": per,
                "load_bc": load_bc,
                "auxiliary_bc_weight": bc_weight,
            },
        })
    return specs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--l5-only", action="store_true")
    parser.add_argument("--only", help="emit exactly one named config")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or (ROOT / "configs" /
                             ("day5_3_l5_rss.json" if args.l5_only else
                              "day5_3_" + args.only + ".json" if args.only else
                              "day5_3_smoke.json"))
    specs = create_specs(args.l5_only, args.only)
    output.write_text(json.dumps({"jobs": specs}, indent=2),
                      encoding="utf-8")
    print(f"wrote {len(specs)} jobs to {output}")


if __name__ == "__main__":
    main()
