# Day 2 routing environment

`NetworkRoutingEnv` accepts a Day 1 undirected NetworkX topology and copies it. It does not modify the source graph or split manifests.

## Action and observation

The action space is `Discrete(K+1)`. Actions `0..K-1` choose entries in the current candidate list; action `K` is the explicit idle/no-route sentinel. With no current flow, the sentinel is idle and earns zero; with a current flow, it represents no route and receives `RewardConfig.failure_penalty * profile.reward_weight`. `observation["action_mask"]` has `K+1` binary values and is the authoritative validity mask. A masked route action receives the same failure penalty, and the selected path is revalidated before execution. Candidate paths are padded node-index sequences of shape `(K, N)` with `-1` padding.

The fixed-shape Dict observation contains node features `(N,2)` (incident offered load divided by incident capacity, UP flag), edge features `(E,5)` (utilization, latency ms, loss probability, UP flag, capacity Mbps), flow features (source/destination one-hot, Mbps demand, QoS class index, priority, remaining duration), candidate paths, action mask, and node/edge history with leading dimension `T`. Reset initializes all `T` history slots with the initial state. After a route decision, traffic and events update the next state and that state is appended; the oldest slot shifts out when full. Thus warm-up is left-padded with the initial state and history contains no future state. Arrivals are queued FIFO rather than discarded when more than one arrives in a timestep; a flow remains current for its configured duration.

## Traffic and QoS

Traffic models share seeded `reset`, `step`, and `sample_flow`. Poisson arrivals use `Pois(arrival_rate * timestep)`. Gravity OD weights are `source_weight * destination_weight / cost**distance_exponent`. Hotspot endpoints are sampled with configurable multiplier weights. `TrafficSpike` and `DiurnalPattern` multiply generated demand over configured time windows/periods. `SNDlibReplay` uses the tuples returned by `load_sndlib`; node mappings must resolve to valid distinct topology nodes or raise (or explicitly skip when requested).

QoS defaults are configurable relative policy weights (`min/target bandwidth` in Mbps):

| Class | Priority | Latency sensitivity | Loss sensitivity | Min/target Mbps | Reward weight |
|---|---:|---:|---:|---:|---:|
| REAL_TIME | 4 | 4.0 | 3.0 | 0.1 / 1.0 | 1.0 |
| STREAMING | 3 | 2.0 | 2.0 | 1.0 / 5.0 | 0.8 |
| BULK | 2 | 0.5 | 0.5 | 1.0 / 10.0 | 0.6 |
| BACKGROUND | 1 | 0.25 | 0.25 | 0.0 / 1.0 | 0.4 |

Loss sensitivity acts on probability; latency sensitivity acts on milliseconds. These are exposed policy defaults, not learned or dataset-derived values.

## Events and link models

Events are scheduled at integer simulation times and applied after the route decision at the end of that transition, affecting the returned next state. Link and router failures set UP false and capacity to zero; router failure also disables every incident link. `BandwidthDrop` sets capacity to `base_capacity * factor`, independently from UP/DOWN, and optionally restores it after a duration. Overlapping drops use the strongest active factor and restore in layers. `event_probability` optionally samples reproducible per-step link failure or persistent capacity drop using the environment RNG. Traffic timestep and spike/diurnal time units must use the same clock units.

Propagation latency is the existing Day 1 link latency in ms. Queue delay assumes fixed `packet_size_bits` and M/M/1 service. Offered load `L` and capacity `C` are Mbps; `lambda = L * 1e6 / packet_size_bits` and `mu = C * 1e6 / packet_size_bits` are packets/second; utilization is `rho = lambda/mu = L/C`. For `rho < 1 - congestion_epsilon`, mean system delay is `W_ms = 1000 / (mu - lambda)`. Within the epsilon margin of saturation, or at/above capacity, queue delay is the configured finite cap. Total link latency is propagation plus queue delay.

Congestion loss is deterministic: if `rho < 1`, loss is `0`; otherwise it is `min(max_loss, slope * (rho - 1) + min(slope * loss_epsilon, max_loss))`. This configurable small epsilon makes loss positive at saturation and increases monotonically above capacity, bounded in `[0,1]`. Path loss combines independent link-loss probabilities as `1 - product(1 - p_link)`.

NetworkX's Yen-based `shortest_simple_paths` provides up to K alternatives, ranked by propagation latency plus `load_weight * load/capacity`. The environment seeded-shuffles the candidate ordering at each state refresh so the best-ranked path is not always action zero; the path list in an observation defines its exact action mapping. Standalone optional edge-disjoint generation returns pairwise edge-disjoint paths only. A filtered graph excludes down routers, down/zero-capacity links, and invalid endpoints; no route is represented by an empty path list and `no_route=True`.

For a nonfailed route, reward is `profile.reward_weight * priority_factor * (bandwidth_credit - latency_cost - loss_cost - minimum_bandwidth_cost - utilization_cost) - flapping_penalty`, where `priority_factor = 1 + 0.05 * max(0, priority-1)`, `bandwidth_credit = min(1, delivered/demand) * min(1, delivered/target_bandwidth)` (the served fraction is 1 for zero demand), latency cost is `latency_sensitivity * path_latency_ms / latency_scale_ms`, loss cost is `loss_sensitivity * path_loss / loss_scale`, minimum-bandwidth cost is `max(0,min_bandwidth-delivered)/max(target_bandwidth,1e-12)`, and utilization cost is `utilization_weight * min(max_link_utilization,2)`. A failed route receives `-failure_penalty * profile.reward_weight`. A changed route incurs `flap_penalty * profile.reward_weight * priority_factor` only if its comparable same-flow quality-cost improvement is below the configured threshold and the previous path is still available; rerouting after a failed path is necessary and is not penalized. Initial route selection is not a flap. The `quality_cost` diagnostic is not added to reward a second time. REAL_TIME's latency sensitivity is deliberately greater than BULK's.
