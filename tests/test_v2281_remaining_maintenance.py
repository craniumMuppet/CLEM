"""Release-blocking maintenance checks added after the v2.28 review."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from climate_model import (
    EARTH_AREA_M2,
    SECONDS_PER_YEAR,
    ModelConfig,
    ProcessClimateModel,
)
from climate_model_gui import CLI_MAP, DEFAULTS
from monte_carlo import MONTE_CARLO_PHYSICAL_PARAMETERS
from setting_metadata import setting_info
from validate_v2281 import (
    COMMON_VALIDATION_SAMPLE_YEARS,
    common_validation_sample,
)


def test_toa_includes_global_arctic_external_flux_anomaly() -> None:
    model = ProcessClimateModel(
        replace(
            ModelConfig(),
            scenario="constant",
            duration_years=1.0,
            auto_initialize_from_1850=False,
        )
    )
    mask = model.arctic_module_blend
    model.state.arctic_atlantic_open_water_heat_anomaly_wyr_m2 += 0.15 * mask
    model.state.arctic_non_atlantic_open_water_heat_anomaly_wyr_m2 += 0.10 * mask
    model.state.arctic_atlantic_air_anomaly_c += 0.8 * mask
    model.state.arctic_non_atlantic_air_anomaly_c += 0.8 * mask
    row = model.record(0.5)

    assert np.isclose(
        row["toa_imbalance_wm2"],
        row["bulk_radiative_toa_imbalance_wm2"]
        + row["arctic_external_toa_anomaly_wm2"],
        rtol=0.0,
        atol=1.0e-14,
    )
    assert abs(row["arctic_external_toa_anomaly_wm2"]) > 1.0e-9


def test_corrected_toa_closes_short_abrupt_2x_heat_budget() -> None:
    result = ProcessClimateModel(
        replace(
            ModelConfig(),
            scenario="step_2x",
            duration_years=20.0,
            dt_years=0.05,
            record_every_years=0.05,
            seasonal_arctic_enabled=False,
            auto_initialize_from_1850=False,
        )
    ).run().dataframe
    elapsed = result["elapsed_years"].to_numpy(dtype=float)
    conversion = EARTH_AREA_M2 * SECONDS_PER_YEAR / 1.0e21
    actual = float(
        result["total_resolved_heat_content_anomaly_zj"].iloc[-1]
        - result["total_resolved_heat_content_anomaly_zj"].iloc[0]
    )
    corrected = float(
        np.trapezoid(result["toa_imbalance_wm2"].to_numpy(dtype=float), elapsed)
        * conversion
    )
    bulk_only = float(
        np.trapezoid(
            result["bulk_radiative_toa_imbalance_wm2"].to_numpy(dtype=float),
            elapsed,
        )
        * conversion
    )
    corrected_relative_error = abs(actual - corrected) / max(abs(corrected), 1.0e-12)
    bulk_relative_error = abs(actual - bulk_only) / max(abs(bulk_only), 1.0e-12)

    assert corrected_relative_error < 0.002
    assert bulk_relative_error < 0.002


def test_open_water_map_is_masked_where_open_water_is_absent() -> None:
    result = ProcessClimateModel(
        replace(
            ModelConfig(),
            scenario="constant",
            duration_years=1.0,
            dt_years=0.05,
            record_every_years=0.05,
            auto_initialize_from_1850=False,
        )
    ).run()
    index = 0
    non_atlantic_map = np.clip(
        result.grid.ocean_fraction_map - result.grid.atlantic_ocean_fraction_map,
        0.0,
        1.0,
    )
    open_area = (
        result.grid.atlantic_ocean_fraction_map
        * (1.0 - result.atlantic_sea_ice_history[index][:, None])
        + non_atlantic_map
        * (1.0 - result.non_atlantic_sea_ice_history[index][:, None])
    )
    mapped = result.arctic_open_water_temperature_map_at_index(index)
    active_latitudes = (
        result.grid.lat2d >= result.config.arctic_module_start_latitude_deg
    )
    no_open_water = active_latitudes & (open_area <= 1.0e-10)
    with_open_water = active_latitudes & (open_area > 1.0e-10)

    assert np.any(no_open_water)
    assert np.all(np.isnan(mapped[no_open_water]))
    assert np.all(np.isfinite(mapped[with_open_water]))


def test_inactive_arctic_controls_are_not_active_gui_or_monte_carlo_inputs() -> None:
    legacy_gui_keys = {
        "arctic_ocean_air_exchange",
        "arctic_ice_air_exchange",
        "arctic_ice_ocean_exchange",
        "arctic_ice_relaxation_years",
        "arctic_winter_thin_ice_years",
    }
    assert legacy_gui_keys.isdisjoint(DEFAULTS)
    assert legacy_gui_keys.isdisjoint(CLI_MAP)
    assert "arctic_winter_thin_ice_relaxation_years" not in (
        MONTE_CARLO_PHYSICAL_PARAMETERS
    )


def test_filtered_sat_output_and_tooltip_use_actual_memory_timescale() -> None:
    model = ProcessClimateModel(
        replace(
            ModelConfig(),
            scenario="constant",
            duration_years=1.0,
            auto_initialize_from_1850=False,
        )
    )
    row = model.record(0.0)
    assert row["arctic_filtered_near_surface_air_warming_c"] == row[
        "arctic_near_surface_air_warming_c"
    ]
    info = setting_info("arctic_air_memory_years")
    tooltip = info.tooltip().lower()
    assert "0.15" in tooltip
    assert "one-year" not in tooltip
    assert "one year" not in tooltip


def test_common_validation_sampling_is_identical_for_all_supported_timesteps() -> None:
    expected = np.arange(0.0, 1.0 + 1.0e-12, COMMON_VALIDATION_SAMPLE_YEARS)
    for dt in (0.1, 0.05, 0.025):
        elapsed = np.arange(0.0, 1.0 + 0.5 * dt, dt)
        frame = pd.DataFrame({"elapsed_years": elapsed, "value": elapsed})
        sampled = common_validation_sample(frame)
        assert np.allclose(
            sampled["elapsed_years"].to_numpy(dtype=float),
            expected,
            rtol=0.0,
            atol=1.0e-8,
        )


def test_validation_script_uses_common_subannual_sampling_for_headline_and_timesteps() -> None:
    source = Path("validate_v2281.py").read_text(encoding="utf-8")
    assert "sampled = common_validation_sample(raw)" in source
    assert "record_every=COMMON_VALIDATION_SAMPLE_YEARS" in source
    assert "record_every=1.0" not in source[source.index("def timestep_metrics"):source.index("def evaluate_benchmarks")]
