#!/usr/bin/env python3
"""Generate synchronized v2.27.0 development and structural validation records."""
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
    MODEL_VERSION,
    ModelConfig,
    ProcessClimateModel,
    SV_TO_GT_PER_YEAR,
)
from held_out_amoc_validation import (
    annual_mean_frame,
    cross_resolution,
    historical_external_metrics,
    hosing_recovery,
    window_mean,
)

ROOT = Path(__file__).resolve().parent
BENCHMARK_PATH = ROOT / "held_out_amoc_benchmarks.json"


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
    return cfg, ProcessClimateModel(cfg).run().dataframe


def amoc_decline(annual) -> float:
    baseline = window_mean(annual, "amoc_sv", 1995.0, 2014.0)
    endpoint = window_mean(annual, "amoc_sv", 2081.0, 2100.0)
    return 100.0 * (1.0 - endpoint / baseline)


def control_check() -> dict[str, float]:
    cfg = replace(
        ModelConfig(),
        scenario="constant",
        duration_years=500.0,
        record_every_years=100.0,
        auto_initialize_from_1850=False,
    )
    model = ProcessClimateModel(cfg)
    initial = model.record(0.0)
    final = model.run().dataframe.iloc[-1]
    return {
        "years": 500.0,
        "initial_gmst_c": float(initial["global_surface_warming_c"]),
        "final_gmst_c": float(final["global_surface_warming_c"]),
        "gmst_drift_c": float(final["global_surface_warming_c"] - initial["global_surface_warming_c"]),
        "initial_amoc_sv": float(initial["amoc_sv"]),
        "final_amoc_sv": float(final["amoc_sv"]),
        "amoc_drift_sv": float(final["amoc_sv"] - initial["amoc_sv"]),
        "final_toa_imbalance_wm2": float(final["toa_imbalance_wm2"]),
        "final_salt_conservation_error_ppm": float(final["salt_conservation_error_ppm"]),
        "final_total_resolved_heat_content_anomaly_zj": float(final["total_resolved_heat_content_anomaly_zj"]),
    }


def perturbation_check(sign: float) -> dict[str, float]:
    cfg = replace(ModelConfig(), scenario="constant", duration_years=1.0, auto_initialize_from_1850=False)
    model = ProcessClimateModel(cfg)
    mask = model.arctic_module_blend
    model.state.arctic_atlantic_air_anomaly_c += sign * 0.5 * mask
    model.state.arctic_non_atlantic_air_anomaly_c += sign * 0.5 * mask
    model.state.arctic_atlantic_ice_energy_anomaly_wyr_m2 += sign * 0.25 * mask
    model.state.arctic_non_atlantic_ice_energy_anomaly_wyr_m2 += sign * 0.25 * mask
    elapsed = 0.0
    while elapsed < 160.0 - 1.0e-12:
        step = min(cfg.dt_years, 160.0 - elapsed)
        model.step(elapsed, step)
        elapsed += step
    row = model.record(elapsed)
    return {
        "sign": sign,
        "years": elapsed,
        "final_arctic_air_c": float(row["arctic_warming_c"]),
        "final_amoc_sv": float(row["amoc_sv"]),
        "final_salt_conservation_error_ppm": float(row["salt_conservation_error_ppm"]),
    }


def timestep_metrics(dt: float) -> dict[str, float]:
    _, frame = scenario_run("ssp245", dt, record_every=1.0)
    return {"dt_years": dt, **historical_external_metrics(annual_mean_frame(frame))}


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


def _summary_ssp245_task() -> dict[str, Any]:
    cfg, raw = scenario_run("ssp245", dt=0.05, record_every=0.05)
    annual = annual_mean_frame(raw)
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
        },
        "metrics": metrics,
        "seasonal": seasonal,
        "greenland": greenland,
    }


