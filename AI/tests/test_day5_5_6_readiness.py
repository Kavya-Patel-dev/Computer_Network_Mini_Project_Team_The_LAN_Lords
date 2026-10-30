from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from models.day5_study import (
    GRU_STEPS,
    MAIN_STEPS,
    SEEDS,
    SelectionState,
    build_manifest,
    canonical_signature,
    checkpoint_steps,
    control_passes,
    effective_workers,
    format_progress,
    full_safety_gate,
    full_run_safety_check,
    load_validation_graphs,
    resolve_attempt_dir,
    safety_stage_allows_next,
    validate_manifest,
)
from models.day5_variants import VariantDQNAgent
from scripts import day5_5_6_runner
from scripts.day5_5_6_worker import save_selected_and_final


def _by_variant(manifest):
    return {job_variant: [job for job in manifest["jobs"]
                          if job["variant"] == job_variant]
            for job_variant in {job["variant"] for job in manifest["jobs"]}}


def test_final_manifest_has_exact_36_runs_three_seeds_and_no_duplicate_combinations():
    manifest = build_manifest()
    validate_manifest(manifest)
    assert len(manifest["jobs"]) == 36
    assert {job["seed"] for job in manifest["jobs"]} == set(SEEDS)
    assert len({job["run_id"] for job in manifest["jobs"]}) == 36
    assert sum(not job["flags"]["gru_history"] for job in manifest["jobs"]) == 33
    assert sum(job["flags"]["gru_history"] for job in manifest["jobs"]) == 3
    variants = _by_variant(manifest)
    assert {name: len(rows) for name, rows in variants.items()} == {
        "L0": 3, "L1": 3, "L2": 3, "L3": 3, "L4": 3, "FULL": 3,
        "ABL_no_dueling": 3, "ABL_no_per_nstep": 3, "ABL_mlp": 3,
        "ABL_no_imitation": 3, "ABL_no_noisy": 3, "L6_GRU_T2": 3,
    }
    assert manifest["labels"]["L5"] == "FULL"


def test_manifest_flags_match_ladder_ablations_and_gru_t2_configuration():
    variants = _by_variant(build_manifest())
    l0, l1, l2, l3, l4, full = [variants[key][0]
                                 for key in ("L0", "L1", "L2", "L3", "L4", "FULL")]
    assert not l0["flags"]["dueling"] and not l0["prioritized_replay"]
    assert l0["n_step"] == 1 and not l0["flags"]["noisy_net"]
    assert l1["flags"]["dueling"] and l1["n_step"] == 1
    assert l2["n_step"] == 3 and not l2["prioritized_replay"]
    assert l3["prioritized_replay"] and not l3["flags"]["noisy_net"]
    assert l4["flags"]["noisy_net"] and not l4["flags"]["auxiliary_utilization"]
    assert full["flags"]["auxiliary_utilization"] and full["flags"]["noisy_net"]
    assert full["flags"]["gru_history"] is False
    for job in build_manifest()["jobs"]:
        if job["variant"] != "L6_GRU_T2":
            assert job["flags"]["gru_history"] is False
            assert job["history_length"] == 4
    gru = variants["L6_GRU_T2"][0]
    assert gru["flags"]["gru_history"] is True
    assert gru["history_length"] == 2
    assert gru["steps"] == GRU_STEPS
    assert all(job["steps"] == MAIN_STEPS for job in variants["FULL"])
    assert variants["ABL_no_imitation"][0]["load_bc"] is False
    assert variants["ABL_no_imitation"][0]["auxiliary_bc_weight"] == 0.0
    assert variants["ABL_mlp"][0]["flags"]["mlp_encoder"] is True
    assert variants["ABL_no_dueling"][0]["flags"]["dueling"] is False
    assert variants["ABL_no_noisy"][0]["flags"]["noisy_net"] is False
    assert variants["ABL_no_per_nstep"][0]["n_step"] == 1
    assert variants["ABL_no_per_nstep"][0]["prioritized_replay"] is False
    assert build_manifest()["reuse"]["ABL_no_aux"]["run_ids"] == [
        f"L4_seed{seed}" for seed in SEEDS]


