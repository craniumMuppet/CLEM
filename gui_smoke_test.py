#!/usr/bin/env python3
"""Headless checks for deterministic and constrained Monte Carlo GUI commands."""

from __future__ import annotations

from climate_model_gui import DEFAULTS, build_cli_command, validate_values


def test_deterministic_command() -> None:
    values = dict(DEFAULTS)
    values.update(
        {
            "scenario": "hybrid_ssp",
            "ssp_before": "ssp585",
            "ssp_after": "ssp245",
            "switch_year": "2020",
            "transition_years": "10",
            "start_year": "1850",
            "years": "250",
            "freshwater_hosing": "0.1",
            "output": "test_output",
            "run_diagnostics": False,
            "run_amoc_hysteresis": True,
            "auto_initialize_from_1850": False,
            "monte_carlo_enabled": False,
        }
    )
    validate_values(values)
    joined = " ".join(build_cli_command(values))
    for item in [
        "climate_model.py",
        "--scenario hybrid_ssp",
        "--ssp-before ssp585",
        "--ssp-after ssp245",
        "--switch-year 2020",
        "--freshwater-hosing 0.1",
        "--skip-diagnostics",
        "--run-amoc-hysteresis",
        "--no-auto-initialize-from-1850",
    ]:
        assert item in joined, item


def test_constrained_monte_carlo_command() -> None:
    values = dict(DEFAULTS)
    values.update(
        {
            "scenario": "ssp245",
            "start_year": "1850",
            "years": "250",
            "output": "mc_output",
            "monte_carlo_enabled": True,
            "mc_runs": "512",
            "mc_seed": "123",
            "mc_workers": "4",
            "mc_sampling": "triangular",
            "mc_design": "sobol",
            "mc_constraint_mode": "ar6_amoc",
            "mc_use_science_defaults": True,
            "mc_run_calibration_experiments": True,
            "mc_correlated_priors": True,
            "mc_max_plotted": "0",
            "mc_save_long_csv": True,
            "mc_no_plots": True,
        }
    )
    validate_values(values)
    joined = " ".join(build_cli_command(values))
    for item in [
        "monte_carlo.py",
        "--monte-carlo-runs 512",
        "--mc-seed 123",
        "--mc-workers 4",
        "--mc-sampling triangular",
        "--mc-design sobol",
        "--mc-constraint-mode ar6_amoc",
        "--mc-use-science-priors",
        "--mc-run-calibration-experiments",
        "--mc-save-long-csv",
        "--mc-no-plots",
    ]:
        assert item in joined, item
    assert "--mc-range" not in joined
    assert "--mc-no-correlated-priors" not in joined



def test_default_clock_seed_command() -> None:
    values = dict(DEFAULTS)
    values.update(
        {
            "monte_carlo_enabled": True,
            "scenario": "ssp245",
            "output": "clock_seed_mc",
        }
    )
    validate_values(values)
    joined = " ".join(build_cli_command(values))
    assert "--mc-seed 0" in joined

def test_custom_exploratory_command() -> None:
    values = dict(DEFAULTS)
    values.update(
        {
            "monte_carlo_enabled": True,
            "mc_constraint_mode": "none",
            "mc_use_science_defaults": False,
            "mc_co2_erf_enabled": True,
            "mc_co2_erf_min": "3.5",
            "mc_co2_erf_max": "4.4",
            "output": "custom_mc",
        }
    )
    validate_values(values)
    joined = " ".join(build_cli_command(values))
    assert "--mc-constraint-mode none" in joined
    assert "--mc-range co2_doubling_erf_wm2 3.5 4.4" in joined


def main() -> None:
    test_deterministic_command()
    print("PASS: deterministic GUI command")
    test_constrained_monte_carlo_command()
    print("PASS: constrained Monte Carlo GUI command")
    test_default_clock_seed_command()
    print("PASS: default system-clock seed GUI command")
    test_custom_exploratory_command()
    print("PASS: custom selected-scenario GUI command")
    print("All GUI command-builder smoke tests passed.")


if __name__ == "__main__":
    main()
