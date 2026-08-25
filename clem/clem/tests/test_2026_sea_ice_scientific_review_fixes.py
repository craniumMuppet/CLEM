"""Regression coverage for the 2026 Arctic sea-ice scientific-review fixes."""
from __future__ import annotations

import numpy as np
import pytest

from climate_model import ModelConfig, build_parser, config_from_args
from monte_carlo import FIXED_SCIENCE_PRIOR_PARAMETERS, science_default_ranges
from scientific_evidence import SCIENTIFIC_USE_METADATA
from sea_ice_observation import (
    MINIMUM_EXTENT_CONCENTRATION,
    diagnosed_area_extent_million_km2,
    reconstruct_concentration_and_occupancy,
)
from sea_ice_validation import (
    homogeneous_area_metadata,
    nested_hindcast_requirements,
    physical_observation_metadata,
)


def _synthetic_observation(concentration: np.ndarray):
    concentration = np.asarray(concentration, dtype=float)
    lat = np.array([60.0, 80.0])
    lon = np.array([0.0, 180.0])
    lat2d = np.repeat(lat[:, None], 2, axis=1)
    lon2d = np.repeat(lon[None, :], 2, axis=0)
    ocean = np.ones((2, 2), dtype=float)
    atlantic = np.ones((2, 2), dtype=float)
    # Equal map weights make the exact absolute Earth area irrelevant to the
    # threshold-operator assertions below.
    weights = np.full((2, 2), 0.25, dtype=float)
    return reconstruct_concentration_and_occupancy(
        atlantic_fraction=concentration,
        non_atlantic_fraction=concentration,
        lat=lat,
        lon=lon,
        lat2d=lat2d,
        lon2d=lon2d,
        atlantic_ocean_fraction_map=atlantic,
        ocean_fraction_map=ocean,
        map_area_weights=weights,
        warming_c=3.0,
        calendar_year=2020.7,
    )


def test_raw_area_multiplier_is_not_used_by_default() -> None:
    area, extent = diagnosed_area_extent_million_km2(
        raw_area_million_km2=6.0,
        warming_c=2.0,
        calendar_year=2020.7,
        northern_ocean_area_million_km2=100.0,
    )
    assert area == 6.0
    assert extent == 6.0


def test_extent_is_native_binary_15pct_threshold_without_fit() -> None:
    concentration, occupancy, metrics = _synthetic_observation(
        np.array([0.10, 0.80])
    )
    assert set(np.unique(occupancy)).issubset({0.0, 1.0})
    assert np.all(occupancy[0] == 0.0)
    assert np.all(occupancy[1] == 1.0)
    assert metrics["extent_threshold_concentration"] == MINIMUM_EXTENT_CONCENTRATION
    assert metrics["extent_observation_operator_calibrated"] == 0.0
    assert metrics["extent_contains_observational_fit"] == 0.0
    assert metrics["extent_is_separate_prognostic_state"] == 0.0
    assert metrics["extent_derived_from_native_concentration"] == 1.0
    assert metrics["legacy_extent_multiplier_used"] == 0.0
    assert metrics["northern_hemisphere_sea_ice_thresholded_area_million_km2"] <= metrics[
        "northern_hemisphere_sea_ice_extent_million_km2"
    ]
    assert np.all((concentration >= 0.0) & (concentration <= 1.0))


def test_empirical_pack_resistance_is_disabled_and_forced_heat_response_is_bounded() -> None:
    cfg = ModelConfig()
    assert cfg.arctic_ice_area_thick_pack_resistance_exponent == 0.0
    assert cfg.arctic_forced_ocean_heat_convergence_ice_fraction_exponent == 1.0
    assert cfg.arctic_forced_ocean_heat_convergence_saturation_scale_c > 0.0
    assert "arctic_ice_area_thick_pack_resistance_exponent" in FIXED_SCIENCE_PRIOR_PARAMETERS
    assert "arctic_ice_area_thick_pack_resistance_exponent" not in science_default_ranges(
        "ar6_amoc"
    )


def test_cli_round_trip_preserves_new_heat_geometry_control() -> None:
    args = build_parser().parse_args([])
    cfg = config_from_args(args)
    assert cfg.arctic_forced_ocean_heat_convergence_ice_fraction_exponent == 1.0
    assert cfg.arctic_forced_ocean_heat_convergence_saturation_scale_c == pytest.approx(0.32)


def test_scientific_validation_fails_closed_until_required_data_exist() -> None:
    from arctic_validation_stack import source_status

    fixed = homogeneous_area_metadata()
    physical = physical_observation_metadata()
    assert fixed["available"] is source_status("nsidc_g02202_v6")["available"]
    assert physical["complete"] is True  # PIOMAS + both satellite thickness streams are operator-complete.
    assert "fixed spatial mask" in SCIENTIFIC_USE_METADATA["components"]["sea_ice"][
        "required_area_validation"
    ]
    hindcast = nested_hindcast_requirements()
    assert hindcast["required"] is True
    assert hindcast["model_recalibration_required_inside_each_fold"] is True
    assert hindcast["scientific_predictive_skill_claim_allowed"] is False


def test_nested_hindcast_harness_recalibrates_each_fold_and_rejects_future_data() -> None:
    from sea_ice_nested_hindcast import (
        CalibratedFold,
        CalibrationProvenance,
        HindcastFold,
        configuration_sha256,
        run_nested_hindcasts,
    )

    folds = (HindcastFold(1989, 1990, 1992), HindcastFold(1999, 2000, 2002))
    calls: list[int] = []

    def calibrate(fold: HindcastFold) -> CalibratedFold:
        calls.append(fold.calibrate_through)
        config = {"training_end": fold.calibrate_through}
        return CalibratedFold(
            configuration=config,
            provenance=CalibrationProvenance(
                training_data_max_year=fold.calibrate_through,
                full_model_recalibrated=True,
                calibration_method="synthetic_test",
                calibrated_parameter_count=2,
                objective_description="test objective",
                configuration_sha256=configuration_sha256(config),
            ),
        )

    payload = run_nested_hindcasts(
        calibrate=calibrate,
        simulate=lambda fold, config: {"fold": fold, "config": config},
        score=lambda fold, simulation: {"rmse": 0.0},
        folds=folds,
    )
    assert calls == [1989, 1999]
    assert payload["all_folds_completed"] is True
    assert payload["distinct_configuration_hashes"] == 2
    assert payload["fixed_trajectory_reuse_allowed"] is False

    bad = CalibrationProvenance(
        training_data_max_year=1990,
        full_model_recalibrated=True,
        calibration_method="bad",
        calibrated_parameter_count=1,
        objective_description="bad",
        configuration_sha256="0" * 64,
    )
    import pytest
    with pytest.raises(ValueError, match="after the fold cutoff"):
        bad.validate_for(HindcastFold(1989, 1990, 1992))
