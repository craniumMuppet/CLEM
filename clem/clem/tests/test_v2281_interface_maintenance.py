"""Release-blocking interface/default parity tests for v2.29.2."""

from __future__ import annotations

from pathlib import Path

import pytest

from climate_model import MODEL_VERSION, ModelConfig, ProcessClimateModel, config_from_args
from climate_model_gui import DEFAULTS, MC_RANGE_SPECS, build_cli_command
from monte_carlo import SCIENCE_PRIOR_SPECS, build_monte_carlo_parser


AMOC_PUBLIC_DEFAULT_FIELDS = {
    "amoc_density_exponent": "amoc_density_transport_exponent",
    "amoc_convection_density_scale_factor": "amoc_convection_density_scale_factor",
    "amoc_convection_recovery_years": "amoc_convection_recovery_years",
    "amoc_reference_density_driver": "amoc_reference_density_driver",
}


def _as_float(value: object) -> float:
    return float(str(value))


def test_release_version_is_v2292() -> None:
    assert MODEL_VERSION == "2.29.28"


def test_desktop_defaults_match_model_config() -> None:
    config = ModelConfig()
    for gui_key, config_field in AMOC_PUBLIC_DEFAULT_FIELDS.items():
        assert _as_float(DEFAULTS[gui_key]) == pytest.approx(
            float(getattr(config, config_field)), rel=0.0, abs=1.0e-12
        )


def test_desktop_monte_carlo_ranges_contain_validated_defaults() -> None:
    config = ModelConfig()
    specs = {config_field: (float(lower), float(upper)) for _, config_field, _, lower, upper, _ in MC_RANGE_SPECS}
    for field in (
        "ocean_heat_exchange_wm2_k",
        "amoc_convection_density_scale_factor",
        "amoc_convection_recovery_years",
    ):
        lower, upper = specs[field]
        value = float(getattr(config, field))
        assert lower <= value <= upper, (field, lower, value, upper)


def test_desktop_monte_carlo_command_constructs_valid_reference_model(tmp_path: Path) -> None:
    values = dict(DEFAULTS)
    values.update(
        {
            "monte_carlo_enabled": True,
            "mc_runs": "2",
            "mc_seed": "123",
            "mc_workers": "1",
            "mc_no_plots": True,
            "output": str(tmp_path / "mc"),
        }
    )
    command = build_cli_command(values)
    parser = build_monte_carlo_parser()
    args = parser.parse_args(command[2:])
    config = config_from_args(args)
    config.validate()
    model = ProcessClimateModel(config)
    assert model.baseline_density_driver_ratio >= config.amoc_minimum_initial_density_ratio
    assert model.baseline_density_driver_ratio <= config.amoc_maximum_initial_density_ratio


def test_science_priors_contain_and_center_validated_amoc_defaults() -> None:
    config = ModelConfig()
    fields = (
        "amoc_density_transport_exponent",
        "amoc_convection_density_scale_factor",
        "amoc_convection_recovery_years",
        "amoc_reference_density_driver",
    )
    for field in fields:
        prior = SCIENCE_PRIOR_SPECS[field]
        value = float(getattr(config, field))
        assert prior.lower <= value <= prior.upper, (field, prior.lower, value, prior.upper)
        assert prior.mode == pytest.approx(value)


def test_streamlit_uses_canonical_model_defaults_for_amoc_controls() -> None:
    text = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    assert "DEFAULT_MODEL_CONFIG = ModelConfig()" in text
    for field in (
        "amoc_density_transport_exponent",
        "amoc_convection_density_scale_factor",
        "amoc_convection_recovery_years",
        "amoc_reference_density_driver",
    ):
        assert f"DEFAULT_MODEL_CONFIG.{field}" in text
    for stale in ("1.67", "9.7e-4"):
        assert stale not in text


def test_v229_arctic_coupling_defaults_match_cli_and_desktop() -> None:
    config = ModelConfig()
    parser_config = config_from_args(__import__("climate_model").build_parser().parse_args([]))
    pairs = {
        "arctic_basal_ocean_exchange": "arctic_basal_ocean_exchange_wm2_k",
        "arctic_open_water_ocean_exchange": "arctic_open_water_ocean_exchange_wm2_k",
        "arctic_lateral_ocean_heat_transport": "arctic_lateral_ocean_heat_transport_wm2_per_ice_fraction",
        "arctic_reference_ocean_heat_capacity": "arctic_reference_ocean_heat_capacity_wyr_m2_k",
        "arctic_reference_ocean_restoring": "arctic_reference_ocean_restoring_wm2_k",
        "arctic_atlantic_reference_ocean_temperature": "arctic_atlantic_reference_ocean_temperature_c",
        "arctic_non_atlantic_reference_ocean_temperature": "arctic_non_atlantic_reference_ocean_temperature_c",
    }
    for gui_key, field in pairs.items():
        expected = float(getattr(config, field))
        assert float(getattr(parser_config, field)) == pytest.approx(expected)
        assert _as_float(DEFAULTS[gui_key]) == pytest.approx(expected)
        prior = SCIENCE_PRIOR_SPECS[field]
        assert prior.lower <= expected <= prior.upper
