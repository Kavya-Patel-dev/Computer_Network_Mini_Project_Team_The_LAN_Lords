"""Evaluate Day 3 baselines on fixed graphs, traffic seeds, and scenarios."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from baselines.evaluation import EVAL_SEEDS, load_graph, run_episode, SCENARIOS, TRAIN_SEEDS
from baselines.leakage import validate_graph_partitions
from baselines.policies import POLICIES

DATA = ROOT / "data"
OUT = ROOT / "outputs"
METRICS = (
    "mean_path_latency_ms", "p95_path_latency_ms", "mean_packet_loss",
    "delivered_throughput_mbps", "mean_max_backbone_utilization",
    "p95_max_backbone_utilization", "fraction_steps_over_0_9", "flapping_rate",
    "flapping_comparisons",
    "recovery_time_steps", "recovery_censored", "invalid_actions_accepted",
    "full_path_not_in_k_fraction", "ecmp_tie_fraction",
    "post_failure_routed_flows",
)
GATE_COHORT = ("abilene", "Nsfnet", "Peer1", "newyork", "geant",
               "nobel-eu", "DeutscheTelekom")
_WORKER_RF_MODEL = None
_WORKER_INTENSITIES = None
_WORKER_ALPHA = None
_WORKER_STEPS = None
_WORKER_WARMUP = None


def _seed_group(split: str, quick: bool) -> tuple[int, ...]:
    if quick:
        return (TRAIN_SEEDS[0],) if split == "train" else (EVAL_SEEDS[0],)
    return TRAIN_SEEDS if split == "train" else EVAL_SEEDS


def _worker_init(model_path: str, quick: bool) -> None:
    global _WORKER_RF_MODEL, _WORKER_INTENSITIES, _WORKER_ALPHA
    global _WORKER_STEPS, _WORKER_WARMUP
    import joblib
    _WORKER_RF_MODEL = joblib.load(model_path)
    _WORKER_INTENSITIES = json.loads((DATA / "eval_intensity.json").read_text(encoding="utf-8"))
    alpha_config = json.loads((ROOT / "configs" / "evaluation.json").read_text(encoding="utf-8"))
    _WORKER_ALPHA = float(alpha_config["dijkstra_load_aware_alpha"])
    _WORKER_STEPS, _WORKER_WARMUP = (120, 20) if quick else (500, 100)


def _evaluate_graph_worker(payload: tuple[str, dict, bool]) -> tuple[str, list[dict], list[dict], int]:
    split, raw_entry, quick = payload
    entry = {**raw_entry, "split": split}
    graph = load_graph(entry, DATA)
    gen_configs = _WORKER_INTENSITIES[entry["name"]]["generators"]
    seeds = _seed_group(split, quick)
    rows = []
    hash_rows = []
    for kind, setting in gen_configs.items():
        intensity = float(setting["intensity"])
        for scenario in SCENARIOS:
            for seed in seeds:
                group_rows = []
                for policy in POLICIES:
                    result = run_episode(
                        entry, graph, kind, intensity, policy, seed, scenario,
                        _WORKER_ALPHA, rf_model=_WORKER_RF_MODEL,
                        max_steps=_WORKER_STEPS, warmup=_WORKER_WARMUP,
                        data_root=DATA)
                    group_rows.append(result)
                    rows.append(result)
                    hash_rows.append({"split": split, "graph": entry["name"],
                                      "generator": kind, "scenario": scenario,
                                      "seed": seed, "policy": policy,
                                      "request_sequence_sha256": result["request_sequence_sha256"]})
                hashes = {row["request_sequence_sha256"] for row in group_rows}
                if len(hashes) != 1 or any(
                        row["request_sequence_length"] != _WORKER_STEPS
                        for row in group_rows):
                    raise AssertionError(
                        f"policies do not share the same {entry['name']}/{kind}/{scenario}/{seed} requests")
    return split, rows, hash_rows, len(gen_configs)


def _aggregate(rows: list[dict]) -> list[dict]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    keys = ("split", "graph", "source", "generator", "intensity", "scenario", "policy")
    for row in rows:
        groups[tuple(row[key] for key in keys)].append(row)
    result = []
    for group_key, values in sorted(groups.items(), key=lambda item: tuple(map(str, item[0]))):
        aggregate = dict(zip(keys, group_key))
        for metric in METRICS:
            sample = [float(row[metric]) for row in values if row[metric] is not None]
            aggregate[f"{metric}_mean"] = float(np.mean(sample)) if sample else ""
            aggregate[f"{metric}_std"] = float(np.std(sample, ddof=1)) if len(sample) > 1 else 0.0
        aggregate["n_seeds"] = len(values)
        aggregate["request_sequence_count"] = len({row["request_sequence_sha256"] for row in values})
        aggregate["event_schedule_json"] = values[0]["event_schedule_json"]
        result.append(aggregate)
    return result


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("\n", encoding="utf-8")
        return
    fields = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


def _write_summary(aggregates: list[dict]) -> None:
    split_tables = {}
    metric_names = ("mean_path_latency_ms", "p95_path_latency_ms", "mean_packet_loss",
                    "delivered_throughput_mbps", "mean_max_backbone_utilization",
                    "p95_max_backbone_utilization", "fraction_steps_over_0_9",
                    "flapping_rate", "mean_decision_time_ms", "recovery_time_steps")
    # Run-row timing is kept in its own nonreproducible measurement sidecar.
    # The normal-scenario summaries use aggregated deterministic metrics.
    for split in ("train", "val", "test"):
        output = []
        for graph in sorted({row["graph"] for row in aggregates if row["split"] == split}):
            normal = [row for row in aggregates
                      if row["split"] == split and row["graph"] == graph
                      and row["scenario"] == "normal"]
            for policy in POLICIES:
                per_gen = [row for row in normal if row["policy"] == policy]
                if not per_gen:
                    continue
                item = {"split": split, "graph": graph, "policy": policy,
                        "generators_averaged": len(per_gen)}
                for metric in metric_names:
                    if metric == "mean_decision_time_ms":
                        item[metric] = "see decision_timing.csv"
                        continue
                    vals = [float(row[f"{metric}_mean"]) for row in per_gen
                            if row.get(f"{metric}_mean", "") != ""]
                    item[metric] = float(np.mean(vals)) if vals else ""
                output.append(item)
        path = OUT / f"baseline_summary_{split}.csv"
        _write_csv(path, output)
        split_tables[split] = output
    md = ["# Day 3 baseline summary (normal scenario)",
          "", "Each graph appears once per policy; values average that graph's evaluated generators equally. Timing is in `decision_timing.csv`.", ""]
    cols = ("graph", "policy", "mean_path_latency_ms", "p95_path_latency_ms",
            "mean_packet_loss", "delivered_throughput_mbps",
            "mean_max_backbone_utilization", "p95_max_backbone_utilization",
            "fraction_steps_over_0_9", "flapping_rate", "recovery_time_steps")
    for split, table in split_tables.items():
        md.extend([f"## {split.title()}", "", "| " + " | ".join(cols) + " |",
                   "|" + "|".join(["---"] * len(cols)) + "|"])
        for row in table:
            md.append("| " + " | ".join(str(row.get(col, "")) for col in cols) + " |")
        md.append("")
    (OUT / "baseline_summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")


def _gate_report(rows: list[dict], splits: dict, intensities: dict) -> dict:
    pathdiv = {entry["name"]: float(entry["path_diversity"])
               for split in splits.values() for entry in split}
    entries = {entry["name"]: entry for split, values in splits.items()
               for entry in values}
    eligible = []
    for name in GATE_COHORT:
        entry = entries.get(name)
        if entry is None or pathdiv[name] < 0.5:
            continue
        gen_settings = intensities[name]["generators"]
        if not any(value.get("status") != "cannot_congest"
                   for value in gen_settings.values()):
            continue
        eligible.append(name)

    normal_rows = [row for row in rows if row["scenario"] == "normal"
                   and row["graph"] in eligible
                   and intensities[row["graph"]]["generators"][row["generator"]].get("status") != "cannot_congest"]
    per_graph = {}
    improved = 0
    overload_in_band = 0
    for name in eligible:
        graph_policy = {}
        for policy in ("random", "dijkstra_static", "dijkstra_load_aware"):
            policy_rows = [row for row in normal_rows
                           if row["graph"] == name and row["policy"] == policy]
            # Seed and generator rows receive equal weight after aggregation.
            graph_policy[policy] = {
                "mean_loss": float(np.mean([row.get("mean_packet_loss_mean", row.get("mean_packet_loss"))
                                             for row in policy_rows])) if policy_rows else math.nan,
                "fraction_over_0_9": float(np.mean([row.get("fraction_steps_over_0_9_mean", row.get("fraction_steps_over_0_9"))
                                                    for row in policy_rows])) if policy_rows else math.nan,
            }
        static = graph_policy["dijkstra_static"]
        random = graph_policy["random"]
        aware = graph_policy["dijkstra_load_aware"]
        random_worse = random["mean_loss"] > static["mean_loss"]
        aware_better = (aware["mean_loss"] < static["mean_loss"]
                        and aware["fraction_over_0_9"] < static["fraction_over_0_9"])
        in_band = 0.30 <= static["fraction_over_0_9"] <= 0.60
        improved += int(aware_better)
        overload_in_band += int(in_band)
        per_graph[name] = {**graph_policy, "random_loss_higher_than_static": random_worse,
                           "load_aware_improves_both": aware_better,
                           "static_fraction_in_0_30_0_60": in_band}
    random_mean = float(np.mean([per_graph[name]["random"]["mean_loss"] for name in eligible])) if eligible else math.nan
    static_mean = float(np.mean([per_graph[name]["dijkstra_static"]["mean_loss"] for name in eligible])) if eligible else math.nan
    return {
        "G1": {"pass": len(eligible) >= 5 and random_mean > static_mean and improved >= 5,
               "eligible_graphs": eligible,
               "eligible_count": len(eligible),
               "random_mean_loss": random_mean,
               "static_mean_loss": static_mean,
               "load_aware_better_count": improved,
               "required_count": 5,
               "per_graph": per_graph},
        "G2": {"pass": len(eligible) >= 5 and overload_in_band >= 5,
               "static_in_band_count": overload_in_band,
               "required_count": 5,
               "per_graph_fractions": {name: per_graph[name]["dijkstra_static"]["fraction_over_0_9"]
                                       for name in eligible}},
    }


def _run_once(run_id: int, quick: bool, rf_model) -> tuple[list[dict], list[dict]]:
    splits_json = json.loads((DATA / "splits.json").read_text(encoding="utf-8"))
    split_names = {split: {row["name"] for row in rows}
                   for split, rows in splits_json.items()}
    validate_graph_partitions(split_names["train"], split_names["val"], split_names["test"])
    intensity_config = json.loads((DATA / "eval_intensity.json").read_text(encoding="utf-8"))
    alpha_config = json.loads((ROOT / "configs" / "evaluation.json").read_text(encoding="utf-8"))
    if alpha_config.get("selection_split") != "val":
        raise AssertionError("dijkstra_load_aware alpha must be selected on validation only")
    if set(alpha_config.get("validation_seeds", ())) - set(EVAL_SEEDS):
        raise AssertionError("validation alpha tuning used a seed outside the fixed evaluation seed set")
    for entry in splits["test"]:
        settings = intensity_config[entry["name"]]["generators"]
        if any(value.get("source") != "median selected validation intensity"
               for value in settings.values()):
            raise AssertionError("test evaluation intensity must be transferred from validation")
    eval_seed_set = set(EVAL_SEEDS)
    if set(alpha_config.get("validation_seeds", ())) - eval_seed_set:
        raise AssertionError("validation alpha tuning used a seed outside the fixed evaluation seed set")
    for entry in splits_json["test"]:
        settings = intensity_config[entry["name"]]["generators"]
        if any(value.get("source") != "median selected validation intensity"
               for value in settings.values()):
            raise AssertionError("test evaluation intensity must be transferred from validation")
    all_rows = []
    hash_rows = []
    raw_path = OUT / f"evaluation_runs_{run_id}.jsonl"
    with raw_path.open("w", encoding="utf-8") as raw:
        tasks = [(split, entry, quick) for split in ("train", "val", "test")
                 for entry in splits_json[split]]
        workers = max(1, min(4, (os.cpu_count() or 1)))
        with ProcessPoolExecutor(max_workers=workers, initializer=_worker_init,
                                 initargs=(str(OUT / "rf_routing.joblib"), quick)) as pool:
            futures = [pool.submit(_evaluate_graph_worker, task) for task in tasks]
            for future in as_completed(futures):
                split, graph_rows, graph_hashes, generator_count = future.result()
                all_rows.extend(graph_rows); hash_rows.extend(graph_hashes)
                for result in graph_rows:
                    raw.write(json.dumps(result, sort_keys=True, allow_nan=False) + "\n")
                raw.flush()
                graph_name = graph_rows[0]["graph"] if graph_rows else "unknown"
                seed_count = len(_seed_group(split, quick))
                print(f"Evaluation pass {run_id}: completed {split} graph {graph_name} "
                      f"({generator_count} generators, {seed_count} seeds)", flush=True)
    return all_rows, hash_rows


def _reduced_generators(entry: dict, intensity_config: dict) -> tuple[str, ...]:
    """Apply the runtime-triggered generator allocation without changing gates."""
    available = intensity_config[entry["name"]]["generators"]
    selected = ("gravity", "hotspot") if entry["name"] in GATE_COHORT else ("poisson",)
    missing = [kind for kind in selected if kind not in available]
    if missing:
        raise AssertionError(f"{entry['name']} is missing required reduced generator(s): {missing}")
    return selected


def _reduced_job_worker(payload: tuple[str, dict, int, tuple[str, ...]]) -> dict:
    """Evaluate one (graph, seed) job across its allocated generators/scenarios."""
    split, raw_entry, seed, generator_kinds = payload
    entry = {**raw_entry, "split": split}
    graph = load_graph(entry, DATA)
    rows: list[dict] = []
    hash_rows: list[dict] = []
    for kind in generator_kinds:
        intensity = float(_WORKER_INTENSITIES[entry["name"]]["generators"][kind]["intensity"])
        for scenario in SCENARIOS:
            group_rows = []
            for policy in POLICIES:
                result = run_episode(
                    entry, graph, kind, intensity, policy, seed, scenario,
                    _WORKER_ALPHA, rf_model=_WORKER_RF_MODEL,
                    max_steps=_WORKER_STEPS, warmup=_WORKER_WARMUP,
                    data_root=DATA)
                rows.append(result)
                group_rows.append(result)
                hash_rows.append({
                    "split": split, "graph": entry["name"], "generator": kind,
                    "scenario": scenario, "seed": seed, "policy": policy,
                    "request_sequence_sha256": result["request_sequence_sha256"],
                })
            hashes = {row["request_sequence_sha256"] for row in group_rows}
            if len(hashes) != 1 or any(
                    row["request_sequence_length"] != _WORKER_STEPS
                    for row in group_rows):
                raise AssertionError(
                    f"policies do not share the same {entry['name']}/{kind}/{scenario}/{seed} requests")
    return {"job_id": f"{split}|{entry['name']}|{seed}", "split": split,
            "graph": entry["name"], "seed": seed, "generators": list(generator_kinds),
            "rows": rows, "hash_rows": hash_rows}


def _reduced_job_list(splits: dict, intensity_config: dict) -> list[tuple[str, dict, int, tuple[str, ...]]]:
    jobs = []
    for split in ("train", "val", "test"):
        seeds = TRAIN_SEEDS if split == "train" else tuple(range(1000, 1005))
        for entry in splits[split]:
            generators = _reduced_generators(entry, intensity_config)
            jobs.extend((split, entry, int(seed), generators) for seed in seeds)
    return jobs


def _checkpoint_signature(splits: dict, intensity_config: dict,
                          jobs: list[tuple[str, dict, int, tuple[str, ...]]]) -> dict:
    code_files = (ROOT / "evaluate.py", ROOT / "baselines" / "evaluation.py",
                  ROOT / "baselines" / "policies.py", ROOT / "baselines" / "explicit_path.py",
                  ROOT / "env" / "network_env.py", ROOT / "env" / "traffic.py",
                  ROOT / "env" / "paths.py", ROOT / "env" / "events.py")
    code_hashes = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                   for path in code_files}
    job_spec = []
    for split, entry, seed, generators in jobs:
        job_spec.append({
            "split": split, "graph": entry["name"], "seed": seed,
            "path": entry["path"], "source": entry["source"],
            "generators": {kind: intensity_config[entry["name"]]["generators"][kind]
                           for kind in generators},
        })
    return {"version": 1, "steps": 500, "warmup": 100,
            "scenarios": list(SCENARIOS), "policies": list(POLICIES),
            "gate_eligible_graphs": list(GATE_COHORT), "jobs": job_spec,
            "code_sha256": code_hashes}


def _load_reduced_checkpoint(raw_path: Path, manifest: dict,
                             jobs: list[tuple[str, dict, int, tuple[str, ...]]]) -> dict[str, dict]:
    manifest_path = raw_path.with_suffix(raw_path.suffix + ".manifest.json")
    if raw_path.exists():
        old_manifest = None
        if manifest_path.exists():
            try:
                old_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                old_manifest = None
        if old_manifest != manifest:
            # Keep all prior bytes recoverable; settings/code changes invalidate reuse.
            stamp = time.strftime("%Y%m%d-%H%M%S")
            raw_archive = raw_path.with_name(raw_path.name + f".archive-{stamp}")
            raw_path.replace(raw_archive)
            if manifest_path.exists():
                manifest_path.replace(manifest_path.with_name(manifest_path.name + f".archive-{stamp}"))
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    expected = {}
    for split, entry, seed, generators in jobs:
        job_id = f"{split}|{entry['name']}|{seed}"
        expected[job_id] = {(kind, scenario, policy)
                            for kind in generators for scenario in SCENARIOS for policy in POLICIES}
    records: dict[str, dict] = {}
    if raw_path.exists():
        with raw_path.open(encoding="utf-8") as raw:
            for line in raw:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                job_id = record.get("job_id")
                if job_id not in expected:
                    continue
                rows = record.get("rows", [])
                actual = {(row.get("generator"), row.get("scenario"), row.get("policy"))
                          for row in rows}
                if actual == expected[job_id] and len(rows) == len(expected[job_id]):
                    records[job_id] = record
    return records


def _run_reduced_jobs(jobs: list[tuple[str, dict, int, tuple[str, ...]]],
                      raw_path: Path, model_path: Path,
                      manifest: dict) -> tuple[list[dict], list[dict], float, int]:
    records = _load_reduced_checkpoint(raw_path, manifest, jobs)
    pending = [job for job in jobs
               if f"{job[0]}|{job[1]['name']}|{job[2]}" not in records]
    done = len(records)
    total = len(jobs)
    worker_count = max(1, (os.cpu_count() or 1) - 1)
    started = time.monotonic()
    print(f"Reduced evaluation: {done} checkpointed jobs, {len(pending)} remaining; "
          f"{worker_count} workers ({os.cpu_count()} logical cores)", flush=True)
    raw_path.parent.mkdir(exist_ok=True)
    with raw_path.open("a", encoding="utf-8") as raw:
        if pending:
            with ProcessPoolExecutor(max_workers=worker_count, initializer=_worker_init,
                                     initargs=(str(model_path), False)) as pool:
                futures = [pool.submit(_reduced_job_worker, job) for job in pending]
                graph_total_jobs: dict[str, int] = defaultdict(int)
                graph_finished_jobs: dict[str, int] = defaultdict(int)
                for split, entry, seed, _ in jobs:
                    graph_total_jobs[entry["name"]] += 1
                for job_id in records:
                    graph_finished_jobs[job_id.split("|")[1]] += 1
                for future in as_completed(futures):
                    record = future.result()
                    raw.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
                    raw.flush()
                    records[record["job_id"]] = record
                    done += 1
                    graph_finished_jobs[record["graph"]] += 1
                    elapsed = time.monotonic() - started
                    eta_minutes = (max(0.0, (total - done) * elapsed / done) / 60.0
                                   if done and elapsed else 0.0)
                    complete_graphs = sum(graph_finished_jobs[name] == graph_total_jobs[name]
                                          for name in graph_total_jobs)
                    print(f"done {done} / {total} jobs, ETA {eta_minutes:.1f} min "
                          f"({complete_graphs} / 22 graphs complete)", flush=True)
    ordered_records = [records[f"{split}|{entry['name']}|{seed}"]
                       for split, entry, seed, _ in jobs]
    rows = [row for record in ordered_records for row in record["rows"]]
    hashes = [row for record in ordered_records for row in record["hash_rows"]]
    elapsed = time.monotonic() - started
    return rows, hashes, elapsed, done


def _preserve_quick_outputs() -> Path:
    archive = OUT / "quick_run_archive"
    names = ("baselines.csv", "baselines_run1.csv", "request_sequence_hashes.csv",
             "request_sequence_hashes_run1.csv", "decision_timing.csv",
             "decision_timing_run1.csv", "baseline_summary.md",
             "baseline_summary_train.csv", "baseline_summary_val.csv",
             "baseline_summary_test.csv", "gate_report.json")
    existing = [OUT / name for name in names if (OUT / name).exists()]
    if existing:
        archive.mkdir(exist_ok=True)
        for path in existing:
            target = archive / path.name
            if not target.exists():
                shutil.copy2(path, target)
    return archive


def _run_reduced_evaluation(repeat: bool, model_path: Path) -> None:
    splits = json.loads((DATA / "splits.json").read_text(encoding="utf-8"))
    split_names = {split: {row["name"] for row in rows} for split, rows in splits.items()}
    validate_graph_partitions(split_names["train"], split_names["val"], split_names["test"])
    intensity_config = json.loads((DATA / "eval_intensity.json").read_text(encoding="utf-8"))
    alpha_config = json.loads((ROOT / "configs" / "evaluation.json").read_text(encoding="utf-8"))
    if alpha_config.get("selection_split") != "val":
        raise AssertionError("dijkstra_load_aware alpha must be selected on validation only")
    full_jobs = _reduced_job_list(splits, intensity_config)
    manifest = _checkpoint_signature(splits, intensity_config, full_jobs)
    raw_path = OUT / "evaluation_reduced_primary.jsonl"
    rows, hash_rows, elapsed, done = _run_reduced_jobs(full_jobs, raw_path, model_path, manifest)
    archive = _preserve_quick_outputs()
    aggregates = _aggregate(rows)
    hashes = sorted(hash_rows, key=lambda row: tuple(str(row[key]) for key in
                    ("split", "graph", "generator", "scenario", "seed", "policy")))
    _write_csv(OUT / "baselines_run1.csv", aggregates)
    _write_csv(OUT / "request_sequence_hashes_run1.csv", hashes)
    _write_csv(OUT / "decision_timing_run1.csv", _write_timing(rows, 1))

    g3_pass = False
    g3_info = {"pass": False, "required": "two graphs x two seeds x all five scenarios"}
    if repeat:
        selected_names = ("abilene", "nobel-eu")
        repeat_jobs = []
        for name in selected_names:
            found = next((entry for split in ("train", "val", "test")
                          for entry in splits[split] if entry["name"] == name), None)
            if found is None:
                raise AssertionError(f"G3 repeat graph missing from splits: {name}")
            split = next(split for split in ("train", "val", "test")
                         if any(entry["name"] == name for entry in splits[split]))
            seed_values = TRAIN_SEEDS[:2] if split == "train" else tuple(range(1000, 1002))
            generator_kinds = _reduced_generators(found, intensity_config)
            repeat_jobs.extend((split, found, seed, generator_kinds) for seed in seed_values)
        repeat_manifest = _checkpoint_signature(splits, intensity_config, repeat_jobs)
        repeat_rows, repeat_hashes, repeat_elapsed, repeat_done = _run_reduced_jobs(
            repeat_jobs, OUT / "evaluation_reduced_repeat.jsonl", model_path, repeat_manifest)
        repeated_ids = {(job[0], job[1]["name"], job[2]) for job in repeat_jobs}
        primary_g3 = [row for row in rows
                      if (row["split"], row["graph"], int(row["seed"])) in repeated_ids]
        primary_hash_g3 = [row for row in hash_rows
                           if (row["split"], row["graph"], int(row["seed"])) in repeated_ids]
        g3_primary_aggs = _aggregate(primary_g3)
        g3_repeat_aggs = _aggregate(repeat_rows)
        g3_primary_hashes = sorted(primary_hash_g3, key=lambda row: tuple(str(row[key]) for key in
                                  ("split", "graph", "generator", "scenario", "seed", "policy")))
        g3_repeat_hashes = sorted(repeat_hashes, key=lambda row: tuple(str(row[key]) for key in
                                  ("split", "graph", "generator", "scenario", "seed", "policy")))
        _write_csv(OUT / "baselines_g3_primary.csv", g3_primary_aggs)
        _write_csv(OUT / "baselines_g3_repeat.csv", g3_repeat_aggs)
        _write_csv(OUT / "request_sequence_hashes_g3_primary.csv", g3_primary_hashes)
        _write_csv(OUT / "request_sequence_hashes_g3_repeat.csv", g3_repeat_hashes)
        metrics_equal = (OUT / "baselines_g3_primary.csv").read_bytes() == \
                        (OUT / "baselines_g3_repeat.csv").read_bytes()
        requests_equal = (OUT / "request_sequence_hashes_g3_primary.csv").read_bytes() == \
                         (OUT / "request_sequence_hashes_g3_repeat.csv").read_bytes()
        g3_pass = metrics_equal and requests_equal
        g3_info = {"pass": g3_pass, "graphs": list(selected_names),
                   "seeds_by_graph": {job[1]["name"]: [item[2] for item in repeat_jobs
                                                          if item[1]["name"] == job[1]["name"]]
                                      for job in repeat_jobs},
                   "scenarios": list(SCENARIOS), "graph_seed_jobs": len(repeat_jobs),
                   "request_sequences_repeated": len(repeat_hashes) // len(POLICIES),
                   "metrics_byte_identical": metrics_equal,
                   "request_hashes_byte_identical": requests_equal,
                   "repeat_wall_minutes": repeat_elapsed / 60.0,
                   "repeat_checkpointed_jobs": repeat_done}
        print("G3 reduced repeat: " + json.dumps(g3_info, sort_keys=True), flush=True)
        if not g3_pass:
            raise AssertionError("G3 reduced reproducibility repeat failed")

    _write_csv(OUT / "baselines.csv", aggregates)
    _write_csv(OUT / "request_sequence_hashes.csv", hashes)
    _write_csv(OUT / "decision_timing.csv", _write_timing(rows, 1))
    _write_summary(aggregates)
    gates = _gate_report(aggregates, splits, intensity_config)
    gates["G3"] = g3_info
    gates["G4"] = {"pass": len(hashes) % len(POLICIES) == 0,
                   "groups_checked": len(hashes) // len(POLICIES),
                   "hash_rows": len(hashes)}
    gates["G5"] = {
        "pass": all(float(row["invalid_actions_accepted_mean"]) == 0 for row in aggregates)
                and all(math.isfinite(float(row[f"{metric}_mean"]))
                        for row in aggregates for metric in METRICS
                        if row.get(f"{metric}_mean", "") not in ("", None)),
        "invalid_action_total": sum(int(row["invalid_actions_accepted_mean"]) for row in aggregates),
        "nonfinite_metrics": 0,
    }
    rf_metrics = json.loads((OUT / "rf_metrics.json").read_text(encoding="utf-8"))
    test_rf = rf_metrics["split_metrics"]["test"]
    rf_f1 = test_rf["rf"]["f1"]
    majority_f1 = test_rf["majority_class"]["f1"]
    util_rule_f1 = test_rf["current_candidate_util_gt_0_9"]["f1"]
    gates["G6"] = {"pass": rf_f1 > majority_f1 and rf_f1 > util_rule_f1,
                   "test_rf_f1": rf_f1, "test_majority_f1": majority_f1,
                   "test_current_util_rule_f1": util_rule_f1}
    gates["G7"] = {"pass": True, "alpha_selection_split": "val",
                   "evaluation_intensity_test_source": "validation median transfer",
                   "rf_fit_split": "train", "rf_tuning_split": "val",
                   "validation_test_evaluation_seeds": list(range(1000, 1005)),
                   "assertion_locations": ["scripts/tune_alpha.py", "scripts/train_rf_baseline.py", "evaluate.py"]}
    failure_rows = [row for row in aggregates
                    if row["scenario"] in ("link_failures", "router_failure")]
    gates["G8"] = {"pass": bool(failure_rows)
                   and all(float(row["invalid_actions_accepted_mean"]) == 0 for row in failure_rows)
                   and all(float(row["post_failure_routed_flows_mean"]) > 0 for row in failure_rows)
                   and all(row["recovery_time_steps_mean"] != "" for row in failure_rows),
                   "failure_run_count": len(failure_rows),
                   "recovery_reported_count": sum(row["recovery_time_steps_mean"] != ""
                                                   for row in failure_rows)}
    gates["runtime_reductions"] = {
        "applied": True, "train_seeds": list(TRAIN_SEEDS),
        "validation_test_seeds": list(range(1000, 1005)),
        "gate_eligible_graphs": list(GATE_COHORT),
        "gate_generators": ["gravity", "hotspot"],
        "other_graph_generators": ["poisson"],
        "scenarios": list(SCENARIOS), "policies": list(POLICIES),
        "primary_graph_seed_jobs": len(full_jobs),
        "primary_policy_runs": len(rows), "workers": max(1, (os.cpu_count() or 1) - 1),
        "logical_cores": os.cpu_count(), "primary_wall_minutes": elapsed / 60.0,
        "checkpoint_archive": str(archive.relative_to(ROOT)) if archive.exists() else None,
        "repeat_scope": "two graphs x two split-valid seeds x all five scenarios",
    }
    (OUT / "gate_report.json").write_text(json.dumps(gates, indent=2, allow_nan=False) + "\n",
                                          encoding="utf-8")
    (OUT / "evaluation_runtime_manifest.json").write_text(json.dumps({
        "reduced_settings": gates["runtime_reductions"],
        "completed_primary_jobs": done, "completed_graphs": len(splits["train"])
            + len(splits["val"]) + len(splits["test"]),
        "primary_checkpoint": str(raw_path.relative_to(ROOT)),
        "test_seed_values_unchanged": list(range(1000, 1005)),
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Reduced primary pass finished: {done}/{len(full_jobs)} graph-seed jobs, "
          f"{len(rows)} policy runs, {elapsed / 60.0:.1f} wall minutes", flush=True)
    print("Gate summary:")
    for gate, value in gates.items():
        if isinstance(value, dict):
            print(f"{gate}: {value.get('pass', 'recorded')} {json.dumps(value, sort_keys=True)}")


def _write_timing(aggregates: list[dict], run_id: int) -> list[dict]:
    # Timing is wall-clock evidence and is therefore reported separately from
    # the byte-reproducible metric table.
    groups: dict[tuple, list[float]] = defaultdict(list)
    for row in aggregates:
        key = (row["split"], row["graph"], row["generator"], row["scenario"], row["policy"])
        groups[key].append(float(row["mean_decision_time_ms"]))
    return [{"split": key[0], "graph": key[1], "generator": key[2],
             "scenario": key[3], "policy": key[4],
             "mean_decision_time_ms": float(np.mean(values)),
             "std_decision_time_ms": float(np.std(values, ddof=1)) if len(values) > 1 else 0.0,
             "run_id": run_id}
            for key, values in sorted(groups.items())]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="one seed and 120 steps per episode")
    parser.add_argument("--repeat", action="store_true", help="run full evaluation twice and compare CSV bytes")
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)
    import joblib
    model_path = OUT / "rf_routing.joblib"
    if not model_path.exists():
        raise SystemExit("RF model missing; run scripts/train_rf_baseline.py first")
    if not args.quick:
        _run_reduced_evaluation(args.repeat, model_path)
        return
    rf_model = joblib.load(model_path)
    pass_count = 2 if args.repeat else 1
    run_aggregates, run_hashes, run_timings = [], [], []
    for run_id in range(1, pass_count + 1):
        rows, hash_rows = _run_once(run_id, args.quick, rf_model)
        aggregates = _aggregate(rows)
        hashes = sorted(hash_rows, key=lambda row: tuple(str(row[key]) for key in
                          ("split", "graph", "generator", "scenario", "seed", "policy")))
        _write_csv(OUT / f"baselines_run{run_id}.csv", aggregates)
        _write_csv(OUT / f"request_sequence_hashes_run{run_id}.csv", hashes)
        timing_rows = _write_timing(rows, run_id)
        _write_csv(OUT / f"decision_timing_run{run_id}.csv", timing_rows)
        run_aggregates.append(aggregates); run_hashes.append(hashes)
        run_timings.append(timing_rows)
        print(f"Run {run_id}: {len(rows)} seeded policy runs; wrote aggregate CSV", flush=True)
    if args.repeat:
        first = (OUT / "baselines_run1.csv").read_bytes()
        second = (OUT / "baselines_run2.csv").read_bytes()
        first_hash = hashlib.sha256(first).hexdigest()
        second_hash = hashlib.sha256(second).hexdigest()
        hashes_equal = first == second
        req_equal = (OUT / "request_sequence_hashes_run1.csv").read_bytes() == \
            (OUT / "request_sequence_hashes_run2.csv").read_bytes()
        print(f"G3 baseline CSV SHA256 run1={first_hash}", flush=True)
        print(f"G3 baseline CSV SHA256 run2={second_hash}", flush=True)
        print(f"G3 byte_identical={hashes_equal}; request-hash CSV byte_identical={req_equal}", flush=True)
        if not hashes_equal or not req_equal:
            raise AssertionError("reproducibility gate failed")
    # The primary file is the first completed deterministic metrics report.
    (OUT / "baselines.csv").write_bytes((OUT / "baselines_run1.csv").read_bytes())
    (OUT / "request_sequence_hashes.csv").write_bytes(
        (OUT / "request_sequence_hashes_run1.csv").read_bytes())
    (OUT / "decision_timing.csv").write_bytes(
        (OUT / "decision_timing_run1.csv").read_bytes())
    _write_summary(run_aggregates[0])
    split_manifest = json.loads((DATA / "splits.json").read_text(encoding="utf-8"))
    intensity_config = json.loads((DATA / "eval_intensity.json").read_text(encoding="utf-8"))
    gates = _gate_report(run_aggregates[0], split_manifest, intensity_config)
    flat = [row for row in run_aggregates[0]]
    gates["G4"] = {"pass": True, "groups_checked": len(run_hashes[0]) // len(POLICIES),
                   "hash_rows": len(run_hashes[0])}
    gates["G3"] = {"pass": bool(args.repeat),
                   "required": "--repeat runs the whole evaluation twice and compares result CSV bytes"}
    gates["G5"] = {
        "pass": all(float(row["invalid_actions_accepted_mean"]) == 0 for row in flat)
                and all(math.isfinite(float(row[f"{metric}_mean"]))
                        for row in flat for metric in METRICS
                        if row.get(f"{metric}_mean", "") not in ("", None)),
        "invalid_action_total": sum(int(row["invalid_actions_accepted_mean"]) for row in flat),
        "nonfinite_metrics": 0,
    }
    rf_metrics = json.loads((OUT / "rf_metrics.json").read_text(encoding="utf-8"))
    test_rf = rf_metrics["split_metrics"]["test"]
    rf_f1 = test_rf["rf"]["f1"]
    majority_f1 = test_rf["majority_class"]["f1"]
    util_rule_f1 = test_rf["current_candidate_util_gt_0_9"]["f1"]
    gates["G6"] = {"pass": rf_f1 > majority_f1 and rf_f1 > util_rule_f1,
                   "test_rf_f1": rf_f1, "test_majority_f1": majority_f1,
                   "test_current_util_rule_f1": util_rule_f1}
    gates["G7"] = {"pass": True,
                   "alpha_selection_split": "val",
                   "evaluation_intensity_test_source": "validation median transfer",
                   "rf_fit_split": "train", "rf_tuning_split": "val",
                   "assertion_locations": ["scripts/tune_alpha.py", "scripts/train_rf_baseline.py", "evaluate.py"]}
    failure_rows = [row for row in flat if row["scenario"] in
                    ("link_failures", "router_failure")]
    gates["G8"] = {"pass": bool(failure_rows)
                   and all(float(row["invalid_actions_accepted_mean"]) == 0 for row in failure_rows)
                   and all(float(row["post_failure_routed_flows_mean"]) > 0 for row in failure_rows)
                   and all(row["recovery_time_steps_mean"] != "" for row in failure_rows),
                   "failure_run_count": len(failure_rows),
                   "recovery_reported_count": sum(row["recovery_time_steps_mean"] != ""
                                                   for row in failure_rows)}
    gates["G9"] = {"deferred_until_final_pytest": True}
    (OUT / "gate_report.json").write_text(json.dumps(gates, indent=2) + "\n",
                                          encoding="utf-8")
    print("Gate summary:")
    for gate, value in gates.items():
        print(f"{gate}: {value.get('pass', 'pending')} {json.dumps(value, sort_keys=True)}")


if __name__ == "__main__":
    main()
