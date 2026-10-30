"""Create deterministic, family-disjoint splits from available real topologies."""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import random
import sys
import tarfile
from statistics import median
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT))

import networkx as nx

from env.topology import (cyclomatic_number, family_key, fingerprint, load_repetita,
                          load_sndlib, load_zoo, path_diversity, validate)
LOG = logging.getLogger("make_splits")
SEED = 2026


def _entry(graph: nx.Graph, source: str, relpath: str) -> dict[str, object]:
    return {"source": source, "path": relpath, "name": str(graph.graph["name"]),
            "family": family_key(str(graph.graph["name"])), "num_nodes": graph.number_of_nodes(),
            "num_edges": graph.number_of_edges(), "fingerprint": fingerprint(graph),
            "cyclomatic": cyclomatic_number(graph), "path_diversity": path_diversity(graph)}


def _load_zoo_items() -> tuple[list[tuple[nx.Graph, str]], int]:
    items: list[tuple[nx.Graph, str]] = []
    failures = 0
    direct = sorted((DATA / "30153949" / "graphml").rglob("*.graphml"))
    for path in direct:
        try: items.append((load_zoo(path), path.relative_to(DATA).as_posix()))
        except Exception as exc: failures += 1; LOG.warning("Zoo parse failed %s: %s", path, exc)
    archive = DATA / "30153949" / "graphml.tar.gz"
    if not direct and archive.exists():
        with tarfile.open(archive, "r:gz") as tf:
            members = sorted((m for m in tf.getmembers() if m.isfile() and m.name.lower().endswith(".graphml")), key=lambda m: m.name)
            for member in members:
                try:
                    stream = tf.extractfile(member)
                    if stream is None: raise OSError("archive member could not be read")
                    graph = load_zoo(stream.read())
                    items.append((graph, f"30153949/graphml.tar.gz::{member.name}"))
                except Exception as exc: failures += 1; LOG.warning("Zoo parse failed %s: %s", member.name, exc)
    return items, failures


