#!/usr/bin/env python3
"""Fast reproducible v2.27.0 AMOC regression ensemble.

This script is a deterministic software regression check, not a probability
assessment. It samples a compact set of climate and AMOC-response coefficients
around the package defaults and verifies a transient SSP5-8.5 response through
2100. The workload is intentionally small enough for routine use on Windows and
restricted continuous-integration environments.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np

from climate_model import (
    MODEL_VERSION,
    ModelConfig,
    ProcessClimateModel,
    weighted_mean,
)
from monte_carlo import generate_samples

RUNS = 4
SEED = 12345


def _window_mean(frame, column: str, start_year: float, end_year: float) -> float:
    selection = frame.loc[
        (frame["year"] >= start_year) & (frame["year"] <= end_year), column
    ]
    if selection.empty:
        raise RuntimeError(
            f"No {column} values are available for {start_year:g}-{end_year:g}."
        )
    return float(selection.mean())


def _maximum_amoc_heat_residual_wm2(
    model: ProcessClimateModel,
    amoc_values: np.ndarray,
) -> float:
    residuals = []
    for amoc_sv in np.asarray(amoc_values, dtype=float):
        flux = model._amoc_heat_flux_atlantic_area(float(amoc_sv))
        residuals.append(
            abs(
                weighted_mean(
                    model.grid.atlantic_ocean_fraction * flux,
                    model.grid.band_area_weights,
                )
            )
        )
    return float(max(residuals, default=0.0))


def main() -> None:
    base = ModelConfig(
        start_year=1850.0,
        duration_years=250.0,
        dt_years=0.2,
        record_every_years=1.0,
        scenario="ssp585",
        forcing_mode="total_effective",
        auto_initialize_from_1850=False,
    )
    ranges = {
        "co2_doubling_erf_wm2": (3.55, 4.32),
        "water_vapor_emission_height_km_per_lnq": (0.85, 1.15),
        "ocean_heat_exchange_wm2_k": (0.80, 1.40),
        "hydrological_freshwater_sv_per_k": (0.002, 0.012),
        "greenland_freshwater_sv_per_k": (0.002, 0.010),
        "greenland_freshwater_adjustment_years": (25.0, 80.0),
        "amoc_temperature_density_coupling": (0.50, 1.00),
        "amoc_interhemispheric_temperature_coupling": (0.00, 0.06),
        "amoc_surface_heat_coupling_fraction": (0.025, 0.20),
        "amoc_heat_response_damping_wm2_k": (0.9, 2.0),
    }
    samples = generate_samples(
        base_config=base,
        ranges=ranges,
        runs=RUNS,
        seed=SEED,
        distribution="triangular",
        design="sobol",
        correlated_priors=True,
        science_modes=False,
    )

    minima: list[float] = []
    finals: list[float] = []
    declines: list[float] = []
    minimum_years: list[float] = []
    final_na: list[float] = []
    salt_errors: list[float] = []
    energy_residuals: list[float] = []

    for member, sampled in enumerate(samples, start=1):
        config = replace(base, **sampled)
        model = ProcessClimateModel(config)
        result = model.run()
        frame = result.dataframe
        amoc = frame["amoc_sv"].to_numpy(dtype=float)
        years = frame["year"].to_numpy(dtype=float)
        baseline = _window_mean(frame, "amoc_sv", 1995.0, 2014.0)
        endpoint = _window_mean(frame, "amoc_sv", 2081.0, 2100.0)

        minima.append(float(np.min(amoc)))
        finals.append(float(amoc[-1]))
        declines.append(float(100.0 * (1.0 - endpoint / baseline)))
        minimum_years.append(float(years[int(np.argmin(amoc))]))
        final_na.append(float(frame.iloc[-1]["north_atlantic_warming_c"]))
        salt_errors.append(float(frame["salt_conservation_error_ppm"].abs().max()))
        energy_residuals.append(_maximum_amoc_heat_residual_wm2(model, amoc))
        print(f"Completed AMOC validation member {member}/{RUNS}", flush=True)

    output = {
        "model_version": MODEL_VERSION,
        "members": RUNS,
        "seed": SEED,
        "scenario": "SSP5-8.5, 1850-2100",
        "purpose": "Fast deterministic software regression; not a probability assessment",
        "minimum_amoc_sv": {
            "minimum": float(np.min(minima)),
            "median": float(np.median(minima)),
            "maximum": float(np.max(minima)),
        },
        "final_amoc_2100_sv": {
            "minimum": float(np.min(finals)),
            "median": float(np.median(finals)),
            "maximum": float(np.max(finals)),
        },
        "amoc_decline_2081_2100_percent": {
            "minimum": float(np.min(declines)),
            "median": float(np.median(declines)),
            "maximum": float(np.max(declines)),
        },
        "final_north_atlantic_warming_2100_c": {
            "minimum": float(np.min(final_na)),
            "median": float(np.median(final_na)),
            "maximum": float(np.max(final_na)),
        },
        "median_year_of_minimum": float(np.median(minimum_years)),
        "maximum_salt_conservation_error_ppm": float(np.max(salt_errors)),
        "maximum_amoc_heat_conservation_error_wm2": float(
            np.max(energy_residuals)
        ),
        "sampled_ranges": {
            key: {"minimum": value[0], "maximum": value[1]}
            for key, value in ranges.items()
        },
        "note": (
            "The four members are deliberately sparse and are used only to catch "
            "software or calibration regressions. Use the Monte Carlo workflow for "
            "larger uncertainty experiments."
        ),
    }
    destination = Path(__file__).with_name("AMOC_ENSEMBLE_VALIDATION.json")
    destination.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
