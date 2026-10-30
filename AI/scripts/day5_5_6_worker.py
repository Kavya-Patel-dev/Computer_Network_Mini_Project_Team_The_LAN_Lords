"""Training worker for the Day 5.5–5.6 study (never accesses test graphs)."""
from __future__ import annotations

import argparse
import copy
import json
import math
import random
import shutil
import statistics
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from baselines import evaluation as day3
from baselines.policies import Decision
from env.network_env import NetworkEnvConfig, NetworkRoutingEnv
from env.traffic import PoissonTrafficGenerator
from models.data_guard import read_partitions
from models.day5_study import (CONTROLS, SELECTION_SEEDS, SelectionState,
                               canonical_signature, checkpoint_steps, control_passes,
                               format_progress, load_validation_graphs,
                               selection_entries)
from models.day5_temporal import TemporalObservationWrapper
from models.day5_variants import (VariantDQNAgent, VariantTransition,
                                  initialize_from_checkpoint,
                                  planned_update_count)
from models.harness import capture_flow_latencies
from models.obs import ObservationWrapper

DATA = ROOT / "data"
BC_CHECKPOINT = ROOT / "runs" / "day5" / "bc_init.pt"


def make_study_env(entry: dict, graph, generator: str, intensity: float,
                   history_length: int, max_steps: int = 500) -> NetworkRoutingEnv:
    config = NetworkEnvConfig(max_steps=max_steps, intensity=float(intensity),
                              history_length=int(history_length))
    stub = PoissonTrafficGenerator(sorted(graph.nodes), demand_mbps=1.0)
    topology = NetworkRoutingEnv(graph, config, traffic_generator=stub)
    traffic = day3.make_traffic(generator, entry, topology, float(intensity), DATA)
    return NetworkRoutingEnv(graph, config, traffic_generator=traffic)


class StudyAgentAdapter:
    """Use the configured observation history with the unchanged Day 3 harness."""

    def __init__(self, agent: VariantDQNAgent, history_length: int) -> None:
        self.agent = agent
        self.history_length = history_length
        self.original_chooser = None
        self.original_config = None
        self.env = None
        self.wrapper = None

    def __enter__(self):
        self.original_chooser = day3.choose_decision
        self.original_config = day3.NetworkEnvConfig

        def config_factory(**kwargs):
            return self.original_config(history_length=self.history_length, **kwargs)

        def choose(policy, env, rng, alpha=1.0, rf_model=None,
                   time_since_last_failure=10_000):
            if policy != "agent_ddqn":
                return self.original_chooser(
                    policy, env, rng, alpha=alpha, rf_model=rf_model,
                    time_since_last_failure=time_since_last_failure)
            if env is not self.env:
                self.env = env
                self.wrapper = (TemporalObservationWrapper(env, "day5-study")
                                if self.agent.flags.get("gru_history", False)
                                else ObservationWrapper(env, "day5-study"))
            state = self.wrapper.process(env._observation())
            valid = np.flatnonzero(state.action_mask)
            if not len(valid):
                return Decision(env.config.k_paths)
            q_values = self.agent.q_values(state)
            q_values = np.where(state.action_mask, q_values, -np.inf)
            return Decision(int(np.argmax(q_values)))

        day3.NetworkEnvConfig = config_factory
        day3.choose_decision = choose
        return self

    def __exit__(self, _exc_type, _exc, _tb):
        day3.choose_decision = self.original_chooser
        day3.NetworkEnvConfig = self.original_config
        self.env = None
        self.wrapper = None


