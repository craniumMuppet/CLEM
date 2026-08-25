#!/usr/bin/env python3
"""Regression tests for continuous, emergent AMOC weakening.

The control-branch check uses physically meaningful release tolerances rather
than exact floating-point equality. The seasonal Arctic and coupled ocean
introduce a tiny bounded periodic control orbit; that orbit must remain far
smaller than any scientifically meaningful AMOC change and must conserve salt
before the roundoff-only salt projection is applied.
"""

from __future__ import annotations

import inspect

import numpy as np

from climate_model import ModelConfig, ProcessClimateModel


def test_no_boolean_collapse_command_controls_dynamics() -> None:
    source = inspect.getsource(ProcessClimateModel._amoc_diagnostics)
    assert "if convection_density_ratio <=" not in source
    assert "amoc_convection_restart_density_ratio" not in source
    assert "amoc_collapsed_convection_fraction" not in source


def test_one_percent_ramp_collapses_continuously() -> None:
    config = ModelConfig(
        scenario="one_percent",
        duration_years=1000.0,
        dt_years=0.10,
        record_every_years=1.0,
        one_percent_cap_ppm=2413.2,
        forcing_mode="co2_only",
    )
    result = ProcessClimateModel(config).run()
    frame = result.dataframe
    assert float(frame["amoc_sv"].min()) < 0.5
    assert float(frame["amoc_convection_efficiency"].min()) < 0.05
    assert float(frame["amoc_convective_mixing_sv"].min()) < 0.02
    # The continuous target must not contain the former one-step 1 -> 0.02 cliff.
    assert float(frame["amoc_convection_target"].diff().abs().max()) < 0.03
    assert float(frame["amoc_sv"].diff().abs().max()) < 1.0
    assert float(frame["salt_conservation_error_ppm"].abs().max()) < 1.0e-5
    assert (
        float(frame["pre_projection_salt_conservation_error_ppm"].abs().max())
        <= config.salt_projection_max_residual_ppm
    )


def test_control_branch_remains_active() -> None:
    config = ModelConfig(
        scenario="constant",
        duration_years=200.0,
        dt_years=0.25,
        record_every_years=10.0,
        warming_freshwater_sv_per_k=0.0,
    )
    result = ProcessClimateModel(config).run()
    frame = result.dataframe

    amoc = frame["amoc_sv"].to_numpy(dtype=float)
    mixing = frame["amoc_convective_mixing_sv"].to_numpy(dtype=float)
    efficiency = frame["amoc_convection_efficiency"].to_numpy(dtype=float)

    assert float(frame["amoc_convection_collapsed"].max()) == 0.0
    assert float(np.max(np.abs(amoc - config.amoc_reference_sv))) < 1.0e-3
    assert float(np.max(np.abs(mixing - 5.0))) < 1.0e-4
    assert float(np.max(np.abs(efficiency - 1.0))) < 1.0e-5
    assert (
        float(frame["pre_projection_salt_conservation_error_ppm"].abs().max())
        <= config.salt_projection_max_residual_ppm
    )


def main() -> None:
    for test in (
        test_no_boolean_collapse_command_controls_dynamics,
        test_one_percent_ramp_collapses_continuously,
        test_control_branch_remains_active,
    ):
        test()
        print(f"PASS: {test.__name__}")
    print("All continuous-collapse tests passed.")


if __name__ == "__main__":
    main()
