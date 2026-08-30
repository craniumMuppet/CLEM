"""Cryptographic provenance envelopes for resumable validation tasks."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from runtime_provenance import runtime_provenance_digest

TASK_RECORD_SCHEMA_VERSION = "1.1"
SOURCE_SUFFIXES = {".py", ".json", ".csv", ".npz", ".toml", ".lock"}
EXCLUDED_DIR_NAMES = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    "outputs",
    "output",
}
GENERATED_TOP_LEVEL_PREFIXES = (
    "VALIDATION_SUMMARY_",
    "DEEP_VALIDATION_",
    "IMPLEMENTATION_AUDIT_",
    "PACKAGE_FILE_MANIFEST_",
    "V2_29_15_REVIEW_REPRODUCTION",
    "V2_29_16_REVIEW_REPRODUCTION",
)
GENERATED_DIR_PREFIXES = ("validation_v",)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_files(root: Path) -> list[Path]:
    """Return deterministic model, validator, test, configuration, and data inputs."""

    root = Path(root).resolve()
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        relative = path.relative_to(root)
        if any(part in EXCLUDED_DIR_NAMES for part in relative.parts):
            continue
        if relative.parts and relative.parts[0].startswith(GENERATED_DIR_PREFIXES):
            continue
        if len(relative.parts) == 1 and relative.name.startswith(
            GENERATED_TOP_LEVEL_PREFIXES
        ):
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(root).as_posix())


def source_tree_sha256(root: Path) -> str:
    """Hash all task-relevant source/configuration/data bytes and relative paths."""

    root = Path(root).resolve()
    digest = hashlib.sha256()
    for path in source_files(root):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(relative)
        digest.update(b"\0")
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        digest.update(b"\0")
    return digest.hexdigest()


def task_configuration_sha256(
    *,
    task_name: str,
    model_version: str,
    validator_sha256: str,
    source_tree_sha256_value: str,
    runtime_provenance_sha256: str,
) -> str:
    payload = {
        "model_version": str(model_version),
        "source_tree_sha256": str(source_tree_sha256_value),
        "task_name": str(task_name),
        "validator_sha256": str(validator_sha256),
        "runtime_provenance_sha256": str(runtime_provenance_sha256),
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def expected_task_metadata(
    *, root: Path, validator_path: Path, task_name: str, model_version: str
) -> dict[str, str]:
    validator_digest = sha256_file(validator_path)
    tree_digest = source_tree_sha256(root)
    runtime_digest = runtime_provenance_digest()
    return {
        "schema_version": TASK_RECORD_SCHEMA_VERSION,
        "task_name": str(task_name),
        "model_version": str(model_version),
        "validator_sha256": validator_digest,
        "source_tree_sha256": tree_digest,
        "runtime_provenance_sha256": runtime_digest,
        "task_configuration_sha256": task_configuration_sha256(
            task_name=task_name,
            model_version=model_version,
            validator_sha256=validator_digest,
            source_tree_sha256_value=tree_digest,
            runtime_provenance_sha256=runtime_digest,
        ),
    }


def make_task_record_from_metadata(
    metadata: dict[str, str], result: Any
) -> dict[str, Any]:
    """Attach a result to a provenance snapshot captured before execution."""

    required = {
        "schema_version",
        "task_name",
        "model_version",
        "validator_sha256",
        "source_tree_sha256",
        "runtime_provenance_sha256",
        "task_configuration_sha256",
    }
    missing = sorted(required - set(metadata))
    if missing:
        raise ValueError(f"Validation task metadata is missing fields: {missing}")
    return {**metadata, "result": result}


def make_task_record(
    *,
    root: Path,
    validator_path: Path,
    task_name: str,
    model_version: str,
    result: Any,
) -> dict[str, Any]:
    """Create an immediate record when execution and hashing are atomic to the caller."""

    metadata = expected_task_metadata(
        root=root,
        validator_path=validator_path,
        task_name=task_name,
        model_version=model_version,
    )
    return make_task_record_from_metadata(metadata, result)


def validate_task_record(
    record: Any,
    *,
    root: Path,
    validator_path: Path,
    task_name: str,
    model_version: str,
) -> Any:
    """Validate a task envelope and return its result payload."""

    if not isinstance(record, dict):
        raise ValueError("Validation task record is not a JSON object.")
    expected = expected_task_metadata(
        root=root,
        validator_path=validator_path,
        task_name=task_name,
        model_version=model_version,
    )
    for key, expected_value in expected.items():
        actual = record.get(key)
        if actual != expected_value:
            raise ValueError(
                f"Validation task provenance mismatch for {key}: "
                f"expected {expected_value!r}, found {actual!r}."
            )
    if "result" not in record:
        raise ValueError("Validation task record is missing the result payload.")
    return record["result"]
