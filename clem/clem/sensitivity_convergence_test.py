#!/usr/bin/env python3
"""Fast tests for explicit equilibrium convergence reporting."""

from climate_model import ModelConfig, diagnose_climate_sensitivity


def main() -> None:
    config = ModelConfig(resolution_deg=10.0, dt_years=0.2)

    unconverged = diagnose_climate_sensitivity(
        config,
        equilibrium_years=20.0,
        maximum_equilibrium_years=40.0,
        equilibrium_toa_tolerance_wm2=1.0e-8,
        auto_extend_equilibrium=True,
    )
    assert unconverged.equilibrium_simulation_years == 40.0
    assert not unconverged.equilibrium_converged

    permissive = diagnose_climate_sensitivity(
        config,
        equilibrium_years=20.0,
        maximum_equilibrium_years=20.0,
        equilibrium_toa_tolerance_wm2=10.0,
        auto_extend_equilibrium=False,
    )
    assert permissive.equilibrium_converged
    assert (
        permissive.gregory_feedback_wm2_k
        == permissive.gregory_restoring_coefficient_wm2_k
    )
    summary = permissive.summary()
    assert "equilibrium_converged" in summary
    assert "gregory_restoring_coefficient_wm2_k" in summary
    assert "gregory_feedback_wm2_k" in summary
    print("sensitivity convergence tests passed")


if __name__ == "__main__":
    main()
