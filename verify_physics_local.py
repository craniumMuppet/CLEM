#!/usr/bin/env python3
"""CLEM physics-repair verification runner.

Run on the user's computer from this directory:

    python verify_physics_local.py

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
OUT = ROOT / "physics_verification_results"
CHECKPOINTS = OUT / "_checkpoints"
BUNDLE = ROOT / "physics_verification_bundle.zip"
MAX_CHUNK_YEARS = 5.0
DEFAULT_CHUNK_TIMEOUT_SECONDS = 300
DEFAULT_SETUP_TIMEOUT_SECONDS = 300
RECORD_INTERVAL_YEARS = 1.0
EPS = 1.0e-9
VERIFIER_REVISION = "2026-08-30-repair-r13-release-consistency"

# Every expensive model experiment is represented here. No segment is advanced
# by more than MAX_CHUNK_YEARS in a child command.
SEGMENTS: dict[str, dict[str, Any]] = {
    "control_40y": {
        "duration": 40.0,
        "config": {
            "resolution_deg": 10.0,
            "scenario": "constant",
            "dt_years": 0.05,
            "seasonal_arctic_enabled": True,
        },
    },
    "dt_step2x_0p10": {
        "duration": 40.0,
        "config": {
            "resolution_deg": 10.0,
            "scenario": "step_2x",
            "dt_years": 0.10,
            "seasonal_arctic_enabled": True,
        },
    },
    "dt_step2x_0p05": {
        "duration": 40.0,
        "config": {
            "resolution_deg": 10.0,
            "scenario": "step_2x",
            "dt_years": 0.05,
            "seasonal_arctic_enabled": True,
        },
    },
    "dt_step2x_0p025": {
        "duration": 40.0,
        "config": {
            "resolution_deg": 10.0,
            "scenario": "step_2x",
            "dt_years": 0.025,
            "seasonal_arctic_enabled": True,
        },
    },
    "energy_step2x_100y": {
        "duration": 100.0,
        # Energy closure is sampled at the model timestep instead of annually;
        # this removes endpoint-quadrature error from the verification metric.
        "record_interval_years": 0.05,
        "config": {
            "resolution_deg": 10.0,
            "scenario": "step_2x",
            "dt_years": 0.05,
            "seasonal_arctic_enabled": True,
        },
    },
    "hosing_0p5_180y": {
        "duration": 180.0,
        "config": {
            "resolution_deg": 10.0,
            "scenario": "constant",
            "dt_years": 0.05,
            "seasonal_arctic_enabled": True,
            "freshwater_hosing_sv": 0.50,
            "freshwater_start_fraction": 0.0,
            "freshwater_ramp_years": 1.0,
        },
    },
    "thermal_only_step2x_150y": {
        "duration": 150.0,
        "config": {
            "resolution_deg": 10.0,
            "scenario": "step_2x",
            "dt_years": 0.05,
            "seasonal_arctic_enabled": True,
            # Isolate the temperature/density pathway. Arctic thermodynamics
            # remain active for energy/albedo, but *all* freshwater routes to
            # the AMOC boxes are disabled, including sea-ice brine/export.
            "warming_freshwater_sv_per_k": 0.0,
            "hydrological_freshwater_sv_per_k": 0.0,
            "greenland_freshwater_sv_per_k": 0.0,
            "greenland_surface_mass_balance_enabled": False,
            "arctic_sea_ice_salinity_coupling_enabled": False,
            "arctic_sea_ice_storage_salinity_coupling_enabled": False,
            "arctic_sea_ice_export_salinity_coupling_enabled": False,
        },
    },
    "thermal_plus_ice_storage_step2x_150y": {
        "duration": 150.0,
        "config": {
            "resolution_deg": 10.0,
            "scenario": "step_2x",
            "dt_years": 0.05,
            "seasonal_arctic_enabled": True,
            "warming_freshwater_sv_per_k": 0.0,
            "hydrological_freshwater_sv_per_k": 0.0,
            "greenland_freshwater_sv_per_k": 0.0,
            "greenland_surface_mass_balance_enabled": False,
            "arctic_sea_ice_salinity_coupling_enabled": True,
            "arctic_sea_ice_storage_salinity_coupling_enabled": True,
            "arctic_sea_ice_export_salinity_coupling_enabled": False,
        },
    },
    "thermal_plus_ice_export_step2x_150y": {
        "duration": 150.0,
        "config": {
            "resolution_deg": 10.0,
            "scenario": "step_2x",
            "dt_years": 0.05,
            "seasonal_arctic_enabled": True,
            "warming_freshwater_sv_per_k": 0.0,
            "hydrological_freshwater_sv_per_k": 0.0,
            "greenland_freshwater_sv_per_k": 0.0,
            "greenland_surface_mass_balance_enabled": False,
            "arctic_sea_ice_salinity_coupling_enabled": True,
            "arctic_sea_ice_storage_salinity_coupling_enabled": False,
            "arctic_sea_ice_export_salinity_coupling_enabled": True,
        },
    },
    "thermal_plus_seaice_step2x_150y": {
        "duration": 150.0,
        "config": {
            "resolution_deg": 10.0,
            "scenario": "step_2x",
            "dt_years": 0.05,
            "seasonal_arctic_enabled": True,
            # Same forcing as thermal_only, but retain only the physically
            # normalized sea-ice brine/export salinity pathway. The difference
            # between these two segments is the cryosphere freshwater effect.
            "warming_freshwater_sv_per_k": 0.0,
            "hydrological_freshwater_sv_per_k": 0.0,
            "greenland_freshwater_sv_per_k": 0.0,
            "greenland_surface_mass_balance_enabled": False,
            "arctic_sea_ice_salinity_coupling_enabled": True,
            "arctic_sea_ice_storage_salinity_coupling_enabled": True,
            "arctic_sea_ice_export_salinity_coupling_enabled": True,
        },
    },
    "ecs_step2x_1600y": {
        "duration": 1600.0,
        # Do not sample seasonal-Arctic TOA at one fixed calendar phase. Five
        # evenly spaced records per year remove the annual alias while keeping
        # the long experiment reasonably small.
        "record_interval_years": 0.2,
        "config": {
            "resolution_deg": 10.0,
            "scenario": "step_2x",
            "dt_years": 0.05,
            "seasonal_arctic_enabled": True,
        },
    },
    "tcr_one_percent_80y": {
        "duration": 80.0,
        "record_interval_years": 0.5,
        "config": {
            "resolution_deg": 10.0,
            "scenario": "one_percent",
            "dt_years": 0.05,
            "seasonal_arctic_enabled": True,
            "one_percent_cap_ppm": None,
        },
    },
    "greenland_warm_200y": {
        "duration": 200.0,
        "config": {
            "resolution_deg": 10.0,
            "scenario": "step_2x",
            "dt_years": 0.05,
            "additional_forcing_wm2": 4.0,
            "seasonal_arctic_enabled": True,
        },
    },
    "recovery_0p4_1050y": {
        "duration": 1050.0,
        "config": {
            "resolution_deg": 10.0,
            "scenario": "constant",
            "dt_years": 0.05,
            "seasonal_arctic_enabled": False,
            "freshwater_hosing_sv": 0.40,
            "freshwater_start_fraction": 0.0,
            "freshwater_ramp_years": 1.0,
        },
        "stages": [
            {"start": 0.0, "end": 250.0, "overrides": {"freshwater_hosing_sv": 0.40}},
            {"start": 250.0, "end": 1050.0, "overrides": {"freshwater_hosing_sv": 0.0}},
        ],
    },
    # Repair R12 validation-only experiments. None of these thresholds or forcing
    # amplitudes were used to tune the Repair R11 physics candidate. SSP2-4.5 is
    # integrated continuously from 1850 so its historical and future response
    # are evaluated from one prognostic trajectory.
    "ssp245_1850_2100_10deg": {
        "duration": 250.0,
        "record_interval_years": 0.25,
        "config": {
            "start_year": 1850.0,
            "resolution_deg": 10.0,
            "scenario": "ssp245",
            "dt_years": 0.05,
            "seasonal_arctic_enabled": True,
            "auto_initialize_from_1850": False,
        },
    },
    "ssp245_1850_2100_5deg": {
        "duration": 250.0,
        "record_interval_years": 0.25,
        "config": {
            "start_year": 1850.0,
            "resolution_deg": 5.0,
            "scenario": "ssp245",
            "dt_years": 0.05,
            "seasonal_arctic_enabled": True,
            "auto_initialize_from_1850": False,
        },
    },
    "hosing_0p1_100y": {
        "duration": 100.0,
        "config": {
            "resolution_deg": 10.0,
            "scenario": "constant",
            "dt_years": 0.05,
            "seasonal_arctic_enabled": True,
            "freshwater_hosing_sv": 0.10,
            "freshwater_start_fraction": 0.0,
            "freshwater_ramp_years": 1.0,
        },
    },
    "hosing_0p2_100y": {
        "duration": 100.0,
        "config": {
            "resolution_deg": 10.0,
            "scenario": "constant",
            "dt_years": 0.05,
            "seasonal_arctic_enabled": True,
            "freshwater_hosing_sv": 0.20,
            "freshwater_start_fraction": 0.0,
            "freshwater_ramp_years": 1.0,
        },
    },
    "hosing_0p3_100y": {
        "duration": 100.0,
        "config": {
            "resolution_deg": 10.0,
            "scenario": "constant",
            "dt_years": 0.05,
            "seasonal_arctic_enabled": True,
            "freshwater_hosing_sv": 0.30,
            "freshwater_start_fraction": 0.0,
            "freshwater_ramp_years": 1.0,
        },
    },
}

VALIDATION_ONLY_SEGMENTS = [
    "ssp245_1850_2100_10deg",
    "ssp245_1850_2100_5deg",
    "hosing_0p1_100y",
    "hosing_0p2_100y",
    "hosing_0p3_100y",
]



def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def core_ast_sha256(path: Path) -> str:
    """Hash dynamics/config code while excluding release-only identity surfaces.

    ``build_parser`` is excluded because Repair R13 changed CLI defaults without
    changing the validated dynamics. ``MODEL_NAME`` is excluded because the
    public model name is metadata only and cannot affect numerical integration.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    filtered = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "build_parser":
            continue
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == "MODEL_NAME" for target in node.targets):
                continue
        if isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "MODEL_NAME":
                continue
        filtered.append(node)
    tree.body = filtered
    payload = ast.dump(tree, annotate_fields=True, include_attributes=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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
            "ecs_record_interval_years": float(SEGMENTS["ecs_step2x_1600y"].get("record_interval_years", RECORD_INTERVAL_YEARS)),
            "pass_ecs_record_interval_anti_alias": bool(float(SEGMENTS["ecs_step2x_1600y"].get("record_interval_years", 1.0)) <= 0.2 + 1.0e-12),
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
                "Run verify_physics_local.py --fresh once."
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
    if name == "control_40y":
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
    results: dict[str, Any] = {"static": static_result, "segments": {}, "tests": {}}
    frames: dict[str, list[dict[str, Any]]] = {}
    for name in SEGMENTS:
        records = collect_segment_records(name)
        if records:
            write_segment_csv(name, records)
        status = segment_status.get(name, {})
        completed = bool(status.get("completed", False))
        planned = float(SEGMENTS[name]["duration"])
        last_elapsed = float(records[-1]["elapsed_years"]) if records else None
        complete_by_record = bool(
            completed
            and last_elapsed is not None
            and last_elapsed >= planned - EPS
        )
        # Never score a partially advanced experiment as a physics pass. Keep
        # its records in the bundle for debugging, but withhold it from all
        # numerical test calculations until the full planned duration exists.
        frames[name] = records if complete_by_record else []
        results["segments"][name] = {
            "records": len(records),
            "last_elapsed_years": last_elapsed,
            "planned_duration_years": planned,
            "completed": complete_by_record,
            "evaluated": complete_by_record,
            "status": status,
        }

    # Control salt conservation and control drift.
    control = frames["control_40y"]
    if control:
        salt = max_abs(control, "salt_conservation_error_ppm")
        pre_salt = max_abs(control, "pre_projection_salt_conservation_error_ppm")
        final_gmst = float(control[-1]["global_surface_warming_c"])
        results["tests"]["control_conservation"] = {
            "max_salt_error_ppm": salt,
            "max_pre_projection_salt_error_ppm": pre_salt,
            "final_gmst_c": final_gmst,
            "pass_salt": bool(salt < 1.0e-6 and pre_salt < 1.0e-6),
            # Recorded only as a regression property, not independent validation.
            "control_drift_regression_only": bool(abs(final_gmst) < 0.05),
        }

    residual_path = segment_dir("control_40y") / "reference_residual.json"
    if residual_path.exists():
        try:
            results["tests"]["reference_residual"] = json.loads(residual_path.read_text(encoding="utf-8"))
        except Exception as exc:
            results["tests"]["reference_residual"] = {"error": repr(exc), "pass_heat_correction_below_half_percent_of_2x_forcing": False}

    # Seasonal-Arctic timestep convergence.
    dt_rows = []
    for name, dt in [("dt_step2x_0p10", 0.10), ("dt_step2x_0p05", 0.05), ("dt_step2x_0p025", 0.025)]:
        r = frames[name]
        if r:
            dt_rows.append({"dt_years": dt, "gmst_c": float(r[-1]["global_surface_warming_c"]), "amoc_sv": float(r[-1]["amoc_sv"])})
    if len(dt_rows) == 3:
        dg = abs(dt_rows[2]["gmst_c"] - dt_rows[1]["gmst_c"])
        da = abs(dt_rows[2]["amoc_sv"] - dt_rows[1]["amoc_sv"])
        results["tests"]["seasonal_arctic_dt_convergence"] = {
            "runs": dt_rows,
            "fine_pair_gmst_delta_c": dg,
            "fine_pair_amoc_delta_sv": da,
            "pass": bool(dg < 0.03 and da < 0.15),
        }

    # Energy closure under a forced trajectory.
    energy = frames["energy_step2x_100y"]
    if len(energy) >= 2:
        years = col(energy, "elapsed_years")
        toa = col(energy, "toa_imbalance_wm2")
        bulk_toa = col(energy, "bulk_radiative_toa_imbalance_wm2")
        arctic_external = col(energy, "arctic_external_toa_anomaly_wm2")
        arctic_longwave = col(energy, "arctic_external_longwave_loss_anomaly_global_wm2")
        heat = col(energy, "total_resolved_heat_content_anomaly_zj")
        # W m-2 * Earth area * seconds/year -> ZJ.
        earth_area_m2 = 4.0 * math.pi * (6_371_000.0 ** 2)
        seconds_per_year = 365.2425 * 24.0 * 3600.0
        conversion = earth_area_m2 * seconds_per_year / 1.0e21
        integrated_toa_zj = trapezoid(years, toa) * conversion
        integrated_bulk_toa_zj = trapezoid(years, bulk_toa) * conversion
        integrated_arctic_external_zj = trapezoid(years, arctic_external) * conversion
        integrated_arctic_longwave_loss_anomaly_zj = trapezoid(years, arctic_longwave) * conversion
        delta_heat_zj = heat[-1] - heat[0]
        residual_zj = integrated_toa_zj - delta_heat_zj
        relative = abs(residual_zj) / max(abs(integrated_toa_zj), abs(delta_heat_zj), 1.0e-9)
        results["tests"]["energy_conservation"] = {
            "integrated_toa_zj": integrated_toa_zj,
            "integrated_bulk_radiative_toa_zj": integrated_bulk_toa_zj,
            "integrated_arctic_external_zj": integrated_arctic_external_zj,
            "integrated_arctic_longwave_loss_anomaly_zj": integrated_arctic_longwave_loss_anomaly_zj,
            "resolved_heat_content_change_zj": delta_heat_zj,
            "residual_zj": residual_zj,
            "relative_residual": relative,
            "pass_target_0p5_percent": bool(relative < 0.005),
            "pass": bool(relative < 0.01),
        }

    # Hosing collapse and North Atlantic cold blob.
    hosing = frames["hosing_0p5_180y"]
    if hosing:
        amoc = col(hosing, "amoc_sv")
        nat = col(hosing, "north_atlantic_warming_c")
        min_amoc = min(amoc)
        min_nat = min(nat)
        min_idx = amoc.index(min_amoc)
        initial = hosing[0]
        at_min = hosing[min_idx]
        results["tests"]["hosing_cold_blob"] = {
            "minimum_amoc_sv": min_amoc,
            "minimum_north_atlantic_anomaly_c": min_nat,
            "final_amoc_sv": float(hosing[-1]["amoc_sv"]),
            "final_north_atlantic_anomaly_c": float(hosing[-1]["north_atlantic_warming_c"]),
            "elapsed_years_at_minimum_amoc": float(at_min["elapsed_years"]),
            "initial_fovs_sv": float(initial.get("fovs_sv", float("nan"))),
            "fovs_at_minimum_amoc_sv": float(at_min.get("fovs_sv", float("nan"))),
            "north_salinity_change_at_minimum_psu": float(at_min["north_salinity_psu"] - initial["north_salinity_psu"]),
            "southern_salinity_change_at_minimum_psu": float(at_min["southern_salinity_psu"] - initial["southern_salinity_psu"]),
            "sau_salinity_change_at_minimum_psu": float(at_min["south_atlantic_upper_salinity_psu"] - initial["south_atlantic_upper_salinity_psu"]),
            "deep_salinity_change_at_minimum_psu": float(at_min["deep_salinity_psu"] - initial["deep_salinity_psu"]),
            "sau_minus_deep_salinity_at_minimum_psu": float(at_min["south_atlantic_upper_salinity_psu"] - at_min["deep_salinity_psu"]),
            "north_minus_southern_salinity_at_minimum_psu": float(at_min["north_minus_southern_salinity_psu"]),
            "density_ratio_at_minimum_amoc": float(at_min["amoc_density_driver_ratio"]),
            "pass_collapse": bool(min_amoc < 3.0),
            "pass_cold_blob_lower_bound": bool(min_nat <= -3.0),
            "pass_cold_blob_target_range": bool(-8.0 <= min_nat <= -3.0),
            "pass_cold_blob_not_extreme": bool(min_nat >= -10.0),
            "pass": bool(min_amoc < 3.0 and -8.0 <= min_nat <= -3.0),
        }

    # Pure thermal forcing: all salinity freshwater pathways disabled.
    thermal = frames["thermal_only_step2x_150y"]
    if thermal:
        initial_amoc = float(thermal[0]["amoc_sv"])
        final_amoc = float(thermal[-1]["amoc_sv"])
        weakening = 100.0 * (initial_amoc - final_amoc) / max(abs(initial_amoc), 1.0e-9)
        feedback_tail = [r for r in thermal if float(r["elapsed_years"]) >= 100.0 - EPS]
        mean_warming = (
            sum(float(r["global_surface_warming_c"]) for r in feedback_tail) / len(feedback_tail)
            if feedback_tail else float("nan")
        )
        def feedback_ratio(key: str) -> float:
            if not feedback_tail or not math.isfinite(mean_warming) or abs(mean_warming) < 1.0e-12:
                return float("nan")
            return sum(float(r[key]) for r in feedback_tail) / len(feedback_tail) / mean_warming
        water_vapor_feedback = feedback_ratio("water_vapor_flux_wm2")
        lapse_feedback = feedback_ratio("lapse_rate_flux_wm2")
        polar_feedback = feedback_ratio("polar_inversion_flux_wm2")
        combined_wv_lr = water_vapor_feedback + lapse_feedback + polar_feedback
        results["tests"]["thermal_only_amoc"] = {
            "initial_amoc_sv": initial_amoc,
            "final_amoc_sv": final_amoc,
            "final_gmst_c": float(thermal[-1]["global_surface_warming_c"]),
            "weakening_percent": weakening,
            "sea_ice_salinity_coupling_enabled": bool(float(thermal[-1].get("arctic_sea_ice_salinity_coupling_enabled", 0.0)) > 0.5),
            "pass_no_sea_ice_freshwater_contamination": bool(
                abs(float(thermal[-1].get("atlantic_sea_ice_export_freshwater_sv", 0.0))) < 1.0e-12
                or float(thermal[-1].get("arctic_sea_ice_salinity_coupling_enabled", 0.0)) < 0.5
            ),
            "water_vapor_feedback_wm2_k_tail": water_vapor_feedback,
            "resolved_lapse_rate_feedback_wm2_k_tail": lapse_feedback,
            "polar_inversion_closure_wm2_k_tail": polar_feedback,
            "combined_lapse_plus_polar_wm2_k_tail": lapse_feedback + polar_feedback,
            "combined_water_vapor_plus_lapse_wm2_k_tail": combined_wv_lr,
            "pass_standalone_water_vapor_plausible": bool(1.40 <= water_vapor_feedback <= 2.10),
            "pass_wv_plus_lr_ar6_very_likely": bool(1.10 <= combined_wv_lr <= 1.50),
            "pass_wv_plus_lr_ar6_likely": bool(1.20 <= combined_wv_lr <= 1.40),
            "pass_material_thermal_response": bool(weakening >= 15.0),
            "pass_not_overcollapsed": bool(final_amoc > 3.0),
        }

    pure = results["tests"].get("thermal_only_amoc", {})
    pure_weakening = float(pure.get("weakening_percent", float("nan")))

    def summarize_ice_mechanism(segment_name: str, test_name: str) -> None:
        rows = frames[segment_name]
        if not rows:
            return
        initial_amoc_ice = float(rows[0]["amoc_sv"])
        final_amoc_ice = float(rows[-1]["amoc_sv"])
        weakening_ice = 100.0 * (initial_amoc_ice - final_amoc_ice) / max(abs(initial_amoc_ice), 1.0e-9)
        raw_export_signed = [float(r.get("atlantic_sea_ice_export_freshwater_raw_sv", 0.0)) for r in rows]
        scaled_export_signed = [float(r.get("atlantic_sea_ice_export_freshwater_sv", 0.0)) for r in rows]
        storage_signed = [float(r.get("atlantic_sea_ice_storage_freshwater_sv", 0.0)) for r in rows]
        raw_export = [abs(v) for v in raw_export_signed]
        scaled_export = [abs(v) for v in scaled_export_signed]
        entry = {
            "initial_amoc_sv": initial_amoc_ice,
            "final_amoc_sv": final_amoc_ice,
            "weakening_percent": weakening_ice,
            "pure_thermal_weakening_percent": pure_weakening,
            "increment_vs_pure_thermal_percentage_points": (weakening_ice - pure_weakening) if math.isfinite(pure_weakening) else float("nan"),
            "storage_coupling_enabled": bool(float(rows[-1].get("arctic_sea_ice_storage_salinity_coupling_enabled", 0.0)) > 0.5),
            "export_coupling_enabled": bool(float(rows[-1].get("arctic_sea_ice_export_salinity_coupling_enabled", 0.0)) > 0.5),
            "final_north_salinity_psu": float(rows[-1]["north_salinity_psu"]),
            "final_fovs_sv": float(rows[-1]["fovs_sv"]),
            "mean_signed_ice_storage_freshwater_sv": sum(storage_signed) / len(storage_signed),
            "mean_signed_scaled_ice_export_freshwater_sv": sum(scaled_export_signed) / len(scaled_export_signed),
            "minimum_signed_scaled_ice_export_freshwater_sv": min(scaled_export_signed, default=0.0),
            "maximum_signed_scaled_ice_export_freshwater_sv": max(scaled_export_signed, default=0.0),
            "maximum_abs_raw_ice_export_freshwater_sv": max(raw_export) if raw_export else 0.0,
            "maximum_abs_scaled_ice_export_freshwater_sv": max(scaled_export) if scaled_export else 0.0,
            "reference_export_target_sv": float(rows[-1].get("arctic_ice_export_freshwater_reference_sv", float("nan"))),
            "raw_reference_export_sv": float(rows[-1].get("arctic_raw_reference_ice_export_freshwater_sv", float("nan"))),
            "salinity_scale": float(rows[-1].get("arctic_ice_export_freshwater_salinity_scale", float("nan"))),
            "pass_export_normalized_down": bool(
                max(scaled_export, default=0.0) <= max(raw_export, default=0.0) + 1.0e-12
                and float(rows[-1].get("arctic_ice_export_freshwater_salinity_scale", 1.0)) < 1.0
            ),
        }
        results["tests"][test_name] = entry

    summarize_ice_mechanism("thermal_plus_ice_storage_step2x_150y", "thermal_plus_ice_storage_amoc")
    summarize_ice_mechanism("thermal_plus_ice_export_step2x_150y", "thermal_plus_ice_export_amoc")
    summarize_ice_mechanism("thermal_plus_seaice_step2x_150y", "thermal_plus_seaice_amoc")

    # Equilibrium climate sensitivity and transient climate response.
    ecs = frames["ecs_step2x_1600y"]
    if ecs:
        equilibrium_end = float(SEGMENTS["ecs_step2x_1600y"]["duration"])
        tail_start = equilibrium_end - 100.0
        trend_start = equilibrium_end - 200.0
        tail = [r for r in ecs if float(r["elapsed_years"]) >= tail_start - EPS]
        ecs_c = sum(float(r["global_surface_warming_c"]) for r in tail) / len(tail)
        # The 0.2-y record interval samples five phases per year, preventing the
        # seasonal Arctic external-flux alias that contaminated the v2.7-v2.9
        # once-per-year equilibrium TOA diagnostic.
        tail_toa = sum(float(r["toa_imbalance_wm2"]) for r in tail) / len(tail)
        trend_tail = [r for r in ecs if float(r["elapsed_years"]) >= trend_start - EPS]
        trend_years = [float(r["elapsed_years"]) for r in trend_tail]
        trend_gmst = [float(r["global_surface_warming_c"]) for r in trend_tail]
        trend_amoc = [float(r["amoc_sv"]) for r in trend_tail]
        gmst_slope_y, _ = linear_fit(trend_years, trend_gmst)
        amoc_slope_y, _ = linear_fit(trend_years, trend_amoc)
        gmst_trend_century = 100.0 * gmst_slope_y
        amoc_trend_century = 100.0 * amoc_slope_y
        # Independent late-time energy check: the slope of resolved heat content
        # must agree with the phase-averaged external TOA flux.
        tail_years = [float(r["elapsed_years"]) for r in tail]
        tail_heat_zj = [float(r["total_resolved_heat_content_anomaly_zj"]) for r in tail]
        heat_slope_zj_per_year, _ = linear_fit(tail_years, tail_heat_zj)
        earth_area_m2 = 4.0 * math.pi * (6_371_000.0 ** 2)
        seconds_per_year = 365.2425 * 24.0 * 3600.0
        zj_per_year_per_wm2 = earth_area_m2 * seconds_per_year / 1.0e21
        heat_tendency_wm2 = heat_slope_zj_per_year / zj_per_year_per_wm2
        late_energy_residual_wm2 = tail_toa - heat_tendency_wm2
        def eq_feedback(key: str) -> float:
            return sum(float(r[key]) for r in tail) / len(tail) / max(abs(ecs_c), 1.0e-12)
        planck = eq_feedback("planck_flux_wm2")
        lapse = eq_feedback("lapse_rate_flux_wm2")
        polar = eq_feedback("polar_inversion_flux_wm2")
        wv = eq_feedback("water_vapor_flux_wm2")
        albedo = eq_feedback("surface_albedo_flux_wm2")
        cloud = eq_feedback("cloud_flux_wm2")
        wv_lr = wv + lapse + polar
        net = planck + wv_lr + albedo + cloud
        greg = [r for r in ecs if 1.0 - EPS <= float(r["elapsed_years"]) <= 150.0 + EPS]
        gs = [float(r["global_surface_warming_c"]) for r in greg]
        gn = [float(r["toa_imbalance_wm2"]) for r in greg]
        slope, intercept = linear_fit(gs, gn)
        greg_lambda = -slope
        greg_ecs = intercept / greg_lambda if greg_lambda > 0.0 else float("nan")
        results["tests"]["climate_sensitivity"] = {
            "equilibrium_ecs_c": ecs_c,
            "equilibrium_tail_toa_imbalance_wm2": tail_toa,
            "equilibrium_tail_gmst_trend_c_per_century": gmst_trend_century,
            "equilibrium_tail_amoc_trend_sv_per_century": amoc_trend_century,
            "equilibrium_tail_heat_tendency_wm2": heat_tendency_wm2,
            "equilibrium_tail_energy_closure_residual_wm2": late_energy_residual_wm2,
            "equilibrium_record_interval_years": float(SEGMENTS["ecs_step2x_1600y"].get("record_interval_years", RECORD_INTERVAL_YEARS)),
            "equilibrium_final_amoc_sv": float(ecs[-1]["amoc_sv"]),
            "equilibrium_final_north_atlantic_warming_c": float(ecs[-1]["north_atlantic_warming_c"]),
            "gregory_1_150_feedback_wm2_k": greg_lambda,
            "gregory_1_150_forcing_wm2": intercept,
            "gregory_1_150_effective_ecs_c": greg_ecs,
            "planck_feedback_wm2_k": planck,
            "water_vapor_feedback_wm2_k": wv,
            "resolved_lapse_rate_feedback_wm2_k": lapse,
            "polar_inversion_closure_wm2_k": polar,
            "combined_wv_plus_lr_wm2_k": wv_lr,
            "surface_albedo_feedback_wm2_k": albedo,
            "cloud_feedback_wm2_k": cloud,
            "net_feedback_wm2_k": net,
            "pass_equilibrium_converged": bool(
                abs(tail_toa) <= 0.05
                and abs(gmst_trend_century) <= 0.02
                and abs(amoc_trend_century) <= 0.10
                and abs(late_energy_residual_wm2) <= 0.03
            ),
            "pass_equilibrium_late_energy_closure": bool(abs(late_energy_residual_wm2) <= 0.03),
            "pass_ecs_ar6_likely": bool(2.5 <= ecs_c <= 4.0),
            "pass_equilibrium_amoc_not_collapsed": bool(float(ecs[-1]["amoc_sv"]) > 5.0),
            "pass_planck_ar6_very_likely": bool(-3.4 <= planck <= -3.0),
            "pass_wv_plus_lr_ar6_very_likely": bool(1.10 <= wv_lr <= 1.50),
            "pass_wv_plus_lr_ar6_likely": bool(1.20 <= wv_lr <= 1.40),
            "pass_albedo_ar6_likely": bool(0.25 <= albedo <= 0.45),
            "pass_cloud_ar6_likely": bool(0.12 <= cloud <= 0.72),
            "pass_cloud_ar6_very_likely": bool(-0.10 <= cloud <= 0.94),
            "pass_net_feedback_ar6_very_likely": bool(-1.81 <= net <= -0.51),
        }

    tcr = frames["tcr_one_percent_80y"]
    if tcr:
        doubling_time = math.log(2.0) / math.log(1.01)
        tcr_c = interpolate_record(tcr, "elapsed_years", "global_surface_warming_c", doubling_time)
        co2_at_double = interpolate_record(tcr, "elapsed_years", "co2_ppm", doubling_time)
        entry = {
            "doubling_time_years": doubling_time,
            "tcr_c": tcr_c,
            "co2_ppm_at_doubling_time": co2_at_double,
            "pass_tcr_ar6_likely": bool(1.4 <= tcr_c <= 2.2),
            "pass_tcr_ar6_very_likely": bool(1.2 <= tcr_c <= 2.4),
        }
        ecs_test = results["tests"].get("climate_sensitivity")
        if ecs_test:
            entry["tcr_less_than_ecs"] = bool(tcr_c < float(ecs_test["equilibrium_ecs_c"]))
        results["tests"]["transient_climate_response"] = entry

    # Greenland cap and new sea-ice freshwater/brine pathway.
    green = frames["greenland_warm_200y"]
    if green:
        applied = col(green, "greenland_applied_freshwater_sv")
        storage = col(green, "atlantic_sea_ice_storage_freshwater_sv")
        export = col(green, "atlantic_sea_ice_export_freshwater_sv")
        export_raw = col(green, "atlantic_sea_ice_export_freshwater_raw_sv")
        gmax = float(static_result["source_invariants"]["greenland_max_freshwater_sv"])
        max_green = max(applied) if applied else 0.0
        max_storage = max((abs(v) for v in storage), default=0.0)
        max_export = max((abs(v) for v in export), default=0.0)
        results["tests"]["cryosphere_freshwater"] = {
            "maximum_greenland_applied_freshwater_sv": max_green,
            "configured_greenland_cap_sv": gmax,
            "old_cap_sv": 0.025,
            "maximum_abs_atlantic_ice_storage_freshwater_sv": max_storage,
            "maximum_abs_atlantic_ice_export_freshwater_sv": max_export,
            "maximum_abs_atlantic_ice_export_freshwater_raw_sv": max((abs(v) for v in export_raw), default=0.0),
            "arctic_raw_reference_ice_export_freshwater_sv": float(green[-1].get("arctic_raw_reference_ice_export_freshwater_sv", float("nan"))),
            "arctic_ice_export_freshwater_reference_sv": float(green[-1].get("arctic_ice_export_freshwater_reference_sv", float("nan"))),
            "arctic_ice_export_freshwater_salinity_scale": float(green[-1].get("arctic_ice_export_freshwater_salinity_scale", float("nan"))),
            "max_salt_error_ppm": max_abs(green, "salt_conservation_error_ppm"),
            "pass_greenland_cap_respected": bool(max_green <= gmax + 1.0e-9),
            "pass_greenland_cap_was_raised": bool(gmax > 0.025),
            "pass_sea_ice_salinity_path_active": bool(max_storage > 1.0e-7 or max_export > 1.0e-7),
            "pass_salt_with_cryosphere_flux": bool(max_abs(green, "salt_conservation_error_ppm") < 1.0e-6),
        }

    # Long collapse/recovery diagnostic, chunked just like every other run.
    rec = frames["recovery_0p4_1050y"]
    if rec:
        pre = [r for r in rec if float(r["elapsed_years"]) <= 250.0 + EPS]
        post = [r for r in rec if float(r["elapsed_years"]) >= 250.0 - EPS]
        minimum = min(col(rec, "amoc_sv"))
        at_release = float(pre[-1]["amoc_sv"]) if pre else None
        final = float(rec[-1]["amoc_sv"])
        overshoot = max(col(post, "amoc_sv")) if post else None
        final_elapsed = float(rec[-1]["elapsed_years"])
        # The freely evolving pycnocline has a ~55-year linearized closure
        # timescale near the collapsed equilibrium. Evaluate it only after the
        # long recovery experiment has actually approached that equilibrium;
        # the previous standalone 300-year test ended while the imbalance was
        # still decaying and falsely reported a structural failure.
        pyc_tail = [r for r in rec if float(r["elapsed_years"]) >= 600.0 - EPS]
        if pyc_tail:
            pyc_imbalances = [abs(float(r["pycnocline_volume_imbalance_sv"])) for r in pyc_tail]
            pyc_tail_mean = sum(pyc_imbalances) / len(pyc_imbalances)
            results["tests"]["pycnocline_closure"] = {
                "evaluation_start_year": 600.0,
                "tail_mean_abs_volume_imbalance_sv": pyc_tail_mean,
                "final_volume_imbalance_sv": float(rec[-1]["pycnocline_volume_imbalance_sv"]),
                "final_depth_m": float(rec[-1]["pycnocline_depth_m"]),
                "final_amoc_sv": float(rec[-1]["amoc_sv"]),
                "pass_closure": bool(pyc_tail_mean < 0.50 and abs(float(rec[-1]["pycnocline_volume_imbalance_sv"])) < 0.05),
            }

        final_row = rec[-1]
        results["tests"]["collapse_recovery"] = {
            "minimum_amoc_sv": minimum,
            "amoc_at_hosing_release_sv": at_release,
            "final_amoc_sv": final,
            "post_release_maximum_amoc_sv": overshoot,
            "final_elapsed_years": final_elapsed,
            "final_north_atlantic_warming_c": float(final_row["north_atlantic_warming_c"]),
            "final_density_driver_ratio": float(final_row["amoc_density_driver_ratio"]),
            "final_north_salinity_psu": float(final_row["north_salinity_psu"]),
            "final_southern_salinity_psu": float(final_row["southern_salinity_psu"]),
            "final_sau_salinity_psu": float(final_row["south_atlantic_upper_salinity_psu"]),
            "final_deep_salinity_psu": float(final_row["deep_salinity_psu"]),
            "pass_persistent_cold_blob_not_extreme": bool(float(final_row["north_atlantic_warming_c"]) >= -8.0),
            "pass_collapsed_under_hosing": bool(minimum < 3.0),
            "pass_full_duration_completed": bool(final_elapsed >= 1050.0 - 1.0e-6),
            "recovered_to_within_10_percent_of_control": bool(abs(final - 17.0) <= 1.7),
            # This field is descriptive: recovery implies monostability for this
            # transient protocol; persistent collapse implies hysteretic memory.
            "classification": (
                "recovered_default_branch" if abs(final - 17.0) <= 1.7
                else "persistent_weakened_or_collapsed_branch"
            ),
        }
        conv = col(rec, "amoc_convection_efficiency")
        if conv:
            configured_max = float(static_result["source_invariants"]["configured_convection_max"])
            results["tests"]["convection_strengthening_bounds"] = {
                "minimum_efficiency": min(conv),
                "maximum_efficiency": max(conv),
                "configured_maximum": configured_max,
                "pass_within_configured_bounds": bool(min(conv) >= -1e-9 and max(conv) <= configured_max + 1e-9),
            }

    # Repair R12 out-of-sample SSP2-4.5 validation and cross-resolution check.
    def window_mean_year(records: list[dict[str, Any]], key: str, start_year: float, end_year: float) -> float:
        values = [
            float(r[key]) for r in records
            if r.get(key) is not None
            and r.get("year") is not None
            and start_year - EPS <= float(r["year"]) <= end_year + EPS
            and math.isfinite(float(r[key]))
        ]
        return sum(values) / len(values) if values else float("nan")

    ssp_rows: dict[str, dict[str, float]] = {}
    for label, segment_name in [("10deg", "ssp245_1850_2100_10deg"), ("5deg", "ssp245_1850_2100_5deg")]:
        ssp = frames.get(segment_name, [])
        if not ssp:
            continue
        gmst_pi = window_mean_year(ssp, "global_surface_warming_c", 1850.0, 1900.0)
        gmst_recent = window_mean_year(ssp, "global_surface_warming_c", 2011.0, 2020.0)
        gmst_late = window_mean_year(ssp, "global_surface_warming_c", 2081.0, 2100.0)
        amoc_recent = window_mean_year(ssp, "amoc_sv", 1995.0, 2014.0)
        amoc_late = window_mean_year(ssp, "amoc_sv", 2081.0, 2100.0)
        late_warming = gmst_late - gmst_pi
        historical_warming = gmst_recent - gmst_pi
        decline = 100.0 * (1.0 - amoc_late / amoc_recent) if abs(amoc_recent) > 1.0e-12 else float("nan")
        minimum_amoc = min(float(r["amoc_sv"]) for r in ssp)
        max_salt_error = max(abs(float(r.get("salt_conservation_error_ppm", 0.0))) for r in ssp)
        ssp_rows[label] = {
            "historical_gmst_2011_2020_vs_1850_1900_c": historical_warming,
            "ssp245_gmst_2081_2100_vs_1850_1900_c": late_warming,
            "amoc_1995_2014_sv": amoc_recent,
            "amoc_2081_2100_sv": amoc_late,
            "amoc_decline_2081_2100_vs_1995_2014_percent": decline,
            "minimum_amoc_sv": minimum_amoc,
            "final_fovs_sv": float(ssp[-1].get("fovs_sv", float("nan"))),
            "max_salt_error_ppm": max_salt_error,
            # IPCC AR6: 2011-2020 observed warming ~1.09 C relative to 1850-1900.
            # Keep a broad validation interval rather than using a calibration target.
            "pass_historical_warming_broad": bool(0.8 <= historical_warming <= 1.3),
            # AR6 SSP2-4.5 2081-2100 very-likely range: 2.1-3.5 C relative to 1850-1900.
            "pass_ssp245_ar6_warming_range": bool(2.1 <= late_warming <= 3.5),
            # CMIP6 ScenarioMIP models decline under SSP2-4.5; Weijer et al. (2020)
            # report ~29% ensemble-mean weakening and a constrained 34-45% range.
            # The gate is intentionally wider than either estimate.
            "pass_ssp245_amoc_declines_without_collapse": bool(5.0 <= decline <= 50.0 and amoc_late > 5.0 and minimum_amoc > 3.0),
            "pass_salt_conservation": bool(max_salt_error < 1.0e-6),
        }
    if ssp_rows:
        results["tests"]["ssp245_out_of_sample"] = ssp_rows
    if "10deg" in ssp_rows and "5deg" in ssp_rows:
        a = ssp_rows["10deg"]
        b = ssp_rows["5deg"]
        dg_hist = abs(a["historical_gmst_2011_2020_vs_1850_1900_c"] - b["historical_gmst_2011_2020_vs_1850_1900_c"])
        dg_late = abs(a["ssp245_gmst_2081_2100_vs_1850_1900_c"] - b["ssp245_gmst_2081_2100_vs_1850_1900_c"])
        da_late = abs(a["amoc_2081_2100_sv"] - b["amoc_2081_2100_sv"])
        dd = abs(a["amoc_decline_2081_2100_vs_1995_2014_percent"] - b["amoc_decline_2081_2100_vs_1995_2014_percent"])
        results["tests"]["ssp245_cross_resolution"] = {
            "historical_warming_difference_c": dg_hist,
            "late_warming_difference_c": dg_late,
            "late_amoc_difference_sv": da_late,
            "amoc_decline_difference_percentage_points": dd,
            "pass_historical_warming_resolution_consistency": bool(dg_hist <= 0.20),
            "pass_late_warming_resolution_consistency": bool(dg_late <= 0.30),
            "pass_late_amoc_resolution_consistency": bool(da_late <= 2.0),
            "pass_amoc_decline_resolution_consistency": bool(dd <= 10.0),
        }

    # Untuned hosing dose response: test monotonicity rather than fitting a new
    # collapse threshold. These amplitudes were not used in the Repair R11 calibration.
    dose_rows = []
    for freshwater, name in [(0.10, "hosing_0p1_100y"), (0.20, "hosing_0p2_100y"), (0.30, "hosing_0p3_100y")]:
        h = frames.get(name, [])
        if not h:
            continue
        amoc_vals = [float(r["amoc_sv"]) for r in h]
        nat_vals = [float(r["north_atlantic_warming_c"]) for r in h]
        salt_err = max(abs(float(r.get("salt_conservation_error_ppm", 0.0))) for r in h)
        dose_rows.append({
            "freshwater_hosing_sv": freshwater,
            "minimum_amoc_sv": min(amoc_vals),
            "final_amoc_sv": amoc_vals[-1],
            "minimum_north_atlantic_anomaly_c": min(nat_vals),
            "final_density_driver_ratio": float(h[-1]["amoc_density_driver_ratio"]),
            "maximum_salt_error_ppm": salt_err,
            "pass_salt_conservation": bool(salt_err < 1.0e-6),
        })
    if len(dose_rows) == 3:
        monotonic_amoc = dose_rows[0]["minimum_amoc_sv"] > dose_rows[1]["minimum_amoc_sv"] > dose_rows[2]["minimum_amoc_sv"]
        monotonic_cooling = dose_rows[0]["minimum_north_atlantic_anomaly_c"] > dose_rows[1]["minimum_north_atlantic_anomaly_c"] > dose_rows[2]["minimum_north_atlantic_anomaly_c"]
        results["tests"]["hosing_dose_response_out_of_sample"] = {
            "runs": dose_rows,
            "pass_monotonic_amoc_weakening": bool(monotonic_amoc),
            "pass_monotonic_north_atlantic_cooling": bool(monotonic_cooling),
            "pass_all_salt_conservation": bool(all(r["pass_salt_conservation"] for r in dose_rows)),
            # A mild 0.1-Sv perturbation should not jump directly onto the
            # collapsed branch over 100 years; this guards against an over-sharp bifurcation.
            "pass_0p1sv_not_collapsed": bool(dose_rows[0]["minimum_amoc_sv"] > 3.0),
        }

    return results


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
    shutil.copy2(Path(__file__).resolve(), OUT / "verify_physics_local.py")
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
    if args.validation_only:
        baseline_manifest_path = ROOT / "REPAIR_R11_VERIFIED_BASELINE_MANIFEST.json"
        baseline_results_path = ROOT / "REPAIR_R11_VERIFIED_BASELINE_RESULTS.json"
        if not baseline_manifest_path.exists() or not baseline_results_path.exists():
            raise SystemExit("Repair R12 validation-only mode requires the bundled verified Repair R11 baseline result + manifest files.")
        baseline_manifest_info = json.loads(baseline_manifest_path.read_text(encoding="utf-8"))
        baseline_source = baseline_manifest_info.get("climate_model_sha256")
        if baseline_source != source_hash:
            equivalence_path = ROOT / "REPAIR_R13_DYNAMICS_EQUIVALENCE.json"
            accepted_equivalent = False
            current_core = core_ast_sha256(SOURCE)
            if equivalence_path.exists():
                equivalence = json.loads(equivalence_path.read_text(encoding="utf-8"))
                accepted_equivalent = bool(
                    equivalence.get("validated_source_sha256") == baseline_source
                    and equivalence.get("release_source_sha256") == source_hash
                    and equivalence.get("validated_core_ast_sha256") == current_core
                    and equivalence.get("release_core_ast_sha256") == current_core
                    and equivalence.get("excluded_top_level_symbols") == ["MODEL_NAME", "build_parser"]
                )
            if not accepted_equivalent:
                raise SystemExit(
                    "Bundled verified baseline uses a different climate_model.py and no valid "
                    "dynamics-equivalence manifest proves the difference is CLI/name-only: "
                    f"baseline={baseline_source}, current={source_hash}."
                )
            print(
                "Validated numerical baseline accepted via Repair R13 dynamics-AST equivalence "
                f"({current_core}).",
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
        "segments": {},
        "static": {},
    }

    print("CLEM local physics verification", flush=True)
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
    manifest["run_mode"] = "repair_r12_out_of_sample_only" if args.validation_only else "full_physics_suite"
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
    print("Upload physics_verification_bundle.zip back to ChatGPT.", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="CLEM local physics verification with <=5-year restartable chunks")
    parser.add_argument("--fresh", action="store_true", help="delete old verification checkpoints/results and restart from zero")
    parser.add_argument("--chunk-years", type=float, default=MAX_CHUNK_YEARS, help="model years per child process; values above 5 are forced down to 5")
    parser.add_argument("--timeout", type=int, default=DEFAULT_CHUNK_TIMEOUT_SECONDS, help="wall-clock timeout per <=5-year integration child")
    parser.add_argument("--setup-timeout", type=int, default=DEFAULT_SETUP_TIMEOUT_SECONDS, help="wall-clock timeout for model initialization/checkpoint setup")
    parser.add_argument("--validation-only", action="store_true", help="run only the Repair R12 out-of-sample SSP2-4.5, cross-resolution, and hosing-dose tests")
    parser.add_argument("--worker-mode", choices=["static", "setup", "advance"], help=argparse.SUPPRESS)
    parser.add_argument("--segment", choices=sorted(SEGMENTS), help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.worker_mode:
        worker_entry(args.worker_mode, args.segment, min(args.chunk_years, MAX_CHUNK_YEARS))
    else:
        parent_main(args)


if __name__ == "__main__":
    main()
