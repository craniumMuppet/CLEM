"""Focused regressions for v2.29.11 integrity and recovery fixes."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import co2_target_sweep as sweep
from climate_model import MODEL_VERSION, ModelConfig, ProcessClimateModel
from run_state import initialize_run_state
from runtime_provenance import ROOT as PROVENANCE_ROOT, runtime_provenance, sha256_file
from safe_checkpoint import CheckpointFormatError, read_checkpoint, write_checkpoint
from sea_ice_validation import march_area_trend_robustness
from worker_supervision import load_compatible_checkpoint, save_compatible_checkpoint


def _safe_summary() -> dict[str, float]:
    return {
        "maximum_absolute_salt_conservation_error_ppm": 0.0,
        "maximum_pre_projection_salt_conservation_error_ppm": 0.0,
        "cumulative_absolute_salt_projection_correction_ppm": 0.0,
        "initial_amoc_density_driver_ratio": 0.8,
        "maximum_arctic_open_water_temperature_c": 5.0,
        "maximum_arctic_open_water_temperature_c_at_5pct_open": 4.0,
        "maximum_dormant_arctic_open_water_heat_wyr_m2": 0.0,
        "arctic_reference_periodic_closure_wyr_m2": 0.0,
        "arctic_reference_spinup_convergence_wyr_m2": 0.0,
        "arctic_reference_convergence_tolerance_wyr_m2": 1.0e-5,
    }


def test_version_and_native_amoc_reference() -> None:
    assert MODEL_VERSION == "2.29.29"
    ratios: list[float] = []
    north: list[float] = []
    for resolution in (2.5, 5.0, 10.0):
        model = ProcessClimateModel(
            replace(
                ModelConfig(),
                resolution_deg=resolution,
                duration_years=0.1,
                auto_initialize_from_1850=False,
            )
        )
        assert model.amoc_reference_mode == "native_grid_fractional_box_means"
        ratios.append(float(model.baseline_density_driver_ratio))
        north.append(float(model.baseline_amoc_north_c))
    assert max(ratios) - min(ratios) <= 0.20
    # Different native grids must not be hidden behind one canonical climatology.
    assert max(north) - min(north) > 1.0e-6


def test_safe_checkpoint_round_trip_and_pickle_rejection(tmp_path: Path) -> None:
    path = tmp_path / "member.ckpt"
    value = {
        "status": "ok",
        "tuple": (1, 2.5, Path("relative/path")),
        "array": np.arange(12, dtype=np.float32).reshape(3, 4),
        "nonfinite": [float("nan"), float("inf"), float("-inf")],
    }
    write_checkpoint(path, value)
    restored = read_checkpoint(path)
    assert restored["status"] == "ok"
    assert restored["tuple"] == (1, 2.5, Path("relative/path"))
    np.testing.assert_array_equal(restored["array"], value["array"])
    assert np.isnan(restored["nonfinite"][0])

    malicious = tmp_path / "legacy_pickle.ckpt"
    malicious.write_bytes(b"\x80\x04cos\nsystem\n.")
    with pytest.raises(CheckpointFormatError):
        read_checkpoint(malicious)


def test_runtime_provenance_covers_physics_orchestration_and_lockfiles() -> None:
    record = runtime_provenance()
    files = record["source_files"]
    for name in (
        "climate_model.py",
        "monte_carlo.py",
        "co2_target_sweep.py",
        "worker_supervision.py",
        "safe_checkpoint.py",
        "requirements.lock",
        "pyproject.toml",
    ):
        assert name in files
        assert len(files[name]) == 64
        assert files[name] == sha256_file(PROVENANCE_ROOT / name)
    assert len(record["combined_digest_sha256"]) == 64


def test_same_version_source_fingerprint_mismatch_rejects_resume(tmp_path: Path) -> None:
    initialize_run_state(
        tmp_path,
        run_kind="monte_carlo",
        model_version=MODEL_VERSION,
        fingerprint="source-digest-a",
        seed_requested=1,
        seed_used=1,
        seed_source="user",
        checkpoint_directory="checkpoints",
        total_work_units=1,
        work_unit_name="members",
        resume=False,
        settings={},
    )
    with pytest.raises(ValueError, match="incompatible"):
        initialize_run_state(
            tmp_path,
            run_kind="monte_carlo",
            model_version=MODEL_VERSION,
            fingerprint="source-digest-b",
            seed_requested=1,
            seed_used=1,
            seed_source="user",
            checkpoint_directory="checkpoints",
            total_work_units=1,
            work_unit_name="members",
            resume=True,
            settings={},
        )


def test_failed_nested_diagnostic_is_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    member_dir = tmp_path / "member_00000000"
    diagnostic = member_dir / "diagnostic.ckpt"
    save_compatible_checkpoint(
        diagnostic,
        "fingerprint",
        {"member": 0, "status": "failed", "error": "transient"},
    )
    diagnostic_calls: list[int] = []
    original_model = ProcessClimateModel

    def fake_member_worker(payload):
        diagnostic_calls.append(int(payload[0]))
        return {"member": 0, "status": "ok", "summary": _safe_summary()}

    class FakeRunResult:
        def __init__(self, start: float, target: float, initial_amoc: float) -> None:
            years = np.arange(1850.0, 1853.0)
            self.dataframe = pd.DataFrame(
                {
                    "year": years,
                    "amoc_sv": [initial_amoc, initial_amoc - 0.5, initial_amoc - 1.0],
                    "global_surface_warming_c": [0.0, 0.2, 0.4],
                    "co2_ppm": [start, (start + target) / 2.0, target],
                    "salt_conservation_error_ppm": [0.0, 0.0, 0.0],
                }
            )

        def summary(self):
            return _safe_summary()

    class FakeModel:
        def __init__(self, config: ModelConfig) -> None:
            self.config = config
            self.state = original_model(config).state.copy()

        def run(self):
            return FakeRunResult(
                float(self.config.co2_start_ppm),
                float(self.config.co2_end_ppm),
                float(self.state.amoc_sv),
            )

    monkeypatch.setattr(sweep, "_member_worker", fake_member_worker)
    monkeypatch.setattr(sweep, "ProcessClimateModel", FakeModel)
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
        0.9,
        0.5,
        1000.0,
        "none",
        True,
        False,
        10.0,
        str(tmp_path),
        "fingerprint",
        True,
        True,
        None,
    )
    result = sweep._sweep_member_worker(payload)
    assert result["status"] == "ok"
    assert diagnostic_calls == [0]
    restored = load_compatible_checkpoint(diagnostic, "fingerprint")
    assert restored["status"] == "ok"

def test_specific_targets_accept_200_with_default_start() -> None:
    targets = sweep.resolve_targets(
        "specific", 278.3, 50.0, 1200.0, "200,300,600,1200"
    )
    np.testing.assert_allclose(targets, [200.0, 300.0, 600.0, 1200.0])
    config = ModelConfig(
        scenario="linear_ramp_hold",
        co2_start_ppm=278.3,
        co2_end_ppm=float(targets[0]),
        co2_ramp_years=10.0,
        co2_hold_years=10.0,
        duration_years=20.0,
    )
    config.validate()
    assert config.co2_start_ppm == pytest.approx(278.3)
    assert config.co2_end_ppm == pytest.approx(200.0)


def test_march_scientific_gate_rejects_large_forced_bias() -> None:
    rows: list[dict[str, float]] = []
    for year in range(1979, 2021):
        observed = 15.0 - 0.04 * (year - 1979) / 10.0
        model = 15.0 - 0.13 * (year - 1979) / 10.0
        rows.append(
            {
                "year": year,
                "month": 3,
                "model_area": model,
                "observed_area": observed,
                "model_extent": model * 1.1,
                "observed_extent": observed * 1.1,
            }
        )
    result = march_area_trend_robustness(pd.DataFrame(rows))
    assert result["scientifically_adequate_for_quantitative_temporal_use"] is False
    assert result["passed"] is False
    assert "historical records were inspected during development" in result["mandatory_limitation"].lower()


def test_mean_timeseries_schema_is_not_percentile_schema() -> None:
    source = Path(sweep.__file__).read_text(encoding="utf-8")
    assert 'percentile_frame[mean_columns].to_csv' in source
    assert '"weighted_mean_amoc_decline_percent"' in source
