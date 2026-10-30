"""Select per-graph evaluation intensities without inspecting test results."""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from env.network_env import NetworkEnvConfig, NetworkRoutingEnv
from env.traffic import (GravityTrafficGenerator, HotspotTrafficGenerator,
                         PoissonTrafficGenerator, SNDlibReplay)
from scripts.calibrate_traffic import DEMAND_FRACTIONS, load_graph, make_traffic
from baselines.leakage import validate_graph_partitions

DATA = ROOT / "data"
OUTPUT = DATA / "eval_intensity.json"
CALIBRATION = ROOT / "outputs" / "calibration_v2.csv"
COARSE = (0.05, 0.1, 0.15, 0.2, 0.3, 0.45)
FINE = tuple(round(0.025 * i, 3) for i in range(1, 25))
GENERATORS = ("poisson", "gravity", "hotspot", "sndlib")
SUPPLEMENTAL = ROOT / "outputs" / "eval_intensity_calibration.csv"


def select_row(rows: list[dict]) -> dict | None:
    in_band = [row for row in rows if 0.30 <= float(row["fraction_steps_max_backbone_gt_0_9"]) <= 0.60]
    if not in_band:
        return None
    return min(in_band, key=lambda row: abs(
        float(row["fraction_steps_max_backbone_gt_0_9"]) - 0.45))


def write_calibration_rows(path: Path, measured: dict, entry_by_name: dict) -> None:
    fields = ("split", "graph", "generator", "intensity",
              "fraction_steps_max_backbone_gt_0_9", "mean_max_backbone_utilization",
              "source")
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for (graph, kind), rows in sorted(measured.items()):
            for row in rows:
                writer.writerow({
                    "split": entry_by_name[graph]["split"], "graph": graph,
                    "generator": kind, "intensity": row["target_intensity"],
                    "fraction_steps_max_backbone_gt_0_9": row["fraction_steps_max_backbone_gt_0_9"],
                    "mean_max_backbone_utilization": row.get(
                        "_mean_max", row.get("mean_max_backbone_utilization", "")),
                    "source": row.get("_source", "outputs/calibration_v2.csv"),
                })
        f.flush()
    temporary.replace(path)


