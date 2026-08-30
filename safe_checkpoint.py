#!/usr/bin/env python3
"""Bounded, atomic serialization for resumable long-run checkpoints.

The format is a ZIP container containing exactly one JSON manifest and the
NumPy ``.npy`` arrays declared by that manifest. Loading never invokes pickle,
validates ZIP metadata and NPY headers before reading array payloads, and places
hard bounds on archive size, members, nesting, dimensions, elements, bytes,
and compression ratios.
"""
from __future__ import annotations

import io
import json
import math
import os
import uuid
import zipfile
from pathlib import Path
from typing import Any

import numpy as np

CHECKPOINT_FORMAT = "emergent-climate-model-safe-checkpoint"
CHECKPOINT_VERSION = 2
_MANIFEST_NAME = "manifest.json"
MAX_MANIFEST_BYTES = 8 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 4096
MAX_ARCHIVE_COMPRESSED_BYTES = 256 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_BYTES = 256 * 1024 * 1024
MAX_ARRAY_MEMBER_BYTES = 128 * 1024 * 1024
MAX_ARRAY_ELEMENTS = 25_000_000
MAX_ARRAY_DIMENSIONS = 8
MAX_NESTING_DEPTH = 100
MAX_COMPRESSION_RATIO = 1000.0
MAX_NPY_HEADER_BYTES = 256 * 1024
ALLOWED_ZIP_COMPRESSION_METHODS = frozenset({zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED})
ZIP_ENCRYPTED_FLAG = 0x1


class CheckpointFormatError(ValueError):
    """Raised when a checkpoint is malformed or exceeds safe resource bounds."""


def fsync_directory(path: Path) -> None:
    directory = Path(path)
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    try:
        descriptor = os.open(str(directory), flags)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _check_depth(depth: int) -> None:
    if depth > MAX_NESTING_DEPTH:
        raise CheckpointFormatError("Checkpoint value nesting exceeds the safe limit")


def _encode_value(value: Any, arrays: dict[str, np.ndarray], depth: int = 0) -> Any:
    _check_depth(depth)
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        label = "nan" if math.isnan(value) else ("positive_infinity" if value > 0 else "negative_infinity")
        return {"__type__": "nonfinite_float", "value": label}
    if isinstance(value, np.generic):
        return _encode_value(value.item(), arrays, depth + 1)
    if isinstance(value, np.ndarray):
        array = np.asarray(value)
        if array.dtype.hasobject:
            raise TypeError("Object-dtype arrays are not permitted in safe checkpoints")
        if array.ndim > MAX_ARRAY_DIMENSIONS:
            raise TypeError("Array has too many dimensions for a safe checkpoint")
        if array.size > MAX_ARRAY_ELEMENTS or array.nbytes > MAX_ARRAY_MEMBER_BYTES:
            raise TypeError("Array exceeds safe checkpoint resource limits")
        if len(arrays) + 2 > MAX_ARCHIVE_MEMBERS:
            raise TypeError("Safe checkpoint contains too many array members")
        key = f"arrays/{len(arrays):08d}.npy"
        arrays[key] = array
        return {"__type__": "ndarray", "name": key, "dtype": array.dtype.str, "shape": list(array.shape)}
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("Safe checkpoint dictionaries require string keys")
        return {"__type__": "dict", "items": {key: _encode_value(item, arrays, depth + 1) for key, item in value.items()}}
    if isinstance(value, list):
        return {"__type__": "list", "items": [_encode_value(item, arrays, depth + 1) for item in value]}
    if isinstance(value, tuple):
        return {"__type__": "tuple", "items": [_encode_value(item, arrays, depth + 1) for item in value]}
    if isinstance(value, Path):
        return {"__type__": "path", "value": str(value)}
    raise TypeError(f"Unsupported safe-checkpoint value type: {type(value).__module__}.{type(value).__qualname__}")


