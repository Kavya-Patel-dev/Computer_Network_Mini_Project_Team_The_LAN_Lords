"""Day 4 GATv2 Double-DQN training; reads train and validation topologies only."""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
import sys
import time
from pathlib import Path

import numpy as np
import torch
from torch.utils.tensorboard import SummaryWriter

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from baselines import evaluation as day3
from baselines.evaluation import load_graph, make_traffic
from env.network_env import NetworkEnvConfig, NetworkRoutingEnv
from env.traffic import PoissonTrafficGenerator
from models.data_guard import guard_graph_request, read_partitions
from models.dqn import DoubleDQNAgent, Transition
from models.harness import AgentPolicyAdapter, run_agent_episode
from models.obs import ObservationWrapper

DATA = ROOT / "data"
RUNS = ROOT / "runs" / "day4"
OUTPUTS = ROOT / "outputs" / "day4"
CONFIG = json.loads((ROOT / "configs" / "day4_agent.json").read_text(encoding="utf-8"))
EVAL_INTENSITIES = json.loads((DATA / "eval_intensity.json").read_text(encoding="utf-8"))


def configure_reproducibility(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)
    # The 100-step CPU profile showed one intra-op thread is fastest for this
    # small graph workload; 4 and 8 threads both reduced throughput.
    torch.set_num_threads(1)


def safe_graph_load(entry: dict, split: str,
                    partitions: dict[str, list[dict]]) -> object:
    guard_graph_request(entry, split, partitions)
    return load_graph({**entry, "split": split}, DATA)


def make_training_env(entry: dict, graph, generator: str, intensity: float,
                      max_steps: int = 500) -> NetworkRoutingEnv:
    config = NetworkEnvConfig(max_steps=max_steps, intensity=float(intensity))
    stub = PoissonTrafficGenerator(sorted(graph.nodes), demand_mbps=1.0)
    topology = NetworkRoutingEnv(graph, config, traffic_generator=stub)
    traffic = make_traffic(generator, entry, topology, float(intensity), DATA)
    return NetworkRoutingEnv(graph, config, traffic_generator=traffic)


def epsilon_at(step: int, total_steps: int) -> float:
    anneal_steps = max(1, int(total_steps * CONFIG["epsilon_fraction"]))
    fraction = min(1.0, max(0.0, step / anneal_steps))
    return float(CONFIG["epsilon_start"] + fraction *
                 (CONFIG["epsilon_end"] - CONFIG["epsilon_start"]))


def validation_score(agent: DoubleDQNAgent,
                     entries: list[dict],
                     partitions: dict[str, list[dict]],
                     seeds: tuple[int, ...] = (30000, 30001)) -> tuple[float, float, list[dict]]:
    results = []
    for raw_entry in entries:
        entry = {**raw_entry, "split": "val"}
        graph = safe_graph_load(entry, "val", partitions)
        setting = EVAL_INTENSITIES[entry["name"]]["generators"]["poisson"]
        for seed in seeds:
            row, _stats = run_agent_episode(
                entry, graph, "poisson", float(setting["intensity"]),
                seed=seed, scenario="normal", alpha=4.0, rf_model=None,
                max_steps=500, warmup=100, data_root=DATA, agent=agent)
            results.append(row)
    loss = statistics.mean(row["mean_packet_loss"] for row in results) if results else math.inf
    overload = statistics.mean(row["fraction_steps_over_0_9"] for row in results) if results else 1.0
    return float(loss), float(overload), results


