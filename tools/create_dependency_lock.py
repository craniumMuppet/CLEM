#!/usr/bin/env python3
"""Refresh platform provenance and installed-content hashes in the dependency lock."""

from __future__ import annotations

import hashlib
import importlib.metadata as metadata
import json
import platform
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "dependency_integrity.lock.json"
MODEL_VERSION = "2.29.28"


def installed_content_sha256(distribution: metadata.Distribution) -> str:
    digest = hashlib.sha256()
    for relative_path in sorted(distribution.files or [], key=str):
        path = distribution.locate_file(relative_path)
        if not path.is_file():
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        digest.update(str(relative_path).encode("utf-8"))
        digest.update(b"\0")
        digest.update(data)
        digest.update(b"\0")
    return digest.hexdigest()


def main() -> None:
    payload = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    for package_name, expected in payload["packages"].items():
        distribution = metadata.distribution(package_name)
        if distribution.version != expected["version"]:
            raise SystemExit(
                f"Cannot refresh lock: {package_name} expected {expected['version']}, "
                f"found {distribution.version}"
            )
        expected["installed_content_sha256"] = installed_content_sha256(distribution)
    payload["generated_for"] = {
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "python": platform.python_version(),
    }
    payload["model_version"] = MODEL_VERSION
    canonical_graph = json.dumps(
        payload["packages"], sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    payload["graph_sha256"] = hashlib.sha256(canonical_graph).hexdigest()
    LOCK_PATH.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"Refreshed {LOCK_PATH.name} for {MODEL_VERSION} on "
        f"{payload['generated_for']['platform']} / Python {payload['generated_for']['python']}"
    )


if __name__ == "__main__":
    main()
