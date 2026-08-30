#!/usr/bin/env python3
"""Generate synchronized v2.29.9 accuracy and evidence-integrity validation records."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np

from climate_model import (
    ARCTIC_MINIMUM_SENSIBLE_OPEN_FRACTION,
    EARTH_AREA_M2,
    MODEL_VERSION,
    ModelConfig,
    ProcessClimateModel,
    SECONDS_PER_YEAR,
    SV_TO_GT_PER_YEAR,
)
from monte_carlo import compute_importance_weights
from scientific_evidence import SCIENTIFIC_USE_METADATA
from sea_ice_observation import (
    diagnosed_area_extent_million_km2,
    raw_northern_ice_area_million_km2,
)
from sea_ice_validation import evaluate_result as evaluate_sea_ice_result
from validation_segmentation import run_segmented

from held_out_amoc_validation import (
    annual_mean_frame,
    cross_resolution,
    historical_external_metrics,
    hosing_recovery,
    window_mean,
)

ROOT = Path(__file__).resolve().parent
BENCHMARK_PATH = ROOT / "development_regression_benchmarks.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(name: str, value: Any) -> None:
    (ROOT / name).write_text(json.dumps(value, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def seasonal_slope_ratio(frame, months: tuple[int, ...]) -> float:
    data = frame.copy()
    data["month"] = data["arctic_calendar_month"].round().astype(int)
    data = data[(data["year"] >= 1979.0) & (data["year"] <= 2021.999)]
    data = data[data["month"].isin(months)]
    if len(data) < 6:
        return float("nan")
    global_slope = float(np.polyfit(data["year"], data["global_instantaneous_near_surface_air_warming_c"], 1)[0])
    arctic_slope = float(np.polyfit(data["year"], data["arctic_instantaneous_near_surface_air_warming_c"], 1)[0])
    return arctic_slope / global_slope if abs(global_slope) > 1.0e-14 else float("nan")


def scenario_run(
    scenario: str,
    dt: float = 0.05,
    record_every: float = 1.0,
):
    cfg = replace(
        ModelConfig(),
        start_year=1850.0,
        duration_years=251.0,
        scenario=scenario,
        dt_years=dt,
        record_every_years=record_every,
        auto_initialize_from_1850=False,
    )
    result = run_segmented(cfg, segment_years=40.0)
    return cfg, result


def arctic_transient_metrics(result) -> dict[str, float]:
    summary = result.summary()
    keys = (
        "maximum_arctic_open_water_temperature_c",
        "maximum_arctic_open_water_temperature_c_at_1pct_open",
        "maximum_arctic_open_water_temperature_c_at_5pct_open",
        "maximum_arctic_open_water_temperature_c_at_10pct_open",
        "maximum_dormant_arctic_open_water_heat_wyr_m2",
        "maximum_absolute_salt_conservation_error_ppm",
        "maximum_pre_projection_salt_conservation_error_ppm",
        "cumulative_absolute_salt_projection_correction_ppm",
        "arctic_reference_periodic_closure_wyr_m2",
        "arctic_reference_spinup_convergence_wyr_m2",
        "arctic_reference_spinup_years_completed",
        "arctic_reference_convergence_tolerance_wyr_m2",
    )
    return {key: float(summary[key]) for key in keys}


COMMON_VALIDATION_SAMPLE_YEARS = 0.1


def common_validation_sample(frame, cadence: float = COMMON_VALIDATION_SAMPLE_YEARS):
    """Return records on one identical subannual time grid.

    All supported validation timesteps divide the 0.1-year cadence exactly.
    Using this common grid prevents fixed-season annual snapshots from being
    compared with time-weighted subannual means.
    """
    elapsed = frame["elapsed_years"].to_numpy(dtype=float)
    nearest = np.rint(elapsed / cadence) * cadence
    keep = np.isclose(elapsed, nearest, rtol=0.0, atol=1.0e-8)
    sampled = frame.loc[keep].copy().reset_index(drop=True)
    if sampled.empty:
        raise ValueError("Common validation sampling produced no records")
    return sampled


def amoc_decline(annual) -> float:
    baseline = window_mean(annual, "amoc_sv", 1995.0, 2014.0)
    endpoint = window_mean(annual, "amoc_sv", 2081.0, 2100.0)
    return 100.0 * (1.0 - endpoint / baseline)


def _uncorrected_control_drift(cfg: ModelConfig) -> dict[str, float]:
    """Integrate the ordinary equations without reference-tendency correction."""
    model = ProcessClimateModel(cfg)
    initial = model.record(0.0)
    elapsed = 0.0
    while elapsed < cfg.duration_years - 1.0e-12:
        dt = min(cfg.dt_years, cfg.duration_years - elapsed)
        model._step_uncorrected(elapsed, dt)
        elapsed += dt
    model._check_state()
    final = model.record(elapsed)
    return {
        "uncorrected_initial_gmst_c": float(initial["global_surface_warming_c"]),
        "uncorrected_final_gmst_c": float(final["global_surface_warming_c"]),
        "uncorrected_gmst_drift_c": float(
            final["global_surface_warming_c"] - initial["global_surface_warming_c"]
        ),
        "uncorrected_initial_amoc_sv": float(initial["amoc_sv"]),
        "uncorrected_final_amoc_sv": float(final["amoc_sv"]),
        "uncorrected_amoc_drift_sv": float(final["amoc_sv"] - initial["amoc_sv"]),
        "uncorrected_final_toa_imbalance_wm2": float(final["toa_imbalance_wm2"]),
        "uncorrected_final_salt_conservation_error_ppm": float(
            final["salt_conservation_error_ppm"]
        ),
    }


def control_check() -> dict[str, Any]:
    cfg = replace(
        ModelConfig(),
        scenario="constant",
        duration_years=500.0,
        record_every_years=100.0,
        auto_initialize_from_1850=False,
    )
    result = run_segmented(cfg, segment_years=40.0)
    initial = result.dataframe.iloc[0]
    final = result.dataframe.iloc[-1]
    values: dict[str, Any] = {
        "years": 500.0,
        "initial_gmst_c": float(initial["global_surface_warming_c"]),
        "final_gmst_c": float(final["global_surface_warming_c"]),
        "gmst_drift_c": float(final["global_surface_warming_c"] - initial["global_surface_warming_c"]),
        "initial_amoc_sv": float(initial["amoc_sv"]),
        "final_amoc_sv": float(final["amoc_sv"]),
        "amoc_drift_sv": float(final["amoc_sv"] - initial["amoc_sv"]),
        "corrected_initial_gmst_c": float(initial["global_surface_warming_c"]),
        "corrected_final_gmst_c": float(final["global_surface_warming_c"]),
        "corrected_gmst_drift_c": float(final["global_surface_warming_c"] - initial["global_surface_warming_c"]),
        "corrected_initial_amoc_sv": float(initial["amoc_sv"]),
        "corrected_final_amoc_sv": float(final["amoc_sv"]),
        "corrected_amoc_drift_sv": float(final["amoc_sv"] - initial["amoc_sv"]),
        "final_toa_imbalance_wm2": float(final["toa_imbalance_wm2"]),
        "final_salt_conservation_error_ppm": float(final["salt_conservation_error_ppm"]),
        "maximum_pre_projection_salt_conservation_error_ppm": float(
            final["pre_projection_salt_conservation_error_ppm"]
        ),
        "cumulative_absolute_salt_projection_correction_psu_m3": float(
            final["cumulative_absolute_salt_projection_correction_psu_m3"]
        ),
        "arctic_reference_periodic_closure_wyr_m2": float(
            result.arctic_reference_periodic_closure_wyr_m2
        ),
        "arctic_reference_spinup_convergence_wyr_m2": float(
            result.arctic_reference_spinup_convergence_wyr_m2
        ),
        "arctic_reference_spinup_years_completed": int(
            result.arctic_reference_spinup_years_completed
        ),
        "final_total_resolved_heat_content_anomaly_zj": float(final["total_resolved_heat_content_anomaly_zj"]),
        "reference_tendency_residual_role": (
            "diagnostic comparison only; corrected control measures release balance, "
            "while uncorrected drift exposes the residual ordinary-equation tendency"
        ),
    }
    values.update(_uncorrected_control_drift(cfg))
    return values


def perturbation_check(sign: float) -> dict[str, float]:
    seed_cfg = replace(ModelConfig(), scenario="constant", duration_years=1.0, auto_initialize_from_1850=False)
    model = ProcessClimateModel(seed_cfg)
    mask = model.arctic_module_blend
    model.state.arctic_atlantic_air_anomaly_c += sign * 0.5 * mask
    model.state.arctic_non_atlantic_air_anomaly_c += sign * 0.5 * mask
    model.state.arctic_atlantic_ice_energy_anomaly_wyr_m2 += sign * 0.25 * mask
    model.state.arctic_non_atlantic_ice_energy_anomaly_wyr_m2 += sign * 0.25 * mask
    model.state.arctic_atlantic_open_water_heat_anomaly_wyr_m2 += sign * 0.10 * mask
    model.state.arctic_non_atlantic_open_water_heat_anomaly_wyr_m2 += sign * 0.10 * mask
    cfg = replace(seed_cfg, duration_years=160.0, record_every_years=160.0)
    result = run_segmented(cfg, segment_years=40.0, initial_state=model.state)
    row = result.dataframe.iloc[-1]
    return {
        "sign": sign,
        "years": 160.0,
        "final_arctic_air_c": float(row["arctic_warming_c"]),
        "final_amoc_sv": float(row["amoc_sv"]),
        "final_salt_conservation_error_ppm": float(row["salt_conservation_error_ppm"]),
        "maximum_pre_projection_salt_conservation_error_ppm": float(
            row["pre_projection_salt_conservation_error_ppm"]
        ),
        "cumulative_absolute_salt_projection_correction_psu_m3": float(
            row["cumulative_absolute_salt_projection_correction_psu_m3"]
        ),
    }


def timestep_metrics(dt: float) -> dict[str, float]:
    _, result = scenario_run(
        "ssp245", dt, record_every=COMMON_VALIDATION_SAMPLE_YEARS
    )
    sampled = common_validation_sample(result.dataframe)
    return {
        "dt_years": dt,
        "sample_cadence_years": COMMON_VALIDATION_SAMPLE_YEARS,
        **historical_external_metrics(annual_mean_frame(sampled)),
        **arctic_transient_metrics(result),
    }


def evaluate_benchmarks(metrics: dict[str, float], benchmark_doc: dict[str, Any]) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for key, benchmark in benchmark_doc["benchmarks"].items():
        value = float(metrics[key])
        low = float(benchmark["minimum"])
        high = float(benchmark["maximum"])
        results[key] = {
            "value": value,
            "minimum": low,
            "maximum": high,
            "units": benchmark["units"],
            "passed": low <= value <= high,
            "evidence_role": benchmark["evidence_role"],
            "used_for_tuning": bool(benchmark["used_for_tuning"]),
            "source_reference": benchmark["source_reference"],
        }
    return results



def _future_sea_ice_metrics(result: Any) -> dict[str, Any]:
    """Summarize native September ice on an explicitly subannual grid.

    Native thermodynamic area is the primary sensitivity output. The only statistical
    conversion retained is a fixed, zero-intercept seasonal area-to-extent
    ratio. No post-2020 trend, scenario closure, or target adjustment is used.
    """
    years = result.dataframe["year"].to_numpy(dtype=float)
    rows: list[tuple[int, float, float, float]] = []
    first_below_one: int | None = None
    for year in range(2021, 2101):
        target = year + (9.0 - 0.5) / 12.0
        index = int(np.argmin(np.abs(years - target)))
        if abs(float(years[index]) - target) > 0.061:
            raise ValueError(
                "September sea-ice validation requires subannual records at "
                "0.1-year cadence or finer"
            )
        metrics = result.northern_sea_ice_area_extent_at_index(index)
        area = float(metrics["northern_hemisphere_sea_ice_area_million_km2"])
        extent = float(metrics["northern_hemisphere_sea_ice_extent_million_km2"])
        native_area = float(
            metrics.get(
                "native_northern_ice_area_million_km2",
                metrics["raw_two_sector_northern_ice_area_million_km2"],
            )
        )
        rows.append((year, area, extent, native_area))
        if first_below_one is None and native_area < 1.0:
            first_below_one = year
    late = [row for row in rows if 2081 <= row[0] <= 2100]
    return {
        "september_area_2081_2100_million_km2": float(np.mean([row[1] for row in late])),
        "september_extent_2081_2100_million_km2": float(np.mean([row[2] for row in late])),
        "native_september_area_2081_2100_million_km2": float(np.mean([row[3] for row in late])),
        "first_september_below_1_million_km2_native_area": first_below_one,
        "september_2100_area_million_km2": rows[-1][1],
        "september_2100_extent_million_km2": rows[-1][2],
        "native_september_2100_area_million_km2": rows[-1][3],
        "maximum_area_identity_error_million_km2": float(
            max(abs(row[1] - row[3]) for row in rows)
        ),
        "evidence_role": "native_thermodynamic_area_sensitivity_with_secondary_extent_operator",
        "used_for_tuning": False,
        "independent_predictive_validation": False,
        "interpretation": (
            "Native prognostic thermodynamic area is a future sensitivity output. "
            "The fixed zero-intercept historical operator is used only for 15% "
            "secondary extent. No post-2020 trend, scenario closure, or future-target "
            "adjustment is applied. Longitude reconstruction is display-only "
            "and has no regional predictive skill. Ice-free timing is a threshold-crossing sensitivity, not a forecast."
        ),
    }


def _open_water_validation(result: Any) -> dict[str, Any]:
    benchmark_path = ROOT / "data" / "validation" / "open_water" / "NOAA_OISST_ARCTIC_BENCHMARKS.json"
    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    years = result.dataframe["year"].to_numpy(dtype=float)
    latitude_mask = result.grid.lat >= 66.0
    records: dict[str, list[float]] = {"atlantic_jja": [], "non_atlantic_jja": [], "atlantic_september": [], "non_atlantic_september": []}
    sectors = (
        ("atlantic", result.arctic_atlantic_open_water_temperature_history_c, result.atlantic_sea_ice_history, result.grid.atlantic_ocean_fraction),
        ("non_atlantic", result.arctic_non_atlantic_open_water_temperature_history_c, result.non_atlantic_sea_ice_history, np.clip(result.grid.ocean_fraction - result.grid.atlantic_ocean_fraction, 0.0, 1.0)),
    )
    for year in range(1991, 2021):
        for month in (6, 7, 8, 9):
            index = int(np.argmin(np.abs(years - (year + (month - 0.5) / 12.0))))
            for name, temperature, ice, ocean_fraction in sectors:
                weights = result.grid.band_area_weights * ocean_fraction * latitude_mask * np.clip(1.0 - ice[index], 0.0, 1.0)
                if float(np.sum(weights)) <= 1.0e-12:
                    continue
                value = float(np.sum(temperature[index] * weights) / np.sum(weights))
                if month in (6, 7, 8):
                    records[f"{name}_jja"].append(value)
                else:
                    records[f"{name}_september"].append(value)
    values = {
        "atlantic_jja_mean_c": float(np.mean(records["atlantic_jja"])),
        "non_atlantic_jja_mean_c": float(np.mean(records["non_atlantic_jja"])),
        "atlantic_september_mean_c": float(np.mean(records["atlantic_september"])),
        "non_atlantic_september_mean_c": float(np.mean(records["non_atlantic_september"])),
    }
    checks = {}
    for key, value in values.items():
        bounds = benchmark["benchmarks"][key]
        checks[key] = {
            "value": value,
            "minimum": float(bounds["minimum"]),
            "maximum": float(bounds["maximum"]),
            "passed": float(bounds["minimum"]) <= value <= float(bounds["maximum"]),
        }
    bounds_passed = all(item["passed"] for item in checks.values())
    reproduction = benchmark.get("reproduction", {})
    return {
        "benchmark_file": benchmark_path.relative_to(ROOT).as_posix(),
        "benchmark_sha256": sha256_file(benchmark_path),
        "evidence_role": benchmark["evidence_role"],
        "used_for_tuning": benchmark["used_for_tuning"],
        "release_gate_role": benchmark.get("release_gate_role", "informational_only"),
        "quantitative_validation_claimed": False,
        "source_artifacts_reproduced": bool(
            reproduction.get("processed_output_in_release", False)
            and reproduction.get("source_hashes_in_release", False)
        ),
        "scope": benchmark["scope"],
        "checks": checks,
        "bounds_passed": bounds_passed,
        "all_checks_passed": bounds_passed,
        "mandatory_warning": benchmark["mandatory_output_warning"],
    }


def _summary_ssp245_task() -> dict[str, Any]:
    cfg, result = scenario_run("ssp245", dt=0.05, record_every=COMMON_VALIDATION_SAMPLE_YEARS)
    raw = result.dataframe
    sampled = common_validation_sample(raw)
    annual = annual_mean_frame(sampled)
    metrics = historical_external_metrics(annual)
    seasonal = {
        "DJF": seasonal_slope_ratio(raw, (12, 1, 2)),
        "MAM": seasonal_slope_ratio(raw, (3, 4, 5)),
        "JJA": seasonal_slope_ratio(raw, (6, 7, 8)),
        "SON": seasonal_slope_ratio(raw, (9, 10, 11)),
        "annual": metrics["historical_arctic_amplification_1979_2021_ratio"],
    }
    recent = annual[(annual["year"] >= 2011.0) & (annual["year"] <= 2020.0)]
    greenland = {
        "mean_total_loss_2011_2020_gt_per_year": (
            float(recent["greenland_annual_mean_freshwater_sv"].mean())
            * SV_TO_GT_PER_YEAR
        ),
        "mean_dynamic_discharge_2011_2020_gt_per_year": (
            float(recent["greenland_dynamic_discharge_sv"].mean())
            * SV_TO_GT_PER_YEAR
        ),
        "mean_surface_mass_balance_loss_2011_2020_gt_per_year": (
            float(
                recent[
                    "greenland_annual_mean_surface_mass_balance_freshwater_sv"
                ].mean()
            )
            * SV_TO_GT_PER_YEAR
        ),
        "cumulative_net_ice_loss_2100_gt": float(
            annual.iloc[-1]["greenland_cumulative_net_ice_loss_gt"]
        ),
        "cumulative_sea_level_2100_mm": float(
            annual.iloc[-1]["greenland_cumulative_sea_level_mm"]
        ),
    }
    return {
        "config": {
            "hydrological_freshwater_sv_per_k": cfg.hydrological_freshwater_sv_per_k,
            "greenland_freshwater_sv_per_k": cfg.greenland_freshwater_sv_per_k,
            "greenland_dynamic_discharge_fraction": cfg.greenland_dynamic_discharge_fraction,
            "greenland_pdd_melt_factor_gt_per_degree_day": (
                cfg.greenland_pdd_melt_factor_gt_per_degree_day
            ),
            "greenland_max_freshwater_sv": cfg.greenland_max_freshwater_sv,
            "amoc_temperature_density_coupling": cfg.amoc_temperature_density_coupling,
            "amoc_convection_density_scale_factor": (
                cfg.amoc_convection_density_scale_factor
            ),
            "amoc_reference_density_driver": cfg.amoc_reference_density_driver,
            "ocean_heat_exchange_wm2_k": cfg.ocean_heat_exchange_wm2_k,
            "arctic_winter_transport_enhancement": cfg.arctic_winter_transport_enhancement,
            "arctic_open_water_stable_exchange_wm2_k": cfg.arctic_open_water_stable_exchange_wm2_k,
            "arctic_open_water_unstable_exchange_wm2_k": cfg.arctic_open_water_unstable_exchange_wm2_k,
            "arctic_open_water_exchange_transition_c": cfg.arctic_open_water_exchange_transition_c,
            "arctic_transient_shortwave_scale": cfg.arctic_transient_shortwave_scale,
            "arctic_basal_ocean_exchange_wm2_k": cfg.arctic_basal_ocean_exchange_wm2_k,
            "arctic_open_water_ocean_exchange_wm2_k": cfg.arctic_open_water_ocean_exchange_wm2_k,
            "arctic_lateral_ocean_heat_transport_wm2_per_ice_fraction": cfg.arctic_lateral_ocean_heat_transport_wm2_per_ice_fraction,
            "arctic_atlantic_reference_ocean_temperature_c": cfg.arctic_atlantic_reference_ocean_temperature_c,
            "arctic_non_atlantic_reference_ocean_temperature_c": cfg.arctic_non_atlantic_reference_ocean_temperature_c,
            "arctic_reference_ocean_heat_capacity_wyr_m2_k": cfg.arctic_reference_ocean_heat_capacity_wyr_m2_k,
            "arctic_reference_ocean_restoring_wm2_k": cfg.arctic_reference_ocean_restoring_wm2_k,
            "arctic_air_low_pass_years": cfg.arctic_air_low_pass_years,
            "arctic_lapse_rate_feedback_wm2_k": cfg.arctic_lapse_rate_feedback_wm2_k,
            "arctic_full_cover_equivalent_thickness_m": cfg.arctic_full_cover_equivalent_thickness_m,
            "arctic_ice_concentration_exponent": cfg.arctic_ice_concentration_exponent,
            "arctic_greenland_marine_influence": cfg.arctic_greenland_marine_influence,
            "amoc_stratification_saturation_c": cfg.amoc_stratification_saturation_c,
            "amoc_convection_recovery_years": cfg.amoc_convection_recovery_years,
        },
        "metrics": metrics,
        "seasonal": seasonal,
        "greenland": greenland,
        "arctic_transient": arctic_transient_metrics(result),
        "sea_ice_validation": evaluate_sea_ice_result(result),
        "future_sea_ice": _future_sea_ice_metrics(result),
        "open_water_validation": _open_water_validation(result),
        "scientific_use": SCIENTIFIC_USE_METADATA,
    }


def _summary_ssp585_task() -> dict[str, float]:
    _, result = scenario_run(
        "ssp585", dt=0.05, record_every=COMMON_VALIDATION_SAMPLE_YEARS
    )
    return {
        "ssp585_amoc_decline_2100_percent": amoc_decline(
            annual_mean_frame(result.dataframe)
        ),
        **arctic_transient_metrics(result),
        "future_sea_ice": _future_sea_ice_metrics(result),
    }


def _pathway_summary_task(scenario: str) -> dict[str, float]:
    _, result = scenario_run(scenario, dt=0.05, record_every=0.1)
    annual = annual_mean_frame(common_validation_sample(result.dataframe))
    late = annual[(annual["year"] >= 2081.0) & (annual["year"] <= 2100.0)]
    return {
        "scenario": scenario,
        "warming_2081_2100_c": float(late["global_surface_warming_c"].mean()),
        "amoc_decline_2100_percent": amoc_decline(annual),
        "final_arctic_sea_ice_fraction": float(late["arctic_thermodynamic_sea_ice_fraction"].mean()),
        **arctic_transient_metrics(result),
    }


def _energy_audit_task() -> dict[str, float]:
    cfg = replace(
        ModelConfig(), scenario="step_2x", start_year=1850.0,
        duration_years=20.0, dt_years=0.01, record_every_years=0.01,
        auto_initialize_from_1850=False,
    )
    frame = run_segmented(cfg, segment_years=5.0).dataframe
    elapsed = frame["elapsed_years"].to_numpy(dtype=float)
    conversion = EARTH_AREA_M2 * SECONDS_PER_YEAR / 1.0e21
    integrated = float(np.trapezoid(frame["toa_imbalance_wm2"], elapsed) * conversion)
    bulk = float(np.trapezoid(frame["bulk_radiative_toa_imbalance_wm2"], elapsed) * conversion)
    arctic = float(np.trapezoid(frame["arctic_external_toa_anomaly_wm2"], elapsed) * conversion)
    actual = float(
        frame.iloc[-1]["total_resolved_heat_content_anomaly_zj"]
        - frame.iloc[0]["total_resolved_heat_content_anomaly_zj"]
    )
    residual = actual - integrated
    return {
        "years": 20.0,
        "actual_resolved_heat_gain_zj": actual,
        "resolved_system_toa_integrated_zj": integrated,
        "bulk_radiative_toa_integrated_zj": bulk,
        "explicit_arctic_toa_integrated_zj": arctic,
        "residual_zj": residual,
        "relative_residual_percent": 100.0 * residual / integrated,
    }


def _arctic_reference_task() -> dict[str, Any]:
    model = ProcessClimateModel(
        replace(
            ModelConfig(),
            scenario="constant",
            duration_years=1.0,
            auto_initialize_from_1850=False,
        )
    )
    mask = model.grid.lat >= model.config.arctic_module_full_latitude_deg
    result: dict[str, Any] = {
        "global_baseline_mean_c": float(
            np.sum(model.baseline_map_c * model.grid.map_area_weights)
        ),
        "arctic_ocean_baseline_mean_c_north_of_full_latitude": float(
            np.mean(model.baseline_ocean_c[mask])
        ),
        "arctic_ocean_baseline_min_c_north_of_full_latitude": float(
            np.min(model.baseline_ocean_c[mask])
        ),
        "arctic_ocean_baseline_max_c_north_of_full_latitude": float(
            np.max(model.baseline_ocean_c[mask])
        ),
        "freezing_temperature_c": model.config.arctic_interface_freezing_temperature_c,
        "periodic_closure_wyr_m2": float(model.arctic_reference_periodic_closure_wyr_m2),
        "spinup_convergence_wyr_m2": float(model.arctic_reference_spinup_convergence_wyr_m2),
        "periodic_closure_temperature_c": float(model.arctic_reference_periodic_closure_temperature_c),
        "spinup_convergence_temperature_c": float(model.arctic_reference_spinup_convergence_temperature_c),
        "spinup_years_completed": int(model.arctic_reference_spinup_years_completed),
    }
    weights = model.grid.band_area_weights[mask] * model.grid.ocean_fraction[mask]
    monthly_ice: list[float] = []
    monthly_interface: list[float] = []
    monthly_native_area: list[float] = []
    for month in range(1, 13):
        state = model._arctic_reference_state((month - 0.5) / 12.0)
        monthly_ice.append(float(np.average(state["ice_fraction"][mask], weights=weights)))
        monthly_interface.append(float(np.average(state["interface_temperature_c"][mask], weights=weights)))
        monthly_native_area.append(
            raw_northern_ice_area_million_km2(
                state["atlantic_effective_ice_fraction"],
                state["non_atlantic_effective_ice_fraction"],
                model.grid.lat,
                model.grid.atlantic_ocean_fraction_map,
                model.grid.ocean_fraction_map,
                model.grid.map_area_weights,
            )
        )
    north = model.grid.lat2d >= 0.0
    northern_ocean_area = float(
        np.sum(
            np.where(
                north,
                model.grid.ocean_fraction_map * model.grid.map_area_weights,
                0.0,
            )
        )
        * EARTH_AREA_M2
        / 1.0e12
    )
    zero_area, zero_extent = diagnosed_area_extent_million_km2(
        raw_area_million_km2=0.0,
        warming_c=0.0,
        calendar_year=2000.0 + (9.0 - 0.5) / 12.0,
        northern_ocean_area_million_km2=northern_ocean_area,
    )
    result["monthly_ocean_area_weighted_ice_fraction"] = monthly_ice
    result["monthly_ocean_area_weighted_interface_temperature_c"] = monthly_interface
    result["monthly_native_northern_ice_area_million_km2"] = monthly_native_area
    result["native_march_ice_area_million_km2"] = monthly_native_area[2]
    result["native_september_ice_area_million_km2"] = monthly_native_area[8]
    result["exact_zero_diagnosed_area_million_km2"] = zero_area
    result["exact_zero_diagnosed_extent_million_km2"] = zero_extent
    result["minimum_ice_month"] = int(np.argmin(monthly_ice)) + 1
    maximum_equivalent_thickness_m = 0.0
    emergency_cap_hits = 0
    emergency_cap_samples = 0
    for month in range(1, 13):
        state = model._arctic_reference_state((month - 0.5) / 12.0)
        for prefix in ("atlantic", "non_atlantic"):
            equivalent = np.asarray(state[f"{prefix}_ice_thickness_m"], dtype=float)
            maximum_equivalent_thickness_m = max(
                maximum_equivalent_thickness_m, float(np.max(equivalent))
            )
            emergency_cap_hits += int(
                np.count_nonzero(
                    np.isclose(
                        equivalent,
                        model.config.arctic_max_equivalent_thickness_m,
                        rtol=0.0,
                        atol=1.0e-8,
                    )
                )
            )
            emergency_cap_samples += int(equivalent.size)
    result["maximum_equivalent_ice_thickness_m"] = maximum_equivalent_thickness_m
    result["configured_emergency_thickness_cap_m"] = float(
        model.config.arctic_max_equivalent_thickness_m
    )
    result["emergency_thickness_cap_hits"] = emergency_cap_hits
    result["emergency_thickness_cap_samples"] = emergency_cap_samples
    result["emergency_thickness_cap_occupancy_fraction"] = float(
        emergency_cap_hits / max(emergency_cap_samples, 1)
    )
    sectors: dict[str, Any] = {}
    for prefix, fraction in (
        ("atlantic", model.grid.atlantic_ocean_fraction),
        ("non_atlantic", model.non_atlantic_ocean_fraction),
    ):
        sector_weights = model.grid.band_area_weights[mask] * fraction[mask]
        sector_monthly_ice: list[float] = []
        sector_monthly_interface: list[float] = []
        sector_monthly_open_water: list[float] = []
        sector_monthly_shallow_ocean: list[float] = []
        for month in range(1, 13):
            state = model._arctic_reference_state((month - 0.5) / 12.0)
            sector_monthly_ice.append(float(np.average(state[f"{prefix}_ice_fraction"][mask], weights=sector_weights)))
            sector_monthly_interface.append(float(np.average(state[f"{prefix}_interface_temperature_c"][mask], weights=sector_weights)))
            sector_monthly_open_water.append(float(np.average(state[f"{prefix}_open_water_temperature_c"][mask], weights=sector_weights)))
            sector_monthly_shallow_ocean.append(float(np.average(state[f"{prefix}_shallow_ocean_temperature_c"][mask], weights=sector_weights)))
        sectors[prefix] = {
            "monthly_ice_fraction": sector_monthly_ice,
            "monthly_interface_temperature_c": sector_monthly_interface,
            "monthly_open_water_temperature_c": sector_monthly_open_water,
            "monthly_shallow_ocean_temperature_c": sector_monthly_shallow_ocean,
            "maximum_open_water_temperature_c": max(sector_monthly_open_water),
            "shallow_ocean_seasonal_range_c": max(sector_monthly_shallow_ocean) - min(sector_monthly_shallow_ocean),
            "minimum_ice_fraction": min(sector_monthly_ice),
            "minimum_ice_month": int(np.argmin(sector_monthly_ice)) + 1,
        }
    result["sectors"] = sectors
    return result


def _arctic_reference_public_range_stress_task() -> dict[str, Any]:
    cfg = replace(
        ModelConfig(),
        duration_years=1.0,
        resolution_deg=10.0,
        arctic_basal_ocean_exchange_wm2_k=0.25,
        arctic_open_water_ocean_exchange_wm2_k=0.05,
        arctic_atlantic_reference_ocean_temperature_c=-1.8,
        arctic_non_atlantic_reference_ocean_temperature_c=-1.8,
        arctic_reference_ocean_heat_capacity_wyr_m2_k=20.0,
        arctic_reference_ocean_restoring_wm2_k=2.0,
        arctic_open_water_stable_exchange_wm2_k=3.0,
        arctic_open_water_unstable_exchange_wm2_k=3.0,
        arctic_lateral_ocean_heat_transport_wm2_per_ice_fraction=2.0,
    )
    model = ProcessClimateModel(cfg)
    return {
        "minimum_spinup_years": int(cfg.arctic_reference_spinup_years),
        "maximum_spinup_years": int(cfg.arctic_reference_max_spinup_years),
        "spinup_years_completed": int(model.arctic_reference_spinup_years_completed),
        "periodic_closure_wyr_m2": float(model.arctic_reference_periodic_closure_wyr_m2),
        "spinup_convergence_wyr_m2": float(model.arctic_reference_spinup_convergence_wyr_m2),
        "tolerance_wyr_m2": float(cfg.arctic_reference_convergence_tolerance_wyr_m2),
        "adapted_beyond_minimum": bool(
            model.arctic_reference_spinup_years_completed
            > cfg.arctic_reference_spinup_years
        ),
    }


def _disabled_arctic_initialization_task() -> dict[str, Any]:
    cfg = replace(
        ModelConfig(),
        duration_years=1.0,
        seasonal_arctic_enabled=False,
        auto_initialize_from_1850=False,
    )
    model = ProcessClimateModel(cfg)
    result = model.run()
    summary = result.summary()
    return {
        "spinup_years_completed": int(model.arctic_reference_spinup_years_completed),
        "periodic_closure_wyr_m2": float(model.arctic_reference_periodic_closure_wyr_m2),
        "maximum_pre_projection_salt_conservation_error_ppm": float(
            summary["maximum_pre_projection_salt_conservation_error_ppm"]
        ),
    }


def _monte_carlo_safety_task() -> dict[str, Any]:
    valid = ProcessClimateModel(
        replace(ModelConfig(), duration_years=1.0, auto_initialize_from_1850=False)
    ).run().summary()
    invalid = dict(valid)
    invalid.update(
        {
            "maximum_arctic_open_water_temperature_c": 5000.0,
            "maximum_dormant_arctic_open_water_heat_wyr_m2": 1.0,
            "maximum_pre_projection_salt_conservation_error_ppm": 99.0,
        }
    )
    weights, logweights, reasons, targets = compute_importance_weights(
        [{"summary": valid}, {"summary": invalid}], "none"
    )
    return {
        "weights": [float(value) for value in weights],
        "logweights": [float(value) for value in logweights],
        "reasons": reasons,
        "targets": targets,
        "invalid_member_rejected": bool(
            weights[1] == 0.0
            and not np.isfinite(logweights[1])
            and bool(reasons[1])
        ),
    }


def _cross_resolution_task(resolution: float) -> dict[str, Any]:
    control_config = replace(
        ModelConfig(),
        resolution_deg=resolution,
        scenario="constant",
        duration_years=100.0,
        additional_forcing_wm2=0.0,
        record_every_years=100.0,
        auto_initialize_from_1850=False,
    )
    control_model = ProcessClimateModel(control_config)
    initial_ratio = control_model.baseline_density_driver_ratio
    mask = control_model.grid.lat >= control_model.config.arctic_module_full_latitude_deg
    sector_reference: dict[str, dict[str, float]] = {}
    for prefix, fraction in (
        ("atlantic", control_model.grid.atlantic_ocean_fraction),
        ("non_atlantic", control_model.non_atlantic_ocean_fraction),
    ):
        weights = control_model.grid.band_area_weights[mask] * fraction[mask]
        ice = getattr(control_model, f"arctic_reference_{prefix}_ice_fraction")
        open_temp = getattr(control_model, f"arctic_reference_{prefix}_open_water_temperature_c")
        interface = getattr(control_model, f"arctic_reference_{prefix}_interface_temperature_c")
        local_thickness = getattr(control_model, f"arctic_reference_{prefix}_local_ice_thickness_m")
        shallow = getattr(control_model, f"arctic_reference_{prefix}_shallow_ocean_temperature_c")
        ice_series = [float(np.average(ice[mask, i], weights=weights)) for i in range(ice.shape[1])]
        open_series = [float(np.average(open_temp[mask, i], weights=weights)) for i in range(open_temp.shape[1])]
        interface_series = [float(np.average(interface[mask, i], weights=weights)) for i in range(interface.shape[1])]
        thickness_series = []
        for i in range(local_thickness.shape[1]):
            ice_weights = weights * ice[mask, i]
            thickness_series.append(
                float(np.average(local_thickness[mask, i], weights=ice_weights))
                if float(np.sum(ice_weights)) > 0.0 else 0.0
            )
        shallow_series = [float(np.average(shallow[mask, i], weights=weights)) for i in range(shallow.shape[1])]
        sector_reference[prefix] = {
            "minimum_area_mean_ice_fraction": min(ice_series),
            "maximum_area_mean_open_water_temperature_c": max(open_series),
            "interface_temperature_seasonal_range_c": max(interface_series) - min(interface_series),
            "maximum_ice_weighted_local_thickness_m": max(thickness_series),
            "shallow_ocean_seasonal_range_c": max(shallow_series) - min(shallow_series),
        }
    control = run_segmented(control_config, segment_years=40.0).dataframe.iloc[-1]
    forced_result = run_segmented(
        replace(control_config, scenario="step_2x"), segment_years=40.0
    )
    forced = forced_result.dataframe.iloc[-1]
    return {
        "resolution_deg": resolution,
        "initial_density_driver_ratio": initial_ratio,
        "control_gmst_c": float(control["global_surface_warming_c"]),
        "control_amoc_sv": float(control["amoc_sv"]),
        "control_toa_imbalance_wm2": float(control["toa_imbalance_wm2"]),
        "abrupt_2x_100yr_gmst_c": float(forced["global_surface_warming_c"]),
        "abrupt_2x_100yr_amoc_sv": float(forced["amoc_sv"]),
        "abrupt_2x_100yr_toa_imbalance_wm2": float(forced["toa_imbalance_wm2"]),
        "arctic_reference": sector_reference,
        "abrupt_2x_arctic_transient": arctic_transient_metrics(forced_result),
    }


def _hybrid_amoc_task() -> dict[str, float]:
    cfg = replace(
        ModelConfig(),
        start_year=1850.0,
        duration_years=450.0,
        dt_years=0.1,
        record_every_years=1.0,
        scenario="hybrid_ssp",
        forcing_mode="total_effective",
        ssp_before="ssp585",
        ssp_after="ssp245",
        ssp_switch_year=2020.0,
        ssp_transition_years=20.0,
        auto_initialize_from_1850=False,
    )
    frame = ProcessClimateModel(cfg).run().dataframe
    years = frame["year"].to_numpy(dtype=float)
    index_2100 = int(np.argmin(np.abs(years - 2100.0)))
    return {
        "amoc_2100_sv": float(frame.iloc[index_2100]["amoc_sv"]),
        "minimum_amoc_sv": float(frame["amoc_sv"].min()),
        "final_amoc_sv": float(frame["amoc_sv"].iloc[-1]),
        "maximum_absolute_salt_error_ppm": float(frame["salt_conservation_error_ppm"].abs().max()),
    }


def _long_ssp245_task() -> dict[str, float]:
    cfg = replace(
        ModelConfig(),
        start_year=1850.0,
        duration_years=650.0,
        dt_years=0.1,
        record_every_years=10.0,
        scenario="ssp245",
        auto_initialize_from_1850=False,
    )
    frame = run_segmented(cfg, segment_years=40.0).dataframe
    years = frame["year"].to_numpy(dtype=float)
    index_2100 = int(np.argmin(np.abs(years - 2100.0)))
    return {
        "amoc_2100_sv": float(frame.iloc[index_2100]["amoc_sv"]),
        "minimum_amoc_sv": float(frame["amoc_sv"].min()),
        "final_amoc_sv": float(frame["amoc_sv"].iloc[-1]),
        "final_greenland_remaining_fraction": float(frame["greenland_remaining_fraction"].iloc[-1]),
        "maximum_absolute_salt_error_ppm": float(frame["salt_conservation_error_ppm"].abs().max()),
    }


def _run_named_task(name: str) -> Any:
    if name == "summary_ssp245":
        return _summary_ssp245_task()
    if name == "summary_ssp585":
        return _summary_ssp585_task()
    if name == "summary_ssp126":
        return _pathway_summary_task("ssp126")
    if name == "summary_ssp460":
        return _pathway_summary_task("ssp460")
    if name == "energy_audit":
        return _energy_audit_task()
    if name == "arctic_reference":
        return _arctic_reference_task()
    if name == "arctic_reference_public_range_stress":
        return _arctic_reference_public_range_stress_task()
    if name == "disabled_arctic_initialization":
        return _disabled_arctic_initialization_task()
    if name == "monte_carlo_safety":
        return _monte_carlo_safety_task()
    if name == "control":
        return control_check()
    if name == "perturbation_cold":
        return perturbation_check(-1.0)
    if name == "perturbation_warm":
        return perturbation_check(1.0)
    if name == "hosing_recovery":
        return hosing_recovery(ModelConfig())
    if name == "hybrid_amoc":
        return _hybrid_amoc_task()
    if name == "long_ssp245":
        return _long_ssp245_task()
    if name.startswith("timestep_"):
        return timestep_metrics(float(name.split("_", 1)[1].replace("p", ".")))
    if name.startswith("resolution_"):
        return _cross_resolution_task(
            float(name.split("_", 1)[1].replace("p", "."))
        )
    raise ValueError(f"Unknown validation task: {name}")


def _run_task_subprocess(name: str, directory: Path) -> Any:
    output = directory / f"{name}.json"
    command = [
        sys.executable,
        "-u",
        str(Path(__file__).resolve()),
        "--task",
        name,
        "--task-output",
        str(output),
    ]
    env = os.environ.copy()
    env.setdefault("OPENBLAS_NUM_THREADS", "1")
    env.setdefault("OMP_NUM_THREADS", "1")
    env.setdefault("MKL_NUM_THREADS", "1")
    env.setdefault("NUMEXPR_NUM_THREADS", "1")
    print(f"Running validation task: {name}", flush=True)
    subprocess.run(command, cwd=ROOT, env=env, check=True, timeout=1800)
    return json.loads(output.read_text(encoding="utf-8"))


def _assemble_records(tasks: dict[str, Any]) -> None:
    """Assemble v2.29.9 records with evidence and release gates separated."""
    ssp245 = tasks["summary_ssp245"]
    ssp585 = tasks["summary_ssp585"]
    benchmark_doc = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
    benchmark_metrics = dict(ssp245["metrics"])
    benchmark_metrics["ssp585_amoc_decline_2100_percent"] = float(
        ssp585["ssp585_amoc_decline_2100_percent"]
    )
    benchmark_metrics["greenland_ssp245_sea_level_2100_mm"] = float(
        ssp245["greenland"]["cumulative_sea_level_2100_mm"]
    )
    benchmark_results = evaluate_benchmarks(benchmark_metrics, benchmark_doc)

    cross_resolution_records = [
        tasks["resolution_2p5"], tasks["resolution_5p0"], tasks["resolution_10p0"]
    ]
    density_ratios = [float(item["initial_density_driver_ratio"]) for item in cross_resolution_records]
    density_ratio_spread = max(density_ratios) - min(density_ratios)

    timestep = [tasks["timestep_0p1"], tasks["timestep_0p05"], tasks["timestep_0p025"]]
    reference = timestep[1]
    timestep_temperatures = [
        item["maximum_arctic_open_water_temperature_c_at_5pct_open"] for item in timestep
    ]
    abrupt_values = [
        item["abrupt_2x_arctic_transient"]["maximum_arctic_open_water_temperature_c_at_5pct_open"]
        for item in cross_resolution_records
    ]
    sea_ice = ssp245["sea_ice_validation"]
    ssp245_future = ssp245["future_sea_ice"]
    ssp585_future = ssp585["future_sea_ice"]
    open_water = ssp245["open_water_validation"]
    cfg = ModelConfig()
    salt_limit = cfg.salt_projection_max_residual_ppm

    development_checks = {
        "literature_regression_envelopes": bool(all(item["passed"] for item in benchmark_results.values())),
        "native_sea_ice_calibration_diagnostics": bool(sea_ice["calibration_passed"]),
        "validation_informed_2021_2025_diagnostics": bool(
            sea_ice["validation_informed_development_evaluation_passed"]
        ),
        "robust_march_trend_diagnostic": bool(
            sea_ice["march_native_area_trend_robustness"]["passed"]
        ),
        "oisst_descriptive_bounds": bool(open_water["bounds_passed"]),
        "ssp245_amoc_decline_15_to_40_percent": bool(
            15.0 <= ssp245["metrics"]["ssp245_amoc_decline_2100_percent"] <= 40.0
        ),
        "ssp585_amoc_decline_25_to_55_percent": bool(
            25.0 <= ssp585["ssp585_amoc_decline_2100_percent"] <= 55.0
        ),
        "greenland_ssp245_60_to_105_mm": bool(
            60.0 <= ssp245["greenland"]["cumulative_sea_level_2100_mm"] <= 105.0
        ),
    }

    scenario_safety_records = [
        ssp245["arctic_transient"], ssp585, tasks["summary_ssp126"], tasks["summary_ssp460"],
        *timestep, *(item["abrupt_2x_arctic_transient"] for item in cross_resolution_records),
    ]

    release_checks = {
        "v2299_version": MODEL_VERSION == "2.29.9",
        "meinshausen2020_default": cfg.co2_forcing_formula == "meinshausen2020",
        "five_percent_unresolved_lead_threshold": abs(
            ARCTIC_MINIMUM_SENSIBLE_OPEN_FRACTION - 0.05
        ) <= 1.0e-12,
        "historical_scores_are_non_release_blocking": bool(
            sea_ice.get("historical_scores_are_release_blocking") is False
            and sea_ice.get("quantitative_temporal_skill_claim", {}).get("claimed") is False
        ),
        "prospective_evaluation_reserved_from_2027": bool(
            sea_ice["prospective_untouched_temporal_evaluation"]["start_year"] >= 2027
            and sea_ice["prospective_untouched_temporal_evaluation"]["independent_predictive_validation"]
        ),
        "sea_ice_dataset_hashes": bool(
            sea_ice["dataset_metadata"].get("packaged_file_hashes_match", False)
        ),
        "continuous_monotone_identity_area_operator": bool(
            sea_ice["area_operator"]["mapping"] == "identity"
            and sea_ice["area_operator"]["zero_preserving"]
            and sea_ice["area_operator"]["continuous"]
            and sea_ice["area_operator"]["monotone"]
            and not sea_ice["area_operator"]["statistical_area_correction"]
        ),
        "future_area_mapping_is_identity": bool(
            ssp245_future["maximum_area_identity_error_million_km2"] <= 1.0e-10
            and ssp585_future["maximum_area_identity_error_million_km2"] <= 1.0e-10
        ),
        "future_sea_ice_is_sensitivity_not_prediction": bool(
            all(
                item["evidence_role"]
                == "native_thermodynamic_area_sensitivity_with_secondary_extent_operator"
                and item["used_for_tuning"] is False
                and item["independent_predictive_validation"] is False
                and "not a forecast" in item["interpretation"]
                for item in (ssp245_future, ssp585_future)
            )
        ),
        "secondary_extent_is_bounded": bool(
            ssp245_future["september_extent_2081_2100_million_km2"]
            >= ssp245_future["september_area_2081_2100_million_km2"]
            and ssp245_future["september_extent_2081_2100_million_km2"]
            <= 1.50 * max(ssp245_future["september_area_2081_2100_million_km2"], 1.0e-12)
        ),
        "sea_ice_forcing_ordering": bool(
            ssp585_future["september_area_2081_2100_million_km2"]
            <= ssp245_future["september_area_2081_2100_million_km2"]
            and ssp585_future["september_extent_2081_2100_million_km2"]
            <= ssp245_future["september_extent_2081_2100_million_km2"]
            and ssp585_future["native_september_area_2081_2100_million_km2"]
            <= ssp245_future["native_september_area_2081_2100_million_km2"]
        ),
        "oisst_is_descriptive_nonblocking": bool(
            open_water["release_gate_role"] == "descriptive_non_blocking_sanity_bounds"
            and open_water["quantitative_validation_claimed"] is False
            and open_water["source_artifacts_reproduced"] is False
            and open_water["used_for_tuning"] is True
            and bool(open_water["mandatory_warning"])
        ),
        "zero_lateral_restoring_is_supported": bool(
            cfg.arctic_lateral_ocean_heat_transport_wm2_per_ice_fraction >= 0.0
        ),
        "energy_budget": abs(tasks["energy_audit"]["relative_residual_percent"]) <= 0.25,
        "continuous_control_balance": abs(tasks["control"]["corrected_gmst_drift_c"]) <= 1.0e-10,
        "control_stability": bool(
            abs(tasks["control"]["corrected_gmst_drift_c"]) <= 1.0e-3
            and abs(tasks["control"]["corrected_amoc_drift_sv"]) <= 1.0e-3
            and abs(tasks["control"]["final_salt_conservation_error_ppm"]) <= 1.0e-8
            and tasks["control"]["maximum_pre_projection_salt_conservation_error_ppm"] <= salt_limit
        ),
        "uncorrected_control_drift_reported": bool(
            all(np.isfinite(tasks["control"][key]) for key in (
                "uncorrected_gmst_drift_c", "uncorrected_amoc_drift_sv", "uncorrected_final_toa_imbalance_wm2"
            ))
        ),
        "reference_cycle_closure": bool(
            tasks["arctic_reference"]["periodic_closure_wyr_m2"] <= 1.0e-8
            and tasks["arctic_reference"]["spinup_convergence_wyr_m2"] <= 1.0e-8
            and tasks["arctic_reference"]["periodic_closure_temperature_c"] <= 1.0e-8
            and tasks["arctic_reference"]["spinup_convergence_temperature_c"] <= 1.0e-8
        ),
        "public_range_reference_cycle_convergence": bool(
            tasks["arctic_reference_public_range_stress"]["spinup_years_completed"]
            <= tasks["arctic_reference_public_range_stress"]["maximum_spinup_years"]
            and tasks["arctic_reference_public_range_stress"]["periodic_closure_wyr_m2"]
            <= tasks["arctic_reference_public_range_stress"]["tolerance_wyr_m2"]
            and tasks["arctic_reference_public_range_stress"]["spinup_convergence_wyr_m2"]
            <= tasks["arctic_reference_public_range_stress"]["tolerance_wyr_m2"]
        ),
        "disabled_arctic_skips_reference_spinup": bool(
            tasks["disabled_arctic_initialization"]["spinup_years_completed"] == 0
            and tasks["disabled_arctic_initialization"]["periodic_closure_wyr_m2"] == 0.0
        ),
        "unconditional_monte_carlo_safety": bool(
            tasks["monte_carlo_safety"]["invalid_member_rejected"]
        ),
        "pre_projection_salt_integrity": bool(
            all(item["maximum_pre_projection_salt_conservation_error_ppm"] <= salt_limit
                for item in scenario_safety_records)
        ),
        "timestep_local_arctic_convergence": bool(
            max(timestep_temperatures) <= 15.0
            and max(timestep_temperatures) - min(timestep_temperatures) <= 2.0
        ),
        "resolution_local_arctic_convergence": bool(
            max(abrupt_values) <= 20.0 and max(abrupt_values) - min(abrupt_values) <= 5.0
        ),
        "canonical_amoc_initialization_spread_le_0p20": density_ratio_spread <= 0.20,
        "hosing_recovery_ge_80_percent": bool(
            tasks["hosing_recovery"]["recovery_percent_of_initial_loss"] >= 80.0
        ),
        "hybrid_2100_amoc_restored_to_10_14_sv": bool(
            10.0 < tasks["hybrid_amoc"]["amoc_2100_sv"] < 14.0
        ),
        "long_ssp245_single_year_2100_floor_restored": bool(
            10.0 < tasks["long_ssp245"]["amoc_2100_sv"] < 14.0
        ),
        "perturbation_recovery": bool(
            all(abs(item["final_arctic_air_c"]) <= 0.01 and item["final_amoc_sv"] >= 16.9
                for item in (tasks["perturbation_cold"], tasks["perturbation_warm"]))
        ),
        "perturbation_salt_conservation": bool(
            all(abs(item["final_salt_conservation_error_ppm"]) <= 1.0e-8
                and item["maximum_pre_projection_salt_conservation_error_ppm"] <= salt_limit
                for item in (tasks["perturbation_cold"], tasks["perturbation_warm"]))
        ),
        "ssp245_arctic_temperature_guard": bool(
            ssp245["arctic_transient"]["maximum_arctic_open_water_temperature_c"] <= 20.0
            and ssp245["arctic_transient"]["maximum_arctic_open_water_temperature_c_at_5pct_open"] <= 15.0
            and ssp245["arctic_transient"]["maximum_dormant_arctic_open_water_heat_wyr_m2"] <= 1.0e-10
        ),
        "ssp585_arctic_temperature_guard": bool(
            ssp585["maximum_arctic_open_water_temperature_c"] <= 30.0
            and ssp585["maximum_arctic_open_water_temperature_c_at_5pct_open"] <= 20.0
            and ssp585["maximum_dormant_arctic_open_water_heat_wyr_m2"] <= 1.0e-10
        ),
    }

    summary = {
        "model_version": MODEL_VERSION,
        "classification": "scientific-review-corrected reduced-complexity sensitivity emulator; no independent historical Arctic temporal validation",
        "development_metrics": benchmark_metrics,
        "development_benchmark_results": benchmark_results,
        "development_checks_non_release_blocking": development_checks,
        "all_development_checks_passed": bool(all(development_checks.values())),
        "sea_ice_historical_diagnostics": sea_ice,
        "ssp245_future_sea_ice_sensitivity": ssp245_future,
        "ssp585_future_sea_ice_sensitivity": ssp585_future,
        "open_water_descriptive_sanity_bounds": open_water,
        "greenland_ssp245": ssp245["greenland"],
        "ssp245_amoc_decline_2100_percent": ssp245["metrics"]["ssp245_amoc_decline_2100_percent"],
        "ssp585_amoc_decline_2100_percent": ssp585["ssp585_amoc_decline_2100_percent"],
        "hosing_recovery": tasks["hosing_recovery"],
        "hybrid_amoc": tasks["hybrid_amoc"],
        "long_ssp245": tasks["long_ssp245"],
        "cross_resolution_initial_density_driver_ratio_spread": density_ratio_spread,
        "release_checks": release_checks,
        "all_release_checks_passed": bool(all(release_checks.values())),
        "scientific_use": SCIENTIFIC_USE_METADATA,
        "provenance": {
            "benchmark_file": BENCHMARK_PATH.name,
            "benchmark_file_sha256": sha256_file(BENCHMARK_PATH),
            "benchmark_set_version": benchmark_doc["benchmark_set_version"],
            "processing_script": Path(__file__).name,
            "processing_script_sha256": sha256_file(Path(__file__)),
            "climate_model_sha256": sha256_file(ROOT / "climate_model.py"),
        },
    }

    deep = {
        "model_version": MODEL_VERSION,
        "classification": summary["classification"],
        "tasks": tasks,
        "development_checks_non_release_blocking": development_checks,
        "release_checks": release_checks,
        "all_release_checks_passed": summary["all_release_checks_passed"],
        "timestep_differences_from_0p05": {
            str(item["dt_years"]): {
                key: float(item[key] - reference[key])
                for key in reference if key not in {"dt_years", "sample_cadence_years"}
            }
            for item in timestep if item["dt_years"] != 0.05
        },
        "cross_resolution_initial_density_driver_ratios": density_ratios,
        "cross_resolution_initial_density_driver_ratio_spread": density_ratio_spread,
    }

    write_json("VALIDATION_SUMMARY_V2_29_9.json", summary)
    write_json("DEEP_VALIDATION_V2_29_9.json", deep)

    audit_source_names = (
        "climate_model.py", "monte_carlo.py", "app.py", "climate_model_gui.py",
        "setting_metadata.py", "run_state.py", "co2_target_sweep.py",
        "sea_ice_observation.py", "sea_ice_validation.py", "scientific_evidence.py",
        "development_regression_benchmarks.json", "validate_v2299.py",
        "tests/test_v2299_scientific_review_fixes.py", "tests/test_v2298_resumable_sweeps.py",
        "V2_29_9_SCIENTIFIC_REVIEW_FIXES.md", "README.md", "CHANGELOG.md",
        "pyproject.toml", "requirements.lock", "requirements-dev.lock",
        "dependency_integrity.lock.json",
        "data/validation/nsidc/METADATA.json",
        "data/validation/nsidc/N_03_extent_v4.0.csv",
        "data/validation/nsidc/N_09_extent_v4.0.csv",
        "data/validation/open_water/NOAA_OISST_ARCTIC_BENCHMARKS.json",
    )
    audit = {
        "model_version": MODEL_VERSION,
        "source_files": {name: sha256_file(ROOT / name) for name in audit_source_names},
        "implemented_review_fixes": {
            "historical_temporal_skill_claim_removed": True,
            "historical_scores_non_release_blocking": True,
            "nonoverlapping_five_year_blocks": True,
            "robust_march_trend_period_uncertainty_diagnostics": True,
            "conservative_native_ice_compactness_curve": True,
            "zero_lateral_restoring_configuration": True,
            "twenty_percent_zero_restoring_monte_carlo_branch": True,
            "oisst_descriptive_nonblocking_without_reproduction_claim": True,
            "public_ranges_cover_documented_priors": True,
            "cross_domain_recalibration_recorded": True,
            "future_extent_and_timing_are_sensitivity_outputs": True,
            "v2298_resume_and_explicit_target_features_retained": True,
        },
        "configuration_snapshot": asdict(ModelConfig()),
        "release_checks": release_checks,
        "development_checks_non_release_blocking": development_checks,
    }
    write_json("IMPLEMENTATION_AUDIT_V2_29_9.json", audit)

    print(json.dumps({
        "model_version": MODEL_VERSION,
        "development_checks_non_release_blocking": development_checks,
        "release_checks": release_checks,
        "all_release_checks_passed": summary["all_release_checks_passed"],
    }, indent=2), flush=True)
    if not summary["all_release_checks_passed"]:
        failed = [name for name, passed in release_checks.items() if not passed]
        raise SystemExit("v2.29.9 release validation failed: " + ", ".join(failed))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task")
    parser.add_argument("--task-output", type=Path)
    args = parser.parse_args()
    if args.task:
        if args.task_output is None:
            raise SystemExit("--task-output is required with --task")
        value = _run_named_task(args.task)
        args.task_output.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        print(f"Completed validation task: {args.task}", flush=True)
        return

    task_names = [
        "summary_ssp245", "summary_ssp585", "summary_ssp126", "summary_ssp460",
        "energy_audit", "arctic_reference", "arctic_reference_public_range_stress",
        "disabled_arctic_initialization", "monte_carlo_safety", "timestep_0p1",
        "timestep_0p05", "timestep_0p025", "control", "perturbation_cold",
        "perturbation_warm", "hosing_recovery", "hybrid_amoc", "long_ssp245",
        "resolution_2p5", "resolution_5p0", "resolution_10p0",
    ]
    with tempfile.TemporaryDirectory(prefix="validation_v2299_") as directory:
        task_root = Path(directory)
        tasks = {name: _run_task_subprocess(name, task_root) for name in task_names}
    _assemble_records(tasks)


if __name__ == "__main__":
    main()
