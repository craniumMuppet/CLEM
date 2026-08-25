#!/usr/bin/env python3
"""Build and verify the clean EGCM v2.27.1 Arctic-maintenance archive."""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "emergent_global_climate_model_v2_27_1_arctic_maintenance"
EXCLUDED_PREFIXES = (
    "validation_continuous_amoc_v2_16_0/",
    "validation_hybrid_rate_splice_v2_16_1/",
)
REQUIRED = (
    "climate_model.py",
    "README.md",
    "V2_27_1_ARCTIC_MAINTENANCE.md",
    "VALIDATION_SUMMARY_V2_27_1.json",
    "DEEP_VALIDATION_V2_27_1.json",
    "IMPLEMENTATION_AUDIT_V2_27_1.json",
    "TEST_RESULTS_V2_27_1.txt",
    "run_tests.py",
    "isolated_pytest_exit.py",
    "tests/test_v2271_maintenance_arctic.py",
)


def tracked_files() -> list[Path]:
    output = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    files: list[Path] = []
    for raw in output.split(b"\0"):
        if not raw:
            continue
        relative = raw.decode("utf-8")
        if relative.startswith(EXCLUDED_PREFIXES):
            continue
        if "/__pycache__/" in f"/{relative}" or relative.endswith((".pyc", ".pyo")):
            continue
        path = ROOT / relative
        if path.is_file():
            files.append(path)
    return sorted(files, key=lambda path: path.relative_to(ROOT).as_posix())


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
    files = tracked_files()
    relative_files = {path.relative_to(ROOT).as_posix() for path in files}
    missing = [name for name in REQUIRED if name not in relative_files]
    if missing:
        raise SystemExit(f"Required release files are not tracked: {missing}")

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
            or name.endswith((".pyc", ".pyo"))
            or any(f"/{prefix}" in name for prefix in EXCLUDED_PREFIXES)
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
