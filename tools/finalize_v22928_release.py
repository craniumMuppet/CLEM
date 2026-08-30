#!/usr/bin/env python3
"""Verify and deterministically package the finalized EGCM v2.29.28 release."""
from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v22928_release_integrity import (  # noqa: E402
    FINGERPRINT_JSON,
    MANIFEST,
    MODEL_VERSION,
    PACKAGE_INFO,
    PACKAGE_NAME,
    ROOT,
    TEST_EVENTS,
    TEST_JUNIT,
    TEST_JSON,
    artifact_bundle_payload,
    build_file_records,
    load_json,
    sha256_file,
    verify_fingerprint_payload,
)
from arctic_validation_stack import validation_stack_status  # noqa: E402

RECALIBRATION_JSON = "ARCTIC_OBSERVATIONAL_RECALIBRATION_10DEG_2026.json"
RETROSPECTIVE_JSON = "RETROSPECTIVE_FOLD_LOCAL_ARCTIC_HINDCAST_V2_29_28.json"
COUPLED_SUMMARY_JSON = "VALIDATION_SUMMARY_V2_29_28.json"
COUPLED_RESOLUTION_JSONS = tuple(
    name
    for resolution in (5, 10)
    for name in (
        f"SEA_ICE_VALIDATION_V2_29_28_{resolution}DEG.json",
        f"ARCTIC_GREENLAND_AMOC_VALIDATION_V2_29_28_{resolution}DEG.json",
    )
)
COUPLED_TIMESERIES = tuple(
    f"COUPLED_TIMESERIES_V2_29_28_{resolution}DEG.csv" for resolution in (5, 10)
)
COUPLED_BUNDLE_MEMBERS = (*COUPLED_RESOLUTION_JSONS, *COUPLED_TIMESERIES)
DECLARED_PYTEST_REQUIREMENT = "pytest==9.1.1"


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
    for name in (
        TEST_JSON,
        FINGERPRINT_JSON,
        RECALIBRATION_JSON,
        RETROSPECTIVE_JSON,
        COUPLED_SUMMARY_JSON,
        *COUPLED_RESOLUTION_JSONS,
    ):
        if not (ROOT / name).is_file():
            raise SystemExit(f"Missing required release evidence: {name}")


def verify_coupled_evidence(tests: dict[str, Any]) -> dict[str, Any]:
    """Reject incomplete, failed, stale, or cross-resolution-free evidence."""

    summary = load_json(ROOT / COUPLED_SUMMARY_JSON)
    if summary.get("model_version") != MODEL_VERSION:
        raise SystemExit("Coupled summary model_version mismatch")
    if summary.get("validation_type") != "version_matched_production_default":
        raise SystemExit("Coupled summary validation_type mismatch")
    required_true = {
        "coupled_validation_complete": summary.get("coupled_validation_complete"),
        "version_matched_arctic_greenland_amoc_validation_complete": summary.get(
            "version_matched_arctic_greenland_amoc_validation_complete"
        ),
        "cross_resolution_validation_passed": summary.get(
            "cross_resolution_validation_passed"
        ),
        "historical_calibration_passed": summary.get("historical_calibration_passed"),
        "recent_period_evaluation_passed": summary.get(
            "recent_period_evaluation_passed"
        ),
        "structural_area_volume_validation_passed": summary.get(
            "structural_area_volume_validation_passed"
        ),
        "amoc_validation_passed": summary.get("amoc_validation_passed"),
    }
    failed = [name for name, value in required_true.items() if value is not True]
    if failed:
        raise SystemExit("Coupled summary contains failed/incomplete gates: " + ", ".join(failed))
    if summary.get("resolutions_deg") != [5.0, 10.0]:
        raise SystemExit("Coupled summary must contain exact 5-degree and 10-degree runs")
    cross = summary.get("cross_resolution", {})
    if cross.get("passed") is not True or not cross.get("gates"):
        raise SystemExit("Coupled summary lacks passing cross-resolution comparisons")
    if not all(value is True for value in cross["gates"].values()):
        raise SystemExit("One or more cross-resolution gates failed")
    if summary.get("test_results") != tests:
        raise SystemExit("Coupled summary is not bound to the current engineering-test evidence")

    expected_bundle = summary.get("canonical_artifact_bundle")
    if not isinstance(expected_bundle, dict):
        raise SystemExit("Coupled summary lacks the canonical artifact bundle")
    actual_bundle = artifact_bundle_payload(ROOT, COUPLED_BUNDLE_MEMBERS)
    if expected_bundle != actual_bundle:
        raise SystemExit("Coupled canonical artifact bundle is incomplete, mixed, or stale")

    expected_hashes = summary.get("source_hashes")
    if not isinstance(expected_hashes, dict) or not expected_hashes:
        raise SystemExit("Coupled summary lacks source hashes")
    for relative, expected in expected_hashes.items():
        source = ROOT / relative
        if not source.is_file() or sha256_file(source) != expected:
            raise SystemExit(f"Coupled source hash is stale or missing: {relative}")

    for name in COUPLED_RESOLUTION_JSONS:
        payload = load_json(ROOT / name)
        if payload.get("model_version") != MODEL_VERSION:
            raise SystemExit(f"Coupled evidence model_version mismatch: {name}")
        if payload.get("validation_type") != "version_matched_production_default":
            raise SystemExit(f"Coupled evidence validation_type mismatch: {name}")
        if payload.get("source_hashes") != expected_hashes:
            raise SystemExit(f"Coupled evidence source hashes mismatch: {name}")
        if payload.get("validation_passed") is not True:
            raise SystemExit(f"Coupled evidence is not a passing canonical run: {name}")
        if name.startswith("ARCTIC_GREENLAND"):
            if payload.get("coupled", {}).get("passed") is not True:
                raise SystemExit(f"Coupled gates failed: {name}")
            if payload.get("structural_area_volume_experiments", {}).get("passed") is not True:
                raise SystemExit(f"Structural area/volume gates failed: {name}")
        else:
            sea_summary = payload.get("summary", {})
            if not all(
                sea_summary.get(key) is True
                for key in (
                    "calibration_passed",
                    "recent_period_evaluation_passed",
                    "all_engineering_gates_passed",
                )
            ):
                raise SystemExit(f"Sea-ice gates failed: {name}")
    return summary


