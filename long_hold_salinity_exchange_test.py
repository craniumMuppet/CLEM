#!/usr/bin/env python3
"""Regression tests for the long-hold salinity-exchange correction.

The calibrated control contains a tiny bounded periodic orbit after the
seasonal Arctic and coupled-ocean additions. These tests therefore enforce
strict release tolerances and honest pre-projection salt conservation instead
of requiring every prognostic value to remain bitwise constant.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from climate_model import ModelConfig, run_model


def test_validation() -> None:
    """Negative background-exchange strengths must be rejected."""
    for field in (
        "amoc_southern_external_exchange_sv",
        "amoc_south_atlantic_external_exchange_sv",
    ):
        try:
            replace(ModelConfig(), **{field: -0.1}).validate()
        except ValueError:
            pass
        else:
            raise AssertionError(f"negative {field} should fail validation")


def test_control_state_is_exactly_unchanged() -> None:
    """The conservative exchange must preserve the calibrated control orbit."""
    config = ModelConfig(
        scenario="constant",
        co2_start_ppm=278.3,
        duration_years=100.0,
        dt_years=0.2,
        record_every_years=10.0,
        auto_initialize_from_1850=False,
    )
    result = run_model(config, diagnose=False, run_hysteresis=False)
    frame = result.dataframe

    salinity_columns = [
        "north_salinity_psu",
        "tropical_salinity_psu",
        "south_atlantic_upper_salinity_psu",
        "southern_salinity_psu",
        "deep_salinity_psu",
        "external_salinity_psu",
    ]
    for column in salinity_columns:
        values = frame[column].to_numpy(dtype=float)
        assert float(np.ptp(values)) < 1.0e-5

    amoc = frame["amoc_sv"].to_numpy(dtype=float)
    assert float(np.max(np.abs(amoc - config.amoc_reference_sv))) < 1.0e-3
    assert float(np.max(np.abs(frame["salt_conservation_error_ppm"]))) < 1.0e-10
    assert (
        float(np.max(np.abs(frame["pre_projection_salt_conservation_error_ppm"])))
        <= config.salt_projection_max_residual_ppm
    )


def test_long_capped_co2_hold_has_no_restart_overshoot() -> None:
    """A long 1200 ppm hold may recover gradually but must not restart abruptly."""
    config = ModelConfig(
        scenario="percent_ramp_hold",
        co2_start_ppm=278.3,
        co2_growth_rate_percent_per_year=1.0,
        co2_growth_cap_ppm=1200.0,
        co2_hold_years=1000.0,
        dt_years=0.2,
        record_every_years=2.0,
    )
    result = run_model(config, diagnose=False, run_hysteresis=False)
    frame = result.dataframe
    years = frame["year"].to_numpy(dtype=float)
    amoc = frame["amoc_sv"].to_numpy(dtype=float)

    assert np.all(np.isfinite(amoc))
    assert len(amoc) >= 3

    minimum_index = int(np.argmin(amoc))
    minimum_amoc = float(amoc[minimum_index])
    post_minimum = amoc[minimum_index:]
    post_minimum_maximum = float(np.max(post_minimum))

    year_steps = np.diff(years)
    amoc_steps = np.diff(amoc)
    assert np.all(year_steps > 0.0)
    maximum_positive_recovery_rate = float(np.max(amoc_steps / year_steps))

    assert minimum_amoc < 10.0
    assert maximum_positive_recovery_rate < 0.5
    assert post_minimum_maximum <= config.amoc_hydraulic_transport_max_sv + 1.0e-8
    assert float(frame["southern_salinity_psu"].min()) > 32.5
    assert float(np.max(np.abs(frame["salt_conservation_error_ppm"]))) < 1.0e-6
    assert (
        float(np.max(np.abs(frame["pre_projection_salt_conservation_error_ppm"])))
        <= config.salt_projection_max_residual_ppm
    )


if __name__ == "__main__":
    test_validation()
    test_control_state_is_exactly_unchanged()
    test_long_capped_co2_hold_has_no_restart_overshoot()
    print("Long-hold salinity-exchange tests passed")
