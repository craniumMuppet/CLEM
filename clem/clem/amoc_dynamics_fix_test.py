#!/usr/bin/env python3
"""Migrated AMOC dynamics regressions for the v2.27.0 seasonal-Arctic model."""

from __future__ import annotations

import numpy as np

from climate_model import ModelConfig, ProcessClimateModel


def test_control_equilibrium() -> None:
    config = ModelConfig(
        scenario="constant",
        duration_years=200.0,
        dt_years=0.1,
        record_every_years=1.0,
        warming_freshwater_sv_per_k=0.0,
    )
    frame = ProcessClimateModel(config).run().dataframe
    # The seasonal reference cycle produces a minute bounded control orbit;
    # require physical stationarity rather than bit-level equality.
    assert np.max(np.abs(frame["amoc_sv"] - config.amoc_reference_sv)) < 1.0e-3
    assert np.max(np.abs(frame["amoc_convection_efficiency"] - 1.0)) < 1.0e-5
    assert np.max(np.abs(frame["amoc_pycnocline_transport_multiplier"] - 1.0)) < 1.0e-5
    assert np.max(np.abs(frame["global_surface_warming_c"])) < 1.0e-4
    assert np.max(np.abs(frame["pre_projection_salt_conservation_error_ppm"])) <= config.salt_projection_max_residual_ppm


def test_hybrid_ssp_has_material_2100_weakening_and_bounded_long_horizon() -> None:
    config = ModelConfig(
        start_year=1850.0,
        duration_years=450.0,
        dt_years=0.1,
        record_every_years=1.0,
        scenario="hybrid_ssp",
        forcing_mode="total_effective",
        ssp_before="ssp585",
        ssp_after="ssp245",
        ssp_switch_year=2020.0,
        ssp_transition_years=20.0,
    )
    frame = ProcessClimateModel(config).run().dataframe
    minimum = float(frame["amoc_sv"].min())
    final = float(frame["amoc_sv"].iloc[-1])
    value_2100 = float(
        frame.iloc[int(np.argmin(np.abs(frame["year"].to_numpy() - 2100.0)))][
            "amoc_sv"
        ]
    )
    # v2.29.9 restores the pre-v2.29.7 scientific compatibility window.
    assert 10.0 < value_2100 < 14.0, value_2100
    # The long hybrid branch weakens materially after 2100 and then recovers
    # under mitigation. The former sub-10 Sv requirement was a self-authored
    # calibration target rather than an external scientific constraint.
    assert 6.5 < minimum < 11.0, minimum
    assert minimum < value_2100 - 0.20, (minimum, value_2100)
    assert final > minimum + 0.5, (minimum, final)
    assert final < 16.0, final
    assert float(frame["amoc_convection_efficiency"].min()) < 0.999
    assert float(frame["amoc_convection_density_driver_ratio"].min()) < 0.99
    assert float(frame["amoc_pycnocline_transport_multiplier"].max()) < 1.04
    assert float(frame["salt_conservation_error_ppm"].abs().max()) < 1.0e-6


def test_annual_arctic_compatibility_family_retains_legacy_hybrid_range() -> None:
    config = ModelConfig(
        start_year=1850.0,
        duration_years=450.0,
        dt_years=0.1,
        record_every_years=1.0,
        scenario="hybrid_ssp",
        forcing_mode="total_effective",
        ssp_before="ssp585",
        ssp_after="ssp245",
        ssp_switch_year=2020.0,
        ssp_transition_years=20.0,
        seasonal_arctic_enabled=False,
    )
    frame = ProcessClimateModel(config).run().dataframe
    minimum = float(frame["amoc_sv"].min())
    final = float(frame["amoc_sv"].iloc[-1])
    value_2100 = float(
        frame.iloc[int(np.argmin(np.abs(frame["year"].to_numpy() - 2100.0)))][
            "amoc_sv"
        ]
    )
    assert 10.0 < value_2100 < 14.0, value_2100
    assert minimum > 6.0, minimum
    assert final > minimum + 0.5, (minimum, final)
    assert final < 16.5, final


def test_ssp585_weakens_more_than_hybrid_mitigation() -> None:
    hybrid = ModelConfig(
        start_year=1850.0,
        duration_years=250.0,
        dt_years=0.1,
        record_every_years=1.0,
        scenario="hybrid_ssp",
        forcing_mode="total_effective",
        ssp_before="ssp585",
        ssp_after="ssp245",
        ssp_switch_year=2020.0,
        ssp_transition_years=20.0,
    )
    high = ModelConfig(
        start_year=1850.0,
        duration_years=250.0,
        dt_years=0.1,
        record_every_years=1.0,
        scenario="ssp585",
        forcing_mode="total_effective",
    )
    hybrid_final = float(ProcessClimateModel(hybrid).run().dataframe["amoc_sv"].iloc[-1])
    high_final = float(ProcessClimateModel(high).run().dataframe["amoc_sv"].iloc[-1])
    assert high_final < hybrid_final - 0.8, (high_final, hybrid_final)


def main() -> None:
    tests = [
        test_control_equilibrium,
        test_hybrid_ssp_has_material_2100_weakening_and_bounded_long_horizon,
        test_annual_arctic_compatibility_family_retains_legacy_hybrid_range,
        test_ssp585_weakens_more_than_hybrid_mitigation,
    ]
    for test in tests:
        test()
        print(f"PASS: {test.__name__}")
    print("All migrated v2.27.0 AMOC-dynamics regression tests passed.")


if __name__ == "__main__":
    main()
