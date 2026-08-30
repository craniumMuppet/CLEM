#!/usr/bin/env python3
"""Regression tests for the generalized percent-ramp-to-cap CO2 scenario."""

from __future__ import annotations

import math
from pathlib import Path
import tempfile

import numpy as np

from climate_model import (
    ModelConfig,
    ProcessClimateModel,
    parse_percent_ramp_rates,
    percent_ramp_time_to_cap_years,
    run_model,
    save_percent_ramp_comparison,
)
from climate_model_gui import build_cli_command, validate_values, DEFAULTS


def main() -> None:
    ramp_years = percent_ramp_time_to_cap_years(278.3, 1200.0, 1.0)
    expected = math.log(1200.0 / 278.3) / math.log(1.01)
    assert abs(ramp_years - expected) < 1.0e-12

    config = ModelConfig(
        scenario="percent_ramp_hold",
        start_year=1850.0,
        duration_years=1.0,  # Deliberately ignored for this scenario.
        dt_years=0.25,
        record_every_years=1.0,
        co2_start_ppm=278.3,
        co2_growth_rate_percent_per_year=2.0,
        co2_growth_cap_ppm=300.0,
        co2_hold_years=3.0,
    )
    model = ProcessClimateModel(config)
    expected_duration = percent_ramp_time_to_cap_years(278.3, 300.0, 2.0) + 3.0
    assert abs(model.config.duration_years - expected_duration) < 1.0e-12
    assert abs(model.co2_ppm(0.0) - 278.3) < 1.0e-12
    assert model.co2_ppm(expected_duration) == 300.0
    assert model.co2_ppm(expected_duration - 1.0) == 300.0

    result = run_model(config, diagnose=False)
    final = result.dataframe.iloc[-1]
    assert abs(float(final["co2_ppm"]) - 300.0) < 1.0e-9
    assert abs(float(final["elapsed_years"]) - expected_duration) < 1.0e-9
    assert result.summary()["co2_growth_rate_percent_per_year"] == 2.0
    assert result.summary()["co2_growth_cap_ppm"] == 300.0
    assert result.summary()["co2_hold_years"] == 3.0

    assert parse_percent_ramp_rates("5, 1;0.5,1") == [0.5, 1.0, 5.0]

    values = dict(DEFAULTS)
    values.update(
        {
            "scenario": "percent_ramp_hold",
            "co2_start": "278.3",
            "co2_growth_cap": "1200",
            "co2_hold_years": "200",
            "percent_ramp_compare_rates": "0.5,1,2,3,5",
            "run_diagnostics": False,
            "output": "outputs_percent_ramp_test",
        }
    )
    validate_values(values)
    command = build_cli_command(values)
    command_text = " ".join(command)
    for expected_option in (
        "--scenario percent_ramp_hold",
        "--co2-growth-cap 1200",
        "--co2-hold-years 200",
        "--percent-ramp-compare-rates 0.5,1,2,3,5",
    ):
        assert expected_option in command_text
    assert "--co2-growth-rate-percent" not in command_text

    with tempfile.TemporaryDirectory() as temporary_directory:
        output = Path(temporary_directory)
        payload = save_percent_ramp_comparison(
            config,
            [0.5, 1.0, 2.0, 3.0, 5.0],
            output,
        )
        assert len(payload["runs"]) == 5
        for filename in (
            "percent_ramp_comparison.png",
            "percent_ramp_comparison_timeseries.csv",
            "percent_ramp_comparison_summary.csv",
            "percent_ramp_comparison_summary.json",
        ):
            path = output / filename
            assert path.exists() and path.stat().st_size > 0

    for bad_config in (
        ModelConfig(
            scenario="percent_ramp_hold",
            co2_growth_rate_percent_per_year=0.0,
        ),
        ModelConfig(
            scenario="percent_ramp_hold",
            co2_start_ppm=400.0,
            co2_growth_cap_ppm=300.0,
        ),
        ModelConfig(
            scenario="percent_ramp_hold",
            co2_hold_years=-1.0,
        ),
    ):
        try:
            ProcessClimateModel(bad_config)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid percent-ramp configuration was accepted")

    print("Percent-ramp hold tests passed.")


if __name__ == "__main__":
    main()
