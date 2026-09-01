"""Regression tests for the v2.29.2 Arctic phase-consistency maintenance release."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from climate_model import (
    ARCTIC_MINIMUM_SENSIBLE_OPEN_FRACTION,
    MODEL_VERSION,
    ModelConfig,
    ProcessClimateModel,
    build_parser,
    weighted_mean,
    config_from_args,
)


def _model(**changes: object) -> ProcessClimateModel:
    config = replace(
        ModelConfig(),
        scenario="constant",
        duration_years=1.0,
        record_every_years=1.0,
        auto_initialize_from_1850=False,
        resolution_deg=10.0,
        **changes,
    )
    return ProcessClimateModel(config)




def _full_cover_phase_model() -> ProcessClimateModel:
    """Use a structurally valid full-cover state for phase-remapping tests.

    These tests target the generic normalization operator at exact full cover,
    so the emergency thickness guard is placed at the representative full-cover
    thickness for this isolated compatibility case.
    """
    config = ModelConfig()
    return _model(
        arctic_max_equivalent_thickness_m=(
            config.arctic_full_cover_equivalent_thickness_m
        )
    )

def _ice_energy_for_fraction(model: ProcessClimateModel, fraction: float) -> np.ndarray:
    fraction = float(np.clip(fraction, 0.0, 1.0))
    equivalent_thickness = (
        model.config.arctic_full_cover_equivalent_thickness_m
        * (
            1.0
            - (1.0 - fraction)
            ** (1.0 / model.config.arctic_ice_concentration_exponent)
        )
    )
    return np.array(
        [-model.arctic_latent_energy_per_m_wyr_m2 * equivalent_thickness],
        dtype=float,
    )


def _open_heat_for_temperature(
    model: ProcessClimateModel,
    open_fraction: float,
    temperature_c: float,
) -> np.ndarray:
    delta = temperature_c - model.config.arctic_interface_freezing_temperature_c
    return np.array(
        [
            max(open_fraction, 0.0)
            * model.config.arctic_interface_heat_capacity_wyr_m2_k
            * max(delta, 0.0)
        ],
        dtype=float,
    )


def test_v2292_version_and_positive_coupling_validation() -> None:
    assert MODEL_VERSION == "2.29.29"
    config = ModelConfig()
    config.validate()
    assert config.arctic_lateral_ocean_heat_transport_wm2_per_ice_fraction == pytest.approx(25.0)
    with pytest.raises(ValueError, match="must be positive"):
        replace(config, arctic_open_water_ocean_exchange_wm2_k=0.0).validate()
    replace(
        config,
        arctic_lateral_ocean_heat_transport_wm2_per_ice_fraction=0.0,
    ).validate()
    with pytest.raises(ValueError, match="cannot be negative"):
        replace(
            config,
            arctic_lateral_ocean_heat_transport_wm2_per_ice_fraction=-0.1,
        ).validate()


def test_freeze_up_remaps_open_water_heat_conservatively() -> None:
    model = _full_cover_phase_model()
    previous_open = 0.50
    new_open = 0.20
    previous_ice = _ice_energy_for_fraction(model, 1.0 - previous_open)
    new_ice = _ice_energy_for_fraction(model, 1.0 - new_open)
    open_heat = _open_heat_for_temperature(model, previous_open, 3.0)
    before = new_ice + open_heat

    ice_after, open_after, ocean_transfer = model._normalize_arctic_surface_reservoirs(
        new_ice,
        open_heat,
        previous_ice_energy_wyr_m2=previous_ice,
    )

    assert np.allclose(ice_after + open_after + ocean_transfer, before, atol=1.0e-12)
    assert open_after[0] == pytest.approx(open_heat[0] * new_open / previous_open)
    diagnosed = model._arctic_open_water_temperature(open_after, np.array([new_open]))
    assert diagnosed[0] == pytest.approx(3.0)
    assert ocean_transfer[0] > 0.0


def test_complete_ice_cover_has_no_dormant_open_water_heat() -> None:
    model = _full_cover_phase_model()
    previous_ice = _ice_energy_for_fraction(model, 0.5)
    full_ice = _ice_energy_for_fraction(model, 1.0)
    open_heat = _open_heat_for_temperature(model, 0.5, 5.0)
    ice_after, open_after, ocean_transfer = model._normalize_arctic_surface_reservoirs(
        full_ice,
        open_heat,
        previous_ice_energy_wyr_m2=previous_ice,
    )
    assert open_after[0] == 0.0
    assert ocean_transfer[0] == pytest.approx(open_heat[0])
    assert np.allclose(ice_after + open_after + ocean_transfer, full_ice + open_heat)


def test_subgrid_opening_is_thermodynamically_closed() -> None:
    model = _full_cover_phase_model()
    subgrid_open = 0.5 * ARCTIC_MINIMUM_SENSIBLE_OPEN_FRACTION
    previous_ice = _ice_energy_for_fraction(model, 0.5)
    new_ice = _ice_energy_for_fraction(model, 1.0 - subgrid_open)
    open_heat = _open_heat_for_temperature(model, 0.5, 5.0)
    _, open_after, ocean_transfer = model._normalize_arctic_surface_reservoirs(
        new_ice,
        open_heat,
        previous_ice_energy_wyr_m2=previous_ice,
    )
    assert open_after[0] == 0.0
    assert ocean_transfer[0] > 0.0


def test_reference_ocean_targets_are_independent_parameters() -> None:
    low = _model(arctic_open_water_ocean_exchange_wm2_k=0.5)
    high = _model(arctic_open_water_ocean_exchange_wm2_k=3.0)
    for model in (low, high):
        assert np.allclose(
            model.arctic_reference_atlantic_ocean_target_temperature_c,
            model.config.arctic_atlantic_reference_ocean_temperature_c,
        )
        assert np.allclose(
            model.arctic_reference_non_atlantic_ocean_target_temperature_c,
            model.config.arctic_non_atlantic_reference_ocean_temperature_c,
        )


def test_arctic_open_water_temperature_is_timestep_convergent() -> None:
    maxima: list[float] = []
    for timestep in (0.1, 0.05, 0.025):
        config = replace(
            ModelConfig(),
            scenario="ssp245",
            start_year=1850.0,
            duration_years=40.0,
            dt_years=timestep,
            record_every_years=1.0,
            resolution_deg=10.0,
            auto_initialize_from_1850=False,
        )
        result = ProcessClimateModel(config).run()
        summary = result.summary()
        maxima.append(summary["maximum_arctic_open_water_temperature_c_at_5pct_open"])
        assert summary["maximum_dormant_arctic_open_water_heat_wyr_m2"] <= 1.0e-12
    assert max(maxima) < 10.0
    assert max(maxima) - min(maxima) < 1.0



def test_lateral_excess_ice_heat_is_sourced_conservatively() -> None:
    model = _model()
    blend = model.arctic_module_blend
    atlantic_convergence = 3.0 * blend
    non_atlantic_convergence = 1.5 * blend
    sink = model._arctic_lateral_ocean_source_sink_wm2(
        atlantic_convergence, non_atlantic_convergence
    )
    supplied = weighted_mean(
        model.grid.atlantic_ocean_fraction * atlantic_convergence
        + model.non_atlantic_ocean_fraction * non_atlantic_convergence,
        model.grid.band_area_weights,
    )
    removed = weighted_mean(
        model.grid.ocean_fraction * (1.0 - blend) * sink,
        model.grid.band_area_weights,
    )
    assert removed == pytest.approx(supplied, rel=0.0, abs=1.0e-12)


def test_public_default_parser_contains_reference_targets() -> None:
    config = ModelConfig()
    parsed = config_from_args(build_parser().parse_args([]))
    assert parsed.arctic_atlantic_reference_ocean_temperature_c == pytest.approx(
        config.arctic_atlantic_reference_ocean_temperature_c
    )
    assert parsed.arctic_non_atlantic_reference_ocean_temperature_c == pytest.approx(
        config.arctic_non_atlantic_reference_ocean_temperature_c
    )
    assert parsed.arctic_lateral_ocean_heat_transport_wm2_per_ice_fraction == pytest.approx(
        config.arctic_lateral_ocean_heat_transport_wm2_per_ice_fraction
    )
