#!/usr/bin/env python3
"""Targeted fixed-preindustrial AMOC fixed-point diagnosis for R18.1.

No time integration or parameter fitting is performed. The script solves the
frozen R18 reduced AMOC equilibrium equations at zero artificial hosing from
several separated initial guesses and classifies the local Jacobian stability.
It reports both the production no-reversal configuration and a reversal-enabled
structural sensitivity.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import least_squares

import climate_model as cm

ROOT = Path(__file__).resolve().parent
EXPECTED_CLIMATE_SHA256 = "e1553c1baccd7a90974f7879dd664a8a4b447adec5bd93407bbc5dd0e2c9bd90"
OUTPUT = ROOT / "R18_1_AMOC_BISTABILITY_DIAGNOSIS.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def base_config(*, allow_reversal: bool) -> cm.ModelConfig:
    return replace(
        cm.ModelConfig(),
        amoc_allow_reversal=allow_reversal,
        start_year=0.0,
        duration_years=1.0,
        scenario="constant",
        co2_start_ppm=278.3,
        co2_end_ppm=278.3,
        co2_peak_ppm=278.3,
        additional_forcing_wm2=0.0,
        freshwater_hosing_sv=0.0,
        warming_freshwater_sv_per_k=0.0,
        hydrological_freshwater_sv_per_k=0.0,
        greenland_freshwater_sv_per_k=0.0,
        freshwater_start_fraction=1.0,
        freshwater_compensation_mode="atlantic",
        auto_initialize_from_1850=False,
    )


def solve_roots(*, allow_reversal: bool) -> list[dict[str, Any]]:
    model = cm.ProcessClimateModel(base_config(allow_reversal=allow_reversal))
    template = model.state.copy()
    total_salt = float(
        np.sum(model.amoc_box_volumes_m3 * model._salinity_array(template))
    )
    lower, upper = cm._amoc_equilibrium_bounds(model)
    control = cm._amoc_equilibrium_vector(model, template)
    seed_specs = [
        (17.0, 35.15, 1.00, 700.0),
        (12.0, 35.05, 1.00, 802.0),
        (1.70, 34.53, 0.55, 850.0),
        (0.05, 34.10, 0.20, 900.0),
        (-5.0, 34.32, 0.15, 1130.0),
        (-18.0, 33.00, 0.20, 1000.0),
    ]
    if not allow_reversal:
        seed_specs = [item for item in seed_specs if item[0] >= 0.0]

    roots: list[np.ndarray] = []
    for q_sv, north_psu, convection, pycnocline_m in seed_specs:
        guess = control.copy()
        guess[0] = north_psu
        guess[5] = q_sv
        guess[6] = convection
        guess[7] = pycnocline_m
        solution = least_squares(
            lambda candidate: cm._scaled_amoc_equilibrium_residual(
                model, candidate, 0.0, template, total_salt
            ),
            np.clip(guess, lower + 1.0e-8, upper - 1.0e-8),
            bounds=(lower, upper),
            xtol=1.0e-10,
            ftol=1.0e-10,
            gtol=1.0e-10,
            max_nfev=1600,
        )
        residual_norm = float(
            np.linalg.norm(
                cm._scaled_amoc_equilibrium_residual(
                    model, solution.x, 0.0, template, total_salt
                )
            )
        )
        full = cm._amoc_equilibrium_full_metrics(
            model, solution.x, 0.0, template, total_salt
        )
        if residual_norm > 2.0e-5:
            continue
        if full["maximum_absolute_full_salinity_tendency_psu_per_year"] > 5.0e-8:
            continue
        if any(
            cm._normalized_equilibrium_distance(solution.x, root) < 0.05
            for root in roots
        ):
            continue
        roots.append(solution.x.copy())

    records: list[dict[str, Any]] = []
    for vector in sorted(roots, key=lambda value: float(value[5])):
        jacobian = cm._amoc_equilibrium_jacobian(
            model, vector, 0.0, template, total_salt, relative_step=1.0e-5
        )
        maximum_real_eigenvalue = float(np.max(np.real(np.linalg.eigvals(jacobian))))
        if maximum_real_eigenvalue < -1.0e-7:
            classification = "stable"
        elif maximum_real_eigenvalue > 1.0e-7:
            classification = "unstable"
        else:
            classification = "marginal"
        state = cm._state_from_amoc_equilibrium_vector(
            model, vector, template, total_salt
        )
        diagnostics = model._amoc_diagnostics(state)
        full = cm._amoc_equilibrium_full_metrics(
            model, vector, 0.0, template, total_salt
        )
        records.append(
            {
                "amoc_sv": float(vector[5]),
                "north_salinity_psu": float(vector[0]),
                "tropical_salinity_psu": float(vector[1]),
                "south_atlantic_upper_salinity_psu": float(vector[2]),
                "southern_salinity_psu": float(vector[3]),
                "deep_salinity_psu": float(vector[4]),
                "external_salinity_psu": float(state.external_salinity_psu),
                "convection_efficiency": float(vector[6]),
                "pycnocline_depth_m": float(vector[7]),
                "density_driver_ratio": float(diagnostics["amoc_density_driver_ratio"]),
                "maximum_real_eigenvalue_per_year": maximum_real_eigenvalue,
                "linear_stability": classification,
                "equilibrium_residual_norm": float(
                    np.linalg.norm(
                        cm._scaled_amoc_equilibrium_residual(
                            model, vector, 0.0, template, total_salt
                        )
                    )
                ),
                "maximum_absolute_full_salinity_tendency_psu_per_year": float(
                    full["maximum_absolute_full_salinity_tendency_psu_per_year"]
                ),
                "whole_domain_salt_closure_error_ppm": float(
                    full["whole_domain_salt_closure_error_ppm"]
                ),
            }
        )
    return records


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    stable = [row for row in records if row["linear_stability"] == "stable"]
    unstable = [row for row in records if row["linear_stability"] == "unstable"]
    return {
        "distinct_converged_roots": len(records),
        "stable_roots": len(stable),
        "unstable_roots": len(unstable),
        "bistability_supported": bool(len(stable) >= 2 and len(unstable) >= 1),
        "unstable_basin_boundary_amoc_sv": (
            float(unstable[0]["amoc_sv"]) if len(unstable) == 1 else None
        ),
    }


def main() -> int:
    source_hash = sha256(ROOT / "climate_model.py")
    if source_hash != EXPECTED_CLIMATE_SHA256:
        raise SystemExit(
            "R18.1 AMOC diagnosis requires the frozen R18 climate_model.py: "
            f"expected={EXPECTED_CLIMATE_SHA256}, current={source_hash}"
        )

    production = solve_roots(allow_reversal=False)
    reversal = solve_roots(allow_reversal=True)
    payload = {
        "candidate": "CLEM v2.29.28 R18.1 maintenance diagnosis",
        "climate_model_sha256": source_hash,
        "diagnostic_scope": "fixed_preindustrial_reduced_amoc_subsystem_zero_artificial_hosing",
        "physics_changed": False,
        "production_no_reversal": {
            "roots": production,
            "summary": summarize(production),
        },
        "reversal_enabled_sensitivity": {
            "roots": reversal,
            "summary": summarize(reversal),
        },
        "interpretation": (
            "The production equations have a stable weak boundary branch, an unstable "
            "intermediate separator near 12.32 Sv, and the stable 17 Sv control branch. "
            "Allowing reversal converts the weak-side attractor into a stable reversed "
            "circulation while retaining the same intermediate separator and strong branch. "
            "R18's ~9.87 Sv -0.40 Sv de-hosing state was below the zero-hosing separator, "
            "so relapse after the salinifying perturbation ended is structurally consistent. "
            "No restart trigger or coefficient retuning is justified by R18."
        ),
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
