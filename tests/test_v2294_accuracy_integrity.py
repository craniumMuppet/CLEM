"""Accuracy, evidence-partition and interpretation tests retained in v2.29.6."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import numpy as np

from climate_model import ModelConfig, ProcessClimateModel, save_outputs
from sea_ice_observation import (
    diagnosed_area_extent_million_km2,
    reconstruct_concentration_and_occupancy,
)
from scientific_evidence import SCIENTIFIC_USE_METADATA

ROOT = Path(__file__).resolve().parents[1]


def test_control_uses_continuous_residual_not_reference_bypass() -> None:
    source = (ROOT / "climate_model.py").read_text(encoding="utf-8")
    assert "_is_unforced_reference_manifold_step" not in source
    assert "_advance_unforced_reference_manifold" not in source
    assert "_reference_step_residual" in source
    cfg = replace(
        ModelConfig(), scenario="constant", duration_years=2.0,
        dt_years=0.1, record_every_years=0.2,
        auto_initialize_from_1850=False, warming_freshwater_sv_per_k=0.0,
    )
    exact = ProcessClimateModel(cfg).run().dataframe
    assert float(np.max(np.abs(exact["global_surface_warming_c"]))) < 1.0e-12
    perturbed = ProcessClimateModel(cfg)
    perturbed.state.land_anomaly_c[:] = 1.0e-4
    perturbed.step(0.0, 0.1)
    assert abs(perturbed._global_surface_mean(perturbed.state)) > 1.0e-7


def test_subgrid_extent_is_conservative_and_not_sector_binary() -> None:
    model = ProcessClimateModel(replace(ModelConfig(), duration_years=0.1, auto_initialize_from_1850=False))
    reference = model._arctic_reference_state(0.70)
    concentration, occupancy, metrics = reconstruct_concentration_and_occupancy(
        atlantic_fraction=reference["atlantic_ice_fraction"],
        non_atlantic_fraction=reference["non_atlantic_ice_fraction"],
        lat=model.grid.lat, lon=model.grid.lon,
        lat2d=model.grid.lat2d, lon2d=model.grid.lon2d,
        atlantic_ocean_fraction_map=model.grid.atlantic_ocean_fraction_map,
        ocean_fraction_map=model.grid.ocean_fraction_map,
        map_area_weights=model.grid.map_area_weights,
        warming_c=1.3656788539939129, calendar_year=2020.70,
    )
    cell_ocean_area = model.grid.ocean_fraction_map * model.grid.map_area_weights * 5.100656e14 / 1.0e12
    north = model.grid.lat2d >= 0.0
    area = float(np.sum(np.where(north, concentration, 0.0) * cell_ocean_area))
    extent = float(np.sum(np.where(north, occupancy, 0.0) * cell_ocean_area))
    np.testing.assert_allclose(area, metrics["northern_hemisphere_sea_ice_area_million_km2"], rtol=0, atol=1e-10)
    np.testing.assert_allclose(extent, metrics["northern_hemisphere_sea_ice_extent_million_km2"], rtol=0, atol=1e-10)
    assert np.any((occupancy > 0.0) & (occupancy < 1.0))
    assert 0.0 < extent < float(np.sum(np.where(north, cell_ocean_area, 0.0)))
    assert area <= extent


def test_area_identity_and_extent_only_operator_match_frozen_coefficients() -> None:
    north_ocean_area = 156.34314969547353
    cases = [
        (13.0, 0.3, 1979.20),
        (8.0, 0.3, 1979.70),
        (10.0, 1.3, 2020.20),
        (6.0, 1.3, 2020.70),
    ]
    for raw, warming, year in cases:
        area, extent = diagnosed_area_extent_million_km2(
            raw_area_million_km2=raw, warming_c=warming,
            calendar_year=year, northern_ocean_area_million_km2=north_ocean_area,
        )
        assert area == raw
        assert raw <= extent <= 1.50 * raw

def test_evidence_roles_are_unambiguous_and_future_test_is_prospective() -> None:
    development = json.loads((ROOT / "development_regression_benchmarks.json").read_text(encoding="utf-8"))
    assert all(item["used_for_tuning"] for item in development["benchmarks"].values())
    assert all("development" in item["evidence_role"] for item in development["benchmarks"].values())
    metadata = json.loads((ROOT / "data/validation/nsidc/METADATA.json").read_text(encoding="utf-8"))
    assert metadata["calibration_period"] == [1979, 2020]
    assert metadata["validation_informed_development_period"] == [2021, 2025]
    assert metadata["prospective_untouched_start_year"] == 2027
    assert metadata["independent_holdout_claimed"] is False

def test_open_water_observational_envelope_and_warning() -> None:
    benchmark = json.loads((ROOT / "data/validation/open_water/NOAA_OISST_ARCTIC_BENCHMARKS.json").read_text(encoding="utf-8"))
    model = ProcessClimateModel(ModelConfig())
    # Reference-cycle maxima are directly available from the spun-up periodic state.
    atlantic = float(model.arctic_reference_maximum_active_open_water_temperature_c)
    assert benchmark["benchmarks"]["atlantic_jja_mean_c"]["minimum"] <= atlantic <= 12.0
    # v2.29.7 explicitly discloses that these broad OISST ranges were
    # inspected during the physical retuning. They are development evidence,
    # not an independent regional validation claim.
    assert benchmark["used_for_tuning"] is True
    assert "tuning_informed" in benchmark["evidence_role"]
    assert benchmark["release_gate_role"] == "descriptive_non_blocking_sanity_bounds"
    assert "local" in benchmark["mandatory_output_warning"].lower()
    assert "independent" in benchmark["mandatory_output_warning"].lower()


def test_summary_labels_amoc_greenland_and_open_water_as_sensitivity_outputs() -> None:
    result = ProcessClimateModel(replace(ModelConfig(), duration_years=0.1, record_every_years=0.1, auto_initialize_from_1850=False)).run()
    summary = result.summary()
    assert summary["amoc_projection_role"] == "sensitivity_experiment_not_precise_forecast"
    assert summary["greenland_projection_role"].endswith("not_precise_forecast")
    assert summary["arctic_open_water_temperature_role"] == "sector_diagnostic_not_local_forecast"
    assert summary["sea_ice_future_projection_role"] == (
        "native_prognostic_area_volume_thickness_with_unfitted_15pct_extent_sensitivity"
    )
    assert summary["scientific_use"] == SCIENTIFIC_USE_METADATA


def test_future_sea_ice_metrics_reject_annual_fixed_phase_sampling() -> None:
    import validate_v2296 as validator

    result = ProcessClimateModel(
        replace(
            ModelConfig(),
            scenario="constant",
            duration_years=2.0,
            record_every_years=1.0,
            auto_initialize_from_1850=False,
        )
    ).run()
    import pytest
    with pytest.raises(ValueError, match="subannual records"):
        validator._future_sea_ice_metrics(result)


def test_release_validator_requires_high_forcing_sea_ice_ordering() -> None:
    source = Path("validate_v2296.py").read_text(encoding="utf-8")
    assert '"sea_ice_forcing_ordering"' in source
    assert '"ssp585_late_century_native_sea_ice_area"' in source
    assert '"future_sea_ice_evidence_role"' in source
    assert '"native_thermodynamic_area_projection_with_extent_only_operator"' in source


def test_direct_sea_ice_aggregator_matches_reconstructed_map() -> None:
    result = ProcessClimateModel(
        replace(
            ModelConfig(), duration_years=0.2, record_every_years=0.1,
            auto_initialize_from_1850=False,
        )
    ).run()
    direct = result.northern_sea_ice_area_extent_at_index(-1)
    _, _, reconstructed = result._sea_ice_observation_at_index(-1)
    for key in (
        "northern_hemisphere_sea_ice_area_million_km2",
        "northern_hemisphere_sea_ice_extent_million_km2",
        "raw_two_sector_northern_ice_area_million_km2",
    ):
        np.testing.assert_allclose(direct[key], reconstructed[key], rtol=0.0, atol=1.0e-10)


def test_public_sea_ice_outputs_are_explicit_and_warned() -> None:
    model_source = (ROOT / "climate_model.py").read_text(encoding="utf-8")
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    metadata_source = (ROOT / "setting_metadata.py").read_text(encoding="utf-8")
    for name in (
        "sea_ice_native_area_fraction",
        "sea_ice_display_area_fraction",
        "sea_ice_extent_occupancy_fraction_of_ocean_cell",
        "thermodynamic_two_sector_ice_area_fraction",
    ):
        assert name in model_source
        assert name in app_source
    assert "no longitude-resolved process skill is claimed" in model_source
    assert "no longitude-resolved process" in app_source
    assert "Native thermodynamic sea ice" in app_source
    assert "native two-sector concentration projection" in metadata_source.lower()


def test_summary_makes_native_thermodynamic_sea_ice_primary() -> None:
    result = ProcessClimateModel(
        replace(
            ModelConfig(), duration_years=0.1, record_every_years=0.1,
            auto_initialize_from_1850=False,
        )
    ).run()
    summary = result.summary()
    assert summary["sea_ice_map_role"] == "native_two_sector_thermodynamic_process_field"
    assert "display_reconstruction" in summary["sea_ice_display_map_role"]
    assert summary["final_northern_hemisphere_sea_ice_area_million_km2"] >= 0.0
    assert (
        summary["final_northern_hemisphere_sea_ice_extent_million_km2"]
        >= summary["final_northern_hemisphere_sea_ice_area_million_km2"]
    )
    assert summary["final_raw_two_sector_northern_ice_area_million_km2"] >= 0.0
    assert summary["final_thermodynamic_sea_ice_area_fraction"] == summary["final_sea_ice_area_fraction"]


def test_saved_outputs_make_native_field_primary_and_keep_display_explicit(tmp_path) -> None:
    result = ProcessClimateModel(
        replace(
            ModelConfig(), duration_years=0.1, record_every_years=0.1,
            auto_initialize_from_1850=False,
        )
    ).run()
    save_outputs(result, tmp_path)
    frame = __import__("pandas").read_csv(tmp_path / "final_map.csv")
    for name in (
        "sea_ice_statistical_area_fraction",
        "sea_ice_statistical_concentration_fraction_of_ocean_cell",
        "sea_ice_extent_occupancy_fraction_of_ocean_cell",
        "thermodynamic_two_sector_ice_area_fraction",
        "sea_ice_fraction",
    ):
        assert name in frame.columns
    np.testing.assert_allclose(
        frame["sea_ice_fraction"],
        frame["sea_ice_native_area_fraction"],
        rtol=0.0, atol=0.0,
    )
    np.testing.assert_allclose(
        frame["sea_ice_fraction"],
        frame["thermodynamic_two_sector_ice_area_fraction"],
        rtol=0.0, atol=0.0,
    )
    with np.load(tmp_path / "final_fields.npz") as fields:
        for name in (
            "sea_ice_native_area_fraction",
            "sea_ice_display_area_fraction",
            "sea_ice_statistical_area_fraction",
            "sea_ice_statistical_concentration_fraction_of_ocean_cell",
            "sea_ice_extent_occupancy_fraction_of_ocean_cell",
            "thermodynamic_two_sector_ice_area_fraction",
        ):
            assert name in fields.files


def test_future_sea_ice_is_not_mislabeled_independent_prediction() -> None:
    import validate_v2296 as validator
    source = (ROOT / "validate_v2296.py").read_text(encoding="utf-8")
    assert "No post-2020 trend" in source
    assert "independent_predictive_validation" in source
    assert "AR6-consistent post-2020 tuning closure" not in source
    metadata = SCIENTIFIC_USE_METADATA["components"]["sea_ice"]
    assert "native prognostic area and volume are sensitivity outputs" in metadata["future_projection_role"]
    assert "extent" in metadata["future_projection_role"]
