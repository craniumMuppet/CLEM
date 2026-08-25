#!/usr/bin/env python3
"""Reproduce the v2.29.24 sea-ice validation runs.

Examples
--------
Historical rolling-origin skill at 10 degrees::

    python tools/validate_sea_ice_fix.py historical --resolution 10 \
        --output validation/sea_ice_fix/historical_10deg_reproduced.json

SSP2-4.5 response through 2100 at 5 degrees::

    python tools/validate_sea_ice_fix.py future --resolution 5 --scenario ssp245 \
        --output validation/sea_ice_fix/ssp245_5deg_reproduced.json

Two-hundred-year unforced stability at 10 degrees::

    python tools/validate_sea_ice_fix.py unforced --resolution 10 --duration 200 \
        --output validation/sea_ice_fix/unforced_10deg_reproduced.json

Complete 5/10-degree historical, four-scenario, and unforced matrix::

    python tools/validate_sea_ice_fix.py all \
        --output validation/sea_ice_fix/full_reproduced.json

The script deliberately uses ModelConfig defaults for the corrected sea-ice
parameters. It does not inject the calibration as command-line overrides.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any, Iterable

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from climate_model import EARTH_AREA_M2, MODEL_VERSION, ModelConfig, run_model
from sea_ice_validation import evaluate_result

SCENARIOS = ("ssp126", "ssp245", "ssp460", "ssp585")
RESOLUTIONS = (5.0, 10.0)
NOT_APPLICABLE_NUMERIC_COLUMNS = {
    "rcmip_total_effective_forcing_wm2",
    "rcmip_anthropogenic_effective_forcing_wm2",
    "rcmip_co2_effective_forcing_wm2",
    "hybrid_ssp_after_weight",
}


def _json_ready(value: Any) -> Any:
    """Convert numpy scalars/arrays and paths into strict JSON values."""
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, np.ndarray):
        return [_json_ready(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    return value


def _write_or_print(payload: dict[str, Any], output: Path | None) -> None:
    text = json.dumps(_json_ready(payload), indent=2, sort_keys=True, allow_nan=False)
    if output is None:
        print(text)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text + "\n", encoding="utf-8")
    print(f"Wrote {output}", file=sys.stderr, flush=True)


def _source_sha256() -> str:
    return hashlib.sha256((ROOT / "climate_model.py").read_bytes()).hexdigest()


def _locked_defaults(config: ModelConfig | None = None) -> dict[str, float]:
    cfg = config if config is not None else ModelConfig()
    return {
        "arctic_reference_air_temperature_at_full_latitude_c": float(
            cfg.arctic_reference_air_temperature_at_full_latitude_c
        ),
        "arctic_basal_ocean_exchange_wm2_k": float(
            cfg.arctic_basal_ocean_exchange_wm2_k
        ),
        "arctic_ice_area_formation_volume_sensitivity": float(
            cfg.arctic_ice_area_formation_volume_sensitivity
        ),
        "arctic_forced_ocean_heat_convergence_wm2_per_k": float(
            cfg.arctic_forced_ocean_heat_convergence_wm2_per_k
        ),
        "arctic_forced_ocean_heat_convergence_onset_warming_c": float(
            cfg.arctic_forced_ocean_heat_convergence_onset_warming_c
        ),
        "arctic_max_equivalent_thickness_m": float(
            cfg.arctic_max_equivalent_thickness_m
        ),
        "arctic_max_local_ice_thickness_m": float(
            cfg.arctic_max_local_ice_thickness_m
        ),
        "arctic_phase_restoring_deficit_saturation_fraction": float(
            cfg.arctic_phase_restoring_deficit_saturation_fraction
        ),
        "arctic_ice_area_thick_pack_resistance_exponent": float(
            cfg.arctic_ice_area_thick_pack_resistance_exponent
        ),
    }


def _nearest_index(years: np.ndarray, year: int, month: int) -> int:
    target = float(year) + (float(month) - 0.5) / 12.0
    return int(np.argmin(np.abs(years - target)))


def _integrated_ice_metrics(result: Any, index: int) -> tuple[float, float, float]:
    """Return volume (10^3 km3), mean thickness, and maximum thickness."""
    grid = result.grid
    atlantic_ocean = grid.atlantic_ocean_fraction_map
    non_atlantic_ocean = np.clip(
        grid.ocean_fraction_map - atlantic_ocean,
        0.0,
        1.0,
    )
    northern = grid.lat2d >= 0.0

    atlantic_fraction = result.atlantic_sea_ice_history[index][:, None]
    non_atlantic_fraction = result.non_atlantic_sea_ice_history[index][:, None]
    atlantic_thickness = (
        result.arctic_atlantic_local_ice_thickness_history_m[index][:, None]
    )
    non_atlantic_thickness = (
        result.arctic_non_atlantic_local_ice_thickness_history_m[index][:, None]
    )

    atlantic_weight = np.where(
        northern,
        atlantic_ocean * atlantic_fraction * grid.map_area_weights,
        0.0,
    )
    non_atlantic_weight = np.where(
        northern,
        non_atlantic_ocean * non_atlantic_fraction * grid.map_area_weights,
        0.0,
    )
    volume = float(
        np.sum(
            atlantic_weight * atlantic_thickness
            + non_atlantic_weight * non_atlantic_thickness
        )
        * EARTH_AREA_M2
        / 1.0e12
    )
    area = float(
        np.sum(atlantic_weight + non_atlantic_weight)
        * EARTH_AREA_M2
        / 1.0e12
    )
    mean_thickness = volume / area if area > 0.0 else 0.0

    active = np.concatenate(
        (
            atlantic_thickness[:, 0][np.any(atlantic_weight > 0.0, axis=1)],
            non_atlantic_thickness[:, 0][
                np.any(non_atlantic_weight > 0.0, axis=1)
            ],
        )
    )
    maximum_thickness = float(np.max(active)) if active.size else 0.0
    return volume, mean_thickness, maximum_thickness


def _common_state_checks(result: Any) -> dict[str, Any]:
    numeric_frame = result.dataframe.select_dtypes(include=[np.number])
    nonfinite_columns = [
        str(column)
        for column in numeric_frame.columns
        if not np.all(np.isfinite(numeric_frame[column].to_numpy(dtype=float)))
    ]
    unexpected_nonfinite_columns = sorted(
        set(nonfinite_columns) - NOT_APPLICABLE_NUMERIC_COLUMNS
    )
    maximum_thickness = float(
        max(
            np.max(result.arctic_atlantic_local_ice_thickness_history_m),
            np.max(result.arctic_non_atlantic_local_ice_thickness_history_m),
        )
    )
    return {
        "prognostic_state_arrays_finite": bool(
            not unexpected_nonfinite_columns
            and np.all(np.isfinite(result.atlantic_sea_ice_history))
            and np.all(np.isfinite(result.non_atlantic_sea_ice_history))
            and np.all(
                np.isfinite(result.arctic_atlantic_local_ice_thickness_history_m)
            )
            and np.all(
                np.isfinite(
                    result.arctic_non_atlantic_local_ice_thickness_history_m
                )
            )
        ),
        "not_applicable_nonfinite_diagnostic_columns": sorted(
            set(nonfinite_columns) & NOT_APPLICABLE_NUMERIC_COLUMNS
        ),
        "unexpected_nonfinite_numeric_columns": unexpected_nonfinite_columns,
        "ice_fractions_within_bounds": bool(
            np.min(result.atlantic_sea_ice_history) >= -1.0e-12
            and np.max(result.atlantic_sea_ice_history) <= 1.0 + 1.0e-12
            and np.min(result.non_atlantic_sea_ice_history) >= -1.0e-12
            and np.max(result.non_atlantic_sea_ice_history) <= 1.0 + 1.0e-12
        ),
        "maximum_local_ice_thickness_m": maximum_thickness,
    }


def _base_config(
    *,
    resolution: float,
    scenario: str,
    duration: float,
) -> ModelConfig:
    config = replace(
        ModelConfig(),
        start_year=1850.0,
        duration_years=duration,
        scenario=scenario,
        dt_years=0.05,
        record_every_years=0.05,
        resolution_deg=resolution,
        auto_initialize_from_1850=False,
    )
    config.validate()
    return config


def run_historical(resolution: float) -> dict[str, Any]:
    config = _base_config(
        resolution=resolution,
        scenario="ssp245",
        duration=177.0,
    )
    started = time.perf_counter()
    result = run_model(config, diagnose=False)
    runtime = time.perf_counter() - started
    evaluation = evaluate_result(result)

    rolling = evaluation["rolling_origin_historical_evaluation"]["metrics"]
    september = rolling["september_area"]
    march = rolling["march_area"]
    calibration_september = evaluation["calibration"]["months"]["9"]["area"]

    years = result.dataframe["year"].to_numpy(dtype=float)
    index = _nearest_index(years, 2025, 9)
    area = result.northern_sea_ice_area_extent_at_index(index)[
        "northern_hemisphere_sea_ice_area_million_km2"
    ]
    volume, mean_thickness, maximum_thickness = _integrated_ice_metrics(
        result,
        index,
    )
    return {
        "mode": "historical",
        "resolution_deg": resolution,
        "runtime_s": runtime,
        "defaults": _locked_defaults(config),
        "september_skill_vs_persistence": september[
            "model_skill_score_vs_persistence"
        ],
        "september_skill_vs_expanding_linear_trend": september[
            "model_skill_score_vs_expanding_linear_trend"
        ],
        "september_trend_million_km2_per_decade": calibration_september[
            "model_trend_million_km2_per_decade"
        ],
        "march_skill_vs_persistence": march["model_skill_score_vs_persistence"],
        "march_skill_vs_expanding_linear_trend": march[
            "model_skill_score_vs_expanding_linear_trend"
        ],
        "september_2025_area_million_km2": float(area),
        "september_2025_volume_thousand_km3": volume,
        "september_2025_mean_local_thickness_m": mean_thickness,
        "september_2025_maximum_local_thickness_m": maximum_thickness,
        **_common_state_checks(result),
    }


def run_future(scenario: str, resolution: float) -> dict[str, Any]:
    config = _base_config(
        resolution=resolution,
        scenario=scenario,
        duration=251.0,
    )
    started = time.perf_counter()
    result = run_model(config, diagnose=False)
    runtime = time.perf_counter() - started

    years = result.dataframe["year"].to_numpy(dtype=float)
    annual_years = np.arange(1850, 2101, dtype=int)
    march: list[float] = []
    september: list[float] = []
    september_volume: list[float] = []
    september_mean_thickness: list[float] = []
    september_max_thickness: list[float] = []

    for year in annual_years:
        march_index = _nearest_index(years, int(year), 3)
        september_index = _nearest_index(years, int(year), 9)
        march.append(
            float(
                result.northern_sea_ice_area_extent_at_index(march_index)[
                    "northern_hemisphere_sea_ice_area_million_km2"
                ]
            )
        )
        september.append(
            float(
                result.northern_sea_ice_area_extent_at_index(september_index)[
                    "northern_hemisphere_sea_ice_area_million_km2"
                ]
            )
        )
        volume, mean_thickness, maximum_thickness = _integrated_ice_metrics(
            result,
            september_index,
        )
        september_volume.append(volume)
        september_mean_thickness.append(mean_thickness)
        september_max_thickness.append(maximum_thickness)

    march_array = np.asarray(march)
    september_array = np.asarray(september)
    late_century = annual_years >= 2081
    common = _common_state_checks(result)
    return {
        "mode": "future",
        "scenario": scenario,
        "resolution_deg": resolution,
        "runtime_s": runtime,
        "defaults": _locked_defaults(config),
        "september_area_2100_million_km2": float(september_array[-1]),
        "september_area_2081_2100_mean_million_km2": float(
            np.mean(september_array[late_century])
        ),
        "march_area_2100_million_km2": float(march_array[-1]),
        "seasonal_amplitude_2100_million_km2": float(
            march_array[-1] - september_array[-1]
        ),
        "september_volume_2100_thousand_km3": float(september_volume[-1]),
        "september_mean_local_thickness_2100_m": float(
            september_mean_thickness[-1]
        ),
        "september_maximum_local_thickness_2100_m": float(
            september_max_thickness[-1]
        ),
        "maximum_single_year_september_loss_million_km2": float(
            np.max(np.maximum(september_array[:-1] - september_array[1:], 0.0))
        ),
        "maximum_single_year_september_gain_million_km2": float(
            np.max(np.maximum(september_array[1:] - september_array[:-1], 0.0))
        ),
        "final_global_surface_warming_c": float(
            result.dataframe.iloc[-1]["global_surface_warming_c"]
        ),
        "local_thickness_bound_respected": bool(
            common["maximum_local_ice_thickness_m"]
            <= config.arctic_max_equivalent_thickness_m + 1.0e-12
        ),
        **common,
    }


def run_unforced(resolution: float, duration: float = 200.0) -> dict[str, Any]:
    config = _base_config(
        resolution=resolution,
        scenario="constant",
        duration=duration,
    )
    started = time.perf_counter()
    result = run_model(config, diagnose=False)
    runtime = time.perf_counter() - started

    years = result.dataframe["year"].to_numpy(dtype=float)
    annual_years = np.arange(1850, int(1850 + duration), dtype=int)
    march: list[float] = []
    september: list[float] = []
    for year in annual_years:
        march_index = _nearest_index(years, int(year), 3)
        september_index = _nearest_index(years, int(year), 9)
        march.append(
            float(
                result.northern_sea_ice_area_extent_at_index(march_index)[
                    "northern_hemisphere_sea_ice_area_million_km2"
                ]
            )
        )
        september.append(
            float(
                result.northern_sea_ice_area_extent_at_index(september_index)[
                    "northern_hemisphere_sea_ice_area_million_km2"
                ]
            )
        )

    march_array = np.asarray(march)
    september_array = np.asarray(september)
    window = min(20, len(annual_years) // 2)
    if window < 1:
        raise ValueError("unforced duration must contain at least two full years")
    first = slice(0, window)
    last = slice(-window, None)
    gmst = result.dataframe["global_surface_warming_c"].to_numpy(dtype=float)
    toa = result.dataframe["toa_imbalance_wm2"].to_numpy(dtype=float)
    tail_count = max(1, int(20.0 / config.record_every_years))

    return {
        "mode": "unforced_constant",
        "resolution_deg": resolution,
        "duration_years": duration,
        "runtime_s": runtime,
        "defaults": _locked_defaults(config),
        "march_first_window_mean_million_km2": float(np.mean(march_array[first])),
        "march_last_window_mean_million_km2": float(np.mean(march_array[last])),
        "march_drift_million_km2": float(
            np.mean(march_array[last]) - np.mean(march_array[first])
        ),
        "september_first_window_mean_million_km2": float(
            np.mean(september_array[first])
        ),
        "september_last_window_mean_million_km2": float(
            np.mean(september_array[last])
        ),
        "september_drift_million_km2": float(
            np.mean(september_array[last]) - np.mean(september_array[first])
        ),
        "seasonal_amplitude_first_window_million_km2": float(
            np.mean(march_array[first] - september_array[first])
        ),
        "seasonal_amplitude_last_window_million_km2": float(
            np.mean(march_array[last] - september_array[last])
        ),
        "gmst_initial_c": float(gmst[0]),
        "gmst_final_c": float(gmst[-1]),
        "gmst_absolute_drift_c": float(abs(gmst[-1] - gmst[0])),
        "final_toa_imbalance_wm2": float(toa[-1]),
        "maximum_absolute_toa_imbalance_last_20_years_wm2": float(
            np.max(np.abs(toa[-tail_count:]))
        ),
        **_common_state_checks(result),
    }


def _acceptance_checks(payload: dict[str, Any]) -> dict[str, bool]:
    historical = payload["historical"]
    future = payload["future"]
    unforced = payload["unforced"]

    checks: dict[str, bool] = {}
    thickness_bound = float(
        payload["locked_defaults"]["arctic_max_equivalent_thickness_m"]
    )
    for resolution in RESOLUTIONS:
        key = str(int(resolution))
        record = historical[key]
        checks[f"historical_september_skill_positive_vs_persistence_{key}deg"] = bool(
            record["september_skill_vs_persistence"] > 0.0
        )
        checks[f"historical_september_skill_positive_vs_trend_{key}deg"] = bool(
            record["september_skill_vs_expanding_linear_trend"] > 0.0
        )
        checks[f"historical_march_skill_positive_{key}deg"] = bool(
            record["march_skill_vs_persistence"] > 0.0
            and record["march_skill_vs_expanding_linear_trend"] > 0.0
        )
        checks[f"historical_states_finite_and_bounded_{key}deg"] = bool(
            record["prognostic_state_arrays_finite"]
            and record["ice_fractions_within_bounds"]
            and record["maximum_local_ice_thickness_m"] <= thickness_bound + 1.0e-12
        )

        ssp245 = future[key]["ssp245"]
        checks[f"ssp245_september_2100_below_2_million_km2_{key}deg"] = bool(
            ssp245["september_area_2100_million_km2"] < 2.0
        )
        checks[f"ssp245_states_finite_and_bounded_{key}deg"] = bool(
            ssp245["prognostic_state_arrays_finite"]
            and ssp245["ice_fractions_within_bounds"]
            and ssp245["local_thickness_bound_respected"]
        )

        ordered = [
            future[key][scenario]["september_area_2100_million_km2"]
            for scenario in SCENARIOS
        ]
        checks[f"scenario_ordering_monotonic_{key}deg"] = bool(
            all(left > right for left, right in zip(ordered, ordered[1:]))
        )
        checks[f"all_scenario_thickness_bounded_{key}deg"] = bool(
            all(
                future[key][scenario]["local_thickness_bound_respected"]
                for scenario in SCENARIOS
            )
        )

        stable = unforced[key]
        checks[f"unforced_march_drift_below_0p01_million_km2_{key}deg"] = bool(
            abs(stable["march_drift_million_km2"]) < 0.01
        )
        checks[f"unforced_september_drift_below_0p01_million_km2_{key}deg"] = bool(
            abs(stable["september_drift_million_km2"]) < 0.01
        )
        checks[f"unforced_states_finite_and_bounded_{key}deg"] = bool(
            stable["prognostic_state_arrays_finite"]
            and stable["ice_fractions_within_bounds"]
            and stable["maximum_local_ice_thickness_m"] <= thickness_bound + 1.0e-12
        )

    difference = abs(
        future["5"]["ssp245"]["september_area_2100_million_km2"]
        - future["10"]["ssp245"]["september_area_2100_million_km2"]
    )
    checks["ssp245_cross_resolution_difference_below_0p2_million_km2"] = bool(
        difference < 0.2
    )
    return checks


def run_all() -> dict[str, Any]:
    historical: dict[str, Any] = {}
    future: dict[str, dict[str, Any]] = {}
    unforced: dict[str, Any] = {}

    for resolution in RESOLUTIONS:
        key = str(int(resolution))
        print(
            f"[historical] running {key}-degree locked defaults",
            file=sys.stderr,
            flush=True,
        )
        historical[key] = run_historical(resolution)

    for resolution in RESOLUTIONS:
        key = str(int(resolution))
        future[key] = {}
        for scenario in SCENARIOS:
            print(
                f"[future] running {scenario} at {key} degrees",
                file=sys.stderr,
                flush=True,
            )
            future[key][scenario] = run_future(scenario, resolution)

    for resolution in RESOLUTIONS:
        key = str(int(resolution))
        print(
            f"[unforced] running 200 years at {key} degrees",
            file=sys.stderr,
            flush=True,
        )
        unforced[key] = run_unforced(resolution, 200.0)

    payload: dict[str, Any] = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_version": MODEL_VERSION,
        "source_sha256": _source_sha256(),
        "locked_defaults": _locked_defaults(),
        "historical": historical,
        "future": future,
        "unforced": unforced,
    }
    checks = _acceptance_checks(payload)
    payload["acceptance_checks"] = checks
    payload["all_acceptance_checks_passed"] = bool(all(checks.values()))
    return payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Reproduce the actual sea-ice physics-fix validation using locked "
            "ModelConfig defaults."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    historical = subparsers.add_parser(
        "historical",
        help="run the historical trajectory and rolling-origin skill evaluation",
    )
    historical.add_argument("--resolution", type=float, choices=RESOLUTIONS, required=True)
    historical.add_argument("--output", type=Path)

    future = subparsers.add_parser(
        "future",
        help="run one SSP scenario through 2100",
    )
    future.add_argument("--resolution", type=float, choices=RESOLUTIONS, required=True)
    future.add_argument("--scenario", choices=SCENARIOS, required=True)
    future.add_argument("--output", type=Path)

    unforced = subparsers.add_parser(
        "unforced",
        help="run a constant-forcing stability experiment",
    )
    unforced.add_argument("--resolution", type=float, choices=RESOLUTIONS, required=True)
    unforced.add_argument("--duration", type=float, default=200.0)
    unforced.add_argument("--output", type=Path)

    complete = subparsers.add_parser(
        "all",
        help="run both resolutions, all four SSP pathways, and unforced stability",
    )
    complete.add_argument("--output", type=Path)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)
    if args.command == "historical":
        payload = run_historical(args.resolution)
    elif args.command == "future":
        payload = run_future(args.scenario, args.resolution)
    elif args.command == "unforced":
        payload = run_unforced(args.resolution, args.duration)
    elif args.command == "all":
        payload = run_all()
    else:
        raise AssertionError(f"unsupported command: {args.command}")
    _write_or_print(payload, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
