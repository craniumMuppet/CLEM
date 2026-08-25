"""Regression tests for the v2.25.2 seasonal Arctic and AMOC corrections."""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from climate_model import MODEL_VERSION, ModelConfig, ProcessClimateModel
from held_out_amoc_validation import annual_mean_frame, historical_external_metrics, hosing_recovery


def test_v2252_physical_defaults_do_not_use_freshwater_compensation() -> None:
    config = ModelConfig()
    assert tuple(map(int, MODEL_VERSION.split("."))) >= (2, 25, 2)
    assert config.seasonal_arctic_enabled
    assert config.hydrological_freshwater_sv_per_k == 0.006
    assert config.greenland_freshwater_sv_per_k == 0.005
    assert config.amoc_temperature_density_coupling == 1.0
    assert config.amoc_convection_density_scale_factor == 4.0
    assert config.amoc_convection_entrainment_feedback == 0.0
    assert config.arctic_ocean_air_exchange_wm2_k == 0.20
    assert config.arctic_moisture_transport_wm2_per_k == 0.22
    assert config.arctic_winter_transport_enhancement == 10.0
    assert config.arctic_open_water_stable_exchange_wm2_k == 0.5
    assert config.arctic_open_water_unstable_exchange_wm2_k == 10.0
    assert config.arctic_open_water_exchange_transition_c == 0.5
    # v2.29.9 reduced this tuning-informed transient-only closure to 0.90.
    assert config.arctic_transient_shortwave_scale == 1.00


def test_unforced_seasonal_arctic_control_is_stable() -> None:
    config = replace(
        ModelConfig(),
        scenario="constant",
        duration_years=300.0,
        record_every_years=100.0,
        auto_initialize_from_1850=False,
    )
    frame = ProcessClimateModel(config).run().dataframe
    final = frame.iloc[-1]
    assert abs(float(final["global_surface_warming_c"])) < 2.0e-5
    assert abs(float(final["arctic_warming_c"])) < 5.0e-4
    assert abs(float(final["amoc_sv"]) - config.amoc_reference_sv) < 1.0e-5
    assert abs(float(final["salt_conservation_error_ppm"])) < 1.0e-8


def test_warm_and_cold_arctic_perturbations_recover() -> None:
    config = replace(
        ModelConfig(),
        scenario="constant",
        duration_years=1.0,
        auto_initialize_from_1850=False,
    )
    for sign in (-1.0, 1.0):
        model = ProcessClimateModel(config)
        mask = model.arctic_module_blend
        model.state.arctic_atlantic_air_anomaly_c += sign * 0.5 * mask
        model.state.arctic_non_atlantic_air_anomaly_c += sign * 0.5 * mask
        model.state.arctic_atlantic_ice_energy_anomaly_wyr_m2 += sign * 0.25 * mask
        model.state.arctic_non_atlantic_ice_energy_anomaly_wyr_m2 += sign * 0.25 * mask
        elapsed = 0.0
        while elapsed < 160.0 - 1.0e-12:
            dt = min(config.dt_years, 160.0 - elapsed)
            model.step(elapsed, dt)
            elapsed += dt
        arctic = model.record(elapsed)["arctic_warming_c"]
        assert abs(arctic) < 0.01
        assert model.state.amoc_sv > 16.9


def test_time_weighted_development_regression_ranges() -> None:
    base = ModelConfig()
    config = replace(
        base,
        start_year=1850.0,
        duration_years=251.0,
        scenario="ssp245",
        record_every_years=base.dt_years,
        auto_initialize_from_1850=False,
    )
    annual = annual_mean_frame(ProcessClimateModel(config).run().dataframe)
    metrics = historical_external_metrics(annual)
    assert 0.95 <= metrics["historical_gmst_2011_2020_c"] <= 1.20
    assert 350.0 <= metrics["historical_ocean_heat_content_change_1971_2018_zj"] <= 500.0
    assert 2.0 <= metrics["historical_arctic_amplification_1979_2021_ratio"] <= 4.5
    assert 15.0 <= metrics["ssp245_amoc_decline_2100_percent"] <= 50.0


def test_transient_hosing_recovers_without_density_memory_feedback() -> None:
    result = hosing_recovery(ModelConfig())
    assert result["amoc_after_40yr_hosing_sv"] < result["initial_amoc_sv"]
    assert result["amoc_after_100yr_recovery_sv"] > result["amoc_after_40yr_hosing_sv"]
    assert result["recovery_percent_of_initial_loss"] >= 80.0


def test_arctic_heat_states_are_finite_and_distinct() -> None:
    config = replace(
        ModelConfig(),
        scenario="ssp245",
        duration_years=180.0,
        record_every_years=1.0,
        auto_initialize_from_1850=False,
    )
    frame = ProcessClimateModel(config).run().dataframe
    final = frame.iloc[-1]
    for key in (
        "arctic_instantaneous_near_surface_air_warming_c",
        "arctic_one_year_low_pass_air_warming_c",
        "arctic_air_heat_content_anomaly_zj",
        "arctic_sea_ice_heat_content_anomaly_zj",
        "total_resolved_heat_content_anomaly_zj",
    ):
        assert np.isfinite(float(final[key]))
    assert final["arctic_near_surface_air_warming_c"] > final["arctic_blended_surface_state_warming_c"]
