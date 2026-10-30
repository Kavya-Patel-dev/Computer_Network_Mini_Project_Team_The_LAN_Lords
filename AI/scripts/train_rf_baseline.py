"""Build graph-split RF congestion labels and fit rf_routing on train only."""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import deque
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from baselines.evaluation import EVAL_SEEDS, load_graph, make_traffic
from baselines.features import FEATURE_NAMES, candidate_features
from baselines.leakage import guard_fit_and_tuning
from baselines.policies import choose_decision
from env.network_env import NetworkEnvConfig, NetworkRoutingEnv
from env.traffic import PoissonTrafficGenerator

DATA = ROOT / "data"
OUT = ROOT / "outputs" / "rf_data"
MODEL = ROOT / "outputs" / "rf_routing.joblib"


def update_labels_for_snapshot(pending: dict, env: NetworkRoutingEnv,
                               actual_path: tuple[str, ...] | None,
                               actual_flow_id: str, demand: float,
                               offset: int) -> None:
    if offset > min(5, int(pending["duration"])):
        return
    active_ids = {flow.flow.flow_id for flow in env.active_flows}
    actual_active = actual_flow_id in active_ids and actual_path is not None
    routers = set(env.router_nodes)
    for i, path in enumerate(pending["paths"]):
        maximum = 0.0
        for u, v in zip(path, path[1:]):
            if u not in routers or v not in routers:
                continue
            attrs = env.graph[u][v]
            capacity = float(attrs.get("capacity", 0.0))
            if not attrs.get("up", True) or capacity <= 0:
                continue
            key = env._key(u, v)
            load = env.loads.get(key, 0.0)
            # Estimate the counterfactual load with this candidate installed:
            # remove the actual rollout flow if it remains active, then add the
            # current request to the candidate edge for its sampled lifetime.
            if actual_active and (u, v) in zip(actual_path, actual_path[1:]):
                load -= demand
            load += demand
            maximum = max(maximum, load / capacity)
        if maximum > 0.9 + 1e-9:
            pending["labels"][i] = 1


def collect_graph(entry: dict, split: str, episodes: int, seeds: list[int],
                  evaluation_intensities: dict, alpha: float,
                  low: float, high: float, rng: np.random.Generator,
                  quick: bool) -> dict[str, np.ndarray]:
    graph = load_graph(entry, DATA)
    rows_x: list[np.ndarray] = []
    rows_y: list[int] = []
    rows_taken: list[bool] = []
    rows_policy: list[str] = []
    rows_seed: list[int] = []
    rows_intensity: list[float] = []
    available_generators = [kind for kind in ("poisson", "gravity", "hotspot", "sndlib")
                            if kind != "sndlib" or entry["source"] == "sndlib"]
    for episode in range(episodes):
        seed = int(seeds[episode % len(seeds)])
        if split == "train" and seed in EVAL_SEEDS:
            raise AssertionError("evaluation seeds cannot be used for training");
        kind = available_generators[(episode + rng.integers(len(available_generators)))
                                    % len(available_generators)]
        if split == "train":
            intensity = math.exp(float(rng.uniform(math.log(low), math.log(high))))
        else:
            intensity = float(evaluation_intensities[entry["name"]]["generators"][kind]["intensity"])
        steps = 180 if quick else 500
        config = NetworkEnvConfig(max_steps=steps, intensity=intensity)
        stub = PoissonTrafficGenerator(sorted(graph.nodes), demand_mbps=1.0)
        topology = NetworkRoutingEnv(graph, config, traffic_generator=stub)
        traffic = make_traffic(kind, entry, topology, intensity, DATA)
        env = NetworkRoutingEnv(graph, config, traffic_generator=traffic)
        observation, _ = env.reset(seed=seed)
        policy_rng = np.random.default_rng(seed ^ 0xBADC0DE)
        pending: deque[dict] = deque()
        rollout_policy_names = ("random", "dijkstra_load_aware_k", "greedy_min_util")
        for step in range(steps):
            if env.flow is None:
                raise RuntimeError(f"missing flow on RF data collection {entry['name']}")
            candidates = tuple(tuple(path) for path in env._paths.paths)
            features = np.stack([candidate_features(env, path, 10_000)
                                 for path in candidates]) if candidates else np.empty((0, len(FEATURE_NAMES)), dtype=np.float32)
            # A reproducible mixture of random and both Day 2 experts.
            choice = float(policy_rng.random())
            selected_policy = (rollout_policy_names[0] if choice < 1 / 3 else
                               rollout_policy_names[1] if choice < 2 / 3 else
                               rollout_policy_names[2])
            decision = choose_decision(selected_policy, env, policy_rng, alpha=alpha)
            actual_path = (candidates[decision.action]
                           if decision.action < len(candidates) else None)
            request = env.flow
            record = {"features": features, "paths": candidates,
                      "labels": np.zeros(len(candidates), dtype=np.uint8),
                      "duration": request.duration_steps,
                      "flow_id": request.flow_id,
                      "demand": request.demand_mbps,
                      "actual_path": actual_path,
                      "taken": decision.action,
                      "policy": selected_policy,
                      "seed": seed, "intensity": intensity}
            pending.append(record)
            observation, _reward, _terminated, _truncated, _info = env.step(decision.action)
            for old in pending:
                offset = len(old.setdefault("future_offsets", [])) + 1
                update_labels_for_snapshot(old, env, old["actual_path"],
                                           old["flow_id"], old["demand"], offset)
                old["future_offsets"].append(offset)
            while pending and len(pending[0].get("future_offsets", [])) >= 5:
                old = pending.popleft()
                for i, feature in enumerate(old["features"]):
                    rows_x.append(feature)
                    rows_y.append(int(old["labels"][i]))
                    rows_taken.append(i == old["taken"])
                    rows_policy.append(old["policy"])
                    rows_seed.append(old["seed"])
                    rows_intensity.append(old["intensity"])
        # End-of-episode samples without five future steps are right-censored
        # and are deliberately omitted from the supervised labels.
    return {"features": np.asarray(rows_x, dtype=np.float32),
            "labels": np.asarray(rows_y, dtype=np.uint8),
            "actual_candidate_taken": np.asarray(rows_taken, dtype=np.uint8),
            "rollout_policy": np.asarray(rows_policy, dtype="U32"),
            "seed": np.asarray(rows_seed, dtype=np.int64),
            "intensity": np.asarray(rows_intensity, dtype=np.float32),
            "graph_name": np.asarray([entry["name"]] * len(rows_y), dtype="U64"),
            "split": np.asarray([split] * len(rows_y), dtype="U8")}


