#!/usr/bin/env python3
"""Regression tests for the v2.21.0 scientific review corrections."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from climate_model import (
    ModelConfig,
    ProcessClimateModel,
    SensitivityDiagnostics,
    _find_amoc_equilibria,
    amoc_hysteresis_summary,
)


def equilibrium_model() -> ProcessClimateModel:
    config = replace(
        ModelConfig(),
        start_year=0.0,
        duration_years=1.0,
        scenario="constant",
        co2_start_ppm=278.3,
        co2_end_ppm=278.3,
        co2_peak_ppm=278.3,
        additional_forcing_wm2=0.0,
        freshwater_hosing_sv=0.0,
        warming_freshwater_sv_per_k=0.0,
        hydrological_freshwater_sv_per_k=0.0,
        greenland_freshwater_sv_per_k=0.0,
        freshwater_start_fraction=1.0,
        freshwater_compensation_mode="atlantic",
        auto_initialize_from_1850=False,
    )
    return ProcessClimateModel(config)


def total_salt(model: ProcessClimateModel) -> float:
    return float(
        np.sum(
            model.amoc_box_volumes_m3
            * model._salinity_array(model.state)
        )
    )


def test_whole_domain_equilibrium_salt_closure() -> None:
    model = equilibrium_model()
    template = model.state.copy()
    roots = _find_amoc_equilibria(
        model,
        0.30,
        template,
        total_salt(model),
    )
    assert roots
    root = roots[0]
    assert root["maximum_absolute_full_salinity_tendency_psu_per_year"] < 5.0e-8
    assert abs(root["external_salinity_tendency_psu_per_year"]) < 5.0e-8
    assert abs(root["whole_domain_salt_closure_error_ppm"]) < 1.0e-8


def test_smooth_stability_and_transient_validation() -> None:
    model = equilibrium_model()
    midpoint = model._convection_adjustment_timescale(1.0, 1.0)
    below = model._convection_adjustment_timescale(1.0 - 1.0e-8, 1.0)
    above = model._convection_adjustment_timescale(1.0 + 1.0e-8, 1.0)
    expected_midpoint = 0.5 * (
        model.config.amoc_convection_adjustment_years
        + model.config.amoc_convection_recovery_years
    )
    assert abs(midpoint - expected_midpoint) < 1.0e-12
    assert abs(above - below) < 1.0e-3

    roots = _find_amoc_equilibria(
        model,
        0.0,
        model.state.copy(),
        total_salt(model),
    )
    assert roots
    control = roots[0]
    assert control["linear_stable"]
    assert control["transient_stable"]
    assert control["stable"]
    assert control["transient_perturbation_failures"] == 0


def test_collapse_threshold_semantics() -> None:
    model = ProcessClimateModel(
        ModelConfig(
            scenario="constant",
            duration_years=1.0,
            auto_initialize_from_1850=False,
            amoc_collapse_threshold_sv=8.0,
        )
    )
    model.state.amoc_sv = 7.0
    diagnostic = model._amoc_diagnostics(model.state)
    assert diagnostic["amoc_weak_or_collapsed"] == 1.0
    assert diagnostic["amoc_active"] == 0.0
    assert diagnostic["amoc_collapsed_numeric"] == 1.0
    assert diagnostic["amoc_below_six_sv_reference"] == 0.0

    model.state.amoc_sv = -1.0
    diagnostic = model._amoc_diagnostics(model.state)
    assert diagnostic["amoc_reversed"] == 1.0
    assert diagnostic["amoc_collapsed_numeric"] == 0.0
    assert diagnostic["amoc_weak_or_collapsed"] == 0.0

    frame = pd.DataFrame(
        {
            "phase": ["up", "up", "down", "down"],
            "target_hosing_sv": [0.0, 0.2, 0.2, 0.1],
            "amoc_sv": [17.0, 7.0, 7.0, 9.0],
            "salt_conservation_error_ppm": [0.0, 0.0, 0.0, 0.0],
            "amoc_collapse_threshold_sv": [8.0, 8.0, 8.0, 8.0],
            "diagnostic_type": ["test"] * 4,
            "equilibrium_stable": [True] * 4,
            "stable_root_found": [True] * 4,
            "root_search_complete": [True] * 4,
            "solver_hit_bounds": [False] * 4,
        }
    )
    summary = amoc_hysteresis_summary(frame)
    assert summary["amoc_collapse_threshold_sv"] == 8.0
    assert summary["collapse_threshold_hosing_sv"] == 0.2
    assert summary["recovery_threshold_hosing_sv"] == 0.1


def test_calibration_outputs_are_not_labeled_validation() -> None:
    diagnostics = SensitivityDiagnostics(
        equilibrium_ecs_c=3.0,
        equilibrium_converged=True,
        equilibrium_simulation_years=1200.0,
        equilibrium_tail_years=100.0,
        equilibrium_toa_tolerance_wm2=0.05,
        gregory_effective_ecs_c=3.1,
        gregory_forcing_wm2=3.93,
        gregory_restoring_coefficient_wm2_k=1.2,
        tcr_c=1.8,
        equilibrium_toa_imbalance_wm2=0.01,
        feedbacks_wm2_k={"net": -1.2},
        abrupt_2x=pd.DataFrame(),
        one_percent=pd.DataFrame(),
    )
    summary = diagnostics.summary()
    assert summary["evidence_role"] == "calibrated_process_diagnostic"
    assert summary["independent_validation"] is False


def test_reversible_regional_freshwater_and_regrowth() -> None:
    config = ModelConfig(
        scenario="constant",
        duration_years=1.0,
        auto_initialize_from_1850=False,
        greenland_temperature_driver="regional",
        hydrological_freshwater_reversible=True,
        greenland_regrowth_sv_per_k=0.01,
        greenland_freshwater_adjustment_years=1.0,
    )
    model = ProcessClimateModel(config)
    state = model.state
    state.land_anomaly_c[:] = -2.0
    state.atlantic_ocean_anomaly_c[:] = -1.0
    state.non_atlantic_ocean_anomaly_c[:] = -1.0
    state.greenland_remaining_ice_gt = 0.5 * config.greenland_initial_ice_mass_gt
    state.greenland_cumulative_melt_gt = (
        config.greenland_initial_ice_mass_gt - state.greenland_remaining_ice_gt
    )
    state.greenland_cumulative_accumulation_gt = 0.0
    state.greenland_cumulative_net_ice_loss_gt = (
        config.greenland_initial_ice_mass_gt - state.greenland_remaining_ice_gt
    )
    state.greenland_freshwater_sv = -0.005

    hydrological, _, target = model._freshwater_components(state, -1.0)
    assert hydrological < 0.0
    assert target < 0.0
    assert model._greenland_regional_warming_c(state) < -1.5

    before = state.greenland_remaining_ice_gt
    model.step(0.0)
    assert model.state.greenland_remaining_ice_gt > before
    assert model.state.greenland_freshwater_sv < 0.0
    assert model.state.greenland_cumulative_melt_gt >= state.greenland_cumulative_melt_gt
    assert model.state.greenland_cumulative_accumulation_gt > 0.0
    assert abs(
        model.state.greenland_cumulative_melt_gt
        - model.state.greenland_cumulative_accumulation_gt
        - model.state.greenland_cumulative_net_ice_loss_gt
    ) < 1.0e-6
    assert abs(
        model.state.greenland_remaining_ice_gt
        + model.state.greenland_cumulative_net_ice_loss_gt
        - config.greenland_initial_ice_mass_gt
    ) < 1.0e-6


def main() -> None:
    tests = (
        test_whole_domain_equilibrium_salt_closure,
        test_smooth_stability_and_transient_validation,
        test_collapse_threshold_semantics,
        test_calibration_outputs_are_not_labeled_validation,
        test_reversible_regional_freshwater_and_regrowth,
    )
    for test in tests:
        test()
        print(f"PASS: {test.__name__}")
    print("All v2.22.0 review-fix tests passed.")


if __name__ == "__main__":
    main()
