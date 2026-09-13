"""Physical invariants for the September 2026 structural revision."""
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

import climate_model as cm
import monte_carlo as mc
from amoc_density_r16 import teos10_density_diagnostics


def config(**changes):
    return replace(cm.ModelConfig(
        resolution_deg=10.0, seasonal_arctic_enabled=False,
        auto_initialize_from_1850=False, scenario="constant",
        co2_start_ppm=cm.ModelConfig().co2_reference_ppm,
        duration_years=1.0, record_every_years=0.2,
    ), **changes)


@pytest.mark.parametrize("resolution", [5.0, 10.0])
def test_ocean_freezing_floor_preserves_global_reference_mean(resolution):
    model = cm.ProcessClimateModel(config(resolution_deg=resolution))
    ocean = model.grid.ocean_fraction_map > 0
    assert model.baseline_ocean_map_c[ocean].min() >= -1.8 - 1e-12
    assert np.sum(model.baseline_map_c * model.grid.map_area_weights) == pytest.approx(14.0)


@pytest.mark.parametrize("resolution", [5.0, 10.0])
def test_default_longwave_damps_uniform_warming_in_every_column(resolution):
    model = cm.ProcessClimateModel(config(resolution_deg=resolution))
    for baseline in (model.baseline_land_c, model.baseline_ocean_c):
        for warming in (0.01, 1.0, 4.0, 10.0):
            anomaly = np.full_like(baseline, warming)
            lw = model._clear_sky_longwave_components(baseline, anomaly)
            total = lw["clear_sky_total"] + model._unresolved_polar_lapse_rate_feedback(anomaly)
            assert np.all(total < 0.0)
        zero = model._clear_sky_longwave_components(baseline, np.zeros_like(baseline))
        assert np.max(np.abs(zero["clear_sky_total"])) == 0.0
    lw = model._clear_sky_longwave_components(model.baseline_land_c, np.ones_like(model.grid.lat))
    assert lw["water_vapor"][-1] < lw["water_vapor"][np.argmin(abs(model.grid.lat))]


def test_hydraulics_respond_to_northern_surface_to_deep_stratification():
    model = cm.ProcessClimateModel(config())
    control = model._amoc_diagnostics(model.state)
    deep = replace(model.state, atlantic_deep_ocean_anomaly_c=np.where(
        model.amoc_north_region_fraction > 0, 1.0, 0.0))
    north = replace(model.state, atlantic_ocean_anomaly_c=np.where(
        model.amoc_north_region_fraction > 0, 1.0, 0.0))
    assert control["amoc_density_driver_ratio"] == pytest.approx(1.0)
    assert model._amoc_diagnostics(deep)["amoc_density_driver"] > control["amoc_density_driver"]
    assert model._amoc_diagnostics(north)["amoc_density_driver"] < control["amoc_density_driver"]
    assert control["amoc_source_freezing_bound_active"] == 0.0


def test_doubled_co2_weakens_amoc_without_an_empirical_target():
    model = cm.ProcessClimateModel(config(scenario="step_2x", duration_years=5.0))
    frame = model.run().dataframe
    assert frame.amoc_sv.iloc[-1] < model.config.amoc_reference_sv
    assert frame.amoc_density_driver_ratio.iloc[-1] < 1.0


def test_fovs_is_the_external_boundary_budget_not_legacy_internal_section():
    model = cm.ProcessClimateModel(config())
    # Perturb the prognostic boundary tracer after the budget initialization.
    # The diagnostic must follow the actual boundary state.
    model.state.external_salinity_psu = 34.70
    diagnostics = model._amoc_diagnostics(model.state)
    expected = (-model.state.amoc_sv
                * (model.state.external_salinity_psu - model.state.deep_salinity_psu)
                / model.config.fovs_reference_salinity_psu)
    assert diagnostics["fovs_sv"] == pytest.approx(expected)
    assert diagnostics["amoc_boundary_overturning_freshwater_sv"] == pytest.approx(expected)
    expected_internal = (-model.state.amoc_sv
                         * (model.state.south_atlantic_upper_salinity_psu
                            - model.state.deep_salinity_psu)
                         / model.config.fovs_reference_salinity_psu)
    assert diagnostics["amoc_internal_section_freshwater_sv"] == pytest.approx(
        expected_internal)
    assert diagnostics["fovs_sv"] != pytest.approx(
        diagnostics["amoc_internal_section_freshwater_sv"]
    )
    assert np.isnan(diagnostics["fovn_northern_boundary_overturning_freshwater_sv"])
    assert np.isnan(diagnostics["delta_fov_stability_indicator_sv"])
    assert diagnostics["delta_fov_stability_indicator_complete"] == 0.0