def atomic_save_agent(agent: VariantDQNAgent, path: Path,
                      metadata: dict[str, Any]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    agent.save(str(temporary), metadata)
    temporary.replace(path)


def save_selected_and_final(agent, selected_candidate: Path, selected_path: Path,
                            final_path: Path, *, run_id: str, seed: int,
                            selected_step: int, selected_loss: float,
                            final_step: int, history_length: int) -> None:
    """Promote the selected snapshot and write a distinct final snapshot."""
    selected_path, final_path = Path(selected_path), Path(final_path)
    if selected_path.exists() or final_path.exists():
        raise FileExistsError("refusing to overwrite selected/final checkpoints")
    shutil.copyfile(selected_candidate, selected_path)
    atomic_save_agent(agent, final_path, {
        "run_id": run_id, "step": final_step, "seed": seed,
        "checkpoint_role": "final",
        "selection_criterion": "final training step; not the selected checkpoint",
        "selected_step": selected_step,
        "selected_validation_loss": selected_loss,
        "history_length": history_length,
    })


def _evaluate(agent: VariantDQNAgent, entry: dict, graph, *, intensity: float,
              seed: int, policy: str, history_length: int,
              scenario: str = "normal", max_steps: int = 500) -> dict[str, Any]:
    started = time.perf_counter()
    with capture_flow_latencies(warmup=100) as capture:
        with StudyAgentAdapter(agent, history_length):
            result = day3.run_episode(
                entry, copy.deepcopy(graph), "poisson", float(intensity), policy,
                seed=int(seed), scenario=scenario, alpha=4.0, rf_model=None,
                max_steps=max_steps, warmup=min(100, max_steps - 1), data_root=DATA)
    result["median_path_latency_ms"] = capture.median_latency_ms
    result["wall_seconds"] = time.perf_counter() - started
    return result


def evaluate_selection(agent: VariantDQNAgent, entries: list[dict],
                       controls: list[dict], graphs: dict[str, Any],
                       history_length: int,
                       static_control_cache: dict[tuple[str, int], dict]
                       , *, seeds=SELECTION_SEEDS, eval_max_steps: int = 500
                       ) -> tuple[float, list[dict], list[dict]]:
    """Evaluate only validation graphs, with selection seeds 30000–30001."""
    intensities = json.loads((DATA / "eval_intensity.json").read_text(encoding="utf-8"))
    rows = []
    control_rows = []
    for entry in entries:
        setting = intensities[entry["name"]]["generators"]["poisson"]
        for seed in seeds:
            rows.append(_evaluate(
                agent, entry, graphs[entry["name"]],
                intensity=float(setting["intensity"]), seed=seed,
                policy="agent_ddqn", history_length=history_length,
                max_steps=eval_max_steps))
    for entry in controls:
        for seed in seeds:
            key = (entry["name"], seed)
            if key not in static_control_cache:
                static_control_cache[key] = _evaluate(
                    agent, entry, graphs[entry["name"]], intensity=0.025,
                    seed=seed, policy="dijkstra_static",
                    history_length=history_length, max_steps=eval_max_steps)
            result = _evaluate(
                agent, entry, graphs[entry["name"]], intensity=0.025,
                seed=seed, policy="agent_ddqn", history_length=history_length,
                max_steps=eval_max_steps)
            result["static_reference_mean_loss"] = static_control_cache[key]["mean_packet_loss"]
            result["static_reference_mean_latency_ms"] = static_control_cache[key]["mean_path_latency_ms"]
            result["static_reference_median_latency_ms"] = static_control_cache[key]["median_path_latency_ms"]
            result["control_pass"] = control_passes(
                result["mean_packet_loss"], result["median_path_latency_ms"],
                static_control_cache[key]["mean_packet_loss"],
                static_control_cache[key]["median_path_latency_ms"])
            control_rows.append(result)
    score = statistics.mean(row["mean_packet_loss"] for row in rows)
    return float(score), rows, control_rows


def evaluate_final(agent: VariantDQNAgent, entries: list[dict], controls: list[dict],
                   graphs: dict[str, Any], history_length: int,
                   eval_max_steps: int = 500) -> dict[str, Any]:
    """Final checkpoint evaluation over validation-only rows and fixed eval seeds."""
    from models.day5_study import EVALUATION_SEEDS

    rows = []
    started = time.perf_counter()
    total = len(entries) * 2 * len(EVALUATION_SEEDS) + len(controls) * len(EVALUATION_SEEDS)
    intensities = json.loads((DATA / "eval_intensity.json").read_text(encoding="utf-8"))
    for entry in entries:
        intensity = float(intensities[entry["name"]]["generators"]["poisson"]["intensity"])
        for scenario in ("normal", "link_failures"):
            for seed in EVALUATION_SEEDS:
                rows.append(_evaluate(
                    agent, entry, graphs[entry["name"]], intensity=intensity,
                    seed=seed, policy="agent_ddqn", history_length=history_length,
                    scenario=scenario, max_steps=eval_max_steps))
                elapsed = time.perf_counter() - started
                completed = len(rows)
                eta = max(0.0, (total - completed) * elapsed / max(1, completed) / 60.0)
                print(f"final eval {completed} / {total} | graph={entry['name']} "
                      f"scenario={scenario} seed={seed} | ETA {eta:.2f} min", flush=True)
    for entry in controls:
        for seed in EVALUATION_SEEDS:
            row = _evaluate(
                agent, entry, graphs[entry["name"]], intensity=0.025,
                seed=seed, policy="agent_ddqn", history_length=history_length,
                scenario="normal", max_steps=eval_max_steps)
            row["scenario"] = "control"
            rows.append(row)
            elapsed = time.perf_counter() - started
            completed = len(rows)
            eta = max(0.0, (total - completed) * elapsed / max(1, completed) / 60.0)
            print(f"final eval {completed} / {total} | graph={entry['name']} "
                  f"scenario=control seed={seed} | ETA {eta:.2f} min", flush=True)
    return {"seeds": list(EVALUATION_SEEDS), "graphs": [row["name"] for row in entries],
            "control_graphs": [row["name"] for row in controls],
            "scenarios": ["normal", "link_failures", "control"],
            "episode_count": len(rows), "elapsed_seconds": time.perf_counter() - started,
            "rows": rows}


def _build_agent(job: dict[str, Any]) -> tuple[VariantDQNAgent, dict[str, Any]]:
    flags = dict(job["flags"])
    steps = int(job["steps"])
    agent = VariantDQNAgent(
        flags=flags, actions=4, learning_rate=1e-4, gamma=0.95, tau=0.002,
        replay_capacity=int(job.get("replay_capacity", 25_000)),
        batch_size=int(job.get("batch_size", 64)),
        learning_starts=int(job.get("learning_starts", 2_000)),
        seed=int(job["seed"]), n_step=int(job["n_step"]),
        prioritized=bool(job["prioritized_replay"]),
        total_updates=planned_update_count(steps),
        auxiliary_bc_weight=float(job["auxiliary_bc_weight"]),
        gradient_clip_norm=10.0)
    init = initialize_from_checkpoint(
        agent.online, str(BC_CHECKPOINT), load_bc=bool(job["load_bc"]))
    agent.target.load_state_dict(agent.online.state_dict())
    agent.target.eval()
    return agent, init


def _validation_reference_state(job: dict[str, Any], entry: dict, graph,
                               history_length: int):
    intensity_data = json.loads((DATA / "eval_intensity.json").read_text(encoding="utf-8"))
    intensity = float(intensity_data[entry["name"]]["generators"]["poisson"]["intensity"])
    env = make_study_env(entry, graph, "poisson", intensity, history_length)
    observation, _info = env.reset(seed=30_000)
    wrapper = (TemporalObservationWrapper(env, entry["name"])
               if job["flags"].get("gru_history", False)
               else ObservationWrapper(env, entry["name"]))
    state = wrapper.process(observation)
    return env, state


def _checkpoint_reload_difference(job: dict[str, Any], checkpoint: Path,
                                  entry: dict, graph, history_length: int) -> float:
    env, state = _validation_reference_state(job, entry, graph, history_length)
    try:
        left, _ = _build_agent(job)
        left.load(str(checkpoint))
        right, _ = _build_agent(job)
        right.load(str(checkpoint))
        left_q = left.q_values(state)
        right_q = right.q_values(state)
        return float(np.max(np.abs(left_q - right_q)))
    finally:
        env.close()


def run(job: dict[str, Any]) -> dict[str, Any]:
    run_id = str(job["run_id"])
    seed, total_steps = int(job["seed"]), int(job["steps"])
    history_length = int(job["history_length"])
    run_dir, output_dir = Path(job["run_dir"]), Path(job["output_dir"])
    run_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "summary.json"
    if summary_path.exists() or (run_dir / "final.pt").exists():
        raise FileExistsError(f"worker refuses to overwrite a prior artifact for {run_id}")

    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    import train
    partitions = read_partitions(DATA / "splits.json")
    train_entries = [dict(row, split="train") for row in partitions["train"]]
    # Selection rows are constructed from the validation partition only.  No
    # holdout entry is passed to safe_graph_load or the evaluation harness.
    val_entries, controls = selection_entries(partitions)
    val_graphs = load_validation_graphs(partitions, train.safe_graph_load)
    selection_names = job.get("selection_graph_names")
    if selection_names is not None:
        available = {entry["name"] for entry in val_entries}
        if not set(selection_names) <= available:
            raise ValueError("smoke selection may name validation graphs only")
        val_entries = [entry for entry in val_entries if entry["name"] in set(selection_names)]
        if len(val_entries) != len(set(selection_names)):
            raise ValueError("smoke selection graph names must be unique")
    agent, init_info = _build_agent(job)

    expert_batch = None
    if float(job["auxiliary_bc_weight"]):
        from scripts.day5_3_worker import _fixed_expert_batch
        expert_batch = _fixed_expert_batch(
            train_entries, partitions,
            include_history=bool(job["flags"].get("gru_history", False)))

    if int(job.get("checkpoint_interval", 0)):
        interval = int(job["checkpoint_interval"])
        schedule = list(range(0, total_steps + 1, interval))
        if schedule[-1] != total_steps:
            schedule.append(total_steps)
    elif job.get("checkpoint_steps"):
        schedule = sorted(set(int(step) for step in job["checkpoint_steps"]))
        if schedule[0] != 0 or schedule[-1] != total_steps:
            raise ValueError("explicit checkpoint schedule must include 0 and final step")
    else:
        schedule = checkpoint_steps(
            total_steps,
            extra_steps=((int(job["gru_comparison_step"]),)
                         if job["variant"] == "FULL"
                         and int(job.get("gru_comparison_step", 0)) < total_steps else ()))
    selection_state = SelectionState()
    validation_history = []
    selection_records = []
    static_control_cache: dict[tuple[str, int], dict] = {}
    losses: list[float] = []
    q_abs: list[float] = []
    eps_start, eps_end = 0.10, 0.02
    eps_anneal = max(1, int(total_steps * 0.30))
    env = wrapper = observation = active_entry = None
    episode_id = -1
    step_in_episode = 0
    started = time.perf_counter()
    last_validation_loss = math.nan
    last_evaluated_step = -1
    print(f"run={run_id} seed={seed} flags={json.dumps(job['flags'], sort_keys=True)} "
          f"history_length={history_length} train_graphs={len(train_entries)} "
          f"selection_graphs={len(val_entries)}", flush=True)

    def select_and_record(step: int) -> None:
        nonlocal selection_state, last_validation_loss, last_evaluated_step
        score, rows, control_rows = evaluate_selection(
            agent, val_entries, controls, val_graphs, history_length,
            static_control_cache,
            seeds=tuple(job.get("selection_seeds", SELECTION_SEEDS)),
            eval_max_steps=int(job.get("selection_eval_max_steps", 500)))
        last_validation_loss = score
        last_evaluated_step = step
        validation_history.append({"step": step, "mean_loss": score})
        selection_records.append({"step": step, "mean_loss": score,
                                  "validation_rows": rows,
                                  "control_rows": control_rows})
        updated = selection_state.consider(step, score)
        if updated.best_step == step:
            candidate = run_dir / f"selected_candidate_step_{step:06d}.pt"
            atomic_save_agent(agent, candidate, {
                "run_id": run_id, "step": step, "seed": seed,
                "checkpoint_role": "selected",
                "selection_criterion": (
                    f"lowest mean packet loss over {len(val_entries)} validation graphs; "
                    f"seeds {','.join(map(str, job.get('selection_seeds', SELECTION_SEEDS)))}"),
                "selection_mean_validation_loss": score,
                "history_length": history_length,
            })
            selection_state = updated
        elapsed = time.perf_counter() - started
        if step == 0:
            # ETA at the reference checkpoint uses the measured contention
            # profile as a seed; later ETAs use this run's elapsed wall time.
            measured_rate = (3.838 if job["flags"].get("gru_history") else 4.322)
            eta = total_steps / measured_rate / 60.0
        else:
            eta = max(0.0, (total_steps - step) * elapsed / step / 60.0)
        control_pass_count = sum(bool(row.get("control_pass")) for row in control_rows)
        state_text = (f"selected_step={selection_state.best_step}; "
                      f"control_passes={control_pass_count}/{len(control_rows)}")
        print(format_progress(run_id, step, total_steps, score, eta, state_text), flush=True)

    try:
        select_and_record(0)
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
                env = make_study_env(active_entry, graph, generator, intensity,
                                     history_length, max_steps=500)
                wrapper = (TemporalObservationWrapper(env, active_entry["name"])
                           if job["flags"].get("gru_history", False)
                           else ObservationWrapper(env, active_entry["name"]))
                # Training episode seeds are disjoint from selection/evaluation seeds.
                observation, _info = env.reset(seed=seed * 1_000 + episode_id)
                step_in_episode = 0

            state = wrapper.process(observation)
            fraction = min(1.0, max(0.0, (step - 1) / eps_anneal))
            epsilon = eps_start + fraction * (eps_end - eps_start)
            action = agent.select_action(state, epsilon, rng)
            next_observation, raw_reward, terminated, truncated, _info = env.step(action)
            scaled_reward, _clipped = wrapper.scale_reward(raw_reward)
            next_state = wrapper.process(next_observation)
            if action < 4 and state.action_mask[action]:
                agent.add_transition(VariantTransition(
                    state, action, scaled_reward, next_state,
                    bool(terminated), bool(truncated)), episode_id)
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
                        raise FloatingPointError(f"nonfinite Huber loss at step {step}")
                    if not math.isfinite(agent.last_q_abs_max):
                        raise FloatingPointError(f"nonfinite Q value at step {step}")
                    losses.append(float(loss))
                    q_abs.append(float(agent.last_q_abs_max))
            if step % 1_000 == 0:
                atomic_save_agent(agent, run_dir / "latest.pt", {
                    "run_id": run_id, "step": step, "seed": seed,
                    "flags": job["flags"], "history_length": history_length,
                })
                elapsed = time.perf_counter() - started
                eta = max(0.0, (total_steps - step) * elapsed / step / 60.0)
                print(format_progress(
                    run_id, step, total_steps, last_validation_loss, eta,
                    f"last_eval_step={last_evaluated_step}; "
                    f"selected_step={selection_state.best_step}"), flush=True)
            if step in schedule:
                select_and_record(step)
            if terminated or truncated:
                observation = None
                step_in_episode = 500
    finally:
        if env is not None:
            env.close()

    if selection_state.best_step is None:
        raise RuntimeError("no selected checkpoint was written")
    selected_candidate = run_dir / f"selected_candidate_step_{selection_state.best_step:06d}.pt"
    save_selected_and_final(
        agent, selected_candidate, run_dir / "selected.pt", run_dir / "final.pt",
        run_id=run_id, seed=seed, selected_step=selection_state.best_step,
        selected_loss=selection_state.best_loss, final_step=total_steps,
        history_length=history_length)
    # Reload both persisted artifacts and compare outputs on one fixed validation
    # state. These checks validate serialization without touching the test split.
    reference_entry = val_entries[0]
    selected_reload_diff = _checkpoint_reload_difference(
        job, run_dir / "selected.pt", reference_entry,
        val_graphs[reference_entry["name"]], history_length)
    final_reload_diff = _checkpoint_reload_difference(
        job, run_dir / "final.pt", reference_entry,
        val_graphs[reference_entry["name"]], history_length)
    if max(selected_reload_diff, final_reload_diff) >= 1e-6:
        raise AssertionError("checkpoint reload Q difference is not below 1e-6")
    selected_metadata = torch.load(
        run_dir / "selected.pt", map_location="cpu", weights_only=False)["metadata"]
    final_metadata = torch.load(
        run_dir / "final.pt", map_location="cpu", weights_only=False)["metadata"]
    # Final evaluation always uses the selected checkpoint, five validation
    # graphs, and the disjoint evaluation seeds. The three controls are reported
    # as a separate 0.025-intensity scenario.
    selected_agent, _ = _build_agent(job)
    selected_agent.load(str(run_dir / "selected.pt"))
    all_val_entries, all_controls = selection_entries(partitions)
    final_evaluation = evaluate_final(
        selected_agent, all_val_entries, all_controls, val_graphs,
        history_length, eval_max_steps=int(job.get("final_eval_max_steps", 500)))
    final_evaluation["checkpoint"] = str(run_dir / "selected.pt")
    (output_dir / "final_evaluation.json").write_text(
        json.dumps(final_evaluation, indent=2), encoding="utf-8")
    val_sorted = sorted(losses)
    median_loss = statistics.median(val_sorted) if val_sorted else math.nan
    summary = {
        "run_id": run_id,
        "signature": canonical_signature(job),
        "completed": True,
        "seed": seed,
        "steps": total_steps,
        "updates": agent.updates,
        "elapsed_seconds": time.perf_counter() - started,
        "steps_per_second": total_steps / max(time.perf_counter() - started, 1e-12),
        "last_validation_loss": validation_history[-1]["mean_loss"],
        "best_validation_loss": selection_state.best_loss,
        "selected_step": selection_state.best_step,
        "selection_criterion": (
            f"minimum mean packet loss over {len(val_entries)} validation graphs, "
            f"averaged over seeds {','.join(map(str, job.get('selection_seeds', SELECTION_SEEDS)))}"),
        "validation_history": validation_history,
        "control_rows": [row for item in selection_records for row in item["control_rows"]],
        "loss_trace": losses,
        "q_abs_trace": q_abs,
        "loss_min": min(losses) if losses else None,
        "loss_median": median_loss if losses else None,
        "loss_max": max(losses) if losses else None,
        "loss_max_over_median": max(losses) / median_loss if losses and median_loss > 0 else None,
        "q_abs_p999": float(np.percentile(q_abs, 99.9)) if q_abs else None,
        "q_abs_max": max(q_abs) if q_abs else None,
        "all_losses_finite": bool(losses) and all(math.isfinite(value) for value in losses),
        "all_q_finite": bool(q_abs) and all(math.isfinite(value) for value in q_abs),
        "flags": job["flags"],
        "history_length": history_length,
        "run_dir": str(run_dir),
        "output_dir": str(output_dir),
        "selected_checkpoint": str(run_dir / "selected.pt"),
        "final_checkpoint": str(run_dir / "final.pt"),
        "initialization": init_info,
        "selected_reload_q_max_abs_diff": selected_reload_diff,
        "final_reload_q_max_abs_diff": final_reload_diff,
        "selected_checkpoint_metadata": selected_metadata,
        "final_checkpoint_metadata": final_metadata,
        "final_evaluation": {key: value for key, value in final_evaluation.items()
                             if key != "rows"},
        "selection_wall_seconds": sum(
            float(item.get("wall_seconds", 0.0))
            for record in selection_records
            for item in record["validation_rows"] + record["control_rows"]),
    }
    (output_dir / "selection_history.json").write_text(
        json.dumps(selection_records, indent=2), encoding="utf-8")
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2),
                                               encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, required=True)
    args = parser.parse_args()
    job = json.loads(args.spec.read_text(encoding="utf-8"))
    run(job)


if __name__ == "__main__":
    main()
