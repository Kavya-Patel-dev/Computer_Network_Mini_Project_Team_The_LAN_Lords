# Network routing environment interface

## Spaces and feature meanings

For `N` topology nodes, `E` topology edges, `K=config.k_paths`, and `T=config.history_length`, `NetworkRoutingEnv.observation_space` is a Gymnasium `spaces.Dict`:

| Field | Shape and dtype | Columns / meaning | Typical range |
|---|---|---|---|
| `node_features` | `(N, 6)`, `float32` | `[incident offered load / incident capacity, up, node_type, is_src, is_dst, degree / max_degree]` | Load is `>=0` and may exceed 1; all other columns are in `[0,1]`. `node_type` is 0 for router, 1 for host. `degree` is in `[0,1]`. |
| `edge_features` | `(E, 5)`, `float32` | `[offered-load utilization, latency_ms, loss_probability, up, capacity_Mbps]` | Utilization `>=0` and may exceed 1; latency `>=0` and capped queue contribution; loss/up in `[0,1]`; capacity `>0` when up and zero after a failure. |
| `flow_features` | `(7,)`, `float32` | `[offered_demand, qos_REAL_TIME, qos_STREAMING, qos_BULK, qos_BACKGROUND, priority, remaining_duration_steps]` | Demand `>=0`; QoS entries are one-hot or all-zero without a flow; priority and duration are nonnegative. |
| `candidate_paths` | `(K, N)`, `int32` | Candidate routes as node indices in `NetworkRoutingEnv.nodes` order. | Valid indices are `[0,N-1]`; unused path positions and rows are `-1`. |
| `action_mask` | `(K+1,)`, `int8` | Valid candidate actions followed by sentinel action `K`. | Binary. |
| `edge_index` | `(2, E)`, `int32` | Each column is the endpoint node indices for the corresponding `edge_features` and `history_edges` row. | Indices in `[0,N-1]`. |
| `history_nodes` | `(T, N, 6)`, `float32` | Past/current node feature snapshots, oldest first. Includes static metadata and each snapshot's source/destination markers. | Same ranges as `node_features`. |
| `history_edges` | `(T, E, 5)`, `float32` | Past/current edge feature snapshots, oldest first. | Same ranges as `edge_features`. |

There is no adjacency matrix. Graphs are undirected and each undirected edge is stored once in `edge_index`, using the canonical sorted endpoint order from `NetworkMonitor.edges`. Column `j` of `edge_index` corresponds exactly to row `j` of `edge_features` and `history_edges`. The array is available as `env.edge_index`, in every observation, and in the `reset()` info dictionary. It is static for an episode, including when links fail.

`flow_features` has a fixed size independent of topology size; source and destination identity is instead encoded by the `is_src` and `is_dst` node columns. Features are not normalized by the environment beyond existing incident-load/capacity utilization, requested degree/max-degree, one-hot, and binary encodings. A future normalization wrapper should account for unbounded load, demand, capacity, and latency values.

For a topology with `N=18`, `E=23`, `K=4`, and `T=4`, with automatic host attachment disabled, the exact Gymnasium representations are:

```text
observation_space = Dict('action_mask': MultiBinary(5), 'candidate_paths': Box(-1, 17, (4, 18), int32), 'edge_features': Box(0.0, 3.4028235e+38, (23, 5), float32), 'edge_index': Box(0, 17, (2, 23), int32), 'flow_features': Box(0.0, 3.4028235e+38, (7,), float32), 'history_edges': Box(0.0, 3.4028235e+38, (4, 23, 5), float32), 'history_nodes': Box(0.0, 3.4028235e+38, (4, 18, 6), float32), 'node_features': Box(0.0, 3.4028235e+38, (18, 6), float32))
action_space = Discrete(5)
```

The action space is `spaces.Discrete(K+1)`. Actions `0..K-1` select the corresponding candidate row; a masked action receives the failed-route penalty. Rows beyond the available candidate count are entirely `-1` and their corresponding action-mask entries are zero. Action `K` is the idle/no-route sentinel. It is valid only when there is no active flow or no candidate path; with an active flow and at least one candidate it is masked.

## Flows and hosts

