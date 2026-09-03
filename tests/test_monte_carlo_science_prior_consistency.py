"""Regression tests for built-in science-prior/model consistency."""

from __future__ import annotations

from climate_model import ModelConfig
from monte_carlo import (
    PHYSICAL_AMOC_PRIORS,
    PHYSICAL_CLIMATE_PRIORS,
    _joint_prior_state_is_physical,
)


def test_transient_shortwave_prior_stays_within_model_validation_bounds() -> None:
    spec = PHYSICAL_CLIMATE_PRIORS["arctic_transient_shortwave_scale"]
    assert 0.0 <= spec.lower <= spec.upper <= 1.0


def test_hydrographic_prior_mode_is_physical_for_current_amoc_geometry() -> None:
    base = ModelConfig()
    north = PHYSICAL_AMOC_PRIORS["initial_north_salinity_psu"]
    southern = PHYSICAL_AMOC_PRIORS["initial_southern_salinity_psu"]
    fovs = PHYSICAL_AMOC_PRIORS["initial_fovs_sv"]
    sampled = {
        "initial_north_salinity_psu": float(north.mode),
        "initial_deep_salinity_psu": float(north.mode),
        "initial_southern_salinity_psu": float(southern.mode),
        "initial_fovs_sv": 0.5 * (fovs.lower + fovs.upper),
    }

    assert _joint_prior_state_is_physical(sampled, base)
