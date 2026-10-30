# Day 6–7 test-run recovery record

## Why a recovery run is authorized

The pre-registered acceptance criteria remain unchanged in
[`test_criteria.md`](test_criteria.md). The original gated invocation was
interrupted by laptop shutdown after 1,475 of 3,000 jobs. Its output tree is
preserved at `outputs/day6_7_lite/test_final/`; it has a one-time marker and
sparse progress snapshots, but no complete `results.json` or per-episode
result journal. The user authorized a fresh evaluation with the exact same
graphs, scenarios, intensities, seeds, policies, and metric code. This recovery
record changes no threshold or evaluation setting.

Because the original run did not persist every completed episode, a valid full
table cannot be reconstructed from it. The recovery run therefore starts the
same 3,000-job matrix from job 1 in a separate directory,
`outputs/day6_7_lite/test_final_retry/`, leaving the interrupted directory
untouched. The retry writes each completed episode to a durable append-only
JSONL journal. If interrupted again, it can resume only from the exact
validated journal prefix; completed jobs are not duplicated.

## Fixed settings

- Test split: the five names in the locked `data/splits.json` test partition.
- Seeds: `1000`–`1004`.
- Intensities: `0.05`, `0.10`, `0.20`.
- Scenarios: normal, link failures, router failure, traffic spike, bandwidth
  drop.
- Policies: the seven registered baselines plus AI with the safety fallback.
- Generator: Poisson; 500 steps per episode; 100 warm-up steps; alpha `4.0`.
- Acceptance criteria: unchanged from the criteria commit recorded in the run
  marker.

## Commands

Start the fresh retry once, from the `AI` directory, and see progress in the
same PowerShell window:

```powershell
& .\venv\Scripts\python.exe .\scripts\day6_7_lite_eval.py --allow-test-retry --output-dir .\outputs\day6_7_lite\test_final_retry
```

If the machine interrupts it, continue the same run from its durable journal:

```powershell
& .\venv\Scripts\python.exe .\scripts\day6_7_lite_eval.py --resume-test-retry --output-dir .\outputs\day6_7_lite\test_final_retry
```

The runner prints `test-eval completed/3000 ... ETA ...` every 25 completed
jobs, and its full durable episode journal is
`outputs/day6_7_lite/test_final_retry/results.jsonl`.