By default, the environment attaches `max(minimum_hosts, ceil(hosts_per_router_fraction * router_count))` leaf hosts; defaults are a fraction of `0.5` and a minimum of `4`. These are configurable through `NetworkEnvConfig`. The built-in generator samples source/destination pairs from hosts only when hosts exist; otherwise it uses routers. A caller-supplied traffic generator controls its own endpoint set and may use any topology nodes.

Time is measured in decision steps. Reset creates the request for the first decision, and each nonterminal step creates exactly one next request. The generator keeps no request FIFO and creates no backlog; its arrival rate is fixed at one request per decision step. The `PoissonTrafficGenerator` name is retained for compatibility, but it now selects a uniform random OD pair for each single request rather than drawing a Poisson count. Gravity, hotspot, and SNDlib replay also produce exactly one request per decision step.

Each request's lifetime is drawn from a geometric distribution using the generator's seeded RNG. For a network-calibrated environment, the mean lifetime is selected from the intensity formula below and clamped to `[3, 200]` decision steps. A standalone, uncalibrated traffic generator defaults to a 20-step mean. The lifetime clock begins when a flow is successfully routed. A successful route installs demand on every link of that path; all active flows contribute to aggregate link loads, latency, loss, and utilization. When the sampled duration expires, the flow's demand is removed from each link. An idle, invalid, or unroutable request is never installed and occupies no capacity.

When a link or router failure makes an installed path unavailable, the whole affected flow is invalidated and released from all edges on its path; it is not rerouted. A bandwidth drop does not invalidate flows: their offered loads remain and latency/loss are recomputed against the reduced capacity. Timed bandwidth restoration similarly keeps flows installed and recomputes metrics against restored capacity.

`intensity` is a target for capacity-weighted average router-backbone utilization, not a per-flow demand multiplier. The demand reference is the median router-to-router link capacity, and each flow's demand is sampled uniformly from 5% to 20% of that median using the seeded RNG. Since there is exactly one request per decision step, Little's law controls intensity through mean flow duration:

```text
intensity = mean_duration * mean_demand * mean_router_path_hops / total_router_link_capacity
mean_duration = intensity * total_router_link_capacity / (mean_demand * mean_router_path_hops)
```

`mean_router_path_hops` is the OD-weighted number of router-to-router edges on latency-weighted shortest paths. `total_router_link_capacity` is the sum of router-to-router link capacities; host-access links are excluded. The duration mean is clamped to `[3, 200]`; the generator reports both requested and achievable intensity when a clamp binds. An uncalibrated environment-owned or caller-supplied generator is configured with `configure_for_network(graph, router_nodes, target_intensity, demand_fraction_range)`. Gravity and hotspot use their configured OD weighting, and SNDlib replay uses matrix-weighted OD proportions.

## Episode, termination, and info

The default time limit is 1,000 decision steps. Reaching `max_steps` returns `terminated=False, truncated=True`. There are currently no real terminal conditions, so `terminated` remains false. `reset(seed=...)` returns `(observation, info)` with `time`, `flow_id`, and `edge_index`. `step(action)` returns `(observation, reward, terminated, truncated, info)`; info reports `time`, `no_route`, `invalid_action`, `selected_path`, `flow_id`, `available_paths`, `active_flow_count`, `routed_flow_id`, `expired_flows`, `invalidated_flows`, full-network `step_max_utilization`, `step_max_access_utilization`, `step_max_backbone_utilization`, and capacity-weighted `step_mean_backbone_utilization`. Failed decisions also provide `failure_cause` as `idle_action`, `masked_or_invalid_action`, or `no_route_due_to_failures`. Successful route decisions additionally report `path_latency_ms`, `path_loss`, `delivered_mbps`, full-path `path_max_utilization`, backbone-only `path_max_backbone_utilization`, and `reward_components` (latency, loss, bandwidth, minimum-bandwidth, utilization, quality-cost, and flap terms). A failed route reports failure and flap reward components.

## Reward, congestion, and clipping

The reward component definitions and weights are unchanged. The utilization term has configurable `RewardConfig.utilization_weight`, default `0.1`; its input is the maximum utilization among router-router links on the selected path. Latency and loss continue to use every link on the path, including host access links. The unchanged nonfailure components are:

