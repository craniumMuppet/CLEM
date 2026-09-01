"""Operational safety regressions for the v2.29.3 maintenance release."""

from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
import pytest

from climate_model import (
    MODEL_VERSION,
    ModelConfig,
    ProcessClimateModel,
    build_parser,
    config_from_args,
    prepare_output_directory,
)
from climate_model_gui import MODEL_DEFAULT_CONFIG, terminate_process_tree
from worker_supervision import run_supervised_tasks, stable_fingerprint


def _square_worker(payload: tuple[int, int]) -> dict[str, object]:
    member, value = payload
    return {"member": member, "status": "completed", "value": value * value}


def _slow_worker(payload: tuple[int, float]) -> dict[str, object]:
    member, seconds = payload
    time.sleep(seconds)
    return {"member": member, "status": "completed"}


def test_version_and_meinshausen_defaults_are_synchronized() -> None:
    assert MODEL_VERSION == "2.29.29"
    assert ModelConfig().co2_forcing_formula == "meinshausen2020"
    assert MODEL_DEFAULT_CONFIG.co2_forcing_formula == "meinshausen2020"
    parsed = config_from_args(build_parser().parse_args([]))
    assert parsed.co2_forcing_formula == "meinshausen2020"
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    assert 'version = "2.29.29"' in pyproject.read_text(encoding="utf-8")


def test_existing_output_is_preserved_without_explicit_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "results"
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("preserve", encoding="utf-8")
    with pytest.raises(FileExistsError):
        prepare_output_directory(output, prompt=False)
    assert sentinel.read_text(encoding="utf-8") == "preserve"

    prepared = prepare_output_directory(output, overwrite=True, prompt=False)
    assert prepared == output
    assert output.is_dir()
    assert not sentinel.exists()


def test_resume_preserves_existing_output(tmp_path: Path) -> None:
    output = tmp_path / "resume"
    output.mkdir()
    sentinel = output / "member.pkl"
    sentinel.write_bytes(b"checkpoint")
    assert prepare_output_directory(output, resume=True, prompt=False) == output
    assert sentinel.read_bytes() == b"checkpoint"


def test_source_working_and_ancestor_paths_are_protected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    with pytest.raises(ValueError, match="protected output path"):
        prepare_output_directory(work, overwrite=True, prompt=False)
    with pytest.raises(ValueError, match="protected output path"):
        prepare_output_directory(tmp_path, overwrite=True, prompt=False)
    source_root = Path(__file__).resolve().parents[1]
    with pytest.raises(ValueError, match="protected output path"):
        prepare_output_directory(source_root, overwrite=True, prompt=False)


def test_supervisor_checkpoints_resumes_and_cleans_stale_files(tmp_path: Path) -> None:
    checkpoints = tmp_path / "checkpoints"
    running = checkpoints / ".running"
    running.mkdir(parents=True)
    stale = running / "abandoned.pkl"
    stale.write_bytes(b"stale")
    tasks = [(0, (0, 2)), (1, (1, 3))]
    fingerprint = stable_fingerprint({"release": "2.29.3", "case": "square"})
    first = run_supervised_tasks(
        tasks,
        _square_worker,
        max_workers=2,
        timeout_seconds=10.0,
        heartbeat_seconds=60.0,
        checkpoint_dir=checkpoints,
        fingerprint=fingerprint,
        resume=False,
        label="test members",
    )
    assert [entry["value"] for entry in first] == [4, 9]
    assert not stale.exists()
    assert (checkpoints / "member_00000000.ckpt").exists()

    progress: list[tuple[int, int, int, float]] = []
    second = run_supervised_tasks(
        tasks,
        _square_worker,
        max_workers=2,
        timeout_seconds=10.0,
        heartbeat_seconds=60.0,
        checkpoint_dir=checkpoints,
        fingerprint=fingerprint,
        resume=True,
        label="test members",
        progress_callback=lambda *values: progress.append(values),
    )
    assert second == first
    assert progress and progress[-1][:3] == (2, 2, 2)


def test_supervisor_times_out_and_checkpoints_failure(tmp_path: Path) -> None:
    checkpoints = tmp_path / "timeout-checkpoints"
    result = run_supervised_tasks(
        [(7, (7, 2.0))],
        _slow_worker,
        max_workers=1,
        timeout_seconds=0.2,
        heartbeat_seconds=60.0,
        checkpoint_dir=checkpoints,
        fingerprint=stable_fingerprint({"case": "timeout"}),
        resume=False,
        label="timeout member",
    )[0]
    assert result["member"] == 7
    assert result["status"] == "failed"
    assert "TimeoutError" in str(result["error"])
    assert (checkpoints / "member_00000007.ckpt").exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX process-group assertion")
def test_process_group_termination_stops_parent_and_children() -> None:
    code = (
        "import subprocess,sys,time; "
        "subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
        "time.sleep(60)"
    )
    process = subprocess.Popen(
        [sys.executable, "-c", code],
        text=True,
        start_new_session=True,
    )
    time.sleep(0.25)
    success, _details = terminate_process_tree(process, graceful_timeout_seconds=2.0)
    assert success
    assert process.poll() is not None
    with pytest.raises(ProcessLookupError):
        os.killpg(process.pid, 0)


def test_gui_contains_launch_close_race_guards() -> None:
    source = (Path(__file__).resolve().parents[1] / "climate_model_gui.py").read_text(
        encoding="utf-8"
    )
    assert "self.launch_in_progress = False" in source
    assert "self.process is not None or self.launch_in_progress" in source
    assert "process is None and not self.launch_in_progress" in source
    assert 'self.output_queue.put(("started", process.pid))' in source
    assert "if self.stop_requested:" in source
    assert "start_new_session" in source
    assert "CREATE_NEW_PROCESS_GROUP" in source


def test_unforced_continuous_control_is_exact_across_lead_transitions() -> None:
    config = ModelConfig(
        scenario="constant",
        duration_years=20.0,
        dt_years=0.1,
        record_every_years=1.0,
        warming_freshwater_sv_per_k=0.0,
    )
    frame = ProcessClimateModel(config).run().dataframe
    assert float(np.max(np.abs(frame["global_surface_warming_c"]))) < 1.0e-12
    assert float(np.max(np.abs(frame["amoc_sv"] - config.amoc_reference_sv))) < 1.0e-12
    assert float(np.max(np.abs(frame["pre_projection_salt_conservation_error_ppm"]))) < 1.0e-12


def test_continuous_control_balance_preserves_real_perturbations() -> None:
    config = ModelConfig(
        scenario="constant",
        duration_years=1.0,
        dt_years=0.1,
        record_every_years=0.1,
        warming_freshwater_sv_per_k=0.0,
    )
    model = ProcessClimateModel(config)
    model.state.land_anomaly_c[:] = 1.0e-4
    model.step(0.0, dt_years=0.1)
    assert float(np.max(np.abs(model.state.land_anomaly_c))) > 1.0e-6
    assert abs(model._global_surface_mean(model.state)) > 1.0e-7
