from __future__ import annotations
import json
from dataclasses import replace
from pathlib import Path
import numpy as np
import pytest
import climate_model as cm
from sea_ice_observation import reconstruct_concentration_and_occupancy


def test_r16_default_restores_validated_high_latitude_geometry_and_alias():
    cfg = cm.ModelConfig(resolution_deg=10.0, auto_initialize_from_1850=False)
    assert cfg.amoc_density_geometry == "interhemispheric_high_latitude"
    default = cm.initial_amoc_density_diagnostics(cfg)
    legacy = cm.initial_amoc_density_diagnostics(replace(cfg, amoc_density_geometry="legacy_southern_surface"))
    sau = cm.initial_amoc_density_diagnostics(replace(cfg, amoc_density_geometry="south_atlantic_upper"))
    assert default["density_driver"] == pytest.approx(4.34e-4, abs=2e-8)
    assert legacy["density_driver"] == pytest.approx(default["density_driver"], rel=0, abs=1e-15)
    assert default["active_source_salinity_psu"] == pytest.approx(cfg.initial_southern_salinity_psu)
    assert sau["density_driver"] > 1.0e-3


@pytest.mark.parametrize("resolution", [10.0, 5.0, 2.5])
def test_high_latitude_density_control_is_resolution_consistent(resolution):
    cfg = cm.ModelConfig(resolution_deg=resolution, auto_initialize_from_1850=False)
    d = cm.initial_amoc_density_diagnostics(cfg)
    assert d["density_driver"] > 0.0
    assert d["density_ratio"] == pytest.approx(1.0, abs=2e-3)


def test_teos10_uses_geometry_specific_source_coordinate(monkeypatch):
    import amoc_density_r16 as eos
    calls = []
    class FakeGSW:
        @staticmethod
        def SA_from_SP(sp,p,lon,lat):
            calls.append((float(lon), float(lat)))
            return float(sp)
        @staticmethod
        def rho_t_exact(sa,t,p):
            return 1000.0 + sa - 0.2*t
    monkeypatch.setitem(__import__('sys').modules, 'gsw', FakeGSW)
    eos.teos10_density_driver(north_temperature_c=10,north_salinity_psu=35,source_temperature_c=2,source_salinity_psu=34,source_latitude_deg=-52.5,source_longitude_deg=-20,reference_density_kg_m3=1025)
    assert calls[-1] == (-20.0, -52.5)


def test_subgrid_extent_is_fractional_conservative_and_unfitted():
    lat=np.array([60.0,80.0]); lon=np.array([0.0,180.0]); lat2d=np.repeat(lat[:,None],2,axis=1); lon2d=np.repeat(lon[None,:],2,axis=0)
    ocean=np.ones((2,2)); atl=np.ones((2,2)); weights=np.full((2,2),0.25)
    concentration, occupancy, metrics = reconstruct_concentration_and_occupancy(
        atlantic_fraction=np.array([0.10,0.80]), non_atlantic_fraction=np.array([0.10,0.80]),
        lat=lat, lon=lon, lat2d=lat2d, lon2d=lon2d,
        atlantic_ocean_fraction_map=atl, ocean_fraction_map=ocean, map_area_weights=weights,
        warming_c=0.0, calendar_year=2020.0)
    assert np.all((occupancy>=0)&(occupancy<=1))
    assert np.any((occupancy>0)&(occupancy<1))
    assert metrics['extent_contains_observational_fit']==0.0
    assert metrics['extent_subgrid_fractional_occupancy']==1.0
    assert abs(metrics['extent_reconstruction_native_area_error_million_km2']) < 1e-12
    assert np.allclose(concentration[:,0], [0.10,0.80])


def _setup_model(**kwargs):
    cfg=cm.ModelConfig(resolution_deg=10.0,duration_years=0.1,auto_initialize_from_1850=False,seasonal_arctic_enabled=False,**kwargs)
    return cm.ProcessClimateModel(cfg)


def test_variable_ocean_volume_preserves_physical_salt_mass():
    model=_setup_model(); scale=1.001; initial=model.initial_amoc_salinity_psu/scale
    projected=model._project_salinity_to_conserved_total(initial,scale)
    physical=float(np.sum(model.amoc_box_volumes_m3*projected))*scale
    assert physical==pytest.approx(model.initial_total_salt_psu_m3,rel=0,abs=1e5)


def test_greenland_elevation_feedback_and_ablation_switches_remain_active():
    model=_setup_model(); lost=model.state.copy(); lost.greenland_remaining_ice_gt*=0.8
    active=model._greenland_surface_mass_balance(lost,0.0,0.0)
    assert active['elevation_feedback_warming_c']>0.0
    off=_setup_model(greenland_elevation_feedback_enabled=False); lost2=off.state.copy(); lost2.greenland_remaining_ice_gt*=0.8
    assert off._greenland_surface_mass_balance(lost2,0.0,0.0)['elevation_feedback_warming_c']==pytest.approx(0.0)
    phase_off=_setup_model(arctic_phase_restoring_enabled=False)
    out=phase_off._arctic_phase_restoring_flux_wm2(np.ones_like(phase_off.grid.lat),np.zeros_like(phase_off.grid.lat),np.ones_like(phase_off.grid.lat))
    assert np.allclose(out,0.0)


def test_diagnostic_only_gyre_transport_removed_from_active_gui_surfaces():
    root=Path(__file__).resolve().parents[1]
    gui=(root/'climate_model_gui.py').read_text(encoding='utf-8')
    app=(root/'app.py').read_text(encoding='utf-8')
    assert 'st.slider(\'Atlantic gyre heat transport (PW)\'' not in app
    assert '("atlantic_gyre_heat", "atlantic_gyre_heat_transport_pw"' not in gui


def test_compatibility_only_controls_hidden_from_cli_help():
    help_text=cm.build_parser().format_help()
    for opt in ('--amoc-pycnocline-relaxation-years','--amoc-convection-critical-density-ratio','--amoc-convection-transition-width','--amoc-convection-transport-exponent','--amoc-interhemispheric-temperature-coupling','--amoc-stratification-saturation-c'):
        assert opt not in help_text


def test_prospective_r16_is_evidence_driven_and_not_available_without_data():
    import prospective_validation_r16 as pv
    result=pv.evaluate()
    assert result['independent_predictive_scientific_validation_status']=='not_available'
    assert result['independent_predictive_scientific_validation_complete'] is False
    protocol=json.loads(pv.DEFAULT_PROTOCOL.read_text(encoding='utf-8'))
    assert protocol['reserved_period']['start_year']==2027
    assert protocol['reserved_period']['end_year']==2036
    assert protocol['decision_rule']['no_manual_boolean'] is True
    assert 'excluded' in protocol['spatial_extent_policy']


def test_r16_runner_has_34_experiments_and_forced_structural_branches():
    import verify_r16_local as vr
    assert vr.MAX_CHUNK_YEARS==5.0
    assert len(vr.SEGMENTS)==34
    names=set(vr.SEGMENTS)
    for required in (
        'r16_teos10_hosing_0p2_100y','r16_teos10_ssp245_1850_2100_10deg',
        'r16_sau_ssp245_1850_2100_10deg','r16_sau_hosing_0p2_100y',
        'r16_struct_cap20_strengthen_120y','r16_struct_cap24_strengthen_120y',
        'r16_struct_no_reversal_hose0p8_200y','r16_struct_reversal_hose0p8_200y',
        'r16_recovery_default_700y'):
        assert required in names
    assert all(float(spec['duration'])>=0 for spec in vr.SEGMENTS.values())
