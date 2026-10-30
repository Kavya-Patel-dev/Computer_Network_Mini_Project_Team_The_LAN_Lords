"""Tune full-graph load-aware Dijkstra alpha on validation graphs only."""
from __future__ import annotations

import argparse
import json
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from baselines.evaluation import EVAL_SEEDS, load_graph, run_episode
from baselines.leakage import guard_fit_and_tuning

DATA = ROOT / "data"
OUTPUT = ROOT / "configs" / "evaluation.json"
SCORES = ROOT / "outputs" / "alpha_tuning.csv"
ALPHAS = (0.5, 1.0, 2.0, 4.0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()
    splits = json.loads((DATA / "splits.json").read_text(encoding="utf-8"))
    validation = [{**entry, "split": "val"} for entry in splits["val"]]
    test_names = {entry["name"] for entry in splits["test"]}
    train_names = {entry["name"] for entry in splits["train"]}
    guard_fit_and_tuning(set(), {entry["name"] for entry in validation},
                         train_names, {entry["name"] for entry in validation},
                         test_names)
    assert validation and all(entry["split"] == "val" for entry in validation)
    assert not ({entry["name"] for entry in validation} & test_names)
    intensities = json.loads((DATA / "eval_intensity.json").read_text(encoding="utf-8"))
    seeds = EVAL_SEEDS[:2] if args.quick else EVAL_SEEDS
    steps, warmup = (140, 30) if args.quick else (500, 100)
    graph_cache = {entry["name"]: load_graph(entry, DATA) for entry in validation}
    scores = []
    SCORES.parent.mkdir(parents=True, exist_ok=True)
    for alpha in ALPHAS:
        losses = []
        for entry in validation:
            intensity = intensities[entry["name"]]["generators"]["poisson"]["intensity"]
            for seed in seeds:
                row = run_episode(entry, graph_cache[entry["name"]], "poisson",
                                  intensity, "dijkstra_load_aware", seed,
                                  "normal", alpha, max_steps=steps,
                                  warmup=warmup, data_root=DATA)
                losses.append(row["mean_packet_loss"])
            print(f"alpha={alpha:g}: completed validation graph {entry['name']}", flush=True)
        score = sum(losses) / len(losses)
        scores.append((alpha, score))
        with SCORES.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=("alpha", "validation_mean_packet_loss"))
            writer.writeheader()
            writer.writerows({"alpha": value, "validation_mean_packet_loss": result}
                             for value, result in scores)
            f.flush()
        print(f"alpha={alpha:g}: validation mean packet loss={score:.8f}", flush=True)
    chosen, best = min(scores, key=lambda item: (item[1], item[0]))
    payload = {
        "dijkstra_load_aware_alpha": chosen,
        "alpha_candidates": list(ALPHAS),
        "selection_split": "val",
        "selection_metric": "mean packet loss; ties choose smaller alpha",
        "validation_mean_packet_loss": {str(alpha): score for alpha, score in scores},
        "validation_graphs": [entry["name"] for entry in validation],
        "validation_seeds": list(seeds),
        "evaluation_seeds": list(EVAL_SEEDS),
        "evaluation_seed_split_guard": "asserted before tuning; test graphs are never loaded",
    }
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Selected alpha={chosen:g} from validation only (loss {best:.8f}); wrote {OUTPUT}", flush=True)


if __name__ == "__main__":
    main()
