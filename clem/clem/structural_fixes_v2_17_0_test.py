#!/usr/bin/env python3
"""Regression tests for the v2.17.0 AMOC structural fixes."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import replace

import numpy as np

from climate_model import ModelConfig, ProcessClimateModel
from monte_carlo import (
    _amoc_response_diagnostics,
    _joint_prior_state_is_physical,
    generate_samples,
    science_default_ranges,
)


def test_finite_greenland_reservoir() -> None:
    config = ModelConfig(
        scenario="constant",
        co2_start_ppm=2400.0,
        duration_years=300.0,
        auto_initialize_from_1850=False,
        greenland_freshwater_sv_per_k=0.05,
        greenland_freshwater_adjustment_years=1.0,
        greenland_initial_ice_mass_gt=1000.0,
        greenland_max_freshwater_sv=0.10,
        greenland_depletion_exponent=1.0,
        record_every_years=1.0,
    )
    frame = ProcessClimateModel(config).run().dataframe
    remaining = frame["greenland_remaining_ice_gt"].to_numpy()
    gross_melt = frame["greenland_cumulative_melt_gt"].to_numpy()
    accumulation = frame["greenland_cumulative_accumulation_gt"].to_numpy()
    net_loss = frame["greenland_cumulative_net_ice_loss_gt"].to_numpy()
    assert np.all(remaining >= -1.0e-9)
    assert np.all(np.diff(gross_melt) >= -1.0e-9)
    assert np.all(np.diff(accumulation) >= -1.0e-9)
    assert np.max(np.abs(gross_melt - accumulation - net_loss)) < 1.0e-6
    assert np.max(np.abs(remaining + net_loss - config.greenland_initial_ice_mass_gt)) < 1.0e-6
    # The reduced SMB permits winter accumulation on a small remnant, so exact
    # exhaustion is no longer the physical contract.  Require a bounded, nearly
    # depleted reservoir and a relaxed slow dynamic-discharge component.
    assert 0.0 <= float(remaining[-1]) < 0.02 * config.greenland_initial_ice_mass_gt
    assert abs(float(frame["greenland_dynamic_discharge_sv"].iloc[-1])) < 1.0e-5
    assert (
        abs(float(frame["greenland_annual_mean_freshwater_sv"].iloc[-1]))
        <= config.greenland_max_freshwater_sv
    )


def test_absolute_density_margin_screening() -> None:
    fragile = ModelConfig(
        scenario="constant",
        duration_years=1.0,
        initial_north_salinity_psu=34.70,
        initial_deep_salinity_psu=34.70,
        initial_southern_salinity_psu=34.70,
    )
    try:
        ProcessClimateModel(fragile)
    except ValueError as exc:
        assert "absolute initial density margin" in str(exc)
    else:
        raise AssertionError("Fragile initial hydrography was not rejected")

    ProcessClimateModel(replace(fragile, amoc_enforce_initial_density_constraint=False))

    base = ModelConfig()
    names = ["initial_north_salinity_psu", "initial_southern_salinity_psu"]
    ranges = {name: science_default_ranges("ar6_amoc")[name] for name in names}
    samples = generate_samples(
        base,
        ranges,
        runs=128,
        seed=41,
        distribution="uniform",
        design="sobol",
        correlated_priors=True,
        science_modes=True,
    )
    accepted = 0
    rejected = 0
    for sampled in samples:
        screened = _joint_prior_state_is_physical(sampled, base)
        try:
            model = ProcessClimateModel(replace(base, **sampled))
        except ValueError as exc:
            assert "absolute initial density margin" in str(exc)
            assert not screened
            rejected += 1
            continue
        assert screened
        assert (
            model.config.amoc_minimum_initial_density_ratio
            <= model.baseline_density_driver_ratio
            <= model.config.amoc_maximum_initial_density_ratio
        )
        accepted += 1
    assert accepted > 0

    # The exact screen and the worker constructor must reject the same clearly
    # non-physical hydrography. A particular finite quasi-random sample is not
    # required to contain both accepted and rejected members.
    invalid = {
        "initial_north_salinity_psu": 34.70,
        "initial_southern_salinity_psu": 34.70,
    }
    assert not _joint_prior_state_is_physical(invalid, base)
    try:
        ProcessClimateModel(replace(base, **invalid))
    except ValueError as exc:
        assert "absolute initial density margin" in str(exc)
    else:
        raise AssertionError("Exact prior screen and worker initialization diverged")


def test_reversal_is_explicit_opt_in() -> None:
    common = dict(
        scenario="constant",
        duration_years=250.0,
        freshwater_hosing_sv=0.50,
        freshwater_start_fraction=0.0,
        freshwater_ramp_years=20.0,
        warming_freshwater_sv_per_k=0.0,
    )
    default = ProcessClimateModel(ModelConfig(**common)).run().dataframe
    exploratory = ProcessClimateModel(
        ModelConfig(**common, amoc_allow_reversal=True)
    ).run().dataframe
    assert float(default["amoc_sv"].min()) >= 0.0
    assert float(default["amoc_sv"].iloc[-1]) < 0.1
    assert float(exploratory["amoc_sv"].iloc[-1]) < 0.0


def test_joint_amoc_calibration_targets() -> None:
    diagnostics = _amoc_response_diagnostics(ModelConfig())
    # v2.29.9 restores the pre-v2.29.7 high-forcing compatibility ceiling.
    assert 25.0 <= diagnostics["ssp585_amoc_decline_2100_percent"] <= 55.0
    assert 10.0 <= diagnostics["hosing_0p1_amoc_decline_40yr_percent"] <= 40.0


def test_long_term_ssp245_structural_branch() -> None:
    frame = ProcessClimateModel(
        ModelConfig(scenario="ssp245", duration_years=650.0, record_every_years=10.0)
    ).run().dataframe
    value_2100 = float(
        frame.iloc[int(np.argmin(np.abs(frame["year"].to_numpy() - 2100.0)))][
            "amoc_sv"
        ]
    )
    # v2.29.9 restores the single-year 2100 floor while retaining explicit
    # multi-century recovery, Greenland capacity and salt closure below.
    assert 10.0 < value_2100 < 14.0
    minimum = float(frame["amoc_sv"].min())
    final = float(frame["amoc_sv"].iloc[-1])
    assert minimum > 6.0
    assert final > minimum + 0.5
    assert final > 12.0
    assert float(frame["greenland_remaining_fraction"].iloc[-1]) > 0.90
    assert float(frame["salt_conservation_error_ppm"].abs().max()) < 1.0e-5


def main() -> None:
    tests = {
        test.__name__: test
        for test in (
            test_finite_greenland_reservoir,
            test_absolute_density_margin_screening,
            test_reversal_is_explicit_opt_in,
            test_joint_amoc_calibration_targets,
            test_long_term_ssp245_structural_branch,
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
            timeout=1200,
        )
    print("All v2.17.0 structural-fix tests passed.", flush=True)


if __name__ == "__main__":
    main()
    os._exit(0)
