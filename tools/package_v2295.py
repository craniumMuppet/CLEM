#!/usr/bin/env python3
"""Build and verify the clean EGCM v2.29.5 accuracy and evidence-integrity archive."""

from __future__ import annotations

import argparse
import hashlib
import os
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "emergent_global_climate_model_v2_29_5_physical_integrity"
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
    "validation_v2295_tasks/",
    "validation_v2295_tasks_final/",
)
EXCLUDED_SUFFIXES = (".pyc", ".pyo", ".tmp", ".bak", ".tolbak", ".stage0")
EXCLUDED_FILE_NAMES = set()
EXCLUDED_FILE_PREFIXES = (
    "validation_v2295_test_nodes",
    "validation_v2295_test_results",
    "validation_v2295_isolated_runner",
    "validation_v2295_parallel_runner",
    "validation_v2295_suite_",
)
REQUIRED = (
    "climate_model.py",
    "monte_carlo.py",
    "app.py",
    "climate_model_gui.py",
    "setting_metadata.py",
    "README.md",
    "CHANGELOG.md",
    "V2_29_5_ACCURACY_AND_VALIDATION.md",
    "V2_29_5_POST_FIX_REVIEW.md",
    "VALIDATION_SUMMARY_V2_29_5.json",
    "DEEP_VALIDATION_V2_29_5.json",
    "IMPLEMENTATION_AUDIT_V2_29_5.json",
    "TEST_RESULTS_V2_29_5.txt",
    "validate_v2295.py",
    "run_tests.py",
    "isolated_pytest_exit.py",
    "tests/test_v2292_release_integrity.py",
    "tests/test_v2293_operational_safety.py",
    "tests/test_v2294_accuracy_integrity.py",
    "tests/test_v2295_physical_integrity.py",
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
    "tools/process_noaa_oisst_arctic_benchmarks.py",
    "data/world_grid_5deg.npz",
    "tools/package_v2295.py",
    "tools/run_v2295_validation_parallel.py",
    "tests/test_property_conservation.py",
    "tests/test_v2291_arctic_phase_consistency.py",
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
        if relative_text.startswith("validation_v2295_test_logs"):
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(ROOT).as_posix())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build(output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
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
