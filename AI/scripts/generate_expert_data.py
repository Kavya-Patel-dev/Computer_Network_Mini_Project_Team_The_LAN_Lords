"""Write 200k+ compact, replayable candidate-action expert observations."""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from baselines.evaluation import load_graph, make_traffic
from baselines.policies import choose_decision
from env.network_env import NetworkEnvConfig, NetworkRoutingEnv
from env.traffic import PoissonTrafficGenerator

DATA = ROOT / "data"
OUT = DATA / "expert"
CONFIG_PATH = ROOT / "configs" / "training.json"
CHUNK = 1000
TRAFFIC_TYPES = ("poisson", "gravity", "hotspot", "sndlib")
EXPERTS = ("dijkstra_load_aware_k", "greedy_min_util")
OBS_KEYS = ("node_features", "edge_features", "flow_features", "candidate_paths",
            "action_mask", "edge_index", "history_nodes", "history_edges")


def pack_observations(obs_rows: list[dict[str, np.ndarray]]) -> dict[str, np.ndarray]:
    return {f"obs_{key}": np.stack([row[key] for row in obs_rows]) for key in OBS_KEYS}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=200_000)
    parser.add_argument("--quick", action="store_true", help="write a small development shard")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    target_steps = 2_000 if args.quick else args.steps
    if target_steps <= 0:
        raise SystemExit("--steps must be positive")
    if OUT.exists() and any(OUT.iterdir()) and not args.force:
        raise SystemExit(f"{OUT} is nonempty; pass --force to replace expert shards")
    OUT.mkdir(parents=True, exist_ok=True)
    shard_dir = OUT / "shards"
    shard_dir.mkdir(exist_ok=True)
    for old in shard_dir.glob("*.npz"):
        old.unlink()

    training = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    low = float(training["intensity_distribution"]["minimum"])
    high = float(training["intensity_distribution"]["maximum"])
    eval_seeds = set(map(int, training["evaluation_seeds"]))
    splits = json.loads((DATA / "splits.json").read_text(encoding="utf-8"))
    train_entries = [{**row, "split": "train"} for row in splits["train"]]
    assert all(entry["split"] == "train" for entry in train_entries)
    rng = np.random.default_rng(20261011)
    alpha_config_path = ROOT / "configs" / "evaluation.json"
    alpha_config = json.loads(alpha_config_path.read_text(encoding="utf-8")) if alpha_config_path.exists() else {}
    alpha = float(alpha_config.get("dijkstra_load_aware_alpha", 1.0))

    per_graph = [target_steps // len(train_entries)] * len(train_entries)
    for i in range(target_steps % len(train_entries)):
        per_graph[i] += 1
    manifest = {
        "format": "npz shards; one complete Day 2 observation per expert decision",
        "split_guard": "train only",
        "total_steps_target": target_steps,
        "total_steps_written": 0,
        "intensity_distribution": {"kind": "log_uniform", "minimum": low, "maximum": high},
        "evaluation_seeds_forbidden": sorted(eval_seeds),
        "seed_start": 20_000,
        "alpha": alpha,
        "experts": list(EXPERTS),
        "candidate_order": "environment-shuffled candidate order; action indices align with obs_candidate_paths",
        "observation_keys": list(OBS_KEYS),
        "shards": [],
        "per_graph_steps": {},
        "action_index_distribution": {},
        "expert_agreement_rate": None,
        "expert_agreement_counts": {"agree": 0, "compared": 0},
    }
    action_counts = Counter()
    policy_counts = Counter()
    episode_seed = 20_000
    global_step = 0

    def save_manifest() -> None:
        compared_count = manifest["expert_agreement_counts"]["compared"]
        agree_count = manifest["expert_agreement_counts"]["agree"]
        manifest["expert_agreement_rate"] = (agree_count / compared_count
                                             if compared_count else 0.0)
        manifest["action_index_distribution"] = {
            str(action): count for action, count in sorted(action_counts.items())}
        manifest["expert_policy_step_distribution"] = dict(policy_counts)
        temporary = OUT / "manifest.json.tmp"
        temporary.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        temporary.replace(OUT / "manifest.json")

    for entry, graph_target in zip(train_entries, per_graph):
        graph = load_graph(entry, DATA)
        base_graph = graph
        graph_steps = 0
        pending: list[dict] = []
        shard_index = 0
        while graph_steps < graph_target:
            seed = episode_seed
            episode_seed += 1
            if seed in eval_seeds:
                raise AssertionError("evaluation seeds must never be used for expert training")
            intensity = math.exp(float(rng.uniform(math.log(low), math.log(high))))
            available = [kind for kind in TRAFFIC_TYPES
                         if kind != "sndlib" or entry["source"] == "sndlib"]
            kind = available[int(rng.integers(len(available)))]
            config = NetworkEnvConfig(max_steps=500, intensity=intensity)
            stub = PoissonTrafficGenerator(sorted(graph.nodes), demand_mbps=1.0)
            topology = NetworkRoutingEnv(graph, config, traffic_generator=stub)
            traffic = make_traffic(kind, entry, topology, intensity, DATA)
            env = NetworkRoutingEnv(base_graph, config, traffic_generator=traffic)
            observation, _info = env.reset(seed=seed)
            observations: list[dict[str, np.ndarray]] = []
            actions: list[int] = []
            rewards: list[float] = []
            chosen_names: list[str] = []
            seeds: list[int] = []
            intensities: list[float] = []
            for _step in range(min(500, graph_target - graph_steps)):
                if env.flow is None:
                    raise RuntimeError("training rollout lost its current request")
                ordered_paths = tuple(tuple(path) for path in env._paths.paths)
                for i, path in enumerate(ordered_paths):
                    encoded = tuple(env.nodes[int(index)] for index in
                                    observation["candidate_paths"][i, :len(path)])
                    if encoded != path:
                        raise AssertionError("candidate index differs from observation path order")
                k_decision = choose_decision("dijkstra_load_aware_k", env, rng, alpha=alpha)
                greedy_decision = choose_decision("greedy_min_util", env, rng, alpha=alpha)
                manifest["expert_agreement_counts"]["compared"] += 1
                if k_decision.action == greedy_decision.action:
                    manifest["expert_agreement_counts"]["agree"] += 1
                selected_name = EXPERTS[global_step % 2]
                decision = k_decision if selected_name == "dijkstra_load_aware_k" else greedy_decision
                if not observation["action_mask"][decision.action]:
                    raise AssertionError("expert selected an action masked by its observation")
                observations.append({key: observation[key].copy() for key in OBS_KEYS})
                actions.append(int(decision.action))
                chosen_names.append(selected_name)
                seeds.append(seed)
                intensities.append(intensity)
                observation, reward, _terminated, _truncated, _info = env.step(decision.action)
                rewards.append(float(reward))
                action_counts[int(decision.action)] += 1
                policy_counts[selected_name] += 1
                graph_steps += 1
                global_step += 1
                if len(observations) >= CHUNK:
                    arrays = pack_observations(observations)
                    arrays.update(action=np.asarray(actions, dtype=np.int16),
                                  reward=np.asarray(rewards, dtype=np.float32),
                                  graph_name=np.asarray([entry["name"]] * len(actions), dtype="U64"),
                                  seed=np.asarray(seeds, dtype=np.int64),
                                  intensity=np.asarray(intensities, dtype=np.float32),
                                  expert=np.asarray(chosen_names, dtype="U32"),
                                  edge_index_static=observations[0]["edge_index"])
                    shard_path = shard_dir / f"{entry['name']}_{shard_index:04d}.npz"
                    np.savez_compressed(shard_path, **arrays)
                    manifest["shards"].append({"path": str(shard_path.relative_to(OUT)),
                                               "graph": entry["name"],
                                               "steps": len(actions),
                                               "bytes": shard_path.stat().st_size})
                    manifest["total_steps_written"] += len(actions)
                    observations.clear(); actions.clear(); rewards.clear()
                    chosen_names.clear(); seeds.clear(); intensities.clear()
                    shard_index += 1
                if _truncated:
                    break
            if observations:
                arrays = pack_observations(observations)
                arrays.update(action=np.asarray(actions, dtype=np.int16),
                              reward=np.asarray(rewards, dtype=np.float32),
                              graph_name=np.asarray([entry["name"]] * len(actions), dtype="U64"),
                              seed=np.asarray(seeds, dtype=np.int64),
                              intensity=np.asarray(intensities, dtype=np.float32),
                              expert=np.asarray(chosen_names, dtype="U32"),
                              edge_index_static=observations[0]["edge_index"])
                shard_path = shard_dir / f"{entry['name']}_{shard_index:04d}.npz"
                np.savez_compressed(shard_path, **arrays)
                manifest["shards"].append({"path": str(shard_path.relative_to(OUT)),
                                           "graph": entry["name"],
                                           "steps": len(actions),
                                           "bytes": shard_path.stat().st_size})
                manifest["total_steps_written"] += len(actions)
                shard_index += 1
        manifest["per_graph_steps"][entry["name"]] = graph_steps
        save_manifest()
        print(f"Generated expert data for train graph {entry['name']}: {graph_steps} steps",
              flush=True)

    compared = manifest["expert_agreement_counts"]["compared"]
    agree = manifest["expert_agreement_counts"]["agree"]
    manifest["total_steps_target"] = target_steps
    save_manifest()
    print(f"Wrote {manifest['total_steps_written']} expert decisions to {OUT}", flush=True)
    print(f"Expert agreement: {agree}/{compared} = {manifest['expert_agreement_rate']:.4f}", flush=True)


if __name__ == "__main__":
    main()
