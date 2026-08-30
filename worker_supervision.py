#!/usr/bin/env python3
"""Spawn-based worker supervision with heartbeats, timeouts, and checkpoints.

Each ensemble member runs in its own spawned process.  This is intentionally
more conservative than a long-lived process pool: a timed-out member can be
terminated without discarding completed work or poisoning unrelated workers.
"""

from __future__ import annotations

import hashlib
import json
import multiprocessing as mp
import os
import time
import traceback
import uuid
from collections import deque
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from safe_checkpoint import CheckpointFormatError, read_checkpoint, write_checkpoint

Worker = Callable[[Any], Any]
ProgressCallback = Callable[[int, int, int, float], None]


def stable_fingerprint(payload: Any) -> str:
    """Return a stable SHA-256 fingerprint for JSON-compatible run metadata."""

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=lambda value: str(value),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _spawn_worker_entry(worker: Worker, payload: Any, result_path: str) -> None:
    """Run one worker and persist its result before the child exits."""

    destination = Path(result_path)
    try:
        result = worker(payload)
    except BaseException as exc:  # pragma: no cover - worker functions normally catch
        member = payload[0] if isinstance(payload, tuple) and payload else -1
        result = {
            "member": int(member),
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(limit=20),
        }
    write_checkpoint(destination, result)


def _checkpoint_path(checkpoint_dir: Path, task_id: int) -> Path:
    return checkpoint_dir / f"member_{int(task_id):08d}.ckpt"


def _load_checkpoint(path: Path, fingerprint: str) -> Any | None:
    try:
        record = read_checkpoint(path)
    except (OSError, CheckpointFormatError, TypeError, ValueError):
        return None
    if not isinstance(record, dict) or record.get("fingerprint") != fingerprint:
        return None
    return record.get("result")


def _save_checkpoint(
    path: Path,
    fingerprint: str,
    result: Any,
    metadata: dict[str, Any] | None = None,
) -> None:
    write_checkpoint(
        path,
        {
            "fingerprint": fingerprint,
            "written_unix_seconds": time.time(),
            "result": result,
            "run_metadata": metadata,
        },
    )


def result_is_failed(result: Any) -> bool:
    """Return whether a saved worker result represents a retriable failure."""

    return (
        isinstance(result, dict)
        and str(result.get("status", "")).lower()
        in {"failed", "error", "timeout", "interrupted"}
    )


def load_compatible_checkpoint(path: Path, fingerprint: str) -> Any | None:
    """Load one atomic checkpoint only when its run fingerprint matches."""

    return _load_checkpoint(Path(path), fingerprint)


