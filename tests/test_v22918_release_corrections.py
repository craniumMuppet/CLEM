from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import numpy as np
import pytest

from climate_model import MODEL_VERSION, ModelConfig, ProcessClimateModel, build_parser
from co2_target_sweep import validate_target_survival_counts


def _mapping_model(**updates: object) -> ProcessClimateModel:
    return ProcessClimateModel(
        replace(
            ModelConfig(),
            resolution_deg=10.0,
            duration_years=1.0,
            dt_years=0.1,
            record_every_years=0.1,
            seasonal_arctic_enabled=False,
            auto_initialize_from_1850=False,
            **updates,
        )
    )


def test_version_and_recalibrated_compactness_default() -> None:
    config = ModelConfig()
    assert MODEL_VERSION == "2.29.29"
    assert config.arctic_new_ice_local_thickness_m == pytest.approx(0.22)
    assert config.arctic_ice_concentration_exponent == pytest.approx(1.0)
    assert config.arctic_full_cover_equivalent_thickness_m == pytest.approx(3.7)
    assert config.arctic_winter_transport_enhancement == pytest.approx(19.0)
    assert config.arctic_winter_transport_temperature_scale_c == pytest.approx(15.0)
    assert config.arctic_ice_surface_exchange_wm2_k == pytest.approx(5.0)
    assert config.arctic_transient_shortwave_scale == pytest.approx(1.00)
    assert config.arctic_winter_lead_closure_fraction == pytest.approx(0.0)


@pytest.mark.parametrize("full", [3.0, 4.0, 5.0])
@pytest.mark.parametrize("thin", [0.08, 0.15, 0.30])
@pytest.mark.parametrize("exponent", [1.5, 2.0, 2.5])
def test_compactness_properties_over_complete_prior_support(
    full: float, thin: float, exponent: float
) -> None:
    model = _mapping_model(
        arctic_full_cover_equivalent_thickness_m=full,
        arctic_new_ice_local_thickness_m=thin,
        arctic_ice_concentration_exponent=exponent,
        arctic_max_equivalent_thickness_m=max(8.0, full),
    )
    equivalent = np.linspace(0.0, full, 4001)
    concentration = model._arctic_concentration_from_equivalent_thickness(equivalent)
    assert concentration[0] == 0.0
    assert concentration[-1] == 1.0
    assert np.all(np.diff(concentration) >= -1.0e-13)
    assert np.all(concentration[:-1] < 1.0)
    tiny = 1.0e-9
    tiny_concentration = float(
        model._arctic_concentration_from_equivalent_thickness(tiny)
    )
    assert tiny / tiny_concentration == pytest.approx(thin, rel=1.0e-6)

    targets = np.asarray([0.01, 0.05, 0.25, 0.50, 0.90, 0.99])
    restored = model._arctic_equivalent_thickness_from_concentration(targets)
    round_trip = model._arctic_concentration_from_equivalent_thickness(restored)
    np.testing.assert_allclose(round_trip, targets, rtol=0.0, atol=2.0e-10)


def test_compactness_uses_a_bounded_young_ice_correction() -> None:
    model = _mapping_model()
    equivalent = np.asarray([0.25, 0.5, 1.0, 2.0, 3.0])
    full = model.config.arctic_full_cover_equivalent_thickness_m
    exponent = model.config.arctic_ice_concentration_exponent
    pack = 1.0 - np.power(1.0 - equivalent / full, exponent)
    actual = model._arctic_concentration_from_equivalent_thickness(equivalent)
    correction = actual - pack

    # The low-volume correction may increase area relative to the mature-pack
    # branch, but it is bounded by thin/full and decays as the pack matures.
    assert np.all(correction > 0.0)
    assert np.all(correction <= model.config.arctic_new_ice_local_thickness_m / full)
    assert np.all(np.diff(correction) < 0.0)
    assert model._arctic_concentration_from_equivalent_thickness(
        np.asarray([full])
    )[0] == pytest.approx(1.0)


def test_reference_cache_identity_includes_longwave_damping() -> None:
    ProcessClimateModel.clear_arctic_reference_cycle_cache()
    common = dict(
        resolution_deg=10.0,
        duration_years=1.0,
        dt_years=0.1,
        record_every_years=0.1,
        auto_initialize_from_1850=False,
    )
    undamped = ProcessClimateModel(
        replace(ModelConfig(), arctic_interface_longwave_damping_wm2_k=0.0, **common)
    )
    first_info = ProcessClimateModel.arctic_reference_cycle_cache_info()
    damped = ProcessClimateModel(
        replace(ModelConfig(), arctic_interface_longwave_damping_wm2_k=4.5, **common)
    )
    second_info = ProcessClimateModel.arctic_reference_cycle_cache_info()
    assert first_info["entries"] == 1
    assert second_info["entries"] == 2
    assert not np.array_equal(
        undamped.arctic_reference_atlantic_ice_fraction,
        damped.arctic_reference_atlantic_ice_fraction,
    )


