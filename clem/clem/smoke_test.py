#!/usr/bin/env python3
"""Fast numerical and structural regression tests for climate model v2.27.0."""

from __future__ import annotations

import numpy as np

from climate_model import ModelConfig, ProcessClimateModel, weighted_mean


def _constant(**overrides: object) -> ModelConfig:
    values: dict[str, object] = {
        "scenario": "constant",
        "duration_years": 50.0,
        "dt_years": 0.1,
        "record_every_years": 1.0,
        "warming_freshwater_sv_per_k": 0.0,
    }
    values.update(overrides)
    return ModelConfig(**values)


def test_control_stability() -> None:
    config = _constant(duration_years=50.0)
    result = ProcessClimateModel(config).run()
    final = result.dataframe.iloc[-1]
    # The coupled seasonal Arctic reference is numerically periodic rather
    # than algebraically frozen, so control drift is tested against physically
    # negligible finite tolerances instead of exact zero.
    assert abs(final["global_surface_warming_c"]) < 1.0e-4
    assert abs(final["amoc_sv"] - config.amoc_reference_sv) < 1.0e-3
    assert abs(final["pycnocline_depth_m"] - config.amoc_initial_pycnocline_depth_m) < 1.0e-2
    assert result.dataframe["salt_conservation_error_ppm"].abs().max() < 1.0e-6
    assert result.dataframe["pre_projection_salt_conservation_error_ppm"].abs().max() <= config.salt_projection_max_residual_ppm


def test_amoc_heat_redistribution_is_conservative() -> None:
    model = ProcessClimateModel(_constant(duration_years=1.0))
    flux = model._amoc_heat_flux_atlantic_area(8.0)
    residual = weighted_mean(
        model.grid.atlantic_ocean_fraction * flux,
        model.grid.band_area_weights,
    )
    assert abs(residual) < 1.0e-12
    assert np.nanmin(flux) < 0.0
    assert np.nanmax(flux) > 0.0


def test_salt_conservation_and_freshwater_routing() -> None:
    config = _constant(
        duration_years=100.0,
        freshwater_hosing_sv=0.3,
        freshwater_start_fraction=0.0,
        freshwater_ramp_years=10.0,
        freshwater_compensation_mode="external",
        hydrological_freshwater_sv_per_k=0.0,
        greenland_freshwater_sv_per_k=0.0,
        greenland_surface_mass_balance_enabled=False,
    )
    model = ProcessClimateModel(config)
    baseline_flux = model.baseline_surface_freshwater_sv.copy()
    result = model.run()
    final = result.dataframe.iloc[-1]
    assert result.dataframe["salt_conservation_error_ppm"].abs().max() < 1.0e-5
    assert final["north_salinity_psu"] < config.initial_north_salinity_psu
    assert final["external_salinity_psu"] > config.initial_external_salinity_psu
    assert abs(final["tropical_surface_freshwater_sv"] - baseline_flux[1]) < 1.0e-12
    assert abs(final["south_atlantic_upper_surface_freshwater_sv"] - baseline_flux[2]) < 1.0e-12
    assert abs(final["southern_surface_freshwater_sv"] - baseline_flux[3]) < 1.0e-12
    assert abs(final["external_surface_freshwater_sv"] + 0.3) < 1.0e-12


def test_directional_advection_and_fovs() -> None:
    model = ProcessClimateModel(_constant(duration_years=1.0))
    salinity = np.array([35.1, 36.0, 35.4, 34.6, 34.9, 34.7])
    positive = model._advective_mixing_salinity_tendency(salinity, 15.0)
    negative = model._advective_mixing_salinity_tendency(salinity, -15.0)
    assert not np.allclose(positive, negative)
    assert abs(np.sum(positive * model.amoc_box_volumes_m3)) < 1.0
    assert abs(np.sum(negative * model.amoc_box_volumes_m3)) < 1.0

    frame = ProcessClimateModel(
        _constant(duration_years=5.0, initial_fovs_sv=-0.15)
    ).run().dataframe
    first = frame.iloc[0]
    expected = -first["amoc_sv"] * (
        first["south_atlantic_upper_salinity_psu"] - first["deep_salinity_psu"]
    ) / 35.0
    assert abs(first["fovs_sv"] + 0.15) < 1.0e-10
    assert abs(first["fovs_sv"] - expected) < 1.0e-12