| Component | Per-step contribution before the common QoS and priority factors |
|---|---|
| Latency | `-latency_sensitivity * path_latency_ms / latency_scale_ms` |
| Loss | `-loss_sensitivity * path_loss / loss_scale` |
| Bandwidth | `bandwidth_credit` |
| Minimum bandwidth | `-max(0, min_bandwidth_mbps - delivered_mbps) / target_bandwidth_mbps` |
| Utilization | `-utilization_weight * min(max_path_backbone_utilization, 2.0)` |
| Flap | The existing separate `flap_penalty` when the same-flow route changes without meaningful quality improvement |

The common factor is `profile.reward_weight * priority_factor`; the quality-cost diagnostic is not added a second time. Failed routing still receives the configured failure penalty. Queue latency uses the M/M/1 model and `NetworkEnvConfig.max_queue_ms`, default **10,000 ms (10 seconds)**, as a finite guard near saturation. Congestion loss is zero below capacity and bounded by `max_loss` above capacity.

The scalar reward is **not clipped**. Queue delay is capped by `max_queue_ms`, the utilization reward component caps its backbone-utilization input at 2.0, and the congestion loss model is bounded by `max_loss`; these caps affect reward inputs/components, not a final reward clipping operation. The substantially negative REAL_TIME saturation example (about -460) used a 10 ms propagation link at/above its 100 Mbps capacity, which drives queue delay to the 10,000 ms cap. The earlier environment minimum of -10 was the failed-route penalty: the idle sentinel was then still selectable for an active routable flow. It is now masked in that state. Current random-valid-action runs had zero steps at the failure-penalty floor; their ordinary 1 Mbps flows also did not recreate the saturation-table condition.

## SNDlib replay and calibration

The Day 1 XML loader returns each numeric `demandValue` unchanged and does not infer units or normalize values. Abilene and GEANT XML declare `MBITPERSEC`; their `<origin>` notes say “scaled directed peak matrix” and “total demand 3Tbps” (periods: 6 months for Abilene, 4 months for GEANT). Raw matrix sums near 3,000,000 are normalized traffic-matrix values and should not be described as Mbps.

When an `SNDlibReplay` is used by the environment, its raw matrix values define OD sampling proportions, not per-flow Mbps. Exactly one OD request is sampled per decision step, with probability proportional to its raw `demandValue`; there is no FIFO request queue or backlog. The request receives the same seeded 5%-20% median-backbone-capacity demand draw and geometric lifetime as other sources. Its duration is calibrated from the SNDlib-matrix-weighted static shortest-path mean router-hop count using the common formula above. The matrix is not started in full on every step, and its raw values are not converted into individual Mbps demands.

The legacy `SNDlibReplay.from_sndlib(..., scale_to_max_util=0.9)` option remains available for explicitly scaling the full static matrix's maximum utilization; it is separate from concurrent environment replay. Raw XML demand values remain unchanged by the Day 1 loader and should not be described as Mbps.

The Day 2 final calibration diagnostic is `scripts/calibrate_traffic.py`. It measures congestion on router-router backbone links only; host-access links are excluded from backbone max and mean utilization (access maximum is separately recorded). Static policy remains latency-shortest routing. Greedy remains selection of the candidate with the lowest predicted maximum utilization, now measured over the candidate's backbone links. Static and greedy policy rules were otherwise unchanged.

For each request, exactly one arrival is generated per decision step. The target is set only by mean lifetime and per-flow demand. Demand is drawn uniformly from 5%-20% of median router-router capacity, and the geometric duration mean is `target_intensity * total_router_link_capacity / (mean_demand * mean_router_path_hops)`, clamped to 3-200 decision steps. There is no arrival-rate parameter or request backlog. Realized mean utilization is the capacity-weighted mean across backbone edges over measured steps after a 100-step warm-up.

The v2 sweep tests intensities `{0.05, 0.1, 0.15, 0.2, 0.3, 0.45}` on eight graphs: train Abilene, Nsfnet, Peer1, New York, GEANT, and Renater2004; test Nobel-EU and DeutscheTelekom. Each graph uses Poisson/uniform-OD, gravity, and hotspot traffic; SNDlib graphs additionally use matrix-weighted SNDlib replay. Every graph/generator/intensity/policy setting runs three 500-step episodes, excluding the first 100 steps from metrics. The complete 336-row report is [outputs/calibration_v2.csv](../outputs/calibration_v2.csv). It records graph, source, node/edge counts, backbone bridge count, router-level path diversity, generator, target and achievable intensity, duration mean and clamp, realized static mean backbone utilization, policy, time-mean maximum backbone utilization, fraction of measured steps above 0.9, mean packet loss, and supporting access-utilization, path-latency, and loss-flow metrics. The script prints progress after each graph and details for any clamp or target miss.

