"""Release-finalization and evidence-integrity checks for EGCM v2.29.28."""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from climate_model import MODEL_VERSION, ModelConfig
from arctic_validation_stack import source_status
from sea_ice_validation import retrospective_fold_local_hindcast_requirements
from scientific_evidence import SCIENTIFIC_USE_METADATA
ROOT=Path(__file__).resolve().parents[1]

def test_v22928_identity_and_selected_defaults() -> None:
    cfg=ModelConfig()
    assert MODEL_VERSION=="2.29.28"
    from tools.v22928_release_integrity import PACKAGE_NAME
    assert PACKAGE_NAME == "emergent_global_climate_model_v2_29_28"
    # The checkout may have any directory name.  The release finalizer enforces
    # PACKAGE_NAME against the staged ZIP root before it will emit metadata.
    assert 'version = "2.29.28"' in (ROOT/"pyproject.toml").read_text()
    assert cfg.arctic_winter_transport_enhancement==pytest.approx(19.0)
    assert cfg.arctic_ice_mechanical_max_local_thickness_m==pytest.approx(12.0)
    assert cfg.arctic_ice_concentration_exponent==pytest.approx(1.0)
    assert cfg.arctic_ice_nonsolar_heat_loss_wm2==pytest.approx(51.0)
    assert cfg.arctic_ice_area_thinning_melt_amplification==pytest.approx(2.0)
    assert cfg.arctic_ice_area_thin_pack_divergence_fraction_per_year==pytest.approx(0.30)
    assert cfg.arctic_ice_export_onset_equivalent_thickness_m==pytest.approx(0.90)
    assert cfg.arctic_ice_export_timescale_years==pytest.approx(0.24)
    assert cfg.arctic_ice_area_formation_volume_sensitivity==pytest.approx(11.5)
    assert cfg.arctic_ice_area_formation_support_floor==pytest.approx(0.59)
    assert cfg.arctic_forced_ocean_heat_convergence_wm2_per_k==pytest.approx(8.0)
    assert cfg.arctic_forced_ocean_heat_convergence_onset_warming_c==pytest.approx(0.40)
    assert cfg.arctic_forced_ocean_heat_convergence_saturation_scale_c==pytest.approx(0.45)

def test_v22928_documents_are_synchronized() -> None:
    assert (ROOT/"README.md").read_text().startswith("# Emergent-Sensitivity Global Climate Model v2.29.28")
    assert "## 2.29.28" in (ROOT/"CHANGELOG.md").read_text()
    assert (ROOT/"V2_29_28_ARCTIC_TREND_AND_VALIDATION_INTEGRITY.md").is_file()

def test_v22928_current_evidence_is_fail_closed_and_osi_is_development_only() -> None:
    p=json.loads((ROOT/"ARCTIC_OBSERVATIONAL_RECALIBRATION_10DEG_2026.json").read_text())
    assert p["calibration_passed"] is True
    assert p["physical_volume_thickness_validation"]["passed"] is True
    assert p["physical_volume_thickness_validation"]["scientific_volume_thickness_validation_complete"] is False
    assert p["osi_saf_development_crosscheck"]["independent_crosscheck"] is False
    assert p["osi_saf_development_crosscheck"]["months"]["3"]["rmse_million_km2"] > 1.0
    assert p["scientific_validation_complete"] is False

def test_v22928_retrospective_fold_local_manifest_is_semantically_honest() -> None:
    status=retrospective_fold_local_hindcast_requirements()
    assert status["all_folds_scored"] is True
    assert status["all_folds_have_minimum_baselines"] is True
    assert status["fold_local_candidate_selection_used"] is True
    assert status["full_continuous_recalibration_used"] is False
    assert status["scientific_predictive_skill_claim_allowed"] is False
    m=json.loads((ROOT/"RETROSPECTIVE_FOLD_LOCAL_ARCTIC_HINDCAST_V2_29_28.json").read_text())
    assert [x["calibrate_through"] for x in m["folds"]] == [1989,1999,2009]
    assert m["invalid_1979_fold_removed"] is True
    assert m["candidate_bank_predeclared_before_this_bank_was_scored"] is True
    assert m["candidate_grid_uses_post_cutoff_observations_for_fold_selection"] is False
    assert m["independent_prospective_validation"] is False

def test_v22928_scientific_wording_matches_fail_closed_status() -> None:
    status=SCIENTIFIC_USE_METADATA["components"]["sea_ice"]["scientific_validation_status"]
    lower=status.lower()
    assert "development-only" in lower
    assert "cryosat-2" in lower
    assert "temporal-correlation" in lower
    assert "nsidc-0611" in lower
    assert "fold-local" in lower
    assert "2027" in lower

def test_v22928_present_observational_sources_pass_hash_integrity() -> None:
    for sid in ("nsidc_g02202_v6","piomas_v2_1","cryosat2_rdeft4_v1","icesat2_is2sitmogr4_v4","osi_saf_osi450a1_v3_1"):
        status=source_status(sid)
        assert status["available"] is True
        assert status["integrity_errors"] == []
    assert source_status("nsidc_0611_v4")["available"] is False