def _summary_ssp585_task() -> dict[str, float]:
    _, raw = scenario_run("ssp585", dt=0.05, record_every=1.0)
    return {"ssp585_amoc_decline_2100_percent": amoc_decline(annual_mean_frame(raw))}


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
        "periodic_closure_wyr_m2": float(
            model.arctic_reference_periodic_closure_wyr_m2
        ),
        "spinup_convergence_wyr_m2": float(
            model.arctic_reference_spinup_convergence_wyr_m2
        ),
        "spinup_years_completed": int(model.arctic_reference_spinup_years_completed),
    }
    weights = model.grid.band_area_weights[mask] * model.grid.ocean_fraction[mask]
    monthly_ice: list[float] = []
    monthly_interface: list[float] = []
    for month in range(1, 13):
        state = model._arctic_reference_state((month - 0.5) / 12.0)
        monthly_ice.append(
            float(np.average(state["ice_fraction"][mask], weights=weights))
        )
        monthly_interface.append(
            float(
                np.average(state["interface_temperature_c"][mask], weights=weights)
            )
        )
    result["monthly_ocean_area_weighted_ice_fraction"] = monthly_ice
    result["monthly_ocean_area_weighted_interface_temperature_c"] = monthly_interface
    result["minimum_ice_month"] = int(np.argmin(monthly_ice)) + 1
    return result


