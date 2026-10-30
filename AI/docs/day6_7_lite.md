# Day 6–7 Lite interface and safety policy

## Frozen checkpoint

`models.api` loads only `runs/day5/final_routing_model.pt` and verifies the
registered SHA-256 before model construction. The checkpoint is a feed-forward
GATv2 + dueling + noisy + auxiliary-head Double-DQN policy initialized from
behavior cloning; it has no GRU. Its `history` argument is accepted for API
stability but is not consumed by this checkpoint.

## Safety fallback

The inference wrapper stays outside the network and does not change its
weights. It uses full-graph `dijkstra_load_aware` with alpha `4.0` when there
is no valid candidate, any valid Q is non-finite, the selected action is
invalid, the selected path contains a down router/link, or the chosen path's
predicted maximum backbone utilization is above `1.0` while another valid
candidate is below `0.9`. The returned reason is one of `none`,
`no_valid_candidate`, `non_finite_q`, `invalid_action`, `failed_path`, or
`overloaded_candidate`.

## Public API

`route(topology_json, link_state, history, flow)` returns candidate paths,
masked Q values, selected candidate index/path, fallback status/reason, and
path-position attention weights. A fallback full-graph route may not belong to
the K candidates; in that case `chosen_index` is `null` and `chosen_path`
contains the Dijkstra route. `link_state` accepts edge-keyed records with
`up`, `capacity_mbps`, `load_mbps` or `utilization`, `latency_ms`, and
`loss_percent`.

`simulate(topology_json, flows_or_preset, scenario)` compares static Dijkstra,
load-aware Dijkstra (alpha 4.0), and AI plus fallback. Its metric fields match
the evaluation harness (`mean_packet_loss`, mean/p95 path latency, delivered
throughput, mean/p95 max backbone utilization, fraction above 0.9, route
flapping, decision time, recovery, invalid actions, and route coverage). The
AI result also includes a per-reason fallback count and rate.
Traffic presets map `light`, `medium`, and `heavy` to intensities `0.05`,
`0.10`, and `0.20`. User JSON link loss percentages are combined with
congestion loss as independent per-link loss probabilities in the API's
environment instance; the frozen environment source is unchanged.

Input topologies use the Day 1 `nodes` and `links` structure. They must be
connected, contain 5–50 routers, have only leaf hosts, positive bandwidth in
Mbps and latency in milliseconds, and loss in `[0, 100]` percent. Manual flows
must reference declared nodes and have distinct endpoints and nonnegative
demand.

## Evaluation protocol

The pre-registered criteria are committed in `docs/test_criteria.md` before
the final test-split run. Validation fallback comparison uses only validation
graphs, seeds `1000`–`1004`, Poisson traffic at the already-transferred
per-graph intensity, all five registered scenarios, 500 decisions, and a
100-decision warm-up. The final evaluation is a single command guarded by
`--allow-test-final`; it uses fixed intensities `0.05`, `0.10`, `0.20`, the
same five scenarios and seeds, and all seven registered baselines plus the
fallback-wrapped AI. A one-shot marker prevents accidental repeat runs.
