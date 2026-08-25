"""Deterministic property-style conservation tests for the climate model.

The release suite must run without optional third-party property-test plugins.
Each test exercises a reproducible boundary grid plus seeded random samples.
"""

from __future__ import annotations

import itertools

import numpy as np

from climate_model import ModelConfig, ProcessClimateModel


BASE_CONFIG = ModelConfig(
    scenario="constant",
    duration_years=20.0,
    dt_years=0.2,
    record_every_years=1.0,
    resolution_deg=10.0,
    auto_initialize_from_1850=False,
    amoc_allow_reversal=True,
)
MODELS = {
    mode: ProcessClimateModel(
        ModelConfig(
            **{
                **BASE_CONFIG.__dict__,
                "freshwater_compensation_mode": mode,
            }
        )
    )
    for mode in ("external", "atlantic")
}


def test_advective_and_mixing_tendencies_conserve_total_salt() -> None:
    model = MODELS["external"]
    samples: list[tuple[np.ndarray, float]] = []
    for salinity in (30.0, 34.7, 38.0):
        for amoc_sv in (-30.0, 0.0, 30.0):
            samples.append((np.full(6, salinity, dtype=float), amoc_sv))
    rng = np.random.default_rng(2292)
    for _ in range(30):
        samples.append(
            (rng.uniform(30.0, 38.0, size=6), float(rng.uniform(-30.0, 30.0)))
        )

    for salinities, amoc_sv in samples:
        tendency = model._advective_mixing_salinity_tendency(salinities, amoc_sv)
        total_salt_tendency = float(np.dot(tendency, model.amoc_box_volumes_m3))
        scale = float(np.sum(np.abs(tendency * model.amoc_box_volumes_m3)))
        assert abs(total_salt_tendency) <= max(1.0e-8 * scale, 1.0e-3)


def test_surface_freshwater_redistribution_has_zero_global_anomaly() -> None:
    for compensation_mode, hosing_sv, hydrological_sv, greenland_sv in itertools.product(
        ("external", "atlantic"),
        (0.0, 0.25, 1.0),
        (0.0, 0.10, 0.30),
        (0.0, 0.05, 0.10),
    ):
        model = MODELS[compensation_mode]
        flux = model._surface_freshwater_fluxes_sv(
            hosing_sv,
            hydrological_sv,
            greenland_sv,
        )
        assert abs(float(np.sum(flux))) < 1.0e-12


def test_amoc_heat_redistribution_is_globally_conservative() -> None:
    model = MODELS["external"]
    for amoc_sv in np.linspace(-15.0, 35.0, 26):
        flux = model._amoc_heat_flux_atlantic_area(float(amoc_sv))
        global_integral = float(
            np.sum(
                model.grid.band_area_weights
                * model.grid.atlantic_ocean_fraction
                * flux
            )
        )
        assert abs(global_integral) < 1.0e-10


def test_short_integrations_preserve_salt() -> None:
    for compensation_mode, hosing_sv, dt_years in itertools.product(
        ("external", "atlantic"),
        (0.0, 0.125, 0.25),
        (0.05, 0.1, 0.2),
    ):
        config = ModelConfig(
            scenario="constant",
            duration_years=15.0,
            dt_years=dt_years,
            record_every_years=1.0,
            resolution_deg=10.0,
            auto_initialize_from_1850=False,
            freshwater_compensation_mode=compensation_mode,
            freshwater_hosing_sv=hosing_sv,
            freshwater_start_fraction=0.0,
            freshwater_ramp_years=2.0,
        )
        frame = ProcessClimateModel(config).run().dataframe
        core_columns = [
            "co2_ppm",
            "global_surface_warming_c",
            "amoc_sv",
            "north_salinity_psu",
            "tropical_salinity_psu",
            "south_atlantic_upper_salinity_psu",
            "southern_salinity_psu",
            "deep_salinity_psu",
            "external_salinity_psu",
            "salt_conservation_error_ppm",
            "pre_projection_salt_conservation_error_ppm",
        ]
        assert np.isfinite(frame[core_columns].to_numpy()).all()
        assert float(frame["salt_conservation_error_ppm"].abs().max()) < 1.0e-8
        assert (
            float(frame["pre_projection_salt_conservation_error_ppm"].abs().max())
            <= config.salt_projection_max_residual_ppm
        )
