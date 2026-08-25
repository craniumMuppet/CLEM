#!/usr/bin/env python3
"""Regression tests for the v2.17.0 hybrid SSP rate splice."""

from __future__ import annotations

from climate_model import ModelConfig, ProcessClimateModel


def build_model(before: str = "ssp585", after: str = "ssp245") -> ProcessClimateModel:
    return ProcessClimateModel(
        ModelConfig(
            start_year=1850.0,
            duration_years=650.0,
            scenario="hybrid_ssp",
            ssp_before=before,
            ssp_after=after,
            ssp_switch_year=2120.0,
            ssp_transition_years=10.0,
            dt_years=0.2,
            record_every_years=1.0,
        )
    )


def test_preserves_switch_level() -> None:
    model = build_model()
    before = model.ssp_pathways["ssp585"]
    expected = float(__import__("numpy").interp(2120.0, before["year"], before["co2_ppm"]))
    actual = model.co2_ppm(2120.0 - model.config.start_year)
    assert abs(actual - expected) < 1.0e-9


def test_late_switch_does_not_reset_to_low_pathway() -> None:
    model = build_model()
    co2_2120 = model.co2_ppm(270.0)
    co2_2130 = model.co2_ppm(280.0)
    forcing_2120 = model.prescribed_forcing_components(270.0)["total_wm2"]
    forcing_2130 = model.prescribed_forcing_components(280.0)["total_wm2"]
    assert co2_2130 > co2_2120
    assert co2_2130 > 1300.0
    assert forcing_2130 > forcing_2120
    assert forcing_2130 > 10.0


def test_identical_pathways_are_unchanged() -> None:
    model = build_model("ssp245", "ssp245")
    for year in (2000.0, 2120.0, 2200.0, 2500.0):
        elapsed = year - model.config.start_year
        hybrid = model.co2_ppm(elapsed)
        original = model._ssp_value_from("ssp245", "co2_ppm", elapsed)
        assert abs(hybrid - original) < 1.0e-6


def test_full_response_has_no_switch_cooling_or_amoc_rebound() -> None:
    model = build_model()
    result = model.run().dataframe
    at_2120 = result.iloc[(result["year"] - 2120.0).abs().argmin()]
    at_2130 = result.iloc[(result["year"] - 2130.0).abs().argmin()]
    assert at_2130["global_surface_warming_c"] >= at_2120["global_surface_warming_c"]
    assert at_2130["amoc_sv"] <= at_2120["amoc_sv"]


def main() -> None:
    test_preserves_switch_level()
    test_late_switch_does_not_reset_to_low_pathway()
    test_identical_pathways_are_unchanged()
    test_full_response_has_no_switch_cooling_or_amoc_rebound()
    print("All v2.17.0 hybrid SSP transition tests passed.")


if __name__ == "__main__":
    main()