def static_measure(entry: dict, kind: str, intensity: float,
                   episodes: int, steps: int, warmup: int) -> dict[str, float]:
    import networkx as nx
    import numpy as np
    from env.paths import PathResult

    graph = load_graph(entry)
    config = NetworkEnvConfig(max_steps=steps, intensity=intensity)
    stub = PoissonTrafficGenerator(sorted(graph.nodes), demand_mbps=1.0)
    topology = NetworkRoutingEnv(graph, config, traffic_generator=stub)
    if kind == "sndlib" and entry["source"] != "sndlib":
        raise ValueError("SNDlib replay is only available on SNDlib source graphs")
    common = dict(demand_mbps=1.0, intensity=intensity)
    if kind == "poisson":
        traffic = PoissonTrafficGenerator(topology.host_nodes, **common)
    elif kind == "gravity":
        costs = {}
        for src in topology.host_nodes:
            lengths = nx.single_source_dijkstra_path_length(topology.graph, src, weight="latency")
            for dst in topology.host_nodes:
                if dst != src:
                    costs[src, dst] = float(lengths[dst])
        traffic = GravityTrafficGenerator(topology.host_nodes,
                                          {n: 1.0 for n in topology.host_nodes},
                                          costs, **common)
    elif kind == "hotspot":
        hot = topology.host_nodes[:max(1, math.ceil(len(topology.host_nodes) / 4))]
        traffic = HotspotTrafficGenerator(topology.host_nodes, hot,
                                          hotspot_multiplier=4.0, **common)
    elif kind == "sndlib":
        traffic = SNDlibReplay.from_sndlib(list(topology.router_nodes),
                                            DATA / entry["path"], **common)
    else:
        raise ValueError(kind)
    traffic.configure_for_network(topology.graph, topology.router_nodes,
                                  intensity, DEMAND_FRACTIONS)
    env = NetworkRoutingEnv(graph, config, traffic_generator=traffic)
    values = []
    for episode in range(episodes):
        env.reset(seed=41_000 + episode + sum(map(ord, entry["name"])))
        for step in range(steps):
            if env.flow is None or not env._paths.paths:
                action = env.config.k_paths
            else:
                path = tuple(nx.shortest_path(env.graph, env.flow.source,
                                              env.flow.destination, weight="latency"))
                env._paths = PathResult((path,), False)
                action = 0
            _obs, _reward, _term, _trunc, info = env.step(action)
            if step >= warmup:
                values.append(float(info["step_max_backbone_utilization"]))
    array = np.asarray(values, dtype=float)
    return {"mean_max": float(np.mean(array)),
            "fraction_over": float(np.mean(array > 0.9 + 1e-9))}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="short diagnostic sweep")
    parser.add_argument("--force", action="store_true", help="replace eval_intensity.json")
    args = parser.parse_args()
    if OUTPUT.exists() and not args.force:
        raise SystemExit(f"{OUTPUT} exists; pass --force to regenerate it")
    splits = json.loads((DATA / "splits.json").read_text(encoding="utf-8"))
    entries = [{**entry, "split": split}
               for split, networks in splits.items() for entry in networks]
    entry_by_name = {entry["name"]: entry for entry in entries}
    validate_graph_partitions(
        [e["name"] for e in entries if e["split"] == "train"],
        [e["name"] for e in entries if e["split"] == "val"],
        [e["name"] for e in entries if e["split"] == "test"])

    # Existing rows are admissible only for train graphs. Test calibration rows
    # are intentionally discarded; test settings transfer from validation.
    measured: dict[tuple[str, str], list[dict]] = defaultdict(list)
    if CALIBRATION.exists():
        with CALIBRATION.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row["split"] == "train" and row["policy"] == "static_latency_shortest":
                    measured[(row["name"], row["generator"])].append(row)

    episodes, steps, warmup = (1, 180, 40) if args.quick else (3, 500, 100)
    for entry in entries:
        if entry["split"] == "test":
            continue
        applicable = [kind for kind in GENERATORS
                      if kind != "sndlib" or entry["source"] == "sndlib"]
        for kind in applicable:
            key = (entry["name"], kind)
            rows = measured.get(key, [])
            if select_row(rows) is not None:
                continue
            print(f"Calibrating {entry['split']} graph {entry['name']} / {kind}", flush=True)
            already = {float(row["target_intensity"]) for row in rows}
            for intensity in COARSE:
                if intensity in already:
                    continue
                metrics = static_measure(entry, kind, intensity,
                                         episodes, steps, warmup)
                rows.append({
                    "target_intensity": str(intensity),
                    "fraction_steps_max_backbone_gt_0_9": str(metrics["fraction_over"]),
                    "_mean_max": metrics["mean_max"],
                    "_source": "supplemental_coarse",
                })
            if select_row(rows) is None:
                print(f"  No coarse point in 0.30-0.60; running graph-specific fine points",
                      flush=True)
                for intensity in FINE:
                    if intensity in {float(row["target_intensity"]) for row in rows}:
                        continue
                    metrics = static_measure(entry, kind, intensity,
                                             episodes, steps, warmup)
                    rows.append({
                        "target_intensity": str(intensity),
                        "fraction_steps_max_backbone_gt_0_9": str(metrics["fraction_over"]),
                        "_mean_max": metrics["mean_max"],
                        "_source": "supplemental_fine",
                    })
            measured[key] = rows
        write_calibration_rows(SUPPLEMENTAL, measured, entry_by_name)
        print(f"Finished evaluation-intensity calibration for {entry['name']}", flush=True)

    # Select train/validation settings from only non-test measurements.
    result: dict[str, dict] = {}
    chosen_val: dict[str, list[float]] = defaultdict(list)
    for entry in entries:
        name = entry["name"]
        result[name] = {"split": entry["split"], "generators": {},
                        "path_diversity": entry["path_diversity"]}
        kinds = [kind for kind in GENERATORS
                 if kind != "sndlib" or entry["source"] == "sndlib"]
        for kind in kinds:
            if entry["split"] == "test":
                continue
            rows = measured.get((name, kind), [])
            chosen = select_row(rows)
            if chosen:
                value = float(chosen["target_intensity"])
                result[name]["generators"][kind] = {
                    "intensity": value,
                    "fraction_over_0_9": float(chosen["fraction_steps_max_backbone_gt_0_9"]),
                    "status": "selected_within_band",
                    "source": chosen.get("_source", "outputs/calibration_v2.csv"),
                }
                if entry["split"] == "val":
                    chosen_val[kind].append(value)
            else:
                # Fine sweep point not bracketed: make explicit rather than
                # manufacturing an in-band intensity.
                rows = measured.get((name, kind), [])
                if rows:
                    closest = min(rows, key=lambda row: abs(
                        float(row["fraction_steps_max_backbone_gt_0_9"]) - 0.45))
                    intensity = float(closest["target_intensity"])
                else:
                    intensity = 0.1
                result[name]["generators"][kind] = {
                    "intensity": intensity, "status": "cannot_congest",
                    "source": "non-test sweep did not reach 0.30-0.60",
                }
    for entry in entries:
        if entry["split"] != "test":
            continue
        name = entry["name"]
        for kind in [g for g in GENERATORS
                     if g != "sndlib" or entry["source"] == "sndlib"]:
            values = chosen_val.get(kind, [])
            # Test intensities are transferred from validation; no test metrics,
            # calibration rows, labels, or topology scores affect this choice.
            result[name]["generators"][kind] = {
                "intensity": float(sorted(values)[len(values) // 2]) if values else 0.1,
                "status": "validation_transfer",
                "source": "median selected validation intensity",
            }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    write_calibration_rows(SUPPLEMENTAL, measured, entry_by_name)
    print(f"Wrote {OUTPUT}", flush=True)


if __name__ == "__main__":
    main()
