# Day 6–7 Lite: pre-registered test criteria

This document was committed before opening or loading any test-split topology.
The final evaluation is a one-time run on the five graphs in the locked test
partition, with evaluation seeds `1000`–`1004`, scenarios `normal`,
`link_failures`, `router_failure`, `traffic_spike`, and `bandwidth_drop`, and
fixed intensities `0.05`, `0.10`, and `0.20`.

The test run is permitted only through the final-evaluation command with the
explicit `--allow-test-final` flag. It must not be repeated with altered
settings or after inspecting results.

## Pass/fail criteria

- **T1 — Normal-scenario loss:** At every tested intensity where pooled
  `dijkstra_static` mean packet loss is greater than `0.005`, pooled mean
  packet loss for AI with the safety fallback is at most `0.5 ×` the static
  value. Intensities where static loss is not greater than `0.005` are reported
  as not applicable for T1.
- **T2 — Load-aware loss:** For each scenario and intensity, pooled AI-with-
  fallback mean packet loss is at most the larger of `1.15 ×` the
  `dijkstra_load_aware` value and that value plus `0.002` absolute.
- **T3 — Runtime safety:** Across all test decisions there are zero accepted
  invalid actions, no NaN or infinite observed metrics/Q-values, and no
  crashes.
- **T4 — Per-graph baseline comparison:** For each test graph, scenario, and
  intensity, report numeric AI-with-fallback loss and comparisons against all
  seven baselines: `random`, `dijkstra_static`, `ecmp`, `greedy_min_util`,
  `dijkstra_load_aware_k`, `dijkstra_load_aware`, and `rf_routing`. A win means
  strictly lower mean packet loss; a tie means equal mean packet loss at
  reported precision; otherwise it is a loss.
- **T5 — Expert-policy agreement:** Report top-1 action agreement between the
  AI policy and `dijkstra_load_aware_k` over the same test decisions.

No additional acceptance criteria will be introduced after this document's
commit. All requested metrics and diagnostic context will still be reported.
