"""Isolated 3,000-step Day 5.3/5.4 model-variant smoke run."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
import sys
import time
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from models.behavior_cloning import (EXPERT_POLICY, ExpertExample,
                                     read_expert_indices)
from models.data_guard import read_partitions
from models.day5_temporal import TemporalObservationWrapper
from models.day5_variants import (VariantDQNAgent, VariantTransition,
                                  initialize_from_checkpoint,
                                  planned_update_count)
from models.obs import ObservationWrapper


def canonical_signature(spec: dict) -> str:
    identity = {key: spec[key] for key in ("stage", "seed", "steps", "overrides")}
    payload = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def epsilon_at(step: int, total_steps: int) -> float:
    anneal_steps = max(1, int(total_steps * 0.30))
    fraction = min(1.0, max(0.0, step / anneal_steps))
    return 0.10 + fraction * (0.02 - 0.10)


def _fixed_expert_batch(train_entries: list[dict], partitions: dict,
                        count: int = 32, include_history: bool = False
                        ) -> list[ExpertExample]:
    """Read one fixed dijkstra_load_aware_k minibatch from a train shard."""
    train_names = {row["name"] for row in train_entries}
    holdout_names = {row["name"] for row in partitions["test"]}
    expert_root = ROOT / "data" / "expert"
    _manifest, indices = read_expert_indices(
        expert_root, train_names, holdout_names, expert_policy=EXPERT_POLICY)
    by_shard: dict[str, list] = {}
    for index in indices:
        by_shard.setdefault(index.shard, []).append(index)
    if not by_shard:
        raise RuntimeError("no permitted expert minibatch exists")
    shard = sorted(by_shard)[0]
    chosen = by_shard[shard][:count]

    import train
    selected_graph = chosen[0].graph
    entry = next(row for row in train_entries if row["name"] == selected_graph)
    graph = train.safe_graph_load(entry, "train", partitions)
    env = train.make_training_env(entry, graph, "poisson", 0.05, 500)
    wrapper = (TemporalObservationWrapper(env, selected_graph) if include_history
               else ObservationWrapper(env, selected_graph))
    examples: list[ExpertExample] = []
    with np.load(expert_root / shard, allow_pickle=False) as data:
        static_edge_index = np.asarray(env.edge_index, dtype=np.int64)
        for index in chosen:
            if index.graph != selected_graph:
                continue
            raw = {
                key: data[f"obs_{key}"][index.row]
                for key in ("node_features", "edge_features", "flow_features",
                            "candidate_paths", "action_mask", "edge_index",
                            "history_nodes", "history_edges")
            }
            if not np.array_equal(raw["edge_index"], static_edge_index):
                raise ValueError("expert edge order differs from the guarded train topology")
            state = wrapper.process(raw)
            if index.action < 4 and state.action_mask[index.action]:
                examples.append(ExpertExample(state, index.action,
                                              index.graph, index.seed))
            if len(examples) >= count:
                break
    env.close()
    if not examples:
        raise RuntimeError("fixed expert minibatch has no valid actions")
    return examples


def state_nbytes(state) -> int:
    arrays = (state.node_features, state.edge_attr, state.flow_features,
              state.candidate_paths, state.candidate_features, state.action_mask,
              state.history_node_features, state.history_edge_attr)
    return sum(int(array.nbytes) for array in arrays if array is not None)


def replay_transition_nbytes(transition) -> int:
    return state_nbytes(transition.state) + state_nbytes(transition.next_state)


def run(spec: dict) -> dict:
    seed, total_steps = int(spec["seed"]), int(spec["steps"])
    overrides = dict(spec.get("overrides", {}))
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    import train
    partitions = read_partitions(ROOT / "data" / "splits.json")
    train_entries = [dict(row, split="train") for row in partitions["train"]]
    if not train_entries:
        raise RuntimeError("train split is empty")
    flags = dict(overrides.get("flags", {}))
    load_bc = bool(overrides.get("load_bc", True))
    bc_weight = float(overrides.get("auxiliary_bc_weight", 0.1 if load_bc else 0.0))
    agent = VariantDQNAgent(
        flags=flags, actions=4, learning_rate=1e-4, gamma=0.95, tau=0.002,
        replay_capacity=25_000, batch_size=64, learning_starts=2_000,
        seed=seed, n_step=int(overrides.get("n_step", 1)),
        prioritized=bool(overrides.get("prioritized_replay", False)),
        total_updates=planned_update_count(total_steps),
        auxiliary_bc_weight=bc_weight,
        gradient_clip_norm=10.0,
    )
    init_info = initialize_from_checkpoint(
        agent.online, str(ROOT / "runs" / "day5" / "bc_init.pt"),
        load_bc=load_bc)
    agent.target.load_state_dict(agent.online.state_dict())
    agent.target.eval()
    expert_batch = (_fixed_expert_batch(
        train_entries, partitions,
        include_history=bool(flags.get("gru_history", False)))
        if bc_weight else None)

    rng = np.random.default_rng(seed)
    env = wrapper = observation = active_entry = None
    episode_id = -1
    step_in_episode = 0
    losses: list[float] = []
    q_abs_values: list[float] = []
    replay_state_bytes: list[int] = []
    started = time.perf_counter()
    progress_interval = max(250, total_steps // 6)
    run_dir = Path(spec["run_dir"])
    output_dir = Path(spec["output_dir"])
    run_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = run_dir / "latest.pt"
    print(f"seed={seed}; train graphs available={len(train_entries)}; "
          f"replay capacity=25000; flags={json.dumps(flags, sort_keys=True)}; "
          f"initialization={init_info['source']} copied="
          f"{init_info['copied_tensors']} tensors; "
          f"fresh tensors={len(init_info['fresh_parameter_tensors'])}; "
          f"history dtype={'float16' if agent.replay.compact_history else 'float32'}; "
          f"expert BC weight={bc_weight:.3f}", flush=True)

    try:
        for step in range(1, total_steps + 1):
            if env is None or observation is None or step_in_episode >= 500:
                if env is not None:
                    env.close()
                episode_id += 1
                active_entry = train_entries[int(rng.integers(len(train_entries)))]
                graph = train.safe_graph_load(active_entry, "train", partitions)
                available = ["poisson", "gravity", "hotspot"]
                if active_entry["source"] == "sndlib":
                    available.append("sndlib")
                generator = available[int(rng.integers(len(available)))]
                intensity = float(np.exp(rng.uniform(math.log(0.01), math.log(0.30))))
                env = train.make_training_env(active_entry, graph, generator,
                                              intensity, max_steps=500)
                wrapper = (
                    TemporalObservationWrapper(env, active_entry["name"])
                    if bool(flags.get("gru_history", False))
                    else ObservationWrapper(env, active_entry["name"])
                )
                observation, _info = env.reset(
                    seed=int(rng.integers(20_000, 1_000_000)))
                step_in_episode = 0

            state = wrapper.process(observation)
            epsilon = epsilon_at(step - 1, total_steps)
            action = agent.select_action(state, epsilon, rng)
            next_observation, raw_reward, terminated, truncated, _info = env.step(action)
            scaled_reward, _clipped = wrapper.scale_reward(raw_reward)
            next_state = wrapper.process(next_observation)
            if action < 4 and state.action_mask[action]:
                agent.add_transition(VariantTransition(
                    state, action, scaled_reward, next_state,
                    bool(terminated), bool(truncated)), episode_id)
                replay_state_bytes.append(state_nbytes(state)
                                          + state_nbytes(next_state))
            elif terminated or truncated:
                agent.end_episode(episode_id, next_state,
                                  terminated=bool(terminated),
                                  truncated=bool(truncated))
            step_in_episode += 1
            observation = next_observation

            if step % 4 == 0 and len(agent.replay) >= agent.learning_starts:
                loss = agent.update(expert_batch)
                if loss is not None:
                    if not math.isfinite(loss):
                        raise FloatingPointError("nonfinite smoke-run loss")
                    losses.append(loss)
                    q_abs_values.append(agent.last_q_abs_max)

            if step % 1_000 == 0 or step == total_steps:
                agent.save(str(checkpoint_path), {
                    "step": step, "seed": seed, "flags": flags,
                    "source": "Day 5.2 BC initialization" if load_bc else "random",
                })
            if step % progress_interval == 0 or step == total_steps:
                elapsed = time.perf_counter() - started
                eta = max(0.0, (total_steps - step) * elapsed / step / 60.0)
                print(f"step {step} / {total_steps} | val loss n/a | ETA {eta:.2f} min",
                      flush=True)
    finally:
        if env is not None:
            env.close()

    elapsed = time.perf_counter() - started
    if not checkpoint_path.exists():
        agent.save(str(checkpoint_path), {"step": total_steps, "seed": seed})
    # Verify the exact final checkpoint/config reload without reading any holdout graph.
    final_state = wrapper.process(observation)
    expected_q = agent.q_values(final_state)
    reloaded = VariantDQNAgent(
        flags=flags, actions=4, learning_rate=1e-4, gamma=0.95, tau=0.002,
        replay_capacity=25_000, batch_size=64, learning_starts=2_000,
        seed=seed + 1, n_step=int(overrides.get("n_step", 1)),
        prioritized=bool(overrides.get("prioritized_replay", False)),
        total_updates=planned_update_count(total_steps),
        auxiliary_bc_weight=bc_weight,
    )
    reloaded.load(str(checkpoint_path))
    observed_q = reloaded.q_values(final_state)
    valid = np.isfinite(expected_q) & np.isfinite(observed_q)
    checkpoint_max_abs_diff = (float(np.max(np.abs(expected_q[valid] - observed_q[valid])))
                               if valid.any() else 0.0)
    if checkpoint_max_abs_diff > 1e-6:
        raise AssertionError(f"checkpoint Q mismatch: {checkpoint_max_abs_diff}")
    stored_transitions = [row for row in agent.replay.items[:len(agent.replay)]
                          if row is not None]
    stored_bytes = [replay_transition_nbytes(row) for row in stored_transitions]
    mean_stored_bytes = statistics.mean(stored_bytes) if stored_bytes else 0.0
    summary = {
        "name": spec["name"], "signature": canonical_signature(spec),
        "seed": seed, "steps": total_steps, "updates": agent.updates,
        "elapsed_seconds": elapsed,
        "steps_per_second": total_steps / max(elapsed, 1e-12),
        "last_val_loss": None, "best_val_loss": None,
        "loss_count": len(losses), "loss_min": min(losses) if losses else None,
        "loss_median": statistics.median(losses) if losses else None,
        "loss_max": max(losses) if losses else None,
        "all_losses_finite": bool(all(math.isfinite(value) for value in losses)),
        "q_abs_min": min(q_abs_values) if q_abs_values else None,
        "q_abs_max": max(q_abs_values) if q_abs_values else None,
        "checkpoint_q_max_abs_diff": checkpoint_max_abs_diff,
        "copied_tensors": init_info["copied_tensors"],
        "fresh_parameter_tensors": init_info["fresh_parameter_tensors"],
        "bc_initialized": load_bc, "auxiliary_bc_weight": bc_weight,
        "replay_capacity": 25_000, "replay_size": len(agent.replay),
        "mean_transition_state_bytes": (statistics.mean(replay_state_bytes)
                                         if replay_state_bytes else 0),
        "peak_transition_state_bytes": max(replay_state_bytes, default=0),
        "mean_stored_transition_bytes": mean_stored_bytes,
        "projected_replay_payload_mib_at_capacity": (
            mean_stored_bytes * 25_000 / (1024**2)),
        "history_storage_dtype": ("float16" if agent.replay.compact_history
                                  else "float32"),
        "flags": flags, "run_dir": str(run_dir), "output_dir": str(output_dir),
        "checkpoint": str(checkpoint_path),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2),
                                                encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--quick", action="store_true",
                        help="run a 300-step bounded smoke for code-path checks")
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    if args.quick:
        spec["steps"] = min(300, int(spec.get("steps", 300)))
    run(spec)


if __name__ == "__main__":
    main()
