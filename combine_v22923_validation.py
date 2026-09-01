#!/usr/bin/env python3
"""Combine v2.29.23 5-degree and 10-degree release-validation outputs."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from prospective_validation_r16 import evaluate as evaluate_r16_prospective

MODEL_VERSION = "2.29.23"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def resolution_payload(
    output_dir: Path,
    label: str,
    *,
    model_version: str = MODEL_VERSION,
    artifact_tag: str = "V2_29_23",
) -> dict[str, Any]:
    sea_path = output_dir / f"SEA_ICE_VALIDATION_{artifact_tag}_{label}DEG.json"
    coupled_path = (
        output_dir / f"ARCTIC_GREENLAND_AMOC_VALIDATION_{artifact_tag}_{label}DEG.json"
    )
    sea = load_json(sea_path)
    coupled = load_json(coupled_path)
    if sea.get("model_version") != model_version or coupled.get("model_version") != model_version:
        raise SystemExit(f"Version mismatch in {label}-degree validation files")
    if (
        sea.get("validation_type") != "version_matched_production_default"
        or coupled.get("validation_type") != "version_matched_production_default"
    ):
        raise SystemExit(f"Validation-type mismatch in {label}-degree validation files")
    if sea.get("source_hashes") != coupled.get("source_hashes"):
        raise SystemExit(f"Source-hash mismatch in {label}-degree validation files")
    if not bool(sea.get("validation_passed", False)):
        raise SystemExit(f"Sea-ice validation failed at {label} degrees")
    if not bool(coupled.get("validation_passed", False)):
        raise SystemExit(f"Coupled validation failed at {label} degrees")
    if not bool(coupled.get("coupled", {}).get("passed", False)):
        raise SystemExit(f"Coupled science gates failed at {label} degrees")
    if not bool(coupled.get("structural_area_volume_experiments", {}).get("passed", False)):
        raise SystemExit(f"Structural area/volume gates failed at {label} degrees")
    return {"sea_ice": sea, "coupled": coupled}


def gate_subset(gates: dict[str, bool], prefixes: tuple[str, ...]) -> bool:
    selected = [value for name, value in gates.items() if name.startswith(prefixes)]
    return bool(selected) and bool(all(selected))


def combine_validation(
    *,
    model_version: str = MODEL_VERSION,
    artifact_tag: str = "V2_29_23",
) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("release_validation"))
    parser.add_argument(
        "--test-results",
        type=Path,
        default=None,
        help=f"Optional engineering-test JSON. Defaults to OUTPUT_DIR/TEST_RESULTS_{artifact_tag}.json, then the current directory.",
    )
    args = parser.parse_args()

    five = resolution_payload(
        args.output_dir, "5", model_version=model_version, artifact_tag=artifact_tag
    )
    ten = resolution_payload(
        args.output_dir, "10", model_version=model_version, artifact_tag=artifact_tag
    )
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
        output_candidate = args.output_dir / f"TEST_RESULTS_{artifact_tag}.json"
        cwd_candidate = Path(f"TEST_RESULTS_{artifact_tag}.json")
        test_results_path = output_candidate if output_candidate.exists() else cwd_candidate
    if test_results_path.exists():
        test_results = load_json(test_results_path)
        engineering_integrity_passed = bool(
            test_results.get(
                "engineering_integrity_passed",
                int(test_results.get("passed", 0)) > 0
                and int(test_results.get("failed", 0)) == 0
                and int(test_results.get("errors", 0)) == 0,
            )
        )
    else:
        test_results = {
            "status": "not_provided",
            "engineering_integrity_passed": False,
        }
        engineering_integrity_passed = False

    # Current engineering/physics prerequisites intentionally exclude two
    # historical diagnostics that the sea-ice validator already declares
    # non-release-blocking: coarse two-sector spatial extent and retrospective
    # temporal skill scores. Neither can substitute for untouched prospective
    # predictive evidence.
    current_validation_prerequisites_passed = bool(
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
    prospective_evidence_path = Path(__file__).resolve().parent / "validation" / "prospective" / "R16_PROSPECTIVE_EVIDENCE.json"
    prospective = evaluate_r16_prospective(
        prospective_evidence_path if prospective_evidence_path.exists() else None
    )
    independent_predictive_scientific_validation_status = str(
        prospective.get("independent_predictive_scientific_validation_status", "not_available")
    )
    independent_predictive_scientific_validation_complete = bool(
        prospective.get("independent_predictive_scientific_validation_complete", False)
    )
    independent_predictive_scientific_validation_passed = bool(
        prospective.get(
            "independent_predictive_scientific_validation_passed",
            independent_predictive_scientific_validation_complete
            and independent_predictive_scientific_validation_status == "passed",
        )
    )
    independent_prospective_validation_available = bool(
        independent_predictive_scientific_validation_status != "not_available"
    )
    # Backwards-compatible alias. A scientific release requires both the current
    # engineering/physics prerequisites and a *passed* frozen prospective test.
    # A completed-but-failed prospective evaluation must never turn this true.
    scientific_release_passed = bool(
        current_validation_prerequisites_passed
        and independent_predictive_scientific_validation_passed
    )
    release_classification = (
        "scientifically_validated"
        if scientific_release_passed
        else (
            "engineering_release_independent_predictive_validation_failed"
            if independent_predictive_scientific_validation_status == "failed"
            else "engineering_release_independent_predictive_validation_not_available"
        )
    )

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
        "model_version": model_version,
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
        "retrospective_temporal_skill_is_release_blocking": False,
        "extent_metrics_are_release_blocking": False,
        "current_validation_prerequisites_passed": current_validation_prerequisites_passed,
        "independent_prospective_validation_available": independent_prospective_validation_available,
        "independent_predictive_scientific_validation_status": independent_predictive_scientific_validation_status,
        "independent_predictive_scientific_validation_complete": independent_predictive_scientific_validation_complete,
        "independent_predictive_scientific_validation_passed": independent_predictive_scientific_validation_passed,
        "prospective_validation_evidence": prospective,
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
            "retrospective_temporal_skill_is_release_blocking": False,
            "extent_metrics_are_release_blocking": False,
            "current_validation_prerequisites_passed": current_validation_prerequisites_passed,
            "independent_prospective_validation_available": independent_prospective_validation_available,
            "independent_predictive_scientific_validation_status": independent_predictive_scientific_validation_status,
            "independent_predictive_scientific_validation_complete": independent_predictive_scientific_validation_complete,
            "independent_predictive_scientific_validation_passed": independent_predictive_scientific_validation_passed,
            "scientific_release_passed": scientific_release_passed,
            "release_classification": release_classification,
        },
        "test_results": test_results,
        "recent_period_september_failure_is_release_blocking": False,
        "interpretation": (
            "Historical and 2021-2025 sea-ice records were inspected during model "
            "development. Retrospective temporal scores and coarse two-sector extent "
            "are diagnostics and are not release-blocking physical predictions. "
            "Current engineering/physics prerequisites can pass while independent "
            "predictive scientific validation remains not_available until sufficient "
            "untouched prospective observations exist."
        ),
    }
    engineering_release_passed = current_validation_prerequisites_passed
    summary["coupled_validation_complete"] = engineering_release_passed
    summary["version_matched_arctic_greenland_amoc_validation_complete"] = bool(
        engineering_release_passed
        and all(
            item["coupled"]["validation_passed"]
            and item["coupled"]["coupled"]["passed"]
            for item in payloads.values()
        )
    )
    output_path = args.output_dir / f"VALIDATION_SUMMARY_{artifact_tag}.json"
    print(json.dumps(summary["release_status"], indent=2, sort_keys=True))
    if not engineering_release_passed:
        failed_path = args.output_dir / f"FAILED_VALIDATION_SUMMARY_{artifact_tag}.json"
        write_json(failed_path, summary)
        raise SystemExit(
            f"{model_version} engineering-release criteria are not all satisfied"
        )
    write_json(output_path, summary)


def main() -> None:
    combine_validation()


if __name__ == "__main__":
    main()