The expected-load formula was within 20% of target on 166 of the 168 graph/generator/intensity settings. The two misses were both at target 0.05 with the minimum duration of 3 steps: Abilene/SNDlib requested 0.05, achieved 0.0767 by the formula, and realized 0.0757; Nsfnet/hotspot requested 0.05, achieved 0.0654, and realized 0.0660. Both realized values are within 20% of their achievable intensities. The other low-clamp case, Abilene/hotspot at 0.05, achieved 0.0506 and realized 0.0508, within 20% of the requested target. No upper-duration clamp occurred.

No tested intensity satisfies the complete requested default criterion across the seven graphs whose router-level path diversity is at least 0.5. For these aggregate figures, generator rows are averaged equally within each graph, then the seven eligible graphs are averaged equally. At 0.05, static routing has a mean fraction of steps over 0.9 backbone utilization of 0.4394, within the required 0.30-0.60 range. Greedy reduces it to 0.2342, but the required half-static maximum is 0.2197; mean loss does fall by more than half, from 0.03633 to 0.01414. At every higher tested intensity, the eligible-graph average static overload fraction exceeds 0.60 (0.6277 at 0.1, rising to 0.9982 at 0.45). I would use **0.05 as the provisional default among tested values**, while recording that no tested value fully meets the joint criterion. At 0.05, only Nobel-EU meets the complete criteria graph-by-graph:

| Graph | Backbone bridges | Router path diversity | Mean max backbone util, static → greedy | Fraction steps > 0.9, static → greedy | Mean loss, static → greedy | Result at 0.05 |
|---|---:|---:|---:|---:|---:|---|
| Abilene | 1 | 0.8333 | 0.7209 → 0.5501 | 0.2823 → 0.1071 | 0.01917 → 0.00169 | No: static overload fraction below 0.30 |
| Nsfnet | 3 | 0.5769 | 0.2732 → 0.2324 | 0.0000 → 0.0000 | 0.00000 → 0.00000 | No overload to improve |
| Peer1 | 4 | 0.5500 | 0.2901 → 0.2662 | 0.0003 → 0.0000 | 0.00000 → 0.00000 | No overload to improve |
| New York | 0 | 1.0000 | 1.3060 → 0.4807 | 0.6856 → 0.0717 | 0.05312 → 0.00010 | No: static overload fraction above 0.60 |
| GEANT | 0 | 1.0000 | 1.4362 → 0.9524 | 0.7763 → 0.4981 | 0.06546 → 0.01422 | No: static overload fraction above 0.60; greedy does not halve it |
| Renater2004 | 11 | 0.3931 | 0.5240 → 0.5105 | 0.1050 → 0.1050 | 0.00724 → 0.00724 | Excluded from eligible average (diversity < 0.5); bridges leave no measured policy gain |
| Nobel-EU | 0 | 1.0000 | 0.9311 → 0.5949 | 0.4442 → 0.1692 | 0.02799 → 0.00327 | Pass |
| DeutscheTelekom | 5 | 0.5885 | 1.6649 → 1.5499 | 0.8872 → 0.7933 | 0.08857 → 0.07971 | No: static fraction above 0.60; five bridges constrain alternatives |

The per-graph values average that graph's generator rows equally at intensity 0.05. The two ring-rich, non-bridged graphs New York and GEANT show strong load-aware improvement but are already above the allowed static-overload range at this setting. Nsfnet and Peer1 are underloaded at 0.05. Renater2004 has 11 backbone bridges and path diversity 0.3931, so it is excluded from the aggregate criterion and shows no change in overload fraction or loss. DeutscheTelekom has path diversity 0.5885 but five bridges; greedy produces only small reductions. These outcomes explain why one tested intensity cannot satisfy every requirement at once.

The Day 2 traffic calibration remains a diagnostic script, separate from the
Day 3 baseline package and evaluation harness.

## Day 3: baselines and evaluation protocol