def verify_test_evidence() -> dict[str, Any]:
    tests = load_json(ROOT / TEST_JSON)
    if tests.get("model_version") != MODEL_VERSION:
        raise SystemExit("Test evidence model_version mismatch")
    if tests.get("schema_version") != 4:
        raise SystemExit("Test evidence schema_version mismatch")
    if tests.get("declared_pytest_requirement") != DECLARED_PYTEST_REQUIREMENT:
        raise SystemExit("Test evidence pytest requirement mismatch")
    if tests.get("pytest_version") != DECLARED_PYTEST_REQUIREMENT.split("==", 1)[1]:
        raise SystemExit("Test evidence was generated with the wrong pytest version")
    counts = {
        name: int(tests.get(name, -1))
        for name in ("collected", "completed", "passed", "failed", "errors", "skipped", "xfailed", "xpassed")
    }
    if counts["collected"] <= 0 or counts["completed"] != counts["collected"]:
        raise SystemExit("Test evidence has no complete executed inventory")
    if counts["passed"] <= 0 or counts["failed"] or counts["errors"]:
        raise SystemExit("Test evidence contains no passes or contains failures/errors")
    if sum(counts[name] for name in ("passed", "failed", "errors", "skipped", "xfailed", "xpassed")) != counts["completed"]:
        raise SystemExit("Test evidence outcome counts do not sum to completed tests")
    if tests.get("pytest_exit_code") != 0 or tests.get("runner_exit_code") != 0:
        raise SystemExit("Test evidence records a nonzero pytest/runner exit code")
    if tests.get("complete") is not True or tests.get("engineering_integrity_passed") is not True:
        raise SystemExit("Engineering-test evidence is not passing and complete")
    if tests.get("tree_unchanged_during_pytest") is not True:
        raise SystemExit("Tests did not execute on one unchanged release tree")
    if not tests.get("runner_command") or not tests.get("pytest_args"):
        raise SystemExit("Test evidence lacks the exact runner selection")
    outcomes = tests.get("outcomes")
    nodeids = tests.get("nodeids")
    if not isinstance(outcomes, list) or not isinstance(nodeids, list):
        raise SystemExit("Test evidence lacks machine-generated outcomes/node IDs")
    if len(outcomes) != counts["collected"] or len(nodeids) != counts["collected"]:
        raise SystemExit("Test outcome or node-ID inventory is incomplete")
    event_nodeids = [str(event.get("nodeid", "")) for event in outcomes]
    if nodeids != event_nodeids or any(not nodeid for nodeid in nodeids):
        raise SystemExit("Test node IDs do not match the outcome inventory")
    if len(set(nodeids)) != len(nodeids):
        raise SystemExit("Test evidence contains duplicate node IDs")
    if [event.get("sequence") for event in outcomes] != list(range(1, counts["collected"] + 1)):
        raise SystemExit("Test outcome sequence is not contiguous")

    raw = tests.get("raw_evidence")
    if not isinstance(raw, dict) or set(raw) != {TEST_EVENTS, TEST_JUNIT}:
        raise SystemExit("Raw test-evidence set mismatch")
    resolved: dict[str, Path] = {}
    for name, metadata in raw.items():
        path = ROOT / name
        resolved[name] = path
        if not path.is_file():
            raise SystemExit(f"Missing raw test evidence: {name}")
        if path.stat().st_size != int(metadata.get("size_bytes", -1)):
            raise SystemExit(f"Raw test-evidence size mismatch: {name}")
        if sha256_file(path) != metadata.get("sha256"):
            raise SystemExit(f"Raw test-evidence hash mismatch: {name}")
    events = [
        json.loads(line)
        for line in resolved[TEST_EVENTS].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if events != outcomes:
        raise SystemExit("NDJSON events do not match the JSON outcome inventory")
    try:
        xml_root = ElementTree.parse(resolved[TEST_JUNIT]).getroot()
    except ElementTree.ParseError as exc:
        raise SystemExit(f"Invalid JUnit XML: {exc}") from exc
    suites = [xml_root] if xml_root.tag == "testsuite" else list(xml_root.findall("testsuite"))
    if not suites:
        suites = list(xml_root.findall(".//testsuite"))
    if not suites:
        raise SystemExit("JUnit XML contains no test suites")
    junit_counts = {
        key: sum(int(suite.attrib.get(key, 0)) for suite in suites)
        for key in ("tests", "failures", "errors", "skipped")
    }
    if junit_counts["tests"] != counts["collected"]:
        raise SystemExit("JUnit test count does not match JSON evidence")
    if junit_counts["failures"] != counts["failed"] or junit_counts["errors"] != counts["errors"]:
        raise SystemExit("JUnit failure/error counts do not match JSON evidence")
    if junit_counts["skipped"] != counts["skipped"] + counts["xfailed"]:
        raise SystemExit("JUnit skipped count does not match JSON evidence")

    tree_fingerprint = tests.get("release_tree_fingerprint")
    if not isinstance(tree_fingerprint, dict):
        raise SystemExit("Test evidence lacks its release-tree fingerprint")
    errors = verify_fingerprint_payload(tree_fingerprint)
    if errors:
        detail = "\n".join(f"- {error}" for error in errors[:20])
        raise SystemExit(f"Test-bound release-tree fingerprint mismatch:\n{detail}")
    return tests


def verify_tested_fingerprint(tests: dict[str, Any]) -> dict[str, Any]:
    payload = load_json(ROOT / FINGERPRINT_JSON)
    if payload != tests.get("release_tree_fingerprint"):
        raise SystemExit("Standalone tested-code fingerprint does not match test evidence")
    errors = verify_fingerprint_payload(payload)
    if errors:
        detail = "\n".join(f"- {error}" for error in errors[:20])
        raise SystemExit(f"Tested-code fingerprint mismatch; refusing to package:\n{detail}")
    return payload


def derived_arctic_status(tests: dict[str, Any]) -> dict[str, Any]:
    recal = load_json(ROOT / RECALIBRATION_JSON)
    retrospective = load_json(ROOT / RETROSPECTIVE_JSON)
    stack = validation_stack_status()
    physical = recal.get("physical_volume_thickness_validation", {})
    osi = recal.get("osi_saf_development_crosscheck", {})
    prospective_complete = bool(recal.get("prospective_untouched_validation_complete", False))
    coupled = verify_coupled_evidence(tests)
    return {
        "calibration_passed": bool(recal.get("calibration_passed", False)),
        "development_evaluation_passed": bool(
            recal.get("validation_informed_development_evaluation_passed", False)
        ),
        "physical_volume_thickness_mean_state_constraints_passed": bool(
            physical.get("mean_state_constraints_passed", False)
        ),
        "physical_volume_thickness_temporal_response_passed": bool(
            physical.get("temporal_response_validation_passed", False)
        ),
        "physical_volume_thickness_gate_passed": bool(
            physical.get("scientific_volume_thickness_validation_complete", False)
        ),
        "osi_saf_development_diagnostic_independent": bool(osi.get("independent_crosscheck", False)),
        "osi_saf_march_development_rmse_le_1p00": bool(
            osi.get("months", {}).get("3", {}).get("rmse_le_1p00_million_km2", False)
        ),
        "osi_saf_september_development_rmse_le_1p00": bool(
            osi.get("months", {}).get("9", {}).get("rmse_le_1p00_million_km2", False)
        ),
        "nsidc_0611_available": bool(stack.get("ice_age_structural_diagnostic_available", False)),
        "retrospective_fold_local_hindcasts_run": bool(retrospective.get("all_folds_scored", False)),
        "retrospective_predictive_skill_gate_passed": bool(
            retrospective.get("scientific_predictive_skill_claim_allowed", False)
        ),
        "prospective_untouched_validation_complete": prospective_complete,
        "version_matched_arctic_greenland_amoc_validation_complete": bool(
            coupled["version_matched_arctic_greenland_amoc_validation_complete"]
        ),
        "scientific_predictive_validation_complete": bool(
            recal.get("scientific_validation_complete", False)
        ),
    }


def write_package_info(tests: dict[str, Any], fingerprint: dict[str, Any]) -> dict[str, Any]:
    status = derived_arctic_status(tests)
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
            "verified_against_test_execution_and_final_archive": True,
        },
        "arctic_scientific_status": status,
        "scientific_status_sources": [RECALIBRATION_JSON, RETROSPECTIVE_JSON],
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


