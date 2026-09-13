"""Behavioral checks for temperature semantics and hydraulic/local EOS isolation."""
from dataclasses import replace
import math
from types import SimpleNamespace

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

import climate_model as cm
import monte_carlo as mc


def test_current_static_physics_checks_evaluate_teos_thermal_sign():
    from verify_physics_local import static_worker
    result = static_worker()
    assert result["control"]["fixed_salinity_thermal_density_contribution"] < 0.0
    failures = [
        f"{group}.{key}" for group, values in result.items()
        for key, value in values.items() if key.startswith("pass_") and value is not True
    ]
    assert failures == []


def test_sensitivity_uses_air_temperature_for_metrics_feedbacks_and_plot(monkeypatch):
    class DiagnosticModel:
        def __init__(self, config):
            self.config = config

        def run(self):
            years = np.arange(0.0, self.config.duration_years + 0.1, 0.5)
            air = (4.0 * (1.0 - np.exp(-years / 10.0))
                   if self.config.scenario == "step_2x" else years / 35.0)
            frame = pd.DataFrame({
                "elapsed_years": years,
                "global_near_surface_air_warming_c": air,
                "global_surface_warming_c": air / 2.0,
                "toa_imbalance_wm2": 4.0 - air,
            })
            for field in ("planck", "lapse_rate", "polar_inversion", "water_vapor",
                          "surface_albedo", "cloud"):
                frame[field + "_flux_wm2"] = -air
            frame["arctic_external_toa_anomaly_wm2"] = 0.25 * air
            return SimpleNamespace(dataframe=frame)

    monkeypatch.setattr(cm, "ProcessClimateModel", DiagnosticModel)
    diagnostics = cm.diagnose_climate_sensitivity(
        cm.ModelConfig(), equilibrium_years=100, maximum_equilibrium_years=100,
    )
    assert diagnostics.equilibrium_converged
    assert diagnostics.equilibrium_ecs_c == pytest.approx(4.0, abs=0.002)
    assert diagnostics.gregory_effective_ecs_c == pytest.approx(4.0)
    assert diagnostics.gregory_restoring_coefficient_wm2_k == pytest.approx(1.0)
    assert diagnostics.tcr_c == pytest.approx(2.0, abs=0.02)
    assert diagnostics.feedbacks_wm2_k["Planck"] == pytest.approx(-1.0)
    assert diagnostics.feedbacks_wm2_k["Arctic module TOA"] == pytest.approx(0.25)
    assert diagnostics.feedbacks_wm2_k["Net feedback"] == pytest.approx(-5.75)
    assert diagnostics.bulk_surface_equilibrium_response_c == pytest.approx(
        diagnostics.equilibrium_ecs_c / 2.0)
    assert diagnostics.bulk_surface_transient_response_c == pytest.approx(diagnostics.tcr_c / 2.0)
    assert diagnostics.summary()["temperature_field"] == "global_near_surface_air_warming_c"
    figure = cm.make_gregory_figure(diagnostics)
    try:
        x = figure.axes[0].collections[0].get_offsets()[:, 0]
        assert x.max() == pytest.approx(4.0, abs=0.002)
        assert "air" in figure.axes[0].get_xlabel()
    finally:
        plt.close(figure)


@pytest.mark.parametrize("eos", ["teos10", "teos10_surface_watermass", "teos10_matched"])
def test_inactive_density_prior_is_removed_and_explicit_sampling_rejected(eos):
    config = cm.ModelConfig(amoc_density_eos=eos)
    name = "amoc_reference_density_driver"
    assert name not in mc.science_default_ranges("ar6_amoc", config)
    assert name not in mc.parse_ranges(None, config, "ar6_amoc", True)
    with pytest.raises(ValueError, match="inactive"):
        mc.parse_ranges([[name, "0.0004", "0.0015"]], config, "none", False)
    with pytest.raises(ValueError, match="inactive"):
        mc.generate_samples(config, {name: (0.0004, 0.0015)}, 2, 42,
                            "uniform", "random", False)


def test_linear_density_prior_remains_available_only_when_it_controls_screening():
    config = cm.ModelConfig(amoc_density_eos="linear", amoc_density_geometry="interhemispheric_high_latitude")
    name = "amoc_reference_density_driver"
    assert name in mc.science_default_ranges("ar6_amoc", config)
    assert name in mc.parse_ranges([[name, "0.0004", "0.0005"]], config, "none", False)
    for inactive in (
        replace(config, amoc_enforce_initial_density_constraint=False),
        replace(config, amoc_density_geometry="south_atlantic_upper"),
    ):
        assert name not in mc.science_default_ranges("ar6_amoc", inactive)