def _cross_resolution_task(resolution: float) -> dict[str, float]:
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
    control = control_model.run().dataframe.iloc[-1]
    forced = ProcessClimateModel(
        replace(control_config, scenario="step_2x")
    ).run().dataframe.iloc[-1]
    return {
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


def _run_named_task(name: str) -> Any:
    if name == "summary_ssp245":
        return _summary_ssp245_task()
    if name == "summary_ssp585":
        return _summary_ssp585_task()
    if name == "arctic_reference":
        return _arctic_reference_task()
    if name == "control":
        return control_check()
    if name == "perturbation_cold":
        return perturbation_check(-1.0)
    if name == "perturbation_warm":
        return perturbation_check(1.0)
    if name == "hosing_recovery":
        return hosing_recovery(ModelConfig())
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
    ssp245 = tasks["summary_ssp245"]
    benchmark_doc = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
    benchmark_results = evaluate_benchmarks(ssp245["metrics"], benchmark_doc)
    cfg = ssp245["config"]
    summary = {
        "model_version": MODEL_VERSION,
        "classification": (
            "tuning-informed development regression checks; not independent validation"
        ),
        "default_freshwater_coefficients_sv_per_k": {
            "hydrological": cfg["hydrological_freshwater_sv_per_k"],
            "greenland_public_coefficient": cfg["greenland_freshwater_sv_per_k"],
        },
        "structural_defaults": {
            key: cfg[key]
            for key in (
                "greenland_dynamic_discharge_fraction",
                "greenland_pdd_melt_factor_gt_per_degree_day",
                "greenland_max_freshwater_sv",
                "amoc_temperature_density_coupling",
                "amoc_convection_density_scale_factor",
                "amoc_reference_density_driver",
            )
        },
        "development_metrics": ssp245["metrics"],
        "benchmark_results": benchmark_results,
        "all_development_checks_passed": all(
            item["passed"] for item in benchmark_results.values()
        ),
        "seasonal_arctic_amplification_1979_2021": ssp245["seasonal"],
        "ssp585_amoc_decline_2100_percent": tasks["summary_ssp585"][
            "ssp585_amoc_decline_2100_percent"
        ],
        "greenland_ssp245": ssp245["greenland"],
        "arctic_reference_cycle": tasks["arctic_reference"],
        "provenance": {
            "benchmark_file": BENCHMARK_PATH.name,
            "benchmark_file_sha256": sha256_file(BENCHMARK_PATH),
            "benchmark_set_version": benchmark_doc["benchmark_set_version"],
            "processing_script": Path(__file__).name,
            "processing_script_sha256": sha256_file(Path(__file__)),
            "climate_model_sha256": sha256_file(ROOT / "climate_model.py"),
        },
    }
    write_json("VALIDATION_SUMMARY_V2_27_0.json", summary)

    timestep = [
        tasks["timestep_0p1"],
        tasks["timestep_0p05"],
        tasks["timestep_0p025"],
    ]
    reference = timestep[1]
    deep = {
        "model_version": MODEL_VERSION,
        "provenance": {
            "processing_script": Path(__file__).name,
            "processing_script_sha256": sha256_file(Path(__file__)),
            "climate_model_sha256": sha256_file(ROOT / "climate_model.py"),
        },
        "control": tasks["control"],
        "arctic_perturbations": [
            tasks["perturbation_cold"],
            tasks["perturbation_warm"],
        ],
        "hosing_recovery": tasks["hosing_recovery"],
        "cross_resolution": [
            tasks["resolution_2p5"],
            tasks["resolution_5p0"],
            tasks["resolution_10p0"],
        ],
        "timestep_metrics": timestep,
        "timestep_differences_from_0p05": {
            str(item["dt_years"]): {
                key: float(item[key] - reference[key])
                for key in reference
                if key != "dt_years"
            }
            for item in timestep
            if item["dt_years"] != 0.05
        },
    }
    write_json("DEEP_VALIDATION_V2_27_0.json", deep)

    audit = {
        "model_version": MODEL_VERSION,
        "source_files": {
            name: sha256_file(ROOT / name)
            for name in (
                "climate_model.py",
                "app.py",
                "climate_model_gui.py",
                "monte_carlo.py",
                "setting_metadata.py",
                "pyproject.toml",
                "requirements.lock",
                "requirements-dev.lock",
                "dependency_integrity.lock.json",
            )
        },
        "implemented_structural_changes": {
            "separate_land_and_ocean_baseline_climatologies": True,
            "arctic_ocean_freezing_bounded_north_of_66n": True,
            "periodic_zero_layer_reference_cycle": True,
            "annual_mean_shortwave_subtraction_removed": True,
            "inherited_annual_mean_ice_mass_removed": True,
            "conductive_ice_and_snow_flux": True,
            "basal_ocean_heat_flux": True,
            "open_water_mixed_layer_reservoir": True,
            "snow_bare_ice_and_melt_pond_albedo": True,
            "reduced_greenland_surface_mass_balance": True,
            "separate_greenland_dynamic_discharge": True,
            "bounded_greenland_combined_diagnostics": True,
            "legacy_combined_freshwater_override_disables_new_smb": True,
            "isolated_test_runner": True,
            "isolated_validation_runner": True,
        },
        "known_scope_limits": [
            "Sea-ice dynamics and mechanical export are not represented.",
            "Greenland firn hydrology, outlet-glacier dynamics, and regional geometry are reduced to emulator terms.",
            "Development benchmark ranges were used during tuning and are not independent validation.",
        ],
        "configuration_snapshot": asdict(ModelConfig()),
    }
    write_json("IMPLEMENTATION_AUDIT_V2_27_0.json", audit)
    print(
        json.dumps(
            {
                "development_metrics": summary["development_metrics"],
                "seasonal_arctic": summary[
                    "seasonal_arctic_amplification_1979_2021"
                ],
                "ssp585_amoc_decline_2100_percent": summary[
                    "ssp585_amoc_decline_2100_percent"
                ],
                "greenland_ssp245": summary["greenland_ssp245"],
                "control": deep["control"],
                "hosing_recovery": deep["hosing_recovery"],
            },
            indent=2,
        ),
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task")
    parser.add_argument("--task-output", type=Path)
    args = parser.parse_args()
    if args.task:
        if args.task_output is None:
            raise SystemExit("--task-output is required with --task")
        value = _run_named_task(args.task)
        args.task_output.write_text(
            json.dumps(value, indent=2) + "\n", encoding="utf-8"
        )
        print(f"Completed validation task: {args.task}", flush=True)
        os._exit(0)

    task_names = [
        "summary_ssp245",
        "summary_ssp585",
        "arctic_reference",
        "timestep_0p1",
        "timestep_0p05",
        "timestep_0p025",
        "control",
        "perturbation_cold",
        "perturbation_warm",
        "hosing_recovery",
        "resolution_2p5",
        "resolution_5p0",
        "resolution_10p0",
    ]
    with tempfile.TemporaryDirectory(prefix="validation_v227_") as directory:
        root = Path(directory)
        tasks = {name: _run_task_subprocess(name, root) for name in task_names}
    _assemble_records(tasks)


if __name__ == "__main__":
    main()
