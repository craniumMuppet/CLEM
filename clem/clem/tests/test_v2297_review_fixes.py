"""Retained review regressions, updated for the v2.29.9 scientific fixes."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from climate_model import ModelConfig, build_parser
from climate_model_gui import CLI_MAP, DEFAULTS
from monte_carlo import SCIENCE_PRIOR_SPECS
from sea_ice_validation import inspected_march_2026_evaluation

ROOT = Path(__file__).resolve().parents[1]


def test_tuned_arctic_controls_have_cli_and_desktop_parity() -> None:
    cfg = ModelConfig()
    args = build_parser().parse_args([])
    assert args.arctic_lapse_rate_feedback == cfg.arctic_lapse_rate_feedback_wm2_k
    assert args.arctic_module_start_latitude == cfg.arctic_module_start_latitude_deg
    assert args.arctic_reference_air_seasonal_amplitude == cfg.arctic_reference_air_seasonal_amplitude_c
    assert args.arctic_basal_ocean_exchange == cfg.arctic_basal_ocean_exchange_wm2_k
    assert args.arctic_open_water_ocean_exchange == cfg.arctic_open_water_ocean_exchange_wm2_k
    assert args.arctic_lateral_ocean_heat_transport == cfg.arctic_lateral_ocean_heat_transport_wm2_per_ice_fraction
    assert args.arctic_forced_ocean_heat_convergence == cfg.arctic_forced_ocean_heat_convergence_wm2_per_k
    assert args.arctic_forced_ocean_heat_convergence_onset == cfg.arctic_forced_ocean_heat_convergence_onset_warming_c
    assert args.arctic_forced_ocean_heat_convergence_saturation_scale == cfg.arctic_forced_ocean_heat_convergence_saturation_scale_c
    assert args.arctic_ice_area_formation_support_floor == cfg.arctic_ice_area_formation_support_floor
    assert args.arctic_phase_restoring_deficit_saturation == cfg.arctic_phase_restoring_deficit_saturation_fraction
    assert args.arctic_phase_restoring_max_deficit_flux == cfg.arctic_phase_restoring_max_deficit_flux_wm2
    assert args.arctic_max_local_ice_thickness == cfg.arctic_max_local_ice_thickness_m
    assert args.arctic_ice_area_thick_pack_resistance_exponent == cfg.arctic_ice_area_thick_pack_resistance_exponent
    assert float(DEFAULTS["arctic_lapse_rate_feedback"]) == cfg.arctic_lapse_rate_feedback_wm2_k
    assert float(DEFAULTS["arctic_module_start_latitude"]) == cfg.arctic_module_start_latitude_deg
    assert float(DEFAULTS["arctic_reference_air_seasonal_amplitude"]) == cfg.arctic_reference_air_seasonal_amplitude_c
    assert float(DEFAULTS["arctic_forced_ocean_heat_convergence"]) == cfg.arctic_forced_ocean_heat_convergence_wm2_per_k
    assert float(DEFAULTS["arctic_forced_ocean_heat_convergence_onset"]) == cfg.arctic_forced_ocean_heat_convergence_onset_warming_c
    assert float(DEFAULTS["arctic_phase_restoring_deficit_saturation"]) == cfg.arctic_phase_restoring_deficit_saturation_fraction
    assert float(DEFAULTS["arctic_phase_restoring_max_deficit_flux"]) == cfg.arctic_phase_restoring_max_deficit_flux_wm2
    assert float(DEFAULTS["arctic_max_local_ice_thickness"]) == cfg.arctic_max_local_ice_thickness_m
    assert float(DEFAULTS["arctic_ice_area_thick_pack_resistance_exponent"]) == cfg.arctic_ice_area_thick_pack_resistance_exponent
    assert CLI_MAP["arctic_module_start_latitude"] == "--arctic-module-start-latitude"
    assert CLI_MAP["arctic_reference_air_seasonal_amplitude"] == "--arctic-reference-air-seasonal-amplitude"
    assert CLI_MAP["arctic_forced_ocean_heat_convergence"] == "--arctic-forced-ocean-heat-convergence"
    assert CLI_MAP["arctic_forced_ocean_heat_convergence_onset"] == "--arctic-forced-ocean-heat-convergence-onset"
    assert CLI_MAP["arctic_forced_ocean_heat_convergence_saturation_scale"] == "--arctic-forced-ocean-heat-convergence-saturation-scale"
    assert CLI_MAP["arctic_ice_area_formation_support_floor"] == "--arctic-ice-area-formation-support-floor"
    assert CLI_MAP["arctic_phase_restoring_deficit_saturation"] == "--arctic-phase-restoring-deficit-saturation"
    assert CLI_MAP["arctic_phase_restoring_max_deficit_flux"] == "--arctic-phase-restoring-max-deficit-flux"
    assert CLI_MAP["arctic_max_local_ice_thickness"] == "--arctic-max-local-ice-thickness"
    assert CLI_MAP["arctic_ice_area_thick_pack_resistance_exponent"] == "--arctic-ice-area-thick-pack-resistance-exponent"
    assert args.amoc_convection_recovery_years == cfg.amoc_convection_recovery_years


def test_amoc_recovery_and_hosing_gate_match_v22910_recalibration() -> None:
    cfg = ModelConfig()
    assert cfg.amoc_convection_recovery_years == 80.0
    assert SCIENCE_PRIOR_SPECS["amoc_convection_recovery_years"].mode == 80.0
    source = (ROOT / "validate_v22914.py").read_text(encoding="utf-8")
    assert '"hosing_recovery_ge_80_percent"' in source
    assert 'recovery_percent_of_initial_loss"] >= 80.0' in source
    assert '"hybrid_2100_amoc_restored_to_10_14_sv"' in source
    assert '"long_ssp245_single_year_2100_floor_restored"' in source


def test_selected_v22910_physics_defaults_are_frozen() -> None:
    cfg = ModelConfig()
    expected = {
        "arctic_lapse_rate_feedback_wm2_k": 1.1,
        "arctic_module_start_latitude_deg": 52.0,
        "arctic_reference_air_seasonal_amplitude_c": 12.0,
        "arctic_basal_ocean_exchange_wm2_k": 6.0,
        "arctic_reference_air_temperature_at_full_latitude_c": -9.5,
        "arctic_ice_area_formation_volume_sensitivity": 11.5,
        "arctic_forced_ocean_heat_convergence_wm2_per_k": 7.5,
        "arctic_forced_ocean_heat_convergence_onset_warming_c": 0.45,
        "arctic_max_equivalent_thickness_m": 20.0,
        "arctic_max_local_ice_thickness_m": 500.0,
        "arctic_phase_restoring_deficit_saturation_fraction": 0.14,
        "arctic_phase_restoring_max_deficit_flux_wm2": 2.5,
        "arctic_ice_area_thick_pack_resistance_exponent": 0.0,
        "arctic_open_water_ocean_exchange_wm2_k": 25.0,
        "arctic_lateral_ocean_heat_transport_wm2_per_ice_fraction": 25.0,
        "arctic_transient_shortwave_scale": 1.0,
        "arctic_full_cover_equivalent_thickness_m": 3.7,
        "arctic_ice_concentration_exponent": 0.56,
        "amoc_stratification_saturation_c": 0.6,
        "arctic_greenland_marine_influence": 0.1,
    }
    for name, value in expected.items():
        assert float(getattr(cfg, name)) == pytest.approx(value)


def test_calibration_informed_arctic_and_amoc_closures_are_sampled() -> None:
    required = {
        "arctic_lapse_rate_feedback_wm2_k",
        "arctic_module_start_latitude_deg",
        "arctic_reference_air_seasonal_amplitude_c",
        "arctic_basal_ocean_exchange_wm2_k",
        "arctic_open_water_ocean_exchange_wm2_k",
        "arctic_lateral_ocean_heat_transport_wm2_per_ice_fraction",
        "arctic_forced_ocean_heat_convergence_wm2_per_k",
        "arctic_forced_ocean_heat_convergence_onset_warming_c",
        "arctic_phase_restoring_deficit_saturation_fraction",
        "arctic_phase_restoring_max_deficit_flux_wm2",
        "arctic_full_cover_equivalent_thickness_m",
        "arctic_ice_concentration_exponent",
        "arctic_greenland_marine_influence",
        "amoc_hydraulic_transport_max_sv",
    }
    assert required <= SCIENCE_PRIOR_SPECS.keys()
    assert "arctic_max_equivalent_thickness_m" not in SCIENCE_PRIOR_SPECS
    assert "arctic_max_local_ice_thickness_m" not in SCIENCE_PRIOR_SPECS
    assert "arctic_ice_area_thick_pack_resistance_exponent" not in __import__("monte_carlo").science_default_ranges("ar6_amoc")
    cfg = ModelConfig()
    for name in required:
        prior = SCIENCE_PRIOR_SPECS[name]
        value = float(getattr(cfg, name))
        if name == "arctic_lateral_ocean_heat_transport_wm2_per_ice_fraction":
            assert prior.point_mass_at_zero == pytest.approx(0.20)
        assert prior.lower <= value <= prior.upper


def test_march_2026_is_reported_as_inspected_evaluation() -> None:
    records = pd.DataFrame([{
        "year": 2026, "month": 3, "model_area": 12.8, "observed_area": 12.6,
        "model_extent": 14.2, "observed_extent": 14.0,
        "observation_source": "synthetic-test",
    }])
    value = inspected_march_2026_evaluation(records)
    assert value["status"] == "reported_after_prior_inspection_not_independent"
    assert value["year"] == 2026
    assert value["independent_predictive_validation"] is False
    assert value["area_error_million_km2"] == pytest.approx(0.2)
    assert value["extent_error_million_km2"] == pytest.approx(0.2)


def test_oisst_bounds_are_descriptive_and_non_release_blocking() -> None:
    source = (ROOT / "validate_v22914.py").read_text(encoding="utf-8")
    assert '"oisst_is_descriptive_nonblocking"' in source
    assert '"release_gate_role"] == "descriptive_non_blocking_sanity_bounds"' in source
    assert '"oisst_descriptive_bounds"' in source
    benchmark = json.loads((ROOT / "data/validation/open_water/NOAA_OISST_ARCTIC_BENCHMARKS.json").read_text(encoding="utf-8"))
    assert benchmark["release_gate_role"] == "descriptive_non_blocking_sanity_bounds"


def test_dev_dependency_input_and_lock_are_consistent() -> None:
    declared = {
        line.strip().split("==")[0].split(">=")[0].lower()
        for line in (ROOT / "requirements-dev.in").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith(("#", "-r "))
    }
    locked = {
        line.strip().split("==")[0].lower()
        for line in (ROOT / "requirements-dev.lock").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#") and "==" in line
    }
    assert declared <= locked


def test_oisst_reproduction_workflow_is_packaged_without_fabricated_hashes() -> None:
    benchmark = json.loads((ROOT / "data/validation/open_water/NOAA_OISST_ARCTIC_BENCHMARKS.json").read_text(encoding="utf-8"))
    assert (ROOT / "tools/acquire_oisst_provenance.py").is_file()
    assert (ROOT / "data/validation/open_water/OISST_SOURCE_ACQUISITION.md").is_file()
    assert benchmark["used_for_tuning"] is True
    assert "not_quantitative_validation" in benchmark["evidence_role"]
    assert benchmark["reproduction"]["source_hashes_in_release"] is False
    assert all(value["sha256"] is None for value in benchmark["source_files"].values())


def test_packager_generates_full_file_manifest() -> None:
    source = (ROOT / "tools/package_v22914.py").read_text(encoding="utf-8")
    assert "PACKAGE_FILE_MANIFEST_V2_29_14.json" in source
    assert "def write_full_file_manifest" in source
    assert '"coverage": "all packaged files except this manifest' in source
