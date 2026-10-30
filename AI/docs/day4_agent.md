# Day 4 core agent

## Day 4 final status

Mechanics, B1, B3, and B5–B7 passed. B2 and B4 failed: reward improvement failed, and no checkpoint met the B4 control gate. The 25,000-step checkpoint was diagnostic only; it was not selected as a passing model.

The old `|Q| < 50` gate was too tight for the wrapper's reward range. With rewards clipped to `[-5, 2]` and `gamma = 0.95`, the absolute discounted-return bound is `5 / (1 - 0.95) = 100`. Day 5 therefore uses a training `|Q|` 99.9th percentile below 60 and an absolute maximum below 100.

## Day 5.1 replay memory estimate

The largest train graph shape used for this estimate is 45 nodes and 64 undirected links after host attachment. Each replay item stores current and next state. The estimate includes the Python/dataclass/list allowance of 1,450 bytes per transition and shares the static topology edge index. A history-inclusive estimate adds `history_nodes` and `history_edges` for both states at `T = 4`; the model itself continues to omit history.

| Stored representation | Estimated bytes per transition | Per process at 50k | 12 processes at 50k |
|---|---:|---:|---:|
| Without history snapshots | 10,426 | 497.2 MiB | 5.826 GiB |
| With `history_nodes` and `history_edges`, `T = 4` | 29,306 | 1,397.4 MiB | 16.376 GiB |

Physical RAM is 15.73 GiB; 60% is 9.438 GiB. The history-inclusive 50k projection exceeds that limit. Day 5 uses one replay capacity of **25,000 for every configuration**. At 25k this projects to 248.6 MiB per process without history and 698.7 MiB with history; across 12 processes the conservative history-inclusive projection is 8.188 GiB (52.1% of physical RAM). The Day 4 config remains unchanged; `configs/day5_1.json` records the Day 5 capacity.

## Day 5.1 learner profile

Profiled on the train-split abilene graph only, seed 27001, one PyTorch thread. Each row uses the same 1,200 collected replay transitions. The optimizer columns are the mean across exactly 100 measured updates after five warm-up updates; the separate live rate is a 1,000-environment-step run. Times are milliseconds per update.

| Variant | Batch / update interval | Live steps/s | Update wall ms | Collate | Online current | Online next | Target | Backward | Optimizer | Other |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Day 4 PyG reference | 64 / 4 | 23.17 | 154.88 | 5.58 | 36.47 | 29.42 | 29.72 | 50.04 | 1.15 | 2.50 |
| Ready tensors + custom collate | 64 / 4 | 25.08 | 159.60 | 0.80 | 38.80 | 30.98 | 31.46 | 53.83 | 1.25 | 2.48 |
| Plus duplicate-state reuse | 64 / 4 | 25.31 | 146.83 | 0.75 | 35.56 | 27.51 | 29.17 | 50.17 | 1.17 | 2.51 |
| Batch 128 / update 4 | 128 / 4 | 5.46 | 300.01 | 1.40 | 73.86 | 52.50 | 58.81 | 108.10 | 1.24 | 4.08 |
| Batch 64 / update 8 | 64 / 8 | 13.70 | 516.70 | 2.45 | 128.14 | 98.93 | 107.01 | 169.44 | 3.90 | 6.82 |

The fast path lowers PyG/collation time from 5.58 ms to 0.75 ms, and exact state reuse reduces redundant forwards where fingerprints match. For the best variant, three GNN forwards take about 92.24 ms and backward takes 50.17 ms; together these dominate the 146.83 ms update. The best measured whole-training rate is 25.31 steps/s, about 1.21x the stated Day 4 rate of 21 and below the 63 steps/s (3x) target. The measured breakdown explains the miss: collation is already below 1 ms, so further collation work cannot remove the roughly 142 ms of forward/backward work. Batch 128/update 4 and batch 64/update 8 were slower in this profile. `configs/day5_1.json` opts into ready tensors, custom collation, and exact duplicate reuse; the Day 4 config and constructor defaults remain on the original path.

