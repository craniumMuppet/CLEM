#!/usr/bin/env python3
"""Build and verify the EGCM v2.29.18 Arctic calibration-integrity archive."""

from __future__ import annotations

import hashlib
import json
import os
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "emergent_global_climate_model_v2_29_18_arctic_calibration_integrity"
MANIFEST_NAME = "PACKAGE_FILE_MANIFEST_V2_29_18.json"

EXCLUDED_DIRS = {".git", ".pytest_cache", "__pycache__", "outputs", "output"}
EXCLUDED_SUFFIXES = (".pyc", ".pyo", ".tmp", ".bak", ".tolbak", ".stage0")
EXCLUDED_PREFIXES = (
    "validation_continuous_amoc_v2_16_0/",
    "validation_hybrid_rate_splice_v2_16_1/",
    "validation_v2297_tasks/",
    "validation_v2297_tasks_final/",
    "validation_v22913_tasks/",
    "validation_v22913_tasks_final/",
    "validation_v22914_tasks/",
    "validation_v22914_tasks_final/",
    "validation_v22916_tasks/",
    "validation_v22916_tasks_final/",
    "validation_v22917_tasks/",
    "validation_v22917_tasks_final/",
    "validation_v22918_tasks/",
    "validation_v22918_tasks_final/",
)
EXCLUDED_NAMES = {
    "gui_startup_error.log",
    "v22916_fast_tests.log",
    "v22916_fast_tests.pid",
    "v22916_fast_tests.exit",
    "v22916_validation.log",
    "v22916_validation.pid",
    "v22916_validation.exit",
    "v22917_focused_tests.log",
    "v22917_focused_tests.pid",
    "v22917_focused_tests.exit",
}
REQUIRED = {
    "climate_model.py",
    "climate_model_gui.py",
    "co2_target_sweep.py",
    "monte_carlo.py",
    "safe_checkpoint.py",
    "launch_gui.pyw",
    "run_gui.bat",
    "run_gui_debug.bat",
    "setting_metadata.py",
    "V2_29_18_ARCTIC_CALIBRATION_AND_TARGET_SURVIVAL.md",
    "TEST_RESULTS_V2_29_18.txt",
    "DEEP_VALIDATION_V2_29_18.json",
    "IMPLEMENTATION_AUDIT_V2_29_18.json",
    "SEA_ICE_VALIDATION_V2_29_18_5DEG.json",
    "SEA_ICE_VALIDATION_V2_29_18_10DEG.json",
    "VALIDATION_SUMMARY_V2_29_18.json",
    "validate_v22918.py",
    "rerun_co2_target_sweep_v22918.ps1",
    "tests/test_v22918_release_corrections.py",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def release_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        rel = relative.as_posix()
        if any(part in EXCLUDED_DIRS for part in relative.parts):
            continue
        if rel.startswith(EXCLUDED_PREFIXES):
            continue
        if rel.endswith(EXCLUDED_SUFFIXES):
            continue
        if relative.name in EXCLUDED_NAMES:
            continue
        if (
            relative.name.startswith("PACKAGE_FILE_MANIFEST_")
            and relative.name != MANIFEST_NAME
        ):
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(ROOT).as_posix())


def write_manifest() -> Path:
    manifest_path = ROOT / MANIFEST_NAME
    entries = []
    for path in release_files():
        if path.resolve() == manifest_path.resolve():
            continue
        entries.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    manifest = {
        "schema_version": "1.0",
        "model_version": "2.29.18",
        "package_variant": "arctic_calibration_and_target_survival_integrity",
        "coverage": "all packaged files except this manifest",
        "file_count": len(entries),
        "files": entries,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def main() -> None:
    output_dir = ROOT.parent.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    write_manifest()
    files = release_files()
    available = {path.relative_to(ROOT).as_posix() for path in files}
    missing = sorted(REQUIRED - available)
    if missing:
        raise SystemExit(f"Missing required v2.29.18 files: {missing}")

    archive = output_dir / f"{PREFIX}.zip"
    checksum = output_dir / f"{PREFIX}.sha256"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as target:
        for source in files:
            rel = source.relative_to(ROOT).as_posix()
            info = zipfile.ZipInfo(f"{PREFIX}/{rel}")
            info.date_time = (2026, 8, 3, 14, 30, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if os.access(source, os.X_OK) else 0o644) << 16
            target.writestr(info, source.read_bytes())

    with zipfile.ZipFile(archive) as source:
        bad_member = source.testzip()
        if bad_member is not None:
            raise SystemExit(f"Corrupt ZIP member: {bad_member}")
        names = set(source.namelist())
        for required in REQUIRED:
            member = f"{PREFIX}/{required}"
            if member not in names:
                raise SystemExit(f"Archive missing {member}")

    digest = sha256(archive)
    checksum.write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    print(archive)
    print(checksum)
    print(f"sha256={digest}")


if __name__ == "__main__":
    main()
