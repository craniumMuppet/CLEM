"""Regression tests for the v2.29.28 coupled-validation trust boundary."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from combine_v22923_validation import resolution_payload
from tools import finalize_v22928_release as finalizer
from tools.v22928_release_integrity import artifact_bundle_payload


def _write(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_resolution_loader_rejects_failed_coupled_run(tmp_path: Path) -> None:
    shared = {
        "model_version": "2.29.28",
        "validation_type": "version_matched_production_default",
        "source_hashes": {"climate_model.py": "not-used-in-loader"},
    }
    _write(
        tmp_path / "SEA_ICE_VALIDATION_V2_29_28_5DEG.json",
        {**shared, "validation_passed": True},
    )
    _write(
        tmp_path / "ARCTIC_GREENLAND_AMOC_VALIDATION_V2_29_28_5DEG.json",
        {
            **shared,
            "validation_passed": False,
            "coupled": {"passed": False},
            "structural_area_volume_experiments": {"passed": True},
        },
    )
    with pytest.raises(SystemExit, match="Coupled validation failed"):
        resolution_payload(
            tmp_path,
            "5",
            model_version="2.29.28",
            artifact_tag="V2_29_28",
        )


def test_finalizer_rejects_two_failed_coupled_files_even_if_summary_claims_complete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "climate_model.py"
    source.write_text("current physics", encoding="utf-8")
    source_hashes = {
        source.name: hashlib.sha256(source.read_bytes()).hexdigest(),
    }
    tests = {"bound_test_evidence": True}
    summary = {
        "model_version": "2.29.28",
        "validation_type": "version_matched_production_default",
        "coupled_validation_complete": True,
        "version_matched_arctic_greenland_amoc_validation_complete": True,
        "cross_resolution_validation_passed": True,
        "historical_calibration_passed": True,
        "recent_period_evaluation_passed": True,
        "structural_area_volume_validation_passed": True,
        "amoc_validation_passed": True,
        "resolutions_deg": [5.0, 10.0],
        "cross_resolution": {"passed": True, "gates": {"example": True}},
        "source_hashes": source_hashes,
        "test_results": tests,
    }
    _write(tmp_path / finalizer.COUPLED_SUMMARY_JSON, summary)
    shared = {
        "model_version": "2.29.28",
        "validation_type": "version_matched_production_default",
        "source_hashes": source_hashes,
    }
    for resolution in (5, 10):
        _write(
            tmp_path / f"SEA_ICE_VALIDATION_V2_29_28_{resolution}DEG.json",
            {
                **shared,
                "validation_passed": True,
                "summary": {
                    "calibration_passed": True,
                    "recent_period_evaluation_passed": True,
                    "all_engineering_gates_passed": True,
                },
            },
        )
        _write(
            tmp_path
            / f"ARCTIC_GREENLAND_AMOC_VALIDATION_V2_29_28_{resolution}DEG.json",
            {
                **shared,
                "validation_passed": False,
                "coupled": {"passed": False},
                "structural_area_volume_experiments": {"passed": True},
            },
        )
        (tmp_path / f"COUPLED_TIMESERIES_V2_29_28_{resolution}DEG.csv").write_text(
            "year,value\n2100,1\n", encoding="utf-8"
        )
    bundle_members = (
        *finalizer.COUPLED_RESOLUTION_JSONS,
        *finalizer.COUPLED_TIMESERIES,
    )
    summary["canonical_artifact_bundle"] = artifact_bundle_payload(
        tmp_path, bundle_members
    )
    _write(tmp_path / finalizer.COUPLED_SUMMARY_JSON, summary)
    monkeypatch.setattr(finalizer, "ROOT", tmp_path)
    with pytest.raises(SystemExit, match="not a passing canonical run"):
        finalizer.verify_coupled_evidence(tests)


def test_finalizer_rejects_fabricated_or_zero_test_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(
        tmp_path / finalizer.TEST_JSON,
        {
            "model_version": "2.29.28",
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "pytest_version": "made-up",
            "commands": ["not a real command"],
            "nodeids": ["not::a_test"],
        },
    )
    monkeypatch.setattr(finalizer, "ROOT", tmp_path)
    with pytest.raises(SystemExit, match="schema_version"):
        finalizer.verify_test_evidence()


def test_finalizer_rejects_mixed_canonical_artifact_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in (*finalizer.COUPLED_RESOLUTION_JSONS, *finalizer.COUPLED_TIMESERIES):
        (tmp_path / name).write_text("original", encoding="utf-8")
    expected = artifact_bundle_payload(
        tmp_path, (*finalizer.COUPLED_RESOLUTION_JSONS, *finalizer.COUPLED_TIMESERIES)
    )
    first = tmp_path / finalizer.COUPLED_RESOLUTION_JSONS[0]
    first.write_text("new generation", encoding="utf-8")
    actual = artifact_bundle_payload(
        tmp_path, (*finalizer.COUPLED_RESOLUTION_JSONS, *finalizer.COUPLED_TIMESERIES)
    )
    assert actual != expected


def test_current_coupled_entry_points_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    assert (root / "validate_v22928.py").is_file()
    assert (root / "combine_v22928_validation.py").is_file()
    assert (root / "validate_v22928_coupled.py").is_file()
    wrapper = (root / "validate_v22928_coupled.py").read_text(encoding="utf-8")
    assert "canonical_artifact_bundle" in wrapper
    assert "destination.unlink()" not in wrapper
