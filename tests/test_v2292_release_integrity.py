"""Regression tests for the v2.29.2 release-integrity maintenance pass."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from climate_model import MODEL_VERSION, ModelConfig, ProcessClimateModel
from climate_model_gui import DEFAULTS, validate_values
from monte_carlo import compute_importance_weights


ROOT = Path(__file__).resolve().parents[1]


def _reference_stress_config(**changes) -> ModelConfig:
    base = ModelConfig(
        duration_years=1.0,
        resolution_deg=10.0,
        arctic_basal_ocean_exchange_wm2_k=0.25,
        arctic_open_water_ocean_exchange_wm2_k=0.05,
        arctic_atlantic_reference_ocean_temperature_c=-1.8,
        arctic_non_atlantic_reference_ocean_temperature_c=-1.8,
        arctic_reference_ocean_heat_capacity_wyr_m2_k=20.0,
        arctic_reference_ocean_restoring_wm2_k=2.0,
        arctic_open_water_stable_exchange_wm2_k=3.0,
        arctic_open_water_unstable_exchange_wm2_k=3.0,
        arctic_lateral_ocean_heat_transport_wm2_per_ice_fraction=2.0,
    )
    return replace(base, **changes)


def test_version_and_complete_runner_configuration() -> None:
    assert MODEL_VERSION == "2.29.29"
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    runner = (ROOT / "run_tests.py").read_text(encoding="utf-8")
    plugin = (ROOT / "isolated_pytest_exit.py").read_text(encoding="utf-8")
    assert 'version = "2.29.29"' in pyproject
    assert "not slow" not in pyproject
    assert '"isolated_pytest_exit"' not in runner
    assert "os._exit" not in plugin
    assert "complete inventory" in runner


def test_reference_cycle_adapts_beyond_minimum_and_enforces_closure() -> None:
    model = ProcessClimateModel(_reference_stress_config())
    tolerance = model.config.arctic_reference_convergence_tolerance_wyr_m2
    assert model.arctic_reference_spinup_years_completed > 80
    assert model.arctic_reference_spinup_years_completed <= 320
    assert model.arctic_reference_periodic_closure_wyr_m2 <= tolerance
    assert model.arctic_reference_spinup_convergence_wyr_m2 <= tolerance


def test_reference_cycle_fails_if_hard_maximum_is_too_short() -> None:
    with pytest.raises(ValueError, match="failed to converge"):
        ProcessClimateModel(
            _reference_stress_config(arctic_reference_max_spinup_years=80)
        )


def test_disabled_seasonal_arctic_skips_reference_spinup() -> None:
    model = ProcessClimateModel(
        ModelConfig(duration_years=1.0, seasonal_arctic_enabled=False)
    )
    assert model.arctic_reference_spinup_years_completed == 0
    assert model.arctic_reference_periodic_closure_wyr_m2 == 0.0
    result = model.run()
    assert result.summary()["arctic_reference_spinup_years_completed"] == 0


def test_salt_projection_reports_roundoff_and_rejects_structural_leak() -> None:
    model = ProcessClimateModel(ModelConfig(duration_years=2.0))
    result = model.run()
    summary = result.summary()
    assert (
        summary["maximum_pre_projection_salt_conservation_error_ppm"]
        <= model.config.salt_projection_max_residual_ppm
    )
    assert summary["cumulative_absolute_salt_projection_correction_ppm"] >= 0.0

    leaked = model._salinity_array(model.state)
    leaked[0] += 0.001
    with pytest.raises(FloatingPointError, match="Pre-projection salt residual"):
        model._project_salinity_to_conserved_total(leaked)


def test_monte_carlo_safety_filters_apply_in_none_mode() -> None:
    summary = ProcessClimateModel(ModelConfig(duration_years=1.0)).run().summary()
    invalid = dict(summary)
    invalid["maximum_arctic_open_water_temperature_c"] = 5000.0
    weights, logweights, reasons, targets = compute_importance_weights(
        [{"summary": summary}, {"summary": invalid}], "none"
    )
    assert targets == []
    assert np.allclose(weights, [1.0, 0.0])
    assert np.isfinite(logweights[0]) and not np.isfinite(logweights[1])
    assert reasons[0] == ""
    assert "temperature" in reasons[1]


def test_phase_restoring_flux_is_signed_and_deficit_bounded() -> None:
    model = ProcessClimateModel(ModelConfig(duration_years=1.0))
    reference = np.full_like(model.grid.lat, 0.5)
    darkness = np.ones_like(reference)
    excess = model._arctic_phase_restoring_flux_wm2(
        reference + 0.1, reference, darkness
    )
    deficit = model._arctic_phase_restoring_flux_wm2(
        reference - 0.1, reference, darkness
    )
    large_deficit = model._arctic_phase_restoring_flux_wm2(
        reference - 0.4, reference, darkness
    )
    active = model.arctic_module_blend > 0.0
    assert np.all(excess[active] > 0.0)
    assert np.all(deficit[active] < 0.0)
    assert np.all(np.abs(deficit[active]) < np.abs(excess[active]))
    assert np.all(np.abs(large_deficit[active]) <= 2.5 * model.arctic_module_blend[active] + 1.0e-12)


def test_summary_uses_configured_full_arctic_latitude() -> None:
    config = ModelConfig(
        duration_years=1.0,
        resolution_deg=5.0,
        arctic_module_full_latitude_deg=70.0,
    )
    result = ProcessClimateModel(config).run()
    between = (result.grid.lat >= 66.0) & (result.grid.lat < 70.0)
    assert np.any(between)
    result.arctic_atlantic_open_water_temperature_history_c[:, between] = 999.0
    result.arctic_non_atlantic_open_water_temperature_history_c[:, between] = 999.0
    result.atlantic_sea_ice_history[:, between] = 0.0
    result.non_atlantic_sea_ice_history[:, between] = 0.0
    assert result.summary()["maximum_arctic_open_water_temperature_c"] < 999.0


def test_gui_rejects_invalid_stability_exchange_pair() -> None:
    values = dict(DEFAULTS)
    values["arctic_open_water_stable_exchange"] = "3.0"
    values["arctic_open_water_unstable_exchange"] = "0.5"
    with pytest.raises(ValueError, match="Unstable open-water exchange"):
        validate_values(values)


def test_streamlit_arctic_defaults_are_canonical_and_cross_validated() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "DEFAULT_MODEL_CONFIG.arctic_open_water_stable_exchange_wm2_k" in source
    assert "min_value=max(float(arctic_open_water_stable_exchange), 1.0)" in source
    assert "DEFAULT_MODEL_CONFIG.arctic_reference_ocean_heat_capacity_wyr_m2_k" in source
    assert "DEFAULT_MODEL_CONFIG.arctic_reference_ocean_restoring_wm2_k" in source


def test_streamlit_direct_modelconfig_defaults_are_canonical() -> None:
    import ast

    source = (ROOT / "app.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    variable_to_field: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        if not isinstance(node.targets[0], ast.Name) or node.targets[0].id != "config":
            continue
        call = node.value
        if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name):
            continue
        if call.func.id != "ModelConfig":
            continue
        for keyword in call.keywords:
            value = keyword.value
            if keyword.arg is None:
                continue
            if (
                isinstance(value, ast.Call)
                and isinstance(value.func, ast.Name)
                and value.func.id in {"float", "int", "bool"}
                and len(value.args) == 1
                and isinstance(value.args[0], ast.Name)
            ):
                variable_to_field[value.args[0].id] = keyword.arg

    checked: set[str] = set()
    noncanonical: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        call = node.value
        if (
            not isinstance(target, ast.Name)
            or target.id not in variable_to_field
            or not isinstance(call, ast.Call)
            or not isinstance(call.func, ast.Attribute)
            or not isinstance(call.func.value, ast.Name)
            or call.func.value.id != "st"
            or call.func.attr not in {"slider", "number_input", "checkbox"}
        ):
            continue
        default = None
        for keyword in call.keywords:
            if keyword.arg == "value":
                default = keyword.value
                break
        if default is None and call.func.attr in {"slider", "number_input"} and len(call.args) >= 4:
            default = call.args[3]
        if default is None:
            continue
        field = variable_to_field[target.id]
        checked.add(field)
        canonical = any(
            isinstance(item, ast.Attribute)
            and isinstance(item.value, ast.Name)
            and item.value.id == "DEFAULT_MODEL_CONFIG"
            and item.attr == field
            for item in ast.walk(default)
        )
        if not canonical:
            noncanonical.append(f"{target.id}->{field}")
    assert len(checked) >= 70
    assert noncanonical == []
