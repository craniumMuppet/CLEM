#!/usr/bin/env python3
"""Run literature-grounded development regression checks and AMOC diagnostics.

The v2.27 parameter set was adjusted against these ranges, so the bundled checks
are reproducible regression targets rather than independent held-out validation.
Structural tests remain separate and have no external pass/fail threshold.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np

from climate_model import MODEL_VERSION, ModelConfig, ProcessClimateModel


HERE = Path(__file__).resolve().parent
DEFAULT_BENCHMARKS = HERE / "development_regression_benchmarks.json"
DEFAULT_CALIBRATION_REGISTRY = HERE / "calibration_targets.json"
PROCESSING_SCRIPT = Path(__file__).name
REQUIRED_PROVENANCE_FIELDS = {
    "source_title",
    "source_reference",
    "source_url",
    "source_location",
    "retrieval_date",
    "dataset_version",
    "processing_script",
}


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()




def annual_mean_frame(frame):
    """Return time-weighted calendar-year means from subannual model output.

    Values at exact year boundaries are linearly interpolated and each numeric
    column is integrated with the trapezoidal rule.  A frame that contains only
    annual snapshots is returned unchanged because a fixed seasonal phase
    cannot be reconstructed into an annual mean after the fact.
    """
    ordered = frame.sort_values("year").reset_index(drop=True)
    years = ordered["year"].to_numpy(dtype=float)
    if len(years) < 2 or float(np.nanmedian(np.diff(years))) >= 0.95:
        return ordered.copy()
    numeric = [
        column for column in ordered.columns
        if column != "year" and np.issubdtype(ordered[column].dtype, np.number)
    ]
    first = int(np.ceil(years[0] - 1.0e-10))
    last = int(np.floor(years[-1] + 1.0e-10)) - 1
    records = []
    for year in range(first, last + 1):
        left = float(year)
        right = float(year + 1)
        inside = years[(years > left) & (years < right)]
        sample_times = np.concatenate(([left], inside, [right]))
        row = {"year": float(year)}
        for column in numeric:
            values = ordered[column].to_numpy(dtype=float)
            samples = np.interp(sample_times, years, values)
            row[column] = float(np.trapezoid(samples, sample_times))
        records.append(row)
    return type(ordered).from_records(records)

def window_mean(frame, column: str, start: float, end: float) -> float:
    mask = (frame["year"] >= start) & (frame["year"] <= end)
    if not np.any(mask):
        return float("nan")
    return float(frame.loc[mask, column].mean())


def linear_trend(frame, column: str, start: float, end: float) -> float:
    mask = (frame["year"] >= start) & (frame["year"] <= end)
    subset = frame.loc[mask, ["year", column]].dropna()
    if len(subset) < 3:
        return float("nan")
    return float(np.polyfit(subset["year"], subset[column], 1)[0])


def historical_external_metrics(frame) -> dict[str, float]:
    baseline_amoc = window_mean(frame, "amoc_sv", 1995.0, 2014.0)
    endpoint_amoc = window_mean(frame, "amoc_sv", 2081.0, 2100.0)
    global_trend = linear_trend(frame, "global_near_surface_air_warming_c", 1979.0, 2021.0)
    arctic_trend = linear_trend(frame, "arctic_near_surface_air_warming_c", 1979.0, 2021.0)
    arctic_ratio = arctic_trend / global_trend if abs(global_trend) > 1.0e-12 else float("nan")
    ohc_1971 = window_mean(frame, "ocean_heat_content_anomaly_zj", 1970.5, 1971.5)
    ohc_2018 = window_mean(frame, "ocean_heat_content_anomaly_zj", 2017.5, 2018.5)
    gmst_baseline = window_mean(
        frame, "global_surface_warming_c", 1850.0, 1900.0
    )
    gmst_2011_2020 = window_mean(
        frame, "global_surface_warming_c", 2011.0, 2020.0
    )
    return {
        "historical_gmst_2011_2020_c": gmst_2011_2020 - gmst_baseline,
        "historical_ocean_heat_content_change_1971_2018_zj": ohc_2018 - ohc_1971,
        "historical_arctic_amplification_1979_2021_ratio": arctic_ratio,
        "ssp245_amoc_decline_2100_percent": 100.0 * (
            1.0 - endpoint_amoc / baseline_amoc
        ),
    }


def forced_decline(config: ModelConfig, freshwater_sv: float) -> dict[str, float]:
    experiment = replace(
        config,
        start_year=1850.0,
        duration_years=80.0,
        scenario="constant",
        co2_start_ppm=config.co2_reference_ppm,
        additional_forcing_wm2=0.0,
        freshwater_hosing_sv=freshwater_sv,
        freshwater_start_fraction=0.0,
        freshwater_ramp_years=0.0,
        warming_freshwater_sv_per_k=0.0,
        auto_initialize_from_1850=False,
        record_every_years=1.0,
    )
    frame = ProcessClimateModel(experiment).run().dataframe
    initial = float(frame.iloc[0]["amoc_sv"])
    around_year_40 = window_mean(frame, "amoc_sv", 1885.0, 1895.0)
    decline = 100.0 * (1.0 - around_year_40 / initial)
    return {
        "freshwater_sv": freshwater_sv,
        "initial_amoc_sv": initial,
        "amoc_around_year_40_sv": around_year_40,
        "decline_percent": decline,
    }


def hosing_recovery(config: ModelConfig) -> dict[str, float]:
    experiment = replace(
        config,
        start_year=1850.0,
        duration_years=140.0,
        scenario="constant",
        co2_start_ppm=config.co2_reference_ppm,
        additional_forcing_wm2=0.0,
        warming_freshwater_sv_per_k=0.0,
        auto_initialize_from_1850=False,
        record_every_years=1.0,
    )
    model = ProcessClimateModel(experiment)
    initial = float(model.state.amoc_sv)
    dt = experiment.dt_years
    elapsed = 0.0
    model._freshwater_override_sv = 0.1
    while elapsed < 40.0 - 1.0e-12:
        step = min(dt, 40.0 - elapsed)
        model.step(elapsed, step)
        elapsed += step
    after_hosing = float(model.state.amoc_sv)
    model._freshwater_override_sv = 0.0
    while elapsed < 140.0 - 1.0e-12:
        step = min(dt, 140.0 - elapsed)
        model.step(elapsed, step)
        elapsed += step
    after_recovery = float(model.state.amoc_sv)
    model._freshwater_override_sv = None
    lost = initial - after_hosing
    recovered = after_recovery - after_hosing
    recovery_fraction = recovered / lost if lost > 0.0 else float("nan")
    return {
        "initial_amoc_sv": initial,
        "amoc_after_40yr_hosing_sv": after_hosing,
        "amoc_after_100yr_recovery_sv": after_recovery,
        "recovery_percent_of_initial_loss": 100.0 * recovery_fraction,
    }


def cross_resolution(config: ModelConfig) -> list[dict[str, float]]:
    rows = []
    for resolution in (2.5, 5.0, 10.0):
        control_config = replace(
            config,
            resolution_deg=resolution,
            scenario="constant",
            duration_years=100.0,
            additional_forcing_wm2=0.0,
            record_every_years=100.0,
            auto_initialize_from_1850=False,
        )
        control_model = ProcessClimateModel(control_config)
        initial_ratio = control_model.baseline_density_driver_ratio
        control = control_model.run().dataframe.iloc[-1]
        forced = ProcessClimateModel(
            replace(control_config, scenario="step_2x")
        ).run().dataframe.iloc[-1]
        rows.append(
            {
                "resolution_deg": resolution,
                "initial_density_driver_ratio": initial_ratio,
                "control_gmst_c": float(control["global_surface_warming_c"]),
                "control_amoc_sv": float(control["amoc_sv"]),
                "control_toa_imbalance_wm2": float(control["toa_imbalance_wm2"]),
                "abrupt_2x_100yr_gmst_c": float(forced["global_surface_warming_c"]),
                "abrupt_2x_100yr_amoc_sv": float(forced["amoc_sv"]),
                "abrupt_2x_100yr_toa_imbalance_wm2": float(
                    forced["toa_imbalance_wm2"]
                ),
            }
        )
    return rows


def load_calibration_registry(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    targets = payload.get("calibration_targets")
    if not isinstance(targets, dict) or not targets:
        raise ValueError("calibration registry must contain calibration_targets")
    return payload


def load_benchmarks(
    path: Path,
    calibration_registry_path: Path = DEFAULT_CALIBRATION_REGISTRY,
) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    benchmarks = payload.get("benchmarks")
    if not isinstance(benchmarks, dict) or not benchmarks:
        raise ValueError("benchmark file must contain a non-empty 'benchmarks' object")
    registry = load_calibration_registry(calibration_registry_path)
    calibration_names = set(registry["calibration_targets"])
    overlap = calibration_names.intersection(benchmarks)
    if overlap:
        raise ValueError(
            "held-out benchmark file overlaps calibration targets: "
            + ", ".join(sorted(overlap))
        )
    for name, benchmark in benchmarks.items():
        if not isinstance(benchmark.get("used_for_tuning"), bool):
            raise ValueError(
                f"benchmark {name!r} must explicitly declare used_for_tuning"
            )
        if float(benchmark["minimum"]) > float(benchmark["maximum"]):
            raise ValueError(f"benchmark {name!r} has inverted bounds")
        missing = sorted(REQUIRED_PROVENANCE_FIELDS.difference(benchmark))
        if missing:
            raise ValueError(
                f"benchmark {name!r} is missing provenance: {', '.join(missing)}"
            )
        if benchmark["processing_script"] != PROCESSING_SCRIPT:
            raise ValueError(
                f"benchmark {name!r} must identify {PROCESSING_SCRIPT} as its processing script"
            )
        benchmark["benchmark_definition_sha256"] = canonical_sha256(benchmark)
    payload["benchmark_set_sha256"] = file_sha256(path)
    payload["calibration_registry_sha256"] = file_sha256(calibration_registry_path)
    return payload


def evaluate_benchmarks(
    metrics: dict[str, float], benchmark_payload: dict[str, Any]
) -> dict[str, Any]:
    evaluations: dict[str, Any] = {}
    missing_metrics = sorted(set(benchmark_payload["benchmarks"]).difference(metrics))
    if missing_metrics:
        raise ValueError("missing validation metrics: " + ", ".join(missing_metrics))
    for name, benchmark in benchmark_payload["benchmarks"].items():
        value = float(metrics[name])
        lower = float(benchmark["minimum"])
        upper = float(benchmark["maximum"])
        passed = bool(np.isfinite(value) and lower <= value <= upper)
        evaluations[name] = {
            "value": value,
            "minimum": lower,
            "maximum": upper,
            "units": benchmark.get("units", "unknown"),
            "passed": passed,
            "distance_below_range": max(lower - value, 0.0),
            "distance_above_range": max(value - upper, 0.0),
            "evidence_role": benchmark["evidence_role"],
            "used_for_tuning": bool(benchmark["used_for_tuning"]),
            "source_title": benchmark["source_title"],
            "source_reference": benchmark["source_reference"],
            "source_url": benchmark["source_url"],
            "source_location": benchmark["source_location"],
            "retrieval_date": benchmark["retrieval_date"],
            "dataset_version": benchmark["dataset_version"],
            "processing_script": benchmark["processing_script"],
            "benchmark_definition_sha256": benchmark["benchmark_definition_sha256"],
            "description": benchmark.get("description", ""),
            "notes": benchmark.get("notes", ""),
        }
    return {
        "all_regression_benchmarks_passed": all(
            item["passed"] for item in evaluations.values()
        ),
        "all_external_benchmarks_passed": all(item["passed"] for item in evaluations.values()),
        "passed_count": sum(item["passed"] for item in evaluations.values()),
        "total_count": len(evaluations),
        "evaluations": evaluations,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path)
    parser.add_argument("--benchmarks", type=Path, default=DEFAULT_BENCHMARKS)
    parser.add_argument(
        "--calibration-registry", type=Path, default=DEFAULT_CALIBRATION_REGISTRY
    )
    parser.add_argument(
        "--output", type=Path, default=Path("development_regression_validation.json")
    )
    parser.add_argument(
        "--fail-on-benchmark",
        action="store_true",
        help="Exit with status 2 when any development regression benchmark fails.",
    )
    args = parser.parse_args()

    config = ModelConfig()
    if args.config:
        with args.config.open("r", encoding="utf-8") as handle:
            config = ModelConfig(**json.load(handle))
    benchmark_payload = load_benchmarks(
        args.benchmarks, args.calibration_registry
    )

    ssp245_config = replace(
        config,
        start_year=1850.0,
        duration_years=251.0,
        scenario="ssp245",
        record_every_years=config.dt_years,
        auto_initialize_from_1850=False,
    )
    ssp245_subannual = ProcessClimateModel(ssp245_config).run().dataframe
    ssp245 = annual_mean_frame(ssp245_subannual)
    external_metrics = historical_external_metrics(ssp245)
    config_payload = asdict(config)

    result = {
        "model_version": MODEL_VERSION,
        "reproducibility": {
            "model_config_sha256": canonical_sha256(config_payload),
            "benchmark_set_sha256": benchmark_payload["benchmark_set_sha256"],
            "calibration_registry_sha256": benchmark_payload[
                "calibration_registry_sha256"
            ],
            "processing_script_sha256": file_sha256(Path(__file__)),
            "benchmark_set_version": benchmark_payload.get(
                "benchmark_set_version", "unknown"
            ),
            "benchmark_schema_version": benchmark_payload.get(
                "schema_version", "unknown"
            ),
        },
        "evidence_partition": {
            "tuning_informed_development_regressions": {
                "legacy_alias": "external_held_out_validation",
                "validation_status": "development_regression_not_independent",
                "interpretation": "Legacy key retained for compatibility; v2.27 was adjusted against these literature ranges.",
                "used_for_posterior_weighting": False,
                "used_for_parameter_tuning": True,
                "metrics": external_metrics,
                "benchmark_results": evaluate_benchmarks(
                    external_metrics, benchmark_payload
                ),
            },
            "structural_stress_tests": {
                "used_for_posterior_weighting": False,
                "used_for_parameter_tuning": False,
                "hosing_0p2_40yr": forced_decline(config, 0.2),
                "hosing_0p1_recovery_100yr": hosing_recovery(config),
                "cross_resolution": cross_resolution(config),
                "interpretation": (
                    "Structural stress tests have no external pass/fail target in the "
                    "bundled benchmark set and are reported separately."
                ),
            },
        },
        "base_config": config_payload,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
    print(json.dumps(result, indent=2))
    print(f"\nWritten to {args.output.resolve()}")
    benchmark_passed = result["evidence_partition"]["tuning_informed_development_regressions"][
        "benchmark_results"
    ]["all_external_benchmarks_passed"]
    if args.fail_on_benchmark and not benchmark_passed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