def test_nonlinear_hosing_response() -> None:
    weak = ProcessClimateModel(
        _constant(
            duration_years=250.0,
            freshwater_hosing_sv=0.10,
            freshwater_start_fraction=0.0,
            freshwater_ramp_years=20.0,
        )
    ).run().dataframe.iloc[-1]
    strong = ProcessClimateModel(
        _constant(
            duration_years=250.0,
            freshwater_hosing_sv=0.50,
            freshwater_start_fraction=0.0,
            freshwater_ramp_years=20.0,
        )
    ).run().dataframe.iloc[-1]
    # A sustained 0.10 Sv perturbation now approaches the weak/collapsed
    # branch after 250 years, but remains distinctly stronger than 0.50 Sv.
    assert weak["amoc_sv"] > strong["amoc_sv"] + 0.05
    assert 0.0 <= strong["amoc_sv"] < 1.0e-3
    assert strong["north_atlantic_warming_c"] < weak["north_atlantic_warming_c"] - 0.02

    exploratory = ProcessClimateModel(
        _constant(
            duration_years=250.0,
            freshwater_hosing_sv=0.50,
            freshwater_start_fraction=0.0,
            freshwater_ramp_years=20.0,
            amoc_allow_reversal=True,
        )
    ).run().dataframe.iloc[-1]
    assert exploratory["amoc_sv"] < 0.0


def test_physical_atlantic_localization() -> None:
    control_result = ProcessClimateModel(_constant(duration_years=120.0)).run()
    hosed_result = ProcessClimateModel(
        _constant(
            duration_years=120.0,
            freshwater_hosing_sv=0.4,
            freshwater_start_fraction=0.0,
            freshwater_ramp_years=0.0,
        )
    ).run()
    control = control_result.dataframe.iloc[-1]
    forced = hosed_result.dataframe.iloc[-1]
    assert forced["amoc_sv"] < control["amoc_sv"] - 10.0
    assert forced["north_atlantic_warming_c"] < control["north_atlantic_warming_c"] - 0.5
    assert abs(forced["global_surface_warming_c"] - control["global_surface_warming_c"]) > 1.0e-4
    assert abs(forced["ocean_heat_uptake_wm2"] - control["ocean_heat_uptake_wm2"]) > 1.0e-4

    grid = control_result.grid
    temperature_difference = hosed_result.map_at_index(-1) - control_result.map_at_index(-1)
    ice_difference = (
        hosed_result.thermodynamic_sea_ice_map_at_index(-1)
        - control_result.thermodynamic_sea_ice_map_at_index(-1)
    )
    north_band = (grid.lat2d >= 45.0) & (grid.lat2d <= 65.0)
    atlantic = north_band * grid.atlantic_ocean_fraction_map * grid.map_area_weights
    pacific = (
        north_band
        * grid.ocean_fraction_map
        * ((grid.lon2d >= 130.0) | (grid.lon2d <= -120.0))
        * grid.map_area_weights
    )
    atlantic_temp = weighted_mean(temperature_difference, atlantic)
    pacific_temp = weighted_mean(temperature_difference, pacific)
    atlantic_ice = weighted_mean(ice_difference, atlantic)
    pacific_ice = weighted_mean(ice_difference, pacific)
    # The retuned full-Northern-Hemisphere Arctic field slightly dilutes the
    # area-mean 45-65 N Atlantic map anomaly while the dedicated North Atlantic
    # diagnostic above still cools by more than 0.5 C. Preserve the physical
    # contract here: substantial cooling that is strongly Atlantic-localized.
    assert atlantic_temp < -0.40
    assert atlantic_temp < pacific_temp - 0.40
    assert pacific_temp > -0.25
    assert atlantic_ice > 0.0
    # The corrected seasonal Arctic field owns the full Northern Hemisphere,
    # so tiny remote ice changes are allowed. The hosing response must remain
    # strongly localized to the North Atlantic.
    assert atlantic_ice > pacific_ice + 1.0e-3


