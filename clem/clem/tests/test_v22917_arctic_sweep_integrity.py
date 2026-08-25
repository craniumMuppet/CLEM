from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from climate_model import MODEL_VERSION, ModelConfig, ProcessClimateModel
from co2_target_sweep import AMOC_BASELINE_DEFINITION, _sweep_member_worker
from safe_checkpoint import read_checkpoint, write_checkpoint
from sea_ice_validation import march_extent_trend_robustness
from trusted_validation_pickle import (
    UntrustedValidationPickleError,
    dump_trusted_pickle,
    load_trusted_pickle,
)
from worker_supervision import save_compatible_checkpoint


def _lightweight_model(**updates: object) -> ProcessClimateModel:
    config = replace(
        ModelConfig(),
        resolution_deg=10.0,
        duration_years=1.0,
        dt_years=0.1,
        record_every_years=0.1,
        seasonal_arctic_enabled=False,
        auto_initialize_from_1850=False,
        **updates,
    )
    return ProcessClimateModel(config)


def test_version_and_revised_arctic_defaults() -> None:
    cfg = ModelConfig()
    assert tuple(int(value) for value in MODEL_VERSION.split(".")) >= (2, 29, 17)
    assert cfg.arctic_new_ice_local_thickness_m == pytest.approx(0.22)
    assert cfg.arctic_ice_concentration_exponent == pytest.approx(0.56)
    assert cfg.arctic_winter_lead_closure_fraction == pytest.approx(0.0)
    assert cfg.arctic_transient_substeps_per_year == 80


def test_thin_ice_mapping_has_physical_small_volume_limit() -> None:
    model = _lightweight_model()
    equivalent = np.asarray([1.0e-8, 0.01, 0.10, 0.50], dtype=float)
    concentration = model._arctic_concentration_from_equivalent_thickness(equivalent)
    local = np.divide(
        equivalent,
        concentration,
        out=np.zeros_like(equivalent),
        where=concentration > 0.0,
    )
    assert local[0] == pytest.approx(model.config.arctic_new_ice_local_thickness_m, rel=1e-6)
    assert 0.10 < local[1] < 0.30
    assert np.allclose(concentration * local, equivalent, rtol=0.0, atol=1.0e-12)
    assert np.all(np.diff(local) > 0.0)


def test_arctic_internal_cadence_is_outer_timestep_independent() -> None:
    model = _lightweight_model()
    target = 1.0 / 80.0
    for outer_dt in (0.05, 0.025, 0.0125):
        durations = model._arctic_substep_durations(outer_dt)
        assert sum(durations) == pytest.approx(outer_dt, abs=1.0e-15)
        assert all(value <= target + 1.0e-15 for value in durations)
        assert all(value == pytest.approx(target, abs=1.0e-15) for value in durations)


def test_open_water_longwave_damping_is_active() -> None:
    base = _lightweight_model(arctic_interface_longwave_damping_wm2_k=0.0)
    damped = _lightweight_model(arctic_interface_longwave_damping_wm2_k=2.2)
    shape = base.grid.lat.shape
    freezing = base.config.arctic_interface_freezing_temperature_c
    open_fraction = np.ones(shape)
    open_temperature = np.full(shape, freezing + 5.0)
    heat = (
        open_fraction
        * base.config.arctic_interface_heat_capacity_wyr_m2_k
        * (open_temperature - freezing)
    )
    ice_energy = np.zeros(shape)
    common = dict(
        insolation_wm2=np.zeros(shape),
        air_temperature_c=np.full(shape, freezing + 5.0),
        ice_energy_wyr_m2=ice_energy,
        open_water_heat_wyr_m2=heat,
        basal_ocean_heat_flux_wm2=0.0,
        ocean_temperature_c=np.full(shape, freezing + 5.0),
    )
    flux_undamped = base._arctic_surface_fluxes(**common)["open_flux_wm2"]
    flux_damped = damped._arctic_surface_fluxes(**common)["open_flux_wm2"]
    assert np.allclose(flux_damped - flux_undamped, -11.0, atol=1.0e-10)


def test_highly_compressible_safe_checkpoint_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "constant-array.ckpt"
    payload = {"values": np.zeros(1_000_000, dtype=np.float64)}
    write_checkpoint(path, payload)
    restored = read_checkpoint(path)
    assert np.array_equal(restored["values"], payload["values"])


