"""Focused regressions for the v2.29.9 independent scientific-review fixes."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from climate_model import MODEL_VERSION, ModelConfig, ProcessClimateModel
from monte_carlo import PHYSICAL_CLIMATE_PRIORS, _inverse_physical_prior
from sea_ice_validation import (
    MARCH_TREND_PERIODS,
    _five_year_forced_signal_metric,
    march_area_trend_robustness,
)

ROOT = Path(__file__).resolve().parents[1]


def test_version_and_reviewed_defaults() -> None:
    cfg = ModelConfig()
    assert MODEL_VERSION == "2.29.28"
    assert cfg.arctic_full_cover_equivalent_thickness_m == 3.7
    assert cfg.arctic_ice_concentration_exponent == 1.0
    assert cfg.arctic_lateral_ocean_heat_transport_wm2_per_ice_fraction == 25.0
    assert cfg.arctic_transient_shortwave_scale == 1.0
    assert cfg.arctic_lapse_rate_feedback_wm2_k == 1.1
    assert cfg.arctic_basal_ocean_exchange_wm2_k == 6.0
    assert cfg.arctic_open_water_ocean_exchange_wm2_k == 25.0
    assert cfg.amoc_stratification_saturation_c == 0.6
    assert cfg.amoc_convection_recovery_years == 80.0
    assert cfg.arctic_greenland_marine_influence == 0.1


def test_conservative_compactness_curve_preserves_volume() -> None:
    model = ProcessClimateModel(replace(ModelConfig(), duration_years=0.1, auto_initialize_from_1850=False))
    equivalent = np.linspace(0.0, 4.0, 17)
    energy = -equivalent * model.arctic_latent_energy_per_m_wyr_m2
    concentration, diagnosed_equivalent, local = model._arctic_ice_energy_to_state(energy)
    assert np.all(np.diff(concentration) >= -1.0e-14)
    assert concentration[0] == 0.0
    assert concentration[-1] == pytest.approx(1.0)
    assert np.allclose(diagnosed_equivalent, equivalent, rtol=0.0, atol=1.0e-12)
    assert np.allclose(concentration * local, diagnosed_equivalent, rtol=0.0, atol=1.0e-12)


def test_zero_lateral_restoring_is_valid_and_negative_is_rejected() -> None:
    ProcessClimateModel(replace(
        ModelConfig(),
        duration_years=0.1,
        auto_initialize_from_1850=False,
        arctic_lateral_ocean_heat_transport_wm2_per_ice_fraction=0.0,
    ))
    with pytest.raises(ValueError, match="cannot be negative"):
        ModelConfig(
            arctic_lateral_ocean_heat_transport_wm2_per_ice_fraction=-0.1
        ).validate()


def test_lateral_restoring_prior_has_twenty_percent_zero_branch() -> None:
    spec = PHYSICAL_CLIMATE_PRIORS[
        "arctic_lateral_ocean_heat_transport_wm2_per_ice_fraction"
    ]
    assert spec.point_mass_at_zero == pytest.approx(0.20)
    assert _inverse_physical_prior(0.01, spec) == 0.0
    assert _inverse_physical_prior(0.20, spec) == 0.0
    assert 2.0 <= _inverse_physical_prior(0.200001, spec) <= 40.0
    assert 2.0 <= _inverse_physical_prior(0.99, spec) <= 40.0


def test_public_ranges_cover_documented_prior_support() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "0.0, 1.8" in source
    assert "0.5, 5.0" in source
    assert "0.0, 40.0" in source
    gui = (ROOT / "climate_model_gui.py").read_text(encoding="utf-8")
    assert '"10", "300", "years"' in gui


def test_historical_scores_are_explicitly_non_predictive() -> None:
    evidence = (ROOT / "scientific_evidence.py").read_text(encoding="utf-8")
    assert "descriptive only and non-release-blocking" in evidence
    assert "reserved from 2027 onward" in evidence
    assert "sensitivity output" in evidence
    assert "precise regional climate forecasts" in evidence


def _synthetic_records() -> pd.DataFrame:
    rows = []
    for month in (3, 9):
        for year in range(1979, 2026):
            observed = 15.0 - (0.04 if month == 3 else 0.45) * (year - 1979) / 10.0
            model = 15.0 - (0.12 if month == 3 else 0.35) * (year - 1979) / 10.0
            rows.append({
                "year": year,
                "month": month,
                "model_area": model,
                "observed_area": observed,
                "model_extent": model * 1.1,
                "observed_extent": observed * 1.1,
            })
    return pd.DataFrame(rows)


def test_march_trend_diagnostic_uses_predeclared_periods_and_uncertainty() -> None:
    result = march_area_trend_robustness(_synthetic_records())
    assert result["predeclared_periods"] == [list(value) for value in MARCH_TREND_PERIODS]
    assert len(result["period_results"]) == len(MARCH_TREND_PERIODS)
    first = result["period_results"][0]
    assert "ols_standard_error_million_km2_per_decade" in first["model"]
    assert "theil_sen_trend_million_km2_per_decade" in first["model"]
    assert "trend_magnitude_ratio" in first
    assert result["independent_predictive_validation"] is False


def test_five_year_blocks_do_not_overlap() -> None:
    result = _five_year_forced_signal_metric(
        _synthetic_records(), month=3, quantity="area", minimum_training_years=15, window_years=5
    )
    assert result["blocks_are_nonoverlapping"] is True
    records = result["records"]
    for previous, current in zip(records, records[1:]):
        assert current["start_year"] > previous["end_year"]
    assert "not predictive validation" in result["interpretation"]


def test_native_amoc_reference_converges_without_canonical_substitution() -> None:
    ratios = []
    north_temperatures = []
    for resolution in (2.5, 5.0, 10.0):
        model = ProcessClimateModel(replace(
            ModelConfig(),
            resolution_deg=resolution,
            duration_years=0.1,
            auto_initialize_from_1850=False,
        ))
        assert model.amoc_reference_mode == "native_grid_fractional_box_means"
        ratios.append(float(model.baseline_density_driver_ratio))
        north_temperatures.append(float(model.baseline_amoc_north_c))
    assert max(ratios) - min(ratios) <= 0.20
    assert max(north_temperatures) - min(north_temperatures) > 1.0e-6
