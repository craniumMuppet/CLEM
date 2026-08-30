#!/usr/bin/env python3
"""Regression coverage for the v2.23.0 continuation and validation fixes."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

import climate_model
from amoc_continuation import assign_branch_ids, pseudo_arclength_predictor
from climate_model import (
    ModelConfig,
    ProcessClimateModel,
    _find_amoc_equilibria_with_diagnostics,
    _validate_amoc_equilibrium_transient_stability,
    diagnose_amoc_hysteresis,
)
from held_out_amoc_validation import (
    DEFAULT_BENCHMARKS,
    evaluate_benchmarks,
    load_benchmarks,
)


def _root(q: float) -> dict:
    vector = np.zeros(8, dtype=float)
    vector[5] = q
    return {"vector": vector}


def test_branch_assignment_uses_global_secant_prediction() -> None:
    roots = {
        0.0: [_root(10.0), _root(0.0)],
        1.0: [_root(4.0), _root(6.0)],
        2.0: [_root(2.0), _root(8.0)],
    }
    assign_branch_ids(roots, maximum_match_distance=100.0)
    branch_from_zero = next(root["branch_id"] for root in roots[0.0] if root["vector"][5] == 0.0)
    branch_from_ten = next(root["branch_id"] for root in roots[0.0] if root["vector"][5] == 10.0)
    assert next(root["branch_id"] for root in roots[2.0] if root["vector"][5] == 8.0) == branch_from_zero
    assert next(root["branch_id"] for root in roots[2.0] if root["vector"][5] == 2.0) == branch_from_ten
    assert all(root["branch_prediction_used"] for root in roots[2.0])


def test_pseudo_arclength_predictor_can_turn_parameter_direction() -> None:
    previous = np.zeros(8)
    current = np.zeros(8)
    previous[5] = 0.0
    current[5] = 1.0
    predicted, parameter, tangent = pseudo_arclength_predictor(
        previous,
        0.10,
        current,
        0.05,
        step_size=1.0,
        parameter_scale=0.05,
    )
    assert predicted[5] > current[5]
    assert parameter < 0.05
    assert np.linalg.norm(tangent) == pytest.approx(1.0)


def test_root_search_reports_saturation_separately_from_seed_failures() -> None:
    config = replace(
        ModelConfig(),
        auto_initialize_from_1850=False,
        resolution_deg=10.0,
        amoc_equilibrium_stability_years=10.0,
        amoc_equilibrium_random_seed_batches=2,
        amoc_equilibrium_random_seeds_per_batch=2,
        amoc_equilibrium_root_saturation_batches=1,
        amoc_equilibrium_pseudo_arclength_enabled=False,
    )
    model = ProcessClimateModel(config)
    total_salt = float(
        np.sum(model.amoc_box_volumes_m3 * model._salinity_array(model.state))
    )
    roots, diagnostics = _find_amoc_equilibria_with_diagnostics(
        model, 0.0, model.state.copy(), total_salt
    )
    assert roots
    assert diagnostics["root_count_saturated"] is True
    assert diagnostics["additional_seed_search_performed"] is True
    assert diagnostics["search_confidence"] in {"high", "medium"}
    assert diagnostics["root_search_root_count_history"]
    assert diagnostics["root_search_failure_details_json"].startswith("[")


def test_unexpected_solver_exceptions_are_not_swallowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = replace(
        ModelConfig(),
        auto_initialize_from_1850=False,
        amoc_equilibrium_random_seed_batches=0,
        amoc_equilibrium_pseudo_arclength_enabled=False,
    )
    model = ProcessClimateModel(config)
    total_salt = float(
        np.sum(model.amoc_box_volumes_m3 * model._salinity_array(model.state))
    )

    def explode(*_args, **_kwargs):
        raise RuntimeError("programming defect")

    monkeypatch.setattr(climate_model, "least_squares", explode)
    with pytest.raises(RuntimeError, match="programming defect"):
        _find_amoc_equilibria_with_diagnostics(
            model, 0.0, model.state.copy(), total_salt
        )


def test_complex_dominant_mode_tests_real_and_imaginary_components(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = replace(
        ModelConfig(),
        auto_initialize_from_1850=False,
        amoc_equilibrium_stability_years=10.0,
    )
    model = ProcessClimateModel(config)
    vector = climate_model._amoc_equilibrium_vector(model, model.state)
    total_salt = float(
        np.sum(model.amoc_box_volumes_m3 * model._salinity_array(model.state))
    )

    def always_pass(*_args, **_kwargs):
        return {
            "final_ratio": 0.5,
            "excursion_ratio": 1.1,
            "last_window_peak_ratio": 0.6,
            "envelope_decay_ratio": 0.8,
            "envelope_log_slope_per_window": -0.1,
            "consecutive_contracting_windows": 3,
            "years_run": 100.0,
            "returned_within_initial_radius": True,
            "envelope_contracting": True,
            "hit_bounds": False,
            "passed": True,
        }

    monkeypatch.setattr(
        climate_model, "_integrate_amoc_equilibrium_perturbation", always_pass
    )
    eigenvectors = np.zeros((8, 8), dtype=complex)
    eigenvectors[0, 0] = 1.0
    eigenvectors[1, 0] = 1.0j
    result = _validate_amoc_equilibrium_transient_stability(
        model,
        vector,
        0.0,
        model.state.copy(),
        total_salt,
        eigenvectors=eigenvectors,
        years=10.0,
    )
    assert result["dominant_eigenvector_real_tested"] is True
    assert result["dominant_eigenvector_imag_tested"] is True
    assert result["transient_required_contracting_windows"] == 3


@pytest.mark.continuation
def test_real_continuation_emits_pseudo_arclength_branch_points() -> None:
    config = replace(
        ModelConfig(),
        resolution_deg=10.0,
        auto_initialize_from_1850=False,
        amoc_equilibrium_stability_years=10.0,
        amoc_equilibrium_random_seed_batches=1,
        amoc_equilibrium_random_seeds_per_batch=2,
        amoc_equilibrium_root_saturation_batches=1,
        amoc_equilibrium_max_refinement_rounds=0,
        amoc_equilibrium_arclength_max_steps=2,
    )
    frame = diagnose_amoc_hysteresis(
        config, maximum_hosing_sv=0.10, hosing_step_sv=0.05
    )
    branch = frame[frame["phase"] == "branch"]
    assert not branch.empty
    assert branch["pseudo_arclength_point"].eq(True).all()
    assert np.isfinite(branch["pseudo_arclength_constraint_error"]).all()
    assert frame.attrs["pseudo_arclength_points"] == len(branch)


def test_frozen_validation_has_multiple_provenance_complete_benchmarks() -> None:
    payload = load_benchmarks(DEFAULT_BENCHMARKS)
    assert len(payload["benchmarks"]) >= 4
    metrics = {
        "historical_gmst_2011_2020_c": 1.09,
        "historical_ocean_heat_content_change_1971_2018_zj": 400.0,
        "historical_arctic_amplification_1979_2021_ratio": 3.8,
        "ssp245_amoc_decline_2100_percent": 35.0,
        "ssp585_amoc_decline_2100_percent": 40.0,
    }
    result = evaluate_benchmarks(metrics, payload)
    assert result["all_external_benchmarks_passed"] is True
    assert len(payload["benchmark_set_sha256"]) == 64
    for evaluation in result["evaluations"].values():
        assert len(evaluation["benchmark_definition_sha256"]) == 64
        assert evaluation["source_location"]
        assert evaluation["retrieval_date"] == "2026-07-25"


def test_ocean_heat_content_diagnostic_is_finite() -> None:
    config = replace(
        ModelConfig(),
        scenario="ssp245",
        start_year=1850.0,
        duration_years=5.0,
        auto_initialize_from_1850=False,
        resolution_deg=10.0,
        record_every_years=1.0,
    )
    frame = ProcessClimateModel(config).run().dataframe
    assert np.isfinite(frame["ocean_heat_content_anomaly_zj"]).all()
    assert np.isfinite(frame["surface_ocean_heat_content_anomaly_zj"]).all()
    assert np.isfinite(frame["deep_ocean_heat_content_anomaly_zj"]).all()