def memory_estimate(train_entries: list[dict], actions: int = 4,
                    capacity: int = 50_000, include_history: bool = False,
                    history_length: int = 4) -> dict[str, float | int]:
    max_routers = max(int(row["num_nodes"]) for row in train_entries)
    max_hosts = max(4, math.ceil(max_routers * 0.5))
    max_nodes = max_routers + max_hosts
    max_links = max(int(row["num_edges"]) for row in train_entries) + max_hosts
    # Two states per replay item; edge_index is topology-cached and shared.
    state_bytes = (max_nodes * 6 * 4 + max_links * 10 * 4
                   + actions * max_nodes * 4 + actions * 6 * 4
                   + 7 * 4 + actions)
    history_per_transition = (2 * history_length
                              * (max_nodes * 6 + max_links * 5) * 4)
    payload = (state_bytes * 2 + (history_per_transition if include_history else 0)) * capacity
    # NumPy/tensor headers and Python dataclasses/lists add roughly 1,450 B
    # per transition. This is estimated separately from the measured payload.
    estimate = payload + capacity * 1_450
    return {"max_nodes": max_nodes, "max_undirected_edges": max_links,
            "payload_bytes": payload, "estimated_bytes": estimate,
            "estimated_mib": estimate / (1024 * 1024),
            "bytes_per_transition": estimate / capacity,
            "history_bytes_per_transition": (history_per_transition
                                               if include_history else 0)}


