#!/usr/bin/env python3
"""Verify and deterministically package the finalized EGCM v2.29.27 release."""
from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v22927_release_integrity import (  # noqa: E402
    FINGERPRINT_JSON,
    MANIFEST,
    MODEL_VERSION,
    PACKAGE_INFO,
    PACKAGE_NAME,
    ROOT,
    TEST_JSON,
    build_file_records,
    iter_project_files,
    load_json,
    sha256_file,
    verify_fingerprint_payload,
)
from arctic_validation_stack import validation_stack_status  # noqa: E402

RECALIBRATION_JSON = "ARCTIC_OBSERVATIONAL_RECALIBRATION_10DEG_2026.json"
NESTED_JSON = "NESTED_ARCTIC_HINDCAST_V2_29_27.json"


def verify_identity() -> None:
    if ROOT.name != PACKAGE_NAME:
        raise SystemExit(f"Release root must be named {PACKAGE_NAME!r}, got {ROOT.name!r}")
    required_text = [
        (ROOT / "climate_model.py", f'MODEL_VERSION = "{MODEL_VERSION}"'),
        (ROOT / "pyproject.toml", f'version = "{MODEL_VERSION}"'),
        (ROOT / "README.md", f"# Coupled Low-complexity Earth Model v{MODEL_VERSION}"),
        (ROOT / "CHANGELOG.md", f"## {MODEL_VERSION}"),
        (ROOT / "SCIENTIFIC_CONSTRAINTS.md", f"# Scientific constraints used by v{MODEL_VERSION}"),
    ]
    for path, needle in required_text:
        if needle not in path.read_text(encoding="utf-8"):
            raise SystemExit(f"Release identity mismatch in {path.name}: missing {needle!r}")
    for name in (TEST_JSON, FINGERPRINT_JSON, RECALIBRATION_JSON, NESTED_JSON):
        if not (ROOT / name).is_file():
            raise SystemExit(f"Missing required release evidence: {name}")


def verify_test_evidence() -> dict[str, Any]:
    tests = load_json(ROOT / TEST_JSON)
    if tests.get("model_version") != MODEL_VERSION:
        raise SystemExit("Test evidence model_version mismatch")
    if int(tests.get("failed", 0)) or int(tests.get("errors", 0)):
        raise SystemExit("Test evidence contains failures/errors")
    if not tests.get("pytest_version"):
        raise SystemExit("Test evidence does not record pytest_version")
    if not tests.get("commands"):
        raise SystemExit("Test evidence does not record exact test commands")
    if not tests.get("nodeids"):
        raise SystemExit("Test evidence does not record exact selected node IDs")
    return tests


def verify_tested_fingerprint() -> dict[str, Any]:
    payload = load_json(ROOT / FINGERPRINT_JSON)
    errors = verify_fingerprint_payload(payload)
    if errors:
        detail = "\n".join(f"- {error}" for error in errors[:20])
        raise SystemExit(f"Tested-code fingerprint mismatch; refusing to package:\n{detail}")
    return payload


def derived_arctic_status() -> dict[str, Any]:
    recal = load_json(ROOT / RECALIBRATION_JSON)
    nested = load_json(ROOT / NESTED_JSON)
    stack = validation_stack_status()
    physical = recal.get("physical_volume_thickness_validation", {})
    osi = recal.get("osi_saf_independent_crosscheck", {})
    prospective = recal.get("prospective_untouched_validation", {})
    return {
        "calibration_passed": bool(recal.get("calibration_passed", False)),
        "development_evaluation_passed": bool(
            recal.get("validation_informed_development_evaluation_passed", False)
        ),
        "physical_volume_thickness_gate_passed": bool(physical.get("passed", False)),
        "osi_saf_march_independent_gate_passed": bool(
            osi.get("months", {}).get("3", {}).get("rmse_le_1p00_million_km2", False)
        ),
        "osi_saf_september_independent_gate_passed": bool(
            osi.get("months", {}).get("9", {}).get("rmse_le_1p00_million_km2", False)
        ),
        "nsidc_0611_available": bool(stack.get("ice_age_structural_diagnostic_available", False)),
        "nested_fold_specific_hindcasts_run": bool(nested.get("all_folds_scored", False)),
        "nested_predictive_skill_gate_passed": bool(
            nested.get("scientific_predictive_skill_claim_allowed", False)
        ),
        "prospective_untouched_validation_complete": bool(prospective.get("complete", False)),
        "scientific_predictive_validation_complete": bool(
            recal.get("scientific_validation_complete", False)
        ),
    }