def save_compatible_checkpoint(
    path: Path,
    fingerprint: str,
    result: Any,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Persist one atomic fingerprinted checkpoint for nested long-run work."""

    _save_checkpoint(Path(path), fingerprint, result, metadata)


def _timeout_result(task_id: int, timeout_seconds: float) -> dict[str, Any]:
    return {
        "member": int(task_id),
        "status": "failed",
        "error": (
            "TimeoutError: ensemble member exceeded "
            f"{float(timeout_seconds):g} seconds"
        ),
        "traceback": "",
    }


def run_supervised_tasks(
    tasks: Sequence[tuple[int, Any]],
    worker: Worker,
    *,
    max_workers: int,
    timeout_seconds: float,
    heartbeat_seconds: float,
    checkpoint_dir: Path,
    fingerprint: str,
    resume: bool,
    retry_failed_on_resume: bool = False,
    label: str = "members",
    progress_callback: ProgressCallback | None = None,
    checkpoint_metadata: dict[str, Any] | None = None,
) -> list[Any]:
    """Execute tasks with spawn isolation, timeout termination, and resume.

    Checkpoints are accepted only when their run fingerprint matches exactly.
    Completed members are restored when their fingerprint matches. Callers may
    request that failed or timed-out checkpoints be retried, allowing transient
    failures to recover without repeating successful work.
    """

    if max_workers < 1:
        raise ValueError("max_workers must be at least one")
    if timeout_seconds <= 0.0:
        raise ValueError("timeout_seconds must be positive")
    if heartbeat_seconds <= 0.0:
        raise ValueError("heartbeat_seconds must be positive")

    checkpoint_dir = Path(checkpoint_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    running_dir = checkpoint_dir / ".running"
    running_dir.mkdir(parents=True, exist_ok=True)
    # A killed parent can leave atomic worker payloads behind. They are never
    # valid checkpoints and must not accumulate or be mistaken for results.
    for stale in running_dir.iterdir():
        if stale.is_file() or stale.is_symlink():
            stale.unlink(missing_ok=True)

    ordered_ids = [int(task_id) for task_id, _payload in tasks]
    if len(set(ordered_ids)) != len(ordered_ids):
        raise ValueError("Supervised task IDs must be unique")

    results: dict[int, Any] = {}
    resumed_count = 0
    pending: deque[tuple[int, Any]] = deque()
    for task_id, payload in tasks:
        checkpoint = _checkpoint_path(checkpoint_dir, int(task_id))
        restored = _load_checkpoint(checkpoint, fingerprint) if resume else None
        restored_failed = result_is_failed(restored)
        if restored is not None and not (retry_failed_on_resume and restored_failed):
            results[int(task_id)] = restored
            resumed_count += 1
        else:
            pending.append((int(task_id), payload))

    total = len(tasks)
    started = time.perf_counter()

    def notify() -> None:
        if progress_callback is not None:
            progress_callback(
                len(results), total, resumed_count, time.perf_counter() - started
            )

    if resumed_count:
        print(
            f"Resumed {resumed_count:,}/{total:,} {label} from compatible checkpoints.",
            flush=True,
        )
        notify()

    context = mp.get_context("spawn")
    active: dict[int, dict[str, Any]] = {}
    last_heartbeat = time.perf_counter()

    def start_available() -> None:
        while pending and len(active) < max_workers:
            task_id, payload = pending.popleft()
            result_path = running_dir / (
                f"member_{task_id:08d}_{uuid.uuid4().hex}.ckpt"
            )
            process = context.Process(
                target=_spawn_worker_entry,
                args=(worker, payload, str(result_path)),
                name=f"climate-{label}-{task_id}",
            )
            process.daemon = False
            process.start()
            active[task_id] = {
                "process": process,
                "payload": payload,
                "result_path": result_path,
                "start": time.perf_counter(),
            }

    try:
        start_available()
        while active or pending:
            now = time.perf_counter()
            changed = False
            for task_id, state in list(active.items()):
                process = state["process"]
                elapsed = now - float(state["start"])
                if process.is_alive() and elapsed <= timeout_seconds:
                    continue

                if process.is_alive():
                    process.terminate()
                    process.join(timeout=5.0)
                    if process.is_alive():
                        process.kill()
                        process.join(timeout=5.0)
                    result = _timeout_result(task_id, timeout_seconds)
                else:
                    process.join(timeout=1.0)
                    result_path = Path(state["result_path"])
                    try:
                        result = read_checkpoint(result_path)
                    except Exception as exc:
                        result = {
                            "member": int(task_id),
                            "status": "failed",
                            "error": (
                                "WorkerProcessError: member exited without a readable "
                                f"result (exit code {process.exitcode}): {exc}"
                            ),
                            "traceback": "",
                        }

                Path(state["result_path"]).unlink(missing_ok=True)
                _save_checkpoint(
                    _checkpoint_path(checkpoint_dir, task_id),
                    fingerprint,
                    result,
                    checkpoint_metadata,
                )
                results[task_id] = result
                del active[task_id]
                changed = True
                notify()

            if changed:
                start_available()

            now = time.perf_counter()
            if now - last_heartbeat >= heartbeat_seconds:
                completed = len(results)
                elapsed = max(now - started, 1.0e-9)
                print(
                    f"Heartbeat: {completed:,}/{total:,} {label} complete; "
                    f"{len(active)} active; {len(pending)} queued; "
                    f"elapsed {elapsed / 60.0:.1f} min.",
                    flush=True,
                )
                last_heartbeat = now
            time.sleep(0.05)
    except BaseException:
        for state in active.values():
            process = state["process"]
            if process.is_alive():
                process.terminate()
            process.join(timeout=2.0)
            if process.is_alive():
                process.kill()
                process.join(timeout=2.0)
            Path(state["result_path"]).unlink(missing_ok=True)
        raise
    finally:
        try:
            running_dir.rmdir()
        except OSError:
            pass

    return [results[task_id] for task_id in ordered_ids]
