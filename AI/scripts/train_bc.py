"""Train and checkpoint the Day 5.2 dijkstra_load_aware_k BC initializer."""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from baselines.evaluation import load_graph
from env.network_env import NetworkEnvConfig, NetworkRoutingEnv
from env.traffic import PoissonTrafficGenerator
from models.behavior_cloning import (DEFAULT_HOLDOUT_FRACTION,
                                     DEFAULT_SPLIT_SEED, EXPERT_POLICY,
                                     bc_optimizer_step, build_examples,
                                     evaluate_bc, example_block_split,
                                     read_expert_indices,
                                     split_graph_seed_blocks)
from models.data_guard import guard_graph_request, read_partitions
from models.dqn import DoubleDQNAgent
from models.obs import ObservationWrapper

DATA = ROOT / "data"
CONFIG_PATH = ROOT / "configs" / "day5_2_bc.json"
OUT = ROOT / "runs" / "day5"
OBSERVATION_KEYS = ("node_features", "edge_features", "flow_features",
                    "candidate_paths", "action_mask", "edge_index",
                    "history_nodes", "history_edges")


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("\n", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as file:
        fields = list(dict.fromkeys(key for row in rows for key in row))
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true",
                        help="small deterministic smoke run; not for gate evaluation")
    parser.add_argument("--epochs", type=int, default=None)
    args = parser.parse_args()

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    seed = int(config["seed"])
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass

    partitions = read_partitions(DATA / "splits.json")
    train_entries = {row["name"]: {**row, "split": "train"}
                     for row in partitions["train"]}
    train_names = set(train_entries)
    test_names = {row["name"] for row in partitions["test"]}
    manifest, indices = read_expert_indices(DATA / "expert", train_names, test_names,
                                             EXPERT_POLICY)
    blocks = {(row.graph, row.seed) for row in indices}
    train_blocks, holdout_blocks = split_graph_seed_blocks(
        blocks, train_names, test_names,
        float(config["block_split"]["holdout_fraction"]),
        int(config["block_split"]["seed"]))
    train_indices = [row for row in indices if (row.graph, row.seed) in train_blocks]
    holdout_indices = [row for row in indices if (row.graph, row.seed) in holdout_blocks]
    if args.quick:
        # Keep enough examples for several minibatches, but preserve whole
        # graph/seed separation and never inspect validation/test topology.
        train_indices = train_indices[:256]
        holdout_indices = holdout_indices[:64]
    if args.epochs is not None and args.epochs <= 0:
        parser.error("--epochs must be positive")
    epochs = 1 if args.quick else int(args.epochs or config["epochs"])
    batch_size = int(config["batch_size"])
    needed_graphs = sorted({row.graph for row in train_indices + holdout_indices})

    graph_contexts = {}
    for graph_no, name in enumerate(needed_graphs, start=1):
        entry = train_entries[name]
        guard_graph_request(entry, "train", partitions)
        graph = load_graph(entry, DATA)
        stub = PoissonTrafficGenerator(sorted(graph.nodes), demand_mbps=1.0)
        env = NetworkRoutingEnv(graph,
                                NetworkEnvConfig(k_paths=4, max_steps=500, intensity=0.1),
                                traffic_generator=stub)
        graph_contexts[name] = (env, ObservationWrapper(env, name))
        print(f"Prepared train topology {graph_no} / {len(needed_graphs)}: {name}",
              flush=True)

    last_progress = 0

    def report_build(shard_no: int, shard_total: int, example_count: int) -> None:
        nonlocal last_progress
        if shard_no == shard_total or shard_no - last_progress >= 25:
            print(f"Wrapped expert shards {shard_no} / {shard_total} | "
                  f"examples {example_count}", flush=True)
            last_progress = shard_no

    prep_start = time.perf_counter()
    examples = build_examples(DATA / "expert", train_indices + holdout_indices,
                              graph_contexts, progress=report_build)
    train_examples, holdout_examples = example_block_split(
        examples, train_blocks, holdout_blocks)
    if args.quick:
        # The samples were selected independently within each partition; retain
        # the explicit holdout separation established above.
        train_examples = [row for row in examples
                          if (row.graph, row.seed) in train_blocks]
        holdout_examples = [row for row in examples
                            if (row.graph, row.seed) in holdout_blocks]
        train_examples = train_examples[:256]
        holdout_examples = holdout_examples[:64]
    prep_seconds = time.perf_counter() - prep_start
    print(f"Expert examples: train={len(train_examples)} holdout={len(holdout_examples)} "
          f"blocks={len(train_blocks)}/{len(holdout_blocks)} "
          f"selected DLAK rows={len(indices)} "
          f"policy={EXPERT_POLICY}; data prep={prep_seconds:.1f}s", flush=True)

    agent = DoubleDQNAgent(
        actions=4, lr=float(config["learning_rate"]), seed=seed,
        use_third_layer=bool(config["architecture"]["optional_third_layer"]),
        use_custom_collate=bool(config["architecture"]["custom_collate"]))
    model, optimizer = agent.online, agent.optimizer
    model.eval()
    quick_eval_limit = 256 if args.quick else None
    initial_val = evaluate_bc(model, holdout_examples, batch_size,
                              max_examples=quick_eval_limit)
    total_updates = epochs * math.ceil(len(train_examples) / batch_size)
    checkpoint_interval = int(config["checkpoint_interval_updates"])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "bc_config.json").write_text(json.dumps(config, indent=2) + "\n",
                                         encoding="utf-8")
    checkpoint = OUT / "bc_init.pt"
    latest_checkpoint = OUT / "bc_latest.pt"
    history: list[dict] = []
    rng = np.random.default_rng(seed + 1)
    best_loss = float("inf")
    best_epoch = 0
    stale_epochs = 0
    update = 0
    training_started = time.perf_counter()
    last_val_loss = initial_val["loss"]

    for epoch in range(1, epochs + 1):
        permutation = rng.permutation(len(train_examples))
        for start in range(0, len(permutation), batch_size):
            batch = [train_examples[int(i)]
                     for i in permutation[start:start + batch_size]]
            losses = bc_optimizer_step(model, optimizer, batch,
                                       margin=float(config["loss"]["margin"]),
                                       max_grad_norm=float(config["gradient_clip_norm"]))
            update += 1
            history.append({"update": update, "epoch": epoch, **losses,
                            "val_loss": last_val_loss})
            if update % checkpoint_interval == 0:
                agent.target.load_state_dict(model.state_dict())
                agent.save(str(latest_checkpoint), {
                    "stage": "day5.2_bc", "step": update, "epoch": epoch,
                    "seed": seed, "config": config,
                })
            if update % 100 == 0 or update == total_updates:
                elapsed = time.perf_counter() - training_started
                rate = elapsed / max(1, update)
                eta_minutes = rate * (total_updates - update) / 60.0
                print(f"step {update} / {total_updates} | val loss {last_val_loss:.6f} | "
                      f"ETA {eta_minutes:.1f} min", flush=True)

        val_metrics = evaluate_bc(model, holdout_examples, batch_size,
                                  max_examples=quick_eval_limit)
        last_val_loss = val_metrics["loss"]
        history.append({"update": update, "epoch": epoch,
                        "train_loss": float(np.mean([row["loss"] for row in history
                                                     if row.get("epoch") == epoch])),
                        "val_loss": last_val_loss,
                        "val_top1_agreement": val_metrics["top1_agreement"]})
        improved = last_val_loss < best_loss - 1e-7
        if improved:
            best_loss, best_epoch, stale_epochs = last_val_loss, epoch, 0
            agent.target.load_state_dict(model.state_dict())
            agent.save(str(checkpoint), {
                "stage": "day5.2_bc", "step": update, "epoch": epoch,
                "seed": seed, "config": config,
                "best_holdout_loss": best_loss,
                "holdout_top1_agreement": val_metrics["top1_agreement"],
                "expert_policy": EXPERT_POLICY,
            })
            print(f"saved best BC checkpoint at step {update}: "
                  f"holdout loss={best_loss:.6f}, top1={val_metrics['top1_agreement']:.4f}",
                  flush=True)
        else:
            stale_epochs += 1
        print(f"epoch {epoch} / {epochs} | holdout loss {last_val_loss:.6f} | "
              f"top1 {val_metrics['top1_agreement']:.4f} | "
              f"best epoch {best_epoch}", flush=True)
        if not args.quick and stale_epochs >= int(config["early_stopping_patience"]):
            print(f"early stop after {stale_epochs} non-improving epochs", flush=True)
            break

    if not checkpoint.exists():
        # The first epoch always creates a best checkpoint unless the holdout
        # metrics are nonfinite, which evaluate_bc rejects through the loss.
        raise RuntimeError("BC training finished without a checkpoint")
    final_training_seconds = time.perf_counter() - training_started
    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    agent.online.load_state_dict(payload["online"])
    agent.online.eval()

    graph_rows: list[dict] = []
    for graph in sorted({row.graph for row in holdout_examples}):
        graph_examples = [row for row in holdout_examples if row.graph == graph]
        metrics = evaluate_bc(model, graph_examples, batch_size)
        graph_rows.append({"graph": graph, **metrics,
                           "holdout_blocks": len({row.seed for row in graph_examples})})
        print(f"held-out agreement {graph}: {metrics['top1_agreement']:.4f} "
              f"({int(metrics['examples'])} examples), loss={metrics['loss']:.6f}",
              flush=True)
    write_csv(OUT / "bc_holdout_by_graph.csv", graph_rows)
    write_csv(OUT / "bc_training_history.csv", history)
    report = {
        "stage": "Day 5.2 BC pretraining",
        "expert_policy": EXPERT_POLICY,
        "excluded_expert_policy": "greedy_min_util",
        "source_expert_labels": manifest.get("experts", []),
        "seed": seed,
        "block_split_seed": int(config["block_split"]["seed"]),
        "training_blocks": len(train_blocks),
        "holdout_blocks": len(holdout_blocks),
        "training_examples": len(train_examples),
        "holdout_examples": len(holdout_examples),
        "expert_rows_selected": len(indices),
        "selected_epoch": best_epoch,
        "selected_step": payload.get("metadata", {}).get("step"),
        "best_holdout_loss": best_loss,
        "preparation_seconds": prep_seconds,
        "training_seconds": final_training_seconds,
        "quick": bool(args.quick),
        "holdout_by_graph": graph_rows,
    }
    (OUT / "bc_training_report.json").write_text(json.dumps(report, indent=2) + "\n",
                                                  encoding="utf-8")
    print(f"BC training time: {final_training_seconds:.1f}s; data preparation: "
          f"{prep_seconds:.1f}s; selected checkpoint: {checkpoint}", flush=True)
    print("held-out agreement table:")
    print("| Graph | examples | top-1 agreement | Q(expert)-Q(chosen) | CE + margin loss |")
    print("|---|---:|---:|---:|---:|")
    for row in graph_rows:
        print(f"| {row['graph']} | {int(row['examples'])} | "
              f"{row['top1_agreement']:.4f} | {row['mean_q_expert_minus_chosen']:.5f} | "
              f"{row['loss']:.6f} |")


if __name__ == "__main__":
    main()