def write_curve_plots(history: dict[str, list[float]], stage: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    (OUTPUTS / "plots").mkdir(parents=True, exist_ok=True)
    for key, title, file_name in (
            ("scaled_rewards", "Scaled training reward", f"{stage}_reward.png"),
            ("losses", "Double-DQN Huber loss", f"{stage}_loss.png")):
        values = history.get(key, [])
        fig, ax = plt.subplots(figsize=(9, 4))
        if values:
            window = max(1, min(500, len(values) // 100 or 1))
            smooth = np.convolve(np.asarray(values), np.ones(window) / window,
                                 mode="valid")
            ax.plot(np.arange(len(smooth)) + window - 1, smooth, linewidth=0.8)
        ax.set(title=title, xlabel="environment step" if key == "scaled_rewards" else "optimizer update",
               ylabel="reward" if key == "scaled_rewards" else "loss")
        ax.grid(True, alpha=0.25)
        fig.tight_layout()
        fig.savefig(OUTPUTS / "plots" / file_name, dpi=140)
        plt.close(fig)


def _save_checkpoint(agent: DoubleDQNAgent, path: Path, step: int,
                     stage: str, val_loss: float | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    agent.save(str(path), {"step": step, "stage": stage,
                           "val_loss": val_loss,
                           "update_count": agent.updates,
                           "architecture": CONFIG["architecture"]})


def run_training(stage: str, total_steps: int, seed: int,
                 partitions: dict[str, list[dict]], quick: bool = False,
                 resume_checkpoint: Path | None = None) -> dict:
    configure_reproducibility(seed)
    train_entries = [dict(row, split="train") for row in partitions["train"]]
    val_entries = [dict(row, split="val") for row in partitions["val"]]
    if stage == "A":
        train_entries = [row for row in train_entries if row["name"] == "abilene"]
        if len(train_entries) != 1:
            raise RuntimeError("Stage A requires the train-split abilene graph")
    graphs = {row["name"]: safe_graph_load(row, "train", partitions)
              for row in train_entries}
    agent = DoubleDQNAgent(
        actions=4, lr=CONFIG["learning_rate"], gamma=CONFIG["gamma"],
        tau=CONFIG["soft_target_tau"], batch_size=CONFIG["batch_size"],
        replay_capacity=CONFIG["replay_capacity"],
        learning_starts=CONFIG["learning_starts"], seed=seed,
        use_third_layer=CONFIG["architecture"]["optional_third_layer"],
        store_tensor_replay=bool(CONFIG.get("store_tensor_replay", False)),
        use_custom_collate=bool(CONFIG.get("use_custom_collate", False)),
        reuse_duplicate_states=bool(CONFIG.get("reuse_duplicate_states", False)))
    start_step = 0
    resume_metadata: dict = {}
    if resume_checkpoint is not None:
        metadata = agent.load(str(resume_checkpoint))
        resume_metadata = metadata
        start_step = int(metadata.get("step", 0))
        agent.updates = int(metadata.get("update_count", 0))
        if start_step <= 0 or start_step >= total_steps:
            raise ValueError("resume checkpoint step must be between 1 and total_steps-1")
    buffer_estimate = memory_estimate(
        train_entries, capacity=int(CONFIG["replay_capacity"]))
    RUNS.mkdir(parents=True, exist_ok=True)
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    tb = SummaryWriter(str(RUNS / f"stage_{stage}_tensorboard"))
    rng = np.random.default_rng(seed)
    fixed_seeds = tuple(CONFIG["stage_a_seeds"])
    fixed_intensity = float(EVAL_INTENSITIES["abilene"]["generators"]["poisson"]["intensity"])
    episode_no = start_step // 500
    env = wrapper = None
    observation = None
    active_entry = None
    active_seed = None
    active_kind = None
    active_intensity = None
    step_in_episode = 0
    history = {"raw_rewards": [], "scaled_rewards": [], "losses": [],
               "loss_steps": [],
               "q_means": [], "q_abs_max": [], "epsilons": [], "clip_flags": []}
    progress_rows = []
    interval = max(500, min(5_000, total_steps // 100 or 500))
    started = time.perf_counter()
    last_print_step = start_step
    last_val_loss: float | None = resume_metadata.get("val_loss")
    best_val_loss = math.inf
    best_path = RUNS / "stage_b_best.pt"
    top_checkpoints: list[dict[str, object]] = []
    if stage == "B" and resume_checkpoint is not None:
        manifest_path = OUTPUTS / "stage_b_top3.json"
        if manifest_path.exists():
            top_checkpoints = json.loads(manifest_path.read_text(encoding="utf-8"))
            if top_checkpoints:
                best_val_loss = min(float(item["val_loss"])
                                    for item in top_checkpoints)
    updates_before = agent.updates
    resume_text = (f"; resuming model weights at step {start_step} (fresh replay/optimizer)"
                   if resume_checkpoint is not None else "")
    print(f"Stage {stage}: target {total_steps} steps; train graphs={len(train_entries)}; "
          f"replay memory estimate={buffer_estimate['estimated_mib']:.1f} MiB "
          f"(payload {buffer_estimate['payload_bytes'] / (1024*1024):.1f} MiB), "
          f"max shape N={buffer_estimate['max_nodes']} E={buffer_estimate['max_undirected_edges']}; "
          f"optimizer update every {CONFIG['update_every']} valid environment decisions"
          f"{resume_text}.",
          flush=True)

    try:
        for step in range(start_step + 1, total_steps + 1):
            if env is None or observation is None or step_in_episode >= 500:
                episode_no += 1
                if stage == "A":
                    active_entry = train_entries[0]
                    active_kind = "poisson"
                    active_intensity = fixed_intensity
                    active_seed = fixed_seeds[(episode_no - 1) % len(fixed_seeds)]
                else:
                    active_entry = train_entries[int(rng.integers(len(train_entries)))]
                    available = ["poisson", "gravity", "hotspot"]
                    if active_entry["source"] == "sndlib":
                        available.append("sndlib")
                    active_kind = available[int(rng.integers(len(available)))]
                    active_intensity = float(np.exp(rng.uniform(
                        math.log(CONFIG["training_intensity_distribution"]["minimum"]),
                        math.log(CONFIG["training_intensity_distribution"]["maximum"]))))
                    active_seed = int(rng.integers(20_000, 1_000_000))
                env = make_training_env(active_entry, graphs[active_entry["name"]],
                                        active_kind, active_intensity, 500)
                wrapper = ObservationWrapper(env, active_entry["name"])
                observation, _info = env.reset(seed=active_seed)
                step_in_episode = 0

            state = wrapper.process(observation)
            epsilon = epsilon_at(step - 1, total_steps)
            valid_actions = np.flatnonzero(state.action_mask)
            if len(valid_actions):
                action = agent.select_action(state, epsilon, rng)
            else:
                # No candidate: honor the environment's idle sentinel without
                # a network query and without making a replay transition.
                action = env.config.k_paths
            next_observation, raw_reward, terminated, truncated, _info = env.step(action)
            scaled_reward, clipped = wrapper.scale_reward(raw_reward)
            next_state = wrapper.process(next_observation)
            if action < env.config.k_paths and state.action_mask[action]:
                agent.replay.add(Transition(state, action, scaled_reward, next_state,
                                            terminated, truncated))
            history["raw_rewards"].append(float(raw_reward))
            history["scaled_rewards"].append(float(scaled_reward))
            history["epsilons"].append(float(epsilon))
            history["clip_flags"].append(float(clipped))
            step_in_episode += 1
            observation = next_observation

            update_every = int(CONFIG["update_every"])
            if step % update_every == 0 and len(agent.replay) >= CONFIG["learning_starts"]:
                loss = agent.update()
                if loss is not None:
                    history["losses"].append(loss)
                    history["loss_steps"].append(step)
                    history["q_means"].append(float(agent.last_q_mean))
                    history["q_abs_max"].append(float(agent.last_q_abs_max))

            evaluate_now = (stage in {"B", "C"}
                            and step % CONFIG["stage_b_evaluation_interval"] == 0)
            if evaluate_now or step == total_steps:
                if stage in {"B", "C"}:
                    last_val_loss, val_overload, _ = validation_score(
                        agent, val_entries, partitions,
                        seeds=tuple(CONFIG["stage_b_validation_seeds"]))
                    if last_val_loss < best_val_loss:
                        best_val_loss = last_val_loss
                        _save_checkpoint(agent, best_path, step, stage, last_val_loss)
                    if stage == "B":
                        candidate_path = RUNS / f"stage_b_val_{step:06d}.pt"
                        _save_checkpoint(agent, candidate_path, step, stage,
                                         last_val_loss)
                        top_checkpoints.append({"step": step,
                                                "val_loss": last_val_loss,
                                                "path": str(candidate_path)})
                        top_checkpoints.sort(key=lambda item: (
                            float(item["val_loss"]), int(item["step"])))
                        keep = top_checkpoints[:int(CONFIG.get(
                            "stage_b_top_checkpoints", 3))]
                        keep_paths = {str(item["path"]) for item in keep}
                        for item in top_checkpoints:
                            path = Path(str(item["path"]))
                            if str(path) not in keep_paths and path.exists():
                                path.unlink()
                        top_checkpoints = keep
                        (OUTPUTS / "stage_b_top3.json").write_text(
                            json.dumps(top_checkpoints, indent=2), encoding="utf-8")
                    tb.add_scalar("validation/mean_loss", last_val_loss, step)
                    tb.add_scalar("validation/overload_fraction", val_overload, step)
                else:
                    val_overload = float("nan")

            if step % interval == 0 or step == total_steps:
                start = last_print_step - start_step
                recent_rewards = history["scaled_rewards"][start:step]
                recent_raw = history["raw_rewards"][start:step]
                recent_clips = history["clip_flags"][start:step]
                reward_mean = statistics.mean(recent_rewards) if recent_rewards else 0.0
                raw_mean = statistics.mean(recent_raw) if recent_raw else 0.0
                clipped_fraction = statistics.mean(recent_clips) if recent_clips else 0.0
                recent_losses = history["losses"][-max(1, interval // update_every):]
                loss_mean = statistics.mean(recent_losses) if recent_losses else None
                q_recent = history["q_means"][-max(1, interval // update_every):]
                q_mean = statistics.mean(q_recent) if q_recent else None
                epsilon = history["epsilons"][-1]
                elapsed = time.perf_counter() - started
                segment_steps = step - start_step
                seconds_per_step = elapsed / max(1, segment_steps)
                eta_min = max(0.0, (total_steps - step) * seconds_per_step / 60.0)
                val_text = "n/a" if last_val_loss is None else f"{last_val_loss:.5f}"
                loss_text = "n/a" if loss_mean is None else f"{loss_mean:.5f}"
                q_text = "n/a" if q_mean is None else f"{q_mean:.4f}"
                print(f"step {step} / {total_steps} | val loss {val_text} | "
                      f"ETA {eta_min:.1f} min | reward {reward_mean:.4f} | "
                      f"raw {raw_mean:.4f} | Huber {loss_text} | Q {q_text} | "
                      f"epsilon {epsilon:.3f} | clipped {clipped_fraction:.3%}",
                      flush=True)
                tb.add_scalar("reward/raw", raw_mean, step)
                tb.add_scalar("reward/scaled", reward_mean, step)
                tb.add_scalar("reward/clipped_fraction", clipped_fraction, step)
                if loss_mean is not None:
                    tb.add_scalar("train/huber_loss", loss_mean, step)
                if q_mean is not None:
                    tb.add_scalar("train/mean_q", q_mean, step)
                tb.add_scalar("train/epsilon", epsilon, step)
                progress_rows.append({"step": step, "raw_reward_mean": raw_mean,
                                      "scaled_reward_mean": reward_mean,
                                      "huber_loss_mean": loss_mean if loss_mean is not None else "",
                                      "mean_q": q_mean if q_mean is not None else "", "epsilon": epsilon,
                                      "reward_clipped_fraction": clipped_fraction,
                                      "validation_loss": last_val_loss,
                                      "validation_overload_fraction": (
                                          val_overload if 'val_overload' in locals() else "")})
                last_print_step = step
                if step % 10_000 == 0 or step == total_steps:
                    _save_checkpoint(agent, RUNS / f"stage_{stage}_latest.pt",
                                     step, stage, last_val_loss)

        if stage in {"B", "C"} and last_val_loss is not None:
            _save_checkpoint(agent, RUNS / "stage_b_final.pt", total_steps,
                             stage, last_val_loss)
        if stage == "B":
            (OUTPUTS / "stage_b_top3.json").write_text(
                json.dumps(top_checkpoints, indent=2), encoding="utf-8")
        curve_path = OUTPUTS / f"stage_{stage.lower()}_progress.csv"
        curve_path.parent.mkdir(parents=True, exist_ok=True)
        with curve_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(progress_rows[0]))
            writer.writeheader(); writer.writerows(progress_rows)
        write_curve_plots(history, f"stage_{stage.lower()}")
        result = {"agent": agent, "history": history, "best_val_loss": best_val_loss,
                  "last_val_loss": last_val_loss, "steps": total_steps,
                  "updates": agent.updates - updates_before,
                  "start_step": start_step,
                  "buffer_estimate": buffer_estimate, "progress_csv": curve_path,
                  "top_checkpoints": top_checkpoints}
        return result
    finally:
        tb.close()


def stage_a_comparison(agent: DoubleDQNAgent,
                       partitions: dict[str, list[dict]]) -> list[dict]:
    entry = next(dict(row, split="train") for row in partitions["train"]
                 if row["name"] == "abilene")
    graph = safe_graph_load(entry, "train", partitions)
    intensity = float(EVAL_INTENSITIES["abilene"]["generators"]["poisson"]["intensity"])
    rows = []
    for policy in ("agent_ddqn", "dijkstra_static", "greedy_min_util"):
        for seed in (20002, 20003):
            if policy == "agent_ddqn":
                adapter = AgentPolicyAdapter(agent)
                with adapter:
                    row = day3.run_episode(entry, graph, "poisson", intensity,
                                           policy, seed, "normal", 4.0,
                                           max_steps=500, warmup=100,
                                           data_root=DATA)
            else:
                row = day3.run_episode(entry, graph, "poisson", intensity,
                                       policy, seed, "normal", 4.0,
                                       max_steps=500, warmup=100,
                                       data_root=DATA)
            rows.append(row)
    return rows


def summarize_stage_a(rows: list[dict]) -> None:
    print("Stage A overfit check (abilene, Poisson, fixed eval intensity):")
    print("| Policy | Mean loss | Fraction >0.9 |", flush=True)
    print("|---|---:|---:|", flush=True)
    for policy in ("agent_ddqn", "dijkstra_static", "greedy_min_util"):
        values = [row for row in rows if row["policy"] == policy]
        loss = statistics.mean(row["mean_packet_loss"] for row in values)
        overload = statistics.mean(row["fraction_steps_over_0_9"] for row in values)
        print(f"| {policy} | {loss:.6f} | {overload:.4f} |", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("A", "B", "C"), default="A")
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--long", action="store_true")
    parser.add_argument("--resume", type=Path,
                        help="resume model weights from an existing Day 4 checkpoint")
    parser.add_argument("--seed", type=int, default=202604)
    parser.add_argument("--steps", type=int,
                        help="override the configured step target for a bounded run")
    args = parser.parse_args()
    if args.long:
        args.stage = "C"
    if args.stage == "C" and not args.long:
        parser.error("Stage C requires --long; it is not run by default")
    partitions = read_partitions(DATA / "splits.json")
    if args.stage == "A":
        steps = CONFIG["stage_a_quick_steps"] if args.quick else CONFIG["stage_a_steps"]
    elif args.stage == "B":
        steps = CONFIG["stage_b_quick_steps"] if args.quick else CONFIG["stage_b_steps"]
    else:
        steps = CONFIG["stage_c_steps"]
    if args.steps is not None:
        if args.steps <= 0:
            parser.error("--steps must be positive")
        steps = args.steps
    print(f"Training uses only {len(partitions['train'])} train entries; "
          "checkpoint selection reads the five validation entries only. "
          "No holdout topology is loaded.", flush=True)
    if args.resume and args.stage not in {"A", "B"}:
        parser.error("--resume currently supports Stages A and B only")
    result = run_training(args.stage, int(steps), args.seed, partitions, args.quick,
                          args.resume)
    if args.stage == "A":
        rows = stage_a_comparison(result["agent"], partitions)
        summarize_stage_a(rows)
        (OUTPUTS / "stage_a_comparison.json").write_text(
            json.dumps(rows, indent=2), encoding="utf-8")
    rewards = np.asarray(result["history"]["scaled_rewards"], dtype=np.float64)
    first = rewards[:max(1, len(rewards) // 10)]
    last = rewards[-max(1, len(rewards) // 10):]
    losses = np.asarray(result["history"]["losses"], dtype=np.float64)
    q_values = np.asarray(result["history"]["q_abs_max"], dtype=np.float64)
    print(f"Training complete: steps={result['steps']} updates={result['updates']} "
          f"best_val_loss={result['best_val_loss']:.6f} "
          f"last_val_loss={result['last_val_loss']}", flush=True)
    if rewards.size:
        print(f"A4 diagnostics: first10% scaled_reward={first.mean():.5f}; "
              f"last10%={last.mean():.5f}; delta={last.mean()-first.mean():.5f}; "
              f"clipped_fraction={np.mean(result['history']['clip_flags']):.3%}.",
              flush=True)
    if losses.size:
        med = float(np.median(losses))
        print(f"Huber loss finite={bool(np.isfinite(losses).all())}; min={losses.min():.6g}; "
              f"median={med:.6g}; max={losses.max():.6g}; "
              f"max/median={(losses.max()/med if med else math.inf):.3f}; "
              f"max |Q|={q_values.max() if q_values.size else 0.0:.5f}.", flush=True)


if __name__ == "__main__":
    main()