def test_full_uses_gru_budget_as_an_equal_step_checkpoint():
    points = checkpoint_steps(MAIN_STEPS, extra_steps=(GRU_STEPS,))
    assert points[0] == 0
    assert points[-1] == MAIN_STEPS
    assert GRU_STEPS in points
    assert all(0 <= point <= MAIN_STEPS for point in points)
    assert len(points) >= 8


def test_regular_checkpoint_schedule_is_zero_plus_six_sixth_intervals():
    points = checkpoint_steps(MAIN_STEPS)
    assert points == sorted({0, *(math.ceil(MAIN_STEPS * part / 6)
                                  for part in range(1, 7))})


def test_checkpoint_selection_keeps_lowest_validation_loss_and_records_step():
    selected = SelectionState()
    selected = selected.consider(0, 0.5)
    selected = selected.consider(100, 0.4)
    selected = selected.consider(200, 0.45)
    assert selected.best_step == 100
    assert selected.best_loss == pytest.approx(0.4)
    with pytest.raises(ValueError, match="finite"):
        selected.consider(300, float("nan"))


def test_selected_and_final_checkpoint_artifacts_are_distinct_and_metadata_is_recorded(
        tmp_path):
    flags = {"dueling": True, "noisy_net": True, "gru_history": False,
             "mlp_encoder": False, "auxiliary_utilization": True,
             "noisy_sigma0": 0.1, "compact_history": False}
    agent = VariantDQNAgent(flags=flags, seed=20101, replay_capacity=16,
                            batch_size=2, learning_starts=2)
    candidate = tmp_path / "candidate.pt"
    selected = tmp_path / "selected.pt"
    final = tmp_path / "final.pt"
    agent.save(str(candidate), {
        "checkpoint_role": "selected", "step": 1200,
        "selection_criterion": "lowest validation packet loss",
        "selected_validation_loss": 0.012,
    })
    save_selected_and_final(
        agent, candidate, selected, final, run_id="FULL_seed20101",
        seed=20101, selected_step=1200, selected_loss=0.012,
        final_step=12967, history_length=4)
    loaded = VariantDQNAgent(flags=flags, seed=20102, replay_capacity=16,
                             batch_size=2, learning_starts=2)
    selected_metadata = loaded.load(str(selected))
    assert selected_metadata["checkpoint_role"] == "selected"
    assert selected_metadata["step"] == 1200
    final_metadata = loaded.load(str(final))
    assert final_metadata["checkpoint_role"] == "final"
    assert final_metadata["step"] == 12967
    assert final_metadata["selected_step"] == 1200
    assert final_metadata["selected_validation_loss"] == pytest.approx(0.012)
    assert not selected.samefile(final)
    with pytest.raises(FileExistsError, match="overwrite"):
        save_selected_and_final(
            agent, candidate, selected, final, run_id="FULL_seed20101",
            seed=20101, selected_step=1200, selected_loss=0.012,
            final_step=12967, history_length=4)


def test_low_load_control_uses_latency_ten_percent_and_loss_no_worse():
    assert control_passes(0.01, 11.0, 0.01, 10.0)
    assert not control_passes(0.011, 10.0, 0.01, 10.0)
    assert not control_passes(0.01, 11.01, 0.01, 10.0)


def test_validation_selection_loader_only_requests_validation_partition():
    train = [{"name": "train_graph", "path": "train.graph"}]
    val_names = ["Arpanet19728", "EliBackbone", "nobel-us",
                 "Compuserve", "Eunetworks"]
    val = [{"name": name, "path": f"val/{name}.graph"} for name in val_names]
    test = [{"name": "LOCKED_TEST", "path": "test/locked.graph"}]
    partitions = {"train": train, "val": val, "test": test}
    seen = []

    def guarded_loader(entry, split, _partitions):
        assert split == "val"
        assert entry["name"] in val_names
        seen.append((entry["name"], split))
        return f"loaded:{entry['name']}"

    graphs = load_validation_graphs(partitions, guarded_loader)
    assert set(graphs) == set(val_names)
    assert len(seen) == 5
    assert all(name != "LOCKED_TEST" for name, _split in seen)


