# Day 5.3–5.4 model variants

## Scope and compatibility

This part adds optional model and learner code in `models/day5_variants.py`,
`models/day5_temporal.py`, and opt-in constructor arguments on `models/gnn.py`.
The flags `dueling`, `noisy_net`, `gru_history`, `mlp_encoder`, and
`auxiliary_utilization` default to `false`. Day 4 model weights loaded through
the flag-off path reproduce the existing Q-values within `1e-6`. No
environment, reward, baseline, split, or evaluation code was changed.

The Day 5 smoke worker loads topologies only through the existing guarded
train-split loader. It uses the Day 5.2 `dijkstra_load_aware_k` expert labels
for its fixed auxiliary behavior-cloning minibatch. Smoke jobs do not run
validation scoring or load any locked holdout topology; their progress line
therefore reports `val loss n/a`.

## Model and learner options

- **Dueling:** `Q(s,a) = V(s) + A(s,a) - mean(A(s,a') for valid a')`.
  `V` uses the mean and max node pools concatenated with flow features. Invalid
  candidates do not enter the advantage mean; a single valid action has a
  zero-centered advantage.
- **N-step:** the default Day 5 ladder uses `n=3`, with discounted rewards over
  consecutive stored decisions from one episode. A truncated tail bootstraps
  from its final next state using `gamma^n`; a terminated tail does not
  bootstrap. Idle and forced-invalid decisions do not enter replay. A partial
  tail is flushed against the final observation if the episode ends on an
  unstored decision.
- **Prioritized replay:** proportional priorities use `alpha=0.6`,
  `priority=abs(TD error)+1e-3`, and new items start at the current maximum.
  Importance `beta` increases linearly from `0.4` to `1.0`; weights are
  normalized by the sampled batch maximum.
- **Noisy Nets:** factorized Gaussian layers with `sigma0=0.1` replace the
  three path-scorer linear layers. Noisy mode bypasses epsilon-greedy action
  selection. Online noise is resampled for action selection and updates. The
  target network stays in evaluation mode and uses its learned `mu` weights
  without noise. Evaluation also uses `mu` weights, making repeated
  evaluations deterministic.
- **GRU:** the shared GATv2 encoder processes each of the four oldest-first
  history snapshots. A 64-wide GRU runs over time per node; the final hidden
  state feeds the path scorer.
- **Auxiliary utilization head:** for each directed edge, endpoint embeddings
  and edge features from the *current* observation predict that same edge's
  utilization in the *next* observation, clipped to `[0, 2]`. The current and
  next snapshots must have identical directed edge row order; loss is computed
  only on rows marked as router-to-router edges in both snapshots. The head
  uses Huber loss with weight `0.1`. This temporal separation prevents the
  target utilization from being fed directly to its predictor. The optional
  fixed expert BC loss has weight `0.1` and uses only the permitted expert
  policy.
- **MLP encoder ablation:** a per-node MLP of width 64 replaces message
  passing. Its node embeddings do not depend on `edge_index`.

Non-Noisy Day 5 smoke policies anneal epsilon from `0.10` to `0.02` over the
first 30% of steps. The learning defaults are `lr=1e-4`, `tau=0.002`,
`gamma=0.95`, Huber loss, gradient norm 10, learning start 2,000, and
500-step episodes. Training intensities are sampled log-uniformly from
`[0.01, 0.30]`.

## History storage

The smoke worker keeps the 25,000-item replay capacity. Float32 histories
were compacted to float16 in replay after measuring the payload and testing
Q-value fidelity. Histories are converted back to float32 for model
computation.

| Replay representation | Bytes per transition | Payload at capacity 25,000 | Payload for 12 processes |
|---|---:|---:|---:|
| Without history snapshots | 4,976 | 118.64 MiB | 1.39 GiB |
| T=4 history, float32 | 20,400 | 486.37 MiB | 5.70 GiB |
| T=4 history, float16 | 12,688 | 302.51 MiB | 3.54 GiB |

These fixed-shape payload measurements use a guarded train graph and include
both state and next state; the 12-process column is replay payload only. In the
actual L5 run across sampled train graphs, mean stored transition payload was
10,994.7 bytes, equivalent to 262.13 MiB per full replay. On the fixed
float16-fidelity probe, the maximum Q difference was `0.00000182` (limit
`0.001`); the unit test also verifies the limit.

The final L5 3,000-step profile's measured full process-tree peak RSS was
694.67 MiB. With 15.73 GiB physical RAM, the measured-smoke cap gives
`W=min(12, floor(0.65 * 15.73 GiB / 694.67 MiB))=12`.
`12 * peak RSS = 8.14 GiB`, or 51.8% of physical RAM. The separate capacity
figures above are payload-only, not an RSS measurement of a fully populated
25,000-entry replay.

