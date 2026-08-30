#!/usr/bin/env python3
"""Reproduce the version-matched v2.29.18 historical sea-ice calibration."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path

from climate_model import MODEL_VERSION, ModelConfig, ProcessClimateModel
from sea_ice_validation import evaluate_result
from validation_segmentation import run_segmented


def run_validation(resolution_deg: float, generated_at: str) -> dict:
    """Run the default SSP2-4.5 historical calibration at one resolution."""

    ProcessClimateModel.clear_arctic_reference_cycle_cache()
    config = replace(
        ModelConfig(),
        start_year=1850.0,
        duration_years=177.0,
        scenario="ssp245",
        dt_years=0.05,
        record_every_years=0.05,
        resolution_deg=float(resolution_deg),
        auto_initialize_from_1850=False,
    )
    result = run_segmented(config, segment_years=40.0)
    evaluation = evaluate_result(result)
    return {
        "schema_version": "1.0",
        "model_version": MODEL_VERSION,
        "generated_at": generated_at,
        "evidence_role": (
            "tuning-informed historical calibration; not independent predictive "
            "validation"
        ),
        "run": {
            "scenario": "ssp245",
            "start_year": 1850.0,
            "duration_years": 177.0,
            "end_year": 2027.0,
            "dt_years": 0.05,
            "record_every_years": 0.05,
            "resolution_deg": float(resolution_deg),
        },
        "configuration": asdict(config),
        "evaluation": evaluation,
        "mandatory_calibration_passed": bool(evaluation["calibration_passed"]),
        "strict_development_evaluation_passed": bool(
            evaluation["validation_informed_development_evaluation_passed"]
        ),
    }


def compact_summary(payload: dict) -> dict:
    evaluation = payload["evaluation"]
    calibration = evaluation["calibration"]
    march = calibration["months"]["3"]
    september = calibration["months"]["9"]
    return {
        "mandatory_calibration_passed": payload["mandatory_calibration_passed"],
        "strict_development_evaluation_passed": payload[
            "strict_development_evaluation_passed"
        ],
        "failed_mandatory_gates": [
            name for name, passed in evaluation["calibration_gates"].items() if not passed
        ],
        "march_area_mean_million_km2": march["area"][
            "model_mean_million_km2"
        ],
        "march_area_rmse_million_km2": march["area"]["rmse_million_km2"],
        "march_extent_mean_million_km2": march["extent"][
            "model_mean_million_km2"
        ],
        "march_extent_rmse_million_km2": march["extent"]["rmse_million_km2"],
        "march_extent_trend_million_km2_per_decade": march["extent"][
            "model_trend_million_km2_per_decade"
        ],
        "march_extent_trend_observed_million_km2_per_decade": march["extent"][
            "observed_trend_million_km2_per_decade"
        ],
        "march_extent_robust_trend_passed": evaluation[
            "march_extent_trend_robustness"
        ]["passed"],
        "september_area_mean_million_km2": september["area"][
            "model_mean_million_km2"
        ],
        "september_area_rmse_million_km2": september["area"][
            "rmse_million_km2"
        ],
        "september_area_trend_million_km2_per_decade": september["area"][
            "model_trend_million_km2_per_decade"
        ],
        "september_area_trend_observed_million_km2_per_decade": september[
            "area"
        ]["observed_trend_million_km2_per_decade"],
        "september_extent_rmse_million_km2": september["extent"][
            "rmse_million_km2"
        ],
        "seasonal_area_amplitude_million_km2": calibration[
            "model_march_minus_september_area_million_km2"
        ],
        "seasonal_area_amplitude_observed_million_km2": calibration[
            "observed_march_minus_september_area_million_km2"
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--resolutions",
        default="5,10",
        help="Comma-separated latitude resolutions, default: 5,10.",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("."))
    args = parser.parse_args()
    resolutions = [
        float(item.strip()) for item in args.resolutions.split(",") if item.strip()
    ]
    if not resolutions:
        raise SystemExit("At least one resolution is required.")
    if MODEL_VERSION != "2.29.18":
        raise SystemExit(f"Expected model version 2.29.18, found {MODEL_VERSION}.")

    generated_at = datetime.now(timezone.utc).isoformat()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    default = ModelConfig()
    summary = {
        "schema_version": "1.0",
        "model_version": MODEL_VERSION,
        "generated_at": generated_at,
        "classification": (
            "tuning-informed historical calibration evidence; not independent "
            "predictive validation"
        ),
        "common_calibration": {
            "arctic_full_cover_equivalent_thickness_m": (
                default.arctic_full_cover_equivalent_thickness_m
            ),
            "arctic_new_ice_local_thickness_m": (
                default.arctic_new_ice_local_thickness_m
            ),
            "arctic_ice_concentration_exponent": (
                default.arctic_ice_concentration_exponent
            ),
            "arctic_winter_transport_enhancement": (
                default.arctic_winter_transport_enhancement
            ),
            "arctic_winter_transport_temperature_scale_c": (
                default.arctic_winter_transport_temperature_scale_c
            ),
            "arctic_ice_surface_exchange_wm2_k": (
                default.arctic_ice_surface_exchange_wm2_k
            ),
            "arctic_transient_shortwave_scale": (
                default.arctic_transient_shortwave_scale
            ),
            "arctic_interface_longwave_damping_wm2_k": (
                default.arctic_interface_longwave_damping_wm2_k
            ),
            "arctic_winter_lead_closure_fraction": (
                default.arctic_winter_lead_closure_fraction
            ),
        },
        "resolutions": {},
        "all_mandatory_calibration_gates_passed": True,
    }

    for resolution in resolutions:
        payload = run_validation(resolution, generated_at)
        label = f"{resolution:g}"
        filename = (
            args.output_dir / f"SEA_ICE_VALIDATION_V2_29_18_{label}DEG.json"
        )
        filename.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        summary["resolutions"][label] = compact_summary(payload)
        summary["all_mandatory_calibration_gates_passed"] = bool(
            summary["all_mandatory_calibration_gates_passed"]
            and payload["mandatory_calibration_passed"]
        )
        print(
            f"{label} degree: mandatory calibration "
            f"{'PASS' if payload['mandatory_calibration_passed'] else 'FAIL'}"
        )

    summary_path = args.output_dir / "VALIDATION_SUMMARY_V2_29_18.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if not summary["all_mandatory_calibration_gates_passed"]:
        raise SystemExit("One or more mandatory calibration suites failed.")


if __name__ == "__main__":
    main()
