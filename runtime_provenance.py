#!/usr/bin/env python3
"""Source, dependency, build, and numerical-backend provenance for resume safety."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import scipy

ROOT = Path(__file__).resolve().parent
_EXCLUDED_PREFIXES = ("validate_", "deep_validation", "full_regression", "run_tests", "run_v216_validation", "isolated_pytest_exit")
_EXCLUDED_SUFFIXES = ("_test.py",)
_RUNTIME_ASSETS = (
    "data/ssp_pathways_rcmip_v5_1_0.csv", "data/world_grid_5deg.npz",
    "calibration_targets.json", "development_regression_benchmarks.json",
    "held_out_amoc_benchmarks.json", "requirements.lock", "requirements-dev.lock",
    "dependency_integrity.lock.json", "pyproject.toml",
)
_DISTRIBUTIONS = ("numpy", "pandas", "scipy", "matplotlib")
_NUMERICAL_ENVIRONMENT_VARIABLES = (
    "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS", "BLIS_NUM_THREADS",
    "OMP_DYNAMIC", "OMP_PROC_BIND",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _runtime_source_paths(root: Path) -> list[Path]:
    paths: list[Path] = []
    for path in root.glob("*.py"):
        if path.name.startswith(_EXCLUDED_PREFIXES) or path.name.endswith(_EXCLUDED_SUFFIXES):
            continue
        paths.append(path)
    for relative in _RUNTIME_ASSETS:
        path = root / relative
        if path.is_file():
            paths.append(path)
    return sorted(set(paths), key=lambda item: item.relative_to(root).as_posix())


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return str(value)


def _distribution_record(distribution_name: str) -> dict[str, Any]:
    try:
        distribution = importlib.metadata.distribution(distribution_name)
    except importlib.metadata.PackageNotFoundError:
        return {"version": "not-installed", "metadata_hashes": {}, "installed_content_sha256": None, "hashed_file_count": 0, "hashed_bytes": 0}
    metadata_hashes: dict[str, str] = {}
    digest = hashlib.sha256()
    file_count = 0
    total_bytes = 0
    for item in sorted(distribution.files or [], key=lambda value: str(value).replace("\\", "/")):
        relative = str(item).replace("\\", "/")
        path = Path(distribution.locate_file(item))
        if not path.is_file():
            continue
        file_count += 1
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        file_digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                file_digest.update(block)
                digest.update(block)
                total_bytes += len(block)
        if Path(relative).name in {"RECORD", "WHEEL", "METADATA", "direct_url.json"}:
            metadata_hashes[relative] = file_digest.hexdigest()
        digest.update(b"\0")
    return {
        "version": distribution.version,
        "metadata_hashes": dict(sorted(metadata_hashes.items())),
        "installed_content_sha256": digest.hexdigest(),
        "hashed_file_count": file_count,
        "hashed_bytes": total_bytes,
    }


def _cpu_dispatch() -> dict[str, Any]:
    try:
        from numpy._core import _multiarray_umath as multiarray
        features = getattr(multiarray, "__cpu_features__", {})
        baseline = getattr(multiarray, "__cpu_baseline__", ())
        dispatch = getattr(multiarray, "__cpu_dispatch__", ())
        return {
            "features": {str(key): bool(value) for key, value in sorted(features.items())},
            "baseline": sorted(str(value) for value in baseline),
            "dispatch": sorted(str(value) for value in dispatch),
        }
    except Exception as exc:
        return {"unavailable": f"{type(exc).__name__}: {exc}"}


def _numerical_build() -> dict[str, Any]:
    return {
        "numpy_config": _json_safe(getattr(np.__config__, "CONFIG", {})),
        "scipy_config": _json_safe(getattr(scipy.__config__, "CONFIG", {})),
        "numpy_cpu_dispatch": _cpu_dispatch(),
        "python_compiler": platform.python_compiler(),
        "python_build": list(platform.python_build()),
        "libc": list(platform.libc_ver()),
        "thread_environment": {name: os.environ.get(name) for name in _NUMERICAL_ENVIRONMENT_VARIABLES},
    }


@lru_cache(maxsize=1)
def runtime_provenance() -> dict[str, Any]:
    files = {path.relative_to(ROOT).as_posix(): sha256_file(path) for path in _runtime_source_paths(ROOT)}
    source_digest = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    distributions = {name: _distribution_record(name) for name in _DISTRIBUTIONS}
    environment = {
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "python_cache_tag": sys.implementation.cache_tag,
        "platform_system": platform.system(),
        "platform_release": platform.release(),
        "platform_version": platform.version(),
        "platform_machine": platform.machine(),
        "distributions": distributions,
        "numerical_build": _numerical_build(),
    }
    environment_digest = hashlib.sha256(json.dumps(environment, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    combined_digest = hashlib.sha256(f"{source_digest}:{environment_digest}".encode("ascii")).hexdigest()
    return {
        "format": "emergent-climate-model-runtime-provenance",
        "version": 2,
        "source_files": files,
        "source_digest_sha256": source_digest,
        "environment": environment,
        "environment_digest_sha256": environment_digest,
        "combined_digest_sha256": combined_digest,
        "python_executable_name": Path(sys.executable).name,
    }


def runtime_provenance_digest() -> str:
    return str(runtime_provenance()["combined_digest_sha256"])