def collect() -> tuple[list[dict[str, object]], dict[str, int]]:
    """Load networks independently, count failures, filter and deduplicate."""
    records: list[dict[str, object]] = []; failures = {"zoo": 0, "sndlib": 0, "repetita": 0}
    raw: list[tuple[nx.Graph, str, str]] = []
    try:
        zoo_items, failures["zoo"] = _load_zoo_items()
        raw.extend((g, "zoo", p) for g, p in zoo_items)
    except Exception as exc: LOG.warning("Zoo archive scan failed: %s", exc); failures["zoo"] += 1
    for path in sorted((DATA / "sndlib-networks-xml").glob("*.xml")):
        try:
            g, _ = load_sndlib(path); raw.append((g, "sndlib", path.relative_to(DATA).as_posix()))
        except Exception as exc: LOG.warning("SNDlib parse failed %s: %s", path, exc); failures["sndlib"] += 1
    for path in sorted((DATA / "Repetita-master" / "data").rglob("*.graph")):
        try:
            matching = sorted(path.parent.glob(path.stem + "*.demands"))
            g, _ = load_repetita(path, matching[0] if matching else None)
            raw.append((g, "repetita", path.relative_to(DATA).as_posix()))
        except Exception as exc: LOG.warning("REPETITA parse failed %s: %s", path, exc); failures["repetita"] += 1
    by_fingerprint: dict[str, list[dict[str, object]]] = {}
    clipped_by_source = {source: {key: {"clipped_low": 0, "clipped_high": 0}
                                   for key in ("bandwidth", "latency", "loss")}
                         for source in ("zoo", "sndlib", "repetita")}
    edge_totals = {source: 0 for source in clipped_by_source}
    missing_latency_totals = {source: 0 for source in clipped_by_source}
    rep_graphs_by_family: dict[str, list[nx.Graph]] = {}
    graphs_by_source: dict[str, list[nx.Graph]] = {s: [] for s in clipped_by_source}
    snd_networks: list[nx.Graph] = []
    for g, src, rel in raw:
        graph_counts = g.graph.get("_attribute_clip_counts", {})
        for metric in ("bandwidth", "latency", "loss"):
            for side in ("clipped_low", "clipped_high"):
                clipped_by_source[src][metric][side] += int(graph_counts.get(metric, {}).get(side, 0))
        edge_totals[src] += int(g.graph.get("_attribute_edge_count", g.number_of_edges()))
        missing_latency_totals[src] += int(g.graph.get("_latency_rederived_missing", 0))
        graphs_by_source[src].append(g)
        if src == "sndlib": snd_networks.append(g)
        if src == "repetita":
            rep_graphs_by_family.setdefault(family_key(str(g.graph.get("name", rel))), []).append(g)
        errors = validate(g)
        if errors:
            failures[src] += 1
            LOG.warning("Invalid %s network %s: %s", src, rel, "; ".join(errors))
            continue
        routers = sum(1 for _, d in g.nodes(data=True) if d.get("type") == "router")
        if not 8 <= routers <= 40: continue
        fp = fingerprint(g)
        by_fingerprint.setdefault(fp, []).append(_entry(g, src, rel))
    # Identical topologies occur in both Zoo and REPETITA. Keep one record,
    # balancing the retained provenance across sources instead of always
    # letting whichever folder was scanned first win every duplicate.
    source_totals = {source: 0 for source in ("zoo", "sndlib", "repetita")}
    groups = sorted(by_fingerprint.items())
    for fp, candidates in groups:
        sources = sorted({str(item["source"]) for item in candidates})
        source = min(sources, key=lambda value: (source_totals[value], value))
        chosen = min((item for item in candidates if item["source"] == source), key=lambda item: str(item["path"]))
        records.append(chosen); source_totals[source] += 1
    print("attribute diagnostics by source (all loaded networks):")
    for source, counts in clipped_by_source.items():
        metric_text = " ".join(
            f"{metric}[low={counts[metric]['clipped_low']},high={counts[metric]['clipped_high']}]"
            for metric in ("latency", "bandwidth", "loss")
        )
        print(f"  {source}: edges={edge_totals[source]} {metric_text} latency_rederived_missing={missing_latency_totals[source]}")
    family_names = sorted(rep_graphs_by_family)
    sample_rng = random.Random(SEED)
    sampled_families = sample_rng.sample(family_names, min(40, len(family_names)))
    sampled_graphs = [sample_rng.choice(rep_graphs_by_family[family]) for family in sampled_families]
    raw_delays = [float(attrs["raw_delay_us"]) for g in sampled_graphs
                  for _, _, attrs in g.edges(data=True) if "raw_delay_us" in attrs]
    raw_bins = {"0": 0, "1-99": 0, "100-999": 0, ">=1000": 0, "negative": 0}
    for delay in raw_delays:
        if delay < 0: raw_bins["negative"] += 1
        elif delay == 0: raw_bins["0"] += 1
        elif delay < 100: raw_bins["1-99"] += 1
        elif delay < 1000: raw_bins["100-999"] += 1
        else: raw_bins[">=1000"] += 1
    print(f"REPETITA raw delay_us distribution (fixed seed {SEED}, {len(sampled_graphs)} graphs / {len(sampled_families)} families, {len(raw_delays)} undirected edges): {raw_bins}")
    for g in snd_networks:
        long_links = []
        for u, v, attrs in g.edges(data=True):
            a, b = g.nodes[u], g.nodes[v]
            if "x" not in a or "x" not in b or a.get("_coordinates_geographical") is False or b.get("_coordinates_geographical") is False:
                continue
            lat1, lon1 = math.radians(float(a["y"])), math.radians(float(a["x"]))
            lat2, lon2 = math.radians(float(b["y"])), math.radians(float(b["x"]))
            h = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
            km = 6371 * 2 * math.asin(min(1.0, math.sqrt(h)))
            long_links.append((km, str(a.get("label", u)), str(b.get("label", v))))
        above = sum(km / 200.0 + 0.1 > 20.0 for km, _, _ in long_links)
        top = sorted(long_links, reverse=True)[:5]
        print(f"SNDlib {g.graph.get('name')}: edges={g.number_of_edges()} geographic_edges={len(long_links)} above_20ms={above}; longest=" +
              ("; ".join(f"{u}-{v} {km:.1f} km" for km,u,v in top) if top else "unavailable (pixel coordinates)"))
        if g.graph.get("name") == "abilene":
            print("Abilene links (u, v, haversine_km, latency_ms):")
            for km, u, v in sorted(long_links, key=lambda row: (row[1], row[2])):
                print(f"  {u:10s} {v:10s} {km:8.1f} {km/200.0+0.1:7.3f}")
            print("Abilene sanity: Sunnyvale-Seattle about 1136 km; Atlanta-Washington about 899 km")
    for source, graphs in graphs_by_source.items():
        sample = random.Random(SEED).sample(graphs, min(40, len(graphs)))
        latencies = [float(a["latency"]) for g in sample for _, _, a in g.edges(data=True)]
        floors = sum(value == 0.1 for value in (float(a["latency"]) for g in graphs for _, _, a in g.edges(data=True)))
        all_edges = sum(g.number_of_edges() for g in graphs)
        if latencies:
            print(f"{source} latency sample (fixed seed {SEED}, {len(sample)} graphs/{all_edges} total edges): "
                  f"floor_edges={floors}/{all_edges} ({100*floors/max(1,all_edges):.2f}%), "
                  f"min={min(latencies):.6g} median={median(latencies):.6g} max={max(latencies):.6g} ms")
    return records, failures