def test_default_fovs_emerges_from_control_freshwater_budget():
    model = cm.ProcessClimateModel(config())
    diagnostics = model._amoc_diagnostics(model.state)
    standalone_density = cm.initial_amoc_density_diagnostics(model.config)
    assert diagnostics["fovs_sv"] == pytest.approx(-0.16, abs=1.0e-10)
    assert standalone_density["density_ratio"] == pytest.approx(1.0)
    assert standalone_density["south_atlantic_upper_salinity_psu"] == pytest.approx(
        model.state.south_atlantic_upper_salinity_psu
    )
    assert standalone_density["active_source_salinity_psu"] == pytest.approx(
        model.state.south_atlantic_upper_salinity_psu
    )
    assert model.state.external_salinity_psu > model.state.deep_salinity_psu
    assert model.baseline_surface_freshwater_sv == pytest.approx(
        [0.43, -0.65, 0.38, 0.0, 0.0, -0.16]
    )
    assert model._configured_control_surface_freshwater_fluxes() == pytest.approx(
        [0.37, -0.65, 0.0, 0.0, 0.0, 0.28]
    )
    assert model.baseline_control_boundary_freshwater_sv == pytest.approx(
        [0.06, 0.0, 0.38, 0.0, 0.0, -0.44]
    )
    assert diagnostics["amoc_control_surface_freshwater_sv"] == pytest.approx(-0.28)
    assert diagnostics["amoc_control_northern_boundary_freshwater_sv"] == pytest.approx(0.06)
    assert diagnostics["amoc_control_southern_gyre_freshwater_sv"] == pytest.approx(0.38)
    assert diagnostics["amoc_control_budget_predicted_fovs_sv"] == pytest.approx(-0.16)
    different_legacy_target = cm.ProcessClimateModel(config(initial_fovs_sv=999.0))
    assert different_legacy_target.initial_amoc_salinity_psu == pytest.approx(
        model.initial_amoc_salinity_psu, abs=1.0e-12
    )
    with pytest.raises(ValueError, match="initial_fovs_sv"):
        cm.ProcessClimateModel(config(
            amoc_control_salinity_mode="prescribed_hydrography",
            initial_fovs_sv=999.0,
        ))
    different_seed = cm.ProcessClimateModel(config(
        initial_external_salinity_psu=35.0,
        initial_fovs_sv=0.10,
    ))
    assert different_seed._amoc_diagnostics(different_seed.state)["fovs_sv"] == pytest.approx(
        diagnostics["fovs_sv"], abs=1.0e-10
    )
    changed_budget = cm.ProcessClimateModel(config(
        amoc_control_north_surface_freshwater_sv=0.32,
    ))
    assert changed_budget._amoc_diagnostics(changed_budget.state)["fovs_sv"] == pytest.approx(
        -0.11, abs=1.0e-10
    )


def test_eos_freezing_bound_is_visible_and_preserves_liquid_eos():
    kwargs = dict(north_temperature_c=-12.0, source_temperature_c=-10.0,
                  north_salinity_psu=35.0, source_salinity_psu=34.0,
                  reference_density_kg_m3=1027.0)
    result = teos10_density_diagnostics(**kwargs)
    assert result["north_freezing_bound_active"] == result["source_freezing_bound_active"] == 1.0
    bounded = teos10_density_diagnostics(**{
        **kwargs, "north_temperature_c": result["north_eos_temperature_c"],
        "source_temperature_c": result["source_eos_temperature_c"],
    })
    assert bounded["density_driver"] == result["density_driver"]
    assert bounded["source_freezing_bound_active"] == 0.0


@pytest.mark.parametrize("transport", [-17.0, 17.0])
def test_open_boundary_conserves_salt_and_ventilates_basin(transport):
    model = cm.ProcessClimateModel(config(
        amoc_allow_reversal=True, amoc_southern_external_exchange_sv=0.0,
        amoc_south_atlantic_external_exchange_sv=0.0))
    salinity = model.initial_amoc_salinity_psu.copy()
    freshened = salinity.copy()
    basin = [0, 1, 2, 4]
    freshened[basin] -= 0.1
    delta = (model._advective_mixing_salinity_tendency(freshened, transport)
             - model._advective_mixing_salinity_tendency(salinity, transport))
    inventory_rate = delta * model.amoc_box_volumes_m3
    assert inventory_rate[basin].sum() == pytest.approx(abs(transport) * 1e6 * cm.SECONDS_PER_YEAR * 0.1)
    assert inventory_rate.sum() == pytest.approx(0.0, abs=10.0)