def _metrics(y: np.ndarray, prediction: np.ndarray) -> dict[str, float]:
    from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
    return {"accuracy": float(accuracy_score(y, prediction)),
            "precision": float(precision_score(y, prediction, zero_division=0)),
            "recall": float(recall_score(y, prediction, zero_division=0)),
            "f1": float(f1_score(y, prediction, zero_division=0))}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="small development RF dataset")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    splits = json.loads((DATA / "splits.json").read_text(encoding="utf-8"))
    split_entries = {split: [{**entry, "split": split} for entry in entries]
                     for split, entries in splits.items()}
    train_names = {entry["name"] for entry in split_entries["train"]}
    val_names = {entry["name"] for entry in split_entries["val"]}
    test_names = {entry["name"] for entry in split_entries["test"]}
    guard_fit_and_tuning(train_names, val_names, train_names, val_names, test_names)
    eval_intensities = json.loads((DATA / "eval_intensity.json").read_text(encoding="utf-8"))
    alpha_config = json.loads((ROOT / "configs" / "evaluation.json").read_text(encoding="utf-8"))
    alpha = float(alpha_config["dijkstra_load_aware_alpha"])
    train_cfg = json.loads((ROOT / "configs" / "training.json").read_text(encoding="utf-8"))
    low = float(train_cfg["intensity_distribution"]["minimum"])
    high = float(train_cfg["intensity_distribution"]["maximum"])
    episodes = {"train": (1 if args.quick else 3),
                "val": (1 if args.quick else 3),
                "test": (1 if args.quick else 10)}
    seed_lists = {
        "train": list(range(40_000, 40_000 + episodes["train"])),
        "val": list(EVAL_SEEDS[:episodes["val"]]),
        "test": list(EVAL_SEEDS[:episodes["test"]]),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {"features": list(FEATURE_NAMES),
                "label": "candidate's counterfactual backbone max utilization > 0.9 at any of the next five decision states after installation",
                "label_horizon_steps": 5,
                "counterfactual_rule": "subtract the rollout flow from its actual route when active, then add it to each candidate route using observed subsequent background loads",
                "split_by_graph": True, "training_graphs": sorted(train_names),
                "validation_graphs": sorted(val_names), "test_graphs": sorted(test_names),
                "training_intensity": {"kind": "log_uniform", "minimum": low, "maximum": high},
                "evaluation_seeds": list(EVAL_SEEDS), "shards": []}
    collected: dict[str, dict[str, np.ndarray]] = {"train": {}, "val": {}, "test": {}}
    for split in ("train", "val", "test"):
        if OUT.exists() and any((OUT / split).glob("*.npz")) and not args.force:
            raise SystemExit(f"RF data for {split} exists; pass --force")
        (OUT / split).mkdir(parents=True, exist_ok=True)
        rng = np.random.default_rng(5500 + len(split))
        for entry in split_entries[split]:
            if split == "test":
                assert entry["name"] in test_names and entry["name"] not in train_names | val_names
            rows = collect_graph(entry, split, episodes[split], seed_lists[split],
                                 eval_intensities, alpha, low, high, rng, args.quick)
            path = OUT / split / f"{entry['name']}.npz"
            np.savez_compressed(path, **rows)
            manifest["shards"].append({"path": str(path.relative_to(OUT)),
                                       "graph": entry["name"], "split": split,
                                       "candidate_rows": int(len(rows["labels"])),
                                       "positive_labels": int(rows["labels"].sum()),
                                       "bytes": path.stat().st_size})
            temporary = OUT / "manifest.json.tmp"
            temporary.write_text(json.dumps(manifest, indent=2) + "\n",
                                 encoding="utf-8")
            temporary.replace(OUT / "manifest.json")
            print(f"Collected RF labels for {split} graph {entry['name']}: "
                  f"{len(rows['labels'])} candidates, positives={int(rows['labels'].sum())}",
                  flush=True)
        pieces = [dict(np.load(OUT / shard["path"])) for shard in manifest["shards"]
                  if shard["split"] == split]
        collected[split] = {key: np.concatenate([piece[key] for piece in pieces])
                            for key in pieces[0]} if pieces else {}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n",
                                        encoding="utf-8")

    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import f1_score
    x_train, y_train = collected["train"]["features"], collected["train"]["labels"]
    x_val, y_val = collected["val"]["features"], collected["val"]["labels"]
    if len(np.unique(y_train)) < 2:
        raise RuntimeError("training RF dataset must include both congestion classes")
    parameter_grid = [
        {"n_estimators": 100, "max_depth": depth, "min_samples_leaf": leaf}
        for depth, leaf in ((None, 1), (12, 1), (8, 3), (16, 5))
    ]
    best = None
    selection_rows = []
    for params in parameter_grid:
        model = RandomForestClassifier(**params, class_weight="balanced_subsample",
                                       random_state=314159, n_jobs=-1)
        model.fit(x_train, y_train)
        prediction = model.predict(x_val)
        score = float(f1_score(y_val, prediction, zero_division=0))
        selection_rows.append({**params, "validation_f1": score})
        key = (score, -params["n_estimators"], -(params["max_depth"] or 10_000),
               -params["min_samples_leaf"])
        if best is None or key > best[0]:
            best = (key, model, params)
        print(f"RF validation tuning {params}: F1={score:.5f}", flush=True)
    assert best is not None
    model, params = best[1], best[2]
    import joblib
    MODEL.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL)

    train_majority = int(np.mean(y_train) >= 0.5)
    report = {"feature_names": list(FEATURE_NAMES), "selected_parameters": params,
              "selection_split": "val", "selection_metric": "candidate-level F1",
              "validation_tuning": selection_rows,
              "training_label_prevalence": float(np.mean(y_train)),
              "training_majority_label": train_majority,
              "split_metrics": {}, "per_graph_test": {},
              "test_data_used_for_tuning": False,
              "leakage_guard": "training fits use train graph shards; hyperparameter selection uses val graph shards; test graph shards are evaluated only after selection"}
    for split in ("train", "val", "test"):
        x, y = collected[split]["features"], collected[split]["labels"]
        predicted = model.predict(x)
        majority = np.full_like(y, train_majority)
        rule = (x[:, 0] > 0.9).astype(np.uint8)
        report["split_metrics"][split] = {
            "n_candidates": int(len(y)), "positive_labels": int(y.sum()),
            "positive_prevalence": float(np.mean(y)) if len(y) else 0.0,
            "rf": _metrics(y, predicted),
            "majority_class": _metrics(y, majority),
            "current_candidate_util_gt_0_9": _metrics(y, rule),
        }
        if split == "test":
            names = collected[split]["graph_name"]
            for name in sorted(set(names.tolist())):
                mask = names == name
                report["per_graph_test"][name] = {
                    "n_candidates": int(mask.sum()),
                    "positive_labels": int(y[mask].sum()),
                    "rf": _metrics(y[mask], predicted[mask]),
                    "majority_class": _metrics(y[mask], majority[mask]),
                    "current_candidate_util_gt_0_9": _metrics(y[mask], rule[mask]),
                }
    report_path = ROOT / "outputs" / "rf_metrics.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote RF model to {MODEL}", flush=True)
    for split, values in report["split_metrics"].items():
        print(f"RF {split}: {json.dumps(values, sort_keys=True)}", flush=True)
    print(f"Wrote {report_path}", flush=True)


if __name__ == "__main__":
    main()
