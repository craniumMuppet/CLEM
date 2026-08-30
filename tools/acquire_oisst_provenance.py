#!/usr/bin/env python3
"""Download official NOAA OISST climatologies and retain reproducibility records."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "sst_climatology": {
        "url": "https://downloads.psl.noaa.gov/Datasets/noaa.oisst.v2/sst.ltm.1991-2020.nc",
        "filename": "sst.ltm.1991-2020.nc",
        "reported_size_bytes": 3441836,
    },
    "ice_concentration_climatology": {
        "url": "https://downloads.psl.noaa.gov/Datasets/noaa.oisst.v2/icec.ltm.1991-2020.nc",
        "filename": "icec.ltm.1991-2020.nc",
        "reported_size_bytes": 2026353,
    },
}

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work-dir", type=Path, required=True)
    ap.add_argument("--output", type=Path, default=ROOT / "data/validation/open_water/OISST_PROCESSED_V2_29_7.json")
    ap.add_argument("--manifest", type=Path, default=ROOT / "data/validation/open_water/OISST_SOURCE_MANIFEST_V2_29_7.json")
    args = ap.parse_args()
    work = args.work_dir.resolve(); work.mkdir(parents=True, exist_ok=True)
    manifest = {"schema_version": "1.0", "files": {}, "processor": "tools/process_noaa_oisst_arctic_benchmarks.py"}
    local = {}
    for key, spec in SOURCES.items():
        path = work / spec["filename"]
        if not path.exists():
            with urllib.request.urlopen(spec["url"], timeout=120) as response, path.open("wb") as target:
                while True:
                    block = response.read(1024 * 1024)
                    if not block: break
                    target.write(block)
        size = path.stat().st_size
        if size != spec["reported_size_bytes"]:
            raise SystemExit(f"Unexpected size for {path.name}: {size}")
        local[key] = path
        manifest["files"][key] = {**spec, "sha256": sha256(path), "size_bytes": size}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        sys.executable, str(ROOT / "tools/process_noaa_oisst_arctic_benchmarks.py"),
        "--sst", str(local["sst_climatology"]),
        "--ice", str(local["ice_concentration_climatology"]),
        "--output", str(args.output.resolve()),
    ], cwd=ROOT, check=True)
    manifest["processed_output"] = {
        "path": args.output.relative_to(ROOT).as_posix() if args.output.resolve().is_relative_to(ROOT) else str(args.output.resolve()),
        "sha256": sha256(args.output.resolve()),
    }
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(args.manifest)
    print(args.output)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
