#!/usr/bin/env python3
"""Long-running migrated AMOC and scenario regressions for v2.27.0."""

from __future__ import annotations

import numpy as np

from climate_model import ModelConfig, ProcessClimateModel, diagnose_amoc_hysteresis


def test_equilibrium_continuation_is_continuous_and_conservative() -> None:
    config = ModelConfig(
        scenario="constant",
        duration_years=10.0,
        dt_years=0.1,
        warming_freshwater_sv_per_k=0.0,
    )
    frame = diagnose_amoc_hysteresis(
        config,
        maximum_hosing_sv=0.6,
        hosing_step_sv=0.05,
    )
    assert not frame.empty
    # Since v2.22 unresolved continuation points are explicit rows rather than
    # silently substituted unstable roots. Require every accepted stable root
    # to be finite and conservative, while permitting explicit NaNs elsewhere.
    resolved = frame[frame["stable_root_found"].astype(bool)]
    assert not resolved.empty
    assert float(resolved["equilibrium_residual_norm"].max()) < 2.0e-5
    assert float(resolved["salt_conservation_error_ppm"].abs().max()) < 1.0e-5
    assert float(resolved.loc[resolved["target_hosing_sv"] == 0.0, "amoc_sv"].max()) > 16.0
    assert np.isfinite(resolved["amoc_sv"]).all()
    unresolved_path = frame[
        (~frame["stable_root_found"].astype(bool))
        & frame["phase"].isin(["forward", "reverse"])
    ]
    if not unresolved_path.empty:
        assert unresolved_path["amoc_sv"].isna().all()
    pseudo = frame[frame["phase"] == "branch"]
    if not pseudo.empty:
        assert pseudo["equilibrium_converged"].astype(bool).all()
        assert np.isfinite(pseudo["amoc_sv"]).all()


def test_long_ramp_hold_has_no_discrete_target_jump() -> None:
    config = ModelConfig(
        scenario="one_percent",
        duration_years=4000.0,
        dt_years=0.25,
        record_every_years=25.0,
        one_percent_cap_ppm=2413.2,
        forcing_mode="co2_only",
    )
    frame = ProcessClimateModel(config).run().dataframe
    assert float(frame["amoc_sv"].min()) < 0.5
    assert float(frame["amoc_convection_efficiency"].min()) < 0.05
    annual_target_change = (
        frame["amoc_convection_target"].diff().abs()
        / frame["year"].diff()
    )
    assert float(annual_target_change.max()) < 0.05
    assert float(frame["salt_conservation_error_ppm"].abs().max()) < 1.0e-5


def test_ssp585_transient_response() -> None:
    frame = ProcessClimateModel(
        ModelConfig(
            scenario="ssp585",
            start_year=1850.0,
            duration_years=650.0,
            dt_years=0.1,
        )
    ).run().dataframe
    initial = frame.iloc[0]
    final = frame.iloc[-1]
    assert final["global_surface_warming_c"] > 5.0
    assert float(frame["amoc_temperature_density_term"].min()) < initial["amoc_temperature_density_term"]
    assert float(frame["amoc_sv"].min()) < 2.0
    assert float(frame["amoc_convective_mixing_sv"].min()) < 0.02
    assert float(frame["salt_conservation_error_ppm"].abs().max()) < 1.0e-5


def main() -> None:
    for test in (
        test_equilibrium_continuation_is_continuous_and_conservative,
        test_long_ramp_hold_has_no_discrete_target_jump,
        test_ssp585_transient_response,
    ):
        test()
        print(f"PASS: {test.__name__}", flush=True)
    print("All migrated climate-model v2.27.0 full regression tests passed.")


if __name__ == "__main__":
    main()