def verify_archive(archive_path: Path, manifest: dict[str, Any]) -> None:
    """Verify inventory, manifest hashes, and test-bound fingerprint in the ZIP."""

    prefix = f"{PACKAGE_NAME}/"
    records = {row["path"]: row for row in manifest["files"]}
    expected_names = {prefix + name for name in records} | {prefix + MANIFEST}
    with zipfile.ZipFile(archive_path) as archive:
        actual_names = set(archive.namelist())
        if actual_names != expected_names:
            raise SystemExit("Final ZIP inventory does not match the package manifest")
        for name, record in records.items():
            data = archive.read(prefix + name)
            if len(data) != int(record["size_bytes"]):
                raise SystemExit(f"Final ZIP size mismatch: {name}")
            if hashlib.sha256(data).hexdigest() != record["sha256"]:
                raise SystemExit(f"Final ZIP SHA-256 mismatch: {name}")
        archived_manifest = json.loads(archive.read(prefix + MANIFEST))
        if archived_manifest != manifest:
            raise SystemExit("Final ZIP contains the wrong manifest")
        tests = json.loads(archive.read(prefix + TEST_JSON))
        fingerprint = json.loads(archive.read(prefix + FINGERPRINT_JSON))
        if fingerprint != tests.get("release_tree_fingerprint"):
            raise SystemExit("Final ZIP fingerprint is not bound to its test evidence")
        for name, record in fingerprint.get("files", {}).items():
            data = archive.read(prefix + name)
            if len(data) != int(record["size_bytes"]):
                raise SystemExit(f"Final ZIP tested-tree size mismatch: {name}")
            if hashlib.sha256(data).hexdigest() != record["sha256"]:
                raise SystemExit(f"Final ZIP contains untested bytes: {name}")