def _array_declarations(node: Any, declarations: dict[str, tuple[str, tuple[int, ...]]], depth: int = 0) -> None:
    _check_depth(depth)
    if not isinstance(node, dict):
        return
    kind = node.get("__type__")
    if kind == "ndarray":
        name = str(node.get("name", ""))
        dtype = str(node.get("dtype", ""))
        try:
            shape = tuple(int(value) for value in node.get("shape", []))
        except (TypeError, ValueError) as exc:
            raise CheckpointFormatError("Array declaration has an invalid shape") from exc
        if name in declarations and declarations[name] != (dtype, shape):
            raise CheckpointFormatError(f"Conflicting declarations for array {name!r}")
        declarations[name] = (dtype, shape)
        return
    if kind == "dict" and isinstance(node.get("items"), dict):
        for item in node["items"].values():
            _array_declarations(item, declarations, depth + 1)
    elif kind in {"list", "tuple"} and isinstance(node.get("items"), list):
        for item in node["items"]:
            _array_declarations(item, declarations, depth + 1)


def _decode_value(node: Any, arrays: dict[str, np.ndarray], depth: int = 0) -> Any:
    _check_depth(depth)
    if node is None or isinstance(node, (bool, str, int, float)):
        return node
    if not isinstance(node, dict):
        raise CheckpointFormatError("Checkpoint manifest contains an invalid node")
    kind = node.get("__type__")
    if kind == "nonfinite_float":
        mapping = {"nan": float("nan"), "positive_infinity": float("inf"), "negative_infinity": float("-inf")}
        if node.get("value") not in mapping:
            raise CheckpointFormatError("Unknown non-finite floating-point label")
        return mapping[node["value"]]
    if kind == "ndarray":
        name = str(node.get("name", ""))
        if name not in arrays:
            raise CheckpointFormatError(f"Missing array payload {name!r}")
        array = arrays[name]
        try:
            expected_shape = tuple(int(value) for value in node.get("shape", []))
        except (TypeError, ValueError) as exc:
            raise CheckpointFormatError("Array declaration has an invalid shape") from exc
        if array.dtype.str != str(node.get("dtype", "")) or array.shape != expected_shape:
            raise CheckpointFormatError(f"Array {name!r} does not match its manifest declaration")
        return array
    if kind == "dict":
        items = node.get("items")
        if not isinstance(items, dict):
            raise CheckpointFormatError("Dictionary node has invalid items")
        return {str(key): _decode_value(item, arrays, depth + 1) for key, item in items.items()}
    if kind in {"list", "tuple"}:
        items = node.get("items")
        if not isinstance(items, list):
            raise CheckpointFormatError(f"{kind.title()} node has invalid items")
        decoded = [_decode_value(item, arrays, depth + 1) for item in items]
        return decoded if kind == "list" else tuple(decoded)
    if kind == "path":
        if not isinstance(node.get("value"), str):
            raise CheckpointFormatError("Path node has invalid value")
        return Path(node["value"])
    raise CheckpointFormatError(f"Unsupported checkpoint node type: {kind!r}")


def _compression_ratio(info: zipfile.ZipInfo) -> float:
    if info.file_size == 0:
        return 1.0
    return float("inf") if info.compress_size <= 0 else float(info.file_size) / float(info.compress_size)


