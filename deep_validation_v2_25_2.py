#!/usr/bin/env python3
"""Generate deep stability and convergence checks for v2.25.2."""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from climate_model import MODEL_VERSION, ModelConfig, ProcessClimateModel
from held_out_amoc_validation import annual_mean_frame, historical_external_metrics, hosing_recovery


def control_check() -> dict[str, float]:
    cfg = replace(ModelConfig(), scenario="constant", duration_years=500.0,
                  record_every_years=100.0, auto_initialize_from_1850=False)
    frame = ProcessClimateModel(cfg).run().dataframe
    final = frame.iloc[-1]
    return {
        "years": 500.0,
        "final_gmst_c": float(final["global_surface_warming_c"]),
        "final_arctic_air_c": float(final["arctic_warming_c"]),
        "final_amoc_sv": float(final["amoc_sv"]),
        "final_toa_imbalance_wm2": float(final["toa_imbalance_wm2"]),
        "final_salt_conservation_error_ppm": float(final["salt_conservation_error_ppm"]),
        "final_total_resolved_heat_content_anomaly_zj": float(final["total_resolved_heat_content_anomaly_zj"]),
    }


def perturbation_check(sign: float) -> dict[str, float]:
    cfg = replace(ModelConfig(), scenario="constant", duration_years=1.0,
                  auto_initialize_from_1850=False)
    model = ProcessClimateModel(cfg)
    mask = model.arctic_module_blend
    model.state.arctic_atlantic_air_anomaly_c += sign * 0.5 * mask
    model.state.arctic_non_atlantic_air_anomaly_c += sign * 0.5 * mask
    model.state.arctic_atlantic_ice_energy_anomaly_wyr_m2 += sign * 0.25 * mask
    model.state.arctic_non_atlantic_ice_energy_anomaly_wyr_m2 += sign * 0.25 * mask
    elapsed = 0.0
    while elapsed < 160.0 - 1.0e-12:
        dt = min(cfg.dt_years, 160.0 - elapsed)
        model.step(elapsed, dt)
        elapsed += dt
    row = model.record(elapsed)
    return {
        "sign": sign,
        "years": elapsed,
        "final_arctic_air_c": float(row["arctic_warming_c"]),
        "final_amoc_sv": float(row["amoc_sv"]),
        "final_salt_conservation_error_ppm": float(row["salt_conservation_error_ppm"]),
    }


def timestep_metrics(dt: float) -> dict[str, float]:
    base = ModelConfig()
    cfg = replace(base, start_year=1850.0, duration_years=251.0,
                  scenario="ssp245", dt_years=dt, record_every_years=dt,
                  auto_initialize_from_1850=False)
    annual = annual_mean_frame(ProcessClimateModel(cfg).run().dataframe)
    return {"dt_years": dt, **historical_external_metrics(annual)}


def main() -> None:
    checks = {
        "model_version": MODEL_VERSION,
        "default_freshwater_coefficients_sv_per_k": {
            "hydrological": ModelConfig().hydrological_freshwater_sv_per_k,
            "greenland": ModelConfig().greenland_freshwater_sv_per_k,
        },
        "control": control_check(),
        "arctic_perturbations": [perturbation_check(-1.0), perturbation_check(1.0)],
        "hosing_recovery": hosing_recovery(ModelConfig()),
        "timestep_metrics": [timestep_metrics(0.10), timestep_metrics(0.05), timestep_metrics(0.025)],
    }
    reference = checks["timestep_metrics"][1]
    checks["timestep_differences_from_0p05"] = {
        str(item["dt_years"]): {
            key: float(item[key] - reference[key])
            for key in reference
            if key != "dt_years"
        }
        for item in checks["timestep_metrics"]
        if item["dt_years"] != 0.05
    }
    Path("DEEP_VALIDATION_V2_25_2.json").write_text(json.dumps(checks, indent=2) + "\n")
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    main()