def build_deterministic_zip(manifest: dict[str, Any]) -> Path:
    destination = ROOT.parent / f"{PACKAGE_NAME}.zip"
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()
    records = {row["path"]: row for row in manifest["files"]}
    try:
        with zipfile.ZipFile(
            temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as archive:
            for name in sorted(records):
                path = ROOT / name
                data = path.read_bytes()
                record = records[name]
                if len(data) != int(record["size_bytes"]) or hashlib.sha256(data).hexdigest() != record["sha256"]:
                    raise SystemExit(f"Release tree changed after manifest creation: {name}")
                rel = Path(PACKAGE_NAME) / name
                info = zipfile.ZipInfo(rel.as_posix(), date_time=(2026, 8, 21, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
            manifest_data = (ROOT / MANIFEST).read_bytes()
            rel = Path(PACKAGE_NAME) / MANIFEST
            info = zipfile.ZipInfo(rel.as_posix(), date_time=(2026, 8, 21, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, manifest_data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        verify_archive(temporary, manifest)
        temporary.replace(destination)
    except BaseException:
        if temporary.exists():
            temporary.unlink()
        raise
    sha_path = destination.with_suffix(destination.suffix + ".sha256")
    sha_temporary = sha_path.with_suffix(sha_path.suffix + ".tmp")
    sha_temporary.write_text(
        f"{sha256_file(destination)}  {destination.name}\n", encoding="ascii"
    )
    sha_temporary.replace(sha_path)
    return destination


def main() -> None:
    verify_identity()
    tests = verify_test_evidence()
    fingerprint = verify_tested_fingerprint(tests)
    verify_coupled_evidence(tests)
    info = write_package_info(tests, fingerprint)
    manifest = write_manifest()
    archive = build_deterministic_zip(manifest)
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
