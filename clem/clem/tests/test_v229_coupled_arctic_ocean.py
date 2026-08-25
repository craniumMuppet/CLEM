"""v2.29 conservative Arctic ocean/surface coupling regressions."""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from climate_model import ModelConfig, ProcessClimateModel


def _model(**changes) -> ProcessClimateModel:
    return ProcessClimateModel(replace(
        ModelConfig(), scenario="constant", duration_years=1.0,
        auto_initialize_from_1850=False, **changes
    ))


def test_reference_cycle_contains_periodic_sector_ocean_states() -> None:
    model = _model()
    assert model.arctic_reference_periodic_closure_wyr_m2 < 1.0e-8
    for prefix in ("atlantic", "non_atlantic"):
        ocean = getattr(model, f"arctic_reference_{prefix}_shallow_ocean_temperature_c")
        assert ocean.shape == getattr(model, f"arctic_reference_{prefix}_ice_fraction").shape
        assert np.all(np.isfinite(ocean))
        assert float(np.ptp(ocean[model.grid.lat >= 66.0])) > 0.0


def test_basal_heat_flux_increases_with_ocean_temperature() -> None:
    model = _model()
    n = 3
    common = dict(
        insolation_wm2=np.zeros(n), air_temperature_c=np.full(n, -15.0),
        ice_energy_wyr_m2=np.full(n, -model.arctic_latent_energy_per_m_wyr_m2),
        open_water_heat_wyr_m2=np.zeros(n), basal_ocean_heat_flux_wm2=1.5,
    )
    cold = model._arctic_surface_fluxes(**common, ocean_temperature_c=np.full(n, -1.5))
    warm = model._arctic_surface_fluxes(**common, ocean_temperature_c=np.full(n, 0.5))
    assert np.all(warm["basal_ocean_heat_flux_wm2"] > cold["basal_ocean_heat_flux_wm2"])
    assert np.all(warm["ice_flux_wm2"] > cold["ice_flux_wm2"])


def test_open_water_exchange_is_two_way() -> None:
    model = _model()
    heat = np.array([0.0, 4.0])
    flux = model._arctic_surface_fluxes(
        insolation_wm2=np.zeros(2), air_temperature_c=np.zeros(2),
        ice_energy_wyr_m2=np.zeros(2), open_water_heat_wyr_m2=heat,
        basal_ocean_heat_flux_wm2=1.5, ocean_temperature_c=np.array([0.0, 0.0]),
    )
    assert flux["open_water_ocean_heat_flux_wm2"][0] > 0.0
    assert flux["open_water_ocean_heat_flux_wm2"][1] < 0.0


def test_transient_ocean_surface_exchange_is_equal_and_opposite() -> None:
    model = _model(arctic_transient_substeps_per_year=12)
    state = model.state.copy()
    mask = model.arctic_module_blend
    state.arctic_atlantic_open_water_heat_anomaly_wyr_m2 += 0.5 * mask
    before_surface = state.arctic_atlantic_open_water_heat_anomaly_wyr_m2.copy()
    before_ocean = state.atlantic_ocean_anomaly_c.copy()
    out = model._advance_seasonal_arctic(
        0.55, 1.0e-4, state, state.land_anomaly_c,
        state.atlantic_ocean_anomaly_c, state.non_atlantic_ocean_anomaly_c,
        state.atlantic_sea_ice_fraction, state.non_atlantic_sea_ice_fraction,
    )
    surface_change = out["atlantic_open_water_heat"] - before_surface
    ocean_energy_change = (out["atlantic_ocean"] - before_ocean) * model.config.ocean_mixed_layer_heat_capacity_wyr_m2_k
    # Other surface fluxes act over this tiny step; the coupled exchange itself
    # must oppose the warm-surface perturbation in the bulk ocean.
    active = mask > 0.99
    assert float(np.mean(surface_change[active])) < 0.0
    assert float(np.mean(ocean_energy_change[active])) > 0.0


def test_reference_area_mean_resolution_spread_is_reduced() -> None:
    minima = {"atlantic": [], "non_atlantic": []}
    for resolution in (2.5, 5.0, 10.0):
        model = _model(resolution_deg=resolution)
        mask = model.grid.lat >= 66.0
        for prefix, fraction in (
            ("atlantic", model.grid.atlantic_ocean_fraction),
            ("non_atlantic", model.non_atlantic_ocean_fraction),
        ):
            values = getattr(model, f"arctic_reference_{prefix}_ice_fraction")
            weights = model.grid.band_area_weights[mask] * fraction[mask]
            monthly = [float(np.average(values[mask, i], weights=weights)) for i in range(values.shape[1])]
            minima[prefix].append(min(monthly))
    assert max(minima["atlantic"]) - min(minima["atlantic"]) < 0.09
    assert max(minima["non_atlantic"]) - min(minima["non_atlantic"]) < 0.09
