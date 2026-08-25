#!/usr/bin/env python3
"""Shared deterministic integrity helpers for the EGCM v2.29.27 release."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MODEL_VERSION = "2.29.27"
PACKAGE_NAME = "emergent_global_climate_model_v2_29_27"
FINGERPRINT_JSON = "TESTED_CODE_FINGERPRINT_V2_29_27.json"
TEST_JSON = "TEST_RESULTS_V2_29_27.json"
TEST_TXT = "TEST_RESULTS_V2_29_27.txt"
PACKAGE_INFO = "PACKAGE_INFO_V2_29_27.json"
MANIFEST = "PACKAGE_MANIFEST_V2_29_27.json"

EXCLUDED_DIRS = {".git", ".pytest_cache", "__pycache__", "outputs", "output"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".tmp", ".bak", ".log", ".pid"}
FINGERPRINT_EXCLUDED_FILES = {
    FINGERPRINT_JSON,
    PACKAGE_INFO,
    MANIFEST,
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def iter_project_files(*, fingerprint_profile: bool) -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if any(part in EXCLUDED_DIRS for part in rel.parts):
            continue
        if path.suffix.lower() in EXCLUDED_SUFFIXES:
            continue
        if fingerprint_profile and rel.as_posix() in FINGERPRINT_EXCLUDED_FILES:
            continue
        if not fingerprint_profile and rel.as_posix() == MANIFEST:
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(ROOT).as_posix())


def build_file_records(*, fingerprint_profile: bool) -> tuple[dict[str, dict[str, Any]], str]:
    records: dict[str, dict[str, Any]] = {}
    aggregate = hashlib.sha256()
    for path in iter_project_files(fingerprint_profile=fingerprint_profile):
        rel = path.relative_to(ROOT).as_posix()
        digest = sha256_file(path)
        size = path.stat().st_size
        records[rel] = {"sha256": digest, "size_bytes": size}
        aggregate.update(rel.encode("utf-8"))
        aggregate.update(b"\0")
        aggregate.update(str(size).encode("ascii"))
        aggregate.update(b"\0")
        aggregate.update(digest.encode("ascii"))
        aggregate.update(b"\n")
    return records, aggregate.hexdigest()


def create_fingerprint_payload() -> dict[str, Any]:
    records, aggregate = build_file_records(fingerprint_profile=True)
    required_inputs = {
        "ARCTIC_OBSERVATIONAL_RECALIBRATION_10DEG_2026.json",
        "NESTED_ARCTIC_HINDCAST_V2_29_27.json",
        "data/validation/temperature/HadCRUT.5.1.0.0.analysis.summary_series.global.annual.csv",
        "climate_model.py",
        "arctic_validation_stack.py",
        "sea_ice_validation.py",
    }
    absent = sorted(required_inputs - set(records))
    if absent:
        raise RuntimeError(f"Fingerprint coverage missing required scientific inputs: {absent}")
    return {
        "schema_version": 2,
        "model_version": MODEL_VERSION,
        "profile": "tested-code-and-scientific-inputs",
        "algorithm": "sha256",
        "coverage": (
            "all source/GUI/tests/tools, dependency/configuration inputs, packaged runtime data, "
            "scientific evaluation JSON/manifests, validation evidence, and release-facing documents; "
            "the fingerprint itself, package-info/manifest outputs, and transient caches are excluded; test evidence is included"
        ),
        "excluded_current_generated_files": sorted(FINGERPRINT_EXCLUDED_FILES),
        "file_count": len(records),
        "aggregate_sha256": aggregate,
        "files": records,
    }


def verify_fingerprint_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("model_version") != MODEL_VERSION:
        errors.append(
            f"model_version mismatch: expected {MODEL_VERSION}, got {payload.get('model_version')!r}"
        )
    expected = payload.get("files")
    if not isinstance(expected, dict):
        return errors + ["fingerprint files field is not an object"]
    actual, aggregate = build_file_records(fingerprint_profile=True)
    expected_names = set(expected)
    actual_names = set(actual)
    for name in sorted(expected_names - actual_names):
        errors.append(f"missing fingerprinted file: {name}")
    for name in sorted(actual_names - expected_names):
        errors.append(f"unexpected untested file: {name}")
    for name in sorted(expected_names & actual_names):
        exp = expected[name]
        act = actual[name]
        if exp.get("size_bytes") != act["size_bytes"]:
            errors.append(
                f"size mismatch for {name}: expected {exp.get('size_bytes')}, got {act['size_bytes']}"
            )
        if str(exp.get("sha256", "")).lower() != act["sha256"].lower():
            errors.append(
                f"SHA-256 mismatch for {name}: expected {exp.get('sha256')}, got {act['sha256']}"
            )
    if payload.get("file_count") != len(actual):
        errors.append(
            f"file_count mismatch: expected {payload.get('file_count')}, got {len(actual)}"
        )
    if str(payload.get("aggregate_sha256", "")).lower() != aggregate.lower():
        errors.append(
            f"aggregate mismatch: expected {payload.get('aggregate_sha256')}, got {aggregate}"
        )
    return errors
