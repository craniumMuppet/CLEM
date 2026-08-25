#!/usr/bin/env python3
"""Regression coverage for the v2.22.0 continuation and validation hardening."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

import climate_model
from climate_model import (
    ModelConfig,
    ProcessClimateModel,
    _amoc_equilibrium_bounds,
    _find_amoc_equilibria,
    amoc_hysteresis_summary,
    diagnose_amoc_hysteresis,
)
from held_out_amoc_validation import evaluate_benchmarks, load_benchmarks, DEFAULT_BENCHMARKS


def _mock_root(model: ProcessClimateModel, template, q: float, stable: bool) -> dict:
    state = template.copy()
    state.amoc_sv = q
    vector = climate_model._amoc_equilibrium_vector(model, state)
    return {
        "vector": vector,
        "state": state,
        "stable": stable,
        "linear_stable": stable,
        "transient_stable": stable,
        "jacobian_classification_consistent": True,
        "transient_perturbation_failures": 0,
        "transient_perturbation_cases": 1,
        "transient_maximum_final_distance_ratio": 0.5,
        "transient_dt_classification_consistent": True,
        "maximum_real_eigenvalue_per_year": -0.01 if stable else 0.01,
        "residual_norm": 0.0,
        "maximum_absolute_full_salinity_tendency_psu_per_year": 0.0,
        "external_salinity_tendency_psu_per_year": 0.0,
        "whole_domain_salt_closure_error_ppm": 0.0,
        "solver_hit_bounds": False,
    }


def _mock_search_diagnostics(roots: list[dict]) -> dict:
    return {
        "root_search_complete": True,
        "root_search_attempts": 1,
        "root_search_solver_failures": 0,
        "root_search_converged_candidates": len(roots),
        "root_search_distinct_roots": len(roots),
        "root_search_stable_roots": sum(bool(root["stable"]) for root in roots),
        "root_search_hit_bounds": False,
    }


@pytest.mark.continuation
def test_unstable_roots_are_never_selected(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_find(model, _hosing, template, _salt, _guesses=None):
        roots = [_mock_root(model, template, 8.0, stable=False)]
        return roots, _mock_search_diagnostics(roots)

    monkeypatch.setattr(climate_model, "_find_amoc_equilibria_with_diagnostics", fake_find)
    config = replace(
        ModelConfig(),
        resolution_deg=10.0,
        auto_initialize_from_1850=False,
        amoc_equilibrium_max_refinement_rounds=0,
    )
    frame = diagnose_amoc_hysteresis(config, maximum_hosing_sv=0.1, hosing_step_sv=0.1)
    assert not frame["stable_root_found"].any()
    assert not frame["equilibrium_stable"].any()
    assert frame["amoc_sv"].isna().all()
    assert amoc_hysteresis_summary(
        frame, allow_incomplete=True
    )["unstable_selected_points"] == 0


@pytest.mark.continuation
def test_adaptive_refinement_and_branch_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_find(model, hosing, template, _salt, _guesses=None):
        q = 17.0 if hosing < 0.05 else 3.0
        roots = [_mock_root(model, template, q, stable=True)]
        return roots, _mock_search_diagnostics(roots)

    monkeypatch.setattr(climate_model, "_find_amoc_equilibria_with_diagnostics", fake_find)
    config = replace(
        ModelConfig(),
        resolution_deg=10.0,
        auto_initialize_from_1850=False,
        amoc_equilibrium_max_refinement_rounds=2,
        amoc_equilibrium_minimum_hosing_step_sv=0.025,
        amoc_equilibrium_branch_jump_sv=3.0,
    )
    frame = diagnose_amoc_hysteresis(config, maximum_hosing_sv=0.1, hosing_step_sv=0.1)
    levels = set(np.round(frame["target_hosing_sv"].unique(), 6))
    assert 0.05 in levels
    assert 0.025 in levels
    assert "branch_id" in frame
    assert frame["root_search_complete"].all()
    assert frame["stable_root_found"].all()
    assert frame["diagnostic_type"].eq(
        "preindustrial_fixed_climate_amoc_equilibrium_continuation"
    ).all()


def test_equilibrium_bounds_are_configurable() -> None:
    config = replace(
        ModelConfig(),
        auto_initialize_from_1850=False,
        amoc_allow_reversal=True,
        amoc_equilibrium_salinity_min_psu=20.0,
        amoc_equilibrium_salinity_max_psu=47.0,
        amoc_equilibrium_transport_max_sv=65.0,
        amoc_equilibrium_pycnocline_min_m=75.0,
        amoc_equilibrium_pycnocline_max_m=5000.0,
    )
    model = ProcessClimateModel(config)
    lower, upper = _amoc_equilibrium_bounds(model)
    assert lower[0] == 20.0 and upper[0] == 47.0
    assert lower[5] == -65.0 and upper[5] == 65.0
    assert lower[7] == 75.0 and upper[7] == 5000.0


@pytest.mark.continuation
def test_jacobian_and_nonlinear_stability_are_multiscale() -> None:
    config = replace(
        ModelConfig(),
        auto_initialize_from_1850=False,
        resolution_deg=10.0,
        amoc_equilibrium_stability_years=40.0,
    )
    model = ProcessClimateModel(config)
    total_salt = float(
        np.sum(model.amoc_box_volumes_m3 * model._salinity_array(model.state))
    )
    roots = _find_amoc_equilibria(model, 0.0, model.state.copy(), total_salt)
    assert roots
    root = roots[-1]
    assert "jacobian_classification_consistent" in root
    assert root["jacobian_relative_steps"] == "3e-06,1e-05,3e-05"
    assert root["stability_scope"] == "reduced_amoc_subsystem"
    if root["linear_stable"]:
        assert root["transient_perturbation_cases"] >= 20
        assert root["transient_validation_dt_years"] == "1.0,0.5,0.25"
        assert "transient_contracting_envelope_cases" in root
        assert "transient_maximum_years_run" in root


def test_greenland_specific_driver_and_separate_mass_counters() -> None:
    config = replace(
        ModelConfig(),
        auto_initialize_from_1850=False,
        resolution_deg=5.0,
        greenland_temperature_driver="greenland",
        greenland_regrowth_sv_per_k=0.01,
        greenland_freshwater_adjustment_years=1.0,
    )
    model = ProcessClimateModel(config)
    state = model.state
    state.land_anomaly_c[:] = np.exp(-0.5 * ((model.grid.lat - 72.0) / 4.0) ** 2)
    greenland = model._greenland_specific_warming_c(state)
    regional = model._greenland_regional_warming_c(state)
    _, selected = model._freshwater_temperature_drivers(state, 0.0)
    assert selected == pytest.approx(greenland)
    assert abs(greenland - regional) > 1.0e-3

    state.land_anomaly_c[:] = -2.0
    state.greenland_remaining_ice_gt = 0.5 * config.greenland_initial_ice_mass_gt
    state.greenland_cumulative_melt_gt = 0.5 * config.greenland_initial_ice_mass_gt
    state.greenland_cumulative_accumulation_gt = 0.0
    state.greenland_cumulative_net_ice_loss_gt = 0.5 * config.greenland_initial_ice_mass_gt
    state.greenland_freshwater_sv = -0.005
    gross_melt_before = state.greenland_cumulative_melt_gt
    model.step(0.0)
    assert model.state.greenland_cumulative_melt_gt >= gross_melt_before - 1.0e-6
    assert model.state.greenland_cumulative_accumulation_gt > 0.0
    assert model.state.greenland_cumulative_net_ice_loss_gt < gross_melt_before
    assert model.record(0.0)["greenland_cumulative_sea_level_mm"] == pytest.approx(
        model.state.greenland_cumulative_net_ice_loss_gt / 362.0
    )


def test_held_out_benchmark_metadata_and_evaluation() -> None:
    payload = load_benchmarks(DEFAULT_BENCHMARKS)
    passing_metrics = {
        "historical_gmst_2011_2020_c": 1.09,
        "historical_ocean_heat_content_change_1971_2018_zj": 400.0,
        "historical_arctic_amplification_1979_2021_ratio": 3.8,
        "ssp245_amoc_decline_2100_percent": 35.0,
        "ssp585_amoc_decline_2100_percent": 40.0,
    }
    passing = evaluate_benchmarks(passing_metrics, payload)
    failing = evaluate_benchmarks(
        {**passing_metrics, "ssp245_amoc_decline_2100_percent": 5.0}, payload
    )
    assert passing["all_external_benchmarks_passed"] is True
    assert failing["all_external_benchmarks_passed"] is False
    evaluation = passing["evaluations"]["ssp245_amoc_decline_2100_percent"]
    assert evaluation["used_for_tuning"] is True
    assert evaluation["evidence_role"] == "tuning_informed_development_regression"
    assert "source_reference" in evaluation


def test_summary_rejects_incomplete_frames_and_reports_gaps() -> None:
    with pytest.raises(ValueError, match="incomplete"):
        amoc_hysteresis_summary(
            pd.DataFrame(
                {
                    "phase": ["up"],
                    "target_hosing_sv": [0.0],
                    "amoc_sv": [17.0],
                    "equilibrium_stable": [True],
                }
            )
        )

    frame = pd.DataFrame(
        {
            "phase": ["up", "down"],
            "target_hosing_sv": [0.0, 0.0],
            "amoc_sv": [np.nan, np.nan],
            "equilibrium_stable": [False, False],
            "stable_root_found": [False, False],
            "root_search_complete": [True, True],
            "solver_hit_bounds": [False, False],
            "amoc_collapse_threshold_sv": [6.0, 6.0],
            "diagnostic_type": ["test", "test"],
            "threshold_resolution_sv": [0.05, 0.05],
        }
    )
    with pytest.raises(ValueError, match="continuation is incomplete"):
        amoc_hysteresis_summary(frame)
    summary = amoc_hysteresis_summary(frame, allow_incomplete=True)
    assert summary["continuation_complete"] is False
    assert summary["unresolved_points"] == 2
    assert summary["collapse_threshold_hosing_sv"] is None
