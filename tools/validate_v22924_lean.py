#!/usr/bin/env python3
"""Lean, resumable scientific checks for EGCM v2.29.24.

This runner advances the exact production ProcessClimateModel timestep loop but
records only the diagnostics needed for the selected check.  It avoids building
the full SimulationResult history, which makes the long Arctic validation gates
practical in constrained environments without changing the model equations.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from climate_model import EARTH_AREA_M2, MODEL_VERSION, ModelConfig, ProcessClimateModel
from sea_ice_validation import (
    CALIBRATION,
    DEVELOPMENT_EVALUATION,
    evaluate_period,
    load_nsidc_month,
    rolling_origin_evaluation,
)


def _config(resolution: float, scenario: str, duration: float) -> ModelConfig:
    cfg = replace(
        ModelConfig(),
        start_year=1850.0,
        duration_years=float(duration),
        scenario=scenario,
        dt_years=0.05,
        record_every_years=0.05,
        resolution_deg=float(resolution),
        auto_initialize_from_1850=False,
    )
    cfg.validate()
    return cfg


def _target_steps(start_year: float, end_year: int, dt: float, min_year: int = 1979) -> dict[int, tuple[int, int]]:
    targets: dict[int, tuple[int, int]] = {}
    for year in range(max(min_year, int(start_year)), end_year + 1):
        for month in (3, 9):
            target_elapsed = year + (month - 0.5) / 12.0 - start_year
            step = int(round(target_elapsed / dt))
            targets[step] = (year, month)
    return targets


def _advance(model: ProcessClimateModel, duration: float, callback=None) -> None:
    dt = float(model.config.dt_years)
    elapsed = 0.0
    step = 0
    next_progress = 25.0
    tolerance = 1.0e-12
    while elapsed < duration - tolerance:
        actual_dt = min(dt, duration - elapsed)
        model.step(elapsed, dt_years=actual_dt)
        elapsed += actual_dt
        step += 1
        if callback is not None:
            callback(step, elapsed)
        if elapsed + tolerance >= next_progress:
            print(f"progress_year={model.config.start_year + elapsed:.1f}", flush=True)
            next_progress += 25.0


def _historical_records(resolution: float) -> tuple[ModelConfig, pd.DataFrame, float]:
    cfg = _config(resolution, "ssp245", 177.0)
    started = time.perf_counter()
    model = ProcessClimateModel(cfg)
    targets = _target_steps(cfg.start_year, 2026, cfg.dt_years)
    rows: list[dict[str, float | int | str]] = []
    observations = {month: load_nsidc_month(month).set_index("year") for month in (3, 9)}

    def capture(step: int, elapsed: float) -> None:
        target = targets.get(step)
        if target is None:
            return
        year, month = target
        observed = observations[month]
        if year not in observed.index:
            return
        record = model.record(elapsed)
        native = float(record["native_northern_ice_area_million_km2"])
        rows.append({
            "year": year,
            "month": month,
            "model_year": cfg.start_year + elapsed,
            "model_area": float(record["northern_hemisphere_sea_ice_area_million_km2"]),
            "model_extent": float(record["northern_hemisphere_sea_ice_extent_million_km2"]),
            "model_native_area": native,
            "model_raw_area": native,
            "model_warming_c": float(record["global_surface_warming_c"]),
            "observed_area": float(observed.loc[year, "area"]),
            "observed_extent": float(observed.loc[year, "extent"]),
            "observation_source": str(observed.loc[year, "source_dataset"] if "source_dataset" in observed.columns else observed.loc[year, "source-data"]),
        })

    _advance(model, cfg.duration_years, capture)
    return cfg, pd.DataFrame(rows), time.perf_counter() - started


def historical(resolution: float) -> dict:
    cfg, records, runtime = _historical_records(resolution)
    rolling = rolling_origin_evaluation(records)
    calibration = evaluate_period(records, CALIBRATION)
    development = evaluate_period(records, DEVELOPMENT_EVALUATION)
    return {
        "model_version": MODEL_VERSION,
        "resolution_deg": resolution,
        "runtime_seconds": runtime,
        "locked_defaults": {
            "arctic_max_equivalent_thickness_m": cfg.arctic_max_equivalent_thickness_m,
            "arctic_max_local_ice_thickness_m": cfg.arctic_max_local_ice_thickness_m,
            "arctic_phase_restoring_deficit_saturation_fraction": cfg.arctic_phase_restoring_deficit_saturation_fraction,
            "arctic_ice_area_thick_pack_resistance_exponent": cfg.arctic_ice_area_thick_pack_resistance_exponent,
            "arctic_forced_ocean_heat_convergence_wm2_per_k": cfg.arctic_forced_ocean_heat_convergence_wm2_per_k,
            "arctic_forced_ocean_heat_convergence_onset_warming_c": cfg.arctic_forced_ocean_heat_convergence_onset_warming_c,
        },
        "rolling_origin": rolling,
        "calibration": calibration,
        "development": development,
    }


def _ice_geometry(model: ProcessClimateModel, elapsed: float) -> dict[str, float]:
    ref = model._arctic_reference_state(elapsed)
    sectors = []
    for prefix, ocean_map, concentration, anomaly in (
        ("atlantic", model.grid.atlantic_ocean_fraction_map, model.state.atlantic_sea_ice_fraction, model.state.arctic_atlantic_ice_energy_anomaly_wyr_m2),
        ("non_atlantic", np.clip(model.grid.ocean_fraction_map - model.grid.atlantic_ocean_fraction_map, 0.0, 1.0), model.state.non_atlantic_sea_ice_fraction, model.state.arctic_non_atlantic_ice_energy_anomaly_wyr_m2),
    ):
        total_energy = ref[f"{prefix}_ice_energy_wyr_m2"] + anomaly
        _, equivalent, local = model._arctic_state_from_energy_and_concentration(total_energy, concentration)
        sectors.append((ocean_map, np.asarray(concentration)[:, None], np.asarray(equivalent)[:, None], np.asarray(local)[:, None]))
    northern = model.grid.lat2d >= 0.0
    area_m2 = 0.0
    volume_m3 = 0.0
    guard_area_m2 = 0.0
    maximum = 0.0
    local_guard = model.config.arctic_max_local_ice_thickness_m
    for ocean_map, concentration, equivalent, local in sectors:
        area_weight = np.where(northern, ocean_map * concentration * model.grid.map_area_weights, 0.0)
        area_m2 += float(np.sum(area_weight) * EARTH_AREA_M2)
        volume_m3 += float(np.sum(np.where(northern, ocean_map * equivalent * model.grid.map_area_weights, 0.0)) * EARTH_AREA_M2)
        guard_area_m2 += float(np.sum(np.where(local >= 0.99 * local_guard, area_weight, 0.0)) * EARTH_AREA_M2)
        active_latitudes = np.any(area_weight > 0.0, axis=1)
        active = local[:, 0][active_latitudes]
        if active.size:
            maximum = max(maximum, float(np.max(active)))
    return {
        "arctic_geometry_area_million_km2": area_m2 / 1.0e12,
        "volume_thousand_km3": volume_m3 / 1.0e12,
        "mean_local_thickness_m": volume_m3 / area_m2 if area_m2 > 0.0 else 0.0,
        "maximum_local_thickness_m": maximum,
        "guard_contact_area_fraction": guard_area_m2 / area_m2 if area_m2 > 0.0 else 0.0,
    }


def future(resolution: float, scenario: str) -> dict:
    cfg = _config(resolution, scenario, 251.0)
    started = time.perf_counter()
    model = ProcessClimateModel(cfg)
    target_elapsed = 2100 + (9 - 0.5) / 12.0 - cfg.start_year
    target_step = int(round(target_elapsed / cfg.dt_years))
    captured: dict[str, float] = {}
    def capture(step: int, elapsed: float) -> None:
        nonlocal captured
        if step == target_step:
            captured = _ice_geometry(model, elapsed)
            record = model.record(elapsed)
            captured["northern_hemisphere_area_million_km2"] = float(
                record["northern_hemisphere_sea_ice_area_million_km2"]
            )
            captured["northern_hemisphere_extent_million_km2"] = float(
                record["northern_hemisphere_sea_ice_extent_million_km2"]
            )
    _advance(model, cfg.duration_years, capture)
    return {
        "model_version": MODEL_VERSION,
        "resolution_deg": resolution,
        "scenario": scenario,
        "runtime_seconds": time.perf_counter() - started,
        "september_2100": captured,
    }



def unforced(resolution: float, duration: float = 200.0) -> dict:
    cfg = _config(resolution, "constant", duration)
    started = time.perf_counter()
    model = ProcessClimateModel(cfg)
    end_year = int(cfg.start_year + duration - 1)
    targets = _target_steps(cfg.start_year, end_year, cfg.dt_years, min_year=int(cfg.start_year))
    rows: list[dict[str, float | int]] = []
    def capture(step: int, elapsed: float) -> None:
        target = targets.get(step)
        if target is None:
            return
        year, month = target
        record = model.record(elapsed)
        rows.append({
            "year": year,
            "month": month,
            "area": float(record["northern_hemisphere_sea_ice_area_million_km2"]),
            "gmst": float(record["global_surface_warming_c"]),
            "toa": float(record["toa_imbalance_wm2"]),
        })
    _advance(model, cfg.duration_years, capture)
    frame = pd.DataFrame(rows)
    metrics: dict[str, dict[str, float]] = {}
    for month, name in ((3, "march"), (9, "september")):
        values = frame[frame["month"] == month].sort_values("year")
        first = values.head(20)
        last = values.tail(20)
        metrics[name] = {
            "first_20_mean_area_million_km2": float(first["area"].mean()),
            "last_20_mean_area_million_km2": float(last["area"].mean()),
            "drift_million_km2": float(last["area"].mean() - first["area"].mean()),
        }
    return {
        "model_version": MODEL_VERSION,
        "resolution_deg": resolution,
        "duration_years": duration,
        "runtime_seconds": time.perf_counter() - started,
        "march": metrics["march"],
        "september": metrics["september"],
        "maximum_absolute_gmst_c": float(frame["gmst"].abs().max()),
        "maximum_absolute_toa_wm2": float(frame["toa"].abs().max()),
    }

def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    h = sub.add_parser("historical")
    h.add_argument("--resolution", type=float, required=True, choices=(5.0, 10.0))
    f = sub.add_parser("future")
    f.add_argument("--resolution", type=float, required=True, choices=(5.0, 10.0))
    f.add_argument("--scenario", choices=("ssp126", "ssp245", "ssp460", "ssp585"), required=True)
    u = sub.add_parser("unforced")
    u.add_argument("--resolution", type=float, required=True, choices=(5.0, 10.0))
    u.add_argument("--duration", type=float, default=200.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "historical":
        payload = historical(args.resolution)
    elif args.command == "future":
        payload = future(args.resolution, args.scenario)
    else:
        payload = unforced(args.resolution, args.duration)
    text = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
        print(f"wrote={args.output}", flush=True)
    else:
        print(text)


if __name__ == "__main__":
    main()
