"""Regressions for v2.29.15 Monte Carlo and long-run integrity fixes."""

from __future__ import annotations

import json
import multiprocessing as mp
import zipfile
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from climate_model import ModelConfig, ProcessClimateModel
from monte_carlo import (
    _joint_prior_state_is_physical,
    assess_ensemble_quality,
    validate_ensemble_survival,
)
from run_state import (
    RUN_STATE_BACKUP_FILENAME,
    OutputDirectoryLockedError,
    describe_run_state,
    initialize_run_state,
    load_run_state,
    output_directory_run_lock,
    recover_run_state,
    update_run_state,
)
from safe_checkpoint import CheckpointFormatError, read_checkpoint, write_checkpoint
from worker_supervision import save_compatible_checkpoint


def _concurrent_state_update(path: str, start: mp.synchronize.Event, key: str) -> None:
    start.wait(10.0)
    update_run_state(Path(path), **{key: key})


def _state_template(output: Path, fingerprint: str = "fingerprint") -> dict[str, object]:
    return {
        "format": "emergent-climate-model-long-run-state",
        "state_version": 3,
        "run_kind": "co2_target_sweep",
        "model_version": "2.29.15",
        "status": "interrupted",
        "fingerprint": fingerprint,
        "seed_requested": 0,
        "seed_used": 123,
        "seed_source": "system_clock",
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
        "settings": {"command_arguments": ["--output", str(output)]},
        "created_unix_seconds": 1.0,
        "updated_unix_seconds": 1.0,
        "completed_unix_seconds": None,
        "resume_count": 0,
        "last_error": None,
    }


def test_joint_prior_screen_uses_sampled_density_normalization() -> None:
    base = ModelConfig(
        auto_initialize_from_1850=False,
        duration_years=0.1,
        amoc_density_eos="linear",
    )
    sampled = {"amoc_reference_density_driver": 0.00100544496}
    sampled_config = replace(base, **sampled)

    with pytest.raises(ValueError, match="initial density margin"):
        ProcessClimateModel(sampled_config)
    assert _joint_prior_state_is_physical(sampled, base) is False


def test_one_survivor_and_excess_failures_are_rejected() -> None:
    with pytest.raises(RuntimeError, match="only 1 successful"):
        validate_ensemble_survival(2, 1, 1)
    with pytest.raises(RuntimeError, match="failed-member fraction"):
        validate_ensemble_survival(10, 7, 3)


def test_small_surviving_ensemble_is_explicitly_exploratory() -> None:
    quality = assess_ensemble_quality(
        requested_members=2,
        successful_members=2,
        failed_members=0,
        effective_sample_size=2.0,
        posterior_weighting_enabled=False,
    )
    assert quality["survival_gate_passed"] is True
    assert quality["uncertainty_products_valid_for_quantitative_use"] is False
    assert quality["quality_classification"].startswith("exploratory_only")


def test_concurrent_state_updates_preserve_both_writers(tmp_path: Path) -> None:
    path = initialize_run_state(
        tmp_path,
        run_kind="monte_carlo",
        model_version="2.29.15",
        fingerprint="fingerprint",
        seed_requested=1,
        seed_used=1,
        seed_source="user",
        checkpoint_directory="checkpoints",
        total_work_units=2,
        work_unit_name="members",
        resume=False,
        settings={},
    )
    context = mp.get_context("spawn")
    start = context.Event()
    first = context.Process(
        target=_concurrent_state_update, args=(str(path), start, "writer_one")
    )
    second = context.Process(
        target=_concurrent_state_update, args=(str(path), start, "writer_two")
    )
    first.start()
    second.start()
    start.set()
    first.join(20.0)
    second.join(20.0)
    assert first.exitcode == 0
    assert second.exitcode == 0
    state = load_run_state(tmp_path)
    assert state is not None
    assert state["writer_one"] == "writer_one"
    assert state["writer_two"] == "writer_two"


def test_output_directory_lock_rejects_second_live_owner(tmp_path: Path) -> None:
    with output_directory_run_lock(tmp_path / "output", run_kind="monte_carlo"):
        with pytest.raises(OutputDirectoryLockedError, match="already locked"):
            with output_directory_run_lock(tmp_path / "output", run_kind="monte_carlo"):
                pass


def test_corrupt_backup_falls_back_to_checkpoint_metadata(tmp_path: Path) -> None:
    template = _state_template(tmp_path)
    checkpoint = tmp_path / "targets" / "member_00000000" / "target_00000000.ckpt"
    save_compatible_checkpoint(
        checkpoint,
        "fingerprint",
        {"status": "ok", "target_summary": {"target_ppm": 300.0}},
        {"state_template": template},
    )
    (tmp_path / RUN_STATE_BACKUP_FILENAME).write_text("{corrupt", encoding="utf-8")

    recovered = recover_run_state(tmp_path)
    assert recovered["recovery_source"] == "checkpoint_metadata"
    assert recovered["validated_work_units"] == 1
    assert any("backup:" in item for item in recovered["recovery_failures"])


def test_state_description_separates_attempted_success_failed_and_validated(
    tmp_path: Path,
) -> None:
    path = initialize_run_state(
        tmp_path,
        run_kind="co2_target_sweep",
        model_version="2.29.15",
        fingerprint="fingerprint",
        seed_requested=1,
        seed_used=1,
        seed_source="user",
        checkpoint_directory="targets",
        total_work_units=6,
        work_unit_name="target simulations",
        resume=False,
        settings={},
    )
    update_run_state(
        path,
        status="completed_with_failures",
        attempted_work_units=6,
        successful_work_units=3,
        failed_work_units=3,
        validated_work_units=3,
        pending_work_units=0,
    )
    description = describe_run_state(tmp_path)
    assert "status=completed_with_failures" in description
    assert "attempted=6/6" in description
    assert "successful=3" in description
    assert "failed=3" in description
    assert "validated 0/6" in description  # no actual compatible checkpoint files


def test_lzma_compressed_checkpoint_is_rejected(tmp_path: Path) -> None:
    original = tmp_path / "original.ckpt"
    altered = tmp_path / "lzma.ckpt"
    write_checkpoint(original, {"array": np.arange(4, dtype=np.float32)})
    with zipfile.ZipFile(original, "r") as source, zipfile.ZipFile(
        altered, "w", compression=zipfile.ZIP_LZMA
    ) as destination:
        for info in source.infolist():
            destination.writestr(info.filename, source.read(info.filename))
    with pytest.raises(CheckpointFormatError, match="Unsupported ZIP compression"):
        read_checkpoint(altered)


def test_npy_member_with_trailing_bytes_is_rejected(tmp_path: Path) -> None:
    original = tmp_path / "original.ckpt"
    altered = tmp_path / "trailing.ckpt"
    write_checkpoint(original, {"array": np.arange(4, dtype=np.float32)})
    with zipfile.ZipFile(original, "r") as source, zipfile.ZipFile(
        altered, "w", compression=zipfile.ZIP_DEFLATED
    ) as destination:
        for info in source.infolist():
            payload = source.read(info.filename)
            if info.filename.endswith(".npy"):
                payload += b"undeclared-trailing-bytes"
            destination.writestr(info.filename, payload)
    with pytest.raises(CheckpointFormatError, match="trailing or truncated"):
        read_checkpoint(altered)