The numerical-equivalence tests compare the PyG and custom-collate GAT outputs, including ready-tensor states, at absolute tolerance `1e-6`, and compare one duplicate-state-reuse optimizer loss to the reference path at the same tolerance. All passed.

## Day 5.1 parallel runner

`scripts/run_experiments.py` launches isolated worker processes, sets one thread per process, caps concurrency at 12, and gives each job its own run/checkpoint folder and log. It supports `--quick` and `--merge`; merge reads completed run summaries into one table. The smoke run uses four 2,000-step Stage B processes: two identical base config/seed jobs and two identical fast-path config/seed jobs. The paired traces check exact equality of all recorded optimizer losses from environment steps 1–1,000. Every Stage B worker loads only the train partition for training and the validation partition for checkpoint scoring; the held-out test split remains behind the existing guard.

The four smoke jobs completed; each recorded 485 optimizer updates and 235 losses in its first 1,000 environment steps. The duplicate seed pairs matched exactly. The two baseline copies ended at validation loss `0.005043`; the two fast-path copies ended at `0.004726`. The merged job table and per-run logs/trace files are in `outputs/day5_1/`. This parallel-run throughput includes validation scoring and is not comparable to the isolated 1,000-step profile above. The initial Windows RSS sampler measured only the small Python launcher process, so RSS for these completed jobs is marked unavailable; a follow-up probe confirmed the launcher has a separate Python child, and the runner now sums the launcher and child process tree for subsequent jobs. The first runner revision also printed a zero ETA while other workers were still active; the ETA now accounts for running and queued jobs. The replay RAM projections above are independent of those runner reporting fixes.

New tests are `test_custom_collate_matches_pyg_path_within_one_e_minus_six`, `test_tensor_replay_stores_ready_tensors_and_reuses_identical_states`, and `test_duplicate_state_reuse_matches_reference_update_loss_within_one_e_minus_six`.

## Frozen baseline and carry-over

The Day 4 reference commit is `f5d7f29560d80ab84a2b758ae13cd1592544931e` (`baseline before Day 4`). Day 4 additions are isolated to `models/`, `train.py`, Day 4 reporting/profile/control scripts, tests, outputs, and this document. The Day 2 environment, Day 3 baseline definitions and evaluator, and split files are compared against that commit.

The explicit full-graph route hook remains in `baselines/explicit_path.py`. It temporarily installs a singleton `PathResult`, invokes the ordinary environment action, and restores candidates through the existing environment refresh. It does not change the agent-facing Day 2 action interface.

The saved Day 3 ECMP tie rule used the current `env.latencies` values, which include the queueing term. The corrected carry-over run uses propagation `graph[u][v]["latency"]` only and preserves the existing 1% tie rule. The old queue-latency tie heuristic is labeled `ties_on_queue_latency`; the corrected policy is `ecmp`. The Day 3 baseline implementation remains unchanged.

The saved Day 3 row records contain per-episode means and p95 path latency, but not per-flow latency arrays or per-link latency values. Consequently, median path latency and the fraction of flows with a link at the 10,000 ms cap cannot be reconstructed for that old run. Day 4 validation captures these values during its requested validation-only evaluation.

## Agent observation wrapper

The wrapper is outside `env/` and does not change Day 2 observations or rewards. It excludes the environment's history arrays.

- Node features are copied from the observation as `(N, 6)`: normalized incident load, up flag, host flag, source flag, destination flag, and degree normalized by maximum degree.
- The underlying `edge_index` has one entry per undirected link and is duplicated in forward-then-reverse order to `(2, 2E)`. `edge_attr` rows follow exactly the same order and have five columns: utilization clipped to `[0, 2]`; `log1p(measured latency ms) / log1p(10000)`; loss probability; up flag; capacity divided by maximum base capacity in this graph.
- Flow features have fixed size 7: demand divided by this graph's median router-router capacity; four QoS indicators; priority; duration divided by 200 steps.
- Candidate features have shape `(K, 6)`: hop count; `log1p(total measured path latency)`; minimum residual-capacity share divided by demand and clipped to `[0, 5]`; maximum path-link utilization; mean path-link utilization; maximum backbone utilization. Padded candidates have zero feature rows and are masked.
- Feature transforms depend on physical graph capacities and observations, not node or edge counts. No history array is used by the model.

