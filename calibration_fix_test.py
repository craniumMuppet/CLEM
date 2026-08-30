#!/usr/bin/env python3
"""Regression tests for the v2.17.0 calibration and likelihood corrections."""

from __future__ import annotations

import numpy as np

from climate_model import ModelConfig, ProcessClimateModel, diagnose_climate_sensitivity
from monte_carlo import (
    AR6_TARGETS,
    AMOC_TARGETS,
    FIXED_SCIENCE_PRIOR_PARAMETERS,
    SCIENCE_PRIOR_SPECS,
    _historical_diagnostics,
    compute_importance_weights,
    generate_samples,
    science_default_ranges,
)


def test_default_feedback_decomposition() -> None:
    diagnostics = diagnose_climate_sensitivity(
        ModelConfig(scenario="constant", duration_years=1.0),
        equilibrium_years=400.0,
    )
    feedbacks = diagnostics.feedbacks_wm2_k
    wv_lr = feedbacks["Water vapor"] + feedbacks["Lapse rate"]
    assert -3.40 <= feedbacks["Planck"] <= -3.00
    assert 1.10 <= wv_lr <= 1.50
    assert 0.10 <= feedbacks["Surface albedo"] <= 0.60
    assert -0.10 <= feedbacks["Cloud"] <= 0.94
    assert -1.81 <= feedbacks["Net feedback"] <= -0.51
    assert 2.0 <= diagnostics.equilibrium_ecs_c <= 5.0
    assert 1.2 <= diagnostics.tcr_c <= 2.4


def test_total_atlantic_heat_transport_definition() -> None:
    config = ModelConfig(scenario="constant", duration_years=1.0)
    diagnostics = _historical_diagnostics(config)
    expected = (
        diagnostics["historical_amoc_2004_2023_sv"]
        * config.amoc_heat_transport_pw_per_sv
        + config.atlantic_gyre_heat_transport_pw
    )
    assert abs(diagnostics["historical_mht_2004_2023_pw"] - expected) < 1.0e-12
    assert 0.90 <= expected <= 1.50



def test_ohue_uses_explicit_ocean_heat_uptake() -> None:
    config = ModelConfig(scenario="constant", duration_years=1.0)
    diagnostics = _historical_diagnostics(config)
    historical = ProcessClimateModel(
        ModelConfig(
            scenario="ssp245",
            forcing_mode="total_effective",
            start_year=1850.0,
            duration_years=173.0,
            freshwater_hosing_sv=0.0,
            freshwater_start_fraction=1.0,
            record_every_years=1.0,
        )
    ).run().dataframe
    baseline = historical.loc[
        (historical["year"] >= 1850.0) & (historical["year"] <= 1900.0),
        "global_surface_warming_c",
    ].mean()
    frame = historical.loc[
        (historical["year"] >= 1970.0) & (historical["year"] <= 2019.0)
    ]
    temperature = frame["global_surface_warming_c"].to_numpy(dtype=float) - float(baseline)
    ocean_uptake = frame["ocean_heat_uptake_wm2"].to_numpy(dtype=float)
    valid = np.isfinite(temperature) & np.isfinite(ocean_uptake) & (temperature > 0.05)
    expected = float(
        np.sum(temperature[valid] * ocean_uptake[valid])
        / np.sum(temperature[valid] ** 2)
    )
    assert abs(diagnostics["historical_ohue_1970_2019_wm2_k"] - expected) < 1.0e-12
    assert abs(
        diagnostics["historical_ocean_heat_uptake_efficiency_1970_2019_wm2_k"]
        - expected
    ) < 1.0e-12


def _summary(offset: float) -> dict[str, float]:
    return {
        "co2_doubling_erf_wm2": 3.93 + 0.05 * offset,
        "feedback_planck_wm2_k": -3.22 + 0.05 * offset,
        "feedback_wv_lr_wm2_k": 1.30 + 0.05 * offset,
        "feedback_surface_albedo_wm2_k": 0.35 + 0.03 * offset,
        "feedback_cloud_wm2_k": 0.42 + 0.10 * offset,
        "feedback_net_wm2_k": -1.16 + 0.10 * offset,
        "equilibrium_ecs_c": 3.0 + 0.2 * offset,
        "tcr_c": 1.8 + 0.1 * offset,
        "historical_warming_2011_2020_c": 1.09 + 0.03 * offset,
        "historical_eei_2006_2018_wm2": 0.79 + 0.05 * offset,
        "historical_ohue_1970_2019_wm2_k": 0.58 + 0.03 * offset,
        "historical_amoc_2004_2023_sv": 16.9 + 0.3 * offset,
        "historical_mht_2004_2023_pw": 1.20 + 0.05 * offset,
        "historical_fovs_2004_2023_sv": -0.15 + 0.02 * offset,
        "ssp585_amoc_decline_2100_percent": 30.0 + 3.0 * offset,
        "hosing_0p1_amoc_decline_40yr_percent": 25.0 + 2.0 * offset,
        "equilibrium_toa_imbalance_wm2": 0.1,
        "maximum_absolute_salt_conservation_error_ppm": 1.0e-9,
        "maximum_pre_projection_salt_conservation_error_ppm": 1.0e-10,
        "cumulative_absolute_salt_projection_correction_ppm": 1.0e-8,
        "initial_amoc_density_driver_ratio": 1.0,
        "maximum_arctic_open_water_temperature_c": 10.0,
        "maximum_arctic_open_water_temperature_c_at_5pct_open": 8.0,
        "maximum_dormant_arctic_open_water_heat_wyr_m2": 0.0,
        "arctic_reference_periodic_closure_wyr_m2": 1.0e-10,
        "arctic_reference_spinup_convergence_wyr_m2": 1.0e-10,
        "arctic_reference_convergence_tolerance_wyr_m2": 1.0e-8,
    }


