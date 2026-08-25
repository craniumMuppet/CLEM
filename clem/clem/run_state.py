#!/usr/bin/env python3
"""Durable save/load, locking, and explicit recovery for long scientific runs."""

from __future__ import annotations

import json
import os
import shutil
import socket
import time
import uuid
from pathlib import Path
from typing import Any, Iterable

from safe_checkpoint import CheckpointFormatError, fsync_directory, read_checkpoint

RUN_STATE_FILENAME = "long_run_state.json"
RUN_STATE_BACKUP_FILENAME = "long_run_state.previous.json"
RUN_STATE_FORMAT = "emergent-climate-model-long-run-state"
RUN_STATE_VERSION = 3
RUN_LOCK_SUFFIX = ".egcm-run.lock"
STATE_UPDATE_LOCK_FILENAME = ".long_run_state.update.lock"
_MAX_RECOVERY_CHECKPOINTS = 1_000_000
_STATE_LOCK_TIMEOUT_SECONDS = 60.0
_STATE_LOCK_POLL_SECONDS = 0.05
_MALFORMED_LOCK_STALE_SECONDS = 3600.0
_REMOTE_LOCK_STALE_SECONDS = 30.0 * 24.0 * 3600.0
_LOCK_GATE_TIMEOUT_SECONDS = 10.0
_LOCK_GATE_POLL_SECONDS = 0.01


class OutputDirectoryLockedError(RuntimeError):
    """Raised when another live process owns an output-directory run lock."""


