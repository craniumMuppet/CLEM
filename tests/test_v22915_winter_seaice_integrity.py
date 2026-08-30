from __future__ import annotations

from dataclasses import replace
import importlib.util
from pathlib import Path

import numpy as np
import pytest

from climate_model import (
    ARCTIC_MINIMUM_LOCAL_ICE_THICKNESS_M,
    MODEL_VERSION,
    ModelConfig,
    ProcessClimateModel,
)


def _minimal_arctic_model(config: ModelConfig | None = None) -> ProcessClimateModel:
    model = ProcessClimateModel.__new__(ProcessClimateModel)
    model.config = config or ModelConfig()
    model.arctic_latent_energy_per_m_wyr_m2 = 1.0
    return model


def test_v22915_version() -> None:
    assert MODEL_VERSION == "2.29.28"


def test_winter_lead_closure_tapers_smoothly_at_vanishing_volume() -> None:
    model = _minimal_arctic_model()
    equivalent = np.array([0.0, 1.0e-12, 1.0e-9, 1.0e-6, 1.0e-4, 1.0e-3])
    concentration, diagnosed, local = model._arctic_ice_energy_to_state(
        -equivalent,
        reference_ice_fraction=np.full(equivalent.shape, 0.99),
        lead_closure_weight=np.full(equivalent.shape, 0.65),
    )

    np.testing.assert_allclose(diagnosed, equivalent, rtol=0.0, atol=0.0)
    np.testing.assert_allclose(concentration * local, equivalent, rtol=0.0, atol=1.0e-18)
    assert concentration[0] == 0.0
    assert concentration[2] < 1.0e-6
    assert concentration[2] < concentration[3] < concentration[4] < concentration[5]
    assert np.all(local[1:] >= ARCTIC_MINIMUM_LOCAL_ICE_THICKNESS_M)
    assert np.all(
        concentration
        <= np.clip(
            equivalent / ARCTIC_MINIMUM_LOCAL_ICE_THICKNESS_M,
            0.0,
            1.0,
        )
        + 1.0e-15
    )

    upper_prior_concentration, upper_prior_equivalent, upper_prior_local = (
        model._arctic_ice_energy_to_state(
            -equivalent,
            reference_ice_fraction=np.full(equivalent.shape, 0.99),
            lead_closure_weight=np.full(equivalent.shape, 0.90),
        )
    )
    assert upper_prior_concentration[2] < 1.0e-6
    np.testing.assert_allclose(
        upper_prior_concentration * upper_prior_local,
        upper_prior_equivalent,
        rtol=0.0,
        atol=1.0e-18,
    )


def test_winter_lead_closure_uses_actual_transient_temperature() -> None:
    model = _minimal_arctic_model(
        ModelConfig(
            arctic_winter_lead_closure_fraction=0.65,
            arctic_winter_lead_closure_temperature_scale_c=15.0,
        )
    )
    reference_temperature = np.full(5, -17.0)
    actual_temperature = np.array([-17.0, -10.0, -4.0, 0.0, 5.0])
    weight = model._arctic_winter_lead_closure_weight(
        reference_temperature, actual_temperature
    )

    assert weight[0] == pytest.approx(0.65)
    assert weight[1] == pytest.approx(0.65)
    assert np.all(np.diff(weight) <= 0.0)
    assert 0.0 < weight[2] < weight[1]
    assert weight[3] == 0.0
    assert weight[4] == 0.0


def test_saved_winter_fields_match_integrated_closure_state() -> None:
    cfg = replace(
        ModelConfig(),
        start_year=1850.0,
        duration_years=1.0,
        dt_years=0.05,
        record_every_years=0.25,
        resolution_deg=10.0,
        scenario="ssp245",
        auto_initialize_from_1850=False,
    )
    model = ProcessClimateModel(cfg)
    result = model.run()
    reference = model._arctic_reference_state(cfg.duration_years)
    active = model.grid.lat >= cfg.arctic_module_full_latitude_deg

    sectors = (
        (
            "atlantic",
            model.state.arctic_atlantic_ice_energy_anomaly_wyr_m2,
            model.state.arctic_atlantic_open_water_heat_anomaly_wyr_m2,
            model.state.arctic_atlantic_air_anomaly_c,
            model.state.arctic_atlantic_seasonal_ice_fraction,
            result.atlantic_sea_ice_history[-1],
            result.arctic_atlantic_local_ice_thickness_history_m[-1],
            result.arctic_atlantic_open_water_temperature_history_c[-1],
        ),
        (
            "non_atlantic",
            model.state.arctic_non_atlantic_ice_energy_anomaly_wyr_m2,
            model.state.arctic_non_atlantic_open_water_heat_anomaly_wyr_m2,
            model.state.arctic_non_atlantic_air_anomaly_c,
            model.state.arctic_non_atlantic_seasonal_ice_fraction,
            result.non_atlantic_sea_ice_history[-1],
            result.arctic_non_atlantic_local_ice_thickness_history_m[-1],
            result.arctic_non_atlantic_open_water_temperature_history_c[-1],
        ),
    )

    for (
        prefix,
        ice_anomaly,
        open_anomaly,
        air_anomaly,
        state_concentration,
        saved_effective_concentration,
        saved_local_thickness,
        saved_open_temperature,
    ) in sectors:
        total_ice = reference[f"{prefix}_ice_energy_wyr_m2"] + ice_anomaly
        total_open = reference[f"{prefix}_open_water_heat_wyr_m2"] + open_anomaly
        reconstructed_concentration, equivalent, reconstructed_local = (
            model._arctic_state_from_energy_and_concentration(
                total_ice,
                state_concentration,
            )
        )
        reconstructed_open = model._arctic_open_water_temperature(
            total_open, 1.0 - reconstructed_concentration
        )

        np.testing.assert_allclose(
            state_concentration,
            reconstructed_concentration,
            rtol=0.0,
            atol=2.0e-12,
        )
        np.testing.assert_allclose(
            saved_local_thickness,
            reconstructed_local,
            rtol=0.0,
            atol=2.0e-12,
        )
        np.testing.assert_allclose(
            saved_open_temperature,
            reconstructed_open,
            rtol=0.0,
            atol=2.0e-12,
        )
        np.testing.assert_allclose(
            saved_effective_concentration[active] * saved_local_thickness[active],
            equivalent[active],
            rtol=0.0,
            atol=2.0e-12,
        )



def test_v22915_packager_excludes_transient_work_files() -> None:
    root = Path(__file__).resolve().parents[1]
    package_path = root / "tools" / "package_v22915.py"
    spec = importlib.util.spec_from_file_location("package_v22915_test", package_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    transient_names = {
        "validation_v22915_runner.pid",
        "validation_v22915_runner.log",
        "v22915_fast_tests.log",
        "v22915_fast_tests.pid",
        "v22915_fast_tests.exit",
        "v22915_validation.log",
        "v22915_validation.pid",
        "v22915_validation.exit",
        "v22915_review_reproduction.log",
        "v22915_review_reproduction.pid",
        "v22915_review_reproduction.exit",
        "v22915_legacy_tests.log",
        "v22915_legacy_tests.pid",
        "v22915_legacy_tests.exit",
    }
    assert transient_names.issubset(module.EXCLUDED_FILE_NAMES)
    packaged_names = {path.relative_to(root).as_posix() for path in module.release_files()}
    assert not transient_names.intersection(packaged_names)
