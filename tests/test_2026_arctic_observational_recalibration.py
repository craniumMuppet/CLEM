"""Regression checks for the v2.29.29 Arctic observational recalibration."""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from arctic_validation_stack import validation_stack_status
from climate_model import ModelConfig
from monte_carlo import PHYSICAL_CLIMATE_PRIORS
ROOT = Path(__file__).resolve().parents[1]

def test_recalibrated_arctic_defaults_are_locked_and_inside_declared_priors() -> None:
    cfg=ModelConfig()
    expected={
        "arctic_full_cover_equivalent_thickness_m":3.70,
        "arctic_new_ice_local_thickness_m":0.22,
        "arctic_winter_transport_enhancement":19.0,
        "arctic_ice_mechanical_max_local_thickness_m":12.0,
        "arctic_ice_concentration_exponent":1.00,
        "arctic_ice_nonsolar_heat_loss_wm2":51.0,
        "arctic_basal_ocean_exchange_wm2_k":6.0,
        "arctic_ice_area_thinning_melt_amplification":2.0,
        "arctic_ice_area_thin_pack_divergence_fraction_per_year":0.30,
        "arctic_ice_export_onset_equivalent_thickness_m":0.90,
        "arctic_ice_export_timescale_years":0.24,
        "arctic_ice_area_formation_volume_sensitivity":11.5,
        "arctic_ice_area_formation_support_floor":0.59,
        "arctic_forced_ocean_heat_convergence_wm2_per_k":8.0,
        "arctic_forced_ocean_heat_convergence_onset_warming_c":0.40,
        "arctic_forced_ocean_heat_convergence_saturation_scale_c":0.45,
        "arctic_forced_ocean_heat_convergence_ice_fraction_exponent":1.0,
    }
    for name,value in expected.items():
        assert getattr(cfg,name)==pytest.approx(value)
        prior=PHYSICAL_CLIMATE_PRIORS[name]
        assert prior.lower <= value <= prior.upper

def test_repaired_core_five_observation_stack_is_complete() -> None:
    status=validation_stack_status()
    assert status["core_five_calibration_validation_stack_complete"] is True
    assert status["all_six_observational_products_available"] is True
    assert status["missing_sources"] == []

def test_packaged_recalibration_enforces_level_trend_and_physical_gates() -> None:
    payload=json.loads((ROOT/"ARCTIC_OBSERVATIONAL_RECALIBRATION_10DEG_2026.json").read_text())
    assert payload["calibration_passed"] is True
    assert payload["validation_informed_development_evaluation_passed"] is True
    assert payload["physical_volume_thickness_validation"]["passed"] is True
    assert payload["physical_volume_thickness_validation"]["scientific_volume_thickness_validation_complete"] is False
    assert payload["physical_volume_thickness_validation"]["temporal_correlation_gates"]["cryosat2_mean_thickness_correlation_ge_0.30"] is False
    for month in ("3","9"):
        area=payload["calibration"]["months"][month]["area"]
        assert area["rmse_million_km2"] <= 1.0
        ratio=abs(area["model_trend_million_km2_per_decade"] / area["observed_trend_million_km2_per_decade"])
        assert 0.80 <= ratio <= 1.25
        assert area["model_trend_million_km2_per_decade"] * area["observed_trend_million_km2_per_decade"] > 0
        model_ci=area["model_trend_diagnostics"]
        observed_ci=area["observed_trend_diagnostics"]
        assert max(model_ci["ols_95pct_ci_low_million_km2_per_decade"],observed_ci["ols_95pct_ci_low_million_km2_per_decade"]) <= min(model_ci["ols_95pct_ci_high_million_km2_per_decade"],observed_ci["ols_95pct_ci_high_million_km2_per_decade"])
        recent=payload["validation_informed_development_evaluation"]["months"][month]["area"]
        assert recent["rmse_million_km2"] <= 0.50
    osi=payload["osi_saf_development_crosscheck"]
    assert osi["independent_crosscheck"] is False
    assert osi["used_during_method_development"] is True
    assert osi["months"]["3"]["rmse_le_1p00_million_km2"] is False
    assert osi["months"]["9"]["rmse_le_1p00_million_km2"] is True
    retrospective=payload["retrospective_fold_local_hindcast_evaluation"]
    assert retrospective["all_folds_scored"] is True
    assert retrospective["all_folds_have_minimum_baselines"] is True
    assert retrospective["fold_local_candidate_selection_used"] is True
    assert retrospective["scientific_predictive_skill_claim_allowed"] is False
    assert payload["prospective_untouched_validation_complete"] is False
    assert payload["scientific_validation_complete"] is False