The wrapper alone scales the environment reward as `clip(raw_reward, -5, 2)`. Training logs retain the raw reward and the clipped-step fraction. If the only valid action is the idle sentinel, the agent does not evaluate the network and adds no replay transition. The environment still returns its original raw no-route failure penalty; the wrapper logs it and clips it for the reward diagnostic, but does not put it in replay.

## Model and Double DQN

Two GATv2 layers use four 16-channel heads (64 hidden features), edge dimension 5, residual connections, LayerNorm, and ELU. A third layer is optional and off by default. The path scorer attends over the node embeddings along each candidate path using an MLP on node-plus-flow features, keeps the attention weights, and concatenates the pooled path, source, destination, six candidate features, and seven flow features. Its two hidden layers have width 128 and produce one Q value per candidate. Parameters do not depend on topology size. PyG `Batch` encodes graphs of different sizes together.

Invalid candidate Q values are `-inf`; losses gather only the selected valid action. Double DQN uses the online network's masked argmax and the target network's value for that action. Only `terminated` stops bootstrapping; truncation does not. A state with no candidate has no replay action and contributes a zero next-state value because no candidate action exists.

The configured optimizer values are Adam `5e-4`, gamma `0.95`, Huber loss, gradient clipping `10`, soft target update `tau=0.005`, batch `64`, replay `50,000`, learning start `2,000`, and epsilon linear decay `1.0 → 0.05` over the first 30% of steps. Optimizer updates run once per four valid environment decisions to control CPU runtime; other listed starting values are unchanged. Replay stores current/next node and edge features, flow/candidate features, paths, masks, action, scaled reward, and termination flags—no history arrays. Topology edge indices are shared within an episode.

Training graph requests pass through `models/data_guard.py`. A requested graph in the locked holdout partition raises before its topology file is opened. Stage A uses only abilene; Stage B samples from the 12 train graphs. Validation checkpoint selection uses the five validation graphs only. No Day 4 training, tuning, checkpoint selection, or agent evaluation loads a holdout topology.

## Training and diagnostics

`train.py --stage A` runs the 30,000-step abilene overfit stage; `--quick` uses 5,000 steps. `--stage B` is configured for 300,000 steps; `--quick` uses 20,000. `--long` enables the optional 1,000,000-step Stage C, which is not run unless requested. Stage B samples a log-uniform intensity in `[0.01, 0.30]`, one generator per episode, and 500-step episodes. The lower bound change from 0.03 is deliberate: it includes the 0.025 uncongested control required by gate A6. Validation runs every 25,000 steps with seeds 30000 and 30001. The top three checkpoints by validation loss are retained; among them, the lowest-loss checkpoint passing the 0.025 control on Arpanet19728, Compuserve, and EliBackbone is selected. If none passes, no checkpoint is selected and the lowest-loss candidate is used only for diagnosis. TensorBoard logs raw/scaled reward, clipping fraction, loss, Q, epsilon, and validation metrics.

The CPU profile uses one PyTorch thread and one learner. On abilene, the measured profile was 1.848 environment steps/s with an optimizer update on every decision and four threads; changing to one update per four decisions increased this to 17.734 steps/s at four threads. With this update-to-data ratio (0.25), four and eight threads measured 17.734 and 14.457 steps/s. Caching static graph tensors measured 17.678 and 14.475 steps/s at four and eight threads; the one-thread cached profile measured 21.736 steps/s on abilene and 21.153 steps/s on the largest training graph (Renater2004). The optimizer dominated runtime, so parallel actors were not used. The selected bounded run is limited by the user's 45-minute runtime request rather than presented as a 300,000-step completion. A resumed run restores model weights and starts with fresh replay and optimizer state; it is not an exact process resume.

