#!/usr/bin/env python3
"""Version-matched v2.29.22 scientific and engineering validation.

The validator runs one production SSP2-4.5 trajectory from 1850 through 2100
at the requested resolution, evaluates historical and 2021-2025 sea ice from
that same result, and runs a matched no-Greenland-freshwater sensitivity case.
All files are generated from the current source tree and carry source hashes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from climate_model import EARTH_AREA_M2, MODEL_VERSION, ModelConfig, ProcessClimateModel
from arctic_process_budget import evaluate_arctic_process_ledger
from sea_ice_validation import evaluate_result
from validation_segmentation import _combine_results

EXPECTED_VERSION = "2.29.22"
SELECTED_TIMESERIES_COLUMNS = (
    "year",
    "co2_ppm",
    "total_prescribed_forcing_wm2",
    "global_surface_warming_c",
    "global_bulk_surface_warming_c",
    "global_near_surface_air_warming_c",
    "arctic_bulk_surface_warming_c",
    "arctic_near_surface_air_warming_c",
    "arctic_filtered_near_surface_air_warming_c",
    "arctic_ocean_interface_temperature_c",
    "arctic_open_water_temperature_c",
    "arctic_local_ice_thickness_m",
    "arctic_sea_ice_equivalent_thickness_m",
    "northern_hemisphere_sea_ice_area_million_km2",
    "northern_hemisphere_sea_ice_extent_million_km2",
    "arctic_calendar_month",
    "greenland_temperature_driver_c",
    "greenland_reference_surface_temperature_c",
    "greenland_absolute_surface_temperature_c",
    "greenland_positive_degree_day_rate",
    "greenland_surface_melt_anomaly_gt_per_year",
    "greenland_snowfall_anomaly_gt_per_year",
    "greenland_net_surface_loss_gt_per_year",
    "greenland_applied_freshwater_sv",
    "greenland_annual_mean_freshwater_sv",
    "greenland_requested_freshwater_sv",
    "greenland_freshwater_target_sv",
    "greenland_remaining_ice_gt",
    "greenland_cumulative_melt_gt",
    "greenland_cumulative_accumulation_gt",
    "greenland_cumulative_net_ice_loss_gt",
    "greenland_cumulative_sea_level_mm",
    "amoc_sv",
    "amoc_weak_or_collapsed",
    "amoc_active",
    "amoc_convection_collapsed",
    "salt_conservation_error_ppm",
    "pre_projection_salt_conservation_error_ppm",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, np.ndarray):
        return json_ready(value.tolist())
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(json_ready(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_segmented_in_process(
    config: ModelConfig,
    *,
    segment_years: float,
    label: str,
) -> Any:
    """Run deterministic integral-year segments while reusing reference cache."""

    state = None
    results: list[tuple[float, Any]] = []
    start = 0.0
    maximum_salt = 0.0
    cumulative_salt = 0.0
    started = time.perf_counter()
    while start < config.duration_years - 1.0e-12:
        duration = min(float(segment_years), config.duration_years - start)
        segment = replace(
            config,
            start_year=float(config.start_year + start),
            duration_years=float(duration),
            auto_initialize_from_1850=False,
        )
        model = ProcessClimateModel(segment)
        if state is not None:
            model.state = state.copy()
            model._maximum_pre_projection_salt_error_ppm = maximum_salt
            model._cumulative_absolute_salt_projection_correction_psu_m3 = (
                cumulative_salt
            )
        result = model.run()
        results.append((start, result))
        state = model.state.copy()
        maximum_salt = float(model._maximum_pre_projection_salt_error_ppm)
        cumulative_salt = float(
            model._cumulative_absolute_salt_projection_correction_psu_m3
        )
        start += duration
        print(
            f"{label}: {start:.0f}/{config.duration_years:.0f} years "
            f"elapsed={time.perf_counter() - started:.1f}s",
            flush=True,
        )
    return _combine_results(results, config)


def weighted_latitude_mean(values: np.ndarray, weights: np.ndarray) -> float:
    valid = np.isfinite(values) & np.isfinite(weights) & (weights > 0.0)
    if not np.any(valid):
        return float("nan")
    return float(np.sum(values[valid] * weights[valid]) / np.sum(weights[valid]))


def sector_monthly_arctic_temperatures(result: Any, late_mask: np.ndarray) -> list[dict[str, Any]]:
    df = result.dataframe
    lat = result.grid.lat
    arctic = (lat >= result.config.arctic_module_full_latitude_deg).astype(float)
    atl_weights = result.grid.band_area_weights * result.grid.atlantic_ocean_fraction * arctic
    non_fraction = np.clip(
        result.grid.ocean_fraction - result.grid.atlantic_ocean_fraction,
        0.0,
        1.0,
    )
    non_weights = result.grid.band_area_weights * non_fraction * arctic
    records: list[dict[str, Any]] = []
    months = np.rint(df["arctic_calendar_month"].to_numpy(dtype=float)).astype(int)
    for month in range(1, 13):
        indices = np.flatnonzero(late_mask & (months == month))
        atl_air: list[float] = []
        non_air: list[float] = []
        atl_interface: list[float] = []
        non_interface: list[float] = []
        atl_open: list[float] = []
        non_open: list[float] = []
        for index in indices:
            atl_air.append(
                weighted_latitude_mean(
                    result.arctic_reference_atlantic_air_temperature_history_c[index]
                    + result.arctic_atlantic_air_low_pass_history_c[index],
                    atl_weights,
                )
            )
            non_air.append(
                weighted_latitude_mean(
                    result.arctic_reference_non_atlantic_air_temperature_history_c[index]
                    + result.arctic_non_atlantic_air_low_pass_history_c[index],
                    non_weights,
                )
            )
            atl_interface.append(
                weighted_latitude_mean(
                    result.arctic_atlantic_interface_temperature_history_c[index],
                    atl_weights,
                )
            )
            non_interface.append(
                weighted_latitude_mean(
                    result.arctic_non_atlantic_interface_temperature_history_c[index],
                    non_weights,
                )
            )
            atl_open_weights = atl_weights * np.clip(
                1.0 - result.atlantic_sea_ice_history[index], 0.0, 1.0
            )
            non_open_weights = non_weights * np.clip(
                1.0 - result.non_atlantic_sea_ice_history[index], 0.0, 1.0
            )
            atl_open.append(
                weighted_latitude_mean(
                    result.arctic_atlantic_open_water_temperature_history_c[index],
                    atl_open_weights,
                )
            )
            non_open.append(
                weighted_latitude_mean(
                    result.arctic_non_atlantic_open_water_temperature_history_c[index],
                    non_open_weights,
                )
            )
        def finite_mean(items: list[float]) -> float:
            values = np.asarray(items, dtype=float)
            values = values[np.isfinite(values)]
            return float(np.mean(values)) if values.size else float("nan")

        records.append(
            {
                "month": month,
                "atlantic_arctic_air_absolute_c": finite_mean(atl_air),
                "non_atlantic_arctic_air_absolute_c": finite_mean(non_air),
                "atlantic_arctic_interface_absolute_c": finite_mean(atl_interface),
                "non_atlantic_arctic_interface_absolute_c": finite_mean(non_interface),
                "atlantic_arctic_open_water_absolute_c": finite_mean(atl_open),
                "non_atlantic_arctic_open_water_absolute_c": finite_mean(non_open),
            }
        )
    return records


def greenland_monthly_summary(df: pd.DataFrame, late_mask: np.ndarray) -> list[dict[str, Any]]:
    months = np.rint(df["arctic_calendar_month"].to_numpy(dtype=float)).astype(int)
    records: list[dict[str, Any]] = []
    fields = (
        "greenland_temperature_driver_c",
        "greenland_reference_surface_temperature_c",
        "greenland_absolute_surface_temperature_c",
        "greenland_positive_degree_day_rate",
        "greenland_surface_melt_anomaly_gt_per_year",
        "greenland_snowfall_anomaly_gt_per_year",
        "greenland_net_surface_loss_gt_per_year",
        "greenland_applied_freshwater_sv",
        "greenland_freshwater_target_sv",
    )
    for month in range(1, 13):
        mask = late_mask & (months == month)
        record: dict[str, Any] = {"month": month}
        for field in fields:
            values = df.loc[mask, field].to_numpy(dtype=float)
            record[f"mean_{field}"] = float(np.mean(values)) if values.size else float("nan")
            record[f"maximum_{field}"] = float(np.max(values)) if values.size else float("nan")
        records.append(record)
    return records


def _volume_identity_error(
    concentration: np.ndarray,
    equivalent_thickness_m: np.ndarray,
) -> float:
    concentration = np.asarray(concentration, dtype=float)
    equivalent = np.asarray(equivalent_thickness_m, dtype=float)
    local = np.divide(
        equivalent,
        concentration,
        out=np.zeros_like(equivalent),
        where=concentration > 1.0e-14,
    )
    reconstructed = local * concentration
    return float(np.max(np.abs(reconstructed - equivalent)))


def _set_integrated_arctic_state(
    model: ProcessClimateModel,
    *,
    elapsed_years: float,
    equivalent_thickness_m: float,
    concentration: float,
    air_anomaly_c: float,
    ocean_anomaly_c: float,
) -> None:
    reference = model._arctic_reference_state(elapsed_years)
    shape = model.grid.lat.shape
    target_energy = (
        -model.arctic_latent_energy_per_m_wyr_m2
        * np.full(shape, equivalent_thickness_m)
    )
    for prefix in ("atlantic", "non_atlantic"):
        setattr(
            model.state,
            f"arctic_{prefix}_ice_energy_anomaly_wyr_m2",
            target_energy - reference[f"{prefix}_ice_energy_wyr_m2"],
        )
        setattr(
            model.state,
            f"arctic_{prefix}_ice_concentration_anomaly",
            np.full(shape, concentration)
            - reference[f"{prefix}_ice_fraction"],
        )
        setattr(
            model.state,
            f"arctic_{prefix}_air_anomaly_c",
            np.full(shape, air_anomaly_c),
        )
        setattr(
            model.state,
            f"arctic_{prefix}_air_low_pass_c",
            np.full(shape, air_anomaly_c),
        )
    model.state.atlantic_ocean_anomaly_c[:] = ocean_anomaly_c
    model.state.non_atlantic_ocean_anomaly_c[:] = ocean_anomaly_c
    model.state.land_anomaly_c[:] = 0.5 * air_anomaly_c


def _integrated_arctic_state_metrics(
    model: ProcessClimateModel,
    elapsed_years: float,
) -> dict[str, float]:
    reference = model._arctic_reference_state(elapsed_years)
    full_arctic = model.arctic_module_blend >= 0.99
    concentrations: list[float] = []
    equivalents: list[float] = []
    identity_errors: list[float] = []
    for prefix in ("atlantic", "non_atlantic"):
        energy = (
            reference[f"{prefix}_ice_energy_wyr_m2"]
            + getattr(model.state, f"arctic_{prefix}_ice_energy_anomaly_wyr_m2")
        )
        concentration, equivalent, local = (
            model._arctic_state_from_energy_and_concentration(
                energy,
                reference[f"{prefix}_ice_fraction"]
                + getattr(
                    model.state,
                    f"arctic_{prefix}_ice_concentration_anomaly",
                ),
            )
        )
        sector_fraction = (
            model.grid.atlantic_ocean_fraction
            if prefix == "atlantic"
            else model.non_atlantic_ocean_fraction
        )
        weights = model.grid.band_area_weights * sector_fraction * full_arctic
        concentrations.append(weighted_latitude_mean(concentration, weights))
        equivalents.append(weighted_latitude_mean(equivalent, weights))
        identity_errors.append(
            float(np.max(np.abs(concentration * local - equivalent)))
        )
    return {
        "averaging_domain": "ocean-area-weighted full Arctic module (blend >= 0.99)",
        "mean_concentration": float(np.mean(concentrations)),
        "mean_equivalent_thickness_m": float(np.mean(equivalents)),
        "maximum_volume_identity_error_m": float(max(identity_errors)),
    }


def integrated_production_path_ice_experiments(
    config: ModelConfig,
) -> dict[str, Any]:
    experiment_config = replace(
        config,
        start_year=1850.0,
        duration_years=1.0,
        dt_years=0.05,
        record_every_years=0.05,
        auto_initialize_from_1850=False,
    )

    loss_model = ProcessClimateModel(experiment_config)
    _set_integrated_arctic_state(
        loss_model,
        elapsed_years=0.0,
        equivalent_thickness_m=1.0,
        concentration=0.80,
        air_anomaly_c=20.0,
        ocean_anomaly_c=5.0,
    )
    loss_initial = _integrated_arctic_state_metrics(loss_model, 0.0)
    loss_records: list[dict[str, float]] = []
    for step_index in range(10):
        elapsed = step_index * experiment_config.dt_years
        loss_model.step(elapsed)
        loss_records.append(
            _integrated_arctic_state_metrics(
                loss_model, elapsed + experiment_config.dt_years
            )
        )
    loss_final = loss_records[-1]
    loss_minimum = min(
        loss_records, key=lambda item: item["mean_concentration"]
    )

    recovery_model = ProcessClimateModel(experiment_config)
    _set_integrated_arctic_state(
        recovery_model,
        elapsed_years=0.0,
        equivalent_thickness_m=0.0,
        concentration=0.0,
        air_anomaly_c=-20.0,
        ocean_anomaly_c=-3.0,
    )
    recovery_initial = _integrated_arctic_state_metrics(recovery_model, 0.0)
    recovery_records: list[dict[str, float]] = []
    for step_index in range(10):
        elapsed = step_index * experiment_config.dt_years
        recovery_model.step(elapsed)
        recovery_records.append(
            _integrated_arctic_state_metrics(
                recovery_model, elapsed + experiment_config.dt_years
            )
        )
    recovery_final = recovery_records[-1]

    maximum_identity_error = max(
        [item["maximum_volume_identity_error_m"] for item in loss_records]
        + [item["maximum_volume_identity_error_m"] for item in recovery_records]
    )
    checks = {
        "warm_production_path_reduces_concentration_by_at_least_25pct": bool(
            loss_minimum["mean_concentration"]
            <= 0.75 * loss_initial["mean_concentration"]
        ),
        "ice_free_production_path_recovers_positive_concentration": bool(
            recovery_final["mean_concentration"] >= 0.10
        ),
        "integrated_concentration_bounds_hold": bool(
            all(
                0.0 <= item["mean_concentration"] <= 1.0
                for item in loss_records + recovery_records
            )
        ),
        "integrated_volume_identity_error_le_1e_minus_10_m": bool(
            maximum_identity_error <= 1.0e-10
        ),
    }
    return {
        "method": "ordinary_ProcessClimateModel.step_production_integrator",
        "loss_initial": loss_initial,
        "loss_final": loss_final,
        "loss_minimum_concentration_state": loss_minimum,
        "recovery_initial": recovery_initial,
        "recovery_final": recovery_final,
        "maximum_volume_identity_error_m": maximum_identity_error,
        "checks": checks,
        "passed": bool(all(checks.values())),
    }


def structural_area_volume_experiments(config: ModelConfig) -> dict[str, Any]:
    """Evaluate conservation from terms emitted by production timesteps.

    Two deliberately perturbed ordinary model steps exercise formation, melt,
    export, phase restoring, ocean transfer, ridging, and divergence. The
    independent evaluator reconstructs final reservoirs from the raw ledger
    fields and never consumes a residual calculated by the model itself.
    """

    experiment_config = replace(
        config,
        start_year=1850.0,
        duration_years=0.1,
        dt_years=0.05,
        record_every_years=0.05,
        auto_initialize_from_1850=False,
    )

    def run_case(
        *,
        elapsed_years: float,
        air_anomaly_c: float,
        ocean_anomaly_c: float,
        ice_energy_anomaly_m: float,
        concentration_anomaly: float,
        asymmetric: bool,
    ) -> tuple[dict[str, Any], ...]:
        model = ProcessClimateModel(experiment_config)
        model.enable_arctic_process_ledger(True, clear=True)
        latent = model.arctic_latent_energy_per_m_wyr_m2
        if asymmetric:
            model.state.arctic_atlantic_air_anomaly_c[:] = air_anomaly_c
            model.state.arctic_non_atlantic_air_anomaly_c[:] = -air_anomaly_c
            model.state.atlantic_ocean_anomaly_c[:] = ocean_anomaly_c
            model.state.non_atlantic_ocean_anomaly_c[:] = -0.5 * ocean_anomaly_c
            model.state.arctic_atlantic_ice_energy_anomaly_wyr_m2[:] = (
                -abs(ice_energy_anomaly_m) * latent
            )
            model.state.arctic_non_atlantic_ice_energy_anomaly_wyr_m2[:] = (
                0.75 * abs(ice_energy_anomaly_m) * latent
            )
            model.state.arctic_atlantic_ice_concentration_anomaly[:] = (
                (2.0 / 3.0) * abs(concentration_anomaly)
            )
            model.state.arctic_non_atlantic_ice_concentration_anomaly[:] = -abs(
                concentration_anomaly
            )
        else:
            for prefix in ("atlantic", "non_atlantic"):
                getattr(model.state, f"arctic_{prefix}_air_anomaly_c")[:] = air_anomaly_c
                getattr(
                    model.state,
                    f"arctic_{prefix}_ice_energy_anomaly_wyr_m2",
                )[:] = abs(ice_energy_anomaly_m) * latent
                getattr(
                    model.state,
                    f"arctic_{prefix}_ice_concentration_anomaly",
                )[:] = -abs(concentration_anomaly)
            model.state.atlantic_ocean_anomaly_c[:] = ocean_anomaly_c
            model.state.non_atlantic_ocean_anomaly_c[:] = ocean_anomaly_c
        model.step(elapsed_years, dt_years=experiment_config.dt_years)
        return model.get_arctic_process_ledger()

    cold_entries = run_case(
        elapsed_years=0.50,
        air_anomaly_c=-15.0,
        ocean_anomaly_c=-3.0,
        ice_energy_anomaly_m=0.50,
        concentration_anomaly=0.20,
        asymmetric=False,
    )
    mixed_entries = run_case(
        elapsed_years=0.00,
        air_anomaly_c=-3.0,
        ocean_anomaly_c=0.0,
        ice_energy_anomaly_m=0.40,
        concentration_anomaly=0.15,
        asymmetric=True,
    )
    ledger_entries = cold_entries + mixed_entries
    ledger_summary = evaluate_arctic_process_ledger(
        ledger_entries,
        energy_tolerance_wyr_m2=1.0e-10,
        area_tolerance=1.0e-12,
        require_activity=True,
    )

    mutation_fields = {
        "formation": "formation_energy_change_wyr_m2",
        "melt": "melt_energy_change_wyr_m2",
        "mechanical_export": "mechanical_export_energy_change_wyr_m2",
        "phase_restoring": "phase_restoring_energy_change_wyr_m2",
        "ocean_transfer": "cleanup_ocean_transfer_wyr_m2",
        "ridging": "ridging_area_change",
        "divergence": "divergence_area_change",
    }
    mutation_checks: dict[str, bool] = {}
    mutation_residuals: dict[str, dict[str, float]] = {}
    for process, field in mutation_fields.items():
        mutated = [
            {
                key: value.copy() if isinstance(value, np.ndarray) else value
                for key, value in entry.items()
            }
            for entry in ledger_entries
        ]
        mutated[0][field] = np.asarray(mutated[0][field], dtype=float) + 1.0e-4
        result = evaluate_arctic_process_ledger(
            mutated,
            energy_tolerance_wyr_m2=1.0e-10,
            area_tolerance=1.0e-12,
            require_activity=False,
        )
        mutation_checks[f"{process}_corruption_detected"] = not result["passed"]
        mutation_residuals[process] = {
            "energy_wyr_m2": result[
                "maximum_energy_closure_residual_wyr_m2"
            ],
            "area": result["maximum_area_closure_residual"],
        }

    representative_model = ProcessClimateModel(experiment_config)
    representative_equivalent = np.asarray(
        [0.0, 1.0e-6, 1.0e-4, 1.0e-3, 1.0e-2, 0.05, 0.10, 1.0, 4.0],
        dtype=float,
    )
    representative_concentration = (
        representative_model._arctic_concentration_from_equivalent_thickness(
            representative_equivalent
        )
    )
    representation_identity_error = _volume_identity_error(
        representative_concentration, representative_equivalent
    )
    zero_area_nonzero_volume = bool(
        np.any(
            (representative_equivalent > 1.0e-14)
            & (representative_concentration <= 1.0e-14)
        )
    )
    integrated = integrated_production_path_ice_experiments(config)
    process_passed = bool(
        ledger_summary["passed"] and all(mutation_checks.values())
    )
    checks = {
        "production_process_ledger_closed": process_passed,
        "integrated_production_path_checks_passed": bool(integrated["passed"]),
        "no_zero_area_nonzero_volume_state": not zero_area_nonzero_volume,
    }
    return {
        "inputs": {
            "young_ice_local_thickness_m": config.arctic_new_ice_local_thickness_m,
            "full_cover_equivalent_thickness_m": config.arctic_full_cover_equivalent_thickness_m,
            "concentration_exponent": config.arctic_ice_concentration_exponent,
        },
        "process_budget_experiments": {
            "method": "production_ProcessClimateModel_step_raw_process_ledger",
            "case_entry_counts": {
                "cold_formation": len(cold_entries),
                "mixed_melt_export_mechanics": len(mixed_entries),
            },
            "ledger_evaluation": ledger_summary,
            "mutation_checks": mutation_checks,
            "mutation_residuals": mutation_residuals,
            "maximum_absolute_residual": max(
                ledger_summary["maximum_energy_closure_residual_wyr_m2"],
                ledger_summary["maximum_area_closure_residual"],
            ),
            "passed": process_passed,
        },
        "helper_level_outputs": {
            "representation_identity_error_m": representation_identity_error,
            "zero_area_nonzero_volume_detected": zero_area_nonzero_volume,
            "maximum_volume_identity_error_m": representation_identity_error,
        },
        "helper_level_checks": {
            "representation_identity_finite": bool(
                np.isfinite(representation_identity_error)
            ),
            "no_zero_area_nonzero_volume_state": not zero_area_nonzero_volume,
        },
        "helper_level_passed": bool(not zero_area_nonzero_volume),
        "integrated_production_path": integrated,
        "checks": checks,
        "passed": bool(all(checks.values())),
    }


def coupled_summary(result: Any, no_greenland_result: Any) -> dict[str, Any]:
    config = result.config
    df = result.dataframe
    no_greenland_df = no_greenland_result.dataframe
    years = df["year"].to_numpy(dtype=float)
    late_mask = (years >= 2081.0) & (years <= 2100.000001)
    final_index = int(np.argmin(np.abs(years - 2100.0)))
    final = df.iloc[final_index]
    initial = df.iloc[0]
    late = df.loc[late_mask]
    no_years = no_greenland_df["year"].to_numpy(dtype=float)
    no_final = no_greenland_df.iloc[int(np.argmin(np.abs(no_years - 2100.0)))]
    gmst = late["global_near_surface_air_warming_c"].to_numpy(dtype=float)
    arctic_air = late["arctic_near_surface_air_warming_c"].to_numpy(dtype=float)
    arctic_bulk = late["arctic_bulk_surface_warming_c"].to_numpy(dtype=float)
    late_gmst = float(np.mean(gmst))
    late_arctic_air = float(np.mean(arctic_air))
    late_arctic_bulk = float(np.mean(arctic_bulk))

    lat = result.grid.lat
    start = config.arctic_module_start_latitude_deg
    full = config.arctic_module_full_latitude_deg
    linear = np.clip((lat - start) / max(full - start, 1.0e-12), 0.0, 1.0)
    blend = linear * linear * (3.0 - 2.0 * linear)
    active_ocean_fraction = float(
        np.sum(result.grid.band_area_weights * result.grid.ocean_fraction * blend)
        / np.sum(result.grid.band_area_weights)
    )
    maximum_forcing_like_coefficient = float(
        config.arctic_moisture_transport_wm2_per_k
        + config.arctic_winter_transport_enhancement
    )
    maximum_forcing_like_flux_upper_bound = float(
        maximum_forcing_like_coefficient
        * max(float(late["global_surface_warming_c"].max()), 0.0)
    )
    maximum_transport_power_upper_bound_pw = float(
        maximum_forcing_like_flux_upper_bound
        * active_ocean_fraction
        * EARTH_AREA_M2
        / 1.0e15
    )

    cap = float(config.greenland_max_freshwater_sv)
    target = df["greenland_freshwater_target_sv"].to_numpy(dtype=float)
    requested = df["greenland_requested_freshwater_sv"].to_numpy(dtype=float)
    cap_activation = float(np.mean(target >= cap - 1.0e-10))
    requested_above_cap = float(np.mean(requested > cap + 1.0e-10))
    mass_identity_error = np.abs(
        config.greenland_initial_ice_mass_gt
        - df["greenland_remaining_ice_gt"].to_numpy(dtype=float)
        - df["greenland_cumulative_net_ice_loss_gt"].to_numpy(dtype=float)
    )

    months = np.rint(df["arctic_calendar_month"].to_numpy(dtype=float)).astype(int)
    late_march = late_mask & (months == 3)
    late_september = late_mask & (months == 9)
    historical_ocean_mask = (years >= 1991.0) & (years <= 2020.999999)
    monthly_arctic = sector_monthly_arctic_temperatures(result, late_mask)
    historical_monthly_arctic = sector_monthly_arctic_temperatures(
        result, historical_ocean_mask
    )
    monthly_greenland = greenland_monthly_summary(df, late_mask)

    open_water_benchmark_document = json.loads(
        Path(
            "data/validation/open_water/NOAA_OISST_ARCTIC_BENCHMARKS.json"
        ).read_text(encoding="utf-8")
    )
    open_water_benchmarks = open_water_benchmark_document["benchmarks"]
    historical_by_month = {
        int(item["month"]): item for item in historical_monthly_arctic
    }

    def mean_open_water(
        field: str,
        selected_months: tuple[int, ...],
    ) -> float:
        values = np.asarray(
            [historical_by_month[month][field] for month in selected_months],
            dtype=float,
        )
        values = values[np.isfinite(values)]
        return float(np.mean(values)) if values.size else float("nan")

    arctic_ocean_benchmark_values = {
        "atlantic_jja_mean_c": mean_open_water(
            "atlantic_arctic_open_water_absolute_c", (6, 7, 8)
        ),
        "non_atlantic_jja_mean_c": mean_open_water(
            "non_atlantic_arctic_open_water_absolute_c", (6, 7, 8)
        ),
        "atlantic_september_mean_c": mean_open_water(
            "atlantic_arctic_open_water_absolute_c", (9,)
        ),
        "non_atlantic_september_mean_c": mean_open_water(
            "non_atlantic_arctic_open_water_absolute_c", (9,)
        ),
    }
    arctic_ocean_sanity_checks = {
        name: bool(
            np.isfinite(arctic_ocean_benchmark_values[name])
            and bounds["minimum"]
            <= arctic_ocean_benchmark_values[name]
            <= bounds["maximum"]
        )
        for name, bounds in open_water_benchmarks.items()
    }

    greenland_benchmark_document = json.loads(
        Path("external_posthoc_sanity_benchmarks.json").read_text(
            encoding="utf-8"
        )
    )
    greenland_benchmark = greenland_benchmark_document["benchmarks"][
        "greenland_ssp245_sea_level_2014_2100_mm"
    ]
    index_2014 = int(np.argmin(np.abs(years - 2014.0)))
    greenland_sle_2014_to_2100_mm = float(
        final["greenland_cumulative_sea_level_mm"]
        - df.iloc[index_2014]["greenland_cumulative_sea_level_mm"]
    )
    greenland_posthoc_sanity_checks = {
        "ssp245_sea_level_2014_2100_within_published_22_to_163_mm": bool(
            greenland_benchmark["minimum"]
            <= greenland_sle_2014_to_2100_mm
            <= greenland_benchmark["maximum"]
        ),
        "remaining_ice_mass_nonnegative": bool(
            float(final["greenland_remaining_ice_gt"]) >= 0.0
        ),
        "maximum_monthly_surface_loss_below_initial_reservoir_per_year": bool(
            float(df["greenland_net_surface_loss_gt_per_year"].max())
            < config.greenland_initial_ice_mass_gt
        ),
    }

    concentration_min = float(
        min(
            np.min(result.atlantic_sea_ice_history),
            np.min(result.non_atlantic_sea_ice_history),
        )
    )
    concentration_max = float(
        max(
            np.max(result.atlantic_sea_ice_history),
            np.max(result.non_atlantic_sea_ice_history),
        )
    )
    local_thickness_min = float(
        min(
            np.min(result.arctic_atlantic_local_ice_thickness_history_m),
            np.min(result.arctic_non_atlantic_local_ice_thickness_history_m),
        )
    )
    local_thickness_max = float(
        max(
            np.max(result.arctic_atlantic_local_ice_thickness_history_m),
            np.max(result.arctic_non_atlantic_local_ice_thickness_history_m),
        )
    )

    gates = {
        "arctic_air_amplification_between_1p5_and_3p5": bool(
            1.5 <= late_arctic_air / max(late_gmst, 1.0e-12) <= 3.5
        ),
        "maximum_arctic_air_anomaly_le_15c": bool(
            float(df["arctic_near_surface_air_warming_c"].max()) <= 15.0
        ),
        "forcing_like_transport_coefficient_le_25_wm2_k": bool(
            maximum_forcing_like_coefficient <= 25.0
        ),
        "transport_power_upper_bound_lt_2pw": bool(
            maximum_transport_power_upper_bound_pw < 2.0
        ),
        "greenland_driver_uses_limited_low_pass_maritime_term": bool(
            config.greenland_temperature_driver == "greenland"
            and config.arctic_greenland_marine_influence <= 0.25
        ),
        "greenland_target_cap_activation_le_5pct": bool(cap_activation <= 0.05),
        "greenland_requested_above_cap_le_5pct": bool(requested_above_cap <= 0.05),
        "greenland_mass_identity_error_le_1e_minus_4_gt": bool(
            float(np.max(mass_identity_error)) <= 1.0e-4
        ),
        "initial_amoc_between_16p5_and_17p5_sv": bool(
            16.5 <= float(initial["amoc_sv"]) <= 17.5
        ),
        "amoc_2100_above_collapse_threshold": bool(
            float(final["amoc_sv"]) > config.amoc_collapse_threshold_sv
        ),
        "amoc_decline_between_0_and_50pct": bool(
            0.0
            <= 100.0 * (float(initial["amoc_sv"]) - float(final["amoc_sv"]))
            / max(float(initial["amoc_sv"]), 1.0e-12)
            <= 50.0
        ),
        "greenland_freshwater_weakens_or_does_not_strengthen_amoc": bool(
            float(final["amoc_sv"]) <= float(no_final["amoc_sv"]) + 1.0e-8
        ),
        "salt_conservation_error_le_0p1ppm": bool(
            float(np.max(np.abs(df["salt_conservation_error_ppm"]))) <= 0.1
        ),
        "concentration_bounds_hold": bool(
            concentration_min >= -1.0e-10 and concentration_max <= 1.0 + 1.0e-10
        ),
        "local_ice_thickness_nonnegative": bool(local_thickness_min >= -1.0e-10),
        "lead_closure_compensation_disabled": bool(
            config.arctic_winter_lead_closure_fraction == 0.0
        ),
    }

    return {
        "late_period": [2081, 2100],
        "arctic_atmosphere_and_ocean": {
            "late_gmst_near_surface_air_c": late_gmst,
            "late_arctic_bulk_surface_c": late_arctic_bulk,
            "late_arctic_near_surface_air_c": late_arctic_air,
            "arctic_bulk_surface_amplification": late_arctic_bulk / max(late_gmst, 1.0e-12),
            "arctic_near_surface_air_amplification": late_arctic_air / max(late_gmst, 1.0e-12),
            "maximum_arctic_air_anomaly_c": float(
                df["arctic_near_surface_air_warming_c"].max()
            ),
            "maximum_arctic_open_water_temperature_c": float(
                result.maximum_arctic_open_water_temperature_c
            ),
            "maximum_arctic_open_water_temperature_c_at_1pct_open": float(
                result.maximum_arctic_open_water_temperature_c_at_1pct_open
            ),
            "maximum_forcing_like_transport_coefficient_wm2_k": maximum_forcing_like_coefficient,
            "maximum_forcing_like_flux_upper_bound_wm2": maximum_forcing_like_flux_upper_bound,
            "maximum_transport_power_upper_bound_pw": maximum_transport_power_upper_bound_pw,
            "monthly_absolute_temperatures": monthly_arctic,
            "historical_1991_2020_monthly_absolute_temperatures": historical_monthly_arctic,
            "open_water_benchmark": {
                "dataset": open_water_benchmark_document["dataset"],
                "evidence_role": open_water_benchmark_document["evidence_role"],
                "used_for_tuning": open_water_benchmark_document["used_for_tuning"],
                "release_gate_role": open_water_benchmark_document["release_gate_role"],
                "values": arctic_ocean_benchmark_values,
                "bounds": open_water_benchmarks,
                "checks": arctic_ocean_sanity_checks,
                "passed": bool(all(arctic_ocean_sanity_checks.values())),
                "independent_quantitative_validation": False,
                "warning": open_water_benchmark_document["mandatory_output_warning"],
            },
            "late_march_area_million_km2": float(
                np.mean(df.loc[late_march, "northern_hemisphere_sea_ice_area_million_km2"])
            ),
            "late_september_area_million_km2": float(
                np.mean(df.loc[late_september, "northern_hemisphere_sea_ice_area_million_km2"])
            ),
            "concentration_minimum": concentration_min,
            "concentration_maximum": concentration_max,
            "local_ice_thickness_minimum_m": local_thickness_min,
            "local_ice_thickness_maximum_m": local_thickness_max,
        },
        "greenland": {
            "driver_formula": (
                "(1-marine_influence)*(0.70*Greenland_land + 0.20*NH_land + "
                "0.10*global_surface) + marine_influence*low_pass_Arctic_air"
            ),
            "marine_influence": config.arctic_greenland_marine_influence,
            "monthly_late_period": monthly_greenland,
            "late_mean_temperature_driver_c": float(
                late["greenland_temperature_driver_c"].mean()
            ),
            "late_mean_absolute_surface_temperature_c": float(
                late["greenland_absolute_surface_temperature_c"].mean()
            ),
            "late_mean_positive_degree_day_rate": float(
                late["greenland_positive_degree_day_rate"].mean()
            ),
            "late_mean_net_surface_loss_gt_per_year": float(
                late["greenland_net_surface_loss_gt_per_year"].mean()
            ),
            "late_mean_applied_freshwater_sv": float(
                late["greenland_applied_freshwater_sv"].mean()
            ),
            "late_mean_target_freshwater_sv": float(
                late["greenland_freshwater_target_sv"].mean()
            ),
            "maximum_target_freshwater_sv": float(
                df["greenland_freshwater_target_sv"].max()
            ),
            "freshwater_cap_sv": cap,
            "target_cap_activation_fraction": cap_activation,
            "requested_above_cap_fraction": requested_above_cap,
            "remaining_ice_mass_2100_gt": float(final["greenland_remaining_ice_gt"]),
            "remaining_ice_fraction_2100": float(final["greenland_remaining_fraction"]),
            "cumulative_melt_2100_gt": float(final["greenland_cumulative_melt_gt"]),
            "cumulative_accumulation_2100_gt": float(
                final["greenland_cumulative_accumulation_gt"]
            ),
            "cumulative_net_loss_2100_gt": float(
                final["greenland_cumulative_net_ice_loss_gt"]
            ),
            "maximum_mass_identity_error_gt": float(np.max(mass_identity_error)),
            "sea_level_contribution_2014_to_2100_mm": greenland_sle_2014_to_2100_mm,
            "external_posthoc_benchmark": {
                "source_title": greenland_benchmark["source_title"],
                "source_reference": greenland_benchmark["source_reference"],
                "evidence_role": greenland_benchmark["evidence_role"],
                "used_for_tuning": greenland_benchmark["used_for_tuning"],
                "minimum_mm": greenland_benchmark["minimum"],
                "maximum_mm": greenland_benchmark["maximum"],
                "checks": greenland_posthoc_sanity_checks,
                "passed": bool(all(greenland_posthoc_sanity_checks.values())),
                "independent_quantitative_validation": False,
                "notes": greenland_benchmark["notes"],
            },
        },
        "amoc": {
            "collapse_threshold_sv": config.amoc_collapse_threshold_sv,
            "initial_amoc_sv": float(initial["amoc_sv"]),
            "amoc_2100_sv": float(final["amoc_sv"]),
            "late_mean_amoc_sv": float(late["amoc_sv"].mean()),
            "minimum_amoc_sv": float(df["amoc_sv"].min()),
            "decline_sv": float(initial["amoc_sv"] - final["amoc_sv"]),
            "decline_percent": float(
                100.0
                * (float(initial["amoc_sv"]) - float(final["amoc_sv"]))
                / max(float(initial["amoc_sv"]), 1.0e-12)
            ),
            "collapsed_at_2100": bool(
                0.0 <= float(final["amoc_sv"]) <= config.amoc_collapse_threshold_sv
            ),
            "reversed_at_2100": bool(float(final["amoc_sv"]) < 0.0),
            "minimum_no_greenland_freshwater_amoc_sv": float(
                no_greenland_df["amoc_sv"].min()
            ),
            "amoc_2100_no_greenland_freshwater_sv": float(no_final["amoc_sv"]),
            "greenland_freshwater_effect_on_amoc_2100_sv": float(
                no_final["amoc_sv"] - final["amoc_sv"]
            ),
            "maximum_absolute_salt_conservation_error_ppm": float(
                np.max(np.abs(df["salt_conservation_error_ppm"]))
            ),
            "maximum_pre_projection_salt_error_ppm": float(
                np.max(np.abs(df["pre_projection_salt_conservation_error_ppm"]))
            ),
            "semantics": {
                "active": f"AMOC > {config.amoc_collapse_threshold_sv:g} Sv",
                "weak_or_collapsed": (
                    f"0 <= AMOC <= {config.amoc_collapse_threshold_sv:g} Sv"
                ),
                "reversed": "AMOC < 0 Sv",
            },
        },
        "gates": gates,
        "passed": bool(all(gates.values())),
    }


def compact_sea_ice_summary(evaluation: dict[str, Any]) -> dict[str, Any]:
    calibration = evaluation["calibration"]
    march = calibration["months"]["3"]
    september = calibration["months"]["9"]
    return {
        "calibration_passed": bool(evaluation["calibration_passed"]),
        "recent_period_evaluation_passed": bool(
            evaluation["validation_informed_development_evaluation_passed"]
        ),
        "all_release_gates_passed": bool(
            evaluation["all_current_sea_ice_release_gates_passed"]
        ),
        "all_engineering_gates_passed": bool(
            evaluation["all_current_sea_ice_engineering_gates_passed"]
        ),
        "scientific_temporal_skill_gate_passed": bool(
            evaluation["scientific_temporal_skill_gate_passed"]
        ),
        "failed_calibration_gates": [
            name for name, passed in evaluation["calibration_gates"].items() if not passed
        ],
        "failed_recent_period_gates": [
            name
            for name, passed in evaluation[
                "validation_informed_development_evaluation_gates"
            ].items()
            if not passed
        ],
        "march_area_mean_million_km2": march["area"]["model_mean_million_km2"],
        "march_area_rmse_million_km2": march["area"]["rmse_million_km2"],
        "march_extent_mean_million_km2": march["extent"]["model_mean_million_km2"],
        "march_extent_rmse_million_km2": march["extent"]["rmse_million_km2"],
        "march_extent_trend_million_km2_per_decade": march["extent"][
            "model_trend_million_km2_per_decade"
        ],
        "march_observed_extent_trend_million_km2_per_decade": march["extent"][
            "observed_trend_million_km2_per_decade"
        ],
        "march_robust_extent_trend_passed": evaluation[
            "march_extent_trend_robustness"
        ]["passed"],
        "september_area_mean_million_km2": september["area"][
            "model_mean_million_km2"
        ],
        "september_area_rmse_million_km2": september["area"]["rmse_million_km2"],
        "september_extent_mean_million_km2": september["extent"][
            "model_mean_million_km2"
        ],
        "september_extent_rmse_million_km2": september["extent"][
            "rmse_million_km2"
        ],
        "september_area_trend_million_km2_per_decade": september["area"][
            "model_trend_million_km2_per_decade"
        ],
        "september_observed_area_trend_million_km2_per_decade": september["area"][
            "observed_trend_million_km2_per_decade"
        ],
        "seasonal_area_amplitude_million_km2": calibration[
            "model_march_minus_september_area_million_km2"
        ],
        "seasonal_area_amplitude_observed_million_km2": calibration[
            "observed_march_minus_september_area_million_km2"
        ],
        "observation_files_verified": bool(
            evaluation["dataset_metadata"]["packaged_file_hashes_match"]
        ),
        "extent_interpretation": evaluation["area_operator"].get(
            "extent_interpretation",
            "Extent is derived from native area with fixed calibrated seasonal multipliers and is not independent evidence.",
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resolution", type=float, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("."))
    parser.add_argument("--segment-years", type=float, default=20.0)
    args = parser.parse_args()

    if MODEL_VERSION != EXPECTED_VERSION:
        raise SystemExit(
            f"Expected model version {EXPECTED_VERSION}, found {MODEL_VERSION}."
        )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    label = f"{args.resolution:g}DEG"
    generated_at = datetime.now(timezone.utc).isoformat()
    package_root = Path(__file__).resolve().parent
    source_files = (
        "validate_v22922.py",
        "climate_model.py",
        "arctic_process_budget.py",
        "sea_ice_validation.py",
        "sea_ice_observation.py",
        "combine_v22922_validation.py",
        "validation_segmentation.py",
        "scientific_evidence.py",
        "validation_provenance.py",
        "runtime_provenance.py",
        "trusted_validation_pickle.py",
        "amoc_continuation.py",
        "external_posthoc_sanity_benchmarks.json",
        "data/validation/open_water/NOAA_OISST_ARCTIC_BENCHMARKS.json",
        "tools/acquire_oisst_provenance.py",
        "tools/process_noaa_oisst_arctic_benchmarks.py",
        "data/validation/nsidc/METADATA.json",
        "data/validation/nsidc/N_03_extent_v4.0.csv",
        "data/validation/nsidc/N_09_extent_v4.0.csv",
    )
    source_hashes = {
        relative: sha256_file(package_root / relative)
        for relative in source_files
    }

    ProcessClimateModel.clear_arctic_reference_cycle_cache()
    base = replace(
        ModelConfig(),
        start_year=1850.0,
        duration_years=250.0,
        scenario="ssp245",
        dt_years=0.05,
        record_every_years=0.05,
        resolution_deg=float(args.resolution),
        auto_initialize_from_1850=False,
    )
    started = time.perf_counter()
    primary = run_segmented_in_process(
        base,
        segment_years=args.segment_years,
        label=f"{label} production",
    )
    sea_ice_evaluation = evaluate_result(primary)

    no_greenland_config = replace(
        base,
        greenland_freshwater_sv_per_k=0.0,
        greenland_surface_mass_balance_enabled=False,
        greenland_regrowth_sv_per_k=0.0,
    )
    no_greenland = run_segmented_in_process(
        no_greenland_config,
        segment_years=args.segment_years,
        label=f"{label} no-Greenland-FW",
    )

    structural = structural_area_volume_experiments(base)
    coupled = coupled_summary(primary, no_greenland)
    elapsed = time.perf_counter() - started

    sea_ice_payload = {
        "schema_version": "3.0",
        "model_version": MODEL_VERSION,
        "generated_at": generated_at,
        "source_hashes": source_hashes,
        "validation_type": "version_matched_production_default",
        "evidence_role": (
            "historical calibration and previously inspected development evaluation; "
            "not independent predictive validation"
        ),
        "run": {
            "scenario": "ssp245",
            "start_year": 1850.0,
            "end_year": 2100.0,
            "dt_years": base.dt_years,
            "record_every_years": base.record_every_years,
            "resolution_deg": args.resolution,
        },
        "configuration": asdict(base),
        "evaluation": sea_ice_evaluation,
        "summary": compact_sea_ice_summary(sea_ice_evaluation),
    }
    coupled_payload = {
        "schema_version": "3.0",
        "model_version": MODEL_VERSION,
        "generated_at": generated_at,
        "source_hashes": source_hashes,
        "validation_type": "version_matched_production_default",
        "run": {
            "scenario": "ssp245",
            "start_year": 1850.0,
            "end_year": 2100.0,
            "dt_years": base.dt_years,
            "record_every_years": base.record_every_years,
            "resolution_deg": args.resolution,
            "elapsed_seconds": elapsed,
        },
        "configuration": {
            key: value
            for key, value in asdict(base).items()
            if key.startswith("arctic_")
            or key.startswith("greenland_")
            or key.startswith("amoc_")
            or key.startswith("salt_")
            or key in {"hydrological_freshwater_sv_per_k"}
        },
        "structural_area_volume_experiments": structural,
        "coupled": coupled,
    }

    sea_ice_path = args.output_dir / f"SEA_ICE_VALIDATION_V2_29_22_{label}.json"
    coupled_path = (
        args.output_dir / f"ARCTIC_GREENLAND_AMOC_VALIDATION_V2_29_22_{label}.json"
    )
    timeseries_path = args.output_dir / f"COUPLED_TIMESERIES_V2_29_22_{label}.csv"
    write_json(sea_ice_path, sea_ice_payload)
    write_json(coupled_path, coupled_payload)
    primary.dataframe.loc[:, SELECTED_TIMESERIES_COLUMNS].to_csv(
        timeseries_path, index=False
    )
    print(
        "RESULT "
        + json.dumps(
            {
                "resolution_deg": args.resolution,
                "sea_ice_historical_passed": sea_ice_payload["summary"][
                    "calibration_passed"
                ],
                "sea_ice_recent_passed": sea_ice_payload["summary"][
                    "recent_period_evaluation_passed"
                ],
                "coupled_passed": coupled["passed"],
                "structural_area_volume_passed": structural["passed"],
                "elapsed_seconds": elapsed,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    if not (
        sea_ice_payload["summary"]["all_engineering_gates_passed"]
        and coupled["passed"]
        and structural["passed"]
    ):
        raise SystemExit("One or more v2.29.22 engineering gates failed.")


if __name__ == "__main__":
    main()