def test_control_hydrology_balances_open_boundary_without_salt_projection():
    model = cm.ProcessClimateModel(config())
    salt = model.initial_amoc_salinity_psu
    tendency = model._advective_mixing_salinity_tendency(salt, 17.0)
    freshwater = model.baseline_surface_freshwater_sv
    residual = tendency - freshwater * model.amoc_reference_salinity_psu * 1e6 * cm.SECONDS_PER_YEAR / model.amoc_box_volumes_m3
    assert np.max(np.abs(residual)) < 1e-15
    assert abs(freshwater.sum()) < 1e-15
    frame = model.run().dataframe
    assert frame.global_surface_warming_c.abs().max() < 1e-10
    assert np.max(abs(frame.amoc_sv - 17.0)) < 1e-10


def test_daily_variability_pdd_matches_gaussian_integral():
    sigma = 4.5
    assert cm.expected_positive_temperature(0.0, sigma) == pytest.approx(sigma / np.sqrt(2 * np.pi))
    np.testing.assert_array_equal(cm.expected_positive_temperature([-2.0, 0.0, 3.0], 0.0), [0.0, 0.0, 3.0])
    assert cm.expected_positive_temperature(-3.0, sigma) > 0.0


@pytest.mark.parametrize("warming", [-3.0, 0.0, 3.0])
def test_greenland_scalar_and_annual_paths_agree(warming):
    model = cm.ProcessClimateModel(config())
    phases = (np.arange(72) + 0.5) / 72
    scalar = [model._greenland_surface_mass_balance(model.state, warming, t)["surface_freshwater_sv"] for t in phases]
    annual = model._greenland_annual_surface_flux_samples_sv(model.state, warming)
    np.testing.assert_allclose(scalar, annual, atol=1e-14)
    if warming == 0.0:
        assert np.max(np.abs(annual)) < 1e-14


def test_annual_means_remove_seasonal_cycle_and_partial_year():
    time = np.arange(0.0, 5.31, 0.1)
    frame = pd.DataFrame({"elapsed_years": time, "flux": 3.0 + 2.0 * np.cos(2 * np.pi * time), "linear": time})
    result = cm.annual_mean_diagnostics(frame)
    assert len(result) == 5
    np.testing.assert_allclose(result.flux, 3.0, atol=1e-12)
    np.testing.assert_allclose(result.linear, np.arange(5) + 0.5, atol=1e-12)


def test_cli_and_api_share_revised_defaults_and_legacy_switches():
    api = cm.ModelConfig()
    cli = cm.config_from_args(cm.build_parser().parse_args([]))
    for key in ("amoc_density_geometry", "amoc_density_eos", "arctic_phase_restoring_enabled", "arctic_forced_ocean_heat_convergence_enabled", "arctic_winter_transport_enhancement"):
        assert getattr(cli, key) == getattr(api, key)
    args = cm.build_parser().parse_args(["--enable-arctic-phase-restoring", "--enable-arctic-forced-ocean-heat-convergence"])
    assert cm.config_from_args(args).arctic_phase_restoring_enabled


@pytest.mark.parametrize("name", ["arctic_phase_restoring_max_deficit_flux_wm2", "arctic_forced_ocean_heat_convergence_wm2_per_k"])
def test_disabled_closures_are_not_sampled_as_active_parameters(name):
    base = cm.ModelConfig()
    assert name not in mc.science_default_ranges("ar6_amoc", base)
    with pytest.raises(ValueError, match="inactive"):
        mc.generate_samples(base, {name: (1.0, 2.0)}, 2, 42, "uniform", "random", False)
    enabled = replace(base, arctic_phase_restoring_enabled=True, arctic_forced_ocean_heat_convergence_enabled=True)
    assert name in mc.science_default_ranges("ar6_amoc", enabled)


@pytest.mark.parametrize("hosing", [0.0, 0.2])
def test_coupled_arctic_short_run_conserves_salt(hosing):
    model = cm.ProcessClimateModel(config(seasonal_arctic_enabled=True, duration_years=2.0,
        freshwater_hosing_sv=hosing, freshwater_start_fraction=0.0, freshwater_ramp_years=0.0))
    frame = model.run().dataframe
    assert frame.pre_projection_salt_conservation_error_ppm.abs().max() < 1e-8
    assert model.arctic_ice_export_freshwater_salinity_scale == 1.0
    if hosing:
        assert frame.amoc_sv.iloc[-1] < 17.0
    else:
        assert frame.global_surface_warming_c.abs().max() < 1e-10