@pytest.mark.parametrize("resolution", [5.0, 10.0])
@pytest.mark.parametrize("perturbation", ["freshening", "stratification"])
def test_hydraulic_eos_does_not_rescale_local_convection(resolution, perturbation):
    config = cm.ModelConfig(
        resolution_deg=resolution, auto_initialize_from_1850=False,
        seasonal_arctic_enabled=False, duration_years=0.1,
    )
    diagnostics = []
    for eos in ("linear", "teos10_matched"):
        model = cm.ProcessClimateModel(replace(config, amoc_density_eos=eos))
        assert model._amoc_diagnostics(model.state)["amoc_convection_target"] == pytest.approx(1.0)
        if perturbation == "freshening":
            model.state.north_salinity_psu -= 0.2
        else:
            model.state.atlantic_ocean_anomaly_c[:] = 1.0
        diagnostics.append(model._amoc_diagnostics(model.state))
    linear, teos = diagnostics
    for key in ("amoc_convection_target", "amoc_convection_density_anomaly",
                "amoc_convection_reference_density_driver"):
        assert teos[key] == pytest.approx(linear[key], abs=1e-12)
    assert teos["amoc_hydraulic_target_sv"] != pytest.approx(linear["amoc_hydraulic_target_sv"])
    if perturbation == "freshening":
        assert teos["amoc_convection_target"] == pytest.approx(
            math.exp(-0.000152 / teos["amoc_convection_reference_density_driver"]))


def test_default_convection_scale_is_independent_of_upper_limb_geometry():
    config = cm.ModelConfig(
        resolution_deg=10.0,
        auto_initialize_from_1850=False,
        seasonal_arctic_enabled=False,
        duration_years=0.1,
    )
    model = cm.ProcessClimateModel(config)
    high_latitude_linear = cm.initial_amoc_density_diagnostics(
        replace(
            config,
            amoc_density_eos="linear",
            amoc_density_geometry="interhemispheric_high_latitude",
        ),
        baseline_north_temperature_c=model.baseline_amoc_north_c,
        baseline_southern_temperature_c=model.baseline_amoc_southern_c,
    )
    upper_limb_linear = cm.initial_amoc_density_diagnostics(
        replace(config, amoc_density_eos="linear"),
        baseline_north_temperature_c=model.baseline_amoc_north_c,
        baseline_southern_temperature_c=model.baseline_amoc_southern_c,
    )
    assert model.baseline_convection_density_driver == pytest.approx(
        abs(high_latitude_linear["density_driver"])
    )
    assert model.baseline_convection_density_driver != pytest.approx(
        abs(upper_limb_linear["density_driver"])
    )


def test_continuous_convection_efficiency_directly_scales_transport():
    config = cm.ModelConfig(
        resolution_deg=10.0,
        auto_initialize_from_1850=False,
        seasonal_arctic_enabled=False,
        duration_years=0.1,
    )
    model = cm.ProcessClimateModel(config)
    model.state.convection_efficiency = 0.8
    diagnostics = model._amoc_diagnostics(model.state)
    assert diagnostics["amoc_convection_transport_multiplier"] == pytest.approx(0.8)
    assert diagnostics["amoc_unbounded_hydraulic_target_sv"] == pytest.approx(
        diagnostics["amoc_hydraulic_target_without_convection_sv"] * 0.8
    )


def test_short_hosing_integration_preserves_salt_and_weakens_amoc():
    config = cm.ModelConfig(
        resolution_deg=10.0, auto_initialize_from_1850=False,
        seasonal_arctic_enabled=False, scenario="constant", duration_years=5.0,
        dt_years=0.05, freshwater_hosing_sv=0.2,
        freshwater_start_fraction=0.0, freshwater_ramp_years=0.0,
    )
    frame = cm.ProcessClimateModel(config).run().dataframe
    assert np.isfinite(frame[["amoc_sv", "north_salinity_psu", "toa_imbalance_wm2"]]).all().all()
    assert frame.amoc_sv.iloc[-1] < frame.amoc_sv.iloc[0]
    assert frame.salt_conservation_error_ppm.abs().max() < 1e-8
    assert frame.pre_projection_salt_conservation_error_ppm.abs().max() < 1e-8
