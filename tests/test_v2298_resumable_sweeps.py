"""Regression tests for resumable long runs and explicit CO2 targets."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import co2_target_sweep as sweep
from climate_model import ModelConfig, ProcessClimateModel
from climate_model_gui import ClimateModelGUI, DEFAULTS, build_cli_command, validate_values
from run_state import (
    describe_run_state,
    initialize_run_state,
    load_run_state,
    saved_seed_for_resume,
)
from worker_supervision import run_supervised_tasks, save_compatible_checkpoint


def _successful_worker(payload: tuple[int, str]) -> dict[str, object]:
    member, value = payload
    return {"member": member, "status": "ok", "value": value}


def _safe_summary() -> dict[str, float]:
    return {
        "maximum_absolute_salt_conservation_error_ppm": 0.0,
        "maximum_pre_projection_salt_conservation_error_ppm": 0.0,
        "cumulative_absolute_salt_projection_correction_ppm": 0.0,
        "initial_amoc_density_driver_ratio": 0.8,
        "maximum_arctic_open_water_temperature_c": 5.0,
        "maximum_arctic_open_water_temperature_c_at_5pct_open": 4.0,
        "maximum_dormant_arctic_open_water_heat_wyr_m2": 0.0,
        "arctic_reference_periodic_closure_wyr_m2": 0.0,
        "arctic_reference_spinup_convergence_wyr_m2": 0.0,
        "arctic_reference_convergence_tolerance_wyr_m2": 1.0e-5,
    }


def test_specific_target_parser_and_gui_command() -> None:
    np.testing.assert_allclose(
        sweep.parse_specific_targets("200, 300;600 1200 600"),
        [200.0, 300.0, 600.0, 1200.0],
    )
    values = dict(DEFAULTS)
    values.update(
        {
            "monte_carlo_enabled": True,
            "mc_co2_target_sweep_enabled": True,
            "mc_sweep_target_mode": "specific",
            "mc_sweep_start_ppm": "278.3",
            "mc_sweep_specific_targets": "200,300,600,1200",
            "mc_runs": "4",
            "mc_workers": "1",
            "output": "specific_target_test",
        }
    )
    validate_values(values)
    command = build_cli_command(values)
    assert command[command.index("--sweep-target-mode") + 1] == "specific"
    assert command[command.index("--sweep-specific-targets") + 1] == "200,300,600,1200"


def test_amoc_decline_uses_exact_supplied_initial_baseline() -> None:
    amoc = np.asarray([19.0, 18.0, 16.0], dtype=float)
    decline, baseline = sweep._amoc_decline_percent(amoc, 20.0)
    assert baseline == pytest.approx(20.0)
    assert decline[0] == pytest.approx(5.0)
    assert decline[1] == pytest.approx(10.0)
    assert decline[2] == pytest.approx(20.0)


def test_saved_clock_seed_and_checkpoint_discovery(tmp_path: Path) -> None:
    state_path = initialize_run_state(
        tmp_path,
        run_kind="co2_target_sweep",
        model_version="test",
        fingerprint="fingerprint",
        seed_requested=0,
        seed_used=987654,
        seed_source="system_clock",
        checkpoint_directory="co2_target_sweep_target_checkpoints",
        total_work_units=6,
        work_unit_name="target simulations",
        resume=False,
        settings={"command_arguments": ["--output", str(tmp_path)]},
    )
    assert state_path.exists()
    seed, source, state = saved_seed_for_resume(
        tmp_path,
        run_kind="co2_target_sweep",
        requested_seed=0,
        resume=True,
    )
    assert seed == 987654
    assert source == "saved_progress"
    assert state is not None

    checkpoint = (
        tmp_path
        / "co2_target_sweep_target_checkpoints"
        / "member_00000000"
        / "target_00000000.ckpt"
    )
    save_compatible_checkpoint(checkpoint, "fingerprint", {"status": "ok"})
    description = describe_run_state(tmp_path)
    assert "validated 1/6 target simulations" in description
    loaded = load_run_state(tmp_path)
    assert loaded is not None and loaded["seed_used"] == 987654


def test_failed_outer_checkpoint_can_be_retried(tmp_path: Path) -> None:
    checkpoint_dir = tmp_path / "members"
    save_compatible_checkpoint(
        checkpoint_dir / "member_00000000.ckpt",
        "fingerprint",
        {"member": 0, "status": "failed", "error": "old timeout"},
    )
    results = run_supervised_tasks(
        [(0, (0, "recovered"))],
        _successful_worker,
        max_workers=1,
        timeout_seconds=30.0,
        heartbeat_seconds=30.0,
        checkpoint_dir=checkpoint_dir,
        fingerprint="fingerprint",
        resume=True,
        retry_failed_on_resume=True,
    )
    assert results == [{"member": 0, "status": "ok", "value": "recovered"}]


def test_target_worker_resumes_each_saved_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[float] = []
    original_model = ProcessClimateModel

    class FakeRunResult:
        def __init__(self, start_ppm: float, target: float, initial_amoc: float) -> None:
            years = np.arange(1850.0, 1862.0)
            amoc = np.linspace(initial_amoc, initial_amoc - target / 100.0, len(years))
            self.dataframe = pd.DataFrame(
                {
                    "year": years,
                    "amoc_sv": amoc,
                    "global_surface_warming_c": np.linspace(0.0, target / 300.0, len(years)),
                    "co2_ppm": np.linspace(start_ppm, target, len(years)),
                    "salt_conservation_error_ppm": np.zeros(len(years)),
                }
            )

        def summary(self) -> dict[str, float]:
            return _safe_summary()

    class FakeModel:
        def __init__(self, config: ModelConfig) -> None:
            self.config = config
            self.state = original_model(config).state.copy()

        def run(self) -> FakeRunResult:
            calls.append(float(self.config.co2_end_ppm))
            return FakeRunResult(
                float(self.config.co2_start_ppm),
                float(self.config.co2_end_ppm),
                float(self.state.amoc_sv),
            )

    monkeypatch.setattr(sweep, "ProcessClimateModel", FakeModel)
    base = ModelConfig(
        scenario="linear_ramp_hold",
        co2_start_ppm=278.3,
        co2_end_ppm=200.0,
        co2_ramp_years=5.0,
        co2_hold_years=6.0,
        duration_years=11.0,
        dt_years=0.2,
        record_every_years=1.0,
        auto_initialize_from_1850=False,
    )
    payload = (
        0,
        base.__dict__.copy(),
        {},
        278.3,
        [200.0, 300.0],
        5.0,
        6.0,
        5.0,
        0.9,
        2.0,
        1000.0,
        "none",
        False,
        False,
        20.0,
        str(tmp_path / "target_checkpoints"),
        "fingerprint",
        False,
        True,
        None,
    )
    first = sweep._sweep_member_worker(payload)
    assert first["status"] == "ok"
    assert calls == [200.0, 300.0]
    assert np.asarray(first["amoc_decline_percent"]).shape == (2, 12)
    assert first["amoc_baseline_definition"] == sweep.AMOC_BASELINE_DEFINITION

    calls.clear()
    resumed = list(payload)
    resumed[17] = True
    second = sweep._sweep_member_worker(tuple(resumed))
    assert second["status"] == "ok"
    assert calls == []
    np.testing.assert_allclose(second["amoc_sv"], first["amoc_sv"])

def test_saved_gui_command_replaces_output_and_forces_resume(tmp_path: Path) -> None:
    gui = object.__new__(ClimateModelGUI)
    gui.loaded_resume_script = Path("co2_target_sweep.py")
    gui.loaded_resume_command_args = [
        "--output",
        "old-output",
        "--mc-seed",
        "123",
        "--overwrite-output",
        "--mc-resume",
    ]
    command = ClimateModelGUI._build_loaded_resume_command(gui, tmp_path)
    assert command.count("--mc-resume") == 1
    assert "--overwrite-output" not in command
    assert command[command.index("--output") + 1] == str(tmp_path)


def test_synthetic_specific_sweep_writes_decline_intervals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    args = sweep.build_parser().parse_args(
        [
            "--monte-carlo-runs",
            "2",
            "--mc-workers",
            "1",
            "--mc-seed",
            "123",
            "--mc-range",
            "hydrological_freshwater_sv_per_k",
            "0.004",
            "0.006",
            "--sweep-target-mode",
            "specific",
            "--sweep-specific-targets",
            "200,300,600,1200",
            "--sweep-ramp-years",
            "5",
            "--sweep-hold-years",
            "6",
            "--sweep-collapse-window-years",
            "5",
            "--sweep-recovery-years",
            "2",
            "--sweep-bootstrap-samples",
            "10",
            "--dt",
            "0.2",
            "--mc-no-plots",
            "--output",
            str(tmp_path),
            "--overwrite-output",
        ]
    )
    args.saved_command_arguments = [
        "--sweep-target-mode",
        "specific",
        "--sweep-specific-targets",
        "200,300,600,1200",
        "--output",
        str(tmp_path),
    ]

    targets = np.asarray([200.0, 300.0, 600.0, 1200.0])
    years = np.arange(1850.0, 1862.0)

    supervised_calls = 0

    def fake_results(*_args: object, **_kwargs: object) -> list[dict[str, object]]:
        nonlocal supervised_calls
        tasks = _args[0]
        members = [int(member) for member, _payload in tasks]
        results: list[dict[str, object]] = []
        for member in members:
            if supervised_calls == 0 and member == 0:
                results.append(
                    {
                        "member": member,
                        "status": "failed",
                        "failure_kind": "common_start_baseline_rejected",
                        "sampled": {
                            "hydrological_freshwater_sv_per_k": 0.004
                        },
                        "error": "RuntimeError: synthetic invalid baseline",
                        "attempted_target_simulations": len(targets),
                        "successful_target_simulations": 0,
                        "failed_target_simulations": len(targets),
                    }
                )
                continue
            amoc_rows = []
            decline_rows = []
            warming_rows = []
            co2_rows = []
            target_summaries = []
            for target in targets:
                amoc = np.linspace(20.0 + member, 20.0 + member - target / 100.0, len(years))
                decline, baseline = sweep._amoc_decline_percent(amoc, 20.0 + member)
                warming = np.linspace(0.0, target / 300.0, len(years))
                co2 = np.linspace(278.3, target, len(years))
                duration = sweep.collapse_duration_diagnostics(
                    amoc,
                    years,
                    10.0,
                    5.0,
                    0.95,
                    2.0,
                )
                target_summaries.append(
                    {
                        "target_ppm": float(target),
                        "common_start_ppm": 278.3,
                        "initial_amoc_baseline_sv": baseline,
                        "amoc_baseline_definition": sweep.AMOC_BASELINE_DEFINITION,
                        "initial_equilibration_years_used": 0.0,
                        "minimum_amoc_sv": float(np.min(amoc)),
                        "maximum_amoc_decline_percent": float(np.max(decline)),
                        "final_window_amoc_sv": float(np.mean(amoc[-5:])),
                        "final_window_amoc_decline_percent": float(np.mean(decline[-5:])),
                        "final_window_warming_c": float(np.mean(warming[-5:])),
                        "persistence_required_fraction": 0.95,
                        "recovery_disqualifying_years": 2.0,
                        **duration,
                        "maximum_salt_error_ppm": 0.0,
                    }
                )
                amoc_rows.append(amoc)
                decline_rows.append(decline)
                warming_rows.append(warming)
                co2_rows.append(co2)
            results.append(
                {
                    "member": member,
                    "status": "ok",
                    "sampled": {"hydrological_freshwater_sv_per_k": 0.004 + member * 0.002},
                    "summary": _safe_summary(),
                    "years": years,
                    "elapsed_years": years - years[0],
                    "targets_ppm": targets,
                    "common_start_ppm": 278.3,
                    "initial_amoc_baseline_sv": 20.0 + member,
                    "amoc_baseline_definition": sweep.AMOC_BASELINE_DEFINITION,
                    "baseline_initialization": "native_reference_control_state",
                    "initial_equilibration_years_used": 0.0,
                    "amoc_sv": np.asarray(amoc_rows, dtype=np.float32),
                    "amoc_decline_percent": np.asarray(decline_rows, dtype=np.float32),
                    "global_surface_warming_c": np.asarray(warming_rows, dtype=np.float32),
                    "co2_ppm": np.asarray(co2_rows, dtype=np.float32),
                    "target_summaries": target_summaries,
                }
            )
        supervised_calls += 1
        return results

    monkeypatch.setattr(sweep, "run_supervised_tasks", fake_results)
    summary = sweep.run_sweep(args)
    assert summary["target_mode"] == "specific"
    assert summary["targets_ppm"] == targets.tolist()
    assert summary["requested_start_ppm"] == pytest.approx(278.3)
    assert summary["start_ppm"] == pytest.approx(278.3)
    assert summary["common_start_ppm"] == pytest.approx(278.3)
    assert summary["amoc_baseline_definition"] == sweep.AMOC_BASELINE_DEFINITION
    assert summary["baseline_rejected_draws"] == 1
    assert summary["members_requiring_baseline_redraw"] == 1
    assert supervised_calls == 2
    assert (tmp_path / "co2_target_sweep_baseline_rejections.csv").exists()

    endpoint = pd.read_csv(tmp_path / "co2_target_sweep_summary.csv")
    for column in (
        "final_amoc_decline_percent_p01",
        "final_amoc_decline_percent_p17",
        "final_amoc_decline_percent_median",
        "final_amoc_decline_percent_p83",
        "final_amoc_decline_percent_p99",
    ):
        assert column in endpoint.columns

    trajectories = pd.read_csv(
        tmp_path / "co2_target_sweep_amoc_percent_decline_timeseries.csv"
    )
    for column in (
        "amoc_decline_percent_p01",
        "amoc_decline_percent_p05",
        "amoc_decline_percent_p17",
        "amoc_decline_percent_p50",
        "amoc_decline_percent_p83",
        "amoc_decline_percent_p95",
        "amoc_decline_percent_p99",
    ):
        assert column in trajectories.columns

    with np.load(tmp_path / "co2_target_sweep_timeseries.npz") as archive:
        assert archive["amoc_decline_percent"].shape == (2, 4, 12)
        np.testing.assert_allclose(archive["initial_amoc_baseline_sv"], [20.0, 21.0])
        assert float(archive["common_start_ppm"]) == pytest.approx(278.3)

    state = json.loads((tmp_path / "long_run_state.json").read_text(encoding="utf-8"))
    assert state["status"] == "completed_with_quality_warning"
    assert state["settings"]["command_arguments"]


def test_standard_monte_carlo_persists_and_reuses_resolved_seed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import monte_carlo as mc

    seed_calls: list[int] = []

    def fake_resolve_seed(requested: int) -> tuple[int, str]:
        seed_calls.append(int(requested))
        return 24681357, "system_clock"

    def fake_generate_samples(*_args, **_kwargs):
        return [{}, {}]

    def fake_supervised(
        tasks,
        _worker,
        *,
        progress_callback=None,
        **_kwargs,
    ):
        if progress_callback is not None:
            progress_callback(len(tasks), len(tasks), 0, 0.1)
        return [
            {"member": member, "status": "ok", "sampled": {}, "summary": {}}
            for member, _payload in tasks
        ]

    def fake_save_ensemble_outputs(**_kwargs):
        return {
            "successful_members": 2,
            "failed_members": 0,
            "uncertainty_products_valid_for_quantitative_use": False,
            "ensemble_quality": {
                "quality_classification": "exploratory_only_invalid_quantitative_uncertainty"
            },
        }

    monkeypatch.setattr(mc, "resolve_random_seed", fake_resolve_seed)
    monkeypatch.setattr(mc, "generate_samples", fake_generate_samples)
    monkeypatch.setattr(mc, "run_supervised_tasks", fake_supervised)
    monkeypatch.setattr(mc, "save_ensemble_outputs", fake_save_ensemble_outputs)
    monkeypatch.setattr(mc, "_automatic_worker_count", lambda _workers: 1)

    base = ModelConfig(
        scenario="constant",
        duration_years=1.0,
        dt_years=0.1,
        auto_initialize_from_1850=False,
    )
    kwargs = dict(
        base_config=base,
        ranges={},
        runs=2,
        seed=0,
        distribution="uniform",
        design="random",
        constraint_mode="none",
        correlated_priors=False,
        use_science_priors=False,
        run_calibration_experiments=False,
        workers=1,
        output_dir=tmp_path,
        create_plots=False,
        command_arguments=["--monte-carlo-runs", "2", "--output", str(tmp_path)],
    )
    first = mc.run_monte_carlo(**kwargs)
    assert first["successful_members"] == 2
    state = load_run_state(tmp_path)
    assert state is not None
    assert state["status"] == "completed_with_quality_warning"
    assert state["seed_used"] == 24681357
    assert state["settings"]["command_arguments"][0] == "--monte-carlo-runs"

    second = mc.run_monte_carlo(**{**kwargs, "resume": True})
    assert second["successful_members"] == 2
    assert seed_calls == [0]
    resumed_state = load_run_state(tmp_path)
    assert resumed_state is not None
    assert resumed_state["resume_count"] == 1
    assert resumed_state["seed_used"] == 24681357
