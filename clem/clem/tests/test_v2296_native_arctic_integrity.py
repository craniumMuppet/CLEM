"""Release-blocking native Arctic and observation-operator tests for v2.29.6."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import numpy as np

from climate_model import EARTH_AREA_M2, ModelConfig, ProcessClimateModel, save_outputs
from sea_ice_observation import diagnosed_area_extent_million_km2

ROOT = Path(__file__).resolve().parents[1]


def _model() -> ProcessClimateModel:
    return ProcessClimateModel(
        replace(ModelConfig(), duration_years=0.1, auto_initialize_from_1850=False)
    )


def test_reference_cycle_has_no_active_emergency_thickness_cap() -> None:
    model = _model()
    maximum_equivalent = 0.0
    cap_hits = 0
    samples = 0
    for month in range(1, 13):
        state = model._arctic_reference_state((month - 0.5) / 12.0)
        for prefix in ("atlantic", "non_atlantic"):
            equivalent = np.asarray(state[f"{prefix}_ice_thickness_m"], dtype=float)
            maximum_equivalent = max(maximum_equivalent, float(np.max(equivalent)))
            cap_hits += int(np.count_nonzero(np.isclose(
                equivalent,
                model.config.arctic_max_equivalent_thickness_m,
                rtol=0.0,
                atol=1.0e-8,
            )))
            samples += equivalent.size
    assert maximum_equivalent < 0.40 * model.config.arctic_max_equivalent_thickness_m
    assert cap_hits == 0
    assert samples > 0


def test_winter_coverage_and_summer_retreat_are_direct_native_states() -> None:
    model = _model()
    mask = model.grid.lat >= model.config.arctic_module_full_latitude_deg
    for prefix, ocean_fraction in (
        ("atlantic", model.grid.atlantic_ocean_fraction),
        ("non_atlantic", model.non_atlantic_ocean_fraction),
    ):
        weights = model.grid.band_area_weights[mask] * ocean_fraction[mask]
        march = model._arctic_reference_state((3.0 - 0.5) / 12.0)[f"{prefix}_ice_fraction"][mask]
        september = model._arctic_reference_state((9.0 - 0.5) / 12.0)[f"{prefix}_ice_fraction"][mask]
        march_mean = float(np.average(march, weights=weights))
        september_mean = float(np.average(september, weights=weights))
        assert 0.65 <= march_mean <= 0.90
        assert 0.20 <= september_mean <= 0.65
        assert march_mean - september_mean >= 0.20


def test_northern_legacy_annual_ice_is_not_double_counted() -> None:
    model = _model()
    regular = np.ones_like(model.grid.lat) * 0.9
    seasonal = np.linspace(0.0, 1.0, model.grid.lat.size)
    effective = model._effective_seasonal_sea_ice_fraction(regular, seasonal)
    expected_north = model.arctic_module_blend * seasonal
    np.testing.assert_allclose(
        effective[model.grid.lat >= 0.0],
        expected_north[model.grid.lat >= 0.0],
        rtol=0.0,
        atol=0.0,
    )
    np.testing.assert_allclose(
        effective[model.grid.lat < 0.0],
        regular[model.grid.lat < 0.0],
        rtol=0.0,
        atol=0.0,
    )


def test_area_mapping_has_bounded_ratio_at_all_small_positive_values() -> None:
    values = np.geomspace(1.0e-14, 1.0, 60)
    for phase in (2000.2, 2000.7):
        previous_extent = -1.0
        for value in values:
            area, extent = diagnosed_area_extent_million_km2(
                raw_area_million_km2=float(value),
                warming_c=6.0,
                calendar_year=phase,
                northern_ocean_area_million_km2=155.0,
            )
            assert area == float(value)
            assert 1.0 <= extent / area <= 1.50
            assert extent >= previous_extent
            previous_extent = extent


def test_primary_map_and_legacy_alias_are_native(tmp_path) -> None:
    result = _model().run()
    native = result.native_sea_ice_map_at_index(-1)
    np.testing.assert_allclose(result.sea_ice_map_at_index(-1), native, rtol=0.0, atol=0.0)
    display = result.sea_ice_display_map_at_index(-1)
    assert display.shape == native.shape
    save_outputs(result, tmp_path)
    with np.load(tmp_path / "final_fields.npz") as fields:
        np.testing.assert_allclose(fields["sea_ice_fraction"], fields["sea_ice_native_area_fraction"])
        np.testing.assert_allclose(fields["thermodynamic_two_sector_ice_area_fraction"], fields["sea_ice_native_area_fraction"])
        assert "sea_ice_display_area_fraction" in fields.files


def test_summary_declares_native_area_primary() -> None:
    summary = _model().run().summary()
    assert summary["sea_ice_area_mapping"] == "native_thermodynamic_identity"
    assert summary["sea_ice_map_role"] == "native_two_sector_thermodynamic_process_field"
    assert summary["final_native_northern_ice_area_million_km2"] == summary[
        "final_northern_hemisphere_sea_ice_area_million_km2"
    ]
    assert "display_reconstruction" in summary["sea_ice_display_map_role"]



def test_nsidc_source_product_column_is_read_from_packaged_tables() -> None:
    from sea_ice_validation import load_nsidc_month

    for month in (3, 9):
        frame = load_nsidc_month(month)
        assert "source_dataset" in frame.columns
        assert set(frame["source_dataset"].astype(str)) >= {"NSIDC-0051", "NSIDC-0803"}

def test_model_atlantic_fraction_is_used_by_oisst_processor() -> None:
    source = (ROOT / "tools/process_noaa_oisst_arctic_benchmarks.py").read_text(encoding="utf-8")
    assert "from climate_model import _atlantic_basin_fraction" in source
    assert "atlantic_fraction = _atlantic_basin_fraction" in source
    assert "lon >= -60" not in source



def test_validation_runner_preserves_completed_tasks_for_resume() -> None:
    source = (ROOT / "tools/run_v22910_validation_parallel.py").read_text(encoding="utf-8")
    assert '"--resume"' in source
    assert "failures: dict[str, str]" in source
    assert "completed records were retained for --resume" in source

def test_windows_ci_and_versioned_dependency_records_exist() -> None:
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "windows-latest" in ci
    assert "ubuntu-latest" in ci
    for name in ("requirements.lock", "requirements-dev.lock"):
        first_lines = "\n".join((ROOT / name).read_text(encoding="utf-8").splitlines()[:8])
        assert "2.29.23" in first_lines
    dependency_record = json.loads(
        (ROOT / "dependency_integrity.lock.json").read_text(encoding="utf-8")
    )
    assert dependency_record["model_version"] == "2.29.23"
    verifier = (ROOT / "tools/verify_dependency_lock.py").read_text(encoding="utf-8")
    assert "verify_installed_hashes" in verifier
    assert "platform.platform()" in verifier
    packager = (ROOT / "tools/package_v22914.py").read_text(encoding="utf-8")
    assert '"tests/test_v2296_native_arctic_integrity.py"' in packager


def test_open_water_metadata_does_not_overclaim_quantitative_validation() -> None:
    benchmark = json.loads(
        (
            ROOT
            / "data/validation/open_water/NOAA_OISST_ARCTIC_BENCHMARKS.json"
        ).read_text(encoding="utf-8")
    )
    assert benchmark["evidence_role"] == (
        "tuning_informed_broad_external_temperature_sanity_check_not_quantitative_validation"
    )
    assert benchmark["used_for_tuning"] is True
    assert benchmark["release_gate_role"] == "descriptive_non_blocking_sanity_bounds"
    assert benchmark["reproduction"]["processed_output_in_release"] is False
    assert benchmark["reproduction"]["source_hashes_in_release"] is False
    validator = (ROOT / "validate_v22914.py").read_text(encoding="utf-8")
    assert '"oisst_is_descriptive_nonblocking"' in validator
    assert '"quantitative_validation_claimed": False' in validator
    assert '"open_water_observational_plausibility": bool(' not in validator


def test_retuned_arctic_lapse_rate_closure_is_explicitly_documented() -> None:
    from setting_metadata import setting_info

    config = ModelConfig()
    assert config.arctic_lapse_rate_feedback_wm2_k == 1.10
    metadata = setting_info("arctic_lapse_rate_feedback_wm2_k")
    assert "1.10" in metadata.interval
    assert "tuning-informed" in metadata.interval


def test_positive_amoc_hydraulic_target_saturates_smoothly() -> None:
    model = _model()
    state = model.state.copy()
    state.north_salinity_psu = 40.0
    state.southern_salinity_psu = 30.0
    state.convection_efficiency = 1.05
    diagnostics = model._amoc_diagnostics(state)
    assert diagnostics["amoc_unbounded_hydraulic_target_sv"] > 100.0
    assert model.config.amoc_reference_sv < diagnostics["amoc_hydraulic_target_sv"]
    assert diagnostics["amoc_hydraulic_target_sv"] < model.config.amoc_hydraulic_transport_max_sv
    assert diagnostics["amoc_hydraulic_transport_max_sv"] == model.config.amoc_hydraulic_transport_max_sv


def test_amoc_hydraulic_saturation_requires_headroom() -> None:
    import pytest

    with pytest.raises(ValueError, match="must exceed amoc_reference_sv"):
        replace(
            ModelConfig(),
            amoc_hydraulic_transport_max_sv=ModelConfig().amoc_reference_sv,
        ).validate()