def _atomic_copy(source: Path, destination: Path) -> None:
    """Durably copy one file without exposing a partial destination."""

    source = Path(source)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    try:
        with source.open("rb") as reader, temporary.open("wb") as writer:
            shutil.copyfileobj(reader, writer, length=1024 * 1024)
            writer.flush()
            os.fsync(writer.fileno())
        os.replace(temporary, destination)
        fsync_directory(destination.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_write_json(
    path: Path,
    payload: dict[str, Any],
    *,
    preserve_previous: bool = True,
) -> None:
    """Write JSON durably and preserve the previous valid state as a backup."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if preserve_previous and path.exists():
        _atomic_copy(path, path.with_name(RUN_STATE_BACKUP_FILENAME))
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _process_start_marker(pid: int) -> str | None:
    """Return a platform process-creation marker that detects PID reuse."""

    pid = int(pid)
    if pid <= 0:
        return None
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            process_query_limited_information = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(
                process_query_limited_information, False, pid
            )
            if not handle:
                return None
            try:
                creation = wintypes.FILETIME()
                exit_time = wintypes.FILETIME()
                kernel = wintypes.FILETIME()
                user = wintypes.FILETIME()
                ok = ctypes.windll.kernel32.GetProcessTimes(
                    handle,
                    ctypes.byref(creation),
                    ctypes.byref(exit_time),
                    ctypes.byref(kernel),
                    ctypes.byref(user),
                )
                if not ok:
                    return None
                value = (int(creation.dwHighDateTime) << 32) | int(
                    creation.dwLowDateTime
                )
                return f"windows-filetime:{value}"
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
        except Exception:
            return None

    stat_path = Path(f"/proc/{pid}/stat")
    try:
        text = stat_path.read_text(encoding="utf-8")
        closing = text.rfind(")")
        if closing < 0:
            return None
        fields_after_comm = text[closing + 2 :].split()
        start_ticks = fields_after_comm[19]
        try:
            boot_id = Path("/proc/sys/kernel/random/boot_id").read_text(
                encoding="utf-8"
            ).strip()
        except OSError:
            boot_id = "unknown-boot"
        return f"linux-proc:{boot_id}:{start_ticks}"
    except (OSError, IndexError, ValueError):
        return None


def _pid_is_running(pid: int) -> bool:
    pid = int(pid)
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            process_query_limited_information = 0x1000
            still_active = 259
            handle = ctypes.windll.kernel32.OpenProcess(
                process_query_limited_information, False, pid
            )
            if not handle:
                return False
            try:
                exit_code = wintypes.DWORD()
                ok = ctypes.windll.kernel32.GetExitCodeProcess(
                    handle, ctypes.byref(exit_code)
                )
                return bool(ok and int(exit_code.value) == still_active)
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
        except Exception:
            return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _read_lock_record(path: Path) -> dict[str, Any] | None:
    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _lock_age_seconds(path: Path, record: dict[str, Any] | None) -> float:
    now = time.time()
    if isinstance(record, dict):
        try:
            return max(0.0, now - float(record.get("acquired_unix_seconds")))
        except (TypeError, ValueError):
            pass
    try:
        return max(0.0, now - Path(path).stat().st_mtime)
    except OSError:
        return float("inf")


def _lock_is_stale(path: Path, record: dict[str, Any] | None) -> bool:
    if not isinstance(record, dict):
        return _lock_age_seconds(path, record) >= _MALFORMED_LOCK_STALE_SECONDS
    try:
        pid = int(record["pid"])
        hostname = str(record["hostname"])
    except (KeyError, TypeError, ValueError):
        return _lock_age_seconds(path, record) >= _MALFORMED_LOCK_STALE_SECONDS

    if hostname != socket.gethostname():
        return _lock_age_seconds(path, record) >= _REMOTE_LOCK_STALE_SECONDS
    if not _pid_is_running(pid):
        return True
    stored_marker = record.get("process_start_marker")
    current_marker = _process_start_marker(pid)
    if stored_marker and current_marker and str(stored_marker) != current_marker:
        return True
    return False


def _format_lock_owner(record: dict[str, Any] | None) -> str:
    if not isinstance(record, dict):
        return "unknown owner (lock metadata is unreadable)"
    acquired = record.get("acquired_unix_seconds")
    acquired_text = "unknown time"
    try:
        acquired_text = time.strftime(
            "%Y-%m-%d %H:%M:%S %Z", time.localtime(float(acquired))
        )
    except (TypeError, ValueError, OSError):
        pass
    return (
        f"PID {record.get('pid', '?')} on {record.get('hostname', '?')} "
        f"since {acquired_text} ({record.get('purpose', 'unknown purpose')})"
    )


class _LockAcquisitionGate:
    """Crash-safe OS lock serializing owner-file acquisition and reclamation.

    The durable JSON owner file records who owns a long run.  This short-lived
    advisory gate protects only the create/check/reclaim transaction so two
    contenders cannot both delete or replace the same stale owner record.  OS
    advisory locks are released automatically when a process exits.
    """

    def __init__(self, owner_path: Path) -> None:
        self.path = Path(owner_path).with_name(Path(owner_path).name + ".gate")
        self.descriptor: int | None = None

    def acquire(self) -> "_LockAcquisitionGate":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(str(self.path), os.O_RDWR | os.O_CREAT, 0o600)
        try:
            if os.name == "nt":
                import msvcrt

                if os.fstat(descriptor).st_size == 0:
                    os.write(descriptor, b"\0")
                    os.fsync(descriptor)
                deadline = time.monotonic() + _LOCK_GATE_TIMEOUT_SECONDS
                while True:
                    try:
                        os.lseek(descriptor, 0, os.SEEK_SET)
                        msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
                        break
                    except OSError as exc:
                        if time.monotonic() >= deadline:
                            raise RuntimeError(
                                f"Timed out acquiring lock-transaction gate {self.path}."
                            ) from exc
                        time.sleep(_LOCK_GATE_POLL_SECONDS)
            else:
                import fcntl

                deadline = time.monotonic() + _LOCK_GATE_TIMEOUT_SECONDS
                while True:
                    try:
                        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError as exc:
                        if time.monotonic() >= deadline:
                            raise RuntimeError(
                                f"Timed out acquiring lock-transaction gate {self.path}."
                            ) from exc
                        time.sleep(_LOCK_GATE_POLL_SECONDS)
        except BaseException:
            os.close(descriptor)
            raise
        self.descriptor = descriptor
        return self

    def release(self) -> None:
        descriptor = self.descriptor
        if descriptor is None:
            return
        try:
            if os.name == "nt":
                import msvcrt

                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)
            self.descriptor = None

    def __enter__(self) -> "_LockAcquisitionGate":
        return self.acquire()

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.release()


class _ExclusiveFileLock:
    """Portable owner lock with transactional stale-lock reclamation."""

    def __init__(
        self,
        path: Path,
        *,
        purpose: str,
        output_dir: Path,
        timeout_seconds: float,
        poll_seconds: float = _STATE_LOCK_POLL_SECONDS,
    ) -> None:
        self.path = Path(path)
        self.purpose = str(purpose)
        self.output_dir = Path(output_dir).resolve()
        self.timeout_seconds = max(float(timeout_seconds), 0.0)
        self.poll_seconds = max(float(poll_seconds), 0.01)
        self.token = uuid.uuid4().hex
        self.acquired = False

    def _record(self) -> dict[str, Any]:
        return {
            "format": "emergent-climate-model-exclusive-lock",
            "version": 1,
            "token": self.token,
            "pid": os.getpid(),
            "hostname": socket.gethostname(),
            "process_start_marker": _process_start_marker(os.getpid()),
            "acquired_unix_seconds": time.time(),
            "purpose": self.purpose,
            "output_directory": str(self.output_dir),
        }

    def _create_owner_file(self) -> None:
        descriptor = os.open(
            str(self.path),
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        try:
            payload = json.dumps(
                self._record(), sort_keys=True, indent=2
            ).encode("utf-8") + b"\n"
            os.write(descriptor, payload)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        fsync_directory(self.path.parent)

    def acquire(self) -> "_ExclusiveFileLock":
        if self.acquired:
            return self
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            blocking_record: dict[str, Any] | None = None
            with _LockAcquisitionGate(self.path):
                try:
                    self._create_owner_file()
                except FileExistsError:
                    record = _read_lock_record(self.path)
                    if _lock_is_stale(self.path, record):
                        try:
                            self.path.unlink()
                            fsync_directory(self.path.parent)
                        except FileNotFoundError:
                            pass
                        try:
                            self._create_owner_file()
                        except FileExistsError:
                            blocking_record = _read_lock_record(self.path)
                    else:
                        blocking_record = record

            if blocking_record is None and self.path.exists():
                record = _read_lock_record(self.path)
                if isinstance(record, dict) and record.get("token") == self.token:
                    self.acquired = True
                    return self

            if time.monotonic() >= deadline:
                error_type = (
                    OutputDirectoryLockedError
                    if self.purpose.startswith("long-run:")
                    else RuntimeError
                )
                raise error_type(
                    f"Output directory is already locked by "
                    f"{_format_lock_owner(blocking_record)}: {self.output_dir}"
                )
            time.sleep(self.poll_seconds)

    def release(self) -> None:
        if not self.acquired:
            return
        with _LockAcquisitionGate(self.path):
            record = _read_lock_record(self.path)
            if isinstance(record, dict) and record.get("token") == self.token:
                try:
                    self.path.unlink()
                    fsync_directory(self.path.parent)
                except FileNotFoundError:
                    pass
        self.acquired = False

    def __enter__(self) -> "_ExclusiveFileLock":
        return self.acquire()

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.release()


def output_run_lock_path(output_dir: Path) -> Path:
    """Use a sibling lock so overwrite preparation cannot delete the lock itself."""

    output = Path(output_dir).expanduser().resolve()
    return output.parent / f".{output.name}{RUN_LOCK_SUFFIX}"


def output_directory_run_lock(
    output_dir: Path,
    *,
    run_kind: str,
) -> _ExclusiveFileLock:
    """Return an immediately exclusive lock covering one output directory run."""

    output = Path(output_dir).expanduser().resolve()
    return _ExclusiveFileLock(
        output_run_lock_path(output),
        purpose=f"long-run:{run_kind}",
        output_dir=output,
        timeout_seconds=0.0,
    )


def _state_update_lock(path: Path) -> _ExclusiveFileLock:
    state_path = Path(path)
    return _ExclusiveFileLock(
        state_path.parent / STATE_UPDATE_LOCK_FILENAME,
        purpose="run-state-transaction",
        output_dir=state_path.parent,
        timeout_seconds=_STATE_LOCK_TIMEOUT_SECONDS,
    )


def run_state_path(output_dir: Path) -> Path:
    return Path(output_dir) / RUN_STATE_FILENAME


def run_state_backup_path(output_dir: Path) -> Path:
    return Path(output_dir) / RUN_STATE_BACKUP_FILENAME


def _load_state_file(path: Path) -> dict[str, Any]:
    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Saved run state is unreadable: {path}: {exc}") from exc
    if not isinstance(state, dict):
        raise ValueError(f"Saved run state must contain a JSON object: {path}")
    if state.get("format") != RUN_STATE_FORMAT:
        raise ValueError(f"Unsupported saved run state format in {path}")
    try:
        version = int(state.get("state_version", -1))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid saved run state version in {path}") from exc
    if version != RUN_STATE_VERSION:
        raise ValueError(
            f"Unsupported saved run state version in {path}: "
            f"{state.get('state_version')!r}; expected {RUN_STATE_VERSION}."
        )
    required = {
        "run_kind",
        "model_version",
        "fingerprint",
        "seed_used",
        "checkpoint_directory",
        "total_work_units",
        "work_unit_name",
        "settings",
    }
    missing = sorted(required.difference(state))
    if missing:
        raise ValueError(f"Saved run state is missing required fields in {path}: {missing}")
    return state


def load_run_state(output_dir: Path) -> dict[str, Any] | None:
    """Load the primary run state, or return None only when it is absent."""

    path = run_state_path(output_dir)
    if not path.exists():
        return None
    return _load_state_file(path)


def saved_seed_for_resume(
    output_dir: Path,
    *,
    run_kind: str,
    requested_seed: int,
    resume: bool,
) -> tuple[int | None, str | None, dict[str, Any] | None]:
    """Return the persisted resolved seed before samples are regenerated."""

    if not resume:
        return None, None, None
    state = load_run_state(output_dir)
    if state is None:
        raise ValueError(
            "Resume was requested, but no long_run_state.json exists in the selected "
            "output folder. Start fresh with overwrite, select the correct folder, or "
            "run recover_run_state.py explicitly."
        )
    if str(state.get("run_kind")) != str(run_kind):
        raise ValueError(
            "The selected output folder contains saved progress for "
            f"{state.get('run_kind')!r}, not {run_kind!r}."
        )
    saved_seed = int(state["seed_used"])
    requested_seed = int(requested_seed)
    if requested_seed not in (0, saved_seed):
        raise ValueError(
            "The requested random seed does not match the saved run: "
            f"requested {requested_seed}, saved {saved_seed}. Use seed 0 or "
            "the saved seed when resuming."
        )
    return saved_seed, "saved_progress", state


def initialize_run_state(
    output_dir: Path,
    *,
    run_kind: str,
    model_version: str,
    fingerprint: str,
    seed_requested: int,
    seed_used: int,
    seed_source: str,
    checkpoint_directory: str,
    total_work_units: int,
    work_unit_name: str,
    resume: bool,
    settings: dict[str, Any],
    extra: dict[str, Any] | None = None,
) -> Path:
    """Create a fresh state or strictly validate an existing resumable state."""

    output_dir = Path(output_dir)
    path = run_state_path(output_dir)
    with _state_update_lock(path):
        existing = load_run_state(output_dir) if resume else None
        if resume and existing is None:
            raise ValueError(
                "Resume was requested, but no long_run_state.json exists in the selected "
                "output folder. Start fresh with overwrite, select the correct folder, or "
                "run recover_run_state.py explicitly."
            )
        now = time.time()
        if existing is not None:
            if str(existing.get("run_kind")) != str(run_kind):
                raise ValueError(
                    f"Saved progress belongs to {existing.get('run_kind')!r}, not {run_kind!r}."
                )
            if str(existing.get("fingerprint")) != str(fingerprint):
                raise ValueError(
                    "Saved progress is incompatible with the current settings, source, or "
                    "runtime environment. Restore the original release/settings or start a "
                    "fresh output folder."
                )
            state = dict(existing)
            state.update(
                {
                    "status": "running",
                    "updated_unix_seconds": now,
                    "last_error": None,
                    "resume_count": int(existing.get("resume_count", 0)) + 1,
                }
            )
        else:
            total = int(total_work_units)
            state = {
                "format": RUN_STATE_FORMAT,
                "state_version": RUN_STATE_VERSION,
                "run_kind": str(run_kind),
                "model_version": str(model_version),
                "status": "running",
                "fingerprint": str(fingerprint),
                "seed_requested": int(seed_requested),
                "seed_used": int(seed_used),
                "seed_source": str(seed_source),
                "checkpoint_directory": str(checkpoint_directory),
                "total_work_units": total,
                "completed_work_units": 0,
                "attempted_work_units": 0,
                "successful_work_units": 0,
                "failed_work_units": 0,
                "validated_work_units": 0,
                "pending_work_units": total,
                "resumed_work_units": 0,
                "work_unit_name": str(work_unit_name),
                "settings": settings,
                "created_unix_seconds": now,
                "updated_unix_seconds": now,
                "completed_unix_seconds": None,
                "resume_count": 0,
                "last_error": None,
            }
            if extra:
                state.update(extra)
        _atomic_write_json(path, state)
    return path


def update_run_state(path: Path, **updates: Any) -> dict[str, Any]:
    """Transactionally merge progress fields into an existing state file."""

    path = Path(path)
    with _state_update_lock(path):
        state = _load_state_file(path)
        state.update(updates)
        total = int(state.get("total_work_units", 0))
        attempted = int(
            state.get(
                "attempted_work_units",
                state.get("completed_work_units", 0),
            )
        )
        state["attempted_work_units"] = attempted
        state["completed_work_units"] = attempted
        state["successful_work_units"] = int(
            state.get("successful_work_units", 0)
        )
        state["failed_work_units"] = int(state.get("failed_work_units", 0))
        state["validated_work_units"] = int(
            state.get("validated_work_units", state["successful_work_units"])
        )
        state["pending_work_units"] = int(
            state.get("pending_work_units", max(total - attempted, 0))
        )
        state["updated_unix_seconds"] = time.time()
        if (
            str(state.get("status", "")).startswith("completed")
            and state.get("completed_unix_seconds") is None
        ):
            state["completed_unix_seconds"] = state["updated_unix_seconds"]
        _atomic_write_json(path, state)
        return state


def _checkpoint_paths(output_dir: Path, state: dict[str, Any]) -> Iterable[Path]:
    checkpoint_name = str(state.get("checkpoint_directory", "")).strip()
    if not checkpoint_name:
        return ()
    root = Path(output_dir) / checkpoint_name
    if not root.is_dir():
        return ()
    if str(state.get("run_kind")) == "co2_target_sweep":
        return root.rglob("target_*.ckpt")
    return root.glob("member_*.ckpt")


_FAILED_CHECKPOINT_STATUSES = {"failed", "error", "timeout", "interrupted"}


def _compatible_checkpoint_terminal_status(
    path: Path, fingerprint: str
) -> str | None:
    """Return ``successful``/``failed`` for a readable compatible terminal result."""

    try:
        record = read_checkpoint(path)
    except (OSError, CheckpointFormatError, TypeError, ValueError):
        return None
    if not isinstance(record, dict) or str(record.get("fingerprint")) != str(fingerprint):
        return None
    result = record.get("result")
    if not isinstance(result, dict):
        return None
    status = str(result.get("status", "")).lower()
    if status == "ok":
        return "successful"
    if status in _FAILED_CHECKPOINT_STATUSES:
        return "failed"
    return None


def compatible_checkpoint_progress(
    output_dir: Path, state: dict[str, Any]
) -> dict[str, int]:
    """Count readable compatible successful and failed terminal checkpoints."""

    fingerprint = str(state.get("fingerprint", ""))
    successful = 0
    failed = 0
    for index, path in enumerate(_checkpoint_paths(output_dir, state)):
        if index >= _MAX_RECOVERY_CHECKPOINTS:
            raise ValueError("Checkpoint recovery scan exceeded the safety limit.")
        status = _compatible_checkpoint_terminal_status(path, fingerprint)
        if status == "successful":
            successful += 1
        elif status == "failed":
            failed += 1
    return {
        "attempted": successful + failed,
        "successful": successful,
        "failed": failed,
    }


def compatible_checkpoint_count(output_dir: Path, state: dict[str, Any]) -> int:
    """Count only readable, compatible, successful immutable checkpoints."""

    return compatible_checkpoint_progress(output_dir, state)["successful"]


def _checkpoint_metadata_candidates(output_dir: Path) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for index, path in enumerate(Path(output_dir).rglob("*.ckpt")):
        if index >= _MAX_RECOVERY_CHECKPOINTS:
            raise ValueError("Checkpoint recovery scan exceeded the safety limit.")
        try:
            record = read_checkpoint(path)
        except (OSError, CheckpointFormatError, TypeError, ValueError):
            continue
        if not isinstance(record, dict):
            continue
        metadata = record.get("run_metadata")
        template = metadata.get("state_template") if isinstance(metadata, dict) else None
        if isinstance(template, dict):
            candidates.append(template)
    return candidates


def _state_from_checkpoint_metadata(output_dir: Path) -> dict[str, Any]:
    candidates = _checkpoint_metadata_candidates(output_dir)
    if not candidates:
        raise ValueError(
            "No recoverable run-state template was found in the saved checkpoints."
        )
    canonical = [json.dumps(item, sort_keys=True, separators=(",", ":")) for item in candidates]
    first = canonical[0]
    if any(item != first for item in canonical[1:]):
        raise ValueError(
            "Saved checkpoints contain conflicting run-state templates; automatic "
            "reconstruction is unsafe."
        )
    return dict(candidates[0])


def _validate_reconstructed_state(output_dir: Path, state: dict[str, Any]) -> dict[str, Any]:
    temporary = Path(output_dir) / f".{RUN_STATE_FILENAME}.recovery-{uuid.uuid4().hex}.json"
    try:
        _atomic_write_json(temporary, state, preserve_previous=False)
        return _load_state_file(temporary)
    finally:
        temporary.unlink(missing_ok=True)


def _recovery_states_are_compatible(
    backup: dict[str, Any], checkpoint_template: dict[str, Any]
) -> bool:
    """Require both recovery sources to describe the same immutable run."""

    identity_fields = (
        "format",
        "state_version",
        "run_kind",
        "model_version",
        "fingerprint",
        "seed_used",
        "checkpoint_directory",
        "total_work_units",
        "work_unit_name",
        "settings",
    )
    return all(backup.get(field) == checkpoint_template.get(field) for field in identity_fields)


def recover_run_state(output_dir: Path) -> dict[str, Any]:
    """Recover primary state from compatible backup/checkpoint evidence."""

    output_dir = Path(output_dir)
    with output_directory_run_lock(output_dir, run_kind="state_recovery"):
        primary = run_state_path(output_dir)
        backup = run_state_backup_path(output_dir)
        failures: list[str] = []

        backup_state: dict[str, Any] | None = None
        checkpoint_state: dict[str, Any] | None = None
        if backup.exists():
            try:
                backup_state = _load_state_file(backup)
            except ValueError as exc:
                failures.append(f"backup: {exc}")

        try:
            checkpoint_state = _validate_reconstructed_state(
                output_dir, _state_from_checkpoint_metadata(output_dir)
            )
        except ValueError as exc:
            failures.append(f"checkpoint metadata: {exc}")

        state: dict[str, Any] | None = None
        recovery_source: str | None = None
        if backup_state is not None and checkpoint_state is not None:
            if _recovery_states_are_compatible(backup_state, checkpoint_state):
                state = backup_state
                recovery_source = RUN_STATE_BACKUP_FILENAME
            else:
                failures.append(
                    "backup: valid state is semantically incompatible with the "
                    "recoverable checkpoint run identity"
                )
                state = checkpoint_state
                recovery_source = "checkpoint_metadata"
        elif backup_state is not None:
            state = backup_state
            recovery_source = RUN_STATE_BACKUP_FILENAME
        elif checkpoint_state is not None:
            state = checkpoint_state
            recovery_source = "checkpoint_metadata"

        if state is None or recovery_source is None:
            raise ValueError(
                "Run-state recovery failed after trying all sources: "
                + " | ".join(failures)
            )

        paths = list(_checkpoint_paths(output_dir, state))
        checkpoint_progress = compatible_checkpoint_progress(output_dir, state)
        terminal = int(checkpoint_progress["attempted"])
        validated = int(checkpoint_progress["successful"])
        checkpoint_failed = int(checkpoint_progress["failed"])
        if paths and terminal <= 0:
            raise ValueError(
                "Recovery found checkpoint files, but none contained a readable, "
                "compatible terminal result for the reconstructed run fingerprint."
            )
        total = int(state.get("total_work_units", 0))
        existing_attempted = int(
            state.get("attempted_work_units", state.get("completed_work_units", 0))
        )
        existing_successful = int(state.get("successful_work_units", 0))
        existing_failed = int(state.get("failed_work_units", 0))
        attempted = max(existing_attempted, terminal)
        successful = max(existing_successful, validated)
        failed = max(
            existing_failed,
            checkpoint_failed,
            attempted - successful,
        )
        attempted = max(attempted, successful + failed)
        recovered = dict(state)
        recovered.update(
            {
                "status": "interrupted",
                "completed_work_units": attempted,
                "attempted_work_units": attempted,
                "successful_work_units": successful,
                "failed_work_units": failed,
                "validated_work_units": validated,
                "pending_work_units": max(total - attempted, 0),
                "recovery_source": recovery_source,
                "recovery_failures": failures,
                "recovered_unix_seconds": time.time(),
                "updated_unix_seconds": time.time(),
                "last_error": "Run state recovered explicitly; resume validation is required.",
            }
        )
        with _state_update_lock(primary):
            _atomic_write_json(primary, recovered, preserve_previous=False)
        return recovered


def describe_run_state(output_dir: Path) -> str:
    """Return progress with attempted, successful, failed, pending, and validated counts."""

    state = load_run_state(output_dir)
    if state is None:
        return "No saved long-run state was found in this folder."
    validated = compatible_checkpoint_count(Path(output_dir), state)
    total = int(state.get("total_work_units", 0))
    attempted = int(
        state.get("attempted_work_units", state.get("completed_work_units", 0))
    )
    successful = int(state.get("successful_work_units", validated))
    failed = int(state.get("failed_work_units", max(attempted - successful, 0)))
    pending = int(state.get("pending_work_units", max(total - attempted, 0)))
    unit = str(state.get("work_unit_name", "work units"))
    return (
        f"{state.get('run_kind', 'long run')} | status={state.get('status', 'unknown')} | "
        f"attempted={attempted:,}/{total:,}, successful={successful:,}, failed={failed:,}, "
        f"pending={pending:,} | validated {validated:,}/{total:,} {unit} | "
        f"seed={state.get('seed_used')}"
    )
