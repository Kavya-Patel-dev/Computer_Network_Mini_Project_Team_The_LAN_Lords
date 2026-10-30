"""Profile Day 5.1 replay/collation/update variants on a train-only graph."""
from __future__ import annotations

import csv
import json
import math
import statistics
import sys
import time
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from baselines.evaluation import load_graph, make_traffic
from env.network_env import NetworkEnvConfig, NetworkRoutingEnv
from env.traffic import PoissonTrafficGenerator
from models.data_guard import guard_graph_request, read_partitions
from models.dqn import DoubleDQNAgent, Transition
from models.obs import ModelState, ObservationWrapper
from train import memory_estimate

DATA = ROOT / "data"
OUT = ROOT / "outputs" / "day5_1"
PROFILE_SEED = 27001
CAPACITY = 25_000


def build_transitions(count: int = 1_200) -> list[Transition]:
    partitions = read_partitions(DATA / "splits.json")
    raw = next(row for row in partitions["train"] if row["name"] == "abilene")
    entry = {**raw, "split": "train"}
    guard_graph_request(entry, "train", partitions)
    graph = load_graph(entry, DATA)
    config = NetworkEnvConfig(max_steps=count + 1, intensity=0.05)
    stub = PoissonTrafficGenerator(sorted(graph.nodes), demand_mbps=1.0)
    topology = NetworkRoutingEnv(graph, config, traffic_generator=stub)
    traffic = make_traffic("poisson", entry, topology, 0.05, DATA)
    env = NetworkRoutingEnv(graph, config, traffic_generator=traffic)
    wrapper = ObservationWrapper(env, entry["name"])
    rng = np.random.default_rng(PROFILE_SEED)
    observation, _info = env.reset(seed=PROFILE_SEED)
    state = wrapper.process(observation)
    transitions: list[Transition] = []
    for _ in range(count):
        valid = np.flatnonzero(state.action_mask)
        action = int(rng.choice(valid)) if len(valid) else env.config.k_paths
        next_observation, raw_reward, terminated, truncated, _info = env.step(action)
        next_state = wrapper.process(next_observation)
        if action < env.config.k_paths and state.action_mask[action]:
            reward, _clipped = wrapper.scale_reward(raw_reward)
            transitions.append(Transition(state, action, reward, next_state,
                                          terminated, truncated))
        state = next_state
    env.close()
    return transitions


def new_agent(variant: dict) -> DoubleDQNAgent:
    torch.manual_seed(PROFILE_SEED)
    return DoubleDQNAgent(
        actions=4, batch_size=int(variant["batch_size"]),
        replay_capacity=CAPACITY, learning_starts=64, seed=PROFILE_SEED,
        store_tensor_replay=bool(variant["store_tensor_replay"]),
        use_custom_collate=bool(variant["use_custom_collate"]),
        reuse_duplicate_states=bool(variant["reuse_duplicate_states"]))


def measure_updates(transitions: list[Transition], variant: dict) -> dict:
    agent = new_agent(variant)
    for transition in transitions:
        agent.replay.add(transition)
    # Five warm-up calls settle PyTorch's one-time CPU paths. Exactly 100
    # subsequent optimizer updates are included in the measurements.
    for _ in range(5):
        if agent.update() is None:
            raise RuntimeError("profile replay did not reach learning threshold")
    losses: list[float] = []
    trace: list[dict[str, float]] = []
    total_started = time.perf_counter()
    for _ in range(100):
        loss = agent.update()
        if loss is None:
            raise RuntimeError("profile replay did not reach learning threshold")
        losses.append(float(loss))
        trace.append(dict(agent.last_update_timings_ms))
    wall_ms = (time.perf_counter() - total_started) * 1000.0
    timed_keys = tuple(agent.last_update_timings_ms)
    means = {key: statistics.mean(row[key] for row in trace) for key in timed_keys}
    phases = [key for key in timed_keys if key != "update_total"]
    means["unattributed"] = max(0.0, wall_ms / 100.0 - sum(means[key] for key in phases))
    means["wall_per_update"] = wall_ms / 100.0
    means["profiled_loss_median"] = statistics.median(losses)
    means["profiled_loss_max"] = max(losses)
    means["measured_optimizer_updates"] = len(trace)
    return means


