#!/usr/bin/env python3
"""Verify the exact non-runtime file set and hashes for the sea-ice-fix tree."""

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


def verify(root: Path) -> dict[str, object]:
    manifest_path = root / MANIFEST_NAME
    tree_hash_path = root / TREE_HASH_NAME
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    if not tree_hash_path.is_file():
        raise FileNotFoundError(tree_hash_path)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = {entry["path"]: entry for entry in manifest["files"]}
    actual_paths = {path.relative_to(root).as_posix(): path for path in iter_payload_files(root)}

    missing = sorted(set(expected) - set(actual_paths))
    unexpected = sorted(set(actual_paths) - set(expected))
    mismatches: list[dict[str, object]] = []
    for relative in sorted(set(expected) & set(actual_paths)):
        path = actual_paths[relative]
        actual_size = path.stat().st_size
        actual_sha = sha256_file(path)
        item = expected[relative]
        if actual_size != item["size_bytes"] or actual_sha != item["sha256"]:
            mismatches.append(
                {
                    "path": relative,
                    "expected_size_bytes": item["size_bytes"],
                    "actual_size_bytes": actual_size,
                    "expected_sha256": item["sha256"],
                    "actual_sha256": actual_sha,
                }
            )

    manifest_sha = sha256_file(manifest_path)
    declared_tree_sha = tree_hash_path.read_text(encoding="utf-8").strip().split()[0]
    tree_hash_matches = manifest_sha == declared_tree_sha
    result = {
        "root": str(root),
        "expected_file_count": len(expected),
        "actual_file_count": len(actual_paths),
        "missing": missing,
        "unexpected": unexpected,
        "mismatches": mismatches,
        "manifest_sha256": manifest_sha,
        "declared_tree_sha256": declared_tree_sha,
        "tree_hash_matches": tree_hash_matches,
        "passed": not missing and not unexpected and not mismatches and tree_hash_matches,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args()
    result = verify(args.root.resolve())
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(
            f"manifest verification: {'PASS' if result['passed'] else 'FAIL'}; "
            f"files={result['actual_file_count']}"
        )
        if not result["passed"]:
            print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