def _passing_full_summary(run_id):
    return {
        "run_id": run_id,
        "loss_trace": [1.0] * 100,
        "q_abs_trace": [50.0] * 100,
        "validation_history": [
            {"step": 0, "mean_loss": 0.5},
            {"step": 100, "mean_loss": 0.4},
            {"step": 200, "mean_loss": 0.3},
        ],
    }


def test_three_full_safety_gate_passes_only_when_every_full_run_meets_each_gate():
    summaries = [_passing_full_summary(f"FULL_seed{seed}") for seed in SEEDS]
    passed, report = full_safety_gate(summaries)
    assert passed
    assert len(report) == 3
    assert all(item["pass"] for item in report)
    assert safety_stage_allows_next(passed)

    summaries[-1]["q_abs_trace"][-1] = 100.0
    passed, report = full_safety_gate(summaries)
    assert not passed
    assert not report[-1]["checks"]["q_abs_max_below_100"]
    assert not safety_stage_allows_next(passed)


def test_three_full_safety_gate_fails_on_divergence_or_upward_validation_trend():
    summaries = [_passing_full_summary(f"FULL_seed{seed}") for seed in SEEDS]
    summaries[0]["loss_trace"][-1] = 200.0
    summaries[1]["validation_history"][-1]["mean_loss"] = 0.6
    passed, report = full_safety_gate(summaries)
    assert not passed
    by_id = {row["run_id"]: row for row in report}
    assert not by_id["FULL_seed20101"]["checks"]["max_huber_over_median_below_100"]
    assert not by_id["FULL_seed20102"]["checks"][
        "validation_last_three_nonincreasing_trend"]


def test_single_full_safety_check_accepts_healthy_smoke_and_rejects_nan_loss():
    summary = {
        "run_id": "FULL_seed20101",
        "loss_trace": [0.5] * 100,
        "q_abs_trace": [25.0] * 100,
        "validation_history": [
            {"step": 0, "mean_loss": 0.8},
            {"step": 200, "mean_loss": 0.7},
            {"step": 400, "mean_loss": 0.6},
            {"step": 600, "mean_loss": 0.5},
        ],
    }
    passed, report = full_run_safety_check(summary)
    assert passed and all(report["checks"].values())
    corrupted = json.loads(json.dumps(summary))
    corrupted["loss_trace"][3] = float("nan")
    passed, report = full_run_safety_check(corrupted)
    assert not passed
    assert not report["checks"]["finite_losses_q_and_validation"]


def test_runner_does_not_schedule_later_stages_after_full_safety_failure(
        monkeypatch, tmp_path):
    manifest = build_manifest()
    called_stages = []
    bad = _passing_full_summary("FULL_seed20101")
    bad["q_abs_trace"][-1] = 101.0
    summaries = {
        f"FULL_seed{seed}": (bad if seed == SEEDS[0] else
                             _passing_full_summary(f"FULL_seed{seed}"))
        for seed in SEEDS
    }

    def fake_run_stage(jobs, **kwargs):
        called_stages.append(kwargs["stage_name"])
        return True

    monkeypatch.setattr(day5_5_6_runner, "run_stage", fake_run_stage)
    monkeypatch.setattr(
        day5_5_6_runner, "completed_summary",
        lambda _root, job: summaries.get(job["run_id"]))
    result = day5_5_6_runner.execute(manifest, root=tmp_path, max_workers=12)
    assert result == 1
    assert called_stages == ["FULL safety stage"]
    gate = json.loads((tmp_path / "full_safety_gate.json").read_text(encoding="utf-8"))
    assert gate["passed"] is False


def test_worker_limit_is_capped_at_twelve_and_rejects_nonpositive_values():
    assert effective_workers(64, 36) == 12
    assert effective_workers(8, 36) == 8
    assert effective_workers(12, 2) == 2
    with pytest.raises(ValueError):
        effective_workers(0, 36)


def test_resume_skips_completed_attempt_and_preserves_partial_attempt(tmp_path):
    run_id = "FULL_seed20101"
    signature = "abc123"
    partial = tmp_path / run_id
    partial.mkdir()
    marker = partial / "partial.marker"
    marker.write_text("keep", encoding="utf-8")

    new_dir, completed = resolve_attempt_dir(tmp_path, run_id, signature)
    assert not completed
    assert new_dir.name == f"{run_id}.attempt02"
    assert marker.read_text(encoding="utf-8") == "keep"

    output = new_dir / "output"
    output.mkdir(parents=True)
    (output / "summary.json").write_text(json.dumps({
        "signature": signature, "completed": True,
    }), encoding="utf-8")
    reused, completed = resolve_attempt_dir(tmp_path, run_id, signature)
    assert completed and reused == new_dir


