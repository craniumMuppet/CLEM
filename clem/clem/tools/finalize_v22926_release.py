#!/usr/bin/env python3
"""Verify and package the finalized EGCM v2.29.26 release."""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MODEL_VERSION = "2.29.26"
PACKAGE_NAME = "emergent_global_climate_model_v2_29_26"
TEST_JSON = "TEST_RESULTS_V2_29_26.json"
FINGERPRINT_JSON = "TESTED_CODE_FINGERPRINT_V2_29_26.json"
PACKAGE_INFO = "PACKAGE_INFO_V2_29_26.json"
MANIFEST = "PACKAGE_MANIFEST_V2_29_26.json"
EXCLUDED_DIRS = {".git", ".pytest_cache", "__pycache__", "outputs", "output"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".tmp", ".bak", ".log", ".pid"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def release_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if any(part in EXCLUDED_DIRS for part in rel.parts):
            continue
        if path.suffix.lower() in EXCLUDED_SUFFIXES:
            continue
        if rel.as_posix() == MANIFEST:
            continue
        files.append(path)
    return sorted(files, key=lambda p: p.relative_to(ROOT).as_posix())


def verify_identity() -> None:
    if ROOT.name != PACKAGE_NAME:
        raise SystemExit(f"Release root must be named {PACKAGE_NAME!r}, got {ROOT.name!r}")
    climate = (ROOT / "climate_model.py").read_text(encoding="utf-8")
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    required = [
        (f'MODEL_VERSION = "{MODEL_VERSION}"', climate, "climate_model.py"),
        (f'version = "{MODEL_VERSION}"', project, "pyproject.toml"),
        (f"# Emergent-Sensitivity Global Climate Model v{MODEL_VERSION}", readme, "README.md"),
        (f"## {MODEL_VERSION}", changelog, "CHANGELOG.md"),
    ]
    for needle, text, label in required:
        if needle not in text:
            raise SystemExit(f"Release identity mismatch in {label}: missing {needle!r}")
    for name in (TEST_JSON, FINGERPRINT_JSON):
        if not (ROOT / name).is_file():
            raise SystemExit(f"Missing required release evidence: {name}")


def write_package_info() -> dict[str, Any]:
    tests = load_json(ROOT / TEST_JSON)
    fingerprint = load_json(ROOT / FINGERPRINT_JSON)
    if tests.get("model_version") != MODEL_VERSION:
        raise SystemExit("Test evidence model_version mismatch")
    if tests.get("failed") or tests.get("errors"):
        raise SystemExit("Test evidence contains failures/errors")
    payload = {
        "model_version": MODEL_VERSION,
        "package_name": PACKAGE_NAME,
        "release_classification": "engineering_release_with_observational_recalibration; scientific_predictive_validation_incomplete",
        "test_evidence": TEST_JSON,
        "tested_code_fingerprint": {
            "file": FINGERPRINT_JSON,
            "aggregate_sha256": fingerprint["aggregate_sha256"],
            "file_count": fingerprint["file_count"],
            "profile": fingerprint["profile"],
        },
        "arctic_scientific_status": {
            "calibration_passed": True,
            "development_evaluation_passed": True,
            "physical_volume_thickness_gate_passed": True,
            "osi_saf_september_independent_gate_passed": False,
            "nsidc_0611_available": False,
            "nested_fold_specific_hindcasts_run": False,
            "scientific_predictive_validation_complete": False,
        },
    }
    (ROOT / PACKAGE_INFO).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def write_manifest() -> dict[str, Any]:
    records = []
    aggregate = hashlib.sha256()
    for path in release_files():
        rel = path.relative_to(ROOT).as_posix()
        digest = sha256_file(path)
        size = path.stat().st_size
        records.append({"path": rel, "sha256": digest, "size_bytes": size})
        aggregate.update(rel.encode("utf-8"))
        aggregate.update(b"\0")
        aggregate.update(str(size).encode("ascii"))
        aggregate.update(b"\0")
        aggregate.update(digest.encode("ascii"))
        aggregate.update(b"\n")
    payload = {
        "model_version": MODEL_VERSION,
        "package_name": PACKAGE_NAME,
        "algorithm": "sha256",
        "manifest_excludes_itself": True,
        "file_count": len(records),
        "aggregate_sha256": aggregate.hexdigest(),
        "files": records,
    }
    (ROOT / MANIFEST).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def build_deterministic_zip() -> Path:
    destination = ROOT.parent / f"{PACKAGE_NAME}.zip"
    if destination.exists():
        destination.unlink()
    files = release_files() + [ROOT / MANIFEST]
    files = sorted(files, key=lambda p: p.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            rel = Path(PACKAGE_NAME) / path.relative_to(ROOT)
            info = zipfile.ZipInfo(rel.as_posix(), date_time=(2026, 8, 18, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    sha_path = destination.with_suffix(destination.suffix + ".sha256")
    sha_path.write_text(f"{sha256_file(destination)}  {destination.name}\n", encoding="ascii")
    return destination


def main() -> None:
    verify_identity()
    write_package_info()
    manifest = write_manifest()
    archive = build_deterministic_zip()
    print(f"Packaged {MODEL_VERSION}: {archive}")
    print(f"Files: {manifest['file_count']}")
    print(f"Manifest aggregate: {manifest['aggregate_sha256']}")
    print(f"Archive SHA-256: {sha256_file(archive)}")


if __name__ == "__main__":
    main()
