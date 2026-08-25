#!/usr/bin/env python3
"""Export only processed Arctic validation evidence for transfer/recalibration.

Raw NetCDF/HDF5 files and authentication material are intentionally excluded.
By default the export requires all six products.  --allow-missing-ice-age permits
exactly one missing source, NSIDC-0611, because it is a structural diagnostic and
not a calibration target.  --allow-partial remains available for diagnostics.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from arctic_validation_stack import SOURCES, validation_stack_status  # noqa: E402


def export_bundle(
    destination: Path,
    *,
    allow_partial: bool = False,
    allow_missing_ice_age: bool = False,
) -> Path:
    status = validation_stack_status()
    missing_sources = set(status["missing_sources"])
    core_five_complete = missing_sources.issubset({"nsidc_0611_v4"})
    if not allow_partial and not status["all_six_observational_products_available"]:
        if not (allow_missing_ice_age and core_five_complete):
            missing = ", ".join(status["missing_sources"])
            raise SystemExit(f"Validation stack incomplete; missing: {missing}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    status_bytes = (json.dumps(status, indent=2, sort_keys=True) + "\n").encode("utf-8")
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("ARCTIC_VALIDATION_STACK_STATUS.json", status_bytes)
        for spec in SOURCES.values():
            for relative in spec.required_paths:
                path = ROOT / relative
                if path.exists() and path.is_file():
                    archive.write(path, arcname=relative)
        manifest = ROOT / "data" / "validation" / "sea_ice_physical" / "SOURCES.json"
        if manifest.exists():
            archive.write(manifest, arcname=str(manifest.relative_to(ROOT)))
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "ARCTIC_VALIDATION_DATA_BUNDLE.zip",
    )
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument(
        "--allow-missing-ice-age",
        action="store_true",
        help="Allow export only when NSIDC-0611 is the sole missing source",
    )
    args = parser.parse_args()
    output = export_bundle(
        args.output,
        allow_partial=args.allow_partial,
        allow_missing_ice_age=args.allow_missing_ice_age,
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