def measure_training_rate(transitions: list[Transition], variant: dict,
                          steps: int = 1_000) -> dict:
    partitions = read_partitions(DATA / "splits.json")
    raw = next(row for row in partitions["train"] if row["name"] == "abilene")
    entry = {**raw, "split": "train"}
    guard_graph_request(entry, "train", partitions)
    graph = load_graph(entry, DATA)
    config = NetworkEnvConfig(max_steps=steps + 1, intensity=0.05)
    stub = PoissonTrafficGenerator(sorted(graph.nodes), demand_mbps=1.0)
    topology = NetworkRoutingEnv(graph, config, traffic_generator=stub)
    traffic = make_traffic("poisson", entry, topology, 0.05, DATA)
    env = NetworkRoutingEnv(graph, config, traffic_generator=traffic)
    wrapper = ObservationWrapper(env, entry["name"])
    agent = new_agent(variant)
    for transition in transitions:
        agent.replay.add(transition)
    rng = np.random.default_rng(PROFILE_SEED + 1)
    observation, _info = env.reset(seed=PROFILE_SEED + 1)
    state = wrapper.process(observation)
    started = time.perf_counter()
    losses = []
    update_every = int(variant["update_every"])
    interval = max(1, steps // 10)
    for step in range(1, steps + 1):
        action = agent.select_action(state, 0.05, rng)
        next_observation, raw_reward, terminated, truncated, _info = env.step(action)
        next_state = wrapper.process(next_observation)
        if action < env.config.k_paths and state.action_mask[action]:
            reward, _ = wrapper.scale_reward(raw_reward)
            agent.replay.add(Transition(state, action, reward, next_state,
                                        terminated, truncated))
        state = next_state
        if step % update_every == 0:
            loss = agent.update()
            if loss is not None:
                losses.append(loss)
        if step % interval == 0 or step == steps:
            elapsed = time.perf_counter() - started
            eta = max(0.0, (steps - step) * elapsed / step / 60.0)
            print(f"[{variant['name']}] step {step} / {steps} | val loss n/a | "
                  f"ETA {eta:.2f} min", flush=True)
    elapsed = time.perf_counter() - started
    env.close()
    return {"seconds": elapsed, "steps_per_second": steps / elapsed,
            "updates": len(losses),
            "median_huber": statistics.median(losses) if losses else math.nan}


def main() -> None:
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    base = {
        "store_tensor_replay": False, "use_custom_collate": False,
        "reuse_duplicate_states": False, "batch_size": 64,
        "update_every": 4,
    }
    variants = [
        {**base, "name": "day4_baseline"},
        {**base, "name": "ready_tensors_custom_collate",
         "store_tensor_replay": True, "use_custom_collate": True},
        {**base, "name": "plus_duplicate_state_reuse",
         "store_tensor_replay": True, "use_custom_collate": True,
         "reuse_duplicate_states": True},
        {**base, "name": "batch128_every4",
         "store_tensor_replay": True, "use_custom_collate": True,
         "reuse_duplicate_states": True, "batch_size": 128},
        {**base, "name": "batch64_every8",
         "store_tensor_replay": True, "use_custom_collate": True,
         "reuse_duplicate_states": True, "update_every": 8},
    ]
    partitions = read_partitions(DATA / "splits.json")
    train_entries = [dict(row, split="train") for row in partitions["train"]]
    try:
        import psutil
        physical_ram = psutil.virtual_memory().total
    except ImportError:
        physical_ram = 0
    print("Replay memory estimate (12 processes, 50,000 entries each):", flush=True)
    for include_history in (False, True):
        estimate = memory_estimate(train_entries, capacity=50_000,
                                   include_history=include_history,
                                   history_length=4)
        total = float(estimate["estimated_bytes"]) * 12
        print(json.dumps({
            "history_snapshots": include_history,
            "bytes_per_transition": estimate["bytes_per_transition"],
            "projected_12_process_GiB": total / 1024**3,
            "physical_RAM_GiB": physical_ram / 1024**3 if physical_ram else None,
            "physical_RAM_fraction": total / physical_ram if physical_ram else None,
        }, sort_keys=True), flush=True)
    transitions = build_transitions()
    if len(transitions) < 128:
        raise RuntimeError(f"too few routed profiling transitions: {len(transitions)}")
    rows = []
    for variant in variants:
        print(f"profile variant: {variant['name']} | 100 optimizer updates", flush=True)
        update_stats = measure_updates(transitions, variant)
        print(f"profile variant: {variant['name']} | 1000 live training steps", flush=True)
        rate_stats = measure_training_rate(transitions, variant)
        rows.append({"name": variant["name"], **update_stats, **rate_stats})
        print(json.dumps(rows[-1], sort_keys=True), flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "learner_profile.json").write_text(json.dumps(rows, indent=2),
                                              encoding="utf-8")
    with (OUT / "learner_profile.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


if __name__ == "__main__":
    main()