The runtime profile, replay estimate, validation metrics, learning-curve gate values, and action diagnostics are recorded in `outputs/day4/` when the runs complete. The minimum-delay control and K=4/K=6/full-graph diagnostics use train/validation graphs only.

## Recorded Day 4 run

Stage A reached 30,000 total environment steps. Its first process was interrupted after writing the 20,000-step model checkpoint; the saved weights were preserved, then used for the remaining 10,000 steps. Replay and optimizer state were not part of that checkpoint and restarted empty, so this was a weight continuation rather than an exact process resume. On the fixed abilene comparison, agent loss/overload was `0.010217 / 0.2900`, versus static `0.018505 / 0.3900` and greedy-min-util `0.005649 / 0.2437`. A3 passes against static and does not beat greedy on either metric.

The first-pass 20,000-step quick run and its checkpoint are preserved separately. The bounded Stage B run reached 52,000 steps, resuming weights from the 25,000-step validation checkpoint with fresh replay and optimizer state. An earlier live process had reached 29,640, but only its 25,000 checkpoint was persisted; the uncheckpointed tail was replayed from that checkpoint. The final 52,000-step training segment took about 26m50s from the persisted 25k checkpoint timestamp to the final save. This is a bounded partial run, not the configured 300,000-step training.

The segment's mean scaled reward for its first/last 10% was `-0.26852 / -0.46739` (delta `-0.19886`), so reward improvement fails. Huber losses were finite (`min 0.115619`, `median 0.991605`, `max 3.12839`, ratio `3.155`, below the 100x limit). Maximum absolute Q was `59.87038`, above the `<50` threshold. B2 therefore fails. Checkpoint validation losses were `0.0050892` at 25k, `0.0059023` at 50k, and `0.0059168` at 52k; the top-three manifest contains those candidates.

No checkpoint passed B4. On the prescribed three controls (five seeds each), the 25k candidate's median latency versus static was `9.952/5.905 ms` on Arpanet19728, `21.360/19.926 ms` on Compuserve, and `6.139/4.834 ms` on EliBackbone. At 50k the pairs were `9.363/5.905`, `21.296/19.926`, `6.140/4.834`; at 52k they were `8.516/5.905`, `21.191/19.926`, `5.358/4.834`. All candidates are within 10% only on Compuserve; none is selected. Loss was no worse than static on these three controls.

B5 used the lowest-loss 25k candidate and compared epsilon 0 and 0.05. The fraction of decisions not choosing the lowest-latency candidate was respectively `0.830/0.829` on Arpanet19728, `0.404/0.409` on Compuserve, and `0.803/0.800` on EliBackbone. The mean `Q(lowest-latency) - Q(chosen)` was `-0.163/-0.159`, `-0.306/-0.277`, and `-0.118/-0.113`. Thus epsilon did not resolve the choice. Component means for chosen versus lowest-latency actions, including latency and quality cost, are recorded in `outputs/day4/control_diagnosis_summary.csv`; per-episode records are beside it. No further training or tuning was done.

For reporting only, the unselected 25k diagnostic candidate was evaluated on all five validation graphs, normal and link-failure scenarios, five seeds each. It beat static loss on all five graphs in both scenarios, and its loss was below `0.8 × static` on 5/5 in both. Versus `random`, corrected `ecmp`, `greedy_min_util`, `dijkstra_load_aware_k`, `dijkstra_load_aware`, `rf_routing`, and the renamed `ties_on_queue_latency`, its normal-scenario win counts were `5/5, 5/5, 1/5 (1 tie), 2/5, 2/5, 1/5 (1 tie), 3/5`; link-failure counts were the same. These are diagnostic checkpoint results, not selected-model claims. All validation means and standard deviations for loss, overload, median/p95 latency, cap fraction, flapping, and decision time are in `outputs/day4/validation_summary.csv`; the episode-level data are in `validation_episode_metrics.csv`.