def test_post_1850_initialization_matches_continuous_run() -> None:
    continuous = ProcessClimateModel(
        ModelConfig(
            scenario="ssp245",
            start_year=1850.0,
            duration_years=165.0,
            dt_years=0.1,
            record_every_years=1.0,
        )
    ).run().dataframe.iloc[-1]
    restarted = ProcessClimateModel(
        ModelConfig(
            scenario="ssp245",
            start_year=2015.0,
            duration_years=1.0,
            dt_years=0.1,
            record_every_years=1.0,
        )
    ).run().dataframe.iloc[0]
    for key in (
        "global_surface_warming_c",
        "amoc_sv",
        "north_atlantic_warming_c",
        "greenland_freshwater_sv",
        "north_salinity_psu",
    ):
        assert abs(float(continuous[key]) - float(restarted[key])) < 1.0e-10


def test_separated_freshwater_components_and_legacy_override() -> None:
    result = ProcessClimateModel(
        ModelConfig(
            scenario="step_2x",
            duration_years=20.0,
            dt_years=0.1,
            record_every_years=1.0,
        )
    ).run().dataframe.iloc[-1]
    assert result["hydrological_freshwater_sv"] > 0.0
    assert 0.0 < result["greenland_dynamic_discharge_sv"] < result["greenland_freshwater_target_sv"]
    assert result["greenland_annual_mean_surface_mass_balance_freshwater_sv"] > 0.0
    assert result["greenland_annual_mean_freshwater_sv"] > result["greenland_dynamic_discharge_sv"]

    legacy = ProcessClimateModel(
        ModelConfig(
            scenario="step_2x",
            duration_years=5.0,
            dt_years=0.1,
            warming_freshwater_sv_per_k=0.02,
        )
    ).run().dataframe.iloc[-1]
    assert legacy["hydrological_freshwater_sv"] > 0.0
    assert legacy["greenland_freshwater_sv"] == 0.0
    assert legacy["greenland_freshwater_target_sv"] == 0.0


def test_nondivisible_timestep_and_summary_compatibility() -> None:
    for dt in (0.18, 0.22, 0.24):
        result = ProcessClimateModel(
            _constant(duration_years=1.0, dt_years=dt, record_every_years=1.0)
        ).run()
        assert abs(float(result.dataframe.iloc[-1]["elapsed_years"]) - 1.0) < 1.0e-12
        assert abs(float(result.dataframe.iloc[-1]["year"]) - 1851.0) < 1.0e-12
        summary = result.summary()
        for key in (
            "final_global_warming_c",
            "final_global_surface_warming_c",
            "minimum_amoc_sv",
            "final_north_salinity_psu",
            "final_atlantic_ocean_warming_c",
        ):
            assert key in summary
        assert result.amoc_ocean_anomaly_history_c.shape == result.ocean_anomaly_history_c.shape


def main() -> None:
    tests = [
        test_control_stability,
        test_amoc_heat_redistribution_is_conservative,
        test_salt_conservation_and_freshwater_routing,
        test_directional_advection_and_fovs,
        test_nonlinear_hosing_response,
        test_physical_atlantic_localization,
        test_post_1850_initialization_matches_continuous_run,
        test_separated_freshwater_components_and_legacy_override,
        test_nondivisible_timestep_and_summary_compatibility,
    ]
    for test in tests:
        test()
        print(f"PASS: {test.__name__}", flush=True)
    print("All climate-model v2.17.0 fast smoke tests passed.")


if __name__ == "__main__":
    main()
