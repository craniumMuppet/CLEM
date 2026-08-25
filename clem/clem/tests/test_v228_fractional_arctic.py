"""Structural regression tests for the v2.28 fractional Arctic rebuild."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from climate_model import MODEL_VERSION, ModelConfig, ProcessClimateModel


def _model(**changes) -> ProcessClimateModel:
    cfg = replace(
        ModelConfig(),
        scenario="constant",
        duration_years=2.0,
        record_every_years=1.0,
        auto_initialize_from_1850=False,
        **changes,
    )
    return ProcessClimateModel(cfg)


def _ocean_arctic_weights(model: ProcessClimateModel) -> np.ndarray:
    return (
        model.grid.band_area_weights
        * model.grid.ocean_fraction
        * (model.grid.lat >= 66.0)
    )


def test_v228_defaults_and_freshwater_are_preserved() -> None:
    cfg = ModelConfig()
    assert MODEL_VERSION == "2.29.28"
    assert cfg.hydrological_freshwater_sv_per_k == 0.006
    assert cfg.greenland_freshwater_sv_per_k == 0.005
    assert cfg.ocean_heat_exchange_wm2_k == 1.45
    assert cfg.arctic_winter_transport_enhancement == 10.0
    assert cfg.arctic_open_water_stable_exchange_wm2_k == 0.5
    assert cfg.arctic_open_water_unstable_exchange_wm2_k == 10.0
    assert cfg.arctic_open_water_exchange_transition_c == 0.5
    assert cfg.arctic_transient_shortwave_scale == 1.0
    assert cfg.arctic_basal_ocean_exchange_wm2_k == 6.0
    assert cfg.arctic_open_water_ocean_exchange_wm2_k == 25.0
    assert cfg.arctic_reference_ocean_heat_capacity_wyr_m2_k == 6.0
    assert cfg.arctic_reference_ocean_restoring_wm2_k == 12.0
    assert cfg.arctic_air_low_pass_years == 0.15


def test_fractional_reference_contains_simultaneous_ice_and_open_water_heat() -> None:
    model = _model()
    mask = model.grid.lat >= 66.0
    for prefix in ("atlantic", "non_atlantic"):
        ice = getattr(model, f"arctic_reference_{prefix}_ice_fraction")[mask]
        open_heat = getattr(model, f"arctic_reference_{prefix}_open_water_heat_wyr_m2")[mask]
        partial = (ice > 1.0e-4) & (ice < 1.0 - 1.0e-4)
        assert np.any(partial)
        assert np.any(open_heat[partial] > 0.0)


def test_local_ice_thickness_not_grid_equivalent_thickness_controls_conduction() -> None:
    model = _model()
    latent = model.arctic_latent_energy_per_m_wyr_m2
    equivalent = np.array([0.20, 0.80])
    ice_energy = -latent * equivalent
    concentration, diagnosed_equivalent, local = model._arctic_ice_energy_to_state(ice_energy)
    assert np.allclose(diagnosed_equivalent, equivalent)
    assert np.allclose(local, equivalent / concentration)
    assert np.all(local >= equivalent)

    flux = model._arctic_surface_fluxes(
        insolation_wm2=np.zeros(2),
        air_temperature_c=np.array([-20.0, -20.0]),
        ice_energy_wyr_m2=ice_energy,
        open_water_heat_wyr_m2=np.zeros(2),
        basal_ocean_heat_flux_wm2=1.5,
    )
    snow = np.clip((-np.array([-20.0, -20.0]) - 1.0) / 10.0, 0.0, 1.0)
    k = model.config.arctic_ice_thermal_conductivity_wm_k
    expected_conductivity = k / (
        np.maximum(local, 0.03)
        + k * model.config.arctic_snow_thermal_resistance_m2k_w * snow
    )
    surface = flux["ice_surface_temperature_c"]
    expected = expected_conductivity * (
        model.config.arctic_interface_freezing_temperature_c - surface
    )
    assert np.allclose(flux["conductive_flux_wm2"], expected)


def test_atlantic_and_central_arctic_reference_cycles_are_distinct_and_periodic() -> None:
    model = _model()
    mask = model.grid.lat >= 66.0
    atl = model.arctic_reference_atlantic_ice_fraction[mask]
    non = model.arctic_reference_non_atlantic_ice_fraction[mask]
    assert not np.allclose(atl, non)
    assert float(model.arctic_reference_periodic_closure_wyr_m2) < 1.0e-8
    assert float(model.arctic_reference_spinup_convergence_wyr_m2) < 1.0e-8
    assert np.nanmin(atl) < np.nanmin(non)


def test_unforced_two_reservoir_control_is_stable() -> None:
    cfg = replace(
        ModelConfig(),
        scenario="constant",
        start_year=1850.0,
        duration_years=5.0,
        record_every_years=0.25,
        auto_initialize_from_1850=False,
    )
    frame = ProcessClimateModel(cfg).run().dataframe
    assert float(np.max(np.abs(frame["global_surface_warming_c"]))) < 1.0e-4
    assert float(np.max(np.abs(frame["arctic_instantaneous_near_surface_air_warming_c"]))) < 1.0e-3
    assert float(np.max(np.abs(frame["arctic_open_water_heat_content_anomaly_zj"]))) < 1.0e-4


def test_reference_cycle_is_independent_of_transient_shortwave_scaling() -> None:
    ProcessClimateModel.clear_arctic_reference_cycle_cache()
    low = _model(arctic_transient_shortwave_scale=0.0)
    high = _model(arctic_transient_shortwave_scale=1.0)
    for prefix in ("atlantic", "non_atlantic"):
        assert np.array_equal(
            getattr(low, f"arctic_reference_{prefix}_ice_fraction"),
            getattr(high, f"arctic_reference_{prefix}_ice_fraction"),
        )
        assert np.array_equal(
            getattr(low, f"arctic_reference_{prefix}_open_water_heat_wyr_m2"),
            getattr(high, f"arctic_reference_{prefix}_open_water_heat_wyr_m2"),
        )


def test_phase_aware_maps_expose_open_water_and_local_ice_products() -> None:
    cfg = replace(
        ModelConfig(),
        scenario="constant",
        duration_years=1.0,
        record_every_years=0.25,
        auto_initialize_from_1850=False,
    )
    result = ProcessClimateModel(cfg).run()
    for index in range(len(result.dataframe)):
        interface = result.arctic_ocean_interface_map_at_index(index)
        open_water = result.arctic_open_water_temperature_map_at_index(index)
        local_thickness = result.arctic_local_ice_thickness_map_at_index(index)
        active = result.grid.lat2d >= cfg.arctic_module_start_latitude_deg
        assert np.any(np.isfinite(interface[active]))
        assert np.any(np.isfinite(open_water[active]))
        assert np.any(np.isfinite(local_thickness[active]))


def test_reference_cycle_bounds_and_closure_at_all_supported_resolutions() -> None:
    for resolution in (2.5, 5.0, 10.0):
        model = _model(resolution_deg=resolution)
        assert model.arctic_reference_periodic_closure_wyr_m2 < 1.0e-8
        assert model.arctic_reference_spinup_convergence_wyr_m2 < 1.0e-8
        for prefix in ("atlantic", "non_atlantic"):
            ice = getattr(model, f"arctic_reference_{prefix}_ice_fraction")
            local = getattr(model, f"arctic_reference_{prefix}_local_ice_thickness_m")
            open_temp = getattr(model, f"arctic_reference_{prefix}_open_water_temperature_c")
            assert np.all((ice >= 0.0) & (ice <= 1.0))
            assert np.all(local >= 0.0)
            assert np.all(np.isfinite(open_temp))


def test_surface_reservoir_normalization_has_no_active_open_water_ceiling() -> None:
    model = _model()
    cfg = model.config
    ice = np.zeros(3)
    former_capacity = cfg.arctic_interface_heat_capacity_wyr_m2_k * (
        cfg.arctic_interface_max_temperature_c
        - cfg.arctic_interface_freezing_temperature_c
    )
    open_heat = np.array([0.5 * former_capacity, former_capacity, 2.0 * former_capacity])
    before = ice + open_heat
    ice_after, open_after, transfer = model._normalize_arctic_surface_reservoirs(
        ice, open_heat
    )
    assert np.allclose(ice_after + open_after + transfer, before)
    assert np.allclose(transfer, 0.0)
    assert open_after[2] == before[2]
    open_fraction = np.ones_like(open_after)
    temperature = model._arctic_open_water_temperature(open_after, open_fraction)
    assert temperature[2] > cfg.arctic_interface_max_temperature_c


def test_stability_dependent_open_water_exchange_reaches_physical_limits() -> None:
    model = _model()
    air = np.zeros(3)
    water = np.array([-10.0, 0.0, 10.0])
    coefficient = model._arctic_stability_exchange_coefficient(water, air)
    stable = model.config.arctic_open_water_stable_exchange_wm2_k
    unstable = model.config.arctic_open_water_unstable_exchange_wm2_k
    assert coefficient[0] == pytest.approx(stable, abs=1.0e-9)
    assert coefficient[1] == pytest.approx(0.5 * (stable + unstable))
    assert coefficient[2] == pytest.approx(unstable, abs=1.0e-9)
    assert np.all(np.diff(coefficient) > 0.0)


def test_transient_shortwave_scaling_changes_only_the_anomaly() -> None:
    model = _model()
    ref = model._arctic_reference_state(0.55)
    prefix = "atlantic"
    reference_flux = model._arctic_surface_fluxes(
        insolation_wm2=ref["insolation_wm2"],
        air_temperature_c=ref[f"{prefix}_air_temperature_c"],
        ice_energy_wyr_m2=ref[f"{prefix}_ice_energy_wyr_m2"],
        open_water_heat_wyr_m2=ref[f"{prefix}_open_water_heat_wyr_m2"],
        basal_ocean_heat_flux_wm2=model.config.arctic_atlantic_basal_ocean_heat_flux_wm2,
    )
    perturbed_ice = ref[f"{prefix}_ice_energy_wyr_m2"] * 0.8
    raw = model._arctic_surface_fluxes(
        insolation_wm2=ref["insolation_wm2"],
        air_temperature_c=ref[f"{prefix}_air_temperature_c"],
        ice_energy_wyr_m2=perturbed_ice,
        open_water_heat_wyr_m2=ref[f"{prefix}_open_water_heat_wyr_m2"],
        basal_ocean_heat_flux_wm2=model.config.arctic_atlantic_basal_ocean_heat_flux_wm2,
    )
    scaled = model._arctic_surface_fluxes(
        insolation_wm2=ref["insolation_wm2"],
        air_temperature_c=ref[f"{prefix}_air_temperature_c"],
        ice_energy_wyr_m2=perturbed_ice,
        open_water_heat_wyr_m2=ref[f"{prefix}_open_water_heat_wyr_m2"],
        basal_ocean_heat_flux_wm2=model.config.arctic_atlantic_basal_ocean_heat_flux_wm2,
        absorbed_shortwave_reference_wm2=ref[f"{prefix}_absorbed_shortwave_wm2"],
    )
    expected = reference_flux["absorbed_shortwave_wm2"] + model.config.arctic_transient_shortwave_scale * (
        raw["absorbed_shortwave_wm2"] - reference_flux["absorbed_shortwave_wm2"]
    )
    assert np.allclose(scaled["absorbed_shortwave_wm2"], expected)


def test_hidden_legacy_arctic_controls_have_zero_dynamical_effect() -> None:
    base = replace(
        ModelConfig(),
        scenario="constant",
        duration_years=1.0,
        record_every_years=1.0,
        auto_initialize_from_1850=False,
    )
    changed = replace(
        base,
        arctic_open_water_heat_release_wm2_per_fraction=999.0,
        arctic_ice_air_exchange_wm2_k=99.0,
        arctic_ice_ocean_exchange_wm2_k=99.0,
        arctic_ice_anomaly_relaxation_years=0.01,
        arctic_winter_thin_ice_relaxation_years=0.01,
    )
    a = ProcessClimateModel(base)
    b = ProcessClimateModel(changed)
    out_a = a._advance_seasonal_arctic(
        0.25, base.dt_years, a.state, a.state.land_anomaly_c,
        a.state.atlantic_ocean_anomaly_c, a.state.non_atlantic_ocean_anomaly_c,
        a.state.atlantic_sea_ice_fraction, a.state.non_atlantic_sea_ice_fraction,
    )
    out_b = b._advance_seasonal_arctic(
        0.25, changed.dt_years, b.state, b.state.land_anomaly_c,
        b.state.atlantic_ocean_anomaly_c, b.state.non_atlantic_ocean_anomaly_c,
        b.state.atlantic_sea_ice_fraction, b.state.non_atlantic_sea_ice_fraction,
    )
    for key in out_a:
        assert np.array_equal(out_a[key], out_b[key]), key


def test_normal_interfaces_expose_structural_not_empirical_arctic_controls() -> None:
    root = Path(__file__).resolve().parents[1]
    for filename in ("app.py", "monte_carlo.py", "setting_metadata.py"):
        text = (root / filename).read_text(encoding="utf-8")
        for active in (
            "arctic_open_water_stable_exchange_wm2_k",
            "arctic_open_water_unstable_exchange_wm2_k",
            "arctic_open_water_exchange_transition_c",
            "arctic_transient_shortwave_scale",
            "arctic_basal_ocean_exchange_wm2_k",
            "arctic_open_water_ocean_exchange_wm2_k",
            "arctic_reference_ocean_heat_capacity_wyr_m2_k",
            "arctic_reference_ocean_restoring_wm2_k",
        ):
            assert active in text
    gui = (root / "climate_model_gui.py").read_text(encoding="utf-8")
    for active in (
        "arctic_open_water_stable_exchange",
        "arctic_open_water_unstable_exchange",
        "arctic_open_water_exchange_transition",
        "arctic_transient_shortwave_scale",
        "arctic_basal_ocean_exchange",
        "arctic_open_water_ocean_exchange",
        "arctic_reference_ocean_heat_capacity",
        "arctic_reference_ocean_restoring",
    ):
        assert active in gui
    app = (root / "app.py").read_text(encoding="utf-8")
    for obsolete in (
        "arctic_open_water_heat_release_wm2_per_fraction",
        "arctic_ice_anomaly_relaxation_years",
        "arctic_winter_thin_ice_relaxation_years",
    ):
        assert obsolete not in app


def test_diagnostics_use_area_weighted_local_ice_and_effective_fluxes() -> None:
    model = _model()
    diagnostics = model._arctic_physical_diagnostics(model.state, 0.55)
    assert diagnostics["arctic_local_ice_thickness_m"] > 0.0
    assert np.isfinite(diagnostics["arctic_effective_external_surface_flux_wm2"])
    assert model.config.arctic_open_water_stable_exchange_wm2_k <= diagnostics[
        "arctic_open_water_exchange_wm2_k"
    ] <= model.config.arctic_open_water_unstable_exchange_wm2_k


def test_cache_is_bounded_and_sensitive_to_sector_and_exchange_inputs() -> None:
    ProcessClimateModel.clear_arctic_reference_cycle_cache()
    base = ModelConfig(
        scenario="constant",
        duration_years=1.0,
        auto_initialize_from_1850=False,
        arctic_reference_cycle_steps=72,
        arctic_reference_spinup_years=12,
        amoc_enforce_initial_density_constraint=False,
    )
    first = ProcessClimateModel(base)
    first_cycle = first.arctic_reference_atlantic_ice_fraction.copy()
    second = ProcessClimateModel(
        replace(base, arctic_atlantic_reference_ocean_temperature_c=1.0)
    )
    assert not np.array_equal(first_cycle, second.arctic_reference_atlantic_ice_fraction)
    for value in np.linspace(0.2, 1.2, 10):
        ProcessClimateModel(
            replace(base, arctic_open_water_stable_exchange_wm2_k=float(value))
        )
    info = ProcessClimateModel.arctic_reference_cycle_cache_info()
    assert info["entries"] <= info["maximum_entries"] == 8
