"""Scientific and interface regression tests for the v2.26 Arctic rebuild."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np

from climate_model import (
    MODEL_VERSION,
    ModelConfig,
    ProcessClimateModel,
    daily_mean_insolation,
)
from sea_ice_observation import raw_northern_ice_area_million_km2


def _seasonal_slope_ratio(frame, months: tuple[int, ...]) -> float:
    subset = frame[
        (frame["year"] >= 1979.0)
        & (frame["year"] <= 2021.999)
        & frame["arctic_calendar_month"].round().astype(int).isin(months)
    ]
    arctic_slope = float(
        np.polyfit(
            subset["year"],
            subset["arctic_instantaneous_near_surface_air_warming_c"],
            1,
        )[0]
    )
    global_slope = float(
        np.polyfit(subset["year"], subset["global_instantaneous_near_surface_air_warming_c"], 1)[0]
    )
    return arctic_slope / global_slope


def test_v226_defaults_are_physical_and_freshwater_is_not_inflated() -> None:
    config = ModelConfig()
    assert tuple(map(int, MODEL_VERSION.split("."))) >= (2, 27, 0)
    assert config.seasonal_arctic_enabled
    assert config.hydrological_freshwater_sv_per_k == 0.006
    assert config.greenland_freshwater_sv_per_k == 0.005
    assert config.amoc_temperature_density_coupling == 1.0
    assert config.amoc_convection_density_scale_factor == 1.0
    assert config.hydrological_freshwater_sv_per_k < 0.023
    assert config.greenland_freshwater_sv_per_k < 0.017
    assert config.arctic_air_local_warming_multiplier == 1.0
    assert config.arctic_sea_ice_air_warming_c_per_fraction_loss == 0.0
    assert config.arctic_reference_seasonal_ice_amplitude == 0.0


def test_orbital_insolation_resolves_polar_night_and_midnight_sun() -> None:
    january = float(daily_mean_insolation(80.0, 10.0 / 365.2425))
    june = float(daily_mean_insolation(80.0, 172.0 / 365.2425))
    equinox = float(daily_mean_insolation(0.0, 80.0 / 365.2425))
    assert january < 1.0e-8
    assert june > 500.0
    assert 420.0 < equinox < 450.0


def test_generated_reference_cycle_has_thermodynamic_ice_and_freezing_interface() -> None:
    model = ProcessClimateModel(
        replace(
            ModelConfig(),
            scenario="constant",
            duration_years=1.0,
            auto_initialize_from_1850=False,
        )
    )
    mask = model.grid.lat >= 66.0
    weights = model.grid.band_area_weights[mask] * model.grid.ocean_fraction[mask]
    monthly_ice = []
    monthly_native_area = []
    monthly_interface = []
    monthly_insolation = []
    for month in range(1, 13):
        phase = (month - 0.5) / 12.0
        state = model._arctic_reference_state(phase)
        monthly_ice.append(float(np.average(state["ice_fraction"][mask], weights=weights)))
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
        monthly_interface.append(
            float(np.average(state["interface_temperature_c"][mask], weights=weights))
        )
        monthly_insolation.append(
            float(np.average(state["insolation_wm2"][mask], weights=weights))
        )
    assert 0.0 < min(monthly_ice) < max(monthly_ice) <= 1.0
    assert max(monthly_ice) - min(monthly_ice) > 0.20
    assert int(np.argmin(monthly_native_area)) + 1 in (8, 9, 10)
    assert 12.0 <= monthly_native_area[2] <= 17.0
    assert 3.0 <= monthly_native_area[8] <= 9.0
    assert monthly_native_area[8] < monthly_native_area[2]
    assert min(monthly_insolation) < 1.0
    assert max(monthly_insolation) > 400.0
    for month in range(1, 13):
        phase = (month - 0.5) / 12.0
        state = model._arctic_reference_state(phase)
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


def test_internal_arctic_heat_exchange_is_conservative() -> None:
    config = replace(
        ModelConfig(),
        scenario="constant",
        duration_years=1.0,
        auto_initialize_from_1850=False,
        arctic_moisture_transport_wm2_per_k=0.0,
        arctic_winter_transport_enhancement=0.0,
        arctic_dry_static_transport_wm2_k=0.0,
        arctic_open_water_heat_release_wm2_per_fraction=0.0,
        arctic_interface_longwave_damping_wm2_k=0.0,
        arctic_ice_anomaly_relaxation_years=1.0e12,
        arctic_winter_thin_ice_relaxation_years=1.0e12,
        arctic_transient_shortwave_scale=0.0,
        arctic_ice_nonsolar_heat_loss_wm2=0.0,
        arctic_open_water_nonsolar_heat_loss_wm2=0.0,
        arctic_atlantic_basal_ocean_heat_flux_wm2=0.0,
        arctic_non_atlantic_basal_ocean_heat_flux_wm2=0.0,
    )
    model = ProcessClimateModel(config)
    blend = model.arctic_module_blend
    control = model.state.copy()
    perturbed = control.copy()
    perturbed.atlantic_ocean_anomaly_c += 0.40 * blend
    perturbed.non_atlantic_ocean_anomaly_c += 0.25 * blend
    perturbed.arctic_atlantic_air_anomaly_c -= 0.15 * blend
    perturbed.arctic_non_atlantic_air_anomaly_c -= 0.10 * blend
    perturbed.arctic_atlantic_ice_energy_anomaly_wyr_m2 += 0.02 * blend
    perturbed.arctic_non_atlantic_ice_energy_anomaly_wyr_m2 += 0.01 * blend
    perturbed.arctic_atlantic_open_water_heat_anomaly_wyr_m2 += 0.015 * blend
    perturbed.arctic_non_atlantic_open_water_heat_anomaly_wyr_m2 += 0.008 * blend

    weights = model.grid.band_area_weights
    atlantic = model.grid.atlantic_ocean_fraction
    non_atlantic = model.non_atlantic_ocean_fraction
    co = config.ocean_mixed_layer_heat_capacity_wyr_m2_k
    ca = config.arctic_air_heat_capacity_wyr_m2_k

    def state_energy(item):
        return float(
            np.sum(
                weights
                * (
                    atlantic
                    * (
                        co * item.atlantic_ocean_anomaly_c
                        + ca * item.arctic_atlantic_air_anomaly_c
                        + item.arctic_atlantic_ice_energy_anomaly_wyr_m2
                        + item.arctic_atlantic_open_water_heat_anomaly_wyr_m2
                    )
                    + non_atlantic
                    * (
                        co * item.non_atlantic_ocean_anomaly_c
                        + ca * item.arctic_non_atlantic_air_anomaly_c
                        + item.arctic_non_atlantic_ice_energy_anomaly_wyr_m2
                        + item.arctic_non_atlantic_open_water_heat_anomaly_wyr_m2
                    )
                )
            )
        )

    def result_energy(item):
        return float(
            np.sum(
                weights
                * (
                    atlantic
                    * (
                        co * item["atlantic_ocean"]
                        + ca * item["atlantic_air"]
                        + item["atlantic_ice_energy"]
                        + item["atlantic_open_water_heat"]
                    )
                    + non_atlantic
                    * (
                        co * item["non_atlantic_ocean"]
                        + ca * item["non_atlantic_air"]
                        + item["non_atlantic_ice_energy"]
                        + item["non_atlantic_open_water_heat"]
                    )
                )
            )
        )

    def advance(item):
        return model._advance_seasonal_arctic(
            0.25,
            config.dt_years,
            item,
            item.land_anomaly_c,
            item.atlantic_ocean_anomaly_c,
            item.non_atlantic_ocean_anomaly_c,
            item.atlantic_sea_ice_fraction,
            item.non_atlantic_sea_ice_fraction,
        )

    before_delta = state_energy(perturbed) - state_energy(control)
    after_delta = result_energy(advance(perturbed)) - result_energy(advance(control))
    assert abs(after_delta - before_delta) < 1.0e-10


def test_legacy_multiplier_controls_do_not_affect_enabled_seasonal_physics() -> None:
    base = replace(
        ModelConfig(),
        scenario="ssp245",
        duration_years=40.0,
        record_every_years=10.0,
        auto_initialize_from_1850=False,
    )
    neutral = ProcessClimateModel(base).run().dataframe
    extreme = ProcessClimateModel(
        replace(
            base,
            arctic_air_local_warming_multiplier=3.0,
            arctic_sea_ice_air_warming_c_per_fraction_loss=100.0,
        )
    ).run().dataframe
    columns = [
        "global_surface_warming_c",
        "arctic_warming_c",
        "arctic_thermodynamic_sea_ice_fraction",
        "amoc_sv",
    ]
    assert np.array_equal(neutral[columns].to_numpy(), extreme[columns].to_numpy())


def test_normal_interfaces_do_not_expose_legacy_multiplier_controls() -> None:
    root = Path(__file__).resolve().parents[1]
    for filename in ("app.py", "climate_model_gui.py", "setting_metadata.py"):
        text = (root / filename).read_text(encoding="utf-8")
        assert "arctic_air_local_warming_multiplier" not in text
        assert "arctic_sea_ice_air_warming_c_per_fraction_loss" not in text
    cli = (root / "climate_model.py").read_text(encoding="utf-8")
    assert 'help=argparse.SUPPRESS' in cli


def test_greenland_seasonal_forcing_is_summer_dominant_and_annually_normalized() -> None:
    config = replace(
        ModelConfig(),
        scenario="constant",
        duration_years=1.0,
        auto_initialize_from_1850=False,
        greenland_seasonal_runoff_fraction=1.0,
    )
    model = ProcessClimateModel(config)
    phases = np.arange(config.arctic_reference_cycle_steps) / config.arctic_reference_cycle_steps
    weights = np.array([model._greenland_melt_season_weight(float(p)) for p in phases])
    assert abs(float(np.mean(weights)) - 1.0) < 1.0e-10
    peak_month = int(np.argmax(weights) * 12 / len(weights)) + 1
    assert peak_month in (5, 6, 7)
    assert float(np.mean(weights[(phases >= 0.42) & (phases < 0.67)])) > 1.5
    winter = (phases < 0.17) | (phases >= 0.92)
    assert float(np.mean(weights[winter])) < 0.5

    annual_flux = 0.02
    routed = np.array(
        [model._greenland_routed_flux_sv(annual_flux, float(p)) for p in phases]
    )
    assert abs(float(np.mean(routed)) - annual_flux) < 1.0e-12
    assert float(np.mean(routed[(phases >= 0.42) & (phases < 0.67)])) > annual_flux
    assert float(np.mean(routed[winter])) < annual_flux


def test_ssp245_generates_winter_autumn_amplification_and_bidirectional_ocean_exchange() -> None:
    base = ModelConfig()
    config = replace(
        base,
        start_year=1850.0,
        duration_years=251.0,
        scenario="ssp245",
        record_every_years=base.dt_years,
        auto_initialize_from_1850=False,
    )
    frame = ProcessClimateModel(config).run().dataframe
    djf = _seasonal_slope_ratio(frame, (12, 1, 2))
    jja = _seasonal_slope_ratio(frame, (6, 7, 8))
    son = _seasonal_slope_ratio(frame, (9, 10, 11))
    assert djf > son > jja
    assert djf > 2.3
    assert son > 2.0

    late = frame[(frame["year"] >= 2081.0) & (frame["year"] < 2101.0)].copy()
    late["month"] = late["arctic_calendar_month"].round().astype(int)
    monthly = late.groupby("month").mean(numeric_only=True)
    ice_min_month = int(
        monthly["raw_two_sector_northern_ice_area_million_km2"].idxmin()
    )
    release_max_month = int(
        monthly["arctic_open_water_heat_release_wm2"].idxmax()
    )
    assert ice_min_month in (8, 9, 10)
    # The explicit open-water reservoir releases its accumulated sensible heat
    # during the cold season; the maximum need not coincide with the ice minimum.
    assert release_max_month in (11, 12, 1, 2)
    release = monthly["arctic_open_water_heat_release_wm2"]
    assert float(release.loc[[11, 12, 1, 2]].mean()) > float(
        release.loc[[6, 7, 8, 9]].mean()
    )

    # The coupled surface/ocean exchange is conservative and temperature-driven.
    # Under late-century SSP2-4.5 the reduced shallow ocean can remain colder than
    # the exposed surface throughout the year, so a forced sign reversal is not a
    # valid requirement. Summer heat uptake must nevertheless exceed winter uptake.
    ocean_exchange = monthly["arctic_ocean_to_surface_heat_flux_wm2"]
    assert np.all(np.isfinite(ocean_exchange))
    assert float(ocean_exchange.loc[[6, 7, 8, 9]].mean()) < float(
        ocean_exchange.loc[[11, 12, 1, 2]].mean()
    )
    assert float(ocean_exchange.min()) < 0.0

    winter_ice = float(
        monthly.loc[
            [11, 12, 1, 2, 3],
            "raw_two_sector_northern_ice_area_million_km2",
        ].mean()
    )
    summer_ice = float(
        monthly.loc[
            [7, 8, 9],
            "raw_two_sector_northern_ice_area_million_km2",
        ].mean()
    )
    assert winter_ice > summer_ice
    interface = monthly["arctic_ocean_interface_temperature_c"]
    assert float(interface.loc[[11, 12, 1, 2, 3]].mean()) < float(
        interface.loc[[7, 8, 9]].mean()
    )
    assert (
        float(interface.max())
        > config.arctic_interface_freezing_temperature_c
    )
