"""Regression checks for the independent v2.29.20 review corrections."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import numpy as np
import pytest

from climate_model import ModelConfig, ProcessClimateModel
from validate_v22920 import structural_area_volume_experiments


def small_model() -> ProcessClimateModel:
    return ProcessClimateModel(
        replace(
            ModelConfig(),
            duration_years=0.1,
            dt_years=0.05,
            record_every_years=0.05,
            resolution_deg=10.0,
            auto_initialize_from_1850=False,
        )
    )


def test_winter_transport_uses_actual_transient_temperature() -> None:
    model = small_model()
    reference = np.full(model.grid.lat.shape, -22.22)
    warmed = np.full(model.grid.lat.shape, -2.22)
    darkness = np.ones(model.grid.lat.shape)
    reference_weight = model._arctic_winter_transport_weight(
        reference, reference, darkness
    )
    warmed_weight = model._arctic_winter_transport_weight(
        reference, warmed, darkness
    )
    assert float(np.max(reference_weight)) > 0.9
    assert float(np.max(warmed_weight)) < 0.05
    assert float(np.max(warmed_weight)) < float(np.max(reference_weight))


def test_structural_validation_is_computed_and_integrated() -> None:
    result = structural_area_volume_experiments(ModelConfig(resolution_deg=10.0))
    assert result["helper_level_passed"] is True
    assert result["integrated_production_path"]["passed"] is True
    assert result["process_budget_experiments"]["passed"] is True
    assert result["process_budget_experiments"]["maximum_absolute_residual"] <= 1.0e-12
    assert result["integrated_production_path"]["maximum_volume_identity_error_m"] <= 1.0e-10


def test_extent_metadata_excludes_the_historical_fitted_operator() -> None:
    observation = Path("sea_ice_observation.py").read_text(encoding="utf-8")
    validation = Path("sea_ice_validation.py").read_text(encoding="utf-8")
    assert '"extent_observation_operator_calibrated": 0.0' in observation
    assert '"extent_contains_observational_fit": 0.0' in observation
    assert '"extent_is_separate_prognostic_state": 0.0' in observation
    assert "Raw Sea Ice Index v4 *area*" in validation
    assert "never\n   used for calibration" in validation


def test_validation_duration_ends_at_2100() -> None:
    text = Path("validate_v22922.py").read_text(encoding="utf-8")
    assert "duration_years=250.0" in text
    assert "duration_years=251.0" not in text


def test_combiner_cannot_classify_scientific_release_without_prospective_data() -> None:
    text = Path("combine_v22922_validation.py").read_text(encoding="utf-8")
    assert "independent_prospective_validation_available = False" in text
    assert 'release_classification = "engineering_only"' in text


def test_fingerprint_covers_validation_dependencies_and_benchmarks() -> None:
    text = Path("validate_v22922.py").read_text(encoding="utf-8")
    for required in (
        "combine_v22922_validation.py",
        "validation_segmentation.py",
        "scientific_evidence.py",
        "runtime_provenance.py",
        "trusted_validation_pickle.py",
        "amoc_continuation.py",
        "external_posthoc_sanity_benchmarks.json",
        "NOAA_OISST_ARCTIC_BENCHMARKS.json",
        "acquire_oisst_provenance.py",
        "process_noaa_oisst_arctic_benchmarks.py",
    ):
        assert required in text
