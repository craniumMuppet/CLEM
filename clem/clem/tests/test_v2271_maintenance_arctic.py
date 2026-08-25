from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from climate_model import MODEL_VERSION, ModelConfig, ProcessClimateModel
from held_out_amoc_validation import historical_external_metrics


def _base_config(**changes):
    base = ModelConfig(
        scenario="constant",
        duration_years=0.1,
        auto_initialize_from_1850=False,
    )
    return replace(base, **changes)


@pytest.mark.parametrize("resolution_deg", [2.5, 5.0, 10.0])
def test_arctic_baseline_and_reference_cycle_at_all_supported_resolutions(
    resolution_deg: float,
) -> None:
    ProcessClimateModel.clear_arctic_reference_cycle_cache()
    model = ProcessClimateModel(_base_config(resolution_deg=resolution_deg))
    cfg = model.config
    active = model.grid.lat >= cfg.arctic_module_start_latitude_deg
    full = model.grid.lat >= cfg.arctic_module_full_latitude_deg

    assert tuple(map(int, MODEL_VERSION.split("."))) >= (2, 28, 0)
    assert np.isclose(
        np.sum(model.baseline_map_c * model.grid.map_area_weights),
        14.0,
        atol=1.0e-10,
    )
    assert np.min(model.baseline_ocean_c[active]) >= (
        cfg.arctic_interface_freezing_temperature_c - 1.0e-12
    )
    assert np.allclose(
        model.baseline_ocean_c[full],
        cfg.arctic_interface_freezing_temperature_c,
        atol=1.0e-12,
    )
    assert np.isfinite(model.arctic_reference_periodic_closure_wyr_m2)
    assert model.arctic_reference_periodic_closure_wyr_m2 < 0.02
    assert np.all(np.isfinite(model.arctic_reference_ice_fraction))
    assert np.min(model.arctic_reference_ice_fraction) >= 0.0
    assert np.max(model.arctic_reference_ice_fraction) <= 1.0


def test_reference_cycle_cache_keys_start_latitude_and_greenland_floor() -> None:
    ProcessClimateModel.clear_arctic_reference_cycle_cache()
    common = dict(
        arctic_reference_cycle_steps=120,
        arctic_reference_spinup_years=12,
        amoc_enforce_initial_density_constraint=False,
    )
    first = ProcessClimateModel(
        _base_config(arctic_module_start_latitude_deg=55.0, **common)
    )
    second = ProcessClimateModel(
        _base_config(arctic_module_start_latitude_deg=60.0, **common)
    )
    latitude_index = int(np.argmin(np.abs(second.grid.lat - 57.5)))
    assert np.mean(first.arctic_reference_ice_fraction[latitude_index]) > 0.05
    assert np.mean(second.arctic_reference_ice_fraction[latitude_index]) == 0.0

    # Keep the latitude fixed at the first model's value so this section
    # isolates the Greenland-floor cache-key dimension after the v2.29.8
    # default Arctic start latitude moved from 55 to 52 degrees N.
    low_floor = ProcessClimateModel(
        _base_config(
            arctic_module_start_latitude_deg=55.0,
            greenland_melt_season_floor=0.05,
            **common,
        )
    )
    high_floor = ProcessClimateModel(
        _base_config(
            arctic_module_start_latitude_deg=55.0,
            greenland_melt_season_floor=0.50,
            **common,
        )
    )
    assert not np.allclose(
        low_floor.greenland_reference_melt_weight,
        high_floor.greenland_reference_melt_weight,
    )
    assert ProcessClimateModel.arctic_reference_cycle_cache_info()["entries"] == 3


def test_reference_cycle_cache_is_bounded_lru() -> None:
    ProcessClimateModel.clear_arctic_reference_cycle_cache()
    for index in range(ProcessClimateModel.ARCTIC_REFERENCE_CACHE_MAX_ENTRIES + 3):
        ProcessClimateModel(
            _base_config(
                greenland_melt_season_floor=0.01 * index,
                arctic_reference_cycle_steps=72,
                arctic_reference_spinup_years=10,
                amoc_enforce_initial_density_constraint=False,
            )
        )
    info = ProcessClimateModel.arctic_reference_cycle_cache_info()
    assert info == {
        "entries": ProcessClimateModel.ARCTIC_REFERENCE_CACHE_MAX_ENTRIES,
        "maximum_entries": ProcessClimateModel.ARCTIC_REFERENCE_CACHE_MAX_ENTRIES,
    }


