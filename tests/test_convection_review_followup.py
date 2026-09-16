"""Behavioral checks for explicit convection experiments and honest SSP reporting."""
import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import climate_model as cm
import climate_model_gui as gui
import monte_carlo as mc
from tools import verify_physics_revision as verify


@pytest.mark.parametrize("exponent", [0.0, 1.0, 1.25])
def test_desktop_roundtrip_preserves_selected_convection_experiment(exponent):
    values = {**gui.DEFAULTS, "amoc_convection_transport_exponent": str(exponent)}
    command = gui.build_cli_command(values)
    config = cm.config_from_args(cm.build_parser().parse_args(command[2:]))
    assert config.amoc_convection_transport_exponent == exponent


def test_science_ensemble_does_not_silently_activate_transport_experiment():
    field = "amoc_convection_transport_exponent"
    config = cm.ModelConfig()
    assert config.amoc_convection_transport_exponent == 0.0
    assert field not in mc.science_default_ranges("ar6_amoc", config)
    assert field not in mc.PHYSICAL_AMOC_PRIORS
    assert mc.parse_ranges([[field, "0", "1"]], config, "none", False)[field] == (0, 1)
    assert not gui.DEFAULTS["mc_conv_transport_enabled"]


@pytest.mark.parametrize("exponent", [float("nan"), float("inf"), -1.0])
def test_transport_experiment_rejects_invalid_exponents(exponent):
    with pytest.raises(ValueError, match="transport_exponent"):
        cm.ModelConfig(amoc_convection_transport_exponent=exponent).validate()


def test_convection_anomaly_uses_solved_control_hydrography():
    config = cm.ModelConfig(
        resolution_deg=10.0,
        auto_initialize_from_1850=False,
        seasonal_arctic_enabled=False,
        duration_years=0.1,
        amoc_control_salinity_mode="freshwater_budget",
        amoc_enforce_initial_density_constraint=False,
        initial_north_salinity_psu=35.2,
        initial_deep_salinity_psu=34.8,
    )
    model = cm.ProcessClimateModel(config)
    solved_contrast = (
        model.state.north_salinity_psu - model.state.deep_salinity_psu
    )
    configured_contrast = (
        config.initial_north_salinity_psu - config.initial_deep_salinity_psu
    )
    assert solved_contrast != pytest.approx(configured_contrast)
    diagnostics = model._amoc_diagnostics(model.state)
    assert diagnostics["amoc_convection_density_anomaly"] == pytest.approx(
        0.0, abs=1.0e-14
    )
    assert diagnostics["amoc_convection_target"] == pytest.approx(1.0)


def ssp_frame(decline=5.0):
    years = np.arange(1850, 2101, dtype=float)
    return pd.DataFrame({
        "year": years,
        "amoc_sv": np.where(years < 2081, 17.0, 17.0 * (1.0 - decline / 100)),
        "fovs_sv": -0.16,
        "amoc_convection_efficiency": 1.0,
        "amoc_forced_heat_capacity_sv": 14.0,
        "amoc_hydraulic_target_sv": 16.0,
        "amoc_transport_target_sv": 14.0,
        "amoc_forced_heat_constraint_active": 1.0,
        "pre_projection_salt_conservation_error_ppm": 0.0,
    })


@pytest.mark.parametrize("decline,passes", [(5, False), (20, True), (51, False)])
def test_ssp_gate_reports_response_independently_of_conservation(decline, passes):
    result = verify.ssp245_metrics(ssp_frame(decline))
    assert result["amoc_decline_percent"] == pytest.approx(decline)
    assert result["numerical_checks_passed"]
    assert result["development_response_gate_passed"] is passes


@pytest.mark.parametrize("corruption", ["missing_year", "duplicate_year", "nan"])
def test_ssp_gate_rejects_incomplete_or_nonfinite_evidence(corruption):
    frame = ssp_frame()
    if corruption == "missing_year":
        frame = frame[frame.year != 1999]
    elif corruption == "duplicate_year":
        frame = pd.concat([frame, frame[frame.year == 1999]])
    else:
        frame.loc[frame.year == 2100, "amoc_sv"] = np.nan
    with pytest.raises(ValueError):
        verify.ssp245_metrics(frame)


def test_ssp_failure_is_saved_for_both_resolutions(tmp_path, monkeypatch):
    monkeypatch.setattr(verify, "snapshot_sources", lambda output: {})
    monkeypatch.setattr(verify.cm, "ProcessClimateModel", lambda config:
                        SimpleNamespace(run=lambda: SimpleNamespace(dataframe=ssp_frame())))
    results = verify.ssp245_probe(tmp_path)
    saved = json.loads((tmp_path / "ssp245_results.json").read_text())
    assert saved == results
    assert results["completed"] and not results["passed"]
    assert not results["independent_validation_passed"]
    assert set(results["resolutions"]) == {"5deg", "10deg"}


def test_failed_ssp_rerun_cannot_leave_a_stale_pass(tmp_path, monkeypatch):
    path = tmp_path / "ssp245_results.json"
    path.write_text(json.dumps({"completed": True, "passed": True}))
    monkeypatch.setattr(verify, "snapshot_sources", lambda output: {})

    def failed_model(config):
        raise ValueError("integration setup failed")

    monkeypatch.setattr(verify.cm, "ProcessClimateModel", failed_model)
    with pytest.raises(ValueError, match="integration setup failed"):
        verify.ssp245_probe(tmp_path)
    saved = json.loads(path.read_text())
    assert saved["completed"] is False
    assert saved["passed"] is False


def test_desktop_explicit_monte_carlo_range_reaches_sampler():
    field = "amoc_convection_transport_exponent"
    values = {**gui.DEFAULTS, "monte_carlo_enabled": True,
              "mc_use_science_defaults": False, "mc_conv_transport_enabled": True,
              "mc_conv_transport_min": "0", "mc_conv_transport_max": "1"}
    command = gui.build_cli_command(values)
    index = command.index(field)
    assert command[index - 1:index + 3] == ["--mc-range", field, "0", "1"]