def _validate_npy_header(archive: zipfile.ZipFile, info: zipfile.ZipInfo, expected_dtype: str, expected_shape: tuple[int, ...]) -> None:
    with archive.open(info, mode="r") as handle:
        version = np.lib.format.read_magic(handle)
        if version == (1, 0):
            shape, _fortran, dtype = np.lib.format.read_array_header_1_0(handle, max_header_size=MAX_NPY_HEADER_BYTES)
        elif version == (2, 0):
            shape, _fortran, dtype = np.lib.format.read_array_header_2_0(handle, max_header_size=MAX_NPY_HEADER_BYTES)
        else:
            raise CheckpointFormatError(f"Unsupported NPY format version {version!r}")
        payload_offset = int(handle.tell())
    dtype = np.dtype(dtype)
    shape = tuple(int(value) for value in shape)
    if dtype.hasobject:
        raise CheckpointFormatError(f"Object dtype is not permitted in {info.filename!r}")
    if len(shape) > MAX_ARRAY_DIMENSIONS or any(value < 0 for value in shape):
        raise CheckpointFormatError(f"Array {info.filename!r} has an invalid shape")
    elements = math.prod(shape) if shape else 1
    if elements > MAX_ARRAY_ELEMENTS:
        raise CheckpointFormatError(f"Array {info.filename!r} has too many elements")
    data_bytes = elements * dtype.itemsize
    if data_bytes > MAX_ARRAY_MEMBER_BYTES:
        raise CheckpointFormatError(f"Array {info.filename!r} is too large")
    expected_member_bytes = payload_offset + data_bytes
    if int(info.file_size) != expected_member_bytes:
        raise CheckpointFormatError(
            f"Array {info.filename!r} has undeclared trailing or truncated bytes"
        )
    if dtype.str != expected_dtype or shape != expected_shape:
        raise CheckpointFormatError(f"Array header for {info.filename!r} does not match the manifest")


