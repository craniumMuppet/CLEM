#!/usr/bin/env python3
"""Small end-to-end tests for exploratory and constrained ensembles."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pandas as pd
import numpy as np

from climate_model import ModelConfig
from monte_carlo import (
    compute_importance_weights,
    generate_samples,
    parse_ranges,
    resolve_random_seed,
    run_monte_carlo,
    science_default_ranges,
    weighted_quantile,
)



def test_seed_resolution() -> None:
    fixed, source = resolve_random_seed(12345)
    assert fixed == 12345
    assert source == "user"

    generated, source = resolve_random_seed(0)
    assert 1 <= generated < 2**32
    assert source == "system_clock"

    try:
        resolve_random_seed(-1)
    except ValueError:
        pass
    else:
        raise AssertionError("Negative seeds must be rejected.")


def test_freshwater_adjustors() -> None:
    config = ModelConfig()
    ranges = parse_ranges(
        [
            ["hydrological_freshwater", "0.003", "0.010"],
            ["hydrological_north_fraction", "0.50", "0.90"],
            ["greenland_freshwater", "0.002", "0.010"],
            ["greenland_response_years", "30", "150"],
        ],
        config,
        "none",
        False,
    )
    assert ranges == {
        "hydrological_freshwater_sv_per_k": (0.003, 0.010),
        "hydrological_freshwater_north_fraction": (0.50, 0.90),
        "greenland_freshwater_sv_per_k": (0.002, 0.010),
        "greenland_freshwater_adjustment_years": (30.0, 150.0),
    }
    samples = generate_samples(
        config,
        ranges,
        runs=16,
        seed=21,
        distribution="triangular",
        design="sobol",
        correlated_priors=False,
        science_modes=False,
    )
    for sample in samples:
        assert 0.003 <= sample["hydrological_freshwater_sv_per_k"] <= 0.010
        assert 0.50 <= sample["hydrological_freshwater_north_fraction"] <= 0.90
        assert 0.002 <= sample["greenland_freshwater_sv_per_k"] <= 0.010
        assert 30.0 <= sample["greenland_freshwater_adjustment_years"] <= 150.0


def test_exploratory() -> None:
    config = ModelConfig(
        scenario="constant",
        start_year=1850.0,
        duration_years=3.0,
        dt_years=0.1,
        co2_start_ppm=400.0,
        warming_freshwater_sv_per_k=0.0,
    )
    ranges = {
        "water_vapor_emission_height_km_per_lnq": (0.70, 0.90),
        "ocean_heat_exchange_wm2_k": (0.60, 0.80),
    }
    with tempfile.TemporaryDirectory(prefix="climate_mc_test_") as folder:
        output = Path(folder)
        summary = run_monte_carlo(
            base_config=config,
            ranges=ranges,
            runs=4,
            seed=17,
            distribution="uniform",
            design="latin_hypercube",
            constraint_mode="none",
            correlated_priors=False,
            use_science_priors=False,
            run_calibration_experiments=False,
            workers=1,
            output_dir=output,
            max_plotted=0,
            save_long_csv=False,
            diagnose_each=False,
            create_plots=False,
        )
        assert summary["successful_members"] == 4
        assert summary["failed_members"] == 0
        members = pd.read_csv(output / "monte_carlo_members.csv")
        assert len(members) == 4
        assert members["water_vapor_emission_height_km_per_lnq"].between(0.70, 0.90).all()
        required = [
            "monte_carlo_members.csv",
            "monte_carlo_weighted_percentiles.csv",
            "monte_carlo_timeseries_weighted.npz",
            "monte_carlo_final_map_percentiles.npz",
            "monte_carlo_summary.json",
            "monte_carlo_amoc_counts.json",
            "monte_carlo_amoc_counts.txt",
        ]
        for filename in required:
            assert (output / filename).exists(), filename
        assert not (output / "monte_carlo_global_surface_warming_c_all.png").exists()
        with (output / "monte_carlo_summary.json").open(encoding="utf-8") as handle:
            on_disk = json.load(handle)
        assert on_disk["requested_members"] == 4
        assert on_disk["seed"] == 17
        assert on_disk["seed_requested"] == 17
        assert on_disk["seed_source"] == "user"
        assert on_disk["percentile_bands"] == [1, 5, 17, 50, 83, 95, 99]
        assert on_disk["selected_scenario_only"] is True
        assert on_disk["extra_calibration_experiments"] is False
        assert on_disk["plots_created"] is False
        assert "amoc_completion_counts" in on_disk
        assert on_disk["amoc_completion_counts"]["at_2100"]["available"] is False
        assert on_disk["amoc_completion_counts"]["final_30_year_duration"]["available"] is False
        fields = np.load(output / "monte_carlo_final_map_percentiles.npz")
        for key in [
            "temperature_p50",
            "sea_ice_p50",
            "snow_p50",
            "sea_ice_p99_minus_p01",
            "snow_p99_minus_p01",
        ]:
            assert key in fields.files, key
        assert np.isfinite(fields["sea_ice_p50"]).all()
        assert np.isfinite(fields["snow_p50"]).all()



def test_constrained_utilities() -> None:
    config = ModelConfig()
    ranges = science_default_ranges("ar6_amoc")
    assert "co2_doubling_erf_wm2" in ranges
    assert "amoc_reference_sv" in ranges
    assert "initial_fovs_sv" in ranges
    samples = generate_samples(
        config,
        {
            "initial_fovs_sv": ranges["initial_fovs_sv"],
            "initial_southern_salinity_psu": ranges["initial_southern_salinity_psu"],
            "initial_north_salinity_psu": ranges["initial_north_salinity_psu"],
        },
        runs=8,
        seed=4,
        distribution="triangular",
        design="sobol",
        correlated_priors=True,
        science_modes=True,
    )
    assert all(
        sample["initial_north_salinity_psu"]
        == sample["initial_deep_salinity_psu"]
        for sample in samples
    )
    assert all(-0.60 <= sample["initial_fovs_sv"] <= 0.30 for sample in samples)
    values = pd.Series([1.0, 2.0, 3.0]).to_numpy()
    weights = pd.Series([0.1, 0.2, 0.7]).to_numpy()
    median = float(weighted_quantile(values, weights, [0.5])[0])
    assert 2.0 <= median <= 3.0


def main() -> None:
    test_seed_resolution()
    print("Monte Carlo seed-resolution tests passed.")
    test_constrained_utilities()
    print("Monte Carlo constrained-utility tests passed.")
    test_freshwater_adjustors()
    print("Monte Carlo freshwater-adjustor tests passed.")
    test_exploratory()
    print("Monte Carlo selected-scenario smoke test passed.")


if __name__ == "__main__":
    main()
