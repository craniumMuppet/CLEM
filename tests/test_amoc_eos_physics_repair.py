from __future__ import annotations

from pathlib import Path

import pytest

from climate_model import (
    ModelConfig,
    ProcessClimateModel,
    build_parser,
    config_from_args,
)


ROOT = Path(__file__).resolve().parents[1]


def test_production_teos10_normalizes_the_unchanged_control_state() -> None:
    config = ModelConfig(
        resolution_deg=10.0,
        duration_years=0.1,
        auto_initialize_from_1850=False,
        seasonal_arctic_enabled=False,
    )
    assert config.amoc_density_eos == "teos10_matched"
    assert config.amoc_reference_sv == pytest.approx(17.0)
    assert config.amoc_density_transport_exponent == pytest.approx(1.5)
    assert config.amoc_hydraulic_depth_exponent == pytest.approx(1.0)
    assert config.amoc_pycnocline_feedback_strength == pytest.approx(0.35)

    model = ProcessClimateModel(config)
    diagnostics = model._amoc_diagnostics(model.state)
    assert model.state.amoc_sv == pytest.approx(17.0, abs=1e-12)
    assert diagnostics["amoc_density_driver_ratio"] == pytest.approx(1.0, abs=1e-12)
    assert diagnostics["amoc_hydraulic_target_sv"] == pytest.approx(17.0, abs=1e-12)


def test_teos10_is_a_declared_runtime_dependency() -> None:
    assert "gsw>=3.6.23" in (ROOT / "requirements.in").read_text(encoding="utf-8")
    assert "gsw==3.6.23" in (ROOT / "requirements.lock").read_text(encoding="utf-8")
    assert '"gsw==3.6.23"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_linear_eos_remains_an_explicit_structural_sensitivity() -> None:
    config = ModelConfig(amoc_density_eos="linear")
    assert config.amoc_density_eos == "linear"
    assert config.amoc_reference_sv == pytest.approx(17.0)


def test_cli_inherits_the_production_teos10_default() -> None:
    config = config_from_args(build_parser().parse_args([]))
    assert config.amoc_density_eos == "teos10_matched"
    assert config.amoc_reference_sv == pytest.approx(17.0)
