#!/usr/bin/env python3
"""Build, relocate, and independently verify the EGCM v2.29.23 archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from release_tree_fingerprint import verify_release_tree_fingerprint

MODEL_VERSION = "2.29.23"
PREFIX = "emergent_global_climate_model_v2_29_23_engineering_only"
MANIFEST_NAME = "PACKAGE_FILE_MANIFEST_V2_29_23.json"
STATUS_NAME = "PACKAGE_STATUS_V2_29_23.json"
COMPATIBILITY_STATUS_NAME = "REVIEW_CORRECTED_STATUS.json"
TEST_JSON = "TEST_RESULTS_V2_29_23.json"
TEST_TXT = "TEST_RESULTS_V2_29_23.txt"
TEST_EVENTS = "TEST_EVENTS_V2_29_23.ndjson"
TEST_JUNIT = "TEST_RESULTS_V2_29_23.junit.xml"
SUMMARY_NAME = "VALIDATION_SUMMARY_V2_29_23.json"

EXCLUDED_DIRS = {
    ".git", ".pytest_cache", ".venv", "venv", "__pycache__", "outputs", "output",
    "calibration_work", "greenland_check", "release_validation",
    "validation_review_corrected",
}
EXCLUDED_SUFFIXES = (".pyc", ".pyo", ".tmp", ".bak", ".tolbak", ".stage0", ".pid", ".exit", ".log")
FORBIDDEN_NAMES = {
    "VALIDATION_SUMMARY_V2_29_22.json",
    "TEST_RESULTS_V2_29_22.json",
    "TEST_RESULTS_V2_29_22.txt",
    "TEST_EVENTS_V2_29_22.ndjson",
    "TEST_RESULTS_V2_29_22.junit.xml",
    "PACKAGE_STATUS_V2_29_22.json",
    "PACKAGE_FILE_MANIFEST_V2_29_22.json",
    "SEA_ICE_VALIDATION_V2_29_22_5DEG.json",
    "SEA_ICE_VALIDATION_V2_29_22_10DEG.json",
    "ARCTIC_GREENLAND_AMOC_VALIDATION_V2_29_22_5DEG.json",
    "ARCTIC_GREENLAND_AMOC_VALIDATION_V2_29_22_10DEG.json",
    "COUPLED_TIMESERIES_V2_29_22_5DEG.csv",
    "COUPLED_TIMESERIES_V2_29_22_10DEG.csv",
}
REQUIRED = {
    "climate_model.py", "climate_model_gui.py", "app.py", "setting_metadata.py",
    "bootstrap_runtime.py",
    "arctic_process_budget.py", "release_tree_fingerprint.py",
    "validate_v22923.py", "combine_v22923_validation.py",
    "run_v22923_engineering_tests.py", "V2_29_23_ENGINEERING_CORRECTIONS.md",
    STATUS_NAME, COMPATIBILITY_STATUS_NAME, TEST_JSON, TEST_TXT, TEST_EVENTS, TEST_JUNIT,
    SUMMARY_NAME,
    "SEA_ICE_VALIDATION_V2_29_23_5DEG.json",
    "SEA_ICE_VALIDATION_V2_29_23_10DEG.json",
    "ARCTIC_GREENLAND_AMOC_VALIDATION_V2_29_23_5DEG.json",
    "ARCTIC_GREENLAND_AMOC_VALIDATION_V2_29_23_10DEG.json",
    "COUPLED_TIMESERIES_V2_29_23_5DEG.csv",
    "COUPLED_TIMESERIES_V2_29_23_10DEG.csv",
    "tests/test_v22923_engineering_corrections.py",
    "tools/finalize_v22923_status.py", "tools/package_v22923.py",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_relative(name: str) -> Path:
    path = Path(name)
    if path.is_absolute() or ".." in path.parts:
        raise SystemExit(f"Non-relocatable package path: {name}")
    return path


def release_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if any(part in EXCLUDED_DIRS for part in relative.parts):
            continue
        if path.name in FORBIDDEN_NAMES or path.name.endswith(EXCLUDED_SUFFIXES):
            continue
        if path.name.startswith("PACKAGE_FILE_MANIFEST_") and path.name != MANIFEST_NAME:
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(ROOT).as_posix())


def verify_raw_test_evidence(tests: dict[str, Any]) -> None:
    raw = tests.get("raw_evidence", {})
    required = {TEST_EVENTS, TEST_JUNIT}
    if set(raw) != required:
        raise SystemExit(f"Raw test evidence mismatch: {sorted(raw)}")
    resolved: dict[str, Path] = {}
    for name, metadata in raw.items():
        path = ROOT / safe_relative(name)
        resolved[name] = path
        if not path.is_file():
            raise SystemExit(f"Missing raw test evidence: {name}")
        if path.stat().st_size != int(metadata["size_bytes"]):
            raise SystemExit(f"Raw test evidence size mismatch: {name}")
        if sha256(path) != metadata["sha256"]:
            raise SystemExit(f"Raw test evidence hash mismatch: {name}")

    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        resolved[TEST_EVENTS].read_text(encoding="utf-8").splitlines(), start=1
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
        xml_root = ElementTree.parse(resolved[TEST_JUNIT]).getroot()
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



def _run_checked(command: list[str], *, root: Path, label: str) -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(root)
    completed = subprocess.run(
        command,
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise SystemExit(
            f"{label} failed:\n{completed.stdout}{completed.stderr}"
        )


def verify_streamlit_dependency_contract(root: Path) -> str:
    """Require one identical exact Streamlit pin in project and lock metadata."""

    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = project.get("project", {}).get("dependencies", [])
    project_pins = [
        str(value).strip()
        for value in dependencies
        if str(value).strip().lower().startswith("streamlit==")
    ]
    lock_pins = [
        line.strip()
        for line in (root / "requirements.lock").read_text(encoding="utf-8").splitlines()
        if line.strip().lower().startswith("streamlit==")
    ]
    if len(project_pins) != 1 or len(lock_pins) != 1:
        raise SystemExit(
            "Streamlit must have exactly one exact pin in pyproject.toml and requirements.lock"
        )
    if project_pins[0] != lock_pins[0]:
        raise SystemExit(
            "Streamlit dependency pin mismatch: "
            f"pyproject={project_pins[0]!r} lock={lock_pins[0]!r}"
        )
    app_source = (root / "app.py").read_text(encoding="utf-8")
    if "import streamlit as st" not in app_source:
        raise SystemExit("app.py does not use the declared Streamlit dependency")
    return project_pins[0]


def verify_runtime_smoke(root: Path) -> dict[str, Any]:
    """Compile all code, import core modules, and construct the desktop GUI."""

    _run_checked(
        [sys.executable, "-m", "compileall", "-q", "-f", "."],
        root=root,
        label="Package compileall",
    )
    _run_checked(
        [
            sys.executable,
            "-c",
            (
                "import climate_model, climate_model_gui, arctic_process_budget, "
                "release_tree_fingerprint, validate_v22923, combine_v22923_validation"
            ),
        ],
        root=root,
        label="Package core import smoke",
    )
    streamlit_pin = verify_streamlit_dependency_contract(root)
    _run_checked(
        [sys.executable, "gui_smoke_test.py"],
        root=root,
        label="GUI command-builder smoke",
    )
    xvfb = shutil.which("xvfb-run")
    if xvfb is not None:
        gui_command = [xvfb, "-a", sys.executable, "gui_startup_smoke_test.py"]
    elif sys.platform.startswith("win") or os.environ.get("DISPLAY"):
        gui_command = [sys.executable, "gui_startup_smoke_test.py"]
    else:
        raise SystemExit("No graphical display or xvfb-run is available for GUI smoke")
    _run_checked(gui_command, root=root, label="Desktop GUI startup smoke")
    return {
        "compileall_passed": True,
        "import_smoke_passed": True,
        "core_import_smoke_passed": True,
        "streamlit_dependency_contract_passed": True,
        "streamlit_dependency_pin": streamlit_pin,
        "gui_command_builder_smoke_passed": True,
        "desktop_gui_startup_smoke_passed": True,
    }

def verify_evidence() -> dict[str, Any]:
    status = load_json(ROOT / STATUS_NAME)
    compatibility = load_json(ROOT / COMPATIBILITY_STATUS_NAME)
    tests = load_json(ROOT / TEST_JSON)
    summary = load_json(ROOT / SUMMARY_NAME)
    if compatibility != status:
        raise SystemExit("Compatibility and canonical status files differ")
    if status.get("model_version") != MODEL_VERSION:
        raise SystemExit("Status has the wrong model version")
    if status.get("release_classification") != "engineering_only":
        raise SystemExit("Package must remain engineering_only")
    if status.get("scientific_release_passed") is not False:
        raise SystemExit("Package cannot claim scientific release")
    if status.get("relocation_safe") is not True:
        raise SystemExit("Status does not declare relocation-safe evidence")
    if not tests.get("engineering_integrity_passed", False):
        raise SystemExit("Engineering test evidence is not passing")
    if (
        tests.get("completed") != tests.get("collected")
        or tests.get("failed") != 0
        or tests.get("pytest_exit_code") != 0
        or tests.get("runner_exit_code") != 0
    ):
        raise SystemExit("Engineering test evidence is incomplete")
    if tests.get("tree_unchanged_during_pytest") is not True:
        raise SystemExit("Engineering test tree changed during pytest")
    tree_fingerprint = tests.get("release_tree_fingerprint")
    if not isinstance(tree_fingerprint, dict):
        raise SystemExit("Engineering test evidence lacks a release-tree fingerprint")
    verify_release_tree_fingerprint(ROOT, tree_fingerprint)
    if len(tests.get("outcomes", [])) != tests.get("collected"):
        raise SystemExit("Per-test outcome evidence is incomplete")
    verify_raw_test_evidence(tests)
    release = summary.get("release_status", {})
    if release.get("release_classification") != "engineering_only":
        raise SystemExit("Combined validation classification mismatch")
    if release.get("scientific_release_passed") is not False:
        raise SystemExit("Combined validation incorrectly claims scientific release")
    if not release.get("engineering_integrity_passed", False):
        raise SystemExit("Combined validation lacks passing engineering evidence")

    expected_hashes = summary.get("source_hashes", {})
    if len(expected_hashes) != 19:
        raise SystemExit("Combined validation fingerprint must contain 19 files")
    if status.get("source_hashes") != expected_hashes:
        raise SystemExit("Status and combined validation fingerprints differ")
    actual_hashes: dict[str, str] = {}
    for name in expected_hashes:
        path = ROOT / safe_relative(name)
        if not path.is_file():
            raise SystemExit(f"Missing fingerprinted file: {name}")
        actual_hashes[name] = sha256(path)
    if actual_hashes != expected_hashes:
        raise SystemExit("Current source does not match validation fingerprint")

    for label in ("5", "10"):
        sea = load_json(ROOT / f"SEA_ICE_VALIDATION_V2_29_23_{label}DEG.json")
        coupled = load_json(ROOT / f"ARCTIC_GREENLAND_AMOC_VALIDATION_V2_29_23_{label}DEG.json")
        if sea.get("source_hashes") != expected_hashes or coupled.get("source_hashes") != expected_hashes:
            raise SystemExit(f"{label}-degree evidence fingerprint mismatch")
        if not sea["summary"].get("all_engineering_gates_passed", False):
            raise SystemExit(f"{label}-degree sea-ice engineering gates failed")
        structural = coupled["structural_area_volume_experiments"]
        if not structural.get("passed", False):
            raise SystemExit(f"{label}-degree process budgets failed")
        process = structural["process_budget_experiments"]
        if process.get("method") != "production_ProcessClimateModel_step_actual_receiving_reservoir_ledger":
            raise SystemExit(f"{label}-degree process evidence is not production-ledger based")
        if not all(process.get("mutation_checks", {}).values()):
            raise SystemExit(f"{label}-degree mutation checks failed")
        if not coupled["coupled"]["passed"]:
            raise SystemExit(f"{label}-degree coupled gates failed")
    return status


def write_manifest(status: dict[str, Any]) -> Path:
    manifest_path = ROOT / MANIFEST_NAME
    entries = []
    for path in release_files():
        if path.resolve() == manifest_path.resolve():
            continue
        entries.append({
            "path": path.relative_to(ROOT).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        })
    manifest = {
        "schema_version": "3.0", "model_version": MODEL_VERSION,
        "package_variant": "engineering_only",
        "release_classification": status["release_classification"],
        "scientific_release_passed": status["scientific_release_passed"],
        "coverage": "all packaged files except this manifest",
        "file_count": len(entries), "files": entries,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest_path


def verify_archive(archive: Path, expected_files: set[str]) -> dict[str, Any]:
    with zipfile.ZipFile(archive) as source:
        bad_member = source.testzip()
        if bad_member is not None:
            raise SystemExit(f"Corrupt ZIP member: {bad_member}")
        names = set(source.namelist())
        expected_names = {f"{PREFIX}/{name}" for name in expected_files}
        if names != expected_names:
            raise SystemExit("ZIP member set mismatch")
        manifest = json.loads(source.read(f"{PREFIX}/{MANIFEST_NAME}"))
        for entry in manifest["files"]:
            member = f"{PREFIX}/{entry['path']}"
            data = source.read(member)
            if len(data) != entry["size_bytes"]:
                raise SystemExit(f"Manifest size mismatch for {member}")
            if hashlib.sha256(data).hexdigest() != entry["sha256"]:
                raise SystemExit(f"Manifest hash mismatch for {member}")
        return {
            "zip_test_passed": True,
            "member_count": len(names),
            "manifest_entries_verified": len(manifest["files"]),
            "manifest_file_count": manifest["file_count"],
        }


def verify_relocated_workflows(archive: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="egcm_v22923_relocated_") as temporary:
        base = Path(temporary)
        with zipfile.ZipFile(archive) as source:
            source.extractall(base)
        relocated = base / PREFIX
        env = dict(os.environ)
        env["PYTHONPATH"] = str(relocated)
        relocated_smoke = verify_runtime_smoke(relocated)
        finalize = subprocess.run(
            [sys.executable, str(relocated / "tools/finalize_v22923_status.py"), "--root", str(relocated)],
            cwd=relocated, env=env, text=True, capture_output=True,
        )
        if finalize.returncode != 0:
            raise SystemExit("Relocated finalizer failed:\n" + finalize.stdout + finalize.stderr)
        repack_dir = base / "repacked"
        repack = subprocess.run(
            [sys.executable, str(relocated / "tools/package_v22923.py"), "--output-dir", str(repack_dir), "--skip-relocation-check"],
            cwd=relocated, env=env, text=True, capture_output=True,
        )
        if repack.returncode != 0:
            raise SystemExit("Relocated packager failed:\n" + repack.stdout + repack.stderr)
        return {
            **{f"relocated_{key}": value for key, value in relocated_smoke.items()},
            "relocated_finalizer_passed": True,
            "relocated_packager_passed": True,
            "relocated_root_was_temporary": True,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT.parent)
    parser.add_argument("--skip-relocation-check", action="store_true")
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    runtime_smoke = verify_runtime_smoke(ROOT)
    status = verify_evidence()
    write_manifest(status)
    files = release_files()
    available = {path.relative_to(ROOT).as_posix() for path in files}
    missing = sorted(REQUIRED - available)
    if missing:
        raise SystemExit(f"Missing required v2.29.23 files: {missing}")
    forbidden_present = sorted(name for name in FORBIDDEN_NAMES if (ROOT / name).exists())
    if forbidden_present:
        raise SystemExit(f"Stale release evidence is present: {forbidden_present}")

    archive = output_dir / f"{PREFIX}.zip"
    checksum = output_dir / f"{PREFIX}.zip.sha256"
    report_path = output_dir / f"{PREFIX}.verification.json"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as target:
        for source in files:
            rel = source.relative_to(ROOT).as_posix()
            info = zipfile.ZipInfo(f"{PREFIX}/{rel}")
            info.date_time = (2026, 8, 5, 21, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if os.access(source, os.X_OK) else 0o644) << 16
            target.writestr(info, source.read_bytes())

    verification = verify_archive(archive, available)
    verification.update(runtime_smoke)
    if not args.skip_relocation_check:
        verification.update(verify_relocated_workflows(archive))
    digest = sha256(archive)
    checksum.write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    verification.update({
        "schema_version": "2.0", "model_version": MODEL_VERSION,
        "archive": archive.name, "archive_size_bytes": archive.stat().st_size,
        "archive_sha256": digest, "checksum_file": checksum.name,
        "release_classification": "engineering_only", "scientific_release_passed": False,
    })
    report_path.write_text(json.dumps(verification, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(archive)
    print(checksum)
    print(report_path)
    print(f"sha256={digest}")


if __name__ == "__main__":
    main()