def test_resume_after_stop_skips_completed_run_and_preserves_partial_attempt(
        tmp_path, capsys):
    jobs = build_manifest()["jobs"][:2]
    completed_job, interrupted_job = jobs
    completed_dir = tmp_path / completed_job["run_id"] / "output"
    completed_dir.mkdir(parents=True)
    (completed_dir / "summary.json").write_text(json.dumps({
        "run_id": completed_job["run_id"],
        "signature": canonical_signature(completed_job),
        "completed": True, "elapsed_seconds": 0.01,
    }), encoding="utf-8")
    partial = tmp_path / interrupted_job["run_id"]
    partial.mkdir()
    (partial / "checkpoint.pt").write_text("preserve", encoding="utf-8")
    worker = tmp_path / "resume_worker.py"
    worker.write_text(
        "import json,sys\nfrom pathlib import Path\n"
        "spec=json.loads(Path(sys.argv[2]).read_text())\n"
        "out=Path(spec['output_dir'])\n"
        "(out/'summary.json').write_text(json.dumps({'run_id':spec['run_id'],"
        "'signature':spec['signature'],'completed':True,'elapsed_seconds':0.01}))\n"
        "print('step 1 / 1 | val loss 0.1 | ETA 0.0 min | selection=smoke',flush=True)\n",
        encoding="utf-8")
    done = {completed_job["run_id"]}
    assert day5_5_6_runner.run_stage(
        jobs, stage_name="resume smoke", root=tmp_path, max_workers=2,
        completed_ids=done, total=2, completed_elapsed=[], worker=worker)
    assert done == {job["run_id"] for job in jobs}
    assert (partial / "checkpoint.pt").read_text(encoding="utf-8") == "preserve"
    assert (tmp_path / f"{interrupted_job['run_id']}.attempt02").exists()
    output = capsys.readouterr().out
    assert f"skip completed {completed_job['run_id']}" in output
    assert f"started {interrupted_job['run_id']}" in output


def test_progress_line_has_real_validation_loss_eta_and_selection_status():
    line = format_progress("FULL_seed20101", 100, 1_000, 0.012345, 4.5,
                           "selected_step=100")
    assert "step 100 / 1000" in line
    assert "val loss 0.012345" in line
    assert "ETA 4.50 min" in line
    assert "selection=selected_step=100" in line
    with pytest.raises(ValueError, match="finite"):
        format_progress("run", 1, 10, float("nan"), 1.0, "none")


def test_four_process_runner_smoke_merges_completed_subprocess_jobs_without_graphs(
        tmp_path, capsys):
    worker = tmp_path / "fake_worker.py"
    worker.write_text(
        "import json, sys\n"
        "from pathlib import Path\n"
        "spec = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))\n"
        "out = Path(spec['output_dir'])\n"
        "(out / 'summary.json').write_text(json.dumps({\n"
        "  'run_id': spec['run_id'], 'signature': spec['signature'],\n"
        "  'completed': True, 'elapsed_seconds': 0.01,\n"
        "  'best_validation_loss': 0.125, 'selected_step': 0}),\n"
        "  encoding='utf-8')\n"
        "print('step 1 / 1 | val loss 0.125000 | ETA 0.00 min | selection=step0', flush=True)\n",
        encoding="utf-8")
    jobs = build_manifest()["jobs"][:4]
    done = set()
    assert day5_5_6_runner.run_stage(
        jobs, stage_name="synthetic subprocess smoke", root=tmp_path / "jobs",
        max_workers=2, completed_ids=done, total=4,
        completed_elapsed=[], worker=worker)
    assert done == {job["run_id"] for job in jobs}
    output = capsys.readouterr().out
    assert "workers=2/2" in output
    assert "runs done 4 / 4" in output
    assert "val loss 0.125000" in output