def write_package_info(tests: dict[str, Any], fingerprint: dict[str, Any]) -> dict[str, Any]:
    status = derived_arctic_status()
    payload = {
        "model_version": MODEL_VERSION,
        "package_name": PACKAGE_NAME,
        "release_classification": (
            "engineering_release_with_observational_recalibration; "
            "scientific_predictive_validation_incomplete"
        ),
        "test_evidence": {
            "file": TEST_JSON,
            "passed": tests.get("passed"),
            "failed": tests.get("failed"),
            "errors": tests.get("errors"),
            "python_version": tests.get("python_version"),
            "pytest_version": tests.get("pytest_version"),
            "nodeid_count": len(tests.get("nodeids", [])),
        },
        "tested_code_fingerprint": {
            "file": FINGERPRINT_JSON,
            "aggregate_sha256": fingerprint["aggregate_sha256"],
            "file_count": fingerprint["file_count"],
            "profile": fingerprint["profile"],
            "verified_immediately_before_packaging": True,
        },
        "arctic_scientific_status": status,
        "scientific_status_sources": [RECALIBRATION_JSON, NESTED_JSON],
    }
    (ROOT / PACKAGE_INFO).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return payload


def write_manifest() -> dict[str, Any]:
    records, aggregate = build_file_records(fingerprint_profile=False)
    rows = [
        {"path": path, "sha256": values["sha256"], "size_bytes": values["size_bytes"]}
        for path, values in records.items()
    ]
    payload = {
        "model_version": MODEL_VERSION,
        "package_name": PACKAGE_NAME,
        "algorithm": "sha256",
        "manifest_excludes_itself": True,
        "file_count": len(rows),
        "aggregate_sha256": aggregate,
        "files": rows,
    }
    (ROOT / MANIFEST).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return payload


def build_deterministic_zip() -> Path:
    destination = ROOT.parent / f"{PACKAGE_NAME}.zip"
    if destination.exists():
        destination.unlink()
    files = iter_project_files(fingerprint_profile=False) + [ROOT / MANIFEST]
    files = sorted(set(files), key=lambda path: path.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(
        destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in files:
            rel = Path(PACKAGE_NAME) / path.relative_to(ROOT)
            info = zipfile.ZipInfo(rel.as_posix(), date_time=(2026, 8, 19, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(
                info,
                path.read_bytes(),
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )
    sha_path = destination.with_suffix(destination.suffix + ".sha256")
    sha_path.write_text(f"{sha256_file(destination)}  {destination.name}\n", encoding="ascii")
    return destination


def main() -> None:
    verify_identity()
    tests = verify_test_evidence()
    fingerprint = verify_tested_fingerprint()
    info = write_package_info(tests, fingerprint)
    manifest = write_manifest()
    archive = build_deterministic_zip()
    print(f"Packaged {MODEL_VERSION}: {archive}")
    print(f"Files: {manifest['file_count']}")
    print(f"Manifest aggregate: {manifest['aggregate_sha256']}")
    print(f"Archive SHA-256: {sha256_file(archive)}")
    print(
        "Scientific predictive validation complete:",
        info["arctic_scientific_status"]["scientific_predictive_validation_complete"],
    )


if __name__ == "__main__":
    main()