def test_temperature_products_are_explicit_and_map_consistent() -> None:
    config = _base_config(
        additional_forcing_wm2=4.0,
        duration_years=5.0,
        record_every_years=1.0,
    )
    result = ProcessClimateModel(config).run()
    final = result.dataframe.iloc[-1]

    required = {
        "global_bulk_surface_warming_c",
        "global_near_surface_air_warming_c",
        "global_instantaneous_near_surface_air_warming_c",
        "arctic_near_surface_air_warming_c",
        "arctic_bulk_surface_warming_c",
        "arctic_ocean_interface_temperature_c",
        "arctic_ocean_interface_temperature_anomaly_c",
    }
    assert required.issubset(result.dataframe.columns)

    bulk = result.bulk_surface_map_at_index(-1)
    air = result.near_surface_air_map_at_index(-1)
    interface = result.arctic_ocean_interface_map_at_index(-1)
    assert bulk.shape == air.shape == interface.shape == result.grid.lat2d.shape
    assert np.max(np.abs(air - bulk)) > 0.1
    assert np.isclose(
        np.sum(air * result.grid.map_area_weights),
        final["global_near_surface_air_warming_c"],
        atol=1.0e-10,
    )
    arctic_mask = result.grid.lat2d >= 66.0
    assert np.isclose(
        np.sum(air * result.grid.map_area_weights * arctic_mask)
        / np.sum(result.grid.map_area_weights * arctic_mask),
        final["arctic_near_surface_air_warming_c"],
        atol=1.0e-10,
    )
    assert np.all(np.isnan(interface[result.grid.lat2d < config.arctic_module_start_latitude_deg]))
    assert np.any(np.isfinite(interface[result.grid.lat2d >= config.arctic_module_start_latitude_deg]))


def test_arctic_amplification_uses_like_for_like_near_surface_air() -> None:
    years = np.arange(1850.0, 2101.0)
    time = years - years[0]
    frame = pd.DataFrame(
        {
            "year": years,
            "amoc_sv": np.full_like(years, 17.0),
            "global_surface_warming_c": 1.0 * time,
            "global_near_surface_air_warming_c": 2.0 * time,
            "arctic_near_surface_air_warming_c": 6.0 * time,
            "ocean_heat_content_anomaly_zj": 3.0 * time,
        }
    )
    metrics = historical_external_metrics(frame)
    assert metrics["historical_arctic_amplification_1979_2021_ratio"] == pytest.approx(3.0)


def test_arctic_exchange_priors_and_tooltips_include_defaults() -> None:
    from monte_carlo import SCIENCE_PRIOR_SPECS
    from setting_metadata import setting_info

    config = ModelConfig()
    stable = SCIENCE_PRIOR_SPECS["arctic_open_water_stable_exchange_wm2_k"]
    unstable = SCIENCE_PRIOR_SPECS["arctic_open_water_unstable_exchange_wm2_k"]
    transition = SCIENCE_PRIOR_SPECS["arctic_open_water_exchange_transition_c"]
    assert stable.lower <= config.arctic_open_water_stable_exchange_wm2_k <= stable.upper
    assert unstable.lower <= config.arctic_open_water_unstable_exchange_wm2_k <= unstable.upper
    assert transition.lower <= config.arctic_open_water_exchange_transition_c <= transition.upper
    assert (stable.lower, stable.upper) == (0.1, 2.0)
    assert (unstable.lower, unstable.upper, unstable.mode) == (2.0, 10.0, 5.0)
    assert "0.50" in setting_info("arctic_open_water_stable_exchange_wm2_k").interval
    assert "5.0" in setting_info("arctic_open_water_unstable_exchange_wm2_k").interval
    assert "0.50" in setting_info("arctic_open_water_exchange_transition_c").interval
    assert setting_info("greenland_smb_enabled") is setting_info(
        "greenland_surface_mass_balance_enabled"
    )
    assert setting_info("greenland_pdd_melt_factor") is setting_info(
        "greenland_pdd_melt_factor_gt_per_degree_day"
    )


def test_archived_v22916_validation_records_are_internally_consistent() -> None:
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    summary = json.loads((root / "VALIDATION_SUMMARY_V2_29_16.json").read_text())
    deep = json.loads((root / "DEEP_VALIDATION_V2_29_16.json").read_text())
    audit = json.loads((root / "IMPLEMENTATION_AUDIT_V2_29_16.json").read_text())
    assert summary["model_version"] == deep["model_version"] == audit["model_version"] == "2.29.16"
    assert summary["provenance"]["climate_model_sha256"] == audit["source_files"]["climate_model.py"]
    assert summary["provenance"]["processing_script_sha256"] == audit["source_files"]["validate_v22916.py"]
    changes = audit["implemented_review_fixes"]
    for key in (
        "historical_temporal_skill_claim_removed",
        "historical_scores_non_release_blocking",
        "nonoverlapping_five_year_blocks",
        "robust_march_trend_period_uncertainty_diagnostics",
        "zero_lateral_restoring_configuration",
        "twenty_percent_zero_restoring_monte_carlo_branch",
        "oisst_descriptive_nonblocking_without_reproduction_claim",
        "public_ranges_cover_documented_priors",
        "future_extent_and_timing_are_sensitivity_outputs",
        "v2298_resume_and_explicit_target_features_retained",
        "stale_lock_reclamation_transaction_gate",
        "semantic_backup_checkpoint_identity_fallback",
        "failed_checkpoint_recovery_accounting",
        "default_science_prior_amoc_anchor_fixed_at_base",
        "explicit_custom_amoc_reference_sampling_retained",
        "saved_winter_diagnostics_match_integrated_state",
        "winter_lead_closure_available_volume_taper",
        "minimum_local_thickness_concentration_cap",
        "transient_temperature_lead_closure_activation",
    ):
        assert changes[key]
    assert summary["release_checks"]["science_prior_fixes_amoc_control_anchor"]
    assert summary["all_release_checks_passed"]
    assert deep["all_release_checks_passed"]
    assert all(summary["release_checks"].values())
