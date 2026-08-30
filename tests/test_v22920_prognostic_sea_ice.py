"""Regression checks for the v2.29.20 prognostic sea-ice rebuild."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from climate_model import (
    MODEL_VERSION,
    ModelConfig,
    ProcessClimateModel,
    build_parser,
    config_from_args,
)
from climate_model_gui import DEFAULTS
from monte_carlo import PHYSICAL_AMOC_PRIORS


def small_model(**overrides: object) -> ProcessClimateModel:
    config = replace(
        ModelConfig(),
        start_year=1850.0,
        duration_years=0.1,
        dt_years=0.05,
        record_every_years=0.05,
        resolution_deg=10.0,
        auto_initialize_from_1850=False,
        **overrides,
    )
    return ProcessClimateModel(config)


def test_version_and_constrained_production_defaults() -> None:
    config = ModelConfig()
    assert MODEL_VERSION == "2.29.28"
    assert config.arctic_winter_transport_enhancement == pytest.approx(19.0)
    assert config.arctic_winter_transport_enhancement <= 25.0
    assert config.arctic_greenland_marine_influence == pytest.approx(0.10)
    assert config.arctic_greenland_marine_influence <= 0.25
    assert 0.05 <= config.arctic_new_ice_local_thickness_m <= 0.30
    assert config.arctic_winter_lead_closure_fraction == 0.0


def test_cli_defaults_match_validated_model_defaults() -> None:
    args = build_parser().parse_args([])
    cli_config = config_from_args(args)
    defaults = ModelConfig()
    assert cli_config.greenland_dynamic_discharge_fraction == pytest.approx(
        defaults.greenland_dynamic_discharge_fraction
    )
    assert cli_config.greenland_pdd_melt_factor_gt_per_degree_day == pytest.approx(
        defaults.greenland_pdd_melt_factor_gt_per_degree_day
    )
    assert cli_config.amoc_stratification_saturation_c == pytest.approx(
        defaults.amoc_stratification_saturation_c
    )


def test_desktop_gui_and_monte_carlo_defaults_match_validated_greenland_physics() -> None:
    defaults = ModelConfig()
    assert float(DEFAULTS["greenland_dynamic_discharge_fraction"]) == pytest.approx(
        defaults.greenland_dynamic_discharge_fraction
    )
    assert float(DEFAULTS["greenland_pdd_melt_factor_gt_per_degree_day"]) == pytest.approx(
        defaults.greenland_pdd_melt_factor_gt_per_degree_day
    )
    dynamic_prior = PHYSICAL_AMOC_PRIORS["greenland_dynamic_discharge_fraction"]
    assert dynamic_prior.lower <= defaults.greenland_dynamic_discharge_fraction <= dynamic_prior.upper
    assert dynamic_prior.mode == pytest.approx(defaults.greenland_dynamic_discharge_fraction)
    pdd_prior = PHYSICAL_AMOC_PRIORS["greenland_pdd_melt_factor_gt_per_degree_day"]
    assert pdd_prior.lower <= defaults.greenland_pdd_melt_factor_gt_per_degree_day <= pdd_prior.upper
    assert pdd_prior.mode == pytest.approx(defaults.greenland_pdd_melt_factor_gt_per_degree_day)


def test_release_configuration_rejects_old_high_transport_regime() -> None:
    invalid = replace(
        ModelConfig(), arctic_winter_transport_enhancement=88.0
    )
    with pytest.raises(ValueError, match="cannot exceed 25"):
        invalid.validate()
    exploratory = replace(
        ModelConfig(),
        unsafe_debug_mode=True,
        arctic_winter_transport_enhancement=88.0,
    )
    exploratory.validate()
    assert exploratory.arctic_winter_transport_enhancement == 88.0


def test_state_copy_preserves_independent_concentration_arrays() -> None:
    model = small_model()
    model.state.arctic_atlantic_ice_concentration_anomaly[:] = 0.123
    model.state.arctic_non_atlantic_ice_concentration_anomaly[:] = -0.045
    copied = model.state.copy()
    assert np.all(copied.arctic_atlantic_ice_concentration_anomaly == 0.123)
    assert np.all(copied.arctic_non_atlantic_ice_concentration_anomaly == -0.045)
    copied.arctic_atlantic_ice_concentration_anomaly[:] = 0.0
    assert np.all(model.state.arctic_atlantic_ice_concentration_anomaly == 0.123)


def test_complete_loss_and_thin_ice_recovery_are_physical() -> None:
    model = small_model()
    shape = model.grid.lat.shape
    zeros = np.zeros(shape)
    ones = np.ones(shape)
    warm = np.full(shape, 3.0)
    cold = np.full(shape, -20.0)
    freezing_ocean = np.full(
        shape, model.config.arctic_interface_freezing_temperature_c
    )

    lost = model._advance_arctic_ice_concentration(
        np.full(shape, 0.70),
        np.full(shape, 1.0),
        zeros,
        air_temperature_c=warm,
        ocean_temperature_c=np.full(shape, 1.0),
        darkness=zeros,
        dt_years=0.05,
    )
    recovered = model._advance_arctic_ice_concentration(
        zeros,
        zeros,
        np.full(shape, 0.05),
        air_temperature_c=cold,
        ocean_temperature_c=freezing_ocean,
        darkness=ones,
        dt_years=0.05,
    )

    assert np.max(np.abs(lost)) <= 1.0e-12
    assert np.all((recovered > 0.0) & (recovered < 1.0))
    local_thickness = 0.05 / recovered
    assert np.all(local_thickness >= 0.05)
    assert np.all(local_thickness <= 0.30)


def test_area_volume_identity_and_low_volume_support_cap() -> None:
    model = small_model()
    shape = model.grid.lat.shape
    equivalent = np.full(shape, 0.05)
    energy = -model.arctic_latent_energy_per_m_wyr_m2 * equivalent
    concentration, recovered_equivalent, local = (
        model._arctic_state_from_energy_and_concentration(energy, np.ones(shape))
    )
    assert np.all(concentration < 1.0)
    assert np.max(np.abs(local * concentration - recovered_equivalent)) <= 1.0e-12
    assert np.all(recovered_equivalent >= 0.0)


def test_ridging_reduces_area_without_changing_supplied_volume() -> None:
    model = small_model()
    shape = model.grid.lat.shape
    volume = np.full(shape, 1.5)
    concentration = model._advance_arctic_ice_concentration(
        np.full(shape, 0.95),
        volume,
        volume,
        air_temperature_c=np.full(shape, -20.0),
        ocean_temperature_c=np.full(
            shape, model.config.arctic_interface_freezing_temperature_c
        ),
        darkness=np.ones(shape),
        dt_years=0.05,
    )
    assert np.all(concentration < 0.95)
    assert np.all(concentration >= 0.0)
    local = volume / concentration
    assert np.max(np.abs(local * concentration - volume)) <= 1.0e-12


def test_greenland_driver_ignores_raw_arctic_air_spike() -> None:
    model = small_model()
    state = model.state.copy()
    state.land_anomaly_c[:] = 0.0
    state.atlantic_ocean_anomaly_c[:] = 0.0
    state.non_atlantic_ocean_anomaly_c[:] = 0.0
    state.arctic_atlantic_air_anomaly_c[:] = 100.0
    state.arctic_non_atlantic_air_anomaly_c[:] = 100.0
    state.arctic_atlantic_air_low_pass_c[:] = 2.0
    state.arctic_non_atlantic_air_low_pass_c[:] = 2.0
    driver = model._greenland_specific_warming_c(state)
    assert driver == pytest.approx(0.2, abs=0.02)
    assert driver < 1.0



def test_mechanical_spreading_precedes_separate_local_thickness_emergency_safeguard() -> None:
    model = small_model()
    shape = model.grid.lat.shape
    equivalent = np.full(shape, 1.0)
    energy = -model.arctic_latent_energy_per_m_wyr_m2 * equivalent
    spread_concentration, spread_equivalent, spread_local = (
        model._arctic_state_from_energy_and_concentration(
            energy, np.full(shape, 1.0e-8)
        )
    )
    np.testing.assert_allclose(spread_local, 12.0, rtol=0.0, atol=1e-12)
    np.testing.assert_allclose(
        spread_concentration * spread_local,
        spread_equivalent,
        rtol=0.0,
        atol=1e-12,
    )
    with pytest.raises(FloatingPointError, match="local ice thickness"):
        model._assert_arctic_local_thickness_safe(
            np.full(shape, 501.0), context="emergency-regression"
        )
    # A physically admissible concentration preserves the latent-energy volume.
    concentration, recovered_equivalent, local = model._arctic_state_from_energy_and_concentration(
        energy, np.full(shape, 0.5)
    )
    np.testing.assert_allclose(recovered_equivalent, equivalent, rtol=0.0, atol=1e-12)
    np.testing.assert_allclose(concentration * local, recovered_equivalent, rtol=0.0, atol=1e-12)


def test_mechanical_spreading_limit_fails_when_full_cover_cannot_hold_volume() -> None:
    model = small_model()
    shape = model.grid.lat.shape
    equivalent = np.full(
        shape, model.config.arctic_ice_mechanical_max_local_thickness_m + 0.1
    )
    energy = -model.arctic_latent_energy_per_m_wyr_m2 * equivalent
    with pytest.raises(FloatingPointError, match="mechanical-spreading full-cover limit"):
        model._arctic_state_from_energy_and_concentration(energy, np.ones(shape))

def test_explicit_greenland_smb_uses_modest_dynamic_discharge_default() -> None:
    config = ModelConfig()
    assert config.greenland_surface_mass_balance_enabled is True
    assert config.greenland_dynamic_discharge_fraction == pytest.approx(0.10)
    assert config.greenland_seasonal_runoff_fraction == pytest.approx(0.05)