The final test command was `python -m pytest -q` from the project virtual environment: `101 passed, 1 warning in 10.95s`. The warning is the installed PyTorch `torch.jit.script` deprecation. Invoking the `pytest.exe` console launcher directly resolved Python without the repository root on its import path; the virtual-environment Python module invocation is the passing test run. The Day 4 guard test `test_locked_holdout_graph_guard_raises_before_loading` and Day 3 split-leakage/lock tests passed. Training, checkpoint selection, B4/B5, and the added validation report loaded only train/validation graphs. Against `f5d7f29`, `git diff --stat -- env/ baselines/ data/splits.json data/splits.lock` is empty.

## Day 5.5–5.6 final-study readiness (smoke completed; final study not launched)

### E1 speed-gate waiver

The 63 environment-steps/s target came from multiplying Day 4's measured 21 steps/s by three. The measured steady-state rates for this CPU-bound GNN learner are 3.8–4.8 steps/s per worker with 12 CPU workers concurrent; online/target GNN forward and backward passes dominate. This is a documented waiver of E1 only. The target is not lowered or relabeled as passed, no frozen environment or reward change was made, and runtime projections use measured rates. No later gate depends on E1 passing.

The study manifest is `configs/day5_5_6_manifest.json`. It contains 36 unique run IDs: 33 non-GRU and 3 GRU runs, each using the paired training seeds `20101`, `20102`, and `20103`. The ladder is L0–L4 plus L5, where the manifest labels L5 as `FULL`; FULL adds the auxiliary utilization head to L4 and has no GRU. The five FULL ablations are `-Dueling`, `-(PER and n-step)`, `-GAT` (MLP), `-Imitation`, and `-Noisy`. `-Aux` is an alias for the three L4 runs and does not add three jobs. L6 is FULL plus a GRU with history length T=2. Every non-GRU job explicitly has `gru_history=false` and T=4. `S_nonGRU=12,967` and `S_GRU=11,515` are the preflight-derived budgets. The FULL jobs also select at step 11,515 so FULL and L6 can be compared at equal steps, not equal wall-clock.

The pre-registered checkpoint schedule evaluates at step 0 and at each of the six `S/6` intervals. Each selection checkpoint uses only all five validation graphs, Poisson intensities from `data/eval_intensity.json`, and selection seeds 30000–30001. It additionally records the three validation-only controls Arpanet19728, Compuserve, and EliBackbone at intensity 0.025, against `dijkstra_static`. A control pass requires loss no worse than static and median latency within 10% of static. The selection criterion is the lowest mean packet loss over the five validation graphs; control results do not select or reject checkpoints. The selected checkpoint records its criterion and step in `selected.pt`; `final.pt` is saved separately. The worker reports a measured validation loss at progress checkpoints, never `n/a`. The selection adapter changes only the worker process's evaluation configuration to T=2 for L6; frozen environment, baseline, reward, calibration, and split files are unchanged.

The orchestrator has three stages: the three FULL seeds alone; then L0–L4 plus L6; then the 15 ablation jobs. Later stages are not queued unless all three FULL runs pass the supplied K2 safety criteria: finite training losses/Q/validation scores, maximum Huber loss divided by median below 100, `|Q|` 99.9th percentile below 60, maximum `|Q|` below 100, and no positive least-squares trend over the last three validation scores. The runner caps total processes at 12. `--plan` validates and prints the manifest without starting work. Execution requires both `--execute` and `--confirm-final-study`. Matching completed jobs are skipped on resume; any partial attempt is preserved and a fresh numbered attempt is used, so no completed run is duplicated and no valid artifact is overwritten. A partial attempt restarts from its fixed seed; it does not claim exact optimizer/replay-state continuation.

