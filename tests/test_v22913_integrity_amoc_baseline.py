"""Regressions for v2.29.15 lock, recovery, and AMOC-anchor fixes."""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import socket
import time
from pathlib import Path

import pytest

from climate_model import ModelConfig, ProcessClimateModel
from monte_carlo import (
    FIXED_SCIENCE_PRIOR_PARAMETERS,
    parse_ranges,
    science_default_ranges,
)
from run_state import (
    RUN_STATE_BACKUP_FILENAME,
    OutputDirectoryLockedError,
    output_directory_run_lock,
    output_run_lock_path,
    recover_run_state,
)
from worker_supervision import save_compatible_checkpoint


def _state_template(output: Path, fingerprint: str) -> dict[str, object]:
    return {
        "format": "emergent-climate-model-long-run-state",
        "state_version": 3,
        "run_kind": "co2_target_sweep",
        "model_version": "2.29.15",
        "status": "interrupted",
        "fingerprint": fingerprint,
        "seed_requested": 1,
        "seed_used": 1,
        "seed_source": "user",
        "checkpoint_directory": "targets",
        "total_work_units": 6,
        "completed_work_units": 0,
        "attempted_work_units": 0,
        "successful_work_units": 0,
        "failed_work_units": 0,
        "validated_work_units": 0,
        "pending_work_units": 6,
        "resumed_work_units": 0,
        "work_unit_name": "target simulations",
        "settings": {"output": str(output)},
        "created_unix_seconds": 1.0,
        "updated_unix_seconds": 1.0,
        "completed_unix_seconds": None,
        "resume_count": 0,
        "last_error": None,
    }


def _stale_lock_contender(
    output: str,
    start: mp.synchronize.Event,
    release: mp.synchronize.Event,
    queue: mp.Queue,
) -> None:
    start.wait(10.0)
    try:
        with output_directory_run_lock(Path(output), run_kind="monte_carlo"):
            queue.put("acquired")
            release.wait(10.0)
    except OutputDirectoryLockedError:
        queue.put("locked")
    except BaseException as exc:  # pragma: no cover - diagnostic path
        queue.put(f"error:{type(exc).__name__}:{exc}")


def test_simultaneous_stale_lock_reclamation_has_one_owner(tmp_path: Path) -> None:
    output = tmp_path / "output"
    lock_path = output_run_lock_path(output)
    lock_path.write_text(
        json.dumps(
            {
                "format": "emergent-climate-model-exclusive-lock",
                "version": 1,
                "token": "stale-token",
                "pid": 999_999_999,
                "hostname": socket.gethostname(),
                "process_start_marker": None,
                "acquired_unix_seconds": time.time(),
                "purpose": "long-run:monte_carlo",
                "output_directory": str(output.resolve()),
            }
        ),
        encoding="utf-8",
    )

    context = mp.get_context("spawn")
    start = context.Event()
    release = context.Event()
    queue = context.Queue()
    processes = [
        context.Process(
            target=_stale_lock_contender,
            args=(str(output), start, release, queue),
        )
        for _ in range(2)
    ]
    for process in processes:
        process.start()
    start.set()

    messages = [queue.get(timeout=20.0), queue.get(timeout=20.0)]
    release.set()
    for process in processes:
        process.join(20.0)
        assert process.exitcode == 0
    assert sorted(messages) == ["acquired", "locked"]
    assert not lock_path.exists()


def test_incompatible_backup_falls_through_to_checkpoint_metadata(
    tmp_path: Path,
) -> None:
    old = _state_template(tmp_path, "old-fingerprint")
    current = _state_template(tmp_path, "current-fingerprint")
    (tmp_path / RUN_STATE_BACKUP_FILENAME).write_text(
        json.dumps(old), encoding="utf-8"
    )
    save_compatible_checkpoint(
        tmp_path / "targets" / "member_00000000" / "target_00000000.ckpt",
        "current-fingerprint",
        {"status": "ok"},
        {"state_template": current},
    )

    recovered = recover_run_state(tmp_path)
    assert recovered["recovery_source"] == "checkpoint_metadata"
    assert recovered["fingerprint"] == "current-fingerprint"
    assert any("semantically incompatible" in item for item in recovered["recovery_failures"])


def test_checkpoint_recovery_counts_terminal_failures(tmp_path: Path) -> None:
    template = _state_template(tmp_path, "fingerprint")
    metadata = {"state_template": template}
    save_compatible_checkpoint(
        tmp_path / "targets" / "member_00000000" / "target_00000000.ckpt",
        "fingerprint",
        {"status": "ok"},
        metadata,
    )
    save_compatible_checkpoint(
        tmp_path / "targets" / "member_00000000" / "target_00000001.ckpt",
        "fingerprint",
        {"status": "failed", "error": "forced"},
        metadata,
    )
    (tmp_path / RUN_STATE_BACKUP_FILENAME).write_text("{corrupt", encoding="utf-8")

    recovered = recover_run_state(tmp_path)
    assert recovered["attempted_work_units"] == 2
    assert recovered["successful_work_units"] == 1
    assert recovered["failed_work_units"] == 1
    assert recovered["validated_work_units"] == 1
    assert recovered["pending_work_units"] == 4


def test_builtin_science_prior_keeps_configured_amoc_anchor() -> None:
    base = ModelConfig(
        amoc_reference_sv=17.0,
        auto_initialize_from_1850=False,
        duration_years=0.1,
    )
    ranges = science_default_ranges("none")
    assert "amoc_reference_sv" in FIXED_SCIENCE_PRIOR_PARAMETERS
    assert "amoc_reference_sv" not in ranges
    parsed = parse_ranges(None, base, "none", use_science_priors=True)
    assert "amoc_reference_sv" not in parsed

    model = ProcessClimateModel(base)
    result = model.run().dataframe
    assert float(result.iloc[0]["amoc_sv"]) == pytest.approx(17.0, abs=1.0e-12)


def test_custom_amoc_reference_range_remains_available() -> None:
    base = ModelConfig()
    ranges = parse_ranges(
        [["amoc_reference_sv", "14", "19"]],
        base,
        "none",
        use_science_priors=False,
    )
    assert ranges == {"amoc_reference_sv": (14.0, 19.0)}
