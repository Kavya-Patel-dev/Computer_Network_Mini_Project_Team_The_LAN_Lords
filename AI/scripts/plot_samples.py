"""Save representative real and synthetic topologies under outputs/plots."""
from __future__ import annotations

import tarfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "outputs" / "plots"
sys.path.insert(0, str(ROOT))

import matplotlib.pyplot as plt
import networkx as nx

from env.topology import attach_hosts, generate_synthetic, load_repetita, load_sndlib, load_zoo


def _zoo_sample() -> nx.Graph:
    direct = sorted((DATA / "30153949" / "graphml").rglob("*.graphml"))
    if direct: return load_zoo(direct[0])
    archive = DATA / "30153949" / "graphml.tar.gz"
    with tarfile.open(archive, "r:gz") as tf:
        member = next(m for m in tf.getmembers() if m.name.lower().endswith(".graphml"))
        return load_zoo(tf.extractfile(member).read())


def _draw(graph: nx.Graph, path: Path, title: str) -> None:
    pos = nx.spring_layout(graph, seed=2026)
    routers = [n for n, d in graph.nodes(data=True) if d.get("type") == "router"]
    hosts = [n for n, d in graph.nodes(data=True) if d.get("type") == "host"]
    plt.figure(figsize=(9, 6))
    nx.draw_networkx_edges(graph, pos, alpha=0.55, width=0.8)
    nx.draw_networkx_nodes(graph, pos, nodelist=routers, node_color="#2c7fb8", node_size=45, label="routers")
    if hosts: nx.draw_networkx_nodes(graph, pos, nodelist=hosts, node_color="#f28e2b", node_shape="s", node_size=35, label="hosts")
    plt.title(title); plt.legend(); plt.axis("off"); plt.tight_layout(); plt.savefig(path, dpi=160); plt.close()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    _draw(_zoo_sample(), OUT / "zoo.png", "Topology Zoo sample")
    snd = sorted((DATA / "sndlib-networks-xml").glob("*.xml"))
    if snd: real, _ = load_sndlib(snd[0]); title = f"SNDlib: {snd[0].stem}"
    else:
        p = next((DATA / "Repetita-master" / "data").rglob("*.graph")); real, _ = load_repetita(p); title = f"REPETITA: {p.stem}"
    _draw(real, OUT / "sndlib.png", title)
    synthetic = generate_synthetic("ba", 16, 2026); attach_hosts(synthetic, 5, 2026)
    _draw(synthetic, OUT / "synthetic_hosts.png", "Synthetic BA topology with access hosts")
    print("Saved:", *(str(p) for p in sorted(OUT.glob("*.png"))), sep="\n")


if __name__ == "__main__": main()
