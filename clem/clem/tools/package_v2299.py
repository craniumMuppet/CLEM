#!/usr/bin/env python3
"""Build and verify the clean EGCM v2.29.9 scientific-review-fix archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "emergent_global_climate_model_v2_29_9_scientific_review_fixes"
EXCLUDED_DIR_NAMES = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    "outputs",
    "output",
}
EXCLUDED_PREFIXES = (
    "validation_continuous_amoc_v2_16_0/",
    "validation_hybrid_rate_splice_v2_16_1/",
    "validation_v2297_tasks/",
    "validation_v2297_tasks_final/",
)
EXCLUDED_SUFFIXES = (".pyc", ".pyo", ".tmp", ".bak", ".tolbak", ".stage0")
EXCLUDED_FILE_NAMES = set()
EXCLUDED_FILE_PREFIXES = (
    "validation_v2297_test_nodes",
    "validation_v2297_test_results",
    "validation_v2297_isolated_runner",
    "validation_v2297_parallel_runner",
    "validation_v2297_suite_",
)
REQUIRED = (
    "climate_model.py",
    "monte_carlo.py",
    "app.py",
    "climate_model_gui.py",
    "setting_metadata.py",
    "run_state.py",
    "co2_target_sweep.py",
    "V2_29_9_SCIENTIFIC_REVIEW_FIXES.md",
    "VALIDATION_SUMMARY_V2_29_9.json",
    "DEEP_VALIDATION_V2_29_9.json",
    "IMPLEMENTATION_AUDIT_V2_29_9.json",
    "PACKAGE_FILE_MANIFEST_V2_29_9.json",
    "TEST_RESULTS_V2_29_9.txt",
    "tests/test_v2298_resumable_sweeps.py",
    "tests/test_v2299_scientific_review_fixes.py",
    "README.md",
    "CHANGELOG.md",
    "V2_29_7_NATIVE_ARCTIC_INTEGRITY.md",
    "V2_29_7_ACCURACY_AND_VALIDATION.md",
    "V2_29_7_POST_FIX_REVIEW.md",
    "V2_29_7_SELECTED_PHYSICS_DIAGNOSTICS.json",
    "VALIDATION_SUMMARY_V2_29_7.json",
    "DEEP_VALIDATION_V2_29_7.json",
    "IMPLEMENTATION_AUDIT_V2_29_7.json",
    "TEST_RESULTS_V2_29_7.txt",
    "validate_v2299.py",
    "run_tests.py",
    "isolated_pytest_exit.py",
    "tests/test_v2292_release_integrity.py",
    "tests/test_v2293_operational_safety.py",
    "tests/test_v2294_accuracy_integrity.py",
    "tests/test_v2297_review_fixes.py",
    "tests/test_v2296_native_arctic_integrity.py",
    "worker_supervision.py",
    "sea_ice_observation.py",
    "sea_ice_validation.py",
    "scientific_evidence.py",
    "development_regression_benchmarks.json",
    "data/validation/nsidc/METADATA.json",
    "data/validation/nsidc/N_03_extent_v4.0.csv",
    "data/validation/nsidc/N_09_extent_v4.0.csv",
    "data/validation/open_water/NOAA_OISST_ARCTIC_BENCHMARKS.json",
    "data/validation/open_water/README.md",
    "data/validation/open_water/OISST_SOURCE_ACQUISITION.md",
    "tools/process_noaa_oisst_arctic_benchmarks.py",
    "tools/acquire_oisst_provenance.py",
    "data/world_grid_5deg.npz",
    "tools/package_v2299.py",
    "tools/run_v2299_validation_parallel.py",
    "tests/test_property_conservation.py",
    "tests/test_v2291_arctic_phase_consistency.py",
    "tests/test_v226_thermodynamic_arctic.py",
    "long_hold_salinity_exchange_test.py",
    "structural_fixes_v2_17_0_test.py",
)


def release_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        relative_text = relative.as_posix()
        if any(part in EXCLUDED_DIR_NAMES for part in relative.parts):
            continue
        if relative_text.startswith(EXCLUDED_PREFIXES):
            continue
        if relative_text.endswith(EXCLUDED_SUFFIXES):
            continue
        if relative.name in EXCLUDED_FILE_NAMES:
            continue
        if relative.name.startswith(EXCLUDED_FILE_PREFIXES):
            continue
        if relative_text.startswith("validation_v2297_test_logs"):
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(ROOT).as_posix())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_full_file_manifest() -> Path:
    """Hash every releasable file except the manifest itself.

    The archive-level checksum protects the manifest. Excluding the manifest
    from its own entry avoids an impossible recursive self-hash while still
    covering every other packaged byte.
    """
    manifest_path = ROOT / "PACKAGE_FILE_MANIFEST_V2_29_9.json"
    entries = []
    for path in release_files():
        if path.resolve() == manifest_path.resolve():
            continue
        entries.append({
            "path": path.relative_to(ROOT).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        })
    payload = {
        "schema_version": "1.0",
        "model_version": "2.29.9",
        "coverage": "all packaged files except this manifest; the archive SHA-256 protects the manifest itself",
        "file_count": len(entries),
        "files": entries,
    }
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest_path


def build(output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_full_file_manifest()
    archive = output_dir / f"{PREFIX}.zip"
    checksum = output_dir / f"{PREFIX}.sha256"
    files = release_files()
    relative_files = {path.relative_to(ROOT).as_posix() for path in files}
    missing = [name for name in REQUIRED if name not in relative_files]
    if missing:
        raise SystemExit(f"Required release files are missing: {missing}")

    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as target:
        for source in files:
            relative = source.relative_to(ROOT).as_posix()
            info = zipfile.ZipInfo(f"{PREFIX}/{relative}")
            info.date_time = (2026, 7, 29, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if os.access(source, os.X_OK) else 0o644) << 16
            target.writestr(info, source.read_bytes())

    digest = sha256(archive)
    checksum.write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    with zipfile.ZipFile(archive) as source:
        names = source.namelist()
        if any(
            "/.git/" in name
            or "/.pytest_cache/" in name
            or "/__pycache__/" in name
            or name.endswith(EXCLUDED_SUFFIXES)
            for name in names
        ):
            raise SystemExit("Release archive contains an excluded path")
        for required in REQUIRED:
            if f"{PREFIX}/{required}" not in names:
                raise SystemExit(f"Release archive is missing {required}")
    return archive, checksum


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT.parent)
    args = parser.parse_args()
    archive, checksum = build(args.output_dir.resolve())
    print(archive)
    print(checksum)
    print(f"sha256={sha256(archive)}")


if __name__ == "__main__":
    main()
