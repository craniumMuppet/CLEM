"""Compatibility and scientific-integrity tests carried forward into v2.29.6."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from climate_model import MODEL_VERSION, ModelConfig, ProcessClimateModel
from sea_ice_observation import (
    diagnosed_area_extent_million_km2,
    reconstruct_concentration_and_occupancy,
    raw_northern_ice_area_million_km2,
)
from sea_ice_validation import (
    CALIBRATION,
    DEVELOPMENT_EVALUATION,
    PROSPECTIVE_UNTOUCHED_START_YEAR,
    calibration_passes,
    development_evaluation_passes,
    evaluate_period,
)

ROOT = Path(__file__).resolve().parents[1]


def _reference_native_area(model: ProcessClimateModel, month: int) -> float:
    state = model._arctic_reference_state((month - 0.5) / 12.0)
    return raw_northern_ice_area_million_km2(
        state["atlantic_effective_ice_fraction"],
        state["non_atlantic_effective_ice_fraction"],
        model.grid.lat,
        model.grid.atlantic_ocean_fraction_map,
        model.grid.ocean_fraction_map,
        model.grid.map_area_weights,
    )


def test_version_native_cycle_and_amoc_physics_defaults() -> None:
    assert MODEL_VERSION == "2.29.29"
    config = ModelConfig()
    assert config.amoc_temperature_density_coupling == 1.0
    assert config.arctic_full_cover_equivalent_thickness_m == 3.7
    assert config.arctic_max_equivalent_thickness_m == 20.0
    assert config.arctic_max_local_ice_thickness_m == 500.0
    model = ProcessClimateModel(
        replace(config, duration_years=0.1, auto_initialize_from_1850=False)
    )
    march = _reference_native_area(model, 3)
    september = _reference_native_area(model, 9)
    # This is the preindustrial periodic reference cycle, not the warmed
    # 1979-2020 climatology. It must retain more summer ice than the historical
    # state while preserving a large seasonal retreat.
    assert 15.5 <= march <= 16.5
    assert 8.0 <= september <= 9.0
    assert 7.0 <= march - september <= 8.5


def test_operator_is_identity_continuous_monotone_and_zero_preserving() -> None:
    ocean = 156.0
    year = 2100.2
    inputs = np.array([0.0, 1e-14, 1e-12, 1e-11, 1e-8, 0.1, 1.0, 4.0])
    outputs = np.array([
        diagnosed_area_extent_million_km2(
            raw_area_million_km2=float(value),
            warming_c=4.0,
            calendar_year=year,
            northern_ocean_area_million_km2=ocean,
        )
        for value in inputs
    ])
    np.testing.assert_allclose(outputs[:, 0], inputs, rtol=0.0, atol=1e-15)
    assert np.all(np.diff(outputs[:, 0]) >= 0.0)
    assert np.all(np.diff(outputs[:, 1]) >= 0.0)
    assert outputs[0, 0] == 0.0 and outputs[0, 1] == 0.0
    assert outputs[3, 1] < 2.0e-11
    assert np.all(outputs[:, 1] >= outputs[:, 0])


def test_zero_native_field_produces_zero_northern_maps() -> None:
    model = ProcessClimateModel(
        replace(ModelConfig(), duration_years=0.1, auto_initialize_from_1850=False)
    )
    zeros = np.zeros_like(model.grid.lat)
    concentration, occupancy, metrics = reconstruct_concentration_and_occupancy(
        atlantic_fraction=zeros,
        non_atlantic_fraction=zeros,
        lat=model.grid.lat,
        lon=model.grid.lon,
        lat2d=model.grid.lat2d,
        lon2d=model.grid.lon2d,
        atlantic_ocean_fraction_map=model.grid.atlantic_ocean_fraction_map,
        ocean_fraction_map=model.grid.ocean_fraction_map,
        map_area_weights=model.grid.map_area_weights,
        warming_c=4.0,
        calendar_year=2100.7,
    )
    north = model.grid.lat2d >= 0.0
    assert np.all(concentration[north] == 0.0)
    assert np.all(occupancy[north] == 0.0)
    assert metrics["sea_ice_area_mapping_is_identity"] == 1.0


def test_evidence_periods_are_not_mislabeled_independent() -> None:
    assert CALIBRATION.used_for_tuning
    assert DEVELOPMENT_EVALUATION.used_for_tuning
    assert "not_independent" in DEVELOPMENT_EVALUATION.evidence_role
    assert PROSPECTIVE_UNTOUCHED_START_YEAR == 2027
    metadata = json.loads(
        (ROOT / "data/validation/nsidc/METADATA.json").read_text(encoding="utf-8")
    )
    assert metadata["prospective_untouched_start_year"] == 2027
    assert metadata["validation_informed_development_period"] == [2021, 2025]
    assert metadata["packaged_file_sha256"]["N_03_extent_v4.0.csv"] == hashlib.sha256(
        (ROOT / "data/validation/nsidc/N_03_extent_v4.0.csv").read_bytes()
    ).hexdigest()


def test_native_state_release_gates_are_explicit() -> None:
    rows = []
    for period in (CALIBRATION, DEVELOPMENT_EVALUATION):
        for year in range(period.start_year, period.end_year + 1):
            elapsed_decades = (year - period.start_year) / 10.0
            # Identical synthetic model/observation series exercise every
            # explicit mean, trend, seasonal-amplitude and identity gate.
            for month, value, ratio in (
                (3, 13.4 - 0.05 * elapsed_decades, 1.16),
                (9, 4.8 - 0.45 * elapsed_decades, 1.44),
            ):
                rows.append({
                    "year": year,
                    "month": month,
                    "model_area": value,
                    "model_native_area": value,
                    "model_physical_area": value,
                    "model_extent": value * ratio,
                    "observed_area": value,
                    "observed_extent": value * ratio,
                    "observation_source": "test",
                })
    records = pd.DataFrame(rows)
    cal = evaluate_period(records, CALIBRATION)
    dev = evaluate_period(records, DEVELOPMENT_EVALUATION)
    # Scientific calibration now fails closed when the package lacks the
    # required fixed-mask area and independent volume/thickness datasets.
    passed, gates = calibration_passes(
        cal,
        {
            "independent_predictive_validation": False,
            "raw_march_area_trend_used_for_calibration": False,
            "extent_observation_operator_calibrated": False,
            "passed": True,
        },
        {"available": False},
    )
    assert passed is False
    assert gates["homogeneous_fixed_mask_area_dataset_available"] is True
    assert gates["independent_volume_or_thickness_dataset_available"] is False
    assert development_evaluation_passes(dev)[0]


def test_oisst_record_uses_model_mask_and_does_not_overclaim_reproduction() -> None:
    benchmark = json.loads(
        (ROOT / "data/validation/open_water/NOAA_OISST_ARCTIC_BENCHMARKS.json").read_text(encoding="utf-8")
    )
    processor = (ROOT / "tools/process_noaa_oisst_arctic_benchmarks.py").read_text(encoding="utf-8")
    assert benchmark["scope"]["mask_equivalence_required"] is True
    assert benchmark["reproduction"]["processed_output_in_release"] is False
    assert benchmark["reproduction"]["source_hashes_in_release"] is False
    assert benchmark["used_for_tuning"] is True
    assert benchmark["release_gate_role"] == "descriptive_non_blocking_sanity_bounds"
    assert "tuning_informed" in benchmark["evidence_role"]
    assert "_atlantic_basin_fraction" in processor
    assert "source_sha256" in processor
