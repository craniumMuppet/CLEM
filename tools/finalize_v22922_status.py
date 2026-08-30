#!/usr/bin/env python3
"""Create canonical relocation-safe v2.29.22 engineering-only status files."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

MODEL_VERSION = "2.29.22"
ROOT = Path(__file__).resolve().parents[1]
CANONICAL_STATUS = "PACKAGE_STATUS_V2_29_22.json"
COMPATIBILITY_STATUS = "REVIEW_CORRECTED_STATUS.json"
TEST_JSON = "TEST_RESULTS_V2_29_22.json"
SUMMARY_JSON = "VALIDATION_SUMMARY_V2_29_22.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_relative_path(name: str) -> Path:
    path = Path(name)
    if path.is_absolute() or ".." in path.parts:
        raise SystemExit(f"Fingerprint path must be package-relative: {name}")
    return path


def verify_source_hashes(root: Path, expected: dict[str, str]) -> None:
    resolved: dict[str, Path] = {
        name: root / canonical_relative_path(name) for name in expected
    }
    missing = [name for name, path in resolved.items() if not path.is_file()]
    if missing:
        raise SystemExit(f"Missing fingerprinted source files: {missing}")
    mismatches = {
        name: {"expected": expected[name], "actual": sha256(path)}
        for name, path in resolved.items()
        if sha256(path) != expected[name]
    }
    if mismatches:
        raise SystemExit(
            "Validation evidence does not match the current source tree: "
            + json.dumps(mismatches, sort_keys=True)
        )


def verify_raw_test_evidence(root: Path, tests: dict[str, Any]) -> None:
    raw = tests.get("raw_evidence", {})
    events_name = "TEST_EVENTS_V2_29_22.ndjson"
    junit_name = "TEST_RESULTS_V2_29_22.junit.xml"
    required = {events_name, junit_name}
    if set(raw) != required:
        raise SystemExit(f"Raw test evidence set mismatch: {sorted(raw)}")
    resolved: dict[str, Path] = {}
    for name, metadata in raw.items():
        path = root / canonical_relative_path(name)
        resolved[name] = path
        if not path.is_file():
            raise SystemExit(f"Missing raw test evidence: {name}")
        if path.stat().st_size != int(metadata["size_bytes"]):
            raise SystemExit(f"Raw test evidence size mismatch: {name}")
        if sha256(path) != metadata["sha256"]:
            raise SystemExit(f"Raw test evidence hash mismatch: {name}")

    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        resolved[events_name].read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(
                f"Invalid NDJSON test event at line {line_number}: {exc}"
            ) from exc
        if not isinstance(event, dict):
            raise SystemExit(f"NDJSON test event {line_number} is not an object")
        events.append(event)
    if events != tests.get("outcomes", []):
        raise SystemExit("NDJSON test events do not match the JSON outcome inventory")
    if len(events) != int(tests["collected"]):
        raise SystemExit("NDJSON test event count does not match collected tests")
    if [event.get("sequence") for event in events] != list(range(1, len(events) + 1)):
        raise SystemExit("NDJSON test event sequence is not contiguous")
    nodeids = [str(event.get("nodeid", "")) for event in events]
    if any(not nodeid for nodeid in nodeids) or len(set(nodeids)) != len(nodeids):
        raise SystemExit("NDJSON test event node IDs are empty or duplicated")

    try:
        xml_root = ElementTree.parse(resolved[junit_name]).getroot()
    except ElementTree.ParseError as exc:
        raise SystemExit(f"Invalid JUnit XML: {exc}") from exc
    suites = [xml_root] if xml_root.tag == "testsuite" else list(xml_root.findall("testsuite"))
    if not suites:
        suites = list(xml_root.findall(".//testsuite"))
    if not suites:
        raise SystemExit("JUnit XML contains no test suites")
    junit_tests = sum(int(suite.attrib.get("tests", 0)) for suite in suites)
    junit_failures = sum(int(suite.attrib.get("failures", 0)) for suite in suites)
    junit_errors = sum(int(suite.attrib.get("errors", 0)) for suite in suites)
    junit_skipped = sum(int(suite.attrib.get("skipped", 0)) for suite in suites)
    if junit_tests != int(tests["collected"]):
        raise SystemExit("JUnit test count does not match collected tests")
    if junit_failures + junit_errors != int(tests["failed"]):
        raise SystemExit("JUnit failure/error count does not match JSON evidence")
    expected_junit_skips = int(tests.get("skipped", 0)) + int(tests.get("xfailed", 0))
    if junit_skipped != expected_junit_skips:
        raise SystemExit("JUnit skipped count does not match JSON evidence")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.root.resolve()

    tests = load_json(root / TEST_JSON)
    summary = load_json(root / SUMMARY_JSON)
    if tests.get("model_version") != MODEL_VERSION:
        raise SystemExit("Test evidence has the wrong model version")
    if summary.get("model_version") != MODEL_VERSION:
        raise SystemExit("Validation evidence has the wrong model version")
    if not tests.get("engineering_integrity_passed", False):
        raise SystemExit("Complete non-slow test evidence is not passing")
    if tests.get("collected", 0) <= 0 or tests.get("completed") != tests.get("collected"):
        raise SystemExit("Complete non-slow inventory is incomplete")
    if tests.get("failed") != 0 or tests.get("pytest_exit_code") != 0:
        raise SystemExit("Complete non-slow test evidence contains failures")
    if len(tests.get("outcomes", [])) != tests["collected"]:
        raise SystemExit("Per-test outcome inventory is incomplete")
    verify_raw_test_evidence(root, tests)

    release = summary.get("release_status", {})
    required_release_gates = (
        "observation_files_verified",
        "engineering_integrity_passed",
        "historical_calibration_passed",
        "recent_period_evaluation_passed",
        "cross_resolution_validation_passed",
        "structural_area_volume_validation_passed",
        "arctic_air_engineering_checks_passed",
        "greenland_engineering_checks_passed",
        "amoc_validation_passed",
    )
    failed_gates = [name for name in required_release_gates if not release.get(name, False)]
    if failed_gates:
        raise SystemExit(f"Engineering validation gates failed: {failed_gates}")
    if release.get("release_classification") != "engineering_only":
        raise SystemExit("Release classification must remain engineering_only")
    if release.get("scientific_release_passed") is not False:
        raise SystemExit("Scientific release must remain disabled")

    source_hashes = summary.get("source_hashes", {})
    if len(source_hashes) != 19:
        raise SystemExit(f"Expected 19 scientific fingerprint files, found {len(source_hashes)}")
    verify_source_hashes(root, source_hashes)

    resolution_status: dict[str, Any] = {}
    for label in ("5", "10"):
        data = summary["resolutions"][label]
        passed = bool(
            data["historical_calibration_passed"]
            and data["recent_period_evaluation_passed"]
            and data["structural_area_volume_validation_passed"]
            and data["coupled_validation_passed"]
        )
        resolution_status[f"{label}_degree"] = {
            "passed": passed,
            "historical_calibration_passed": data["historical_calibration_passed"],
            "recent_period_evaluation_passed": data["recent_period_evaluation_passed"],
            "structural_process_budgets_passed": data[
                "structural_area_volume_validation_passed"
            ],
            "coupled_validation_passed": data["coupled_validation_passed"],
            "sea_ice_file": f"SEA_ICE_VALIDATION_V2_29_22_{label}DEG.json",
            "coupled_file": f"ARCTIC_GREENLAND_AMOC_VALIDATION_V2_29_22_{label}DEG.json",
            "timeseries_file": f"COUPLED_TIMESERIES_V2_29_22_{label}DEG.csv",
        }
    if not all(item["passed"] for item in resolution_status.values()):
        raise SystemExit("One or more resolution evidence sets failed")

    payload: dict[str, Any] = {
        "schema_version": "3.0",
        "model_version": MODEL_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "package_variant": "engineering_only",
        "release_classification": "engineering_only",
        "scientific_release_passed": False,
        "relocation_safe": True,
        "full_period_validation": {
            "status": "complete",
            "requested": (
                "1850-2100 SSP2-4.5 at 5-degree and 10-degree plus matched "
                "no-Greenland-freshwater sensitivity"
            ),
            "resolutions": resolution_status,
            "cross_resolution_passed": summary["cross_resolution_validation_passed"],
            "combined_summary": SUMMARY_JSON,
        },
        "complete_non_slow_test_suite": {
            "status": "complete",
            "selection": tests["test_selection"],
            "single_frozen_tree_invocation": True,
            "collected": tests["collected"],
            "completed": tests["completed"],
            "passed": tests["passed"],
            "failed": tests["failed"],
            "skipped": tests["skipped"],
            "engineering_integrity_passed": tests["engineering_integrity_passed"],
            "evidence": TEST_JSON,
            "raw_evidence": sorted(tests["raw_evidence"]),
        },
        "source_corrections": {
            "simulation_result_arctic_blend": "implemented_and_regression_tested",
            "low_volume_compactness_mapping": "implemented_and_regression_tested",
            "production_process_ledger": "implemented_closure_and_mutation_tested",
            "relocation_safe_scientific_fingerprint": "implemented_19_relative_files",
            "self_contained_single_invocation_test_evidence": "implemented",
            "relocated_finalizer_and_packager_verification": "implemented",
            "gui_tooltip_metadata_completeness": "implemented_and_regression_tested",
            "primary_documentation": "updated_to_v2.29.22",
        },
        "source_hashes": source_hashes,
        "remaining_scientific_limitations": [
            "No prospective untouched temporal validation is available before 2027.",
            "Sea-ice extent is multiplier-derived and is not independent scientific evidence.",
            "Historical and 2021-2025 sea-ice observations are retrospective development evidence.",
            "OISST and Greenland magnitude checks are tuning-informed or post-hoc sanity checks.",
            "The Arctic, Greenland, and AMOC components remain reduced sensitivity emulators rather than precise forecasts.",
        ],
    }

    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    for name in (CANONICAL_STATUS, COMPATIBILITY_STATUS):
        (root / name).write_text(text, encoding="utf-8")
    print(root / CANONICAL_STATUS)
    print(root / COMPATIBILITY_STATUS)


if __name__ == "__main__":
    main()