## Smoke results

All rows ran 3,000 environment steps with 251 optimizer updates. The loss
column gives optimizer Huber loss min / median / max. “|Q| min–max” is the
observed absolute-Q range. Each checkpoint was reloaded and matched its saved
Q-values with maximum absolute difference `0.0`. No optimizer loss was NaN or
infinite.

The ladder/MLP and no-GRU ablation jobs ran in the corrected 7-worker batch;
the other GRU ablations ran in the earlier 6-worker batch. L5 and
`profile_no_gru_single` were individual profile runs. The latter is an extra
full-stack comparator, not one of the 14 requested configurations.

| Configuration | steps/s | Loss min / median / max | \|Q\| min–max | peak RSS MiB | history |
|---|---:|---:|---:|---:|---|
| L0 base | 36.60 | 8.53 / 13.65 / 22.76 | 44.03–115.70 | 445.9 | none |
| L1 dueling | 33.50 | 2.47 / 4.60 / 9.74 | 4.62–60.01 | 443.8 | none |
| L2 n-step | 32.03 | 2.68 / 5.72 / 11.77 | 8.37–63.59 | 448.7 | none |
| L3 prioritized | 32.67 | 0.26 / 2.37 / 10.43 | 7.52–72.26 | 449.4 | none |
| L4 Noisy | 26.89 | 0.53 / 2.66 / 10.88 | 15.14–76.27 | 510.0 | none |
| L5 GRU + auxiliary | 4.70 | 0.24 / 2.67 / 10.67 | 15.79–62.44 | 694.7 | float16 |
| MLP encoder | 42.05 | 4.95 / 8.23 / 14.21 | 95.70–133.18 | 417.6 | none |
| Ablation: no dueling | 4.63 | 0.57 / 4.61 / 18.90 | 86.13–123.85 | 742.2 | float16 |
| Ablation: no PER and n-step | 5.17 | 1.55 / 2.62 / 4.72 | 5.15–54.69 | 749.4 | float16 |
| Ablation: no GRU | 20.76 | 0.34 / 2.17 / 8.70 | 11.59–75.76 | 550.8 | none |
| Ablation: no auxiliary head | 7.10 | 0.49 / 2.81 / 8.93 | 13.69–50.09 | 645.6 | float16 |
| Ablation: no GAT (MLP) | 7.39 | 0.26 / 2.48 / 7.38 | 6.33–51.33 | 599.5 | float16 |
| Ablation: no imitation | 5.28 | 0.07 / 1.81 / 3.76 | 0.12–5.23 | 633.6 | float16 |
| Ablation: no NoisyNet | 5.11 | 0.16 / 1.79 / 7.53 | 10.53–56.41 | 618.3 | float16 |
| Full stack, no GRU (single-worker comparator) | 28.28 | 0.59 / 3.57 / 11.12 | 16.66–63.56 | 537.7 | none |

Non-GRU rates across the requested configurations were 20.76–42.05 steps/s,
and GRU rates were 4.63–7.39 steps/s. In the single-worker full-stack
comparison, adding GRU changed 28.28 to 4.70 steps/s, a 6.02x slowdown, so
the addendum requires a separate step budget and a user choice before any
final study. Several smoke configs exceeded |Q|=100; this is reported without
tuning or adding Q clipping.

For architecture transfer from `bc_init.pt`, L5 copied 30 matching tensors
and freshly initialized 24 tensors: the four `history_gru` weights/biases,
the four `auxiliary_head` weights/biases, the four dueling `value_head`
weights/biases, and the `weight_sigma`, `bias_sigma`, `weight_epsilon`, and
`bias_epsilon` parameters for each of the three noisy scorer layers. The MLP
variant copied 30 matching tensors and freshly initialized the four
`node_mlp` weights/biases; its other matching scorer parameters were copied.

## Step budget

Using the slowest observed rate in each requested family gives
`S_non-GRU=floor(3,000 * 20.7566)=62,269` and
`S_GRU=floor(3,000 * 4.6275)=13,882` steps for a 50-minute wave. These rates
are smoke rates under different concurrency levels, so treat the per-family
budgets as conservative estimates, not a controlled throughput benchmark.
With 18 non-GRU runs and 21 GRU runs, `W=12` implies two waves per family and
about 200 minutes total (3 h 20 min), excluding validation overhead. A common
budget for all configs would be `S=13,882`; separate budgets are explicitly
unfair. No final-study run was launched.

The measured GRU slowdown exceeds 2x. Before a final study, choose one:
(1) same S for all with GRU at history T=2, (2) same S for all and fewer
seeds for GRU configs, (3) different S per family (unfair), or (4) drop GRU
from FULL and run it as a separate small experiment.
