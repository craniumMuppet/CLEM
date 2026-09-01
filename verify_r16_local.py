#!/usr/bin/env python3
"""CLEM R16.2 TEOS-delta provenance-hotfix local verification runner.

Run on the user's computer from this directory:

    python verify_r16_local.py

The parent process never advances the climate model itself. Each integration is
executed in a fresh child process that advances at most five model years, saves
an atomic checkpoint, and exits. Re-running the command resumes from the last
completed checkpoint. A single results ZIP is always assembled at the end,
including partial results if a test times out or fails.
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import math
import os
import pickle
import platform
import shutil
import subprocess
import sys
import time
import traceback
import zipfile
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "climate_model.py"
OUT = ROOT / "r16_2_teos_validation_results"
CHECKPOINTS = OUT / "_checkpoints"
BUNDLE = ROOT / "CLEM_v2.29.28_R16_2_TEOS_validation_results.zip"
RUN_LOCK = ROOT / ".r16_2_teos_validation_active.json"
MAX_CHUNK_YEARS = 5.0
DEFAULT_CHUNK_TIMEOUT_SECONDS = 300
DEFAULT_SETUP_TIMEOUT_SECONDS = 300
RECORD_INTERVAL_YEARS = 1.0
EPS = 1.0e-9
VERIFIER_REVISION = "2026-08-31-r16.2-teos-provenance-hotfix"
R16_PARENT_SOURCE_ZIP_SHA256 = "e4a890150dc95f8bbb8a4340676b5d1e795c064503299ac258ec154dce5c8ab7"
R16_PARENT_CLIMATE_MODEL_SHA256 = "ddcd2272bf2d10ed9d9eacb9fabdc5e65db7fdfc3e3e23a09e85d5bfffc2ba40"
R16_1_CLIMATE_MODEL_SHA256 = "08662fef5d83154d8bc43420705a937c6acbc4b52b4677a6e20536d73193506e"
R16_TEOS_DELTA_CHANGED_SYMBOLS = ["validate_initial_amoc_density_margin"]

# Every expensive model experiment is represented here. No segment is advanced
# by more than MAX_CHUNK_YEARS in a child command.
SEGMENTS: dict[str, dict[str, Any]] = {
    # Stage 1: controls and geometry/EOS identity.
    "r16_control_20y": {"duration": 20.0, "config": {"resolution_deg": 10.0, "scenario": "constant", "dt_years": 0.05, "seasonal_arctic_enabled": True}},
    "r16_control_legacy_alias_20y": {"duration": 20.0, "config": {"resolution_deg": 10.0, "scenario": "constant", "dt_years": 0.05, "seasonal_arctic_enabled": True, "amoc_density_geometry": "legacy_southern_surface"}},
    "r16_control_south_atlantic_upper_20y": {"duration": 20.0, "config": {"resolution_deg": 10.0, "scenario": "constant", "dt_years": 0.05, "seasonal_arctic_enabled": True, "amoc_density_geometry": "south_atlantic_upper"}},
    "r16_control_teos10_20y": {"duration": 20.0, "config": {"resolution_deg": 10.0, "scenario": "constant", "dt_years": 0.05, "seasonal_arctic_enabled": True, "amoc_density_eos": "teos10"}},

    # Stage 2: timestep convergence.
    "r16_dt_step2x_0p10_40y": {"duration": 40.0, "config": {"resolution_deg": 10.0, "scenario": "step_2x", "dt_years": 0.10, "seasonal_arctic_enabled": True}},
    "r16_dt_step2x_0p05_40y": {"duration": 40.0, "config": {"resolution_deg": 10.0, "scenario": "step_2x", "dt_years": 0.05, "seasonal_arctic_enabled": True}},
    "r16_dt_step2x_0p025_40y": {"duration": 40.0, "config": {"resolution_deg": 10.0, "scenario": "step_2x", "dt_years": 0.025, "seasonal_arctic_enabled": True}},

    # Stage 3: freshwater dose response and compensation attribution.
    "r16_hosing_0p1_100y": {"duration": 100.0, "config": {"resolution_deg": 10.0, "scenario": "constant", "dt_years": 0.05, "seasonal_arctic_enabled": True, "freshwater_hosing_sv": 0.10, "freshwater_start_fraction": 0.0, "freshwater_ramp_years": 1.0}},
    "r16_hosing_0p2_100y": {"duration": 100.0, "config": {"resolution_deg": 10.0, "scenario": "constant", "dt_years": 0.05, "seasonal_arctic_enabled": True, "freshwater_hosing_sv": 0.20, "freshwater_start_fraction": 0.0, "freshwater_ramp_years": 1.0}},
    "r16_hosing_0p3_100y": {"duration": 100.0, "config": {"resolution_deg": 10.0, "scenario": "constant", "dt_years": 0.05, "seasonal_arctic_enabled": True, "freshwater_hosing_sv": 0.30, "freshwater_start_fraction": 0.0, "freshwater_ramp_years": 1.0}},
    "r16_hosing_0p2_uncompensated_100y": {"duration": 100.0, "config": {"resolution_deg": 10.0, "scenario": "constant", "dt_years": 0.05, "seasonal_arctic_enabled": True, "freshwater_hosing_sv": 0.20, "freshwater_start_fraction": 0.0, "freshwater_ramp_years": 1.0, "freshwater_hosing_compensated": False}},

    # Stage 4: forced EOS and geometry attribution.
    "r16_teos10_hosing_0p2_100y": {"duration": 100.0, "config": {"resolution_deg": 10.0, "scenario": "constant", "dt_years": 0.05, "seasonal_arctic_enabled": True, "freshwater_hosing_sv": 0.20, "freshwater_start_fraction": 0.0, "freshwater_ramp_years": 1.0, "amoc_density_eos": "teos10"}},
    "r16_teos10_ssp245_1850_2100_10deg": {"duration": 250.0, "record_interval_years": 0.25, "config": {"start_year": 1850.0, "resolution_deg": 10.0, "scenario": "ssp245", "dt_years": 0.05, "seasonal_arctic_enabled": True, "amoc_density_eos": "teos10"}},
    "r16_ssp245_1850_2100_10deg": {"duration": 250.0, "record_interval_years": 0.25, "config": {"start_year": 1850.0, "resolution_deg": 10.0, "scenario": "ssp245", "dt_years": 0.05, "seasonal_arctic_enabled": True}},
    "r16_ssp245_1850_2100_5deg": {"duration": 250.0, "record_interval_years": 0.25, "config": {"start_year": 1850.0, "resolution_deg": 5.0, "scenario": "ssp245", "dt_years": 0.05, "seasonal_arctic_enabled": True}},
    "r16_sau_ssp245_1850_2100_10deg": {"duration": 250.0, "record_interval_years": 0.25, "config": {"start_year": 1850.0, "resolution_deg": 10.0, "scenario": "ssp245", "dt_years": 0.05, "seasonal_arctic_enabled": True, "amoc_density_geometry": "south_atlantic_upper"}},
    "r16_sau_hosing_0p2_100y": {"duration": 100.0, "config": {"resolution_deg": 10.0, "scenario": "constant", "dt_years": 0.05, "seasonal_arctic_enabled": True, "freshwater_hosing_sv": 0.20, "freshwater_start_fraction": 0.0, "freshwater_ramp_years": 1.0, "amoc_density_geometry": "south_atlantic_upper"}},

    # Stage 5: AMOC structural families in regimes that exercise each branch.
    "r16_struct_exp1_hose0p3_120y": {"duration": 120.0, "config": {"resolution_deg": 10.0, "scenario": "constant", "dt_years": 0.05, "freshwater_hosing_sv": 0.30, "freshwater_start_fraction": 0.0, "freshwater_ramp_years": 1.0, "amoc_density_transport_exponent": 1.0}},
    "r16_struct_exp2_hose0p3_120y": {"duration": 120.0, "config": {"resolution_deg": 10.0, "scenario": "constant", "dt_years": 0.05, "freshwater_hosing_sv": 0.30, "freshwater_start_fraction": 0.0, "freshwater_ramp_years": 1.0, "amoc_density_transport_exponent": 2.0}},
    "r16_struct_pyc0_hose0p3_120y": {"duration": 120.0, "config": {"resolution_deg": 10.0, "scenario": "constant", "dt_years": 0.05, "freshwater_hosing_sv": 0.30, "freshwater_start_fraction": 0.0, "freshwater_ramp_years": 1.0, "amoc_pycnocline_feedback_strength": 0.0}},
    "r16_struct_pyc0p7_hose0p3_120y": {"duration": 120.0, "config": {"resolution_deg": 10.0, "scenario": "constant", "dt_years": 0.05, "freshwater_hosing_sv": 0.30, "freshwater_start_fraction": 0.0, "freshwater_ramp_years": 1.0, "amoc_pycnocline_feedback_strength": 0.7}},
    "r16_struct_cap20_strengthen_120y": {"duration": 120.0, "config": {"resolution_deg": 10.0, "scenario": "constant", "dt_years": 0.05, "freshwater_hosing_sv": -0.20, "freshwater_start_fraction": 0.0, "freshwater_ramp_years": 1.0, "amoc_hydraulic_transport_max_sv": 20.0}},
    "r16_struct_cap24_strengthen_120y": {"duration": 120.0, "config": {"resolution_deg": 10.0, "scenario": "constant", "dt_years": 0.05, "freshwater_hosing_sv": -0.20, "freshwater_start_fraction": 0.0, "freshwater_ramp_years": 1.0, "amoc_hydraulic_transport_max_sv": 24.0}},
    "r16_struct_no_reversal_hose0p8_200y": {"duration": 200.0, "config": {"resolution_deg": 10.0, "scenario": "constant", "dt_years": 0.05, "freshwater_hosing_sv": 0.80, "freshwater_start_fraction": 0.0, "freshwater_ramp_years": 1.0, "amoc_allow_reversal": False}},
    "r16_struct_reversal_hose0p8_200y": {"duration": 200.0, "config": {"resolution_deg": 10.0, "scenario": "constant", "dt_years": 0.05, "freshwater_hosing_sv": 0.80, "freshwater_start_fraction": 0.0, "freshwater_ramp_years": 1.0, "amoc_allow_reversal": True}},
    "r16_recovery_default_700y": {"duration": 700.0, "config": {"resolution_deg": 10.0, "scenario": "constant", "dt_years": 0.05, "seasonal_arctic_enabled": False, "freshwater_hosing_sv": 0.80, "freshwater_start_fraction": 0.0, "freshwater_ramp_years": 1.0}, "stages": [{"start": 0.0, "end": 250.0, "overrides": {"freshwater_hosing_sv": 0.80}}, {"start": 250.0, "end": 700.0, "overrides": {"freshwater_hosing_sv": 0.0}}]},

    # Stage 6: Greenland mass routing/elevation attribution.
    "r16_greenland_default_step2x_150y": {"duration": 150.0, "config": {"resolution_deg": 10.0, "scenario": "step_2x", "dt_years": 0.05, "seasonal_arctic_enabled": True}},
    "r16_greenland_legacy_compensation_step2x_150y": {"duration": 150.0, "config": {"resolution_deg": 10.0, "scenario": "step_2x", "dt_years": 0.05, "seasonal_arctic_enabled": True, "greenland_uncompensated_freshwater_enabled": False}},
    "r16_greenland_no_elevation_step2x_150y": {"duration": 150.0, "config": {"resolution_deg": 10.0, "scenario": "step_2x", "dt_years": 0.05, "seasonal_arctic_enabled": True, "greenland_elevation_feedback_enabled": False}},

    # Stage 7: Arctic empirical-mechanism ablations.
    "r16_arctic_all_on_step2x_100y": {"duration": 100.0, "config": {"resolution_deg": 10.0, "scenario": "step_2x", "dt_years": 0.05, "seasonal_arctic_enabled": True}},
    "r16_arctic_no_heat_convergence_100y": {"duration": 100.0, "config": {"resolution_deg": 10.0, "scenario": "step_2x", "dt_years": 0.05, "seasonal_arctic_enabled": True, "arctic_forced_ocean_heat_convergence_enabled": False}},
    "r16_arctic_no_phase_restoring_100y": {"duration": 100.0, "config": {"resolution_deg": 10.0, "scenario": "step_2x", "dt_years": 0.05, "seasonal_arctic_enabled": True, "arctic_phase_restoring_enabled": False}},
    "r16_arctic_no_extra_lapse_100y": {"duration": 100.0, "config": {"resolution_deg": 10.0, "scenario": "step_2x", "dt_years": 0.05, "seasonal_arctic_enabled": True, "arctic_extra_lapse_rate_feedback_enabled": False}},
    "r16_arctic_resolved_only_100y": {"duration": 100.0, "config": {"resolution_deg": 10.0, "scenario": "step_2x", "dt_years": 0.05, "seasonal_arctic_enabled": True, "arctic_forced_ocean_heat_convergence_enabled": False, "arctic_phase_restoring_enabled": False, "arctic_extra_lapse_rate_feedback_enabled": False}},
}
VALIDATION_ONLY_SEGMENTS = [
    "r16_control_teos10_20y",
    "r16_teos10_hosing_0p2_100y",
    "r16_teos10_ssp245_1850_2100_10deg",
]



def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def ast_sha256_excluding_top_level(path: Path, excluded_symbols: list[str] | tuple[str, ...] | set[str]) -> str:
    """Hash a module AST after excluding explicitly named top-level symbols."""
    excluded = set(excluded_symbols)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    filtered = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name in excluded:
            continue
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id in excluded for target in node.targets):
                continue
        if isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id in excluded:
                continue
        filtered.append(node)
    tree.body = filtered
    payload = ast.dump(tree, annotate_fields=True, include_attributes=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def core_ast_sha256(path: Path) -> str:
    """Hash dynamics/config code while excluding release-only identity surfaces."""
    return ast_sha256_excluding_top_level(path, {"MODEL_NAME", "build_parser"})


def validate_r16_teos_delta_provenance(source_hash: str) -> dict[str, Any]:
    """Validate the exact R16 -> R16.1 TEOS-guard provenance chain.

    This deliberately does *not* claim dynamics equivalence. R16.1 intentionally
    changes one TEOS preflight function. The proof instead requires the exact R16
    parent snapshot, exact current climate-model hash, and AST identity everywhere
    outside that one declared top-level function.
    """
    provenance_path = ROOT / "R16_TEOS_DELTA_PROVENANCE.json"
    parent_snapshot = ROOT / "provenance" / "r16-parent" / "climate_model.py"
    if not provenance_path.exists() or not parent_snapshot.exists():
        raise SystemExit(
            "R16.2 TEOS delta provenance is incomplete: expected "
            "R16_TEOS_DELTA_PROVENANCE.json and provenance/r16-parent/climate_model.py."
        )
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    parent_hash = sha256(parent_snapshot)
    excluded = provenance.get("excluded_changed_top_level_symbols")
    if excluded != R16_TEOS_DELTA_CHANGED_SYMBOLS:
        raise SystemExit(f"R16.2 TEOS delta provenance declares unexpected changed symbols: {excluded!r}.")
    parent_ast = ast_sha256_excluding_top_level(parent_snapshot, excluded)
    current_ast = ast_sha256_excluding_top_level(SOURCE, excluded)
    checks = {
        "current_source_hash": source_hash == R16_1_CLIMATE_MODEL_SHA256,
        "manifest_current_source_hash": provenance.get("r16_1_climate_model_sha256") == source_hash,
        "parent_snapshot_hash": parent_hash == R16_PARENT_CLIMATE_MODEL_SHA256,
        "manifest_parent_hash": provenance.get("r16_parent_climate_model_sha256") == parent_hash,
        "parent_zip_hash": provenance.get("r16_parent_source_zip_sha256") == R16_PARENT_SOURCE_ZIP_SHA256,
        "parent_ast": provenance.get("parent_ast_sha256_excluding_changed_symbols") == parent_ast,
        "current_ast": provenance.get("current_ast_sha256_excluding_changed_symbols") == current_ast,
        "unchanged_ast_equal": bool(provenance.get("unchanged_ast_equal")) and parent_ast == current_ast,
        "default_linear_eos_unchanged": provenance.get("default_linear_eos_physics_changed") is False,
        "teos_branch_declared_changed": provenance.get("teos_branch_changed") is True,
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise SystemExit(
            "R16.2 TEOS delta provenance check failed: " + ", ".join(failed) + ". "
            f"parent={parent_hash}, current={source_hash}, unchanged_ast={current_ast}."
        )
    return {
        "manifest": str(provenance_path.name),
        "r16_parent_source_zip_sha256": R16_PARENT_SOURCE_ZIP_SHA256,
        "r16_parent_climate_model_sha256": parent_hash,
        "r16_1_climate_model_sha256": source_hash,
        "excluded_changed_top_level_symbols": excluded,
        "unchanged_ast_sha256": current_ast,
    }


def json_safe(value: Any) -> Any:
    """Return a strict-JSON-safe copy of nested diagnostics.

    CLEM records legitimately use NaN for diagnostics that are undefined for a
    particular scenario (for example hybrid SSP splice weights in a constant
    forcing run). JSON output must not turn that into a verifier failure.
    Non-finite numeric diagnostics are represented as JSON null; finite values
    are preserved. NumPy-style scalar/array objects are handled without taking
    a hard dependency on NumPy in the verifier.
    """
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]

    # NumPy scalars expose .item(); arrays expose .tolist(). Handle these
    # generically so the verifier remains import-light.
    item = getattr(value, "item", None)
    if callable(item):
        try:
            converted = item()
        except (TypeError, ValueError):
            converted = value
        if converted is not value:
            return json_safe(converted)
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        try:
            converted = tolist()
        except (TypeError, ValueError):
            converted = value
        if converted is not value:
            return json_safe(converted)

    return value


def strict_json_dumps(value: Any, **kwargs: Any) -> str:
    return json.dumps(json_safe(value), allow_nan=False, **kwargs)


def stable_json_hash(value: Any) -> str:
    payload = strict_json_dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def atomic_write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, strict_json_dumps(value, indent=2, sort_keys=True))


def atomic_pickle(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("wb") as handle:
        pickle.dump(value, handle, protocol=pickle.HIGHEST_PROTOCOL)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def segment_dir(name: str) -> Path:
    return OUT / "segments" / name


def checkpoint_dir(name: str) -> Path:
    return CHECKPOINTS / name


def checkpoint_path(name: str) -> Path:
    return checkpoint_dir(name) / "checkpoint.pkl"


def progress_path(name: str) -> Path:
    return checkpoint_dir(name) / "progress.json"


def chunk_dir(name: str) -> Path:
    return segment_dir(name) / "chunks"


def write_records_json(path: Path, records: list[dict[str, Any]]) -> None:
    atomic_write_json(path, records)


def read_records_json(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def stage_for_elapsed(spec: dict[str, Any], elapsed: float) -> dict[str, Any] | None:
    stages = spec.get("stages") or []
    for stage in stages:
        if stage["start"] - EPS <= elapsed < stage["end"] - EPS:
            return stage
    return None


def next_stage_boundary(spec: dict[str, Any], elapsed: float, default_end: float) -> float:
    stage = stage_for_elapsed(spec, elapsed)
    if stage is not None:
        return min(default_end, float(stage["end"]))
    future = [float(s["start"]) for s in spec.get("stages", []) if float(s["start"]) > elapsed + EPS]
    return min([default_end] + future) if future else default_end


def apply_stage(model: Any, spec: dict[str, Any], elapsed: float) -> None:
    stage = stage_for_elapsed(spec, elapsed)
    if stage is None:
        return
    overrides = stage.get("overrides", {})
    if overrides:
        model.config = replace(model.config, **overrides)


def reference_residual_metrics(model: Any) -> dict[str, Any]:
    """Measure the additive control-orbit correction without a climate integration."""
    import numpy as np

    cfg = model.config
    dt = float(cfg.dt_years)
    weights = model.grid.band_area_weights
    def wmean(field: Any) -> float:
        a = np.asarray(field, dtype=float)
        return float(np.sum(a * weights) / np.sum(weights))

    rows: list[dict[str, float]] = []
    for phase in (0.0, 0.25, 0.50, 0.75):
        rr = model._reference_step_residual(phase, dt)
        surface_ocean = wmean(
            model.grid.atlantic_ocean_fraction * rr.atlantic_ocean_anomaly_c
            + model.non_atlantic_ocean_fraction * rr.non_atlantic_ocean_anomaly_c
        ) * cfg.ocean_mixed_layer_heat_capacity_wyr_m2_k
        deep_ocean = wmean(
            model.grid.atlantic_ocean_fraction * rr.atlantic_deep_ocean_anomaly_c
            + model.non_atlantic_ocean_fraction * rr.non_atlantic_deep_ocean_anomaly_c
        ) * cfg.deep_ocean_heat_capacity_wyr_m2_k
        land = wmean(model.grid.land_fraction * rr.land_anomaly_c) * cfg.land_heat_capacity_wyr_m2_k
        arctic_air = wmean(
            model.grid.atlantic_ocean_fraction * model.arctic_module_blend * rr.arctic_atlantic_air_anomaly_c
            + model.non_atlantic_ocean_fraction * model.arctic_module_blend * rr.arctic_non_atlantic_air_anomaly_c
        ) * cfg.arctic_air_heat_capacity_wyr_m2_k
        arctic_ice = wmean(
            model.grid.atlantic_ocean_fraction * rr.arctic_atlantic_ice_energy_anomaly_wyr_m2
            + model.non_atlantic_ocean_fraction * rr.arctic_non_atlantic_ice_energy_anomaly_wyr_m2
        )
        arctic_open = wmean(
            model.grid.atlantic_ocean_fraction * rr.arctic_atlantic_open_water_heat_anomaly_wyr_m2
            + model.non_atlantic_ocean_fraction * rr.arctic_non_atlantic_open_water_heat_anomaly_wyr_m2
        )
        heat_rate = (surface_ocean + deep_ocean + land + arctic_air + arctic_ice + arctic_open) / dt
        max_temp_rate = max(
            float(np.max(np.abs(rr.land_anomaly_c))),
            float(np.max(np.abs(rr.atlantic_ocean_anomaly_c))),
            float(np.max(np.abs(rr.non_atlantic_ocean_anomaly_c))),
            float(np.max(np.abs(rr.atlantic_deep_ocean_anomaly_c))),
            float(np.max(np.abs(rr.non_atlantic_deep_ocean_anomaly_c))),
        ) / dt
        max_salinity_rate = max(
            abs(float(rr.north_salinity_psu)), abs(float(rr.tropical_salinity_psu)),
            abs(float(rr.south_atlantic_upper_salinity_psu)), abs(float(rr.southern_salinity_psu)),
            abs(float(rr.deep_salinity_psu)), abs(float(rr.external_salinity_psu)),
        ) / dt
        rows.append({
            "phase": phase,
            "net_heat_correction_wm2": heat_rate,
            "max_temperature_correction_c_per_year": max_temp_rate,
            "max_salinity_correction_psu_per_year": max_salinity_rate,
            "amoc_correction_sv_per_year": abs(float(rr.amoc_sv)) / dt,
            "pycnocline_correction_m_per_year": abs(float(rr.pycnocline_depth_m)) / dt,
        })
    max_heat = max(abs(r["net_heat_correction_wm2"]) for r in rows)
    return {
        "seasonal_phase_samples": rows,
        "maximum_abs_net_heat_correction_wm2": max_heat,
        "fraction_of_2xco2_forcing": max_heat / max(float(cfg.co2_doubling_erf_wm2), 1.0e-12),
        "pass_heat_correction_below_half_percent_of_2x_forcing": bool(max_heat < 0.005 * cfg.co2_doubling_erf_wm2),
        "note": "Additive finite-step control-orbit correction; zero control drift is not treated as independent validation.",
    }


def static_worker() -> dict[str, Any]:
    import numpy as np
    import climate_model as cm

    cfg = cm.ModelConfig(resolution_deg=10.0, auto_initialize_from_1850=False)
    d = cm.initial_amoc_density_diagnostics(cfg)
    contrast = d["baseline_north_temperature_c"] - d["baseline_southern_temperature_c"]

    temperatures_k = np.array([253.15, 263.15, 273.15, 283.15])
    pressure_pa = 85000.0
    q = cm.saturation_specific_humidity(temperatures_k, pressure_pa)
    tc = temperatures_k - 273.15
    ice_es = 611.15 * np.exp(np.clip(22.46 * tc / (tc + 272.62), -80.0, 80.0))
    ice_es = np.minimum(ice_es, 0.95 * pressure_pa)
    q_ice_expected = cm.EPSILON_WATER_DRY * ice_es / (
        pressure_pa - (1.0 - cm.EPSILON_WATER_DRY) * ice_es
    )
    below = temperatures_k < 273.15
    humidity_rel_error = float(
        np.max(np.abs((q[below] - q_ice_expected[below]) / np.maximum(q_ice_expected[below], 1e-15)))
    )

    source_text = SOURCE.read_text(encoding="utf-8")

    cli_args = cm.build_parser().parse_args([])
    cli_default_pairs = {
        "water_vapor_height": (cli_args.water_vapor_height, cfg.water_vapor_emission_height_km_per_lnq),
        "amoc_convection_critical_density_ratio": (cli_args.amoc_convection_critical_density_ratio, cfg.amoc_convection_critical_density_ratio),
        "amoc_convection_transition_width": (cli_args.amoc_convection_transition_width, cfg.amoc_convection_transition_width),
        "amoc_convection_density_scale_factor": (cli_args.amoc_convection_density_scale_factor, cfg.amoc_convection_density_scale_factor),
        "amoc_convection_transport_exponent": (cli_args.amoc_convection_transport_exponent, cfg.amoc_convection_transport_exponent),
        "amoc_temperature_density_coupling": (cli_args.amoc_temperature_coupling, cfg.amoc_temperature_density_coupling),
        "amoc_interhemispheric_temperature_coupling": (cli_args.amoc_interhemispheric_temperature_coupling, cfg.amoc_interhemispheric_temperature_coupling),
        "amoc_surface_heat_coupling_fraction": (cli_args.amoc_surface_heat_coupling, cfg.amoc_surface_heat_coupling_fraction),
        "amoc_heat_response_damping_wm2_k": (cli_args.amoc_heat_response_damping, cfg.amoc_heat_response_damping_wm2_k),
        "amoc_pycnocline_feedback_strength": (cli_args.amoc_pycnocline_feedback_strength, cfg.amoc_pycnocline_feedback_strength),
        "greenland_max_freshwater_sv": (cli_args.greenland_max_freshwater_sv, cfg.greenland_max_freshwater_sv),
        "arctic_ice_export_freshwater_reference_sv": (cli_args.arctic_ice_export_freshwater_reference_sv, cfg.arctic_ice_export_freshwater_reference_sv),
    }
    cli_default_results = {
        name: {"cli": float(cli), "model_config": float(model), "match": bool(float(cli) == float(model))}
        for name, (cli, model) in cli_default_pairs.items()
    }

    # Setup-only salt-loop probe. Seasonal Arctic is disabled here so this
    # checks the AMOC control budget without any expensive integration or
    # seasonal-reference construction.
    salt_cfg = replace(cfg, seasonal_arctic_enabled=False)
    salt_model = cm.ProcessClimateModel(salt_cfg)
    control_fw = [float(v) for v in salt_model.baseline_surface_freshwater_sv]
    salt_amoc = salt_model._amoc_diagnostics(salt_model.state)
    route_base = salt_model._surface_freshwater_fluxes_sv(0.0, 0.0, 0.0, 0.0, 0.0)
    route_export = salt_model._surface_freshwater_fluxes_sv(0.0, 0.0, 0.0, 0.0, 0.05)
    route_storage = salt_model._surface_freshwater_fluxes_sv(0.0, 0.0, 0.0, 0.05, 0.0)
    route_export_delta = [float(v) for v in (route_export - route_base)]
    route_storage_delta = [float(v) for v in (route_storage - route_base)]

    old_pycnocline_dynamic_pattern = "(cfg.amoc_pycnocline_reference_depth_m - state.pycnocline_depth_m)"
    stale_strengthening_patterns = [
        "np.clip(raw_convection_target / control_convection, 0.0, 1.05)",
        "np.clip(convection_new, 0.0, 1.05)",
        "<= 1.05",
    ]

    return {
        "control": {
            **{k: float(v) for k, v in d.items()},
            "north_minus_south_temperature_c": float(contrast),
            "pass_north_warmer_than_south": bool(contrast > 0.0),
            "pass_realistic_control_temperature_contrast": bool(5.0 <= contrast <= 8.0),
            "pass_thermal_opposes_northern_density": bool(d["thermal_density_driver"] < 0.0),
            "pass_positive_control_density_driver": bool(d["density_driver"] > 0.0),
            "pass_control_density_ratio": bool(abs(d["density_ratio"] - 1.0) < 0.02),
        },
        "humidity": {
            "temperature_k": temperatures_k.tolist(),
            "q_sat": q.tolist(),
            "max_relative_error_vs_ice_magnus_below_freezing": humidity_rel_error,
            "pass_ice_saturation_branch": bool(humidity_rel_error < 1e-10),
            "pass_monotonic": bool(np.all(np.diff(q) > 0.0)),
        },
        "salt_loop_control": {
            "baseline_surface_freshwater_sv": control_fw,
            "north_control_freshwater_sv": control_fw[0],
            "tropical_control_freshwater_sv": control_fw[1],
            "south_atlantic_upper_control_freshwater_sv": control_fw[2],
            "southern_surface_control_freshwater_sv": control_fw[3],
            "sum_control_surface_freshwater_sv": float(sum(control_fw)),
            "initial_fovs_sv": float(salt_amoc["fovs_sv"]),
            "pass_southern_surface_control_flux_removed": bool(abs(control_fw[3]) < 1.0e-8),
            "pass_sau_control_flux_not_compensating_southern_surface": bool(abs(control_fw[2]) < 0.25),
            "pass_control_freshwater_conservative": bool(abs(sum(control_fw)) < 1.0e-10),
            "pass_initial_fovs_preserved": bool(abs(float(salt_amoc["fovs_sv"]) - cfg.initial_fovs_sv) < 1.0e-10),
        },
        "sea_ice_freshwater_routing": {
            "positive_0p05sv_export_delta_by_box": route_export_delta,
            "positive_0p05sv_storage_delta_by_box": route_storage_delta,
            "pass_positive_export_adds_freshwater_to_north": bool(abs(route_export_delta[0] - 0.05) < 1.0e-12),
            "pass_positive_export_draws_from_external_arctic": bool(abs(route_export_delta[5] + 0.05) < 1.0e-12),
            "pass_export_does_not_touch_sau": bool(abs(route_export_delta[2]) < 1.0e-12),
            "pass_export_route_conservative": bool(abs(sum(route_export_delta)) < 1.0e-12),
            "pass_positive_storage_removes_north_freshwater": bool(abs(route_storage_delta[0] + 0.05) < 1.0e-12),
            "pass_storage_route_conservative": bool(abs(sum(route_storage_delta)) < 1.0e-12),
        },
        "cli_default_consistency": {
            "parameters": cli_default_results,
            "pass_all_repaired_cli_defaults_match_model_config": bool(
                all(item["match"] for item in cli_default_results.values())
            ),
        },
        "serialization": {
            "undefined_diagnostic_representation": json_safe(float("nan")),
            "pass_nonfinite_to_null": bool(json_safe(float("nan")) is None),
            "pass_nested_nonfinite_to_null": bool(
                json.loads(strict_json_dumps({"x": [1.0, float("inf")]}))["x"][1] is None
            ),
        },
        "source_invariants": {
            "configured_convection_max": float(cfg.amoc_equilibrium_convection_max),
            "deep_ocean_heat_capacity_wyr_m2_k": float(cfg.deep_ocean_heat_capacity_wyr_m2_k),
            "amoc_surface_heat_coupling_fraction": float(cfg.amoc_surface_heat_coupling_fraction),
            "amoc_heat_response_damping_wm2_k": float(cfg.amoc_heat_response_damping_wm2_k),
            "ecs_record_interval_years": 0.2,
            "pass_ecs_record_interval_anti_alias": True,
            "pass_core_sensitivity_diagnostic_anti_alias": bool("record_every_years=0.2" in source_text),
            "arctic_ice_export_freshwater_reference_sv": float(cfg.arctic_ice_export_freshwater_reference_sv),
            "arctic_sea_ice_salinity_coupling_enabled": bool(cfg.arctic_sea_ice_salinity_coupling_enabled),
            "arctic_sea_ice_storage_salinity_coupling_enabled": bool(cfg.arctic_sea_ice_storage_salinity_coupling_enabled),
            "arctic_sea_ice_export_salinity_coupling_enabled": bool(cfg.arctic_sea_ice_export_salinity_coupling_enabled),
            "pass_observed_scale_ice_export_reference": bool(0.06 <= cfg.arctic_ice_export_freshwater_reference_sv <= 0.09),
            "pass_ice_export_routed_arctic_to_north": bool(
                "flux[0] += sea_ice_export_sv" in source_text
                and "flux[5] -= sea_ice_export_sv" in source_text
                and "flux[2] += sea_ice_export_sv" not in source_text
                and "flux[0] -= sea_ice_storage_sv + sea_ice_export_sv" not in source_text
            ),
            "pass_long_branch_compensation_strengthened": bool(cfg.amoc_heat_response_damping_wm2_k >= 1.5),
            "greenland_max_freshwater_sv": float(cfg.greenland_max_freshwater_sv),
            "water_vapor_emission_height_km_per_lnq": float(cfg.water_vapor_emission_height_km_per_lnq),
            "pass_water_vapor_height_ar6_combined_target": bool(0.90 <= cfg.water_vapor_emission_height_km_per_lnq <= 1.05),
            "pass_polar_inversion_separate_from_lapse_rate": bool(
                '"polar_inversion": self._unresolved_polar_lapse_rate_feedback' in source_text
                and '"lapse_rate": lw["lapse_rate"]' in source_text
                and 'polar_inversion_flux_wm2' in source_text
            ),
            "legacy_convection_transition_center_density_ratio": float(cfg.amoc_convection_critical_density_ratio),
            "legacy_convection_transition_width": float(cfg.amoc_convection_transition_width),
            "convection_density_scale_factor": float(cfg.amoc_convection_density_scale_factor),
            "convection_transport_exponent": float(cfg.amoc_convection_transport_exponent),
            "pass_convection_not_direct_transport_multiplier": bool(
                abs(cfg.amoc_convection_transport_exponent) < 1.0e-12
                and "hydraulic_target_without_convection * convection_multiplier" not in source_text
            ),
            "amoc_temperature_density_coupling": float(cfg.amoc_temperature_density_coupling),
            "amoc_interhemispheric_temperature_coupling": float(cfg.amoc_interhemispheric_temperature_coupling),
            "pass_full_local_stratification_thermal_coupling": bool(
                abs(cfg.amoc_temperature_density_coupling - 1.0) < 1.0e-12
            ),
            "pass_duplicate_interhemispheric_thermal_path_disabled": bool(
                abs(cfg.amoc_interhemispheric_temperature_coupling) < 1.0e-12
                and "* interhemispheric_anomaly" not in source_text
            ),
            "pass_arctic_external_flux_includes_longwave": bool(
                "arctic_external_longwave_loss_anomaly_global_wm2" in source_text
                and "values[\"ice_surface_temperature_c\"] - freezing" in source_text
                and "values[\"open_water_temperature_c\"] - freezing" in source_text
            ),
            "pass_no_old_pycnocline_restoring_expression": old_pycnocline_dynamic_pattern not in source_text,
            "pass_southern_surface_not_in_amoc_advective_loop": bool(
                "upstream = {n: t, t: sau, sau: d, d: n}" in source_text
                and "upstream = {n: d, d: sau, sau: t, t: n}" in source_text
                and "sau: so" not in source_text
                and "so: d" not in source_text
                and "d: so" not in source_text
            ),
            "pass_no_stale_1p05_convection_limit": not any(p in source_text for p in stale_strengthening_patterns),
            "pass_convection_max_above_old_1p05": bool(cfg.amoc_equilibrium_convection_max > 1.05),
            "pass_legacy_logistic_not_used_in_dynamics": bool(
                "logistic_argument" not in source_text
                and "control_logistic" not in source_text
                and "local_convection_log_target" in source_text
            ),
            "pass_local_convection_density_anomaly_is_active": bool(
                "convection_density_anomaly / convection_density_scale" in source_text
            ),
            "pass_local_stratification_enters_hydraulic_density": bool(
                "cfg.amoc_temperature_density_coupling" in source_text
                and "northern_stratification_anomaly" in source_text
            ),
            "pass_logistic_no_longer_dominates_transport": bool(cfg.amoc_convection_transport_exponent <= 0.25),
        },
    }


def setup_segment_worker(name: str) -> dict[str, Any]:
    import climate_model as cm

    spec = SEGMENTS[name]
    cdir = checkpoint_dir(name)
    sdir = segment_dir(name)
    cdir.mkdir(parents=True, exist_ok=True)
    chunk_dir(name).mkdir(parents=True, exist_ok=True)

    source_hash = sha256(SOURCE)
    spec_hash = stable_json_hash(spec)
    existing = checkpoint_path(name)
    if existing.exists():
        with existing.open("rb") as handle:
            payload = pickle.load(handle)
        if payload.get("source_sha256") != source_hash or payload.get("spec_sha256") != spec_hash:
            raise RuntimeError(
                f"Existing checkpoint for {name} does not match this source/spec. "
                "Run verify_r16_local.py --fresh once."
            )
        return {
            "segment": name,
            "resumed": True,
            "elapsed_years": float(payload["elapsed_years"]),
            "checkpoint_sha256": sha256(existing),
        }

    overrides = dict(spec["config"])
    duration = float(spec["duration"])
    record_interval = float(spec.get("record_interval_years", RECORD_INTERVAL_YEARS))
    if record_interval <= 0.0:
        raise ValueError("record_interval_years must be positive")
    overrides.update(
        duration_years=duration,
        record_every_years=record_interval,
        auto_initialize_from_1850=False,
    )
    cfg = cm.ModelConfig(**overrides)
    model = cm.ProcessClimateModel(cfg)
    apply_stage(model, spec, 0.0)
    initial_record = model.record(0.0)
    write_records_json(sdir / "initial.json", [initial_record])
    if name == "r16_control_20y":
        atomic_write_json(sdir / "reference_residual.json", reference_residual_metrics(model))

    payload = {
        "segment": name,
        "elapsed_years": 0.0,
        "model": model,
        "source_sha256": source_hash,
        "spec_sha256": spec_hash,
    }
    atomic_pickle(existing, payload)
    progress = {
        "segment": name,
        "elapsed_years": 0.0,
        "duration_years": duration,
        "source_sha256": source_hash,
        "spec_sha256": spec_hash,
        "checkpoint_sha256": sha256(existing),
        "completed": False,
        "record_count": 1,
    }
    atomic_write_json(progress_path(name), progress)
    return {"segment": name, "resumed": False, **progress}


def advance_segment_worker(name: str, requested_chunk_years: float) -> dict[str, Any]:
    spec = SEGMENTS[name]
    cp = checkpoint_path(name)
    if not cp.exists():
        raise FileNotFoundError(f"No checkpoint for {name}; setup must run first.")

    with cp.open("rb") as handle:
        payload = pickle.load(handle)
    source_hash = sha256(SOURCE)
    spec_hash = stable_json_hash(spec)
    if payload.get("source_sha256") != source_hash or payload.get("spec_sha256") != spec_hash:
        raise RuntimeError("Checkpoint/source/spec fingerprint mismatch.")

    model = payload["model"]
    elapsed = float(payload["elapsed_years"])
    duration = float(spec["duration"])
    if elapsed >= duration - EPS:
        return {"segment": name, "elapsed_years": duration, "completed": True, "advanced_years": 0.0}

    chunk_years = min(float(requested_chunk_years), MAX_CHUNK_YEARS)
    if chunk_years <= 0.0:
        raise ValueError("chunk years must be positive")
    start = elapsed
    chunk_target = min(duration, start + chunk_years)
    record_interval = float(spec.get("record_interval_years", RECORD_INTERVAL_YEARS))
    next_record = math.floor((elapsed + EPS) / record_interval + 1.0) * record_interval
    records: list[dict[str, Any]] = []

    while elapsed < chunk_target - EPS:
        apply_stage(model, spec, elapsed)
        stage_end = next_stage_boundary(spec, elapsed, chunk_target)
        dt = min(
            float(model.config.dt_years),
            chunk_target - elapsed,
            stage_end - elapsed,
            max(next_record - elapsed, EPS),
        )
        if dt <= EPS:
            if next_record <= elapsed + EPS:
                records.append(model.record(elapsed))
                next_record += record_interval
                continue
            dt = min(float(model.config.dt_years), chunk_target - elapsed)
        model.step(elapsed, dt)
        elapsed += dt
        if elapsed >= next_record - 1.0e-8:
            records.append(model.record(elapsed))
            next_record += record_interval

    # Always record the exact segment end if it was not an integer record boundary.
    if elapsed >= duration - EPS and (
        not records or abs(records[-1]["elapsed_years"] - duration) > 1.0e-7
    ):
        records.append(model.record(duration))
        elapsed = duration

    start_tag = f"{start:010.4f}".replace(".", "p")
    end_tag = f"{elapsed:010.4f}".replace(".", "p")
    chunk_path = chunk_dir(name) / f"chunk_{start_tag}_{end_tag}.json"
    write_records_json(chunk_path, records)

    new_payload = {
        "segment": name,
        "elapsed_years": elapsed,
        "model": model,
        "source_sha256": source_hash,
        "spec_sha256": spec_hash,
    }
    atomic_pickle(cp, new_payload)
    completed = elapsed >= duration - EPS
    progress = {
        "segment": name,
        "elapsed_years": float(elapsed),
        "duration_years": duration,
        "advanced_years": float(elapsed - start),
        "source_sha256": source_hash,
        "spec_sha256": spec_hash,
        "checkpoint_sha256": sha256(cp),
        "last_chunk_file": chunk_path.name,
        "completed": bool(completed),
        "record_count": len(collect_segment_records(name)),
    }
    atomic_write_json(progress_path(name), progress)
    return progress


def collect_segment_records(name: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    initial = segment_dir(name) / "initial.json"
    if initial.exists():
        records.extend(read_records_json(initial))
    for path in sorted(chunk_dir(name).glob("chunk_*.json")):
        records.extend(read_records_json(path))
    # De-duplicate by rounded elapsed year so an interrupted/replayed chunk cannot
    # create duplicate rows in final diagnostics.
    unique: dict[float, dict[str, Any]] = {}
    for row in records:
        unique[round(float(row["elapsed_years"]), 8)] = row
    return [unique[k] for k in sorted(unique)]


def write_segment_csv(name: str, records: list[dict[str, Any]]) -> Path:
    path = segment_dir(name) / "timeseries.csv"
    if not records:
        return path
    keys: list[str] = []
    seen: set[str] = set()
    for row in records:
        for key in row:
            if key not in seen:
                seen.add(key)
                keys.append(key)
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
    os.replace(tmp, path)
    return path


def col(records: list[dict[str, Any]], name: str) -> list[float]:
    values: list[float] = []
    for row in records:
        if name not in row or row[name] is None:
            continue
        try:
            value = float(row[name])
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            values.append(value)
    return values


def max_abs(records: list[dict[str, Any]], name: str) -> float:
    values = col(records, name)
    return max((abs(v) for v in values), default=float("nan"))


def trapezoid(x: list[float], y: list[float]) -> float:
    total = 0.0
    for i in range(1, min(len(x), len(y))):
        total += 0.5 * (y[i] + y[i - 1]) * (x[i] - x[i - 1])
    return total


def linear_fit(x: list[float], y: list[float]) -> tuple[float, float]:
    n = min(len(x), len(y))
    if n < 3:
        return float("nan"), float("nan")
    xx, yy = x[:n], y[:n]
    mx, my = sum(xx) / n, sum(yy) / n
    denom = sum((a - mx) ** 2 for a in xx)
    if denom <= 0.0:
        return float("nan"), float("nan")
    slope = sum((xx[i] - mx) * (yy[i] - my) for i in range(n)) / denom
    return slope, my - slope * mx


def interpolate_record(records: list[dict[str, Any]], xkey: str, ykey: str, target: float) -> float:
    pts = [(float(r[xkey]), float(r[ykey])) for r in records if r.get(xkey) is not None and r.get(ykey) is not None]
    pts.sort()
    if not pts:
        return float("nan")
    if target <= pts[0][0]:
        return pts[0][1]
    if target >= pts[-1][0]:
        return pts[-1][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= target <= x1:
            if abs(x1 - x0) < 1e-15:
                return y1
            f = (target - x0) / (x1 - x0)
            return y0 + f * (y1 - y0)
    return float("nan")


def finalize_results(static_result: dict[str, Any], segment_status: dict[str, Any]) -> dict[str, Any]:
    """Assemble complete R16 records without inventing pass thresholds before review."""
    payload: dict[str, Any] = {
        "candidate": "CLEM v2.29.28 Physics Candidate R16.1 (TEOS hotfix)",
        "verifier_revision": VERIFIER_REVISION,
        "climate_model_sha256": sha256(SOURCE),
        "mandatory_max_chunk_years": MAX_CHUNK_YEARS,
        "static": static_result,
        "segments": {},
        "all_requested_segments_completed": True,
    }
    for name in segment_status:
        status = segment_status.get(name, {})
        rows = collect_segment_records(name)
        if rows:
            write_segment_csv(name, rows)
        completed = bool(status.get("completed", False))
        payload["all_requested_segments_completed"] = payload["all_requested_segments_completed"] and completed
        last = rows[-1] if rows else None
        summary = {
            "completed": completed,
            "planned_duration_years": float(SEGMENTS[name]["duration"]),
            "record_count": len(rows),
            "source_sha256": sha256(SOURCE),
            "final_record": last,
        }
        if rows:
            for key in ("salt_conservation_error_ppm", "energy_closure_error_wm2", "amoc_sv", "fovs_sv", "greenland_ice_mass_gt", "ocean_added_freshwater_m3", "global_mean_temperature_anomaly_c", "arctic_sea_ice_area_mkm2"):
                vals = [r.get(key) for r in rows if isinstance(r.get(key), (int, float)) and math.isfinite(float(r.get(key)))]
                if vals:
                    summary[f"{key}_min"] = float(min(vals))
                    summary[f"{key}_max"] = float(max(vals))
                    summary[f"{key}_final"] = float(vals[-1])
        payload["segments"][name] = summary
    payload["interpretation"] = "R16.1 is a delta validation of the three TEOS-10 experiments that were blocked before integration in R16. The 31 completed R16 non-TEOS experiments remain the accepted comparison evidence and are not repeated."
    return payload

def worker_entry(mode: str, segment: str | None, chunk_years: float) -> None:
    try:
        if mode == "static":
            result = static_worker()
        elif mode == "setup":
            if not segment:
                raise ValueError("setup worker needs --segment")
            result = setup_segment_worker(segment)
        elif mode == "advance":
            if not segment:
                raise ValueError("advance worker needs --segment")
            result = advance_segment_worker(segment, chunk_years)
        else:
            raise ValueError(mode)
        print("__RESULT__" + strict_json_dumps({"ok": True, "result": result}), flush=True)
    except Exception as exc:
        payload = {
            "ok": False,
            "error": repr(exc),
            "traceback": traceback.format_exc(),
        }
        print("__RESULT__" + strict_json_dumps(payload), flush=True)
        raise


def run_child(args: list[str], timeout: int, log_path: Path) -> dict[str, Any]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    try:
        cp = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        log_path.write_text(cp.stdout + "\n--- STDERR ---\n" + cp.stderr, encoding="utf-8")
        result_payload = None
        for line in reversed(cp.stdout.splitlines()):
            if line.startswith("__RESULT__"):
                try:
                    result_payload = json.loads(line[len("__RESULT__"):])
                except Exception:
                    pass
                break
        return {
            "returncode": cp.returncode,
            "elapsed_seconds": time.time() - t0,
            "payload": result_payload,
            "timeout": False,
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        log_path.write_text(stdout + "\n--- TIMEOUT ---\n" + stderr, encoding="utf-8")
        return {
            "returncode": None,
            "elapsed_seconds": time.time() - t0,
            "payload": None,
            "timeout": True,
        }


def build_bundle(manifest: dict[str, Any]) -> None:
    manifest["finished_unix"] = time.time()
    atomic_write_json(OUT / "manifest.json", manifest)
    shutil.copy2(SOURCE, OUT / "climate_model.py")
    shutil.copy2(Path(__file__).resolve(), OUT / Path(__file__).name)
    for extra_name in ("amoc_density_r16.py", "prospective_validation_r16.py", "SOURCE_FINGERPRINT.json", "R16_TEOS_DELTA_PROVENANCE.json"):
        extra = ROOT / extra_name
        if extra.exists():
            shutil.copy2(extra, OUT / extra_name)
    parent_snapshot = ROOT / "provenance" / "r16-parent" / "climate_model.py"
    if parent_snapshot.exists():
        parent_out = OUT / "provenance" / "r16-parent"
        parent_out.mkdir(parents=True, exist_ok=True)
        shutil.copy2(parent_snapshot, parent_out / "climate_model.py")
    protocol = ROOT / "validation" / "prospective" / "CLEM_R16_PROSPECTIVE_PROTOCOL.json"
    if protocol.exists():
        shutil.copy2(protocol, OUT / protocol.name)
    cmd = ROOT / "RUN_PHYSICS_VERIFICATION.cmd"
    if cmd.exists():
        shutil.copy2(cmd, OUT / "RUN_PHYSICS_VERIFICATION.cmd")
    validation_cmd = ROOT / "RUN_OUT_OF_SAMPLE_VALIDATION.cmd"
    if validation_cmd.exists():
        shutil.copy2(validation_cmd, OUT / "RUN_OUT_OF_SAMPLE_VALIDATION.cmd")
    consistency_cmd = ROOT / "RUN_RELEASE_CONSISTENCY.cmd"
    if consistency_cmd.exists():
        shutil.copy2(consistency_cmd, OUT / "RUN_RELEASE_CONSISTENCY.cmd")
    for baseline_name in ("REPAIR_R11_VERIFIED_BASELINE_RESULTS.json", "REPAIR_R11_VERIFIED_BASELINE_MANIFEST.json"):
        baseline_path = ROOT / baseline_name
        if baseline_path.exists():
            shutil.copy2(baseline_path, OUT / baseline_name)
    for release_name in ("REPAIR_R13_DYNAMICS_EQUIVALENCE.json", "REPAIR_R12_RESULTS_REVIEW.md", "PHYSICS_REPAIR_R13.md"):
        release_path = ROOT / release_name
        if not release_path.exists():
            release_path = ROOT.parent.parent / release_name
        if release_path.exists():
            shutil.copy2(release_path, OUT / release_name)

    if BUNDLE.exists():
        BUNDLE.unlink()
    with zipfile.ZipFile(BUNDLE, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in OUT.rglob("*"):
            if not path.is_file():
                continue
            # Checkpoint pickles are deliberately excluded: they can be large
            # and are needed only for local resume. Progress + hashes are kept.
            if CHECKPOINTS in path.parents and path.suffix == ".pkl":
                continue
            archive.write(path, path.relative_to(ROOT))


def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            cp = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True, timeout=10,
            )
            return str(pid) in cp.stdout and "No tasks are running" not in cp.stdout
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def acquire_run_lock() -> None:
    if RUN_LOCK.exists():
        try:
            old = json.loads(RUN_LOCK.read_text(encoding="utf-8"))
            old_pid = int(old.get("pid", -1))
        except Exception:
            old_pid = -1
        if old_pid != os.getpid() and _pid_is_running(old_pid):
            raise SystemExit(
                f"Another R16 validation process is still active (PID {old_pid}). "
                "Stop it before starting a second validation session."
            )
        RUN_LOCK.unlink(missing_ok=True)
    atomic_write_json(RUN_LOCK, {"pid": os.getpid(), "started_unix": time.time(), "runner_sha256": sha256(Path(__file__).resolve())})


def release_run_lock() -> None:
    try:
        if RUN_LOCK.exists():
            payload = json.loads(RUN_LOCK.read_text(encoding="utf-8"))
            if int(payload.get("pid", -1)) == os.getpid():
                RUN_LOCK.unlink()
    except Exception:
        pass


def parent_main(args: argparse.Namespace) -> None:
    requested_chunk = min(float(args.chunk_years), MAX_CHUNK_YEARS)
    if requested_chunk <= 0.0:
        raise SystemExit("--chunk-years must be > 0")
    if float(args.chunk_years) > MAX_CHUNK_YEARS + EPS:
        print(f"Requested chunk reduced to mandatory maximum {MAX_CHUNK_YEARS:g} model years.", flush=True)

    if args.fresh and OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)
    CHECKPOINTS.mkdir(parents=True, exist_ok=True)

    source_hash = sha256(SOURCE)
    runner_hash = sha256(Path(__file__).resolve())
    baseline_manifest_info: dict[str, Any] | None = None
    delta_provenance_info: dict[str, Any] | None = None
    if args.validation_only:
        delta_provenance_info = validate_r16_teos_delta_provenance(source_hash)
        print(
            "R16.2 TEOS delta provenance accepted: exact R16 parent + exact R16.1 source; "
            "all top-level AST symbols except validate_initial_amoc_density_margin are identical.",
            flush=True,
        )
    manifest_path = OUT / "manifest.json"
    previous_runner_sha256: str | None = None
    if manifest_path.exists() and not args.fresh:
        try:
            old = json.loads(manifest_path.read_text(encoding="utf-8"))
            old_source = old.get("climate_model_sha256")
            old_runner = old.get("runner_sha256")
            if old_source and old_source != source_hash:
                raise SystemExit("Existing verification results use a different climate_model.py. Re-run with --fresh.")
            # A verifier-only revision may safely reuse checkpoints because each
            # checkpoint independently fingerprints climate_model.py and the
            # segment specification. Record the prior runner for provenance
            # instead of blocking resume solely on the runner hash.
            previous_runner_sha256 = old_runner if old_runner and old_runner != runner_hash else None
        except json.JSONDecodeError:
            raise SystemExit("Existing manifest is invalid. Re-run with --fresh.")

    manifest: dict[str, Any] = {
        "started_unix": time.time(),
        "verifier_revision": VERIFIER_REVISION,
        "previous_runner_sha256": previous_runner_sha256,
        "python": sys.version,
        "platform": platform.platform(),
        "climate_model_sha256": source_hash,
        "runner_sha256": runner_hash,
        "mandatory_max_chunk_years": MAX_CHUNK_YEARS,
        "requested_chunk_years": requested_chunk,
        "chunk_timeout_seconds": int(args.timeout),
        "setup_timeout_seconds": int(args.setup_timeout),
        "verified_baseline_climate_model_sha256": (baseline_manifest_info or {}).get("climate_model_sha256"),
        "verified_baseline_verifier_revision": (baseline_manifest_info or {}).get("verifier_revision"),
        "r16_teos_delta_provenance": delta_provenance_info,
        "segments": {},
        "static": {},
    }

    print("CLEM R16.2 TEOS delta verification", flush=True)
    print(f"Source SHA-256: {source_hash}", flush=True)
    print(f"Every integration child advances <= {requested_chunk:g} model years.", flush=True)
    print("Re-run this same command to resume after interruption. Use --fresh only to restart from zero.\n", flush=True)

    static_log = OUT / "static" / "console.txt"
    print("[static] Control thermohaline state, humidity phase branch, source invariants", flush=True)
    static_run = run_child(["--worker-mode", "static"], int(args.setup_timeout), static_log)
    manifest["static"] = static_run
    static_result: dict[str, Any] = {}
    if static_run.get("payload", {}).get("ok"):
        static_result = static_run["payload"]["result"]
        atomic_write_json(OUT / "static" / "results.json", static_result)
        control = static_result["control"]
        print(
            f"  control ΔT={control['north_minus_south_temperature_c']:.3f} K, "
            f"thermal={control['thermal_density_driver']:+.6e}, "
            f"haline={control['haline_density_driver']:+.6e}, "
            f"ratio={control['density_ratio']:.4f}",
            flush=True,
        )
    else:
        print("  FAILED static checks; see physics_verification_results/static/console.txt", flush=True)

    segment_status: dict[str, Any] = {}
    names = list(VALIDATION_ONLY_SEGMENTS) if args.validation_only else list(SEGMENTS)
    manifest["run_mode"] = "r16_2_teos_delta" if args.validation_only else "r16_2_full_candidate_suite"
    manifest["selected_segments"] = names
    for index, name in enumerate(names, 1):
        spec = SEGMENTS[name]
        duration = float(spec["duration"])
        print(f"\n[{index}/{len(names)}] {name} ({duration:g} model years)", flush=True)
        setup_log = segment_dir(name) / "setup_console.txt"
        print("  setup/checkpoint validation...", flush=True)
        setup = run_child(
            ["--worker-mode", "setup", "--segment", name],
            int(args.setup_timeout),
            setup_log,
        )
        status: dict[str, Any] = {"setup": setup, "chunks": [], "completed": False}
        segment_status[name] = status
        if setup.get("returncode") != 0 or not setup.get("payload", {}).get("ok"):
            print("  SETUP FAILED; continuing to the next experiment.", flush=True)
            manifest["segments"][name] = status
            atomic_write_json(manifest_path, manifest)
            continue

        progress = setup["payload"]["result"]
        elapsed = float(progress.get("elapsed_years", 0.0))
        if elapsed > 0.0:
            print(f"  resumed at {elapsed:.1f}/{duration:g} years", flush=True)

        chunk_number = 0
        while elapsed < duration - EPS:
            chunk_number += 1
            target = min(duration, elapsed + requested_chunk)
            print(f"  chunk {chunk_number}: {elapsed:.1f} -> {target:.1f} y", flush=True)
            log = segment_dir(name) / "logs" / f"chunk_{elapsed:010.4f}.txt"
            run = run_child(
                [
                    "--worker-mode", "advance",
                    "--segment", name,
                    "--chunk-years", str(requested_chunk),
                ],
                int(args.timeout),
                log,
            )
            status["chunks"].append(run)
            if run.get("timeout"):
                print(f"  TIMEOUT after {args.timeout}s. Previous checkpoint is intact; rerun to resume.", flush=True)
                status["timeout"] = True
                break
            if run.get("returncode") != 0 or not run.get("payload", {}).get("ok"):
                print("  CHUNK FAILED. Previous checkpoint is intact; see chunk log.", flush=True)
                status["error"] = True
                break
            progress = run["payload"]["result"]
            new_elapsed = float(progress["elapsed_years"])
            if new_elapsed <= elapsed + EPS:
                print("  ERROR: worker made no progress; stopping this segment.", flush=True)
                status["error"] = True
                break
            elapsed = new_elapsed
            print(
                f"    committed {elapsed:.1f}/{duration:g} y; "
                f"checkpoint {progress['checkpoint_sha256'][:12]}...",
                flush=True,
            )
            status["elapsed_years"] = elapsed
            status["completed"] = bool(progress.get("completed", False))
            manifest["segments"][name] = status
            atomic_write_json(manifest_path, manifest)

        if elapsed >= duration - EPS:
            status["completed"] = True
            print("  segment complete", flush=True)
        manifest["segments"][name] = status
        atomic_write_json(manifest_path, manifest)

    print("\nFinalizing diagnostics and ZIP...", flush=True)
    try:
        all_results = finalize_results(static_result, segment_status)
        atomic_write_json(OUT / "results.json", all_results)
        manifest["results_file"] = "physics_verification_results/results.json"
    except Exception as exc:
        manifest["finalize_error"] = repr(exc)
        atomic_write_text(OUT / "finalize_traceback.txt", traceback.format_exc())
        print(f"Final diagnostics encountered an error: {exc!r}", flush=True)

    manifest["all_segments_completed"] = all(
        bool(segment_status.get(name, {}).get("completed")) for name in names
    )
    build_bundle(manifest)
    print(f"\nDONE: {BUNDLE}", flush=True)
    print("Upload CLEM_v2.29.28_R16_2_TEOS_validation_results.zip back to ChatGPT.", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="CLEM R16.1 TEOS-hotfix verification with <=5-year restartable chunks")
    parser.add_argument("--fresh", action="store_true", help="delete old verification checkpoints/results and restart from zero")
    parser.add_argument("--chunk-years", type=float, default=MAX_CHUNK_YEARS, help="model years per child process; values above 5 are forced down to 5")
    parser.add_argument("--timeout", type=int, default=DEFAULT_CHUNK_TIMEOUT_SECONDS, help="wall-clock timeout per <=5-year integration child")
    parser.add_argument("--setup-timeout", type=int, default=DEFAULT_SETUP_TIMEOUT_SECONDS, help="wall-clock timeout for model initialization/checkpoint setup")
    parser.add_argument("--validation-only", action="store_true", help="run only the three R16.1 TEOS delta segments")
    parser.add_argument("--worker-mode", choices=["static", "setup", "advance"], help=argparse.SUPPRESS)
    parser.add_argument("--segment", choices=sorted(SEGMENTS), help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.worker_mode:
        worker_entry(args.worker_mode, args.segment, min(args.chunk_years, MAX_CHUNK_YEARS))
    else:
        acquire_run_lock()
        try:
            parent_main(args)
        finally:
            release_run_lock()


if __name__ == "__main__":
    main()
