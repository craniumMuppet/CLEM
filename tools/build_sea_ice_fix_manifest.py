#!/usr/bin/env python3
"""Build the derivative package manifest and canonical tree hash."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Iterable

MANIFEST_NAME = "PACKAGE_MANIFEST_SEA_ICE_FIX.json"
TREE_HASH_NAME = "PACKAGE_TREE_SHA256_SEA_ICE_FIX.txt"
RUNTIME_DIR_NAMES = {"__pycache__", ".pytest_cache"}
RUNTIME_SUFFIXES = {".pyc", ".pyo"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_runtime_artifact(relative: Path) -> bool:
    return any(part in RUNTIME_DIR_NAMES for part in relative.parts) or relative.suffix in RUNTIME_SUFFIXES


def iter_payload_files(root: Path) -> Iterable[Path]:
    excluded = {MANIFEST_NAME, TREE_HASH_NAME}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if relative.as_posix() in excluded or is_runtime_artifact(relative):
            continue
        yield path


def build(root: Path) -> dict[str, object]:
    files = []
    for path in iter_payload_files(root):
        relative = path.relative_to(root).as_posix()
        files.append(
            {
                "path": relative,
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
        )
    manifest = {
        "schema_version": "1.0",
        "package": root.name,
        "coverage": (
            "all packaged non-runtime files except PACKAGE_MANIFEST_SEA_ICE_FIX.json "
            "and PACKAGE_TREE_SHA256_SEA_ICE_FIX.txt"
        ),
        "file_count": len(files),
        "files": files,
    }
    manifest_path = root / MANIFEST_NAME
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tree_sha = sha256_file(manifest_path)
    (root / TREE_HASH_NAME).write_text(
        f"{tree_sha}  {MANIFEST_NAME}\n",
        encoding="utf-8",
    )
    return {
        "manifest": str(manifest_path),
        "file_count": len(files),
        "manifest_sha256": tree_sha,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = build(args.root.resolve())
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
