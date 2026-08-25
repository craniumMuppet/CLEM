"""Regressions for v2.29.15 recovery, deterministic records, and sea-ice fixes."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import co2_target_sweep as sweep
from climate_model import ModelConfig, ProcessClimateModel
from run_state import RUN_STATE_BACKUP_FILENAME, recover_run_state
from validate_v22914 import canonical_json_text
from worker_supervision import (
    load_compatible_checkpoint,
    save_compatible_checkpoint,
)


def _sweep_state_template(output: Path, fingerprint: str, total: int) -> dict[str, object]:
    return {
        "format": "emergent-climate-model-long-run-state",
        "state_version": 3,
        "run_kind": "co2_target_sweep",
        "model_version": "2.29.15",
        "status": "interrupted",
        "fingerprint": fingerprint,
        "seed_requested": 7,
        "seed_used": 7,
        "seed_source": "user",
        "checkpoint_directory": "co2_target_sweep_target_checkpoints",
        "total_work_units": total,
        "completed_work_units": 0,
        "attempted_work_units": 0,
        "successful_work_units": 0,
        "failed_work_units": 0,
        "validated_work_units": 0,
        "pending_work_units": total,
        "resumed_work_units": 0,
        "work_unit_name": "target simulations",
        "settings": {"output": str(output)},
        "created_unix_seconds": 1.0,
        "updated_unix_seconds": 1.0,
        "completed_unix_seconds": None,
        "resume_count": 0,
        "last_error": None,
    }


def test_real_target_failure_gets_canonical_nested_checkpoint_and_recovers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "output"
    target_root = output / "co2_target_sweep_target_checkpoints"
    member_root = output / "co2_target_sweep_member_checkpoints"
    fingerprint = "v22914-target-failure"
    targets = [300.0, 600.0, 900.0]
    template = _sweep_state_template(output, fingerprint, len(targets))
    metadata = {"state_template": template}

    base = ModelConfig(
        scenario="linear_ramp_hold",
        co2_start_ppm=278.3,
        co2_end_ppm=300.0,
        co2_ramp_years=1.0,
        co2_hold_years=1.0,
        duration_years=2.0,
        record_every_years=1.0,
        auto_initialize_from_1850=False,
    )
    original_model = sweep.ProcessClimateModel
    template_state = original_model(base).state.copy()

    class FakeRunResult:
        def __init__(self, config: ModelConfig, initial_amoc: float) -> None:
            years = np.array([1850.0, 1851.0, 1852.0])
            self.dataframe = pd.DataFrame(
                {
                    "year": years,
                    "amoc_sv": [initial_amoc, initial_amoc - 0.25, initial_amoc - 0.5],
                    "global_surface_warming_c": [0.0, 0.1, 0.2],
                    "co2_ppm": np.linspace(config.co2_start_ppm, config.co2_end_ppm, 3),
                    "salt_conservation_error_ppm": [0.0, 0.0, 0.0],
                }
            )

        def summary(self) -> dict[str, bool]:
            return {"synthetic": True}

    class FakeModel:
        def __init__(self, config: ModelConfig) -> None:
            self.config = config
            self.state = template_state.copy()

        def run(self) -> FakeRunResult:
            if float(self.config.co2_end_ppm) == 600.0:
                raise RuntimeError("forced production-layout target failure")
            return FakeRunResult(self.config, float(self.state.amoc_sv))

    monkeypatch.setattr(sweep, "ProcessClimateModel", FakeModel)
    payload = (
        0,
        asdict(base),
        {},
        278.3,
        targets,
        1.0,
        1.0,
        1.0,
        0.9,
        0.5,
        0.0,
        "none",
        False,
        False,
        10.0,
        str(target_root),
        fingerprint,
        False,
        True,
        metadata,
    )
    result = sweep._sweep_member_worker(payload)
    assert result["status"] == "partial"
    assert result["attempted_target_simulations"] == 3
    assert result["successful_target_simulations"] == 2
    assert result["failed_target_simulations"] == 1

    first = load_compatible_checkpoint(
        target_root / "member_00000000" / "target_00000000.ckpt",
        fingerprint,
    )
    failed = load_compatible_checkpoint(
        target_root / "member_00000000" / "target_00000001.ckpt",
        fingerprint,
    )
    assert first["status"] == "ok"
    assert failed["status"] == "failed"
    assert "forced production-layout target failure" in failed["error"]

    # Mirror the outer aggregate checkpoint written by run_supervised_tasks.
    save_compatible_checkpoint(
        member_root / "member_00000000.ckpt",
        fingerprint,
        result,
        metadata,
    )
    (output / RUN_STATE_BACKUP_FILENAME).write_text("{corrupt", encoding="utf-8")
    recovered = recover_run_state(output)
    assert recovered["attempted_work_units"] == 3
    assert recovered["successful_work_units"] == 2
    assert recovered["failed_work_units"] == 1
    assert recovered["validated_work_units"] == 2
    assert recovered["pending_work_units"] == 0


def test_canonical_validation_json_is_insertion_order_independent() -> None:
    first = {
        "model_version": "2.29.15",
        "tasks": {"summary_ssp245": {"value": 1}, "control": {"value": 2}},
    }
    second = {
        "tasks": {"control": {"value": 2}, "summary_ssp245": {"value": 1}},
        "model_version": "2.29.15",
    }
    assert canonical_json_text(first).encode("utf-8") == canonical_json_text(second).encode(
        "utf-8"
    )



def _minimal_arctic_model(config: ModelConfig) -> ProcessClimateModel:
    model = ProcessClimateModel.__new__(ProcessClimateModel)
    model.config = config
    # Same latent energy conversion used by the initialized model; only the
    # ratio matters for this volume-conservation unit test.
    model.arctic_latent_energy_per_m_wyr_m2 = 10.0
    return model


def test_winter_lead_closure_conserves_ice_volume_and_never_creates_ice() -> None:
    cfg = ModelConfig(
        arctic_winter_lead_closure_fraction=0.75,
        arctic_winter_lead_closure_temperature_scale_c=15.0,
    )
    model = _minimal_arctic_model(cfg)
    energy = np.array([-10.0, -20.0, 0.0])
    reference = np.array([0.95, 0.98, 0.90])
    weight = np.array([0.75, 0.75, 0.75])
    concentration, equivalent, local = model._arctic_ice_energy_to_state(
        energy,
        reference_ice_fraction=reference,
        lead_closure_weight=weight,
    )
    np.testing.assert_allclose(concentration * local, equivalent, atol=1.0e-14)
    assert concentration[2] == 0.0
    assert local[2] == 0.0


def test_winter_lead_closure_is_cold_season_selective() -> None:
    cfg = ModelConfig(
        arctic_winter_lead_closure_fraction=0.80,
        arctic_winter_lead_closure_temperature_scale_c=15.0,
    )
    model = _minimal_arctic_model(cfg)
    weights = model._arctic_winter_lead_closure_weight(
        np.array([-17.0, -4.0, 0.0])
    )
    assert weights[0] > 0.75
    assert weights[1] < 0.02
    assert weights[2] == 0.0


def test_default_winter_lead_closure_contract_and_science_prior() -> None:
    from monte_carlo import PHYSICAL_CLIMATE_PRIORS, science_default_ranges

    cfg = ModelConfig()
    assert cfg.arctic_winter_lead_closure_fraction == pytest.approx(0.0)
    assert cfg.arctic_winter_lead_closure_onset_fraction == pytest.approx(0.01)
    assert cfg.arctic_winter_lead_closure_temperature_scale_c == pytest.approx(15.0)
    spec = PHYSICAL_CLIMATE_PRIORS["arctic_winter_lead_closure_fraction"]
    assert spec.lower == pytest.approx(0.0)
    assert spec.upper == pytest.approx(0.60)
    assert spec.mode == pytest.approx(0.10)
    assert spec.point_mass_at_zero == pytest.approx(0.35)
    assert "arctic_winter_lead_closure_fraction" in science_default_ranges("none")


def test_release_packager_excludes_transient_validation_runner_files() -> None:
    import importlib.util

    root = Path(__file__).resolve().parents[1]
    package_path = root / "tools" / "package_v22914.py"
    spec = importlib.util.spec_from_file_location("package_v22914_test", package_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    created = [
        root / "validation_v22913_runner.pid",
        root / "validation_v22913_runner.log",
        root / "validation_v22914_runner.pid",
        root / "validation_v22914_runner.log",
    ]
    previous = {path: path.read_bytes() if path.exists() else None for path in created}
    try:
        for path in created:
            path.write_text("transient\n", encoding="utf-8")
        names = {path.relative_to(root).as_posix() for path in module.release_files()}
        assert not names.intersection(path.name for path in created)
    finally:
        for path, content in previous.items():
            if content is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(content)