def test_grouped_likelihood_outputs() -> None:
    results = [{"summary": _summary(x)} for x in (-1.0, -0.3, 0.0, 0.4, 1.0)]
    weights, _, reasons, _ = compute_importance_weights(results, "ar6_amoc")
    assert np.isclose(weights.sum(), 1.0)
    assert all(not reason for reason in reasons)
    assert 1.0 / np.sum(weights**2) > 2.5
    for result in results:
        keys = {
            k
            for k in result["summary"]
            if k.startswith("constraint_loglike_")
            and not k.startswith("constraint_loglike_target_")
        }
        assert keys == {
            "constraint_loglike_forcing",
            "constraint_loglike_feedback_decomposition",
            "constraint_loglike_sensitivity",
            "constraint_loglike_historical_climate",
            "constraint_loglike_amoc_state",
            "constraint_loglike_amoc_response",
        }
        assert "constraint_loglike_target_equilibrium_ecs_c" in result["summary"]
        assert "constraint_weighted_loglike_sensitivity" in result["summary"]



def test_physical_priors_do_not_duplicate_likelihood_intervals() -> None:
    ranges = science_default_ranges("ar6_amoc")
    targets = {target.key: target for target in (*AR6_TARGETS, *AMOC_TARGETS)}
    for key in ("co2_doubling_erf_wm2", "initial_fovs_sv"):
        target = targets[
            {"initial_fovs_sv": "historical_fovs_2004_2023_sv"}.get(key, key)
        ]
        lower, upper = ranges[key]
        assert lower < target.lower
        assert upper > target.upper

    # The control-state AMOC strength is an initialization/calibration anchor,
    # not a process prior. It remains represented in the AMOC-state likelihood
    # but is fixed at the configured base value in built-in science-prior runs.
    assert "amoc_reference_sv" in FIXED_SCIENCE_PRIOR_PARAMETERS
    assert "amoc_reference_sv" not in ranges
    assert ModelConfig().amoc_reference_sv == 17.0
    assert "historical_amoc_2004_2023_sv" in targets
    assert all(target.key != "feedback_net_wm2_k" for target in AR6_TARGETS)


def test_parameter_specific_prior_marginals_and_correlations() -> None:
    config = ModelConfig()
    names = [
        "relative_humidity",
        "deep_ocean_heat_capacity_wyr_m2_k",
        "ocean_heat_exchange_wm2_k",
        "amoc_initial_pycnocline_depth_m",
        "initial_fovs_sv",
    ]
    default_ranges = science_default_ranges("ar6_amoc")
    assert "amoc_reference_sv" not in default_ranges
    assert config.amoc_reference_sv == 17.0
    ranges = {name: default_ranges[name] for name in names}
    samples = generate_samples(
        config,
        ranges,
        runs=1024,
        seed=123,
        distribution="triangular",
        design="sobol",
        correlated_priors=True,
        science_modes=True,
    )
    for name in names:
        values = np.asarray([sample[name] for sample in samples], dtype=float)
        spec = SCIENCE_PRIOR_SPECS[name]
        assert np.all(values >= spec.lower)
        assert np.all(values <= spec.upper)
        assert np.std(values) > 0.0
    exchange = np.asarray([sample["ocean_heat_exchange_wm2_k"] for sample in samples])
    capacity = np.asarray([sample["deep_ocean_heat_capacity_wyr_m2_k"] for sample in samples])
    assert np.corrcoef(exchange, capacity)[0, 1] > 0.15
    assert all("amoc_reference_sv" not in sample for sample in samples)

def main() -> None:
    tests = [
        test_default_feedback_decomposition,
        test_total_atlantic_heat_transport_definition,
        test_ohue_uses_explicit_ocean_heat_uptake,
        test_grouped_likelihood_outputs,
        test_physical_priors_do_not_duplicate_likelihood_intervals,
        test_parameter_specific_prior_marginals_and_correlations,
    ]
    for test in tests:
        test()
        print(f"PASS: {test.__name__}")
    print("All v2.17.0 calibration-fix tests passed.")


if __name__ == "__main__":
    main()
