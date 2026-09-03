"""Focused regressions for v2.29.11 target, baseline, and resume safety."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import numpy as np
import pytest

import co2_target_sweep as sweep
import safe_checkpoint
from climate_model import MODEL_VERSION, ModelConfig
from run_state import (
    RUN_STATE_BACKUP_FILENAME,
    RUN_STATE_FILENAME,
    RUN_STATE_VERSION,
    initialize_run_state,
    load_run_state,
    recover_run_state,
    saved_seed_for_resume,
    update_run_state,
)
from runtime_provenance import runtime_provenance
from safe_checkpoint import CheckpointFormatError, read_checkpoint, write_checkpoint
from worker_supervision import save_compatible_checkpoint


def _state_template(output: Path, fingerprint: str = "fingerprint") -> dict[str, object]:
    return {
        "format": "emergent-climate-model-long-run-state",
        "state_version": RUN_STATE_VERSION,
        "run_kind": "co2_target_sweep",
        "model_version": MODEL_VERSION,
        "status": "interrupted",
        "fingerprint": fingerprint,
        "seed_requested": 0,
        "seed_used": 123,
        "seed_source": "system_clock",
        "checkpoint_directory": "targets",
        "total_work_units": 1,
        "completed_work_units": 0,
        "resumed_work_units": 0,
        "work_unit_name": "target simulations",
        "settings": {"command_arguments": ["--output", str(output)]},
        "created_unix_seconds": 1.0,
        "updated_unix_seconds": 1.0,
        "completed_unix_seconds": None,
        "resume_count": 0,
        "last_error": None,
    }


def test_version_and_descending_target_semantics() -> None:
    assert MODEL_VERSION == "2.29.29"
    targets = sweep.resolve_targets(
        "specific", 278.3, 50.0, 1200.0, "200,300,600,1200"
    )
    np.testing.assert_allclose(targets, [200.0, 300.0, 600.0, 1200.0])
    config = ModelConfig(
        scenario="linear_ramp_hold",
        co2_start_ppm=278.3,
        co2_end_ppm=200.0,
        co2_ramp_years=10.0,
        co2_hold_years=10.0,
        duration_years=20.0,
    )
    config.validate()
    assert config.co2_start_ppm == pytest.approx(278.3)


def test_common_amoc_baseline_is_supplied_not_inferred_from_forced_records() -> None:
    amoc = np.asarray([18.0, 17.0, 16.0])
    decline, baseline = sweep._amoc_decline_percent(amoc, 20.0)
    assert baseline == pytest.approx(20.0)
    np.testing.assert_allclose(decline, [10.0, 15.0, 20.0])
    assert sweep.AMOC_BASELINE_DEFINITION == "common_member_pre_forcing_t0"


def _healthy_common_start_diagnostics(**updates: float) -> dict[str, float]:
    values = {
        "common_start_ppm": 300.0,
        "global_surface_warming_c": 0.25,
        "annual_mean_toa_imbalance_wm2": 0.05,
        "annual_mean_prescribed_forcing_wm2": 0.45,
        "annual_gmst_drift_c": 0.001,
        "annual_amoc_drift_sv": 0.01,
        "initial_amoc_sv": 17.0,
        "maximum_absolute_local_temperature_anomaly_c": 2.0,
    }
    values.update(updates)
    return values


def test_common_start_gate_accepts_stable_active_control() -> None:
    limits = sweep.validate_common_start_baseline(
        _healthy_common_start_diagnostics(), ModelConfig()
    )
    assert limits["maximum_equivalent_global_warming_c"] > 1.0
    assert limits["maximum_local_temperature_anomaly_c"] == pytest.approx(40.0)


def test_common_start_replacement_draws_are_deterministic_and_explicit() -> None:
    seeds = [
        sweep._common_start_redraw_seed(19930929, attempt)
        for attempt in range(1, 4)
    ]
    assert seeds == [
        sweep._common_start_redraw_seed(19930929, attempt)
        for attempt in range(1, 4)
    ]
    assert len(set(seeds)) == 3
    assert all(0 <= seed < 2**32 for seed in seeds)
    with pytest.raises(ValueError, match="numbered from one"):
        sweep._common_start_redraw_seed(19930929, 0)

    rejected = {
        "status": "failed",
        "failure_kind": "common_start_baseline_rejected",
    }
    assert sweep._is_common_start_rejection(rejected)
    assert not sweep._is_common_start_rejection(
        {"status": "failed", "error": "unrelated worker failure"}
    )
    assert not sweep._is_common_start_rejection(
        {**rejected, "status": "ok"}
    )


def test_common_start_redraw_parser_default_and_validation(tmp_path: Path) -> None:
    parsed = sweep.build_parser().parse_args([])
    assert (
        parsed.sweep_baseline_redraw_attempts
        == sweep.DEFAULT_COMMON_START_REDRAW_ATTEMPTS
    )

    invalid = sweep.build_parser().parse_args(
        [
            "--monte-carlo-runs",
            "2",
            "--mc-range",
            "hydrological_freshwater_sv_per_k",
            "0.004",
            "0.006",
            "--sweep-baseline-redraw-attempts",
            "101",
            "--output",
            str(tmp_path),
            "--overwrite-output",
        ]
    )
    with pytest.raises(ValueError, match="between 0 and 100"):
        sweep.run_sweep(invalid)


def test_worker_tags_common_start_gate_failure_for_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeState:
        def __init__(self) -> None:
            self.land_anomaly_c = np.zeros(1)
            self.atlantic_ocean_anomaly_c = np.zeros(1)
            self.non_atlantic_ocean_anomaly_c = np.zeros(1)
            self.amoc_sv = 17.0

        def copy(self) -> "FakeState":
            return self

    class FakeModel:
        def __init__(self, config: ModelConfig) -> None:
            self.config = config
            self.state = FakeState()

        def run(self) -> None:
            raise AssertionError("native reference baseline must not spin up")

    def reject_baseline(*_args: object, **_kwargs: object) -> dict[str, float]:
        raise ValueError("synthetic baseline rejection")

    monkeypatch.setattr(sweep, "ProcessClimateModel", FakeModel)
    monkeypatch.setattr(sweep, "validate_common_start_baseline", reject_baseline)
    base = ModelConfig(
        scenario="linear_ramp_hold",
        co2_start_ppm=278.3,
        co2_end_ppm=300.0,
        co2_ramp_years=1.0,
        co2_hold_years=1.0,
        duration_years=2.0,
        auto_initialize_from_1850=False,
    )
    payload = (
        0,
        base.__dict__.copy(),
        {},
        278.3,
        [300.0],
        1.0,
        1.0,
        1.0,
        0.95,
        0.0,
        0.0,
        "none",
        False,
        False,
        20.0,
        str(tmp_path / "targets"),
        "fingerprint",
        False,
        False,
        None,
    )
    result = sweep._sweep_member_worker(payload)
    assert result["status"] == "failed"
    assert result["failure_kind"] == "common_start_baseline_rejected"
    assert "synthetic baseline rejection" in result["baseline_rejection_reason"]
    assert sweep._is_common_start_rejection(result)


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"initial_amoc_sv": 3.69}, "already weak/collapsed"),
        ({"annual_mean_toa_imbalance_wm2": 0.5}, "energy-balance gate"),
        ({"global_surface_warming_c": -0.8}, "wrong sign"),
        ({"global_surface_warming_c": 9.09}, "global warming"),
        (
            {"maximum_absolute_local_temperature_anomaly_c": 72.7},
            "local temperature",
        ),
        ({"annual_gmst_drift_c": 0.2}, "annual GMST change"),
        ({"annual_amoc_drift_sv": -1.0}, "annual AMOC change"),
    ],
)
def test_common_start_gate_rejects_contaminated_baselines(
    updates: dict[str, float], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        sweep.validate_common_start_baseline(
            _healthy_common_start_diagnostics(**updates), ModelConfig()
        )


def test_resume_fails_closed_without_primary_state(tmp_path: Path) -> None:
    (tmp_path / "stale.txt").write_text("stale", encoding="utf-8")
    with pytest.raises(ValueError, match="no long_run_state.json"):
        saved_seed_for_resume(
            tmp_path,
            run_kind="co2_target_sweep",
            requested_seed=0,
            resume=True,
        )


def test_state_update_preserves_backup_and_explicit_recovery(tmp_path: Path) -> None:
    path = initialize_run_state(
        tmp_path,
        run_kind="co2_target_sweep",
        model_version=MODEL_VERSION,
        fingerprint="fingerprint",
        seed_requested=0,
        seed_used=123,
        seed_source="system_clock",
        checkpoint_directory="targets",
        total_work_units=1,
        work_unit_name="target simulations",
        resume=False,
        settings={},
    )
    update_run_state(path, completed_work_units=1)
    backup = tmp_path / RUN_STATE_BACKUP_FILENAME
    assert backup.exists()
    path.write_text("{broken", encoding="utf-8")
    recovered = recover_run_state(tmp_path)
    assert recovered["recovery_source"] == RUN_STATE_BACKUP_FILENAME
    assert load_run_state(tmp_path) is not None


def test_state_reconstruction_from_checkpoint_metadata(tmp_path: Path) -> None:
    template = _state_template(tmp_path)
    checkpoint = tmp_path / "targets" / "member_00000000" / "target_00000000.ckpt"
    save_compatible_checkpoint(
        checkpoint,
        "fingerprint",
        {"status": "ok", "target_summary": {"target_ppm": 300.0}},
        {"state_template": template},
    )
    recovered = recover_run_state(tmp_path)
    assert recovered["recovery_source"] == "checkpoint_metadata"
    assert recovered["completed_work_units"] == 1
    assert (tmp_path / RUN_STATE_FILENAME).exists()


def test_safe_checkpoint_rejects_undeclared_archive_members(tmp_path: Path) -> None:
    path = tmp_path / "checkpoint.ckpt"
    write_checkpoint(path, {"status": "ok", "array": np.arange(3)})
    altered = tmp_path / "altered.ckpt"
    with zipfile.ZipFile(path, "r") as source, zipfile.ZipFile(altered, "w") as destination:
        for info in source.infolist():
            destination.writestr(info.filename, source.read(info.filename))
        destination.writestr("unexpected.bin", b"x")
    with pytest.raises(CheckpointFormatError, match="member set mismatch"):
        read_checkpoint(altered)


def test_safe_checkpoint_enforces_resource_bound(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "checkpoint.ckpt"
    write_checkpoint(path, {"array": np.arange(16, dtype=np.float64)})
    monkeypatch.setattr(safe_checkpoint, "MAX_TOTAL_UNCOMPRESSED_BYTES", 32)
    with pytest.raises(CheckpointFormatError, match="uncompressed size"):
        read_checkpoint(path)


def test_runtime_provenance_hashes_distributions_and_backend() -> None:
    record = runtime_provenance()
    assert record["version"] >= 2
    distributions = record["environment"]["distributions"]
    for name in ("numpy", "pandas", "scipy", "matplotlib"):
        assert distributions[name]["hashed_file_count"] > 0
        assert len(distributions[name]["installed_content_sha256"]) == 64
    numerical = record["environment"]["numerical_build"]
    assert "numpy_config" in numerical
    assert "scipy_config" in numerical
    assert "numpy_cpu_dispatch" in numerical
