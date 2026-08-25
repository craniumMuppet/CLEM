#!/usr/bin/env python3
"""Regression tests for the paired CO2 target sweep."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from climate_model import ModelConfig, ProcessClimateModel, resolved_scenario_config
from climate_model_gui import DEFAULTS, build_cli_command, validate_values
from co2_target_sweep import build_parser, build_targets, parse_specific_targets, run_sweep


def test_linear_ramp_hold() -> None:
    config = resolved_scenario_config(
        ModelConfig(
            scenario="linear_ramp_hold",
            co2_start_ppm=278.3,
            co2_end_ppm=600.0,
            co2_ramp_years=40.0,
            co2_hold_years=60.0,
            dt_years=0.2,
            record_every_years=1.0,
        )
    )
    assert config.duration_years == 100.0
    frame = ProcessClimateModel(config).run().dataframe
    assert abs(float(frame.iloc[0]["co2_ppm"]) - 278.3) < 1.0e-9
    at_cap = frame.iloc[int(np.argmin(abs(frame["elapsed_years"] - 40.0)))]
    assert abs(float(at_cap["co2_ppm"]) - 600.0) < 1.0e-6
    assert abs(float(frame.iloc[-1]["co2_ppm"]) - 600.0) < 1.0e-6


def test_target_sequence() -> None:
    targets = build_targets(278.3, 50.0, 400.0)
    np.testing.assert_allclose(targets, [278.3, 328.3, 378.3, 400.0])
    specific = parse_specific_targets("200,300;600 1200,600", 200.0)
    np.testing.assert_allclose(specific, [200.0, 300.0, 600.0, 1200.0])


def test_gui_command() -> None:
    values = dict(DEFAULTS)
    values.update(
        {
            "monte_carlo_enabled": True,
            "mc_co2_target_sweep_enabled": True,
            "mc_runs": "4",
            "mc_workers": "1",
            "mc_use_science_defaults": False,
            "mc_sweep_bootstrap_samples": "25",
            "output": "outputs_sweep_test",
        }
    )
    validate_values(values)
    command = build_cli_command(values)
    assert Path(command[1]).name == "co2_target_sweep.py"
    assert "--sweep-start-ppm" in command
    assert "--sweep-target-mode" in command
    assert "--sweep-specific-targets" in command
    assert "--sweep-persistence-fraction" in command
    assert "--sweep-recovery-years" in command
    assert "--sweep-bootstrap-samples" in command
    assert "--sweep-confidence-level" in command
    assert "--sweep-plot-mode" in command


def test_small_sweep() -> None:
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory)
        args = build_parser().parse_args(
            [
                "--monte-carlo-runs", "4",
                "--mc-workers", "1",
                "--mc-seed", "123",
                "--mc-range", "hydrological_freshwater_sv_per_k", "0.003", "0.009",
                "--sweep-start-ppm", "278.3",
                "--sweep-step-ppm", "100",
                "--sweep-max-ppm", "500",
                "--sweep-ramp-years", "10",
                "--sweep-hold-years", "20",
                "--sweep-collapse-window-years", "10",
                "--sweep-persistence-fraction", "0.90",
                "--sweep-recovery-years", "3",
                "--sweep-bootstrap-samples", "50",
                "--sweep-confidence-level", "0.90",
                "--sweep-plot-mode", "mean",
                "--dt", "0.2",
                "--output", str(output),
                "--overwrite-output",
            ]
        )
        summary = run_sweep(args)
        assert summary["successful_paired_members"] == 4
        assert summary["targets_ppm"] == [278.3, 378.3, 478.3, 500.0]
        assert summary["bootstrap_samples"] == 50
        assert summary["persistence_required_fraction"] == 0.90
        assert summary["recovery_disqualifying_years"] == 3.0
        assert "conditional_fraction_threshold_targets" in summary
        assert "monotonicity_checks" in summary
        assert "warnings" in summary

        table = pd.read_csv(output / "co2_target_sweep_summary.csv")
        assert len(table) == 4
        required_summary_columns = {
            "ever_collapse_conditional_ensemble_fraction",
            "persistent_collapse_conditional_ensemble_fraction",
            "ever_collapse_conditional_fraction_ci_lower",
            "ever_collapse_conditional_fraction_ci_upper",
            "persistent_collapse_conditional_fraction_ci_lower",
            "persistent_collapse_conditional_fraction_ci_upper",
            "persistence_required_fraction",
            "recovery_disqualifying_years",
            "final_amoc_decline_percent_p01",
            "final_amoc_decline_percent_p17",
            "final_amoc_decline_percent_median",
            "final_amoc_decline_percent_p83",
            "final_amoc_decline_percent_p99",
        }
        assert required_summary_columns.issubset(table.columns)

        members = pd.read_csv(output / "co2_target_sweep_members.csv")
        assert len(members) == 16
        required_member_columns = {
            "ever_collapsed",
            "persistent_collapsed",
            "final_window_collapsed_duration_years",
            "final_window_collapsed_fraction",
            "final_window_longest_continuous_collapse_years",
            "final_window_longest_active_recovery_years",
            "final_window_reversed_duration_years",
        }
        assert required_member_columns.issubset(members.columns)

        with np.load(output / "co2_target_sweep_timeseries.npz") as archive:
            assert archive["amoc_sv"].shape[0:2] == (4, 4)
            assert archive["amoc_decline_percent"].shape[0:2] == (4, 4)
        decline = pd.read_csv(output / "co2_target_sweep_amoc_percent_decline_timeseries.csv")
        assert {
            "amoc_decline_percent_p01",
            "amoc_decline_percent_p17",
            "amoc_decline_percent_p50",
            "amoc_decline_percent_p83",
            "amoc_decline_percent_p99",
        }.issubset(decline.columns)
        assert (output / "co2_target_sweep_overview.png").exists()
        assert (output / "co2_target_sweep_amoc_trajectories.png").exists()
        assert (output / "co2_target_sweep_amoc_percent_decline_trajectories.png").exists()
        assert (output / "long_run_state.json").exists()

        loaded = json.loads((output / "co2_target_sweep_summary.json").read_text())
        assert loaded["paired_parameter_design"] is True
        for outcome in ("persistent_collapse", "ever_collapse"):
            checks = loaded["monotonicity_checks"][outcome]
            assert set(checks) == {
                "is_non_decreasing",
                "violation_count",
                "maximum_downward_step",
            }
            for threshold in ("10_percent", "50_percent", "90_percent"):
                record = loaded["conditional_fraction_threshold_targets"][outcome][threshold]
                assert "estimate_ppm" in record
                assert "confidence_lower_ppm" in record
                assert "confidence_upper_ppm" in record
                assert record["confidence_level"] == 0.90


if __name__ == "__main__":
    test_linear_ramp_hold()
    test_target_sequence()
    test_gui_command()
    test_small_sweep()
    print("CO2 target-sweep tests passed")
