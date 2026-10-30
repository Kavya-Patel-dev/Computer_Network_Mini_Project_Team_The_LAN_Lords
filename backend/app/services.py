from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

AI_ROOT = Path(__file__).resolve().parents[2] / "AI"
MODEL_PATH = AI_ROOT / "runs" / "day5" / "final_routing_model.pt"
MODEL_SHA256 = "45957597F56CF163C5AE5D69F6FE6959DDB638601C7ADE97B865A848151FFF28"

ROUTING_DEVICE_TYPES = {
    "router", "cisco_2911", "cisco_2901", "cisco_1941", "cisco_4321", "cisco_1841",
    "cisco_2811", "cisco_819", "cisco_829", "cisco_2620xm", "cisco_4331", "cisco_4351",
    "cisco_4451", "router_pt", "catalyst_2960", "catalyst_2950", "catalyst_2960x",
    "catalyst_3560", "catalyst_3650", "catalyst_3750", "catalyst_3850", "catalyst_9200",
    "multilayer_switch_pt", "switch_pt", "bridge_pt", "hub_pt", "repeater_pt", "coaxial_splitter",
    "ap_pt", "wlc_pt", "cell_tower", "asa_5506", "asa_5505", "asa_5508", "ips_pt", "wrt300n",
    "home_gateway", "cloud_pt", "dsl_modem", "cable_modem", "dslam_pt",
}


def _model_api():
    ai_root = str(AI_ROOT)
    if ai_root not in sys.path:
        sys.path.insert(0, ai_root)
    from models import api  # imported lazily; model loading remains in the frozen API
    return api


def model_sha256() -> str:
    if not MODEL_PATH.is_file():
        raise FileNotFoundError("frozen routing checkpoint is missing")
    digest = hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest().upper()
    if digest != MODEL_SHA256:
        raise RuntimeError("frozen routing checkpoint integrity check failed")
    return digest


def prepare_model_runtime() -> None:
    """Import and validate the model package before dispatching CPU work to a thread."""
    _model_api()


def frontend_topology_to_model(topology: dict[str, Any]) -> dict[str, Any]:
    """Translate the canvas schema into the Day 1 model API schema."""
    nodes = topology.get("nodes")
    links = topology.get("links")
    if not isinstance(nodes, list) or not isinstance(links, list):
        raise ValueError("topology needs nodes and links arrays")
    result_nodes = []
    for node in nodes:
        if not isinstance(node, dict) or not node.get("id"):
            raise ValueError("every topology node needs an id")
        kind = str(node.get("type", ""))
        role = node.get("simulationRole")
        is_router = role == "router" if role in {"router", "host"} else kind in ROUTING_DEVICE_TYPES
        result_nodes.append({
            "id": str(node["id"]),
            "type": "router" if is_router else "host",
            "label": str(node.get("label", node["id"])),
            **({"x": node["x"], "y": node["y"]} if "x" in node and "y" in node else {}),
        })
    result_links = []
    for link in links:
        if not isinstance(link, dict):
            raise ValueError("every topology link must be an object")
        if link.get("simulationIncluded") is False:
            continue
        result_links.append({
            "src": link.get("src"),
            "dst": link.get("dst"),
            "bandwidth": link.get("bandwidth", link.get("bandwidth_mbps", link.get("capacity_mbps"))),
            "latency": link.get("latency", link.get("latency_ms")),
            "loss_percent": link.get("loss_percent", link.get("loss", 0.0)),
        })
    return {"name": str(topology.get("name", "user-topology")), "nodes": result_nodes, "links": result_links}


def frontend_flows_to_model(flows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    class_map = {
        "real_time": "REAL_TIME", "streaming": "STREAMING",
        "bulk": "BULK", "background": "BACKGROUND",
        "REAL_TIME": "REAL_TIME", "STREAMING": "STREAMING",
        "BULK": "BULK", "BACKGROUND": "BACKGROUND",
    }
    for row in flows:
        if not isinstance(row, dict):
            raise ValueError("each flow must be an object")
        qos = row.get("qos_class", row.get("class", "bulk"))
        if qos not in class_map:
            raise ValueError(f"unsupported flow class: {qos}")
        result.append({
            "flow_id": str(row.get("flow_id", row.get("id", "manual-flow"))),
            "source": row.get("source", row.get("src")),
            "destination": row.get("destination", row.get("dst")),
            "demand_mbps": row.get("demand_mbps", row.get("demand")),
            "qos_class": class_map[qos],
            "priority": row.get("priority", 2),
            "duration_steps": row.get("duration_steps", 20),
        })
    return result


def run_simulation(topology: dict[str, Any], traffic: str | list[dict[str, Any]],
                   scenario: str, seed: int, max_steps: int) -> dict[str, Any]:
    api = _model_api()
    model_topology = frontend_topology_to_model(topology)
    model_traffic: str | list[dict[str, Any]] = (
        frontend_flows_to_model(traffic) if isinstance(traffic, list) else traffic
    )
    model_scenario = "link_failures" if scenario == "link_failure" else scenario
    return api.simulate(model_topology, model_traffic, model_scenario,
                        seed=seed, max_steps=max_steps)


def serialize_json(value: Any) -> str:
    return json.dumps(value, allow_nan=False, separators=(",", ":"))
