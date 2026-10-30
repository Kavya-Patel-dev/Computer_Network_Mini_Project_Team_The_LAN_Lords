# The LAN Lords — routing model API

This project includes a frozen Day 5 behavior-cloned routing checkpoint and a
policy wrapper that can route one flow or simulate a topology. The API does
not train or tune the checkpoint.

## Setup

From the `AI` directory, use the project virtual environment:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.lock.txt
```

The `final_routing_model.pt` checkpoint is expected at
`runs/day5/final_routing_model.pt`; the API verifies its pinned SHA-256 before
loading it.

## Evaluate

Validation-only safety-wrapper comparison:

```powershell
.\venv\Scripts\python.exe scripts/day6_7_lite_eval.py --validation-only
```

The locked test suite has a one-time command. It refuses to run without the
explicit flag and refuses a second run after its one-shot marker is written:

```powershell
.\venv\Scripts\python.exe scripts/day6_7_lite_eval.py --allow-test-final
```

## Simulate

Compare static Dijkstra, load-aware Dijkstra, and the AI policy with fallback
on the included topology:

```powershell
.\venv\Scripts\python.exe -m models.api simulate examples/topology.json --traffic medium --scenario normal
```

Traffic presets map to target intensities: `light=0.05`, `medium=0.10`, and
`heavy=0.20`. Manual traffic may be supplied as a JSON list with
`--traffic flows --flows flows.json`. Supported scenarios are `normal`,
`link_failures`, `router_failure`, `traffic_spike`, and `bandwidth_drop`.

Topology input follows the Day 1 shape: `nodes` have `id` and `type`
(`router`/`host`); `links` have `src`, `dst`, `bandwidth` (Mbps), `latency`
(ms), and `loss_percent`. The graph must be connected, contain 5–50 routers,
and every host must be a leaf. Bandwidth and latency must be positive; loss
must be in `[0,100]` percent. Manual flow objects use `source`, `destination`,
`demand_mbps`, and optional `qos_class`, `priority`, `duration_steps`, and
`flow_id`.

The saved checkpoint is feed-forward (no GRU). The `route()` call accepts a
`history` argument for API stability, but this checkpoint does not consume it.
The inference-time fallback is outside the learned model and uses full-graph
`dijkstra_load_aware` with alpha `4.0`.
