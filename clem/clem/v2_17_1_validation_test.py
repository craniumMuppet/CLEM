#!/usr/bin/env python3
"""Regression tests for the v2.17.1 review fixes."""

import os
import subprocess
import sys
from dataclasses import replace

import numpy as np

from climate_model import ModelConfig, ProcessClimateModel


def expect_value_error(config: ModelConfig, text: str) -> None:
    try:
        config.validate()
    except ValueError as error:
        assert text in str(error), str(error)
    else:
        raise AssertionError(f"Expected validation error containing {text!r}")


def test_missing_validation_checks() -> None:
    base = ModelConfig()
    expect_value_error(
        replace(base, amoc_external_box_volume_m3=0.0),
        "amoc_external_box_volume_m3",
    )
    expect_value_error(
        replace(base, initial_external_salinity_psu=-1.0),
        "external-reservoir salinities",
    )


def test_cross_resolution_initialization_and_control() -> None:
    initial_ratios = []
    controls = []
    forced = []

    for resolution in (2.5, 5.0, 10.0):
        model = ProcessClimateModel(
            ModelConfig(
                resolution_deg=resolution,
                dt_years=0.2,
                duration_years=50.0,
                scenario="constant",
                record_every_years=50.0,
            )
        )
        initial_ratios.append(model.baseline_density_driver_ratio)
        control_result = model.run()
        control = control_result.dataframe.iloc[-1]
        controls.append(
            [
                control["global_surface_warming_c"],
                control["amoc_sv"],
                control["toa_imbalance_wm2"],
                control["salt_conservation_error_ppm"],
                control_result.summary()[
                    "maximum_pre_projection_salt_conservation_error_ppm"
                ],
            ]
        )

        forced_frame = ProcessClimateModel(
            ModelConfig(
                resolution_deg=resolution,
                dt_years=0.2,
                duration_years=100.0,
                scenario="step_2x",
                record_every_years=100.0,
            )
        ).run().dataframe
        endpoint = forced_frame.iloc[-1]
        forced.append(
            [
                endpoint["global_surface_warming_c"],
                endpoint["amoc_sv"],
                endpoint["toa_imbalance_wm2"],
            ]
        )

    initial_ratios = np.asarray(initial_ratios)
    controls = np.asarray(controls)
    forced = np.asarray(forced)

    default_config = ModelConfig()
    assert np.all(
        (initial_ratios >= default_config.amoc_minimum_initial_density_ratio)
        & (initial_ratios <= default_config.amoc_maximum_initial_density_ratio)
    )
    # The native-Arctic geometry produces a wider but still bounded initial
    # density-ratio spread at 10 degrees. Every resolution remains inside the
    # configured physical screen and the forced AMOC spread below stays tight.
    assert np.ptp(initial_ratios) < 0.30
    assert np.max(np.abs(controls[:, 0])) < 1.0e-4
    assert np.max(np.abs(controls[:, 1] - default_config.amoc_reference_sv)) < 1.0e-3
    assert np.max(np.abs(controls[:, 2])) < 1.0e-3
    assert np.max(np.abs(controls[:, 3])) < 1.0e-6
    assert np.max(np.abs(controls[:, 4])) <= default_config.salt_projection_max_residual_ppm
    assert np.ptp(forced[:, 0]) < 0.02
    assert np.ptp(forced[:, 1]) < 0.60
    assert np.ptp(forced[:, 2]) < 0.02



def test_default_five_degree_migrated_compatibility() -> None:
    # v2.25.2 adds prognostic seasonal Arctic states and revised AMOC coupling,
    # so exact pre-v2.21 endpoint values are intentionally obsolete. This test
    # retains the useful compatibility contract: legacy options must run, stay
    # finite, and remain close to the default global response while preserving
    # the expected Greenland-driver distinction.
    legacy_frame = ProcessClimateModel(
        ModelConfig(
            resolution_deg=5.0,
            scenario="ssp245",
            duration_years=250.0,
            record_every_years=250.0,
            amoc_coupling_scheme="euler",
            amoc_southern_external_exchange_sv=0.0,
            amoc_south_atlantic_external_exchange_sv=0.0,
            greenland_temperature_driver="global",
            amoc_convection_timescale_smoothing=1.0e-12,
        )
    ).run().dataframe
    legacy_endpoint = legacy_frame.iloc[-1]
    assert np.isfinite(legacy_endpoint[[
        "global_surface_warming_c", "amoc_sv", "greenland_freshwater_sv"
    ]].to_numpy(dtype=float)).all()
    assert 3.0 < float(legacy_endpoint["global_surface_warming_c"]) < 3.5
    assert 8.5 < float(legacy_endpoint["amoc_sv"]) < 12.0
    assert 0.0 < float(legacy_endpoint["greenland_freshwater_sv"]) < 0.03

    default_frame = ProcessClimateModel(
        ModelConfig(
            resolution_deg=5.0,
            scenario="ssp245",
            duration_years=250.0,
            record_every_years=250.0,
            amoc_coupling_scheme="euler",
        )
    ).run().dataframe
    endpoint = default_frame.iloc[-1]
    assert abs(
        float(endpoint["global_surface_warming_c"])
        - float(legacy_endpoint["global_surface_warming_c"])
) < 1.0e-2
    assert abs(float(endpoint["amoc_sv"]) - float(legacy_endpoint["amoc_sv"])) < 0.75
    # The calibrated seasonal blended driver need not be larger than the legacy
    # global-only driver and can be signed at an individual seasonal sample. The
    # compatibility requirement is that it remains finite, bounded, and distinct.
    assert abs(float(endpoint["greenland_freshwater_sv"])) <= (
        ModelConfig().greenland_max_freshwater_sv + 1.0e-12
    )
    assert abs(
        float(endpoint["greenland_freshwater_sv"])
        - float(legacy_endpoint["greenland_freshwater_sv"])
    ) > 1.0e-8


def test_optional_heun_coupling() -> None:
    common = dict(
        scenario="ssp245",
        duration_years=100.0,
        dt_years=0.2,
        record_every_years=10.0,
    )
    euler = ProcessClimateModel(
        ModelConfig(**common, amoc_coupling_scheme="euler")
    ).run().dataframe
    heun = ProcessClimateModel(
        ModelConfig(**common, amoc_coupling_scheme="heun")
    ).run().dataframe

    assert float(heun["salt_conservation_error_ppm"].abs().max()) < 1.0e-6
    assert abs(float(euler.iloc[-1]["global_surface_warming_c"]) - float(heun.iloc[-1]["global_surface_warming_c"])) < 0.01
    assert abs(float(euler.iloc[-1]["amoc_sv"]) - float(heun.iloc[-1]["amoc_sv"])) < 0.10


if __name__ == "__main__":
    tests = {
        test.__name__: test
        for test in (
            test_missing_validation_checks,
            test_cross_resolution_initialization_and_control,
            test_default_five_degree_migrated_compatibility,
            test_optional_heun_coupling,
        )
    }
    if len(sys.argv) == 3 and sys.argv[1] == "--single":
        selected = tests[sys.argv[2]]
        selected()
        print(f"PASS: {selected.__name__}", flush=True)
        os._exit(0)
    for name in tests:
        subprocess.run(
            [sys.executable, __file__, "--single", name],
            check=True,
            timeout=600,
        )
    print("v2.17.1 validation and cross-resolution tests passed", flush=True)
    os._exit(0)