The saved `outputs/day5_5/preflight_base/` profile, previously reported as the 12-worker 4/4/4 cohort, records mean steady throughput of 4.396 steps/s for L0, 4.353 for FULL without GRU, and 3.858 for L6 T=2; the slowest of four runs per type was 4.365, 4.322, and 3.838 steps/s. A second saved `outputs/day5_5/mixed_rate/` cohort has different rates: means 4.850 (L0), 3.808 (FULL), and 3.560 (L6), with mean optimizer-update times 0.788, 1.015, and 1.085 seconds. These real profile sets disagree, so they do not support one stable throughput estimate. In both sets, 63 steps/s remains **failed** by a wide margin; no environment changes or threshold reductions were made. At the second cohort's rates, the configured budgets correspond to about 44.6 minutes per L0 job, 56.8 per FULL job, and 53.9 per L6 job. The three serial stages need five worker waves at a 12-process cap, but the exact wall time across the unprofiled ablations is not established. The earlier 4h05–4h25 projection excludes repeated validation/control episodes at up to eight checkpoints per FULL run and seven per other run, whose cost was not measured. Treat it as an incomplete estimate, not a realistic end-to-end runtime; the true total remains unmeasured and will be longer. The update-time measurements also explain the speed miss: one update takes 0.79–1.09 seconds and is scheduled every four decisions, before environment and validation work. No final-study or new training job was launched in this part.

The new runner's manifest, stage gate, checkpoint-choice, val-only loading, worker cap, resumable-artifact, and progress formatting behavior are covered by `tests/test_day5_5_6_readiness.py`. The old four-job Day 5.1 smoke results in `outputs/day5_1/` remain intact and passed their identical-seed loss-trace check. Existing exploratory preflight files in `outputs/day5_5/` remain untouched.

### Real-worker smoke result and launch decision

The smoke ran the real FULL (no GRU) and L6 (GRU T=2) workers concurrently for 1,200 steps each, with learning starting at 200 and validation at steps 0, 200, 400, 600, 800, 1,000, and 1,200. Selection used only `nobel-us` and `Eunetworks` plus the validation controls `Arpanet19728`, `Compuserve`, and `EliBackbone`, with selection seeds 30000 and 30001. Each selected checkpoint and final checkpoint was saved with its metadata. Reloaded Q values matched exactly on the fixed validation state (maximum absolute difference 0.0 for both checkpoints in both jobs). Each selected checkpoint then completed the final 65-episode validation evaluation: all five validation graphs, seeds 1000–1004, normal and link-failure, plus the three low-load controls at intensity 0.025. The JSON is in each run's `output/final_evaluation.json`.

| Smoke run | Worker elapsed (s) | Final eval (s / episodes) | Peak process-tree RSS | Q p99.9 / max | Last three validation losses |
|---|---:|---:|---:|---:|---|
| FULL_seed20101 | 618.43 | 195.69 / 65 | 523.0 MiB | 60.2569 / 60.3101 | 0.010935, 0.018541, 0.018588 |
| L6_GRU_T2_seed20101 | 716.04 | 154.28 / 65 | 590.7 MiB | 47.0022 / 47.0382 | 0.012592, 0.015398, 0.017958 |

The FULL smoke summary parsed from the real worker output, but it failed two unchanged safety checks: Q p99.9 was 60.2569 against the strict `<60` gate, and the last three validation losses had a positive trend. The checker accepted a separate healthy fixture and rejected a copy of the real summary with a NaN loss. Since the actual FULL summary did not pass the safety gate, the staged study was not launched. No test-split graph name appeared in either worker log; evaluation/training graph loading used train and validation guards only.

Using the measured 3.8 steps/s per-worker lower bound for training, and the smoke's measured selection/final-evaluation times scaled to the full five-graph/two-seed selection schedule (including the extra FULL equal-step checkpoint), projected elapsed time is about 333 minutes (5 h 33 min) for the full staged 36-run design. This includes final evaluation for every run and the selection evaluations at step 0 and each of the six budget intervals, plus a conservative allowance for the six cached static-control episodes. The estimate is below six hours, but the safety-gate failure independently blocks launch. Smoke artifacts and the gate report are preserved under `outputs/day5_5_6/smoke/`.