def write_checkpoint(path: Path, value: Any) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    arrays: dict[str, np.ndarray] = {}
    root = _encode_value(value, arrays)
    manifest = {"format": CHECKPOINT_FORMAT, "version": CHECKPOINT_VERSION, "root": root, "array_names": sorted(arrays)}
    manifest_bytes = json.dumps(manifest, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(manifest_bytes) > MAX_MANIFEST_BYTES:
        raise TypeError("Safe checkpoint manifest exceeds the size limit")
    total_uncompressed = len(manifest_bytes)
    try:
        with temporary.open("wb") as raw:
            with zipfile.ZipFile(raw, "w", allowZip64=True) as archive:
                # The small JSON manifest benefits from compression. Array members
                # are deliberately stored verbatim: valid constant/sparse arrays can
                # exceed the loader's anti-zip-bomb ratio when DEFLATE is used.
                archive.writestr(
                    _MANIFEST_NAME,
                    manifest_bytes,
                    compress_type=zipfile.ZIP_DEFLATED,
                    compresslevel=6,
                )
                for name in sorted(arrays):
                    buffer = io.BytesIO()
                    np.save(buffer, arrays[name], allow_pickle=False)
                    payload = buffer.getvalue()
                    if len(payload) > MAX_ARRAY_MEMBER_BYTES:
                        raise TypeError("Serialized array exceeds the checkpoint size limit")
                    total_uncompressed += len(payload)
                    if total_uncompressed > MAX_TOTAL_UNCOMPRESSED_BYTES:
                        raise TypeError("Safe checkpoint exceeds the total uncompressed size limit")
                    archive.writestr(name, payload, compress_type=zipfile.ZIP_STORED)
            raw.flush()
            os.fsync(raw.fileno())
        if temporary.stat().st_size > MAX_ARCHIVE_COMPRESSED_BYTES:
            raise TypeError("Safe checkpoint archive exceeds the compressed size limit")
        # Never replace a previous good checkpoint with bytes that the bounded
        # reader rejects. This also catches writer/reader format drift atomically.
        read_checkpoint(temporary)
        os.replace(temporary, destination)
        fsync_directory(destination.parent)
    finally:
        temporary.unlink(missing_ok=True)


def read_checkpoint(path: Path) -> Any:
    source = Path(path)
    try:
        if source.stat().st_size > MAX_ARCHIVE_COMPRESSED_BYTES:
            raise CheckpointFormatError("Checkpoint exceeds the compressed size limit")
        with zipfile.ZipFile(source, "r") as archive:
            infos = archive.infolist()
            if len(infos) > MAX_ARCHIVE_MEMBERS:
                raise CheckpointFormatError("Checkpoint contains too many archive members")
            names_list = [info.filename for info in infos]
            if len(names_list) != len(set(names_list)):
                raise CheckpointFormatError("Checkpoint contains duplicate archive members")
            info_by_name = {info.filename: info for info in infos}
            if _MANIFEST_NAME not in info_by_name:
                raise CheckpointFormatError("Checkpoint manifest is missing")
            total_uncompressed = total_compressed = 0
            for info in infos:
                name = info.filename
                if name.startswith("/") or ".." in Path(name).parts or "\\" in name:
                    raise CheckpointFormatError("Checkpoint contains an unsafe archive path")
                if int(info.flag_bits) & ZIP_ENCRYPTED_FLAG:
                    raise CheckpointFormatError(
                        f"Encrypted checkpoint member {name!r} is not permitted"
                    )
                if int(info.compress_type) not in ALLOWED_ZIP_COMPRESSION_METHODS:
                    raise CheckpointFormatError(
                        f"Unsupported ZIP compression method for checkpoint member {name!r}: "
                        f"{info.compress_type}"
                    )
                total_uncompressed += int(info.file_size)
                total_compressed += int(info.compress_size)
                if _compression_ratio(info) > MAX_COMPRESSION_RATIO:
                    raise CheckpointFormatError(f"Checkpoint member {name!r} exceeds the compression-ratio limit")
            if total_uncompressed > MAX_TOTAL_UNCOMPRESSED_BYTES:
                raise CheckpointFormatError("Checkpoint exceeds the uncompressed size limit")
            if total_compressed > MAX_ARCHIVE_COMPRESSED_BYTES:
                raise CheckpointFormatError("Checkpoint exceeds the compressed size limit")
            manifest_info = info_by_name[_MANIFEST_NAME]
            if manifest_info.file_size > MAX_MANIFEST_BYTES:
                raise CheckpointFormatError("Checkpoint manifest is unreasonably large")
            manifest = json.loads(archive.read(_MANIFEST_NAME).decode("utf-8"))
            if not isinstance(manifest, dict) or manifest.get("format") != CHECKPOINT_FORMAT or int(manifest.get("version", -1)) != CHECKPOINT_VERSION:
                raise CheckpointFormatError("Unsupported checkpoint format or version")
            expected_names = manifest.get("array_names")
            if not isinstance(expected_names, list) or not all(isinstance(name, str) for name in expected_names) or len(expected_names) != len(set(expected_names)):
                raise CheckpointFormatError("Checkpoint array list is invalid")
            declared: dict[str, tuple[str, tuple[int, ...]]] = {}
            _array_declarations(manifest.get("root"), declared)
            if set(expected_names) != set(declared):
                raise CheckpointFormatError("Checkpoint array list does not exactly match manifest references")
            exact_members = {_MANIFEST_NAME, *expected_names}
            if set(names_list) != exact_members:
                raise CheckpointFormatError(f"Checkpoint member set mismatch; extra={sorted(set(names_list)-exact_members)}, missing={sorted(exact_members-set(names_list))}")
            for name in expected_names:
                if not name.startswith("arrays/") or not name.endswith(".npy"):
                    raise CheckpointFormatError(f"Invalid array member name: {name!r}")
                info = info_by_name[name]
                if info.file_size > MAX_ARRAY_MEMBER_BYTES:
                    raise CheckpointFormatError(f"Array member {name!r} is too large")
                _validate_npy_header(archive, info, *declared[name])
            arrays: dict[str, np.ndarray] = {}
            for name in expected_names:
                payload = archive.read(name)
                buffer = io.BytesIO(payload)
                array = np.load(buffer, allow_pickle=False)
                if buffer.tell() != len(payload):
                    raise CheckpointFormatError(
                        f"Array {name!r} contains undeclared trailing bytes"
                    )
                if not isinstance(array, np.ndarray) or array.dtype.hasobject:
                    raise CheckpointFormatError(f"Unsafe array payload in {name!r}")
                arrays[name] = array
            return _decode_value(manifest.get("root"), arrays)
    except CheckpointFormatError:
        raise
    except (OSError, RecursionError, zipfile.BadZipFile, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise CheckpointFormatError(f"Unreadable safe checkpoint {source}: {exc}") from exc
