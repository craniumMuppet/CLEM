"""Regression coverage for the v2.24 accuracy remediation."""

from __future__ import annotations

import pandas as pd

from climate_model import MODEL_VERSION, ModelConfig, ProcessClimateModel
from held_out_amoc_validation import historical_external_metrics


def test_v224_default_parameters() -> None:
    config = ModelConfig()
    assert tuple(map(int, MODEL_VERSION.split("."))) >= (2, 24, 0)
    assert config.ocean_heat_exchange_wm2_k == 1.45
    assert config.hydrological_freshwater_sv_per_k == 0.006
    assert config.greenland_freshwater_sv_per_k == 0.005
    assert config.amoc_temperature_density_coupling == 1.0
    assert config.amoc_surface_heat_coupling_fraction == 0.5


def test_historical_gmst_uses_1850_1900_reference() -> None:
    years = list(range(1850, 2101))
    warming = [0.1 if year <= 1900 else 1.2 if 2011 <= year <= 2020 else 0.5 for year in years]
    frame = pd.DataFrame(
        {
            "year": years,
            "global_surface_warming_c": warming,
            "global_near_surface_air_warming_c": warming,
            "arctic_warming_c": [3.0 * value for value in warming],
            "arctic_near_surface_air_warming_c": [3.0 * value for value in warming],
            "ocean_heat_content_anomaly_zj": [float(year - 1850) for year in years],
            "amoc_sv": [17.0 if year <= 2014 else 13.6 for year in years],
        }
    )
    metrics = historical_external_metrics(frame)
    assert abs(metrics["historical_gmst_2011_2020_c"] - 1.1) < 1.0e-12


def test_arctic_air_diagnostic_is_distinct_from_surface_state() -> None:
    config = ModelConfig(
        scenario="ssp245",
        start_year=1850.0,
        duration_years=180.0,
        dt_years=0.2,
        record_every_years=10.0,
        auto_initialize_from_1850=False,
    )
    final = ProcessClimateModel(config).run().dataframe.iloc[-1]
    assert final["arctic_warming_c"] == final["arctic_near_surface_air_warming_c"]
    assert final["arctic_near_surface_air_warming_c"] > final["arctic_blended_surface_state_warming_c"]
