"""Regression coverage for the v2.28.0 Arctic and Greenland structural rebuild."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np

from climate_model import (
    MODEL_VERSION,
    SV_TO_GT_PER_YEAR,
    ModelConfig,
    ProcessClimateModel,
    build_parser,
    config_from_args,
)
from sea_ice_observation import raw_northern_ice_area_million_km2


def _control_model(**overrides: object) -> ProcessClimateModel:
    config = replace(
        ModelConfig(),
        scenario="constant",
        duration_years=1.0,
        auto_initialize_from_1850=False,
        **overrides,
    )
    return ProcessClimateModel(config)


def test_v227_defaults_keep_freshwater_rates_and_use_structural_amoc_settings() -> None:
    config = ModelConfig()
    assert MODEL_VERSION == "2.29.29"
    assert config.hydrological_freshwater_sv_per_k == 0.006
    assert config.greenland_freshwater_sv_per_k == 0.005
    assert config.greenland_surface_mass_balance_enabled
    assert config.greenland_dynamic_discharge_fraction == 0.10
    assert config.greenland_pdd_melt_factor_gt_per_degree_day == 0.38
    assert config.greenland_max_freshwater_sv == 0.10
    assert config.amoc_temperature_density_coupling == 1.0
    assert config.amoc_stratification_saturation_c == 4.0
    assert config.amoc_convection_temperature_density_coupling == 0.8
    assert config.amoc_density_transport_exponent == 1.5
    assert config.amoc_convection_recovery_years == 80.0
    assert config.amoc_convection_density_scale_factor == 1.0
    assert config.amoc_reference_density_driver == 4.34e-4
    assert config.ocean_heat_exchange_wm2_k == 1.45
    assert config.arctic_winter_transport_enhancement == 19.0
    assert config.arctic_open_water_stable_exchange_wm2_k == 0.5
    assert config.arctic_open_water_unstable_exchange_wm2_k == 10.0
    assert config.arctic_open_water_exchange_transition_c == 0.5
    cli_config = config_from_args(build_parser().parse_args([]))
    assert cli_config.amoc_reference_density_driver == config.amoc_reference_density_driver


def test_arctic_ocean_baseline_is_freezing_bounded_and_global_mean_is_preserved() -> None:
    model = _control_model()
    mask = model.grid.lat >= model.config.arctic_module_full_latitude_deg
    assert np.allclose(
        model.baseline_ocean_c[mask],
        model.config.arctic_interface_freezing_temperature_c,
        atol=1.0e-12,
    )
    assert abs(float(np.sum(model.baseline_map_c * model.grid.map_area_weights)) - 14.0) < 1.0e-12
    # The corrected ocean climatology is independent of the much colder land field.
    assert float(np.mean(model.baseline_land_c[mask])) < float(np.mean(model.baseline_ocean_c[mask])) - 5.0


def test_reference_ice_cycle_is_periodic_and_energy_budget_generated() -> None:
    model = _control_model()
    assert model.arctic_reference_periodic_closure_wyr_m2 < 1.0e-8
    assert model.arctic_reference_spinup_convergence_wyr_m2 < 1.0e-8
    assert model.arctic_reference_spinup_years_completed <= model.config.arctic_reference_spinup_years

    mask = model.grid.lat >= 66.0
    weights = model.grid.band_area_weights[mask] * model.grid.ocean_fraction[mask]
    monthly = []
    monthly_native_area = []
    for month in range(1, 13):
        state = model._arctic_reference_state((month - 0.5) / 12.0)
        monthly.append(float(np.average(state["ice_fraction"][mask], weights=weights)))
        monthly_native_area.append(
            raw_northern_ice_area_million_km2(
                state["atlantic_effective_ice_fraction"],
                state["non_atlantic_effective_ice_fraction"],
                model.grid.lat,
                model.grid.atlantic_ocean_fraction_map,
                model.grid.ocean_fraction_map,
                model.grid.map_area_weights,
            )
        )
        atlantic_fraction = np.divide(
            model.grid.atlantic_ocean_fraction,
            model.grid.ocean_fraction,
            out=np.zeros_like(model.grid.ocean_fraction),
            where=model.grid.ocean_fraction > 1.0e-12,
        )
        expected_aggregate_interface = (
            atlantic_fraction * state["atlantic_interface_temperature_c"]
            + (1.0 - atlantic_fraction) * state["non_atlantic_interface_temperature_c"]
        )
        assert np.allclose(
            state["interface_temperature_c"], expected_aggregate_interface, atol=1.0e-10
        )
        for prefix in ("atlantic", "non_atlantic"):
            expected_sector_interface = (
                state[f"{prefix}_ice_fraction"]
                * model.config.arctic_interface_freezing_temperature_c
                + (1.0 - state[f"{prefix}_ice_fraction"])
                * state[f"{prefix}_open_water_temperature_c"]
            )
            # Reference values are linearly interpolated between stored phases;
            # the nonlinear product is therefore equal within interpolation error.
            assert np.allclose(
                state[f"{prefix}_interface_temperature_c"],
                expected_sector_interface,
                atol=5.0e-4,
            )
    assert 0.0 < min(monthly) < max(monthly) <= 1.0
    assert max(monthly) - min(monthly) > 0.20
    assert int(np.argmin(monthly_native_area)) + 1 in (8, 9, 10)
    assert 12.0 <= monthly_native_area[2] <= 17.0
    assert 3.0 <= monthly_native_area[8] <= 9.0
    assert monthly_native_area[8] < monthly_native_area[2]


def test_greenland_surface_mass_balance_is_zero_in_control_and_signed_under_anomalies() -> None:
    model = _control_model()
    phases = np.arange(48, dtype=float) / 48.0
    control = np.array(
        [
            model._greenland_surface_mass_balance(model.state, 0.0, float(phase))[
                "surface_freshwater_sv"
            ]
            for phase in phases
        ]
    )
    assert np.max(np.abs(control)) < 1.0e-14

    warm = model._greenland_annual_mean_surface_flux_sv(model.state, 2.0)
    cool = model._greenland_annual_mean_surface_flux_sv(model.state, -2.0)
    assert warm > 0.0
    assert cool < 0.0


def test_greenland_dynamic_discharge_is_separate_from_surface_mass_balance() -> None:
    model = _control_model()
    state = model.state.copy()
    target_temperature = 2.0
    target = (
        model.config.greenland_freshwater_sv_per_k
        * model.config.greenland_dynamic_discharge_fraction
        * target_temperature
    )
    # Force the temperature-driver helper to isolate the target calculation.
    original = model._freshwater_temperature_drivers
    model._freshwater_temperature_drivers = lambda *_args, **_kwargs: (0.0, target_temperature)  # type: ignore[method-assign]
    try:
        _, surface_plus_dynamic, diagnosed_target = model._freshwater_components(
            state, 0.0, 0.5
        )
    finally:
        model._freshwater_temperature_drivers = original  # type: ignore[method-assign]
    assert abs(diagnosed_target - target) < 1.0e-12
    assert surface_plus_dynamic != diagnosed_target



def test_greenland_combined_diagnostic_obeys_total_rate_and_reservoir_caps() -> None:
    model = _control_model()
    state = model.state.copy()
    state.greenland_freshwater_sv = 0.020
    annual = model._greenland_annual_mean_applied_flux_sv(
        state, state.greenland_freshwater_sv, 12.0
    )
    assert 0.0 <= annual <= model.config.greenland_max_freshwater_sv

    state.greenland_remaining_ice_gt = 0.000125 * SV_TO_GT_PER_YEAR
    reservoir_limited = model._greenland_annual_mean_applied_flux_sv(
        state, state.greenland_freshwater_sv, 12.0
    )
    assert reservoir_limited <= 0.000125 + 1.0e-12

def test_release_metadata_and_normal_interfaces_are_synchronized() -> None:
    root = Path(__file__).resolve().parents[1]
    assert 'version = "2.29.29"' in (root / "pyproject.toml").read_text(encoding="utf-8")
    assert '"model_version": "2.29.29"' in (root / "dependency_integrity.lock.json").read_text(encoding="utf-8")
    for filename in ("app.py", "climate_model_gui.py"):
        text = (root / filename).read_text(encoding="utf-8")
        assert "2.26.0" not in text
    readme = (root / "README.md").read_text(encoding="utf-8")
    constraints = (root / "SCIENTIFIC_CONSTRAINTS.md").read_text(encoding="utf-8")
    assert "greenland_freshwater_sv_per_k 0.004 0.020" not in readme
    assert "0.004–0.020 Sv/K" not in constraints


def test_desktop_gui_and_monte_carlo_expose_structural_controls() -> None:
    from climate_model_gui import DEFAULTS, build_cli_command
    from monte_carlo import MONTE_CARLO_PHYSICAL_PARAMETERS, SCIENCE_PRIOR_SPECS

    command = build_cli_command(DEFAULTS)
    for flag in (
        "--arctic-winter-transport-enhancement",
        "--arctic-open-water-stable-exchange",
        "--arctic-open-water-unstable-exchange",
        "--arctic-open-water-exchange-transition",
        "--arctic-transient-shortwave-scale",
        "--arctic-basal-ocean-exchange",
        "--arctic-open-water-ocean-exchange",
        "--arctic-reference-ocean-heat-capacity",
        "--arctic-reference-ocean-restoring",
        "--greenland-dynamic-discharge-fraction",
        "--greenland-pdd-melt-factor",
        "--greenland-meltwater-retention-fraction",
    ):
        assert flag in command
    disabled = dict(DEFAULTS)
    disabled["greenland_surface_mass_balance_enabled"] = False
    assert "--disable-greenland-smb" in build_cli_command(disabled)

    for key in (
        "arctic_winter_transport_enhancement",
        "arctic_open_water_stable_exchange_wm2_k",
        "arctic_open_water_unstable_exchange_wm2_k",
        "arctic_open_water_exchange_transition_c",
        "arctic_transient_shortwave_scale",
        "arctic_basal_ocean_exchange_wm2_k",
        "arctic_open_water_ocean_exchange_wm2_k",
        "arctic_reference_ocean_heat_capacity_wyr_m2_k",
        "arctic_reference_ocean_restoring_wm2_k",
        "greenland_dynamic_discharge_fraction",
        "greenland_pdd_melt_factor_gt_per_degree_day",
        "greenland_meltwater_retention_fraction",
    ):
        assert key in MONTE_CARLO_PHYSICAL_PARAMETERS
        assert key in SCIENCE_PRIOR_SPECS
