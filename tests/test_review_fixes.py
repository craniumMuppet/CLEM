"""Targeted tests for the v2.20.0 review fixes."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from amoc_outcomes import collapse_duration_diagnostics
from climate_model import ModelConfig, ProcessClimateModel
from co2_target_sweep import (
    _isotonic_non_decreasing,
    _monotonicity_diagnostics,
    _threshold_estimates,
)
from monte_carlo import parse_ranges


def test_hybrid_switch_must_be_inside_requested_run() -> None:
    config = ModelConfig(
        scenario="hybrid_ssp",
        start_year=2100.0,
        duration_years=20.0,
        ssp_switch_year=2000.0,
    )
    with pytest.raises(ValueError, match="2100"):
        config.validate()


def test_ssp460_summary_reports_automatic_initialization() -> None:
    config = ModelConfig(
        scenario="ssp460",
        start_year=2000.0,
        duration_years=1.0,
        dt_years=0.25,
        record_every_years=1.0,
        resolution_deg=10.0,
    )
    summary = ProcessClimateModel(config).run().summary()
    assert summary["auto_initialized_from_1850"] is True


def test_meinshausen_forcing_is_zero_at_reference_and_exact_at_doubling() -> None:
    config = ModelConfig(
        scenario="constant",
        co2_forcing_formula="meinshausen2020",
        co2_doubling_erf_wm2=3.93,
        auto_initialize_from_1850=False,
        resolution_deg=10.0,
    )
    model = ProcessClimateModel(config)
    assert model.co2_forcing_wm2(config.co2_reference_ppm) == pytest.approx(0.0)
    assert model.co2_forcing_wm2(2.0 * config.co2_reference_ppm) == pytest.approx(3.93)


def test_meinshausen_high_co2_curvature_differs_from_logarithmic() -> None:
    logarithmic = ProcessClimateModel(
        ModelConfig(
            co2_forcing_formula="logarithmic",
            auto_initialize_from_1850=False,
            resolution_deg=10.0,
        )
    )
    meinshausen = ProcessClimateModel(
        replace(logarithmic.config, co2_forcing_formula="meinshausen2020")
    )
    assert not np.isclose(
        logarithmic.co2_forcing_wm2(1200.0),
        meinshausen.co2_forcing_wm2(1200.0),
    )


def test_monte_carlo_rejects_experiment_controls() -> None:
    with pytest.raises(ValueError, match="experiment control"):
        parse_ranges(
            [["dt_years", "0.05", "0.2"]],
            ModelConfig(),
            "none",
            False,
        )


def test_monte_carlo_accepts_whitelisted_physical_parameters() -> None:
    ranges = parse_ranges(
        [["amoc_reference_sv", "14", "20"]],
        ModelConfig(),
        "none",
        False,
    )
    assert ranges == {"amoc_reference_sv": (14.0, 20.0)}


def test_duration_classifier_rejects_sustained_recovery() -> None:
    years = np.arange(0.0, 31.0)
    values = np.full(years.size, 5.0)
    values[(years >= 20.0) & (years <= 26.0)] = 9.0
    diagnostics = collapse_duration_diagnostics(
        values,
        years,
        threshold_sv=6.0,
        window_years=30.0,
        persistence_fraction=0.75,
        recovery_years=5.0,
    )
    assert diagnostics["final_amoc_sv"] == 5.0
    assert diagnostics["final_window_collapsed_fraction"] >= 0.75
    assert diagnostics["final_window_longest_active_recovery_years"] >= 5.0
    assert diagnostics["persistent_collapsed"] is False


def test_zero_recovery_threshold_allows_no_recovery_but_rejects_any_recovery() -> None:
    years = np.arange(0.0, 31.0)
    fully_weak = collapse_duration_diagnostics(
        np.full(years.size, 5.0),
        years,
        threshold_sv=6.0,
        window_years=30.0,
        recovery_years=0.0,
    )
    assert fully_weak["persistent_collapsed"] is True

    recovered = np.full(years.size, 5.0)
    recovered[15] = 7.0
    diagnostics = collapse_duration_diagnostics(
        recovered,
        years,
        threshold_sv=6.0,
        window_years=30.0,
        persistence_fraction=0.90,
        recovery_years=0.0,
    )
    assert diagnostics["final_window_longest_active_recovery_years"] > 0.0
    assert diagnostics["persistent_collapsed"] is False


def test_duration_classifier_accepts_persistent_weak_state() -> None:
    years = np.arange(0.0, 31.0)
    diagnostics = collapse_duration_diagnostics(
        np.full(years.size, 5.0),
        years,
        threshold_sv=6.0,
        window_years=30.0,
    )
    assert diagnostics["persistent_collapsed"] is True
    assert diagnostics["final_window_collapsed_fraction"] == pytest.approx(1.0)


def test_monotonicity_check_and_isotonic_projection() -> None:
    fractions = np.array([0.0, 0.4, 0.3, 0.8])
    diagnostics = _monotonicity_diagnostics(fractions)
    projected = _isotonic_non_decreasing(fractions)
    assert diagnostics["is_non_decreasing"] is False
    assert diagnostics["violation_count"] == 1
    assert np.all(np.diff(projected) >= -1.0e-12)


def test_threshold_estimates_include_bootstrap_interval() -> None:
    targets = np.array([300.0, 400.0, 500.0, 600.0])
    point = np.array([0.0, 0.2, 0.6, 0.9])
    bootstrap = np.array(
        [
            [0.0, 0.1, 0.5, 0.8],
            [0.0, 0.3, 0.7, 1.0],
            [0.0, 0.2, 0.6, 0.9],
        ]
    )
    estimates, diagnostics = _threshold_estimates(
        targets,
        point,
        bootstrap,
        [0.5],
        0.90,
    )
    record = estimates["50_percent"]
    assert diagnostics["is_non_decreasing"] is True
    assert record["estimate_ppm"] is not None
    assert record["confidence_lower_ppm"] is not None
    assert record["confidence_upper_ppm"] is not None
    assert record["confidence_lower_ppm"] <= record["confidence_upper_ppm"]


def test_structural_amoc_modes_are_explicit_and_operational() -> None:
    base = ModelConfig(
        scenario="constant",
        duration_years=1.0,
        dt_years=0.2,
        resolution_deg=10.0,
        auto_initialize_from_1850=False,
    )
    diagnostic_model = ProcessClimateModel(
        replace(base, amoc_indo_pacific_compensation_mode="diagnostic")
    )
    diagnostic_state = diagnostic_model.state.copy()
    diagnostic_state.amoc_sv = 5.0
    diagnostic = diagnostic_model._amoc_diagnostics(diagnostic_state)
    assert diagnostic["amoc_indo_pacific_compensation_diagnostic_sv"] > 0.0
    assert diagnostic["amoc_indo_pacific_compensation_active_sv"] == 0.0

    interactive_model = ProcessClimateModel(
        replace(base, amoc_indo_pacific_compensation_mode="interactive")
    )
    interactive_state = interactive_model.state.copy()
    interactive_state.amoc_sv = 5.0
    interactive = interactive_model._amoc_diagnostics(interactive_state)
    assert interactive["amoc_indo_pacific_compensation_active_sv"] > 0.0
    assert interactive["pycnocline_volume_imbalance_sv"] > diagnostic[
        "pycnocline_volume_imbalance_sv"
    ]

    southern_model = ProcessClimateModel(
        replace(base, amoc_southern_ocean_structure="warming_sensitive")
    )
    southern_state = southern_model.state.copy()
    southern_state.atlantic_ocean_anomaly_c[:] = 2.0
    southern = southern_model._amoc_diagnostics(southern_state)
    assert southern["amoc_southern_wind_multiplier"] > 1.0
    assert southern["amoc_southern_upwelling_multiplier"] > 1.0
