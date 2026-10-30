"""Profile 100 Day 4 training decisions by pipeline component."""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from models.dqn import DoubleDQNAgent, Transition
from models.obs import ObservationWrapper
from train import CONFIG, DATA, make_training_env, safe_graph_load


def profile(threads: int, update_every: int, measured_steps: int = 100,
            graph_name: str = "abilene") -> dict[str, float]:
    seed = 93817
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(threads)
    partitions = json.loads((DATA / "splits.json").read_text(encoding="utf-8"))
    entry = next(dict(row, split="train") for row in partitions["train"]
                 if row["name"] == graph_name)
    graph = safe_graph_load(entry, "train", partitions)
    env = make_training_env(entry, graph, "poisson", 0.15, max_steps=500)
    wrapper = ObservationWrapper(env, entry["name"])
    observation, _ = env.reset(seed=seed)
    agent = DoubleDQNAgent(
        actions=4, lr=CONFIG["learning_rate"], gamma=CONFIG["gamma"],
        tau=CONFIG["soft_target_tau"], batch_size=64, replay_capacity=2000,
        learning_starts=64, seed=seed,
        use_third_layer=CONFIG["architecture"]["optional_third_layer"],
    )
    rng = np.random.default_rng(seed)

    # Seed the replay just enough to exercise the same batch size during the
    # measured window. This setup is excluded from the 100-step timings.
    for _ in range(64):
        state = wrapper.process(observation)
        valid = np.flatnonzero(state.action_mask)
        action = int(rng.choice(valid)) if len(valid) else env.config.k_paths
        next_observation, reward, terminated, truncated, _ = env.step(action)
        next_state = wrapper.process(next_observation)
        if action < env.config.k_paths and state.action_mask[action]:
            agent.replay.add(Transition(state, action,
                                        wrapper.scale_reward(reward)[0], next_state,
                                        terminated, truncated))
        observation = next_observation
    observation, _ = env.reset(seed=seed + 1)

    component = {name: 0.0 for name in
                 ("wrapper", "action_forward", "environment", "replay_sampling", "optimizer_update")}
    sample_time = 0.0
    original_sample = agent.replay.sample

    def timed_sample(count: int):
        nonlocal sample_time
        start = time.perf_counter()
        result = original_sample(count)
        sample_time += time.perf_counter() - start
        return result

    agent.replay.sample = timed_sample
    started = time.perf_counter()
    for step in range(1, measured_steps + 1):
        begin = time.perf_counter()
        state = wrapper.process(observation)
        component["wrapper"] += time.perf_counter() - begin

        begin = time.perf_counter()
        q_values = agent.q_values(state)
        valid = np.flatnonzero(state.action_mask)
        action = int(valid[np.argmax(q_values[valid])]) if len(valid) else env.config.k_paths
        component["action_forward"] += time.perf_counter() - begin

        begin = time.perf_counter()
        next_observation, reward, terminated, truncated, _ = env.step(action)
        component["environment"] += time.perf_counter() - begin

        begin = time.perf_counter()
        next_state = wrapper.process(next_observation)
        if action < env.config.k_paths and state.action_mask[action]:
            agent.replay.add(Transition(state, action,
                                        wrapper.scale_reward(reward)[0], next_state,
                                        terminated, truncated))
        component["wrapper"] += time.perf_counter() - begin
        observation = next_observation

        if step % update_every == 0:
            begin = time.perf_counter()
            before_sample = sample_time
            agent.update()
            update_wall = time.perf_counter() - begin
            sampled = sample_time - before_sample
            component["replay_sampling"] += sampled
            component["optimizer_update"] += max(0.0, update_wall - sampled)

    elapsed = time.perf_counter() - started
    result = {
        "threads": float(threads),
        "graph": graph_name,
        "update_every": float(update_every),
        "steps": float(measured_steps),
        "steps_per_second": measured_steps / elapsed,
        "elapsed_s": elapsed,
        "updates": float(agent.updates),
        **{f"{key}_ms_per_step": value * 1000 / measured_steps
           for key, value in component.items()},
        **{f"{key}_fraction": value / elapsed for key, value in component.items()},
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--threads", type=int, choices=(1, 4, 8), default=4)
    parser.add_argument("--update-every", type=int, choices=(1, 4), default=4)
    parser.add_argument("--graph", default="abilene")
    args = parser.parse_args()
    result = profile(args.threads, args.update_every, graph_name=args.graph)
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