def test_each_co2_target_has_independent_survival_gate() -> None:
    with pytest.raises(RuntimeError, match="2200 ppm failed its independent"):
        validate_target_survival_counts(
            [150.0, 300.0, 2200.0],
            [16, 16, 0],
            requested_members=16,
        )


def test_quantitative_target_count_requires_explicit_exploratory_override() -> None:
    with pytest.raises(RuntimeError, match="declared quantitative member count"):
        validate_target_survival_counts(
            [300.0, 600.0],
            [20, 19],
            requested_members=20,
        )
    diagnostics = validate_target_survival_counts(
        [300.0, 600.0],
        [20, 19],
        requested_members=20,
        allow_exploratory_target_counts=True,
    )
    assert [item["successful_members"] for item in diagnostics] == [20, 19]


def test_requested_subquantitative_sweep_remains_explicitly_exploratory() -> None:
    diagnostics = validate_target_survival_counts(
        [300.0, 600.0],
        [16, 13],
        requested_members=16,
    )
    assert all(item["failed_fraction"] <= 0.20 for item in diagnostics)


def test_winter_transport_index_rejects_warm_dark_shoulder_season() -> None:
    model = _mapping_model(
        arctic_winter_transport_temperature_scale_c=15.0,
    )
    darkness = np.asarray([0.60, 0.60, 0.95])
    reference_air = np.asarray([-10.0, -2.7, 0.0])
    weight = model._arctic_winter_transport_weight(reference_air, reference_air, darkness)
    assert weight[0] > 5.0 * weight[1]
    assert weight[2] == pytest.approx(0.0)
    assert np.all((weight >= 0.0) & (weight <= 1.0))


def test_winter_transport_temperature_scale_must_be_positive() -> None:
    with pytest.raises(ValueError, match="temperature_scale_c must be positive"):
        replace(
            ModelConfig(),
            arctic_winter_transport_temperature_scale_c=0.0,
        ).validate()


def test_compactness_controls_are_public_cli_inputs() -> None:
    args = build_parser().parse_args(
        [
            "--arctic-full-cover-equivalent-thickness",
            "3.7",
            "--arctic-ice-concentration-exponent",
            "2.0",
        ]
    )
    assert args.arctic_full_cover_equivalent_thickness == pytest.approx(3.7)
    assert args.arctic_ice_concentration_exponent == pytest.approx(2.0)


def test_review_corrected_status_is_generated_only_after_complete_evidence() -> None:
    root = Path(__file__).resolve().parents[1]
    finalizer = (root / "tools/finalize_v22922_status.py").read_text(encoding="utf-8")
    runner = (root / "run_v22922_engineering_tests.py").read_text(encoding="utf-8")

    assert 'CANONICAL_STATUS = "PACKAGE_STATUS_V2_29_22.json"' in finalizer
    assert 'COMPATIBILITY_STATUS = "REVIEW_CORRECTED_STATUS.json"' in finalizer
    assert 'TEST_JSON = "TEST_RESULTS_V2_29_22.json"' in finalizer
    assert 'SUMMARY_JSON = "VALIDATION_SUMMARY_V2_29_22.json"' in finalizer
    assert 'if tests.get("failed") != 0 or tests.get("pytest_exit_code") != 0:' in finalizer
    assert 'if release.get("release_classification") != "engineering_only":' in finalizer
    assert 'if release.get("scientific_release_passed") is not False:' in finalizer
    assert 'for name in (CANONICAL_STATUS, COMPATIBILITY_STATUS):' in finalizer
    assert "REVIEW_CORRECTED_STATUS.json" not in runner

    status_path = root / "REVIEW_CORRECTED_STATUS.json"
    if status_path.exists():
        status = json.loads(status_path.read_text(encoding="utf-8"))
        assert status["model_version"] == MODEL_VERSION
        assert status["release_classification"] == "engineering_only"
        assert status["scientific_release_passed"] is False
        assert status["full_period_validation"]["status"] == "complete"
        assert status["complete_non_slow_test_suite"]["status"] == "complete"
        assert status["complete_non_slow_test_suite"]["failed"] == 0

    assert not (root / "VALIDATION_SUMMARY_V2_29_20.json").exists()