Day 1 and Day 2 files remain frozen. Day 3 code lives in `baselines/`,
`evaluate.py`, and `scripts/`; it does not alter the environment or split
manifest. The per-graph/per-generator evaluation intensities are recorded in
`data/eval_intensity.json`. They are selected from the existing
`outputs/calibration_v2.csv` by choosing the tested intensity whose static
routing overload fraction is closest to 0.45, accepting values from 0.30 to
0.60. Only non-test calibration rows are used to make that choice. Where a
train/validation graph has no tested point in range, the selection script adds
fine sweep points for that graph only; if the band remains unreachable, that
graph/generator is marked `cannot_congest`. Test graph settings are the median
of the selected validation intensities for the matching generator, with the
source string `median selected validation intensity`. The evaluator asserts
this source for every test entry. The complete selection record, including
test transfers, is in `outputs/eval_intensity_calibration.csv`.

Training traffic intensity is log-uniform on `[0.03, 0.30]`, defined in
`configs/training.json`. Training seeds begin at 20000. Evaluation seeds come
from the fixed range 1000 through 1009; collection and tuning scripts reject
these seeds for training. The runtime-controlled final evaluation used 1000
through 1004 on validation and test. The selected dynamic-cost coefficient is
`alpha=4.0`. It was chosen
on validation graphs by mean packet loss from `{0.5, 1, 2, 4}`; validation
losses were 0.006306, 0.005705, 0.005195, and 0.005061 respectively. The
selection record is `configs/evaluation.json`.

The evaluation policies are `random`, `dijkstra_static`,
`dijkstra_load_aware`, `dijkstra_load_aware_k`, `ecmp`, `greedy_min_util`, and
`rf_routing`. Full-graph Dijkstra routes are installed by an evaluation-only
hook that temporarily supplies one explicit `PathResult`, then invokes the
normal environment step. It does not change the agent-facing action space or
candidate checks; a test verifies that a noncandidate action remains invalid
through the public Day 2 API. The two full-graph Dijkstra policies observe
exact current utilization without noise, so they are upper-bound-style
references. Their specified link cost is
`latency * (1 + alpha * u / (1 - min(u, 0.95)))`, where `u` is the current
utilization. The `*_k` variant applies the same cost only to candidate paths.
ECMP samples uniformly among candidate routes within 1% of the best latency;
`greedy_min_util` retains the Day 2 definition.

`evaluate.py` uses 500 decision steps per episode and excludes the first 100
steps from metrics. Train uses seeds 20000, 20001, and 20002; the final
runtime-reduced validation/test pass uses seeds 1000 through 1004. All policies
for a graph/generator/scenario/seed receive the same generated
request sequence and schedule. The harness hashes each canonical flow request
and asserts equality across policies. Scenarios are normal traffic, two
non-bridge backbone-link failures at steps 200 and 220 restored at 260 and
280, a non-articulation router failure at 200 restored at 260, a 4x demand
spike for 50 steps, and 50% bandwidth drops on three links for 100 steps.
The fixed graph-specific failure plan is reproducible from the graph name.
Metric rows include mean and p95 path latency, mean packet loss, delivered
throughput, mean and p95 maximum backbone utilization, fraction of steps above
0.9 maximum backbone utilization, route-flapping rate, inference time per
decision, invalid-action count, and recovery time.

The reported flapping rate is the fraction of repeated successful requests
for the same source/destination pair whose selected path differs from the
previous successful request for that same pair. Different OD pairs are never
compared. The CSV also records the number of repeated-OD comparisons used as
the denominator; the environment does not reroute an already installed flow.

Recovery time is measured after a failure as the number of steps until a
complete rolling ten-new-flow window returns within 10% of the mean loss over
the ten new-flow decisions before failure. When that pre-failure loss is at or
below 0.001, the absolute tolerance is 0.001. Recovery is capped at episode
end and flagged as censored when no qualifying window occurs. A synthetic
unit test covers this calculation. Per-graph raw JSONL rows are flushed
incrementally; final metric and request-hash CSVs are written after a pass.
Wall-clock inference measurements are saved separately
in `outputs/decision_timing.csv`, because runtime measurements naturally vary
between repeated executions.

## Day 3: expert data and RF routing

The compact expert dataset is stored as NPZ shards in `data/expert/shards/`
with `data/expert/manifest.json`. It contains exactly 200,000 train-split
decisions over all 12 train graphs, 100,000 selected by
`dijkstra_load_aware_k` and 100,000 by `greedy_min_util`. The experts agreed on
116,674 of 200,000 decisions (58.337%). Chosen action-index counts were 0:
87,473; 1: 43,201; 2: 37,619; and 3: 31,707. Each shard preserves environment
candidate ordering, the full Day 2 observation, valid-action mask, action,
reward, graph name, and seed. Evaluation seeds are listed as forbidden in the
manifest.

