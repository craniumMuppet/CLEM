"""Regression tests for the FAFMIP-informed AMOC heat-response proxy."""

from dataclasses import asdict, replace
import math

import pytest

import climate_model as cm
import climate_model_gui as gui
import co2_target_sweep as sweep
import monte_carlo as mc


def fast_config(**changes: object) -> cm.ModelConfig:
    values: dict[str, object] = {
        "scenario": "step_2x",
        "duration_years": 0.2,
        "dt_years": 0.1,
        "record_every_years": 0.1,
        "resolution_deg": 10.0,
        "seasonal_arctic_enabled": False,
        "auto_initialize_from_1850": False,
    }
    values.update(changes)
    return cm.ModelConfig(**values)


def test_default_forced_heat_proxy_uses_documented_fafmip_values() -> None:
    config = cm.ModelConfig()
    assert config.amoc_forced_heat_response_sv_per_doubling == pytest.approx(5.10)
    assert config.amoc_forced_heat_adjustment_years == pytest.approx(20.0)
    prior = mc.PHYSICAL_AMOC_PRIORS[
        "amoc_forced_heat_response_sv_per_doubling"
    ]
    assert (prior.lower, prior.upper) == pytest.approx((3.27, 8.63))


def test_step_doubling_advances_separate_heat_capacity_exactly() -> None:
    config = fast_config()
    model = cm.ProcessClimateModel(config)
    assert model._amoc_forced_heat_capacity_target_sv(0.0) == pytest.approx(
        config.amoc_reference_sv
        - config.amoc_forced_heat_response_sv_per_doubling
    )

    initial = model.state.amoc_forced_heat_capacity_sv
    model.step(0.0, dt_years=config.dt_years)
    target = (
        config.amoc_reference_sv
        - config.amoc_forced_heat_response_sv_per_doubling
    )
    expected = target + (initial - target) * math.exp(
        -config.dt_years / config.amoc_forced_heat_adjustment_years
    )
    assert model.state.amoc_forced_heat_capacity_sv == pytest.approx(
        expected, abs=1.0e-12
    )
    diagnostics = model._amoc_diagnostics(model.state)
    assert diagnostics["amoc_transport_target_sv"] == pytest.approx(
        min(
            diagnostics["amoc_hydraulic_target_sv"],
            diagnostics["amoc_forced_heat_capacity_sv"],
        )
    )
    explicitly_limited = model.state.copy()
    explicitly_limited.amoc_forced_heat_capacity_sv = 10.0
    limited = model._amoc_diagnostics(explicitly_limited)
    assert limited["amoc_forced_heat_constraint_active"] == 1.0
    assert limited["amoc_transport_target_sv"] == pytest.approx(10.0)


def test_forced_heat_index_respects_public_forcing_mode() -> None:
    config = fast_config(
        forcing_mode="total_effective", additional_forcing_wm2=0.75
    )
    model = cm.ProcessClimateModel(config)
    model.prescribed_forcing_components = lambda elapsed_years: {
        "rcmip_anthropogenic_wm2": 2.5,
        "total_wm2": 1.25,
    }
    assert model._amoc_forced_heat_forcing_wm2(0.0) == pytest.approx(3.25)

    model.config = replace(config, forcing_mode="co2_only")
    assert model._amoc_forced_heat_forcing_wm2(0.0) == pytest.approx(1.25)


def test_zero_response_disables_new_constraint_without_changing_hydraulics() -> None:
    config = fast_config(amoc_forced_heat_response_sv_per_doubling=0.0)
    model = cm.ProcessClimateModel(config)
    model.step(0.0, dt_years=config.dt_years)
    diagnostics = model._amoc_diagnostics(model.state)
    assert model.state.amoc_forced_heat_capacity_sv == pytest.approx(
        config.amoc_reference_sv, abs=1.0e-12
    )
    assert diagnostics["amoc_transport_target_sv"] == pytest.approx(
        diagnostics["amoc_hydraulic_target_sv"], abs=1.0e-12
    )

    # A disabled forced-heat response must also permit hydraulic strengthening
    # above the 17 Sv reference. The original implementation incorrectly left
    # the stored reference capacity as an active upper bound in this branch.
    strengthened = model.state.copy()
    strengthened.pycnocline_depth_m *= 1.3
    strengthened.amoc_forced_heat_capacity_sv = 10.0
    strengthened_diagnostics = model._amoc_diagnostics(strengthened)
    assert strengthened_diagnostics["amoc_hydraulic_target_sv"] > (
        config.amoc_reference_sv
    )
    assert strengthened_diagnostics["amoc_forced_heat_constraint_active"] == 0.0
    assert strengthened_diagnostics["amoc_transport_target_sv"] == pytest.approx(
        strengthened_diagnostics["amoc_hydraulic_target_sv"], abs=1.0e-12
    )


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"amoc_forced_heat_response_sv_per_doubling": -0.1}, "nonnegative"),
        ({"amoc_forced_heat_adjustment_years": 0.0}, "positive"),
    ],
)
def test_forced_heat_parameters_fail_closed(
    changes: dict[str, float], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        cm.ModelConfig(**changes).validate()


def test_old_baseline_checkpoint_gets_deterministic_heat_capacity() -> None:
    model = cm.ProcessClimateModel(fast_config())
    payload = asdict(model.state)
    del payload["amoc_forced_heat_capacity_sv"]
    restored = sweep._state_from_checkpoint(payload)
    assert restored.amoc_forced_heat_capacity_sv == pytest.approx(
        restored.amoc_sv
    )


def test_cli_and_desktop_gui_expose_forced_heat_parameters() -> None:
    values = {
        **gui.DEFAULTS,
        "amoc_forced_heat_response": "6.2",
        "amoc_forced_heat_adjustment_years": "25",
    }
    command = gui.build_cli_command(values)
    response_index = command.index("--amoc-forced-heat-response")
    adjustment_index = command.index("--amoc-forced-heat-adjustment-years")
    assert command[response_index + 1] == "6.2"
    assert command[adjustment_index + 1] == "25"

    parser = cm.build_parser()
    args = parser.parse_args(
        [
            "--amoc-forced-heat-response",
            "6.2",
            "--amoc-forced-heat-adjustment-years",
            "25",
        ]
    )
    config = cm.config_from_args(args)
    assert config.amoc_forced_heat_response_sv_per_doubling == pytest.approx(6.2)
    assert config.amoc_forced_heat_adjustment_years == pytest.approx(25.0)
