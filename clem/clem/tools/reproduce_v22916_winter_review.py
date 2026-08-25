#!/usr/bin/env python3
"""Reproduce the v2.29.14 winter-sea-ice review probes on v2.29.16."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from climate_model import ModelConfig, ProcessClimateModel

OUTPUT = ROOT / "V2_29_16_REVIEW_REPRODUCTION.json"


def _max_active_error(left: np.ndarray, right: np.ndarray, active: np.ndarray) -> float:
    return float(np.max(np.abs(np.asarray(left)[active] - np.asarray(right)[active])))


def main() -> None:
    cfg = replace(
        ModelConfig(),
        start_year=1850.0,
        duration_years=251.0,
        dt_years=0.05,
        record_every_years=1.0,
        resolution_deg=10.0,
        scenario="ssp245",
        auto_initialize_from_1850=False,
    )
    model = ProcessClimateModel(cfg)
    result = model.run()
    reference = model._arctic_reference_state(cfg.duration_years)
    active = model.grid.lat >= cfg.arctic_module_full_latitude_deg

    sectors: dict[str, dict[str, float]] = {}
    definitions = (
        (
            "atlantic",
            model.state.arctic_atlantic_ice_energy_anomaly_wyr_m2,
            model.state.arctic_atlantic_open_water_heat_anomaly_wyr_m2,
            model.state.arctic_atlantic_air_anomaly_c,
            model.state.atlantic_sea_ice_fraction,
            result.atlantic_sea_ice_history[-1],
            result.arctic_atlantic_local_ice_thickness_history_m[-1],
            result.arctic_atlantic_open_water_temperature_history_c[-1],
        ),
        (
            "non_atlantic",
            model.state.arctic_non_atlantic_ice_energy_anomaly_wyr_m2,
            model.state.arctic_non_atlantic_open_water_heat_anomaly_wyr_m2,
            model.state.arctic_non_atlantic_air_anomaly_c,
            model.state.non_atlantic_sea_ice_fraction,
            result.non_atlantic_sea_ice_history[-1],
            result.arctic_non_atlantic_local_ice_thickness_history_m[-1],
            result.arctic_non_atlantic_open_water_temperature_history_c[-1],
        ),
    )
    for (
        prefix,
        ice_anomaly,
        open_anomaly,
        air_anomaly,
        state_concentration,
        saved_concentration,
        saved_local_thickness,
        saved_open_temperature,
    ) in definitions:
        total_ice = reference[f"{prefix}_ice_energy_wyr_m2"] + ice_anomaly
        total_open = reference[f"{prefix}_open_water_heat_wyr_m2"] + open_anomaly
        direct_concentration, equivalent, direct_local = model._arctic_ice_energy_to_state(
            total_ice,
            reference_ice_fraction=reference[f"{prefix}_ice_fraction"],
            lead_closure_weight=model._arctic_winter_lead_closure_weight(
                reference[f"{prefix}_air_temperature_c"],
                reference[f"{prefix}_air_temperature_c"] + air_anomaly,
            ),
        )
        direct_open = model._arctic_open_water_temperature(
            total_open, 1.0 - direct_concentration
        )
        sectors[prefix] = {
            "state_concentration_max_error": _max_active_error(
                state_concentration, direct_concentration, active
            ),
            "saved_concentration_max_error": _max_active_error(
                saved_concentration, direct_concentration, active
            ),
            "saved_local_thickness_max_error_m": _max_active_error(
                saved_local_thickness, direct_local, active
            ),
            "saved_open_water_temperature_max_error_c": _max_active_error(
                saved_open_temperature, direct_open, active
            ),
            "saved_volume_identity_max_error_m": _max_active_error(
                saved_concentration * saved_local_thickness, equivalent, active
            ),
        }

    equivalent_probe = np.array([0.0, 1.0e-12, 1.0e-9, 1.0e-6, 1.0e-4])
    concentration, diagnosed, local = model._arctic_ice_energy_to_state(
        -equivalent_probe * model.arctic_latent_energy_per_m_wyr_m2,
        reference_ice_fraction=np.full(equivalent_probe.shape, 0.99),
        lead_closure_weight=np.full(equivalent_probe.shape, 0.65),
    )
    upper_prior_concentration, upper_prior_diagnosed, upper_prior_local = (
        model._arctic_ice_energy_to_state(
            -equivalent_probe * model.arctic_latent_energy_per_m_wyr_m2,
            reference_ice_fraction=np.full(equivalent_probe.shape, 0.99),
            lead_closure_weight=np.full(equivalent_probe.shape, 0.90),
        )
    )
    payload = {
        "model_version": "2.29.16",
        "run": {
            "scenario": cfg.scenario,
            "start_year": cfg.start_year,
            "end_year": cfg.start_year + cfg.duration_years,
            "resolution_deg": cfg.resolution_deg,
            "dt_years": cfg.dt_years,
            "fully_active_arctic_latitude_deg": cfg.arctic_module_full_latitude_deg,
        },
        "saved_state_reproduction": sectors,
        "near_zero_volume_reproduction": {
            "equivalent_thickness_m": equivalent_probe.tolist(),
            "diagnosed_equivalent_thickness_m": diagnosed.tolist(),
            "concentration": concentration.tolist(),
            "local_thickness_m": local.tolist(),
            "maximum_volume_identity_error_m": float(
                np.max(np.abs(concentration * local - diagnosed))
            ),
            "concentration_at_1e_9_m": float(concentration[2]),
            "upper_prior_concentration_at_1e_9_m": float(
                upper_prior_concentration[2]
            ),
            "concentration_at_zero_m": float(concentration[0]),
            "upper_prior_maximum_volume_identity_error_m": float(
                np.max(
                    np.abs(
                        upper_prior_concentration * upper_prior_local
                        - upper_prior_diagnosed
                    )
                )
            ),
        },
        "transient_temperature_gate": {
            "reference_air_temperature_c": -17.0,
            "cold_actual_air_temperature_c": -17.0,
            "warm_actual_air_temperature_c": 0.0,
            "cold_weight": float(
                model._arctic_winter_lead_closure_weight(
                    np.array([-17.0]), np.array([-17.0])
                )[0]
            ),
            "warm_weight": float(
                model._arctic_winter_lead_closure_weight(
                    np.array([-17.0]), np.array([0.0])
                )[0]
            ),
        },
    }
    OUTPUT.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(OUTPUT)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