def test_private_validation_pickle_rejects_unmarked_input(tmp_path: Path) -> None:
    trusted = tmp_path / "private"
    path = trusted / "value.pkl"
    dump_trusted_pickle(path, {"answer": 42}, trusted)
    assert load_trusted_pickle(path, trusted) == {"answer": 42}
    raw = trusted / "raw.pkl"
    raw.write_bytes(b"not-an-egcm-validation-transport")
    with pytest.raises(UntrustedValidationPickleError):
        load_trusted_pickle(raw, trusted)


def test_partial_co2_member_keeps_other_targets(tmp_path: Path) -> None:
    model = _lightweight_model()
    base = model.config
    fingerprint = "partial-target-regression"
    member_root = tmp_path / "targets"
    member_dir = member_root / "member_00000000"
    member_dir.mkdir(parents=True)
    start_ppm = float(base.co2_reference_ppm)
    initial_amoc = float(model.state.amoc_sv)
    baseline = {
        "status": "ok",
        "member": 0,
        "baseline_definition": AMOC_BASELINE_DEFINITION,
        "initialization": "native_reference_control_state",
        "common_start_ppm": start_ppm,
        "reference_co2_ppm": start_ppm,
        "initial_equilibration_years_requested": 0.0,
        "initial_equilibration_years_used": 0.0,
        "initial_amoc_sv": initial_amoc,
        "state": asdict(model.state.copy()),
    }
    save_compatible_checkpoint(member_dir / "baseline.ckpt", fingerprint, baseline)
    years = np.asarray([1850.0, 1851.0], dtype=float)
    successful = {
        "status": "ok",
        "target_index": 0,
        "target_ppm": 300.0,
        "common_start_ppm": start_ppm,
        "initial_amoc_baseline_sv": initial_amoc,
        "amoc_baseline_definition": AMOC_BASELINE_DEFINITION,
        "years": years,
        "amoc_sv": np.asarray([initial_amoc, initial_amoc - 0.1], dtype=np.float32),
        "amoc_decline_percent": np.asarray([0.0, 100.0 * 0.1 / initial_amoc], dtype=np.float32),
        "global_surface_warming_c": np.asarray([0.0, 0.1], dtype=np.float32),
        "co2_ppm": np.asarray([start_ppm, 300.0], dtype=np.float32),
        "target_summary": {"maximum_salt_error_ppm": 0.0},
        "run_summary": {"model_version": MODEL_VERSION},
    }
    failed = {
        "status": "failed",
        "member": 0,
        "target_index": 1,
        "target_ppm": 600.0,
        "common_start_ppm": start_ppm,
        "initial_amoc_baseline_sv": initial_amoc,
        "amoc_baseline_definition": AMOC_BASELINE_DEFINITION,
        "error": "RuntimeError: synthetic target failure",
        "traceback": "",
    }
    save_compatible_checkpoint(member_dir / "target_00000000.ckpt", fingerprint, successful)
    save_compatible_checkpoint(member_dir / "target_00000001.ckpt", fingerprint, failed)
    payload = (
        0,
        asdict(base),
        {},
        start_ppm,
        np.asarray([300.0, 600.0]),
        1.0,
        1.0,
        1.0,
        0.95,
        5.0,
        0.0,
        "none",
        False,
        False,
        10.0,
        str(member_root),
        fingerprint,
        True,
        False,
        None,
    )
    result = _sweep_member_worker(payload)
    assert result["status"] == "partial"
    assert result["successful_target_simulations"] == 1
    assert result["failed_target_simulations"] == 1
    assert result["target_success_mask"].tolist() == [True, False]
    assert np.all(np.isfinite(result["amoc_sv"][0]))
    assert np.all(np.isnan(result["amoc_sv"][1]))


def test_march_temporal_target_uses_extent_not_raw_area() -> None:
    years = np.arange(1988, 2021)
    frame = pd.DataFrame(
        {
            "year": np.repeat(years, 1),
            "month": 3,
            "model_extent": 16.0 - 0.03 * (years - 1988),
            "observed_extent": 16.0 - 0.04 * (years - 1988),
            "model_area": 13.0 - 0.01 * (years - 1988),
            "observed_area": 13.0 + 0.50 * (years >= 2008) - 0.02 * (years - 1988),
        }
    )
    result = march_extent_trend_robustness(frame)
    assert result["metric"] == "march_extent"
    assert result["raw_march_area_trend_used_for_calibration"] is False
    assert result["period_results"][0]["observed"]["ols_trend_million_km2_per_decade"] == pytest.approx(-0.4)
