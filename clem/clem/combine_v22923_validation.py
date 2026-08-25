#!/usr/bin/env python3
"""Combine v2.29.23 5-degree and 10-degree release-validation outputs."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MODEL_VERSION = "2.29.23"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def resolution_payload(output_dir: Path, label: str) -> dict[str, Any]:
    sea_path = output_dir / f"SEA_ICE_VALIDATION_V2_29_23_{label}DEG.json"
    coupled_path = (
        output_dir / f"ARCTIC_GREENLAND_AMOC_VALIDATION_V2_29_23_{label}DEG.json"
    )
    sea = load_json(sea_path)
    coupled = load_json(coupled_path)
    if sea["model_version"] != MODEL_VERSION or coupled["model_version"] != MODEL_VERSION:
        raise SystemExit(f"Version mismatch in {label}-degree validation files")
    if sea["source_hashes"] != coupled["source_hashes"]:
        raise SystemExit(f"Source-hash mismatch in {label}-degree validation files")
    return {"sea_ice": sea, "coupled": coupled}


def gate_subset(gates: dict[str, bool], prefixes: tuple[str, ...]) -> bool:
    selected = [value for name, value in gates.items() if name.startswith(prefixes)]
    return bool(selected) and bool(all(selected))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("release_validation"))
    parser.add_argument(
        "--test-results",
        type=Path,
        default=None,
        help="Optional engineering-test JSON. Defaults to OUTPUT_DIR/TEST_RESULTS_V2_29_23.json, then the current directory.",
    )
    args = parser.parse_args()

    five = resolution_payload(args.output_dir, "5")
    ten = resolution_payload(args.output_dir, "10")
    payloads = {"5": five, "10": ten}

    source_hashes = five["sea_ice"]["source_hashes"]
    if ten["sea_ice"]["source_hashes"] != source_hashes:
        raise SystemExit("5-degree and 10-degree files were not generated from identical sources")

    resolution_summaries: list[dict[str, Any]] = []
    for label, item in payloads.items():
        sea_summary = item["sea_ice"]["summary"]
        coupled = item["coupled"]["coupled"]
        structural = item["coupled"]["structural_area_volume_experiments"]
        resolution_summaries.append(
            {
                "resolution_deg": float(label),
                "sea_ice": sea_summary,
                "structural_area_volume": {
                    "passed": structural["passed"],
                    "checks": structural["checks"],
                    "helper_level_outputs": structural["helper_level_outputs"],
                    "integrated_production_path": structural["integrated_production_path"],
                },
                "arctic_atmosphere_and_ocean": coupled[
                    "arctic_atmosphere_and_ocean"
                ],
                "greenland": coupled["greenland"],
                "amoc": coupled["amoc"],
                "coupled_gates": coupled["gates"],
                "all_resolution_science_gates_passed": bool(
                    sea_summary["all_release_gates_passed"]
                    and structural["passed"]
                    and coupled["passed"]
                ),
            }
        )

    five_coupled = five["coupled"]["coupled"]
    ten_coupled = ten["coupled"]["coupled"]
    five_arctic = five_coupled["arctic_atmosphere_and_ocean"]
    ten_arctic = ten_coupled["arctic_atmosphere_and_ocean"]
    five_amoc = five_coupled["amoc"]
    ten_amoc = ten_coupled["amoc"]

    differences = {
        "late_gmst_c": abs(
            five_arctic["late_gmst_near_surface_air_c"]
            - ten_arctic["late_gmst_near_surface_air_c"]
        ),
        "arctic_air_amplification": abs(
            five_arctic["arctic_near_surface_air_amplification"]
            - ten_arctic["arctic_near_surface_air_amplification"]
        ),
        "amoc_2100_sv": abs(five_amoc["amoc_2100_sv"] - ten_amoc["amoc_2100_sv"]),
        "late_march_area_million_km2": abs(
            five_arctic["late_march_area_million_km2"]
            - ten_arctic["late_march_area_million_km2"]
        ),
        "late_september_area_million_km2": abs(
            five_arctic["late_september_area_million_km2"]
            - ten_arctic["late_september_area_million_km2"]
        ),
    }
    cross_gates = {
        "gmst_difference_le_0p10c": differences["late_gmst_c"] <= 0.10,
        "arctic_air_amplification_difference_le_0p50": (
            differences["arctic_air_amplification"] <= 0.50
        ),
        "amoc_2100_difference_le_1sv": differences["amoc_2100_sv"] <= 1.0,
        "march_area_difference_le_0p30_mkm2": (
            differences["late_march_area_million_km2"] <= 0.30
        ),
        "september_area_difference_le_0p30_mkm2": (
            differences["late_september_area_million_km2"] <= 0.30
        ),
    }
    cross_resolution_passed = bool(all(cross_gates.values()))

    observation_files_verified = bool(
        all(
            item["sea_ice"]["summary"]["observation_files_verified"]
            for item in payloads.values()
        )
    )
    historical_calibration_passed = bool(
        all(
            item["sea_ice"]["summary"]["calibration_passed"]
            for item in payloads.values()
        )
    )
    recent_period_evaluation_passed = bool(
        all(
            item["sea_ice"]["summary"]["recent_period_evaluation_passed"]
            for item in payloads.values()
        )
    )
    positive_september_temporal_skill_passed = bool(
        all(
            item["sea_ice"]["summary"]["scientific_temporal_skill_gate_passed"]
            for item in payloads.values()
        )
    )
    extent_independently_validated = bool(
        all(
            item["sea_ice"]["evaluation"]["area_operator"].get(
                "extent_independent_validation_evidence", False
            )
            for item in payloads.values()
        )
    )
    structural_area_volume_passed = bool(
        all(
            item["coupled"]["structural_area_volume_experiments"]["passed"]
            for item in payloads.values()
        )
    )
    arctic_air_engineering_checks_passed = bool(
        all(
            gate_subset(
                item["coupled"]["coupled"]["gates"],
                (
                    "arctic_air_",
                    "maximum_arctic_air_",
                    "forcing_like_transport_",
                    "transport_power_",
                    "concentration_",
                    "local_ice_",
                    "lead_closure_",
                ),
            )
            for item in payloads.values()
        )
    )
    greenland_engineering_checks_passed = bool(
        all(
            gate_subset(
                item["coupled"]["coupled"]["gates"],
                ("greenland_",),
            )
            for item in payloads.values()
        )
    )
    arctic_ocean_sanity_checks_passed = bool(
        all(
            item["coupled"]["coupled"]["arctic_atmosphere_and_ocean"]
            ["open_water_benchmark"]["passed"]
            for item in payloads.values()
        )
    )
    greenland_posthoc_sanity_checks_passed = bool(
        all(
            item["coupled"]["coupled"]["greenland"]
            ["external_posthoc_benchmark"]["passed"]
            for item in payloads.values()
        )
    )
    amoc_validation_passed = bool(
        all(
            gate_subset(
                item["coupled"]["coupled"]["gates"],
                ("initial_amoc_", "amoc_", "salt_conservation_"),
            )
            for item in payloads.values()
        )
    )

    test_results_path = args.test_results
    if test_results_path is None:
        output_candidate = args.output_dir / "TEST_RESULTS_V2_29_23.json"
        cwd_candidate = Path("TEST_RESULTS_V2_29_23.json")
        test_results_path = output_candidate if output_candidate.exists() else cwd_candidate
    if test_results_path.exists():
        test_results = load_json(test_results_path)
        engineering_integrity_passed = bool(
            test_results.get("engineering_integrity_passed", False)
        )
    else:
        test_results = {
            "status": "not_provided",
            "engineering_integrity_passed": False,
        }
        engineering_integrity_passed = False

    scientific_release_passed = bool(
        observation_files_verified
        and engineering_integrity_passed
        and historical_calibration_passed
        and recent_period_evaluation_passed
        and cross_resolution_passed
        and structural_area_volume_passed
        and arctic_air_engineering_checks_passed
        and greenland_engineering_checks_passed
        and positive_september_temporal_skill_passed
        and extent_independently_validated
        and amoc_validation_passed
    )
    independent_prospective_validation_available = False
    scientific_release_passed = bool(
        scientific_release_passed and independent_prospective_validation_available
    )
    release_classification = "engineering_only"

    configuration_keys = (
        "arctic_winter_transport_enhancement",
        "arctic_greenland_marine_influence",
        "arctic_full_cover_equivalent_thickness_m",
        "arctic_new_ice_local_thickness_m",
        "arctic_ice_concentration_exponent",
        "arctic_ice_area_melt_thickness_m",
        "arctic_ice_area_compaction_years",
        "arctic_ice_area_formation_temperature_scale_c",
        "arctic_basal_ocean_exchange_wm2_k",
        "arctic_ice_surface_exchange_wm2_k",
        "arctic_transient_shortwave_scale",
        "greenland_dynamic_discharge_fraction",
        "greenland_seasonal_runoff_fraction",
        "amoc_collapse_threshold_sv",
    )
    five_configuration = five["sea_ice"]["configuration"]
    ten_configuration = ten["sea_ice"]["configuration"]
    common_configuration = {
        key: five_configuration[key] for key in configuration_keys
    }
    for key, value in common_configuration.items():
        if ten_configuration[key] != value:
            raise SystemExit(
                f"5-degree and 10-degree physical defaults differ for {key}: "
                f"{value!r} != {ten_configuration[key]!r}"
            )

    resolutions = {
        label: {
            "historical_calibration_passed": bool(
                item["sea_ice"]["summary"]["calibration_passed"]
            ),
            "recent_period_evaluation_passed": bool(
                item["sea_ice"]["summary"]["recent_period_evaluation_passed"]
            ),
            "structural_area_volume_validation_passed": bool(
                item["coupled"]["structural_area_volume_experiments"]["passed"]
            ),
            "coupled_validation_passed": bool(item["coupled"]["coupled"]["passed"]),
        }
        for label, item in payloads.items()
    }

    summary = {
        "schema_version": "3.0",
        "model_version": MODEL_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "validation_type": "version_matched_production_default",
        "source_hashes": source_hashes,
        "resolutions_deg": [5.0, 10.0],
        "common_configuration": common_configuration,
        "resolutions": resolutions,
        "resolution_summaries": resolution_summaries,
        "cross_resolution": {
            "differences": differences,
            "gates": cross_gates,
            "passed": cross_resolution_passed,
        },
        "observation_files_verified": observation_files_verified,
        "engineering_integrity_passed": engineering_integrity_passed,
        "historical_calibration_passed": historical_calibration_passed,
        "recent_period_evaluation_passed": recent_period_evaluation_passed,
        "cross_resolution_validation_passed": cross_resolution_passed,
        "structural_area_volume_validation_passed": structural_area_volume_passed,
        "arctic_air_engineering_checks_passed": arctic_air_engineering_checks_passed,
        "greenland_engineering_checks_passed": greenland_engineering_checks_passed,
        "arctic_ocean_tuning_informed_sanity_checks_passed": arctic_ocean_sanity_checks_passed,
        "greenland_external_posthoc_sanity_checks_passed": greenland_posthoc_sanity_checks_passed,
        "amoc_validation_passed": amoc_validation_passed,
        "positive_september_temporal_skill_passed": positive_september_temporal_skill_passed,
        "extent_independently_validated": extent_independently_validated,
        "independent_prospective_validation_available": independent_prospective_validation_available,
        "scientific_release_passed": scientific_release_passed,
        "release_classification": release_classification,
        "release_status": {
            "observation_files_verified": observation_files_verified,
            "engineering_integrity_passed": engineering_integrity_passed,
            "historical_calibration_passed": historical_calibration_passed,
            "recent_period_evaluation_passed": recent_period_evaluation_passed,
            "cross_resolution_validation_passed": cross_resolution_passed,
            "structural_area_volume_validation_passed": structural_area_volume_passed,
            "arctic_air_engineering_checks_passed": arctic_air_engineering_checks_passed,
            "greenland_engineering_checks_passed": greenland_engineering_checks_passed,
            "arctic_ocean_tuning_informed_sanity_checks_passed": arctic_ocean_sanity_checks_passed,
            "greenland_external_posthoc_sanity_checks_passed": greenland_posthoc_sanity_checks_passed,
            "amoc_validation_passed": amoc_validation_passed,
            "positive_september_temporal_skill_passed": positive_september_temporal_skill_passed,
            "extent_independently_validated": extent_independently_validated,
            "independent_prospective_validation_available": independent_prospective_validation_available,
            "scientific_release_passed": scientific_release_passed,
            "release_classification": release_classification,
        },
        "test_results": test_results,
        "recent_period_september_failure_is_release_blocking": True,
        "interpretation": (
            "Historical and 2021-2025 sea-ice records were inspected during model "
            "development. Passing these gates demonstrates calibration and "
            "development consistency, not independent predictive validation. "
            "Prospective untouched temporal evaluation begins in 2027."
        ),
    }
    output_path = args.output_dir / "VALIDATION_SUMMARY_V2_29_23.json"
    write_json(output_path, summary)
    print(json.dumps(summary["release_status"], indent=2, sort_keys=True))
    engineering_release_passed = bool(
        observation_files_verified
        and engineering_integrity_passed
        and historical_calibration_passed
        and recent_period_evaluation_passed
        and cross_resolution_passed
        and structural_area_volume_passed
        and arctic_air_engineering_checks_passed
        and greenland_engineering_checks_passed
        and amoc_validation_passed
    )
    if not engineering_release_passed:
        raise SystemExit("v2.29.23 engineering-release criteria are not all satisfied")


if __name__ == "__main__":
    main()
