#!/usr/bin/env python3
"""Paired Monte Carlo sweep across linearly ramped CO2 concentration targets.

Each sampled parameter member is reused at every CO2 target. This paired design
isolates the effect of target concentration from Monte Carlo sampling noise.
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
import time
import traceback
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from amoc_outcomes import collapse_duration_diagnostics
from climate_model import (
    MODEL_NAME,
    MODEL_VERSION,
    ModelConfig,
    ModelState,
    ProcessClimateModel,
)
from monte_carlo import (
    MONTE_CARLO_VERSION,
    MINIMUM_QUANTITATIVE_UNCERTAINTY_MEMBERS,
    PERCENTILES,
    _automatic_worker_count,
    _member_worker,
    assess_ensemble_quality,
    build_monte_carlo_parser,
    compute_importance_weights,
    config_from_args,
    prepare_output_directory,
    constraints_enabled,
    generate_samples,
    normalize_constraint_mode,
    parse_ranges,
    resolve_random_seed,
    validate_ensemble_survival,
    weighted_quantile,
    weighted_percentile_timeseries,
)

from runtime_provenance import runtime_provenance
from run_state import (
    RUN_STATE_FORMAT,
    RUN_STATE_VERSION,
    OutputDirectoryLockedError,
    compatible_checkpoint_count,
    initialize_run_state,
    load_run_state,
    output_directory_run_lock,
    run_state_path,
    saved_seed_for_resume,
    update_run_state,
)
from worker_supervision import (
    load_compatible_checkpoint,
    run_supervised_tasks,
    save_compatible_checkpoint,
    stable_fingerprint,
    result_is_failed,
)

SWEEP_VERSION = MODEL_VERSION
TARGET_MODES = ("increments", "specific")
AMOC_BASELINE_DEFINITION = "common_member_pre_forcing_t0"
COMMON_START_REFERENCE_TOLERANCE_PPM = 1.0e-9
COMMON_START_TOA_IMBALANCE_TOLERANCE_WM2 = 0.20
COMMON_START_MAXIMUM_EQUIVALENT_ECS_C = 10.0
COMMON_START_WARMING_SIGN_TOLERANCE_C = 0.25
COMMON_START_WARMING_SLACK_C = 0.50
COMMON_START_MINIMUM_LOCAL_TEMPERATURE_LIMIT_C = 40.0
COMMON_START_LOCAL_TO_GLOBAL_LIMIT_RATIO = 2.0
COMMON_START_MAXIMUM_ANNUAL_GMST_DRIFT_C = 0.02
COMMON_START_MAXIMUM_ANNUAL_AMOC_DRIFT_SV = 0.10
DEFAULT_COMMON_START_REDRAW_ATTEMPTS = 3
COMMON_START_REDRAW_SEED_STRIDE = 0x9E3779B9


def _common_start_redraw_seed(seed: int, attempt: int) -> int:
    """Return a deterministic independent seed for one replacement-draw round."""

    attempt_number = int(attempt)
    if attempt_number < 1:
        raise ValueError("Common-start redraw attempts are numbered from one.")
    return int(
        (int(seed) + attempt_number * COMMON_START_REDRAW_SEED_STRIDE)
        % (2**32)
    )


def _is_common_start_rejection(result: Any) -> bool:
    """Return whether a worker failed solely because its baseline draw was invalid."""

    return (
        isinstance(result, dict)
        and str(result.get("status", "")).lower() == "failed"
        and result.get("failure_kind") == "common_start_baseline_rejected"
    )


def validate_common_start_baseline(
    diagnostics: dict[str, Any],
    config: ModelConfig,
) -> dict[str, float]:
    """Reject a numerically completed but scientifically invalid sweep baseline.

    A CO2-collapse sweep is conditional on an active, stable common-start
    climate.  Merely reaching the requested spin-up duration is insufficient:
    broad prior combinations can produce a runaway or already-collapsed state
    without crossing the model's deliberately loose emergency bounds.
    """

    required = (
        "common_start_ppm",
        "global_surface_warming_c",
        "annual_mean_toa_imbalance_wm2",
        "annual_mean_prescribed_forcing_wm2",
        "annual_gmst_drift_c",
        "annual_amoc_drift_sv",
        "initial_amoc_sv",
        "maximum_absolute_local_temperature_anomaly_c",
    )
    values: dict[str, float] = {}
    for name in required:
        try:
            value = float(diagnostics[name])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"Common-start baseline diagnostic {name!r} is missing or invalid."
            ) from exc
        if not math.isfinite(value):
            raise ValueError(
                f"Common-start baseline diagnostic {name!r} is non-finite."
            )
        values[name] = value

    amoc = values["initial_amoc_sv"]
    if amoc <= float(config.amoc_collapse_threshold_sv):
        raise ValueError(
            "Common-start baseline AMOC is already weak/collapsed: "
            f"{amoc:.6g} Sv <= {float(config.amoc_collapse_threshold_sv):.6g} Sv. "
            "A CO2-induced collapse sweep requires an active pre-forcing AMOC."
        )

    imbalance = abs(values["annual_mean_toa_imbalance_wm2"])
    if imbalance > COMMON_START_TOA_IMBALANCE_TOLERANCE_WM2:
        raise ValueError(
            "Common-start spin-up did not reach the energy-balance gate: "
            f"annual-mean |TOA imbalance|={imbalance:.6g} W/m2 exceeds "
            f"{COMMON_START_TOA_IMBALANCE_TOLERANCE_WM2:.6g} W/m2."
        )

    forcing = values["annual_mean_prescribed_forcing_wm2"]
    warming = values["global_surface_warming_c"]
    if (
        forcing > 1.0e-8
        and warming < -COMMON_START_WARMING_SIGN_TOLERANCE_C
    ) or (
        forcing < -1.0e-8
        and warming > COMMON_START_WARMING_SIGN_TOLERANCE_C
    ):
        raise ValueError(
            "Common-start warming has the wrong sign for the prescribed forcing: "
            f"forcing={forcing:.6g} W/m2, warming={warming:.6g} C."
        )

    equivalent_warming_limit = (
        COMMON_START_WARMING_SLACK_C
        + COMMON_START_MAXIMUM_EQUIVALENT_ECS_C
        * abs(forcing)
        / float(config.co2_doubling_erf_wm2)
    )
    if abs(warming) > equivalent_warming_limit:
        raise ValueError(
            "Common-start global warming is outside the unconditional "
            "numerical-plausibility envelope: "
            f"|warming|={abs(warming):.6g} C exceeds "
            f"{equivalent_warming_limit:.6g} C."
        )

    local_temperature_limit = max(
        COMMON_START_MINIMUM_LOCAL_TEMPERATURE_LIMIT_C,
        COMMON_START_LOCAL_TO_GLOBAL_LIMIT_RATIO * equivalent_warming_limit,
    )
    local_maximum = values["maximum_absolute_local_temperature_anomaly_c"]
    if local_maximum > local_temperature_limit:
        raise ValueError(
            "Common-start local temperature is outside the broad physical "
            "plausibility envelope: "
            f"maximum |anomaly|={local_maximum:.6g} C exceeds "
            f"{local_temperature_limit:.6g} C."
        )

    gmst_drift_limit = COMMON_START_MAXIMUM_ANNUAL_GMST_DRIFT_C * max(
        1.0, equivalent_warming_limit
    )
    if abs(values["annual_gmst_drift_c"]) > gmst_drift_limit:
        raise ValueError(
            "Common-start spin-up is still drifting: "
            f"annual GMST change={values['annual_gmst_drift_c']:.6g} C exceeds "
            f"{gmst_drift_limit:.6g} C."
        )

    amoc_drift_limit = max(
        COMMON_START_MAXIMUM_ANNUAL_AMOC_DRIFT_SV,
        0.01 * abs(amoc),
    )
    if abs(values["annual_amoc_drift_sv"]) > amoc_drift_limit:
        raise ValueError(
            "Common-start spin-up is still drifting: "
            f"annual AMOC change={values['annual_amoc_drift_sv']:.6g} Sv exceeds "
            f"{amoc_drift_limit:.6g} Sv."
        )

    return {
        "maximum_equivalent_global_warming_c": float(equivalent_warming_limit),
        "maximum_local_temperature_anomaly_c": float(local_temperature_limit),
        "maximum_absolute_annual_toa_imbalance_wm2": float(
            COMMON_START_TOA_IMBALANCE_TOLERANCE_WM2
        ),
        "maximum_absolute_annual_gmst_drift_c": float(gmst_drift_limit),
        "maximum_absolute_annual_amoc_drift_sv": float(amoc_drift_limit),
    }


def _common_start_baseline_diagnostics(
    model: ProcessClimateModel,
    state: ModelState,
    elapsed_years: float,
    common_start_ppm: float,
) -> dict[str, Any]:
    """Probe one further annual cycle without changing the accepted baseline."""

    initial_arrays = (
        np.asarray(state.land_anomaly_c, dtype=float),
        np.asarray(state.atlantic_ocean_anomaly_c, dtype=float),
        np.asarray(state.non_atlantic_ocean_anomaly_c, dtype=float),
    )
    if (
        abs(float(common_start_ppm) - float(model.config.co2_reference_ppm))
        <= COMMON_START_REFERENCE_TOLERANCE_PPM
        and float(elapsed_years) == 0.0
    ):
        # The native reference manifold is constructed as the exact control
        # state.  Avoid an unnecessary extra model year (and preserve the
        # lightweight test/extension interface) when no spin-up was required.
        diagnostics: dict[str, Any] = {
            "common_start_ppm": float(common_start_ppm),
            "probe_duration_years": 0.0,
            "global_surface_warming_c": 0.0,
            "annual_mean_toa_imbalance_wm2": 0.0,
            "annual_mean_prescribed_forcing_wm2": 0.0,
            "annual_gmst_drift_c": 0.0,
            "annual_amoc_drift_sv": 0.0,
            "initial_amoc_sv": float(state.amoc_sv),
            "maximum_absolute_local_temperature_anomaly_c": max(
                float(np.max(np.abs(array))) for array in initial_arrays
            ),
            "maximum_absolute_land_temperature_anomaly_c": float(
                np.max(np.abs(initial_arrays[0]))
            ),
            "maximum_absolute_ocean_temperature_anomaly_c": max(
                float(np.max(np.abs(array))) for array in initial_arrays[1:]
            ),
        }
        return diagnostics

    model.state = state.copy()
    initial_record = model.record(float(elapsed_years))
    initial_gmst = float(initial_record["global_surface_warming_c"])
    initial_amoc = float(state.amoc_sv)
    weighted_toa = 0.0
    weighted_forcing = 0.0
    offset = 0.0
    while offset < 1.0 - 1.0e-12:
        dt = min(float(model.config.dt_years), 1.0 - offset)
        model.step(float(elapsed_years) + offset, dt_years=dt)
        offset += dt
        record = model.record(float(elapsed_years) + offset)
        weighted_toa += dt * float(record["toa_imbalance_wm2"])
        weighted_forcing += dt * float(record["total_prescribed_forcing_wm2"])

    final_gmst = float(model._global_surface_mean(model.state))
    arrays = (
        *initial_arrays,
        np.asarray(model.state.land_anomaly_c, dtype=float),
        np.asarray(model.state.atlantic_ocean_anomaly_c, dtype=float),
        np.asarray(model.state.non_atlantic_ocean_anomaly_c, dtype=float),
    )
    local_maximum = max(float(np.max(np.abs(array))) for array in arrays)
    diagnostics: dict[str, Any] = {
        "common_start_ppm": float(common_start_ppm),
        "probe_duration_years": 1.0,
        "global_surface_warming_c": initial_gmst,
        "annual_mean_toa_imbalance_wm2": float(weighted_toa),
        "annual_mean_prescribed_forcing_wm2": float(weighted_forcing),
        "annual_gmst_drift_c": float(final_gmst - initial_gmst),
        "annual_amoc_drift_sv": float(model.state.amoc_sv - initial_amoc),
        "initial_amoc_sv": initial_amoc,
        "maximum_absolute_local_temperature_anomaly_c": local_maximum,
        "maximum_absolute_land_temperature_anomaly_c": max(
            float(np.max(np.abs(arrays[0]))),
            float(np.max(np.abs(arrays[3]))),
        ),
        "maximum_absolute_ocean_temperature_anomaly_c": max(
            *(float(np.max(np.abs(array))) for array in arrays[1:3]),
            *(float(np.max(np.abs(array))) for array in arrays[4:6]),
        ),
    }
    return diagnostics




def validate_target_survival_counts(
    targets_ppm: Sequence[float],
    successful_counts: Sequence[int],
    *,
    requested_members: int,
    allow_exploratory_target_counts: bool = False,
) -> list[dict[str, Any]]:
    """Enforce survival and quantitative-count gates independently per target."""

    targets = np.asarray(targets_ppm, dtype=float)
    counts = np.asarray(successful_counts, dtype=int)
    requested = int(requested_members)
    if targets.ndim != 1 or counts.ndim != 1 or len(targets) != len(counts):
        raise RuntimeError(
            "Target survival accounting is inconsistent: target and count vectors "
            "must be one-dimensional and equal length."
        )
    if requested <= 0 or np.any(counts < 0) or np.any(counts > requested):
        raise RuntimeError(
            "Target survival accounting is inconsistent: successful counts must "
            "lie between zero and the requested member count."
        )

    diagnostics: list[dict[str, Any]] = []
    for target_ppm, successful in zip(targets, counts, strict=True):
        failed = requested - int(successful)
        try:
            survival = validate_ensemble_survival(requested, int(successful), failed)
        except RuntimeError as exc:
            raise RuntimeError(
                f"CO2 target {float(target_ppm):g} ppm failed its independent "
                f"ensemble-survival gate: {exc}"
            ) from exc
        diagnostics.append({"target_ppm": float(target_ppm), **survival})

    requested_quantitative = (
        requested >= MINIMUM_QUANTITATIVE_UNCERTAINTY_MEMBERS
    )
    below_quantitative = [
        float(targets[index])
        for index, count in enumerate(counts)
        if int(count) < MINIMUM_QUANTITATIVE_UNCERTAINTY_MEMBERS
    ]
    if (
        requested_quantitative
        and below_quantitative
        and not bool(allow_exploratory_target_counts)
    ):
        formatted = ", ".join(f"{value:g}" for value in below_quantitative)
        raise RuntimeError(
            "CO2 target sweep lost the declared quantitative member count at "
            f"target(s) {formatted} ppm. At least "
            f"{MINIMUM_QUANTITATIVE_UNCERTAINTY_MEMBERS} usable members are "
            "required per target. Re-run the failed cells or explicitly pass "
            "--sweep-allow-exploratory-target-counts to export non-quantitative "
            "exploratory products."
        )
    return diagnostics

def build_targets(start_ppm: float, step_ppm: float, maximum_ppm: float) -> np.ndarray:
    """Return start, regular increments, and an exact final maximum target."""
    values = [float(start_ppm)]
    value = float(start_ppm)
    tolerance = max(1.0e-9, abs(maximum_ppm) * 1.0e-12)
    while value + step_ppm < maximum_ppm - tolerance:
        value += step_ppm
        values.append(float(value))
    if maximum_ppm > values[-1] + tolerance:
        values.append(float(maximum_ppm))
    return np.asarray(values, dtype=float)


def parse_specific_targets(
    value: str | Sequence[float],
    start_ppm: float | None = None,
) -> np.ndarray:
    """Parse, sort, and deduplicate an explicit positive CO2 target list.

    ``start_ppm`` is retained for source compatibility with earlier callers.
    Targets below the configured common start are valid and use a descending
    linear ramp; the common pre-forcing state is not silently changed.
    """

    if isinstance(value, str):
        tokens = [token for token in re.split(r"[,;\s]+", value.strip()) if token]
        if not tokens:
            raise ValueError("Specific CO2 target mode requires at least one target.")
        try:
            raw = [float(token) for token in tokens]
        except ValueError as exc:
            raise ValueError(
                "Specific CO2 targets must be numbers separated by commas, spaces, or semicolons."
            ) from exc
    else:
        raw = [float(item) for item in value]
    if not raw:
        raise ValueError("Specific CO2 target mode requires at least one target.")
    if any(not math.isfinite(item) or item <= 0.0 for item in raw):
        raise ValueError("Specific CO2 targets must be finite positive concentrations.")
    return np.asarray(sorted(set(raw)), dtype=float)


def resolve_targets(
    mode: str,
    start_ppm: float,
    step_ppm: float,
    maximum_ppm: float,
    specific_targets: str | Sequence[float],
) -> np.ndarray:
    normalized = str(mode).strip().lower()
    if normalized not in TARGET_MODES:
        raise ValueError(f"Unknown target mode {mode!r}; choose one of {TARGET_MODES}.")
    if normalized == "specific":
        return parse_specific_targets(specific_targets)
    return build_targets(start_ppm, step_ppm, maximum_ppm)


def _amoc_decline_percent(
    amoc: np.ndarray,
    baseline_amoc_sv: float | None = None,
) -> tuple[np.ndarray, float]:
    """Return percentage decline from one exact common pre-forcing AMOC state."""

    values = np.asarray(amoc, dtype=float)
    if baseline_amoc_sv is None:
        finite = values[np.isfinite(values)]
        baseline = float(finite[0]) if finite.size else float("nan")
    else:
        baseline = float(baseline_amoc_sv)
    if not math.isfinite(baseline) or abs(baseline) <= 1.0e-8:
        return np.full(values.shape, np.nan, dtype=float), baseline
    return 100.0 * (1.0 - values / baseline), baseline


def _count_target_checkpoints(
    directory: Path,
    fingerprint: str,
    cache: dict[str, bool] | None = None,
) -> int:
    """Count only readable compatible successful target checkpoints."""

    root = Path(directory)
    if not root.exists():
        return 0
    validated = cache if cache is not None else {}
    count = 0
    for path in root.glob("member_*/target_*.ckpt"):
        key = str(path)
        good = validated.get(key)
        if good is None:
            record = load_compatible_checkpoint(path, fingerprint)
            good = (
                isinstance(record, dict)
                and str(record.get("status", "")).lower() == "ok"
                and isinstance(record.get("target_summary"), dict)
            )
            validated[key] = bool(good)
        if good:
            count += 1
    return count


def _state_from_checkpoint(payload: dict[str, Any]) -> ModelState:
    """Reconstruct a ModelState from a validated safe-checkpoint payload.

    v2.29.20 adds independent Arctic concentration anomalies and R17 adds
    mass-neutral Arctic ice-support anomalies. Current fingerprints prevent old
    runs from being resumed accidentally, but direct checkpoint migration
    remains deterministic: older states start each new anomaly at zero relative
    to the periodic reference.
    """

    if not isinstance(payload, dict):
        raise ValueError("Saved baseline state must be a mapping")
    state_payload = dict(payload)
    migration_templates = {
        "arctic_atlantic_ice_concentration_anomaly": (
            "arctic_atlantic_seasonal_ice_fraction"
        ),
        "arctic_non_atlantic_ice_concentration_anomaly": (
            "arctic_non_atlantic_seasonal_ice_fraction"
        ),
        "arctic_atlantic_ice_support_anomaly": (
            "arctic_atlantic_seasonal_ice_fraction"
        ),
        "arctic_non_atlantic_ice_support_anomaly": (
            "arctic_non_atlantic_seasonal_ice_fraction"
        ),
    }
    for field_name, template_name in migration_templates.items():
        if field_name not in state_payload:
            if template_name not in state_payload:
                raise ValueError(
                    f"Saved baseline state is missing both {field_name!r} "
                    f"and its migration template {template_name!r}."
                )
            state_payload[field_name] = np.zeros_like(
                np.asarray(state_payload[template_name], dtype=float)
            )
    return ModelState(**state_payload)

def _final_window_mean(values: np.ndarray, years: np.ndarray, window_years: float) -> float:
    end = float(years[-1])
    start = end - float(window_years)
    finite = np.isfinite(values) & np.isfinite(years)
    if np.sum(finite) < 2:
        return float("nan")
    x = np.asarray(years[finite], dtype=float)
    y = np.asarray(values[finite], dtype=float)
    if start < x[0] or end > x[-1]:
        return float("nan")
    interior = (x > start) & (x < end)
    integration_years = np.concatenate(([start], x[interior], [end]))
    integration_values = np.interp(integration_years, x, y)
    return float(np.trapezoid(integration_values, integration_years) / window_years)


def _sweep_member_worker(payload: tuple[Any, ...]) -> dict[str, Any]:
    (
        member_id,
        base_config_dict,
        sampled,
        start_ppm,
        targets,
        ramp_years,
        hold_years,
        collapse_window_years,
        persistence_fraction,
        recovery_years,
        initial_equilibration_years,
        constraint_mode,
        diagnose_each,
        run_calibration_experiments,
        equilibrium_years,
        target_checkpoint_root,
        run_fingerprint,
        resume,
        retry_failed_on_resume,
        checkpoint_metadata,
    ) = payload
    member_checkpoint_dir = Path(target_checkpoint_root) / f"member_{int(member_id):08d}"
    attempted_target_simulations = 0
    successful_target_simulations = 0
    failed_target_simulations = 0
    baseline_diagnostics: dict[str, Any] | None = None
    baseline_rejection_reason: str | None = None
    try:
        base = ModelConfig(**base_config_dict)
        target_values = np.asarray(targets, dtype=float)
        member_checkpoint_dir.mkdir(parents=True, exist_ok=True)

        baseline_duration = max(float(initial_equilibration_years), float(base.dt_years))
        baseline_config = replace(
            base,
            **sampled,
            scenario="constant",
            co2_start_ppm=float(start_ppm),
            co2_end_ppm=float(start_ppm),
            co2_peak_ppm=float(start_ppm),
            duration_years=baseline_duration,
            forcing_mode="co2_only",
            additional_forcing_wm2=0.0,
            freshwater_hosing_sv=0.0,
            auto_initialize_from_1850=False,
            record_every_years=baseline_duration,
        )

        baseline_path = member_checkpoint_dir / "baseline.ckpt"
        baseline_record = (
            load_compatible_checkpoint(baseline_path, run_fingerprint)
            if resume
            else None
        )
        if result_is_failed(baseline_record) and retry_failed_on_resume:
            baseline_path.unlink(missing_ok=True)
            baseline_record = None
        if baseline_record is None:
            try:
                baseline_model = ProcessClimateModel(baseline_config)
                if abs(float(start_ppm) - float(base.co2_reference_ppm)) > COMMON_START_REFERENCE_TOLERANCE_PPM:
                    if initial_equilibration_years <= 0.0:
                        raise ValueError(
                            "A non-reference sweep start requires a positive "
                            "--sweep-initial-equilibration-years value."
                        )
                    baseline_model.run()
                    initialization = "constant_co2_spinup"
                    equilibration_used = float(initial_equilibration_years)
                else:
                    initialization = "native_reference_control_state"
                    equilibration_used = 0.0
                shared_baseline_state = baseline_model.state.copy()
                shared_initial_amoc = float(shared_baseline_state.amoc_sv)
                baseline_diagnostics = _common_start_baseline_diagnostics(
                    baseline_model,
                    shared_baseline_state,
                    equilibration_used,
                    float(start_ppm),
                )
                baseline_diagnostics["acceptance_limits"] = (
                    validate_common_start_baseline(
                        baseline_diagnostics, baseline_config
                    )
                )
                baseline_record = {
                    "status": "ok",
                    "member": int(member_id),
                    "sampled": sampled,
                    "baseline_definition": AMOC_BASELINE_DEFINITION,
                    "baseline_semantics": (
                        "One exact member-specific accepted pre-forcing state is reused "
                        "for every target; percentage change is measured from its t=0 AMOC."
                    ),
                    "initialization": initialization,
                    "common_start_ppm": float(start_ppm),
                    "reference_co2_ppm": float(base.co2_reference_ppm),
                    "initial_equilibration_years_requested": float(initial_equilibration_years),
                    "initial_equilibration_years_used": equilibration_used,
                    "initial_amoc_sv": shared_initial_amoc,
                    "baseline_diagnostics": baseline_diagnostics,
                    "state": asdict(shared_baseline_state),
                }
                save_compatible_checkpoint(
                    baseline_path,
                    run_fingerprint,
                    baseline_record,
                    checkpoint_metadata,
                )
            except Exception as baseline_exc:
                failed_baseline = {
                    "status": "failed",
                    "member": int(member_id),
                    "common_start_ppm": float(start_ppm),
                    "baseline_definition": AMOC_BASELINE_DEFINITION,
                    "error": f"{type(baseline_exc).__name__}: {baseline_exc}",
                    "traceback": traceback.format_exc(limit=12),
                }
                if baseline_diagnostics is not None:
                    failed_baseline["baseline_diagnostics"] = baseline_diagnostics
                try:
                    save_compatible_checkpoint(
                        baseline_path,
                        run_fingerprint,
                        failed_baseline,
                        checkpoint_metadata,
                    )
                except Exception as checkpoint_exc:
                    raise RuntimeError(
                        "Common-start baseline failed and its terminal failure "
                        f"checkpoint could not be saved: {checkpoint_exc}"
                    ) from baseline_exc
                baseline_rejection_reason = (
                    f"{type(baseline_exc).__name__}: {baseline_exc}"
                )
                print(
                    f"Member {int(member_id) + 1} prior draw excluded by the "
                    f"common-start safety gate: {baseline_rejection_reason}. "
                    "No target simulations were run for this draw.",
                    flush=True,
                )
                raise RuntimeError(
                    f"Common-start baseline rejected: {baseline_exc}"
                ) from baseline_exc
        if not isinstance(baseline_record, dict) or baseline_record.get("status") != "ok":
            raise RuntimeError(f"Saved baseline checkpoint {baseline_path} is not successful.")
        if baseline_record.get("baseline_definition") != AMOC_BASELINE_DEFINITION:
            raise ValueError("Saved baseline uses an incompatible AMOC definition.")
        if not math.isclose(
            float(baseline_record.get("common_start_ppm", float("nan"))),
            float(start_ppm),
            rel_tol=0.0,
            abs_tol=1.0e-8,
        ):
            raise ValueError("Saved baseline common CO2 start is incompatible.")
        shared_baseline_state = _state_from_checkpoint(dict(baseline_record["state"]))
        shared_initial_amoc = float(baseline_record["initial_amoc_sv"])
        baseline_diagnostics = baseline_record.get("baseline_diagnostics")
        if isinstance(baseline_diagnostics, dict):
            validate_common_start_baseline(baseline_diagnostics, baseline_config)
        else:
            # Compatibility path for a checkpoint created before the baseline
            # acceptance gate.  Reconstruct and validate it before reuse.
            baseline_validation_model = ProcessClimateModel(baseline_config)
            baseline_diagnostics = _common_start_baseline_diagnostics(
                baseline_validation_model,
                shared_baseline_state,
                float(baseline_record["initial_equilibration_years_used"]),
                float(start_ppm),
            )
            baseline_diagnostics["acceptance_limits"] = (
                validate_common_start_baseline(
                    baseline_diagnostics, baseline_config
                )
            )

        diagnostic_summary: dict[str, Any] | None = None
        if diagnose_each or run_calibration_experiments:
            diagnostic_path = member_checkpoint_dir / "diagnostic.ckpt"
            diagnostic_result = (
                load_compatible_checkpoint(diagnostic_path, run_fingerprint)
                if resume
                else None
            )
            if result_is_failed(diagnostic_result) and retry_failed_on_resume:
                diagnostic_path.unlink(missing_ok=True)
                diagnostic_result = None
            if diagnostic_result is None:
                diagnostic_config = replace(
                    base,
                    **sampled,
                    scenario="linear_ramp_hold",
                    co2_start_ppm=float(start_ppm),
                    co2_end_ppm=float(start_ppm),
                    co2_ramp_years=float(ramp_years),
                    co2_hold_years=float(hold_years),
                    duration_years=float(ramp_years + hold_years),
                    forcing_mode="co2_only",
                    additional_forcing_wm2=0.0,
                    freshwater_hosing_sv=0.0,
                    auto_initialize_from_1850=False,
                    record_every_years=1.0,
                )
                diagnostic_result = _member_worker(
                    (
                        member_id,
                        asdict(diagnostic_config),
                        sampled,
                        constraint_mode,
                        diagnose_each,
                        run_calibration_experiments,
                        equilibrium_years,
                    )
                )
                save_compatible_checkpoint(
                    diagnostic_path,
                    run_fingerprint,
                    diagnostic_result,
                    checkpoint_metadata,
                )
            if diagnostic_result.get("status") != "ok":
                return diagnostic_result
            diagnostic_summary = dict(diagnostic_result["summary"])

        years: np.ndarray | None = None
        elapsed: np.ndarray | None = None
        target_count = int(len(target_values))
        amoc_rows: list[np.ndarray | None] = [None] * target_count
        decline_rows: list[np.ndarray | None] = [None] * target_count
        warming_rows: list[np.ndarray | None] = [None] * target_count
        co2_rows: list[np.ndarray | None] = [None] * target_count
        salt_errors: list[float] = []
        target_summaries: list[dict[str, Any] | None] = [None] * target_count
        target_failures: list[dict[str, Any]] = []
        first_run_summary: dict[str, Any] | None = None

        for target_index, target in enumerate(target_values):
            target_path = member_checkpoint_dir / f"target_{target_index:08d}.ckpt"
            target_record = (
                load_compatible_checkpoint(target_path, run_fingerprint)
                if resume
                else None
            )
            if result_is_failed(target_record) and retry_failed_on_resume:
                target_path.unlink(missing_ok=True)
                target_record = None
            attempted_target_simulations += 1
            if target_record is None:
                try:
                    config = replace(
                        base,
                        **sampled,
                        scenario="linear_ramp_hold",
                        co2_start_ppm=float(start_ppm),
                        co2_end_ppm=float(target),
                        co2_ramp_years=float(ramp_years),
                        co2_hold_years=float(hold_years),
                        duration_years=float(ramp_years + hold_years),
                        forcing_mode="co2_only",
                        additional_forcing_wm2=0.0,
                        freshwater_hosing_sv=0.0,
                        auto_initialize_from_1850=False,
                        record_every_years=1.0,
                    )
                    model = ProcessClimateModel(config)
                    model.state = shared_baseline_state.copy()
                    result = model.run()
                    frame = result.dataframe
                    current_years = frame["year"].to_numpy(dtype=np.float64)
                    amoc_raw = frame["amoc_sv"].to_numpy(dtype=np.float64)
                    co2_raw = frame["co2_ppm"].to_numpy(dtype=np.float64)
                    if amoc_raw.size == 0 or not math.isclose(
                        float(amoc_raw[0]), shared_initial_amoc, rel_tol=0.0, abs_tol=1.0e-8
                    ):
                        raise RuntimeError(
                            "Target trajectory did not begin from the common pre-forcing AMOC state."
                        )
                    if co2_raw.size == 0 or not math.isclose(
                        float(co2_raw[0]), float(start_ppm), rel_tol=0.0, abs_tol=1.0e-8
                    ):
                        raise RuntimeError(
                            "Target trajectory did not begin at the configured common CO2 start."
                        )
                    decline_values, initial_amoc = _amoc_decline_percent(
                        amoc_raw, shared_initial_amoc
                    )
                    amoc_values = np.asarray(amoc_raw, dtype=np.float32)
                    warming_values = frame["global_surface_warming_c"].to_numpy(dtype=np.float32)
                    co2_values = np.asarray(co2_raw, dtype=np.float32)
                    salt_error = float(frame["salt_conservation_error_ppm"].abs().max())
                    final_amoc = _final_window_mean(
                        amoc_raw, current_years, collapse_window_years
                    )
                    final_decline = _final_window_mean(
                        decline_values, current_years, collapse_window_years
                    )
                    final_warming = _final_window_mean(
                        warming_values, current_years, collapse_window_years
                    )
                    duration_diagnostics = collapse_duration_diagnostics(
                        amoc_raw,
                        current_years,
                        base.amoc_collapse_threshold_sv,
                        collapse_window_years,
                        persistence_fraction,
                        recovery_years,
                    )
                    target_summary = {
                        "target_ppm": float(target),
                        "common_start_ppm": float(start_ppm),
                        "initial_amoc_baseline_sv": float(initial_amoc),
                        "amoc_baseline_definition": AMOC_BASELINE_DEFINITION,
                        "initial_equilibration_years_used": float(
                            baseline_record["initial_equilibration_years_used"]
                        ),
                        "minimum_amoc_sv": float(np.nanmin(amoc_raw)),
                        "maximum_amoc_decline_percent": float(np.nanmax(decline_values)),
                        "final_window_amoc_sv": final_amoc,
                        "final_window_amoc_decline_percent": final_decline,
                        "final_window_warming_c": final_warming,
                        "persistence_required_fraction": persistence_fraction,
                        "recovery_disqualifying_years": recovery_years,
                        **duration_diagnostics,
                        "maximum_salt_error_ppm": salt_error,
                    }
                    target_record = {
                        "status": "ok",
                        "target_index": int(target_index),
                        "target_ppm": float(target),
                        "common_start_ppm": float(start_ppm),
                        "initial_amoc_baseline_sv": float(shared_initial_amoc),
                        "amoc_baseline_definition": AMOC_BASELINE_DEFINITION,
                        "years": current_years,
                        "amoc_sv": amoc_values,
                        "amoc_decline_percent": np.asarray(decline_values, dtype=np.float32),
                        "global_surface_warming_c": warming_values,
                        "co2_ppm": co2_values,
                        "target_summary": target_summary,
                        "run_summary": result.summary(),
                    }
                    save_compatible_checkpoint(
                        target_path,
                        run_fingerprint,
                        target_record,
                        checkpoint_metadata,
                    )
                    print(
                        f"Saved member {int(member_id) + 1} target {target_index + 1}/{len(target_values)} "
                        f"({float(target):g} ppm).",
                        flush=True,
                    )
                except Exception as target_exc:
                    target_record = {
                        "status": "failed",
                        "member": int(member_id),
                        "target_index": int(target_index),
                        "target_ppm": float(target),
                        "common_start_ppm": float(start_ppm),
                        "initial_amoc_baseline_sv": float(shared_initial_amoc),
                        "amoc_baseline_definition": AMOC_BASELINE_DEFINITION,
                        "error": f"{type(target_exc).__name__}: {target_exc}",
                        "traceback": traceback.format_exc(limit=12),
                        "attempted_target_simulations": 1,
                        "successful_target_simulations": 0,
                        "failed_target_simulations": 1,
                    }
                    try:
                        save_compatible_checkpoint(
                            target_path,
                            run_fingerprint,
                            target_record,
                            checkpoint_metadata,
                        )
                    except Exception as checkpoint_exc:
                        raise RuntimeError(
                            "Target simulation failed and its terminal failure "
                            f"checkpoint could not be saved: {checkpoint_exc}"
                        ) from target_exc
            if not isinstance(target_record, dict) or target_record.get("status") != "ok":
                failed_target_simulations += 1
                failure_record = {
                    "member": int(member_id),
                    "target_index": int(target_index),
                    "target_ppm": float(target),
                    "error": (
                        str(target_record.get("error", "Saved target checkpoint is not successful."))
                        if isinstance(target_record, dict)
                        else "Saved target checkpoint is unreadable."
                    ),
                    "traceback": (
                        str(target_record.get("traceback", ""))
                        if isinstance(target_record, dict)
                        else ""
                    ),
                }
                target_failures.append(failure_record)
                print(
                    f"Member {int(member_id) + 1} target {target_index + 1}/{len(target_values)} "
                    f"({float(target):g} ppm) failed; continuing remaining independent targets.",
                    flush=True,
                )
                continue
            if target_record.get("amoc_baseline_definition") != AMOC_BASELINE_DEFINITION:
                raise ValueError("Saved target checkpoint uses an incompatible AMOC baseline.")
            if not math.isclose(
                float(target_record.get("initial_amoc_baseline_sv", float("nan"))),
                shared_initial_amoc,
                rel_tol=0.0,
                abs_tol=1.0e-8,
            ):
                raise ValueError("Saved target checkpoint has a different member baseline.")

            current_years = np.asarray(target_record["years"], dtype=np.float64)
            if years is None:
                years = current_years
                elapsed = years - years[0]
                first_run_summary = dict(target_record["run_summary"])
            elif len(current_years) != len(years) or not np.allclose(
                current_years, years, rtol=0.0, atol=1.0e-8
            ):
                raise ValueError("CO2 target sweep members returned inconsistent time axes")
            amoc_rows[target_index] = np.asarray(
                target_record["amoc_sv"], dtype=np.float32
            )
            decline_rows[target_index] = np.asarray(
                target_record["amoc_decline_percent"], dtype=np.float32
            )
            warming_rows[target_index] = np.asarray(
                target_record["global_surface_warming_c"], dtype=np.float32
            )
            co2_rows[target_index] = np.asarray(
                target_record["co2_ppm"], dtype=np.float32
            )
            target_summary = dict(target_record["target_summary"])
            target_summaries[target_index] = target_summary
            salt_errors.append(float(target_summary["maximum_salt_error_ppm"]))
            successful_target_simulations += 1

        if years is None or elapsed is None or first_run_summary is None:
            raise RuntimeError("CO2 target sweep contained no successful targets")
        successful_indices = [
            index for index, row in enumerate(amoc_rows) if row is not None
        ]
        template = np.asarray(amoc_rows[successful_indices[0]], dtype=np.float32)

        def stack_optional(rows: list[np.ndarray | None]) -> np.ndarray:
            return np.stack(
                [
                    np.full(template.shape, np.nan, dtype=np.float32)
                    if row is None
                    else np.asarray(row, dtype=np.float32)
                    for row in rows
                ]
            ).astype(np.float32)

        summary = diagnostic_summary if diagnostic_summary is not None else first_run_summary
        summary["maximum_absolute_salt_conservation_error_ppm"] = (
            float(max(salt_errors)) if salt_errors else float("nan")
        )
        return {
            "member": int(member_id),
            "status": "ok" if failed_target_simulations == 0 else "partial",
            "sampled": sampled,
            "summary": summary,
            "years": years,
            "elapsed_years": elapsed,
            "targets_ppm": target_values,
            "common_start_ppm": float(start_ppm),
            "initial_amoc_baseline_sv": float(shared_initial_amoc),
            "amoc_baseline_definition": AMOC_BASELINE_DEFINITION,
            "baseline_initialization": baseline_record["initialization"],
            "baseline_diagnostics": baseline_diagnostics,
            "initial_equilibration_years_used": float(
                baseline_record["initial_equilibration_years_used"]
            ),
            "amoc_sv": stack_optional(amoc_rows),
            "amoc_decline_percent": stack_optional(decline_rows),
            "global_surface_warming_c": stack_optional(warming_rows),
            "co2_ppm": stack_optional(co2_rows),
            "target_summaries": target_summaries,
            "target_success_mask": np.asarray(
                [row is not None for row in target_summaries], dtype=bool
            ),
            "target_failures": target_failures,
            "attempted_target_simulations": int(attempted_target_simulations),
            "successful_target_simulations": int(successful_target_simulations),
            "failed_target_simulations": int(failed_target_simulations),
        }
    except Exception as exc:
        target_count = int(len(target_values)) if "target_values" in locals() else 0
        if attempted_target_simulations == 0 and target_count > 0:
            # A baseline/diagnostic failure makes every target unavailable for
            # this member, so account for those work units explicitly.
            attempted_target_simulations = target_count
            failed_target_simulations = target_count
        elif attempted_target_simulations > successful_target_simulations + failed_target_simulations:
            failed_target_simulations += 1
        failure = {
            "member": int(member_id),
            "status": "failed",
            "sampled": sampled,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(limit=12),
            "attempted_target_simulations": int(attempted_target_simulations),
            "successful_target_simulations": int(successful_target_simulations),
            "failed_target_simulations": int(failed_target_simulations),
        }
        if baseline_rejection_reason is not None:
            failure["failure_kind"] = "common_start_baseline_rejected"
            failure["baseline_rejection_reason"] = baseline_rejection_reason
            if baseline_diagnostics is not None:
                failure["baseline_diagnostics"] = baseline_diagnostics
        return failure

def _weighted_stats(values: np.ndarray, weights: np.ndarray) -> dict[str, float]:
    q = weighted_quantile(
        values, weights, [0.01, 0.05, 0.17, 0.50, 0.83, 0.95, 0.99]
    )
    valid = np.isfinite(values) & np.isfinite(weights) & (weights > 0.0)
    mean = (
        float(np.sum(values[valid] * weights[valid]) / np.sum(weights[valid]))
        if np.any(valid)
        else float("nan")
    )
    return {
        "weighted_mean": mean,
        "p01": float(q[0]),
        "p05": float(q[1]),
        "p17": float(q[2]),
        "median": float(q[3]),
        "p83": float(q[4]),
        "p95": float(q[5]),
        "p99": float(q[6]),
    }

def _conditional_ensemble_fraction(outcomes: np.ndarray, weights: np.ndarray) -> float:
    values = np.asarray(outcomes, dtype=float)
    weights = np.asarray(weights, dtype=float)
    valid = np.isfinite(values) & np.isfinite(weights) & (weights >= 0.0)
    total = float(np.sum(weights[valid]))
    return (
        float(np.sum(weights[valid] * (values[valid] > 0.5)) / total)
        if total > 0.0
        else float("nan")
    )


def _weighted_mean_timeseries_missing(
    values: np.ndarray, weights: np.ndarray
) -> np.ndarray:
    data = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    valid_members = np.any(np.isfinite(data), axis=1) & np.isfinite(weights) & (weights > 0.0)
    if not np.any(valid_members):
        return np.full(data.shape[1], np.nan, dtype=float)
    selected = data[valid_members]
    selected_weights = weights[valid_members]
    selected_weights = selected_weights / np.sum(selected_weights)
    return np.sum(selected * selected_weights[:, None], axis=0)


def _weighted_percentile_timeseries_missing(
    values: np.ndarray, weights: np.ndarray, percentiles: Sequence[float]
) -> np.ndarray:
    data = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    valid_members = np.any(np.isfinite(data), axis=1) & np.isfinite(weights) & (weights > 0.0)
    if not np.any(valid_members):
        return np.full((len(percentiles), data.shape[1]), np.nan, dtype=float)
    selected_weights = weights[valid_members]
    selected_weights = selected_weights / np.sum(selected_weights)
    return weighted_percentile_timeseries(
        data[valid_members], selected_weights, percentiles
    )


def _isotonic_non_decreasing(values: np.ndarray) -> np.ndarray:
    """Pool-adjacent-violators projection with equal target weights."""

    y = np.asarray(values, dtype=float)
    blocks: list[list[float]] = []
    for index, value in enumerate(y):
        blocks.append([float(value), 1.0, float(index), float(index + 1)])
        while len(blocks) >= 2 and blocks[-2][0] > blocks[-1][0]:
            right = blocks.pop()
            left = blocks.pop()
            weight = left[1] + right[1]
            mean = (left[0] * left[1] + right[0] * right[1]) / weight
            blocks.append([mean, weight, left[2], right[3]])
    result = np.empty_like(y)
    for mean, _, first, last in blocks:
        result[int(first):int(last)] = mean
    return np.clip(result, 0.0, 1.0)


def _monotonicity_diagnostics(values: np.ndarray, tolerance: float = 1.0e-12) -> dict[str, Any]:
    y = np.asarray(values, dtype=float)
    differences = np.diff(y)
    violations = differences < -tolerance
    return {
        "is_non_decreasing": bool(not np.any(violations)),
        "violation_count": int(np.sum(violations)),
        "maximum_downward_step": float(max(0.0, -np.min(differences))) if differences.size else 0.0,
    }


def _interpolated_crossing(
    targets_ppm: np.ndarray,
    fractions: np.ndarray,
    requested_fraction: float,
) -> float | None:
    x = np.asarray(targets_ppm, dtype=float)
    y = np.asarray(fractions, dtype=float)
    valid = np.isfinite(x) & np.isfinite(y)
    x = x[valid]
    y = y[valid]
    if x.size == 0 or float(np.max(y)) < requested_fraction:
        return None
    index = int(np.flatnonzero(y >= requested_fraction)[0])
    if index == 0:
        return float(x[0])
    if abs(y[index] - y[index - 1]) < 1.0e-15:
        return float(x[index])
    fraction = (requested_fraction - y[index - 1]) / (y[index] - y[index - 1])
    return float(x[index - 1] + fraction * (x[index] - x[index - 1]))


def _bootstrap_fraction_curves(
    outcomes: np.ndarray,
    weights: np.ndarray,
    samples: int,
    seed: int,
) -> np.ndarray:
    """Bootstrap partially paired target outcomes without treating failures as zero."""

    outcomes = np.asarray(outcomes, dtype=float)
    weights = np.asarray(weights, dtype=float)
    if outcomes.ndim != 2 or outcomes.shape[0] != weights.size:
        raise ValueError("Outcome matrix and member weights are inconsistent")
    if samples <= 0:
        return np.empty((0, outcomes.shape[1]), dtype=float)
    valid_weights = np.isfinite(weights) & (weights > 0.0)
    if not np.any(valid_weights):
        return np.full((samples, outcomes.shape[1]), np.nan, dtype=float)
    normalized = np.where(valid_weights, weights, 0.0)
    normalized = normalized / np.sum(normalized)
    rng = np.random.default_rng(seed)
    member_count = outcomes.shape[0]
    curves = np.full((samples, outcomes.shape[1]), np.nan, dtype=float)
    for index in range(samples):
        selected = rng.choice(member_count, size=member_count, replace=True, p=normalized)
        sampled = outcomes[selected]
        for target_index in range(outcomes.shape[1]):
            finite = np.isfinite(sampled[:, target_index])
            if np.any(finite):
                curves[index, target_index] = float(
                    np.mean(sampled[finite, target_index])
                )
    return curves


def _fraction_interval(
    bootstrap_curves: np.ndarray,
    confidence_level: float,
) -> tuple[np.ndarray, np.ndarray]:
    if bootstrap_curves.shape[0] == 0:
        width = bootstrap_curves.shape[1]
        return np.full(width, np.nan), np.full(width, np.nan)
    alpha = 1.0 - confidence_level
    return (
        np.nanquantile(bootstrap_curves, alpha / 2.0, axis=0),
        np.nanquantile(bootstrap_curves, 1.0 - alpha / 2.0, axis=0),
    )


def _threshold_estimates(
    targets_ppm: np.ndarray,
    point_fractions: np.ndarray,
    bootstrap_curves: np.ndarray,
    requested_fractions: Sequence[float],
    confidence_level: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    monotonicity = _monotonicity_diagnostics(point_fractions)
    projected = _isotonic_non_decreasing(point_fractions)
    alpha = 1.0 - confidence_level
    records: dict[str, Any] = {}
    for requested in requested_fractions:
        bootstrap_thresholds: list[float] = []
        for curve in bootstrap_curves:
            threshold = _interpolated_crossing(
                targets_ppm,
                _isotonic_non_decreasing(curve),
                requested,
            )
            if threshold is not None and math.isfinite(threshold):
                bootstrap_thresholds.append(float(threshold))
        estimate = _interpolated_crossing(targets_ppm, projected, requested)
        raw_estimate = _interpolated_crossing(targets_ppm, point_fractions, requested)
        if bootstrap_thresholds:
            lower, upper = np.quantile(
                bootstrap_thresholds,
                [alpha / 2.0, 1.0 - alpha / 2.0],
            )
            lower_value: float | None = float(lower)
            upper_value: float | None = float(upper)
        else:
            lower_value = None
            upper_value = None
        key = f"{int(round(100.0 * requested))}_percent"
        records[key] = {
            "estimate_ppm": estimate,
            "raw_first_crossing_ppm": raw_estimate,
            "confidence_lower_ppm": lower_value,
            "confidence_upper_ppm": upper_value,
            "confidence_level": confidence_level,
            "bootstrap_crossing_fraction": (
                float(len(bootstrap_thresholds) / len(bootstrap_curves))
                if len(bootstrap_curves)
                else None
            ),
            "method": "isotonic projection with weighted member bootstrap",
        }
    return records, monotonicity


def _make_overview_plot(summary: pd.DataFrame, output: Path) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(11.5, 17.0), constrained_layout=True)
    x = summary["target_ppm"].to_numpy(dtype=float)

    axes[0].fill_between(
        x,
        100.0 * summary["ever_collapse_conditional_fraction_ci_lower"],
        100.0 * summary["ever_collapse_conditional_fraction_ci_upper"],
        alpha=0.16,
    )
    axes[0].fill_between(
        x,
        100.0 * summary["persistent_collapse_conditional_fraction_ci_lower"],
        100.0 * summary["persistent_collapse_conditional_fraction_ci_upper"],
        alpha=0.16,
    )
    axes[0].plot(
        x,
        100.0 * summary["ever_collapse_conditional_ensemble_fraction"],
        marker="o",
        label="Ever AMOC ≤ threshold",
    )
    axes[0].plot(
        x,
        100.0 * summary["persistent_collapse_conditional_ensemble_fraction"],
        marker="o",
        label="Duration-based persistent collapse",
    )
    axes[0].set_ylabel("Conditional ensemble fraction (%)")
    axes[0].set_ylim(-2, 102)
    axes[0].set_title("Conditional AMOC outcome fractions by CO₂ target")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend()

    axes[1].fill_between(
        x, summary["final_amoc_p01"], summary["final_amoc_p99"], alpha=0.10, label="1–99%"
    )
    axes[1].fill_between(
        x, summary["final_amoc_p05"], summary["final_amoc_p95"], alpha=0.18, label="5–95%"
    )
    axes[1].fill_between(
        x, summary["final_amoc_p17"], summary["final_amoc_p83"], alpha=0.28, label="17–83%"
    )
    axes[1].plot(x, summary["final_amoc_median"], marker="o", label="Median")
    axes[1].axhline(
        float(summary["collapse_threshold_sv"].iloc[0]),
        linestyle="--",
        linewidth=1.0,
        label="Collapse threshold",
    )
    axes[1].set_ylabel("Final-window AMOC (Sv)")
    axes[1].set_title("AMOC state after the hold period")
    axes[1].grid(True, alpha=0.25)
    axes[1].legend()

    axes[2].fill_between(
        x,
        summary["final_amoc_decline_percent_p01"],
        summary["final_amoc_decline_percent_p99"],
        alpha=0.10,
        label="1–99%",
    )
    axes[2].fill_between(
        x,
        summary["final_amoc_decline_percent_p05"],
        summary["final_amoc_decline_percent_p95"],
        alpha=0.18,
        label="5–95%",
    )
    axes[2].fill_between(
        x,
        summary["final_amoc_decline_percent_p17"],
        summary["final_amoc_decline_percent_p83"],
        alpha=0.28,
        label="17–83%",
    )
    axes[2].plot(
        x, summary["final_amoc_decline_percent_median"], marker="o", label="Median"
    )
    axes[2].axhline(0.0, linestyle="--", linewidth=0.9)
    axes[2].set_ylabel("Final-window AMOC decline (%)")
    axes[2].set_title("AMOC decline relative to each member's initial baseline")
    axes[2].grid(True, alpha=0.25)
    axes[2].legend()

    axes[3].fill_between(
        x, summary["final_warming_p01"], summary["final_warming_p99"], alpha=0.10, label="1–99%"
    )
    axes[3].fill_between(
        x, summary["final_warming_p05"], summary["final_warming_p95"], alpha=0.18, label="5–95%"
    )
    axes[3].fill_between(
        x, summary["final_warming_p17"], summary["final_warming_p83"], alpha=0.28, label="17–83%"
    )
    axes[3].plot(x, summary["final_warming_median"], marker="o", label="Median")
    axes[3].set_xlabel("CO₂ target (ppm)")
    axes[3].set_ylabel("Final-window warming (°C)")
    axes[3].set_title("Climate response by CO₂ target")
    axes[3].grid(True, alpha=0.25)
    axes[3].legend()

    fig.savefig(output, dpi=180)
    plt.close(fig)


def _make_trajectory_plot(
    elapsed: np.ndarray,
    targets: np.ndarray,
    amoc: np.ndarray,
    weights: np.ndarray,
    threshold: float,
    plot_mode: str,
    max_plotted: int,
    output: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(12.5, 7.5), constrained_layout=True)
    cmap = plt.get_cmap("viridis")
    target_min = float(np.min(targets))
    target_span = max(float(np.max(targets) - target_min), 1.0)
    rng = np.random.default_rng(7319)
    member_count = amoc.shape[0]
    for target_index, target in enumerate(targets):
        color = cmap((float(target) - target_min) / target_span)
        values = amoc[:, target_index, :]
        valid_members = np.any(np.isfinite(values), axis=1)
        if plot_mode == "all":
            available = np.flatnonzero(valid_members)
            if max_plotted > 0 and len(available) > max_plotted:
                indices = np.sort(rng.choice(available, max_plotted, replace=False))
            else:
                indices = available
            alpha = min(0.35, max(0.015, 8.0 / max(len(indices), 1)))
            for member_index in indices:
                ax.plot(elapsed, values[member_index], color=color, alpha=alpha, linewidth=0.55)
        mean = _weighted_mean_timeseries_missing(values, weights)
        ax.plot(elapsed, mean, color=color, linewidth=1.7, label=f"{target:g} ppm")
    ax.axhline(threshold, linestyle="--", linewidth=1.1, color="black", label=f"{threshold:g} Sv threshold")
    ax.set_xlabel("Years since experiment start")
    ax.set_ylabel("AMOC (Sv)")
    ax.set_title(
        "Paired Monte Carlo AMOC trajectories — all members" if plot_mode == "all" else "Paired Monte Carlo mean AMOC trajectories"
    )
    ax.grid(True, alpha=0.22)
    columns = 2 if len(targets) <= 14 else 3
    ax.legend(ncol=columns, fontsize=8, loc="best")
    fig.savefig(output, dpi=180)
    plt.close(fig)


def _make_decline_trajectory_plot(
    elapsed: np.ndarray,
    targets: np.ndarray,
    decline_percent: np.ndarray,
    weights: np.ndarray,
    output: Path,
) -> None:
    """Plot weighted AMOC percentage-decline trajectories with all intervals."""

    fig, ax = plt.subplots(figsize=(12.5, 7.5), constrained_layout=True)
    cmap = plt.get_cmap("viridis")
    target_min = float(np.min(targets))
    target_span = max(float(np.max(targets) - target_min), 1.0)
    for target_index, target in enumerate(targets):
        color = cmap((float(target) - target_min) / target_span)
        values = decline_percent[:, target_index, :]
        q = _weighted_percentile_timeseries_missing(
            values, weights, (1.0, 5.0, 17.0, 50.0, 83.0, 95.0, 99.0)
        )
        ax.fill_between(elapsed, q[0], q[6], color=color, alpha=0.035)
        ax.fill_between(elapsed, q[1], q[5], color=color, alpha=0.055)
        ax.fill_between(elapsed, q[2], q[4], color=color, alpha=0.085)
        ax.plot(elapsed, q[3], color=color, linewidth=1.65, label=f"{target:g} ppm")
    ax.axhline(0.0, linestyle="--", linewidth=0.9, color="black")
    ax.set_xlabel("Years since experiment start")
    ax.set_ylabel("AMOC decline from initial baseline (%)")
    ax.set_title(
        "Paired Monte Carlo AMOC percentage decline — median with 17–83%, 5–95%, and 1–99% intervals"
    )
    ax.grid(True, alpha=0.22)
    columns = 2 if len(targets) <= 14 else 3
    ax.legend(ncol=columns, fontsize=8, loc="best")
    fig.savefig(output, dpi=180)
    plt.close(fig)


def run_sweep(args: Any) -> dict[str, Any]:
    """Run one paired sweep under an exclusive output-directory lock."""

    output = Path(args.output)
    with output_directory_run_lock(output, run_kind="co2_target_sweep"):
        try:
            return _run_sweep_unlocked(args)
        except BaseException as exc:
            state_path = run_state_path(Path(args.output))
            if state_path.exists():
                update_run_state(
                    state_path,
                    status=(
                        "interrupted"
                        if isinstance(exc, (KeyboardInterrupt, SystemExit))
                        else "failed"
                    ),
                    last_error=f"{type(exc).__name__}: {exc}",
                )
            raise


def _run_sweep_unlocked(args: Any) -> dict[str, Any]:
    start_ppm = float(args.sweep_start_ppm)
    target_mode = str(args.sweep_target_mode).strip().lower()
    step_ppm = float(args.sweep_step_ppm)
    maximum_ppm = float(args.sweep_max_ppm)
    specific_targets_input = str(args.sweep_specific_targets).strip()
    ramp_years = float(args.sweep_ramp_years)
    hold_years = float(args.sweep_hold_years)
    collapse_window_years = float(args.sweep_collapse_window_years)
    persistence_fraction = float(args.sweep_persistence_fraction)
    recovery_years = float(args.sweep_recovery_years)
    initial_equilibration_years = float(
        getattr(args, "sweep_initial_equilibration_years", 1000.0)
    )
    bootstrap_samples = int(args.sweep_bootstrap_samples)
    confidence_level = float(args.sweep_confidence_level)
    baseline_redraw_attempts = int(
        getattr(
            args,
            "sweep_baseline_redraw_attempts",
            DEFAULT_COMMON_START_REDRAW_ATTEMPTS,
        )
    )
    if start_ppm <= 0.0:
        raise ValueError("Sweep starting CO2 must be positive")
    if target_mode not in TARGET_MODES:
        raise ValueError(f"Sweep target mode must be one of {TARGET_MODES}")
    if target_mode == "increments" and (step_ppm <= 0.0 or maximum_ppm < start_ppm):
        raise ValueError(
            "Increment-mode sweep step must be positive and maximum must be at least start"
        )
    if ramp_years <= 0.0 or hold_years < 0.0:
        raise ValueError("Sweep ramp years must be positive and hold years cannot be negative")
    if collapse_window_years <= 0.0 or collapse_window_years > ramp_years + hold_years:
        raise ValueError("Collapse window must be positive and no longer than the experiment")
    if not 0.0 < persistence_fraction <= 1.0:
        raise ValueError("Persistence fraction must be in (0, 1]")
    if recovery_years < 0.0 or recovery_years > collapse_window_years:
        raise ValueError("Recovery years must be between zero and the collapse window")
    if (
        not math.isfinite(initial_equilibration_years)
        or initial_equilibration_years < 0.0
        or not float(initial_equilibration_years).is_integer()
    ):
        raise ValueError("Initial-equilibration years must be a non-negative whole number")
    if bootstrap_samples < 0:
        raise ValueError("Bootstrap samples cannot be negative")
    if not 0 <= baseline_redraw_attempts <= 100:
        raise ValueError("Baseline redraw attempts must be between 0 and 100")
    if not 0.0 < confidence_level < 1.0:
        raise ValueError("Confidence level must be between zero and one")
    if not 2 <= args.monte_carlo_runs <= 100000:
        raise ValueError("monte_carlo_runs must be between 2 and 100,000")

    requested_start_ppm = start_ppm
    targets = resolve_targets(
        target_mode,
        start_ppm,
        step_ppm,
        maximum_ppm,
        specific_targets_input,
    )
    args.scenario = "linear_ramp_hold"
    args.co2_start = start_ppm
    args.co2_end = float(targets[0])
    args.co2_ramp_years = ramp_years
    args.co2_hold_years = hold_years
    args.years = ramp_years + hold_years
    base_config = config_from_args(args)
    base_config = replace(
        base_config,
        scenario="linear_ramp_hold",
        co2_start_ppm=start_ppm,
        co2_end_ppm=float(targets[0]),
        co2_ramp_years=ramp_years,
        co2_hold_years=hold_years,
        duration_years=ramp_years + hold_years,
        forcing_mode="co2_only",
        additional_forcing_wm2=0.0,
        freshwater_hosing_sv=0.0,
        auto_initialize_from_1850=False,
        record_every_years=1.0,
    )
    base_config.validate()
    constraint_mode = normalize_constraint_mode(args.mc_constraint_mode)
    ranges = parse_ranges(args.mc_range, base_config, constraint_mode, args.mc_use_science_priors)
    args.output = prepare_output_directory(
        Path(args.output),
        overwrite=bool(args.overwrite_output),
        resume=bool(args.mc_resume),
        prompt=True,
    )
    output = Path(args.output)
    seed_requested = int(args.mc_seed)
    saved_seed, saved_seed_source, _saved_state = saved_seed_for_resume(
        output,
        run_kind="co2_target_sweep",
        requested_seed=seed_requested,
        resume=bool(args.mc_resume),
    )
    if saved_seed is None:
        seed_used, seed_source = resolve_random_seed(seed_requested)
    else:
        seed_used = int(saved_seed)
        seed_source = str(saved_seed_source)
    samples = generate_samples(
        base_config,
        ranges,
        args.monte_carlo_runs,
        seed_used,
        args.mc_sampling,
        args.mc_design,
        not args.mc_no_correlated_priors,
        science_modes=args.mc_use_science_priors,
    )
    redraw_seeds = [
        _common_start_redraw_seed(seed_used, attempt)
        for attempt in range(1, baseline_redraw_attempts + 1)
    ]
    redraw_sample_batches = [
        generate_samples(
            base_config,
            ranges,
            args.monte_carlo_runs,
            redraw_seed,
            args.mc_sampling,
            args.mc_design,
            not args.mc_no_correlated_priors,
            science_modes=args.mc_use_science_priors,
        )
        for redraw_seed in redraw_seeds
    ]
    workers = _automatic_worker_count(args.mc_workers)
    calibration = constraints_enabled(constraint_mode)
    provenance = runtime_provenance()
    run_fingerprint = stable_fingerprint(
        {
            "model_version": MODEL_VERSION,
            "runtime_provenance_digest": provenance["combined_digest_sha256"],
            "base_config": asdict(base_config),
            "ranges": ranges,
            "target_mode": target_mode,
            "targets": targets.tolist(),
            "common_start_ppm": start_ppm,
            "initial_equilibration_years": initial_equilibration_years,
            "amoc_baseline_definition": AMOC_BASELINE_DEFINITION,
            "runs": args.monte_carlo_runs,
            "seed_used": seed_used,
            "sampling": args.mc_sampling,
            "design": args.mc_design,
            "constraint_mode": constraint_mode,
            "correlated_priors": not args.mc_no_correlated_priors,
            "science_priors": args.mc_use_science_priors,
            "baseline_redraw_attempts": baseline_redraw_attempts,
            "baseline_redraw_seeds": redraw_seeds,
            "diagnose_each": bool(args.mc_diagnose_each),
            "calibration": calibration,
            "collapse_window_years": collapse_window_years,
            "persistence_fraction": persistence_fraction,
            "recovery_years": recovery_years,
        }
    )
    target_checkpoint_root = output / "co2_target_sweep_target_checkpoints"
    member_checkpoint_root = output / "co2_target_sweep_member_checkpoints"
    state_settings = {
        "base_config": asdict(base_config),
        "parameter_ranges": {name: list(bounds) for name, bounds in ranges.items()},
        "target_mode": target_mode,
        "requested_start_ppm": float(requested_start_ppm),
        "common_start_ppm": float(start_ppm),
        "targets_ppm": targets.tolist(),
        "specific_targets_input": specific_targets_input,
        "runs": int(args.monte_carlo_runs),
        "ramp_years": ramp_years,
        "hold_years": hold_years,
        "initial_equilibration_years": initial_equilibration_years,
        "amoc_baseline_definition": AMOC_BASELINE_DEFINITION,
        "collapse_window_years": collapse_window_years,
        "persistence_fraction": persistence_fraction,
        "recovery_years": recovery_years,
        "sampling": args.mc_sampling,
        "design": args.mc_design,
        "constraint_mode": constraint_mode,
        "science_priors": bool(args.mc_use_science_priors),
        "baseline_redraw_attempts": baseline_redraw_attempts,
        "baseline_redraw_seeds": redraw_seeds,
        "command_arguments": list(getattr(args, "saved_command_arguments", [])),
    }
    created_unix_seconds = time.time()
    state_template = {
        "format": RUN_STATE_FORMAT,
        "state_version": RUN_STATE_VERSION,
        "run_kind": "co2_target_sweep",
        "model_version": MODEL_VERSION,
        "status": "interrupted",
        "fingerprint": run_fingerprint,
        "seed_requested": int(seed_requested),
        "seed_used": int(seed_used),
        "seed_source": str(seed_source),
        "checkpoint_directory": target_checkpoint_root.name,
        "total_work_units": int(len(targets) * args.monte_carlo_runs),
        "completed_work_units": 0,
        "attempted_work_units": 0,
        "successful_work_units": 0,
        "failed_work_units": 0,
        "validated_work_units": 0,
        "pending_work_units": int(len(targets) * args.monte_carlo_runs),
        "resumed_work_units": 0,
        "work_unit_name": "target simulations",
        "settings": state_settings,
        "created_unix_seconds": created_unix_seconds,
        "updated_unix_seconds": created_unix_seconds,
        "completed_unix_seconds": None,
        "resume_count": 0,
        "last_error": None,
        "total_members": int(args.monte_carlo_runs),
        "completed_members": 0,
        "targets_per_member": int(len(targets)),
        "runtime_provenance": provenance,
        "checkpoint_format": "safe_json_npy_zip_v2_bounded",
    }
    checkpoint_metadata = {
        "run_kind": "co2_target_sweep",
        "model_version": MODEL_VERSION,
        "fingerprint": run_fingerprint,
        "seed_used": int(seed_used),
        "runtime_provenance_digest": provenance["combined_digest_sha256"],
        "command_arguments": list(getattr(args, "saved_command_arguments", [])),
        "state_template": state_template,
    }
    state_path = initialize_run_state(
        output,
        run_kind="co2_target_sweep",
        model_version=MODEL_VERSION,
        fingerprint=run_fingerprint,
        seed_requested=seed_requested,
        seed_used=seed_used,
        seed_source=seed_source,
        checkpoint_directory=target_checkpoint_root.name,
        total_work_units=int(len(targets) * args.monte_carlo_runs),
        work_unit_name="target simulations",
        resume=bool(args.mc_resume),
        settings=state_settings,
        extra={
            "total_members": int(args.monte_carlo_runs),
            "completed_members": 0,
            "targets_per_member": int(len(targets)),
            "runtime_provenance": provenance,
            "checkpoint_format": "safe_json_npy_zip_v2_bounded",
        },
    )
    def build_member_payload(
        member: int, sampled: dict[str, float]
    ) -> tuple[Any, ...]:
        return (
            member,
            asdict(base_config),
            sampled,
            start_ppm,
            targets.tolist(),
            ramp_years,
            hold_years,
            collapse_window_years,
            persistence_fraction,
            recovery_years,
            initial_equilibration_years,
            constraint_mode,
            bool(args.mc_diagnose_each),
            calibration,
            float(args.equilibrium_years),
            str(target_checkpoint_root),
            run_fingerprint,
            bool(args.mc_resume),
            bool(args.mc_retry_failed_on_resume),
            checkpoint_metadata,
        )

    payloads = [
        build_member_payload(member, sampled)
        for member, sampled in enumerate(samples)
    ]
    print(
        f"Starting paired CO2 target sweep: {len(targets)} targets × {args.monte_carlo_runs} members "
        f"= {len(targets) * args.monte_carlo_runs:,} transient simulations with {workers} worker(s).",
        flush=True,
    )
    print(f"Target mode: {target_mode}", flush=True)
    print(f"Common pre-forcing start: {start_ppm:g} ppm", flush=True)
    if np.any(targets < start_ppm - 1.0e-9):
        print(
            "Targets below the common start use descending linear ramps; the initial "
            "state and baseline are unchanged.",
            flush=True,
        )
    if abs(start_ppm - base_config.co2_reference_ppm) > COMMON_START_REFERENCE_TOLERANCE_PPM:
        print(
            f"Each member is spun up for {initial_equilibration_years:g} years at "
            "the non-reference common start, then must pass the active-AMOC, "
            "energy-balance, drift, and temperature-plausibility gates before "
            "any target ramp.",
            flush=True,
        )
    print("Targets (ppm): " + ", ".join(f"{value:g}" for value in targets), flush=True)
    if baseline_redraw_attempts > 0:
        print(
            "Common-start exclusions are expected rejection-sampling events, "
            f"not runtime errors; up to {baseline_redraw_attempts} deterministic "
            "replacement round(s) will refill invalid prior draws.",
            flush=True,
        )

    progress_interval = max(1, len(payloads) // 50)
    checkpoint_validation_cache: dict[str, bool] = {}

    def report_progress(
        completed: int, total: int, resumed_count: int, elapsed: float
    ) -> None:
        completed_this_run = max(completed - resumed_count, 0)
        rate = completed_this_run / max(elapsed, 1.0e-9)
        saved_targets = _count_target_checkpoints(
            target_checkpoint_root, run_fingerprint, checkpoint_validation_cache
        )
        state_now = load_run_state(output)
        prior_attempted = int(
            state_now.get("attempted_work_units", 0) if state_now is not None else 0
        )
        attempted_targets = max(prior_attempted, int(saved_targets))
        update_run_state(
            state_path,
            completed_work_units=attempted_targets,
            attempted_work_units=attempted_targets,
            successful_work_units=int(saved_targets),
            failed_work_units=int(max(attempted_targets - saved_targets, 0)),
            validated_work_units=int(saved_targets),
            pending_work_units=int(max(len(targets) * total - attempted_targets, 0)),
            resumed_work_units=int(resumed_count * len(targets)),
            completed_members=int(completed),
            elapsed_seconds=float(elapsed),
        )
        if completed == 1 or completed == total or completed % progress_interval == 0:
            print(
                f"Completed {completed}/{total} paired members; "
                f"saved {saved_targets}/{len(targets) * total} target simulations "
                f"({rate:.3f} members/s)",
                flush=True,
            )

    tasks = [(member, payload) for member, payload in enumerate(payloads)]
    results = run_supervised_tasks(
        tasks,
        _sweep_member_worker,
        max_workers=workers,
        timeout_seconds=float(args.mc_member_timeout_seconds),
        heartbeat_seconds=float(args.mc_heartbeat_seconds),
        checkpoint_dir=member_checkpoint_root,
        fingerprint=run_fingerprint,
        resume=bool(args.mc_resume),
        retry_failed_on_resume=bool(args.mc_retry_failed_on_resume),
        label="paired sweep members",
        progress_callback=report_progress,
        checkpoint_metadata=checkpoint_metadata,
    )

    # Invalid common-start climates are outside the support of a CO2-induced
    # collapse experiment. Replace those draws deterministically instead of
    # silently shrinking the requested ensemble or letting their target runs
    # fail later. Each redraw round has its own supervisor checkpoints, while
    # an accepted nested baseline remains resumable in the member target tree.
    rejection_history: dict[int, list[dict[str, Any]]] = {
        member: [] for member in range(int(args.monte_carlo_runs))
    }

    def record_baseline_rejection(result: dict[str, Any], attempt: int) -> None:
        member = int(result["member"])
        rejection_history[member].append(
            {
                "member": member,
                "draw_attempt": int(attempt),
                "error": str(result.get("error", "Common-start baseline rejected")),
                "sampled": dict(result.get("sampled", {})),
                "baseline_diagnostics": dict(
                    result.get("baseline_diagnostics", {})
                ),
            }
        )

    for result in results:
        result.setdefault("baseline_draw_attempt", 0)
        if _is_common_start_rejection(result):
            record_baseline_rejection(result, 0)
        result["baseline_rejected_draws"] = list(
            rejection_history[int(result["member"])]
        )

    for redraw_attempt, replacement_samples in enumerate(
        redraw_sample_batches, start=1
    ):
        rejected_members = [
            int(result["member"])
            for result in results
            if _is_common_start_rejection(result)
        ]
        if not rejected_members:
            break
        print(
            f"Common-start screening excluded {len(rejected_members)} prior "
            f"draw(s); trying deterministic replacement round "
            f"{redraw_attempt}/{baseline_redraw_attempts}.",
            flush=True,
        )
        for member in rejected_members:
            baseline_path = (
                target_checkpoint_root
                / f"member_{member:08d}"
                / "baseline.ckpt"
            )
            saved_baseline = load_compatible_checkpoint(
                baseline_path, run_fingerprint
            )
            if result_is_failed(saved_baseline):
                baseline_path.unlink(missing_ok=True)

        replacement_tasks = [
            (
                member,
                build_member_payload(member, replacement_samples[member]),
            )
            for member in rejected_members
        ]
        replacement_checkpoint_dir = (
            member_checkpoint_root / f"baseline_redraw_{redraw_attempt:02d}"
        )
        replacement_results = run_supervised_tasks(
            replacement_tasks,
            _sweep_member_worker,
            max_workers=workers,
            timeout_seconds=float(args.mc_member_timeout_seconds),
            heartbeat_seconds=float(args.mc_heartbeat_seconds),
            checkpoint_dir=replacement_checkpoint_dir,
            fingerprint=run_fingerprint,
            resume=bool(args.mc_resume),
            # A scientifically rejected draw must advance to the next
            # deterministic candidate, not rerun the same candidate forever.
            retry_failed_on_resume=False,
            label=f"baseline redraw {redraw_attempt} members",
            checkpoint_metadata=checkpoint_metadata,
        )
        accepted_this_round = 0
        for replacement in replacement_results:
            member = int(replacement["member"])
            replacement["baseline_draw_attempt"] = int(redraw_attempt)
            if _is_common_start_rejection(replacement):
                record_baseline_rejection(replacement, redraw_attempt)
            else:
                accepted_this_round += 1
            replacement["baseline_rejected_draws"] = list(
                rejection_history[member]
            )
            results[member] = replacement
            save_compatible_checkpoint(
                replacement_checkpoint_dir / f"member_{member:08d}.ckpt",
                run_fingerprint,
                replacement,
                checkpoint_metadata,
            )
        remaining_rejections = sum(
            _is_common_start_rejection(result) for result in results
        )
        print(
            f"Replacement round {redraw_attempt} accepted "
            f"{accepted_this_round}/{len(rejected_members)} draw(s); "
            f"{remaining_rejections} still require replacement.",
            flush=True,
        )

    exhausted_rejections = sum(
        _is_common_start_rejection(result) for result in results
    )
    if exhausted_rejections:
        print(
            f"{exhausted_rejections} member(s) exhausted all "
            f"{baseline_redraw_attempts} common-start replacement round(s) "
            "and remain failed.",
            flush=True,
        )

    baseline_rejection_records = [
        record
        for member_history in rejection_history.values()
        for record in member_history
    ]
    if baseline_rejection_records:
        flattened_rejections: list[dict[str, Any]] = []
        for record in baseline_rejection_records:
            row: dict[str, Any] = {
                "member": int(record["member"]),
                "draw_attempt": int(record["draw_attempt"]),
                "error": str(record["error"]),
            }
            row.update(
                {
                    f"sample_{name}": value
                    for name, value in record["sampled"].items()
                }
            )
            row.update(
                {
                    f"baseline_{name}": value
                    for name, value in record["baseline_diagnostics"].items()
                    if isinstance(value, (bool, int, float, str))
                }
            )
            flattened_rejections.append(row)
        pd.DataFrame(flattened_rejections).to_csv(
            output / "co2_target_sweep_baseline_rejections.csv", index=False
        )

    # Normalize older/synthetic worker records that predate target-level
    # accounting. This keeps resume and tests backward compatible while the
    # current worker always writes explicit masks and counters.
    for result in results:
        status = str(result.get("status", "failed")).lower()
        summaries = list(result.get("target_summaries", []))
        if len(summaries) < len(targets):
            summaries.extend([None] * (len(targets) - len(summaries)))
        result["target_summaries"] = summaries[: len(targets)]
        if "target_success_mask" not in result:
            if status == "ok":
                inferred_mask = np.ones(len(targets), dtype=bool)
            elif status == "partial":
                inferred_mask = np.asarray(
                    [item is not None for item in result["target_summaries"]],
                    dtype=bool,
                )
            else:
                inferred_mask = np.zeros(len(targets), dtype=bool)
            result["target_success_mask"] = inferred_mask
        else:
            result["target_success_mask"] = np.asarray(
                result["target_success_mask"], dtype=bool
            )
        inferred_successful = int(np.sum(result["target_success_mask"]))
        inferred_attempted = len(targets)
        result.setdefault("attempted_target_simulations", inferred_attempted)
        result.setdefault("successful_target_simulations", inferred_successful)
        result.setdefault(
            "failed_target_simulations",
            max(int(result["attempted_target_simulations"]) - inferred_successful, 0),
        )
        result.setdefault("target_failures", [])

    eligible = sorted(
        (r for r in results if r.get("status") in {"ok", "partial"}),
        key=lambda r: r["member"],
    )
    complete = [r for r in eligible if r.get("status") == "ok"]
    partial = [r for r in eligible if r.get("status") == "partial"]
    failed = sorted(
        (r for r in results if r.get("status") not in {"ok", "partial"}),
        key=lambda r: r["member"],
    )
    total_target_units = int(len(targets) * args.monte_carlo_runs)
    state_snapshot = load_run_state(output)
    validated_target_units = (
        compatible_checkpoint_count(output, state_snapshot)
        if state_snapshot is not None
        else 0
    )
    attempted_target_units = int(
        sum(
            int(result.get("attempted_target_simulations", 0))
            for result in results
        )
    )
    worker_successful_target_units = int(
        sum(
            int(result.get("successful_target_simulations", 0))
            for result in results
        )
    )
    failed_target_units = int(
        sum(int(result.get("failed_target_simulations", 0)) for result in results)
    )
    # A successful worker result is itself atomically checkpointed by the
    # supervisor, and each current worker saves its nested target checkpoint
    # before returning. Treat the larger independently reconstructed count as
    # validated so synthetic/in-memory supervisors and recovered member
    # checkpoints are not incorrectly reduced to zero.
    validated_target_units = max(validated_target_units, worker_successful_target_units)
    successful_target_units = worker_successful_target_units
    pending_target_units = max(total_target_units - attempted_target_units, 0)
    unavailable_target_units = max(total_target_units - successful_target_units, 0)
    update_run_state(
        state_path,
        completed_work_units=attempted_target_units,
        attempted_work_units=attempted_target_units,
        successful_work_units=successful_target_units,
        failed_work_units=failed_target_units,
        validated_work_units=int(validated_target_units),
        pending_work_units=pending_target_units,
        completed_members=int(args.monte_carlo_runs),
        successful_members=int(len(eligible)),
        failed_members=int(len(failed)),
    )

    # Baseline failures are member failures. Individual target failures are
    # independent missing cells and are assessed across all requested target
    # simulations rather than incorrectly discarding the whole paired member.
    validate_ensemble_survival(
        int(args.monte_carlo_runs), len(eligible), len(failed)
    )
    validate_ensemble_survival(
        total_target_units, successful_target_units, unavailable_target_units
    )
    weights, logweights, hard_reasons, targets_used = compute_importance_weights(
        eligible, constraint_mode
    )
    ess = float(1.0 / np.sum(weights**2))
    ensemble_quality = assess_ensemble_quality(
        int(args.monte_carlo_runs),
        len(eligible),
        len(failed),
        ess,
        constraints_enabled(constraint_mode),
    )
    elapsed_years = np.asarray(eligible[0]["elapsed_years"], dtype=np.float64)
    amoc = np.stack([r["amoc_sv"] for r in eligible]).astype(np.float32)
    amoc_decline_percent = np.stack(
        [r["amoc_decline_percent"] for r in eligible]
    ).astype(np.float32)
    warming = np.stack(
        [r["global_surface_warming_c"] for r in eligible]
    ).astype(np.float32)
    co2_members = np.stack([r["co2_ppm"] for r in eligible]).astype(np.float32)
    target_success_mask = np.stack(
        [np.asarray(r["target_success_mask"], dtype=bool) for r in eligible]
    )
    target_success_counts = np.sum(target_success_mask, axis=0).astype(int)
    target_failed_counts = int(args.monte_carlo_runs) - target_success_counts

    # Every requested CO2 target must independently satisfy the same survival
    # gate as a standalone ensemble. A failure concentrated at one extreme
    # target can no longer be diluted by successful cells at other targets.
    target_survival = validate_target_survival_counts(
        targets,
        target_success_counts,
        requested_members=int(args.monte_carlo_runs),
        allow_exploratory_target_counts=bool(
            getattr(args, "sweep_allow_exploratory_target_counts", False)
        ),
    )

    initial_amoc_baselines = np.asarray(
        [r["initial_amoc_baseline_sv"] for r in eligible], dtype=np.float64
    )
    if any(
        r.get("amoc_baseline_definition") != AMOC_BASELINE_DEFINITION
        for r in eligible
    ):
        raise RuntimeError("Sweep members contain inconsistent AMOC baselines")
    if any(
        not math.isclose(
            float(r.get("common_start_ppm", float("nan"))),
            start_ppm,
            rel_tol=0.0,
            abs_tol=1.0e-8,
        )
        for r in eligible
    ):
        raise RuntimeError("Sweep members contain inconsistent CO2 starts")
    co2 = np.full((len(targets), len(elapsed_years)), np.nan, dtype=np.float32)
    for target_index in range(len(targets)):
        available = np.flatnonzero(target_success_mask[:, target_index])
        if available.size:
            co2[target_index] = co2_members[int(available[0]), target_index]
    per_target_quantitative_count_gate = bool(
        np.all(
            target_success_counts
            >= MINIMUM_QUANTITATIVE_UNCERTAINTY_MEMBERS
        )
    )
    if not per_target_quantitative_count_gate:
        ensemble_quality["uncertainty_products_valid_for_quantitative_use"] = False
        ensemble_quality["quality_classification"] = (
            "exploratory_only_invalid_quantitative_uncertainty"
        )
        target_warning = (
            "At least one CO2 target has fewer than "
            f"{MINIMUM_QUANTITATIVE_UNCERTAINTY_MEMBERS} usable members; "
            "target-conditioned uncertainty products are exploratory only."
        )
        if target_warning not in ensemble_quality["warnings"]:
            ensemble_quality["warnings"].append(target_warning)

    ensemble_quality.update(
        {
            "complete_paired_members": int(len(complete)),
            "partial_paired_members": int(len(partial)),
            "baseline_failed_members": int(len(failed)),
            "successful_members_by_target": target_success_counts.tolist(),
            "failed_members_by_target": target_failed_counts.tolist(),
            "target_survival_gates": target_survival,
            "per_target_survival_gate_passed": True,
            "per_target_quantitative_count_gate_passed": (
                per_target_quantitative_count_gate
            ),
            "allow_exploratory_target_counts": bool(
                getattr(args, "sweep_allow_exploratory_target_counts", False)
            ),
            "target_simulation_survival_fraction": float(
                successful_target_units / total_target_units
            ),
            "target_simulation_failed_fraction": float(
                unavailable_target_units / total_target_units
            ),
        }
    )

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    member_rows: list[dict[str, Any]] = []
    failure_rows: list[dict[str, Any]] = []
    for member_index, result in enumerate(eligible):
        for target_summary in result["target_summaries"]:
            if target_summary is None:
                continue
            row = {
                "member": result["member"],
                "member_status": result["status"],
                "posterior_weight": float(weights[member_index]),
                "log_weight": float(logweights[member_index]),
                "hard_filter_reason": hard_reasons[member_index],
                **target_summary,
                **result["sampled"],
            }
            member_rows.append(row)
        for failure in result.get("target_failures", []):
            failure_rows.append(
                {
                    "failure_scope": "target",
                    **failure,
                    **result.get("sampled", {}),
                }
            )
    for result in failed:
        failure_rows.append(
            {
                "failure_scope": "member_baseline_or_diagnostic",
                "member": result["member"],
                "target_index": None,
                "target_ppm": None,
                "error": result.get("error", ""),
                "traceback": result.get("traceback", ""),
                **result.get("sampled", {}),
            }
        )
    members = pd.DataFrame(member_rows)
    members.to_csv(output / "co2_target_sweep_members.csv", index=False)
    if failure_rows:
        pd.DataFrame(failure_rows).to_csv(
            output / "co2_target_sweep_failures.csv", index=False
        )

    def outcome_matrix(field: str) -> np.ndarray:
        return np.asarray(
            [
                [
                    float("nan") if row is None else float(bool(row[field]))
                    for row in result["target_summaries"]
                ]
                for result in eligible
            ],
            dtype=float,
        )

    outcome_matrices = {
        "ever_collapse": outcome_matrix("ever_collapsed"),
        "persistent_collapse": outcome_matrix("persistent_collapsed"),
        "reversal": outcome_matrix("reversed"),
        "active": outcome_matrix("active"),
    }
    point_fraction_curves = {
        name: np.asarray(
            [
                _conditional_ensemble_fraction(matrix[:, index], weights)
                for index in range(matrix.shape[1])
            ],
            dtype=float,
        )
        for name, matrix in outcome_matrices.items()
    }
    bootstrap_curves = {
        name: _bootstrap_fraction_curves(
            matrix,
            weights,
            bootstrap_samples,
            seed_used + 104729 + offset,
        )
        for offset, (name, matrix) in enumerate(outcome_matrices.items())
    }
    fraction_intervals = {
        name: _fraction_interval(curves, confidence_level)
        for name, curves in bootstrap_curves.items()
    }

    summary_rows = []
    for target_index, target in enumerate(targets):
        group = members[members["target_ppm"] == target].sort_values("member")
        target_weights = group["posterior_weight"].to_numpy(dtype=float)
        minimum = group["minimum_amoc_sv"].to_numpy(dtype=float)
        final_amoc = group["final_window_amoc_sv"].to_numpy(dtype=float)
        maximum_decline = group["maximum_amoc_decline_percent"].to_numpy(dtype=float)
        final_decline = group["final_window_amoc_decline_percent"].to_numpy(dtype=float)
        final_warming = group["final_window_warming_c"].to_numpy(dtype=float)
        ever = group["ever_collapsed"].to_numpy(dtype=bool)
        persistent = group["persistent_collapsed"].to_numpy(dtype=bool)
        min_stats = _weighted_stats(minimum, target_weights)
        amoc_stats = _weighted_stats(final_amoc, target_weights)
        maximum_decline_stats = _weighted_stats(maximum_decline, target_weights)
        decline_stats = _weighted_stats(final_decline, target_weights)
        warming_stats = _weighted_stats(final_warming, target_weights)
        target_successes = int(len(group))
        summary_rows.append(
            {
                "target_ppm": float(target),
                "successful_members": target_successes,
                "failed_members": int(args.monte_carlo_runs) - target_successes,
                "collapse_threshold_sv": base_config.amoc_collapse_threshold_sv,
                "collapse_window_years": collapse_window_years,
                "persistence_required_fraction": persistence_fraction,
                "recovery_disqualifying_years": recovery_years,
                "ever_collapse_count": int(np.sum(ever)),
                "ever_collapse_unweighted_fraction": (
                    float(np.mean(ever)) if ever.size else float("nan")
                ),
                "ever_collapse_conditional_ensemble_fraction": point_fraction_curves["ever_collapse"][target_index],
                "ever_collapse_conditional_fraction_ci_lower": fraction_intervals["ever_collapse"][0][target_index],
                "ever_collapse_conditional_fraction_ci_upper": fraction_intervals["ever_collapse"][1][target_index],
                "persistent_collapse_count": int(np.sum(persistent)),
                "persistent_collapse_unweighted_fraction": (
                    float(np.mean(persistent)) if persistent.size else float("nan")
                ),
                "persistent_collapse_conditional_ensemble_fraction": point_fraction_curves["persistent_collapse"][target_index],
                "persistent_collapse_conditional_fraction_ci_lower": fraction_intervals["persistent_collapse"][0][target_index],
                "persistent_collapse_conditional_fraction_ci_upper": fraction_intervals["persistent_collapse"][1][target_index],
                "reversal_conditional_ensemble_fraction": point_fraction_curves["reversal"][target_index],
                "active_conditional_ensemble_fraction": point_fraction_curves["active"][target_index],
                "minimum_amoc_weighted_mean": min_stats["weighted_mean"],
                "minimum_amoc_p01": min_stats["p01"],
                "minimum_amoc_p05": min_stats["p05"],
                "minimum_amoc_median": min_stats["median"],
                "minimum_amoc_p95": min_stats["p95"],
                "minimum_amoc_p99": min_stats["p99"],
                "final_amoc_weighted_mean": amoc_stats["weighted_mean"],
                "final_amoc_p01": amoc_stats["p01"],
                "final_amoc_p05": amoc_stats["p05"],
                "final_amoc_p17": amoc_stats["p17"],
                "final_amoc_median": amoc_stats["median"],
                "final_amoc_p83": amoc_stats["p83"],
                "final_amoc_p95": amoc_stats["p95"],
                "final_amoc_p99": amoc_stats["p99"],
                "maximum_amoc_decline_percent_weighted_mean": maximum_decline_stats["weighted_mean"],
                "maximum_amoc_decline_percent_p01": maximum_decline_stats["p01"],
                "maximum_amoc_decline_percent_p05": maximum_decline_stats["p05"],
                "maximum_amoc_decline_percent_median": maximum_decline_stats["median"],
                "maximum_amoc_decline_percent_p95": maximum_decline_stats["p95"],
                "maximum_amoc_decline_percent_p99": maximum_decline_stats["p99"],
                "final_amoc_decline_percent_weighted_mean": decline_stats["weighted_mean"],
                "final_amoc_decline_percent_p01": decline_stats["p01"],
                "final_amoc_decline_percent_p05": decline_stats["p05"],
                "final_amoc_decline_percent_p17": decline_stats["p17"],
                "final_amoc_decline_percent_median": decline_stats["median"],
                "final_amoc_decline_percent_p83": decline_stats["p83"],
                "final_amoc_decline_percent_p95": decline_stats["p95"],
                "final_amoc_decline_percent_p99": decline_stats["p99"],
                "final_warming_weighted_mean": warming_stats["weighted_mean"],
                "final_warming_p01": warming_stats["p01"],
                "final_warming_p05": warming_stats["p05"],
                "final_warming_p17": warming_stats["p17"],
                "final_warming_median": warming_stats["median"],
                "final_warming_p83": warming_stats["p83"],
                "final_warming_p95": warming_stats["p95"],
                "final_warming_p99": warming_stats["p99"],
            }
        )
    summary_frame = pd.DataFrame(summary_rows)
    summary_frame.to_csv(output / "co2_target_sweep_summary.csv", index=False)

    weighted_mean_amoc = np.stack(
        [
            _weighted_mean_timeseries_missing(amoc[:, index, :], weights)
            for index in range(len(targets))
        ]
    )
    weighted_mean_decline = np.stack(
        [
            _weighted_mean_timeseries_missing(
                amoc_decline_percent[:, index, :], weights
            )
            for index in range(len(targets))
        ]
    )
    weighted_mean_warming = np.stack(
        [
            _weighted_mean_timeseries_missing(warming[:, index, :], weights)
            for index in range(len(targets))
        ]
    )
    percentile_rows = []
    decline_percentile_rows = []
    for target_index, target in enumerate(targets):
        amoc_q = _weighted_percentile_timeseries_missing(
            amoc[:, target_index, :], weights, PERCENTILES
        )
        decline_q = _weighted_percentile_timeseries_missing(
            amoc_decline_percent[:, target_index, :], weights, PERCENTILES
        )
        warming_q = _weighted_percentile_timeseries_missing(
            warming[:, target_index, :], weights, PERCENTILES
        )
        for time_index, elapsed_value in enumerate(elapsed_years):
            row = {
                "target_ppm": float(target),
                "successful_members": int(target_success_counts[target_index]),
                "elapsed_years": float(elapsed_value),
                "co2_ppm": float(co2[target_index, time_index]),
                "weighted_mean_amoc_sv": float(weighted_mean_amoc[target_index, time_index]),
                "weighted_mean_amoc_decline_percent": float(
                    weighted_mean_decline[target_index, time_index]
                ),
                "weighted_mean_warming_c": float(
                    weighted_mean_warming[target_index, time_index]
                ),
            }
            for percentile_index, percentile in enumerate(PERCENTILES):
                suffix = f"p{int(percentile):02d}"
                row[f"amoc_sv_{suffix}"] = float(amoc_q[percentile_index, time_index])
                row[f"amoc_decline_percent_{suffix}"] = float(
                    decline_q[percentile_index, time_index]
                )
                row[f"global_surface_warming_c_{suffix}"] = float(
                    warming_q[percentile_index, time_index]
                )
            percentile_rows.append(row)
            decline_percentile_rows.append(
                {
                    key: value
                    for key, value in row.items()
                    if key
                    in {
                        "target_ppm",
                        "successful_members",
                        "elapsed_years",
                        "co2_ppm",
                        "weighted_mean_amoc_decline_percent",
                    }
                    or key.startswith("amoc_decline_percent_")
                }
            )
    percentile_frame = pd.DataFrame(percentile_rows)
    percentile_frame.to_csv(
        output / "co2_target_sweep_percentile_timeseries.csv", index=False
    )
    mean_columns = [
        "target_ppm",
        "successful_members",
        "elapsed_years",
        "co2_ppm",
        "weighted_mean_amoc_sv",
        "weighted_mean_amoc_decline_percent",
        "weighted_mean_warming_c",
    ]
    percentile_frame[mean_columns].to_csv(
        output / "co2_target_sweep_mean_timeseries.csv", index=False
    )
    pd.DataFrame(decline_percentile_rows).to_csv(
        output / "co2_target_sweep_amoc_percent_decline_timeseries.csv",
        index=False,
    )
    if args.mc_save_long_csv:
        long_rows = []
        for member_index, result in enumerate(eligible):
            for target_index, target in enumerate(targets):
                if not target_success_mask[member_index, target_index]:
                    continue
                for time_index, elapsed_value in enumerate(elapsed_years):
                    long_rows.append(
                        {
                            "member": result["member"],
                            "posterior_weight": float(weights[member_index]),
                            "target_ppm": float(target),
                            "common_start_ppm": float(start_ppm),
                            "initial_amoc_baseline_sv": float(initial_amoc_baselines[member_index]),
                            "amoc_baseline_definition": AMOC_BASELINE_DEFINITION,
                            "elapsed_years": float(elapsed_value),
                            "co2_ppm": float(co2_members[member_index, target_index, time_index]),
                            "amoc_sv": float(amoc[member_index, target_index, time_index]),
                            "amoc_decline_percent": float(
                                amoc_decline_percent[member_index, target_index, time_index]
                            ),
                            "global_surface_warming_c": float(
                                warming[member_index, target_index, time_index]
                            ),
                        }
                    )
        pd.DataFrame(long_rows).to_csv(
            output / "co2_target_sweep_long_timeseries.csv", index=False
        )

    np.savez_compressed(
        output / "co2_target_sweep_timeseries.npz",
        elapsed_years=np.asarray(elapsed_years, dtype=np.float32),
        targets_ppm=np.asarray(targets, dtype=np.float32),
        posterior_weight=np.asarray(weights, dtype=np.float64),
        member=np.asarray([r["member"] for r in eligible], dtype=np.int32),
        member_status=np.asarray([r["status"] for r in eligible]),
        target_success_mask=target_success_mask,
        target_successful_members=target_success_counts,
        initial_amoc_baseline_sv=initial_amoc_baselines,
        amoc_baseline_definition=np.asarray(AMOC_BASELINE_DEFINITION),
        common_start_ppm=np.asarray(float(start_ppm)),
        initial_equilibration_years=np.asarray(float(initial_equilibration_years)),
        co2_ppm=co2,
        co2_ppm_by_member=co2_members,
        amoc_sv=amoc,
        amoc_decline_percent=amoc_decline_percent,
        global_surface_warming_c=warming,
    )

    if not args.mc_no_plots:
        _make_overview_plot(summary_frame, output / "co2_target_sweep_overview.png")
        _make_trajectory_plot(
            elapsed_years,
            targets,
            amoc,
            weights,
            base_config.amoc_collapse_threshold_sv,
            args.sweep_plot_mode,
            args.mc_max_plotted,
            output / "co2_target_sweep_amoc_trajectories.png",
        )
        _make_decline_trajectory_plot(
            elapsed_years,
            targets,
            amoc_decline_percent,
            weights,
            output / "co2_target_sweep_amoc_percent_decline_trajectories.png",
        )

    requested_threshold_fractions = (0.10, 0.50, 0.90)
    persistent_thresholds, persistent_monotonicity = _threshold_estimates(
        targets,
        point_fraction_curves["persistent_collapse"],
        bootstrap_curves["persistent_collapse"],
        requested_threshold_fractions,
        confidence_level,
    )
    ever_thresholds, ever_monotonicity = _threshold_estimates(
        targets,
        point_fraction_curves["ever_collapse"],
        bootstrap_curves["ever_collapse"],
        requested_threshold_fractions,
        confidence_level,
    )
    conditional_fraction_threshold_targets = {
        "persistent_collapse": persistent_thresholds,
        "ever_collapse": ever_thresholds,
    }
    monotonicity_checks = {
        "persistent_collapse": persistent_monotonicity,
        "ever_collapse": ever_monotonicity,
    }
    warnings = []
    if partial:
        warnings.append(
            f"{len(partial)} members had one or more target-specific failures; "
            "successful targets were retained and target-specific sample counts are reported."
        )
    if failed:
        warnings.append(
            f"{len(failed)} members failed before any target trajectory could be used."
        )
    minimum_target_members = int(np.min(target_success_counts))
    required_quantitative_members = int(
        ensemble_quality["minimum_successful_members_for_quantitative_uncertainty"]
    )
    target_count_gate = minimum_target_members >= required_quantitative_members
    ensemble_quality["minimum_successful_members_across_targets"] = minimum_target_members
    ensemble_quality["target_member_count_gate_passed"] = bool(target_count_gate)
    ensemble_quality["uncertainty_products_valid_for_quantitative_use"] = bool(
        ensemble_quality["uncertainty_products_valid_for_quantitative_use"]
        and target_count_gate
    )
    for outcome_name, diagnostics in monotonicity_checks.items():
        if not diagnostics["is_non_decreasing"]:
            warnings.append(
                f"{outcome_name} conditional ensemble fractions are not monotonic "
                f"across the sampled CO2 targets; threshold estimates use an "
                f"isotonic non-decreasing projection."
            )
    output_summary = {
        "model": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "monte_carlo_version": MONTE_CARLO_VERSION,
        "sweep_version": SWEEP_VERSION,
        "experiment": "paired_co2_target_sweep",
        "target_mode": target_mode,
        "requested_start_ppm": requested_start_ppm,
        "start_ppm": start_ppm,
        "common_start_ppm": start_ppm,
        "initial_equilibration_years": initial_equilibration_years,
        "baseline_initialization": (
            "native_reference_control_state"
            if abs(start_ppm - base_config.co2_reference_ppm) <= COMMON_START_REFERENCE_TOLERANCE_PPM
            else "constant_co2_spinup"
        ),
        "step_ppm": step_ppm if target_mode == "increments" else None,
        "maximum_ppm": maximum_ppm if target_mode == "increments" else None,
        "specific_targets_input": (
            specific_targets_input if target_mode == "specific" else None
        ),
        "targets_ppm": targets.tolist(),
        "ramp_years": ramp_years,
        "hold_years": hold_years,
        "collapse_window_years": collapse_window_years,
        "persistence_required_fraction": persistence_fraction,
        "recovery_disqualifying_years": recovery_years,
        "collapse_threshold_sv": base_config.amoc_collapse_threshold_sv,
        "bootstrap_samples": bootstrap_samples,
        "confidence_level": confidence_level,
        "percentile_bands": [1, 5, 17, 50, 83, 95, 99],
        "amoc_decline_definition": (
            "100 * (1 - AMOC / member pre-forcing t=0 AMOC); one exact "
            "member-specific baseline is shared by every CO2 target"
        ),
        "amoc_baseline_definition": AMOC_BASELINE_DEFINITION,
        "members_per_target_requested": int(args.monte_carlo_runs),
        "baseline_redraw_attempts_allowed": baseline_redraw_attempts,
        "baseline_redraw_seeds": redraw_seeds,
        "baseline_rejected_draws": len(baseline_rejection_records),
        "members_requiring_baseline_redraw": sum(
            bool(history) for history in rejection_history.values()
        ),
        "complete_paired_members": len(complete),
        "partial_paired_members": len(partial),
        "usable_members": len(eligible),
        "baseline_failed_members": len(failed),
        "successful_members_by_target": target_success_counts.tolist(),
        "failed_members_by_target": target_failed_counts.tolist(),
        "survival_fraction": ensemble_quality["survival_fraction"],
        "failed_member_fraction": ensemble_quality["failed_fraction"],
        "ensemble_quality": ensemble_quality,
        "uncertainty_products_valid_for_quantitative_use": ensemble_quality[
            "uncertainty_products_valid_for_quantitative_use"
        ],
        "total_transient_simulations_requested": int(len(targets) * args.monte_carlo_runs),
        "total_transient_simulations_attempted": attempted_target_units,
        "total_transient_simulations_successful": successful_target_units,
        "total_transient_simulations_failed": failed_target_units,
        "total_transient_simulations_validated": int(validated_target_units),
        "total_transient_simulations_pending": pending_target_units,
        "paired_parameter_design": True,
        "constraint_mode": constraint_mode,
        "posterior_weighting_enabled": constraints_enabled(constraint_mode),
        "effective_sample_size": ess,
        "seed_requested": seed_requested,
        "seed": seed_used,
        "seed_source": seed_source,
        "sampling_design": args.mc_design,
        "sampling_distribution": "mixed_physical_marginals" if args.mc_use_science_priors else args.mc_sampling,
        "plot_mode": args.sweep_plot_mode,
        "parameter_ranges": {name: {"minimum": bounds[0], "maximum": bounds[1]} for name, bounds in ranges.items()},
        "conditional_fraction_threshold_targets": conditional_fraction_threshold_targets,
        "monotonicity_checks": monotonicity_checks,
        "warnings": warnings,
        "output_files": [],
    }
    with (output / "co2_target_sweep_base_config.json").open("w", encoding="utf-8") as handle:
        json.dump(asdict(base_config), handle, indent=2)
    output_summary["output_files"] = sorted(
        {path.name for path in output.iterdir() if path.is_file()}
        | {"co2_target_sweep_summary.json"}
    )
    with (output / "co2_target_sweep_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(output_summary, handle, indent=2)
    with (output / "co2_target_sweep_ensemble_quality.json").open(
        "w", encoding="utf-8"
    ) as handle:
        json.dump(ensemble_quality, handle, indent=2)
    final_status = (
        "completed_with_partial_failures"
        if unavailable_target_units > 0
        else (
            "completed"
            if bool(ensemble_quality["uncertainty_products_valid_for_quantitative_use"])
            else "completed_with_quality_warning"
        )
    )
    update_run_state(
        state_path,
        status=final_status,
        completed_work_units=attempted_target_units,
        attempted_work_units=attempted_target_units,
        successful_work_units=successful_target_units,
        failed_work_units=failed_target_units,
        validated_work_units=int(validated_target_units),
        pending_work_units=pending_target_units,
        completed_members=int(args.monte_carlo_runs),
        successful_members=int(len(eligible)),
        failed_members=int(len(failed)),
        ensemble_quality=ensemble_quality,
        summary_file="co2_target_sweep_summary.json",
    )
    return output_summary


def build_parser():
    parser = build_monte_carlo_parser()
    parser.description = "Run a paired Monte Carlo AMOC sweep across linearly ramped CO2 targets."
    parser.set_defaults(
        scenario="linear_ramp_hold",
        co2_start=278.3,
        co2_end=278.3,
        co2_ramp_years=100.0,
        co2_hold_years=200.0,
        years=300.0,
        output=Path("outputs_co2_target_sweep"),
    )
    parser.add_argument("--sweep-start-ppm", type=float, default=278.3, help="Common initial CO2 concentration for every ramp.")
    parser.add_argument(
        "--sweep-target-mode",
        choices=TARGET_MODES,
        default="increments",
        help="Use regular increments or an explicit comma/space-separated target list.",
    )
    parser.add_argument("--sweep-step-ppm", type=float, default=50.0, help="Increment between successive CO2 targets in increment mode.")
    parser.add_argument("--sweep-max-ppm", type=float, default=1200.0, help="Maximum CO2 target in increment mode; always included exactly.")
    parser.add_argument(
        "--sweep-specific-targets",
        default="200,300,600,1200",
        help=(
            "Exact CO2 targets for specific mode, separated by commas, spaces, or "
            "semicolons. Values are sorted and deduplicated. Targets below the "
            "configured start use descending ramps; the common start is unchanged."
        ),
    )
    parser.add_argument(
        "--sweep-initial-equilibration-years",
        type=float,
        default=1000.0,
        help=(
            "Constant-CO2 spinup used only when the common sweep start differs "
            "from the model reference concentration. Must be a non-negative whole year count."
        ),
    )
    parser.add_argument(
        "--sweep-baseline-redraw-attempts",
        type=int,
        default=DEFAULT_COMMON_START_REDRAW_ATTEMPTS,
        help=(
            "Maximum deterministic replacement draws for a member whose "
            "common-start climate fails the mandatory physical baseline gate. "
            "Rejected draws are written to an audit CSV."
        ),
    )
    parser.add_argument("--sweep-ramp-years", type=float, default=100.0, help="Linear ramp duration for every target.")
    parser.add_argument("--sweep-hold-years", type=float, default=200.0, help="Years held at each target after the ramp.")
    parser.add_argument(
        "--sweep-collapse-window-years",
        type=float,
        default=30.0,
        help="Final window used for duration-based persistent-collapse classification.",
    )
    parser.add_argument(
        "--sweep-persistence-fraction",
        type=float,
        default=0.95,
        help="Required fraction of the final window classified as weak/collapsed.",
    )
    parser.add_argument(
        "--sweep-recovery-years",
        type=float,
        default=5.0,
        help="An active recovery spell this long disqualifies persistent collapse.",
    )
    parser.add_argument(
        "--sweep-bootstrap-samples",
        type=int,
        default=1000,
        help="Weighted member-bootstrap replicates for fraction and threshold intervals.",
    )
    parser.add_argument(
        "--sweep-confidence-level",
        type=float,
        default=0.90,
        help="Central confidence level for bootstrap intervals.",
    )
    parser.add_argument(
        "--sweep-allow-exploratory-target-counts",
        action="store_true",
        help=(
            "Permit export when a sweep requested at least the quantitative "
            "minimum member count but one or more targets retain fewer usable "
            "members. Independent per-target survival gates still apply and "
            "the products are explicitly classified as exploratory."
        ),
    )
    parser.add_argument("--sweep-plot-mode", choices=["mean", "all"], default="mean", help="Plot weighted ensemble means only or individual member curves plus means.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.saved_command_arguments = [
        argument
        for argument in sys.argv[1:]
        if argument not in {"--overwrite-output", "--mc-resume"}
    ]
    summary = run_sweep(args)
    print(json.dumps(summary, indent=2))
    print(f"\nCO2 target sweep outputs written to: {Path(args.output).resolve()}")


if __name__ == "__main__":
    main()
