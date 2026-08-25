"""Private validation-only pickle transport with strict local-file checks.

Pickle is retained only for short-lived validation objects that contain pandas
and model dataclasses not supported by the portable checkpoint format. Files
must live under an explicitly supplied private work root, must be regular
non-symlink files owned by the current user where ownership is available, and
must carry the EGCM validation transport header. These files are never accepted
as general user inputs or release checkpoints.
"""
from __future__ import annotations

import os
import pickle
import stat
import uuid
from pathlib import Path
from typing import Any

_MAGIC = b"EGCM_PRIVATE_VALIDATION_PICKLE_V1\n"


class UntrustedValidationPickleError(ValueError):
    """Raised when a validation pickle is outside its private trust boundary."""


def _resolved_under(path: Path, trusted_root: Path) -> tuple[Path, Path]:
    root = Path(trusted_root).expanduser().resolve()
    candidate = Path(path).expanduser()
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise UntrustedValidationPickleError(
            f"Validation pickle path escapes trusted root: {candidate}"
        ) from exc
    return resolved, root


def _check_private_root(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    if root.is_symlink() or not root.is_dir():
        raise UntrustedValidationPickleError(
            f"Trusted validation root is not a private directory: {root}"
        )
    if os.name == "posix":
        info = root.stat()
        if hasattr(os, "geteuid") and info.st_uid != os.geteuid():
            raise UntrustedValidationPickleError(
                f"Trusted validation root is not owned by the current user: {root}"
            )
        if info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise UntrustedValidationPickleError(
                f"Trusted validation root is group/world writable: {root}"
            )


def dump_trusted_pickle(path: Path, value: Any, trusted_root: Path) -> None:
    """Atomically write one private validation transport file."""

    destination, root = _resolved_under(Path(path), Path(trusted_root))
    _check_private_root(root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination_parent, _ = _resolved_under(destination.parent, root)
    if destination_parent.is_symlink():
        raise UntrustedValidationPickleError(
            f"Validation pickle parent cannot be a symlink: {destination_parent}"
        )
    temporary = destination.with_name(
        f".{destination.name}.{uuid.uuid4().hex}.tmp"
    )
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(temporary, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(_MAGIC)
            pickle.dump(value, handle, protocol=pickle.HIGHEST_PROTOCOL)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        try:
            os.chmod(destination, 0o600)
        except OSError:
            pass
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        temporary.unlink(missing_ok=True)
        raise


def load_trusted_pickle(path: Path, trusted_root: Path) -> Any:
    """Load a private validation transport file after trust-boundary checks."""

    source, root = _resolved_under(Path(path), Path(trusted_root))
    _check_private_root(root)
    if source.is_symlink() or not source.is_file():
        raise UntrustedValidationPickleError(
            f"Validation pickle must be a regular non-symlink file: {source}"
        )
    info = source.stat()
    if os.name == "posix":
        if hasattr(os, "geteuid") and info.st_uid != os.geteuid():
            raise UntrustedValidationPickleError(
                f"Validation pickle is not owned by the current user: {source}"
            )
        if info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise UntrustedValidationPickleError(
                f"Validation pickle is group/world writable: {source}"
            )
    with source.open("rb") as handle:
        if handle.read(len(_MAGIC)) != _MAGIC:
            raise UntrustedValidationPickleError(
                f"Validation pickle lacks the required private transport header: {source}"
            )
        return pickle.load(handle)
