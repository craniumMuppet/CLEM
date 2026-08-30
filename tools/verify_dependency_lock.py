#!/usr/bin/env python3
"""Verify exact dependency versions and platform-matched installed hashes.

The lock records one tested platform's installed-file hashes. Exact package
versions are portable release requirements, but installed-file hashes are not:
wheels legitimately differ across operating systems, architectures and Python
builds. Hash verification is therefore enabled only when the current runtime
matches the recorded implementation, platform and Python version exactly.
"""
from __future__ import annotations

import hashlib
import importlib.metadata as metadata
import json
import platform
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / "dependency_integrity.lock.json").read_text(encoding="utf-8"))
errors: list[str] = []

project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
project_version = str(project["project"]["version"])
if LOCK.get("model_version") != project_version:
    errors.append(
        f"model_version mismatch: lock={LOCK.get('model_version')!r}, project={project_version!r}"
    )
canonical_graph = json.dumps(
    LOCK.get("packages", {}), sort_keys=True, separators=(",", ":")
).encode("utf-8")
actual_graph_sha256 = hashlib.sha256(canonical_graph).hexdigest()
if LOCK.get("graph_sha256") != actual_graph_sha256:
    errors.append("dependency graph SHA-256 mismatch")

recorded = LOCK.get("generated_for", {})
current = {
    "implementation": platform.python_implementation(),
    "platform": platform.platform(),
    "python": platform.python_version(),
}
verify_installed_hashes = all(
    str(recorded.get(key, "")) == current[key]
    for key in ("implementation", "platform", "python")
)

for package_name, expected in LOCK["packages"].items():
    try:
        distribution = metadata.distribution(package_name)
    except metadata.PackageNotFoundError:
        errors.append(f"missing: {package_name}=={expected['version']}")
        continue
    if distribution.version != expected["version"]:
        errors.append(
            f"version mismatch: {package_name} expected {expected['version']} "
            f"got {distribution.version}"
        )
        continue
    expected_digest = expected.get("installed_content_sha256")
    if not expected_digest or not verify_installed_hashes:
        continue
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
    if digest.hexdigest() != expected_digest:
        errors.append(f"content hash mismatch: {package_name}")

if errors:
    raise SystemExit("Dependency lock verification failed:\n- " + "\n- ".join(errors))
mode = "versions and installed hashes" if verify_installed_hashes else "exact versions"
print(f"Dependency lock verified for {len(LOCK['packages'])} packages ({mode}).")