The RF model is fitted on train graph shards, tuned on validation graph
shards, and evaluated only afterward on test graph shards. Each candidate
feature row contains path maximum/mean backbone utilization, hop count, total
latency, minimum residual capacity, demand divided by residual capacity, QoS
one-hot fields, network-wide maximum/mean backbone utilization, active-flow
count, and time since failure. The positive label is 1 when the candidate's
counterfactual maximum backbone utilization exceeds 0.9 in any of the next
five decision states after installation; the installation state itself is
not part of that five-step horizon. The actually selected candidate is also
recorded. `rf_routing` chooses the candidate with the lowest predicted
congestion probability, breaking ties by latency.

With the corrected five-future-state label, the test set has 91,727 candidate
rows and 36,294 positive labels. RF test accuracy/precision/recall/F1 are
0.91224/0.90469/0.86984/0.88692. The majority-class baseline F1 is 0.00000;
the current-candidate-utilization-above-0.9 baseline F1 is 0.57407. RF
hyperparameter selection uses validation candidate-level F1 only; the test
split is not used for selecting model settings.

## Day 3: congestion sanity result

The synthetic diamond uses OD `s->t` and 25 Mbps demand. Static routing has
mean maximum backbone utilization 1.2188, overload fraction 0.9625, and mean
loss 0.115040. Its edge-disjoint unused alternative has maximum utilization
0.000000. `dijkstra_load_aware`, `dijkstra_load_aware_k`, and
`greedy_min_util` each have zero overload fraction and zero loss in this
case. On the real New York topology, static OD `R0->R12` uses direct edge
`R0-R12`; edge-disjoint alternative `R0-R11-R8-R12` stays at maximum
utilization 0.000000 under the static rollout. Static mean maximum backbone
utilization is 1.2188, overload fraction 0.9625, and mean loss 0.059375.
The load-aware full-graph policy and candidate-constrained policy both have
zero overload and loss; Day 2 greedy has zero overload and mean maximum
backbone utilization 0.1219.

The completed runtime-reduced primary pass wrote its baseline summaries, gate
results, request-sequence hashes, and per-graph tables to `outputs/`. The G3
reproducibility check reran two graphs, two split-valid seeds per graph, and
all five scenarios. It compared aggregate metrics and request hashes byte for
byte. See `outputs/baseline_summary.md`, the per-split CSV tables, and
`outputs/gate_report.json` for the recorded results.

## Day 3: runtime-controlled final evaluation

The original full schedule was estimated at approximately 3.1 hours per pass,
above the two-hour limit. Runtime reductions were therefore applied without
changing any gate threshold, scenario, seed value, or policy. Train retained
seeds 20000–20002; validation and test used the first five fixed evaluation
seeds, 1000–1004. The seven gate graphs (`abilene`, `Nsfnet`, `Peer1`,
`newyork`, `geant`, `nobel-eu`, and `DeutscheTelekom`) used gravity and hotspot
traffic. The other 15 graphs used Poisson traffic. All five scenarios and all
seven policies remained enabled.

The primary pass ran 86 graph/seed jobs, covering 3,885 policy runs, with a
23-process pool on 24 logical CPU cores. It completed all 22 graphs in 18.07
wall minutes. Each completed job was flushed to
`outputs/evaluation_reduced_primary.jsonl`; the earlier quick-run CSVs were
preserved in `outputs/quick_run_archive/` before the full results replaced the
standard baseline outputs.

The G3 repeat covered Abilene seeds 20000 and 20001 and nobel-eu seeds 1000
and 1001, across all five scenarios and both selected generators. Its four
graph/seed jobs completed in 2.63 minutes. All 40 repeated request sequences,
the aggregate metrics, and request-hash CSVs matched byte for byte. Gates G1
through G8 passed. G1 had six of seven eligible graphs where load-aware
routing improved both loss and overload fraction; G2 had five of seven graphs
with static overload fraction within the required 0.30–0.60 band. The
DeutscheTelekom and nobel-eu settings were above that band, while five graphs
met it. `pytest -q` passed: 92 tests in 6.46 seconds.