def create_splits(records: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    """Assign disjoint families satisfying size, density, and path resilience."""
    families: dict[str, list[dict[str, object]]] = {}
    for rec in records: families.setdefault(str(rec["family"]), []).append(rec)
    buckets: dict[str, list[dict[str, object]]] = {k: [] for k in ("train", "val", "test")}
    targets = {"train": 12, "val": 5, "test": 5}
    selected: set[str] = set()
    seed_order = random.Random(SEED).sample(sorted(families), len(families))
    family_rank = {family: index for index, family in enumerate(seed_order)}
    source_counts = {source: 0 for source in ("zoo", "sndlib", "repetita")}
    split_sources = {key: set() for key in buckets}
    dense_train_count = 0

    def avg_degree(entry: dict[str, object]) -> float:
        return 2.0 * int(entry["num_edges"]) / max(1, int(entry["num_nodes"]))

    def candidates(predicate, source: str | None = None):
        return [(family, entry) for family, entries in families.items() if family not in selected
                for entry in entries if predicate(entry) and (source is None or entry["source"] == source)]

    def eligible(split: str, entry: dict[str, object]) -> bool:
        return (int(entry["cyclomatic"]) >= 3
                and float(entry["path_diversity"]) >= (0.3 if split == "train" else 0.5)
                and (split == "train" or avg_degree(entry) <= 5.0))

    def choose(split: str, options, size_target: int) -> None:
        nonlocal dense_train_count
        if not options:
            raise ValueError(f"not enough eligible family groups for {split} split constraints")
        family, entry = min(options, key=lambda pair: (
            source_counts[str(pair[1]["source"])],
            abs(int(pair[1]["num_nodes"]) - size_target),
            avg_degree(pair[1]), family_rank[str(pair[0])], str(pair[1]["source"]), str(pair[1]["path"]),
        ))
        buckets[split].append(entry)
        selected.add(family)
        source = str(entry["source"])
        source_counts[source] += 1
        split_sources[split].add(source)
        if split == "train" and avg_degree(entry) > 5.0:
            dense_train_count += 1

    # Reserve the mandated 20–40 router representatives first, all sparse.
    for split, count in (("train", 1), ("val", 1), ("test", 2)):
        for _ in range(count):
            choose(split, candidates(lambda e: 20 <= int(e["num_nodes"]) <= 40 and eligible(split, e)), 30)

    # Keep every source represented in every split when eligible families exist.
    for split in buckets:
        for source in source_counts:
            if source in split_sources[split] or len(buckets[split]) >= targets[split]:
                continue
            options = candidates(lambda e: eligible(split, e), source)
            if options:
                choose(split, options, 15)

    # Fill remaining slots with sparse graphs. Dense graphs are an exceptional
    # fallback in train only, and no more than one may enter that split.
    for split, target in targets.items():
        while len(buckets[split]) < target:
            options = candidates(lambda e: eligible(split, e))
            if not options and split == "train" and dense_train_count == 0:
                options = candidates(lambda e: eligible(split, e) and avg_degree(e) > 5.0)
            choose(split, options, 14 + 2 * (len(buckets[split]) % 4))
    for value in buckets.values(): value.sort(key=lambda e: (str(e["source"]), str(e["name"]), str(e["path"])))
    return buckets


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="replace existing split files")
    args = parser.parse_args()
    out, lock = DATA / "splits.json", DATA / "splits.lock"
    if out.exists() and not args.force:
        raise SystemExit(f"Refusing to overwrite {out}; pass --force to replace it")
    previous = json.loads(out.read_text(encoding="utf-8")) if out.exists() else None
    if out.exists() and args.force: print(f"WARNING: --force is replacing existing {out}")
    records, failures = collect()
    splits = create_splits(records)
    encoded = json.dumps(splits, indent=2, sort_keys=True) + "\n"
    test_entries = json.dumps(sorted(splits["test"], key=lambda x: json.dumps(x, sort_keys=True)), sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(test_entries).hexdigest()
    out.write_text(encoded, encoding="utf-8")
    lock.write_text(digest + "\n", encoding="ascii")
    print("split  zoo  sndlib  repetita  total")
    for split, entries in splits.items():
        counts = {src: sum(e["source"] == src for e in entries) for src in ("zoo", "sndlib", "repetita")}
        print(f"{split:5}  {counts['zoo']:3}  {counts['sndlib']:6}  {counts['repetita']:8}  {len(entries):5}")
    print("split  name  source  #nodes  #edges  avg_degree  cyclomatic  path_diversity")
    for split, entries in splits.items():
        for e in entries:
            avg = 2 * int(e["num_edges"]) / int(e["num_nodes"])
            print(f"{split:5}  {e['name']}  {e['source']}  {e['num_nodes']}  {e['num_edges']}  {avg:.3f}  {e['cyclomatic']}  {e['path_diversity']:.3f}")
    if previous:
        for split, entries in splits.items():
            old_by_name = {str(e["name"]): e for e in previous.get(split, [])}
            new_by_name = {str(e["name"]): e for e in entries}
            print(f"{split} removed: {sorted(set(old_by_name)-set(new_by_name))}; added: {sorted(set(new_by_name)-set(old_by_name))}")
    print(f"unique families: {len({str(r['family']) for r in records})}; parse failures: {failures}")
    for source, count in failures.items(): print(f"{source} failed files: {count}")
    print(f"test sha256: {digest}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    main()
