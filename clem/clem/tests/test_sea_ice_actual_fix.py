"""Focused regression coverage for the reviewed Arctic sea-ice behavior fixes."""

from __future__ import annotations
from dataclasses import replace
from pathlib import Path
import numpy as np
import pytest
from arctic_process_budget import evaluate_arctic_process_ledger
from climate_model import ModelConfig, ProcessClimateModel
from monte_carlo import MONTE_CARLO_PHYSICAL_PARAMETERS, SCIENCE_PRIOR_SPECS
ROOT = Path(__file__).resolve().parents[1]

def _small_config(**changes: object) -> ModelConfig:
    return replace(ModelConfig(), scenario="constant", duration_years=0.1, dt_years=0.05, record_every_years=0.05, resolution_deg=10.0, auto_initialize_from_1850=False, **changes)

def test_actual_fix_defaults_are_locked_and_exposed() -> None:
    cfg=ModelConfig()
    assert cfg.arctic_reference_air_temperature_at_full_latitude_c == pytest.approx(-9.5)
    assert cfg.arctic_basal_ocean_exchange_wm2_k == pytest.approx(6.0)
    assert cfg.arctic_ice_area_formation_volume_sensitivity == pytest.approx(11.5)
    assert cfg.arctic_ice_area_formation_support_floor == pytest.approx(0.59)
    assert cfg.arctic_forced_ocean_heat_convergence_wm2_per_k == pytest.approx(7.5)
    assert cfg.arctic_forced_ocean_heat_convergence_onset_warming_c == pytest.approx(0.45)
    assert cfg.arctic_forced_ocean_heat_convergence_saturation_scale_c == pytest.approx(0.32)
    assert cfg.arctic_max_equivalent_thickness_m == pytest.approx(20.0)
    assert cfg.arctic_max_local_ice_thickness_m == pytest.approx(500.0)
    assert cfg.arctic_phase_restoring_deficit_saturation_fraction == pytest.approx(0.14)
    assert cfg.arctic_phase_restoring_max_deficit_flux_wm2 == pytest.approx(2.5)
    assert cfg.arctic_ice_area_thick_pack_resistance_exponent == pytest.approx(0.0)

def test_emergency_safeguards_are_not_science_priors() -> None:
    safeguards={"arctic_max_equivalent_thickness_m","arctic_max_local_ice_thickness_m"}
    assert safeguards.isdisjoint(MONTE_CARLO_PHYSICAL_PARAMETERS)
    assert safeguards.isdisjoint(SCIENCE_PRIOR_SPECS)
    active={"arctic_basal_ocean_exchange_wm2_k","arctic_ice_area_formation_volume_sensitivity","arctic_ice_area_formation_support_floor","arctic_forced_ocean_heat_convergence_wm2_per_k","arctic_forced_ocean_heat_convergence_onset_warming_c","arctic_forced_ocean_heat_convergence_saturation_scale_c","arctic_forced_ocean_heat_convergence_ice_fraction_exponent","arctic_phase_restoring_deficit_saturation_fraction","arctic_phase_restoring_max_deficit_flux_wm2"}
    assert active <= MONTE_CARLO_PHYSICAL_PARAMETERS
    assert active <= SCIENCE_PRIOR_SPECS.keys()
    assert "arctic_ice_area_thick_pack_resistance_exponent" not in __import__("monte_carlo").science_default_ranges("ar6_amoc")

def test_local_safeguard_is_fail_fast_and_does_not_remap_area() -> None:
    equivalent=np.array([0.05,0.5,1.0,2.0,4.0]); requested=np.array([0.10,0.20,0.25,0.20,0.25])
    model=ProcessClimateModel(_small_config()); energy=-equivalent*model.arctic_latent_energy_per_m_wyr_m2
    model.config=replace(model.config, arctic_max_local_ice_thickness_m=500.0); loose=model._arctic_state_from_energy_and_concentration(energy,requested)
    model.config=replace(model.config, arctic_max_local_ice_thickness_m=20.0); tight=model._arctic_state_from_energy_and_concentration(energy,requested)
    for left,right in zip(loose,tight): np.testing.assert_allclose(left,right,rtol=0.0,atol=1e-12)
    concentration,diagnosed,local=loose; np.testing.assert_allclose(concentration*local,diagnosed,rtol=0.0,atol=1e-12); assert float(np.max(local))<20.0
    model.config=replace(model.config, arctic_max_local_ice_thickness_m=10.0)
    with pytest.raises(FloatingPointError,match="local ice thickness"): model._arctic_state_from_energy_and_concentration(energy,requested)

def test_equivalent_safeguard_is_fail_fast_and_never_clips_or_transfers_energy() -> None:
    model=ProcessClimateModel(_small_config()); eq=np.array([6.0]); ice=-eq*model.arctic_latent_energy_per_m_wyr_m2
    ni,no,tr=model._normalize_arctic_surface_reservoirs(ice,np.zeros_like(ice),remap_open_area=False)
    np.testing.assert_allclose(-ni/model.arctic_latent_energy_per_m_wyr_m2,eq,rtol=0.0,atol=1e-12); np.testing.assert_allclose(no,0.0,atol=1e-12); np.testing.assert_allclose(tr,0.0,atol=1e-12)
    too=np.array([model.config.arctic_max_equivalent_thickness_m+1.0])
    with pytest.raises(FloatingPointError,match="equivalent thickness"): model._normalize_arctic_surface_reservoirs(-too*model.arctic_latent_energy_per_m_wyr_m2,np.zeros_like(too),remap_open_area=False)

def test_thick_pack_resistance_is_monotone_and_only_scales_area_retreat_support() -> None:
    model=ProcessClimateModel(_small_config()); ref=np.array([1.0,1.0,1.0]); cur=np.array([0.5,1.0,2.0])
    model.config=replace(model.config,arctic_ice_area_thick_pack_resistance_exponent=1.0); r1=model._arctic_thick_pack_resistance(ref,cur)
    model.config=replace(model.config,arctic_ice_area_thick_pack_resistance_exponent=4.0); r4=model._arctic_thick_pack_resistance(ref,cur)
    np.testing.assert_allclose(r1[:2],1.0,atol=1e-12); np.testing.assert_allclose(r4[:2],1.0,atol=1e-12); assert r1[2]==pytest.approx(0.5); assert r4[2]==pytest.approx(0.5**4); assert r4[2]<r1[2]
    kwargs=dict(previous_concentration=np.array([0.5]),previous_equivalent_thickness_m=np.array([1.0]),next_equivalent_thickness_m=np.array([0.9]),air_temperature_c=np.array([0.0]),ocean_temperature_c=np.array([0.0]),darkness=np.array([0.0]),dt_years=0.05,reference_previous_equivalent_thickness_m=np.array([1.5]),reference_previous_concentration=np.array([1.0]),return_process_ledger=True)
    model.config=replace(model.config,arctic_ice_area_thick_pack_resistance_exponent=1.0); _,l1=model._advance_arctic_ice_concentration(**kwargs)
    model.config=replace(model.config,arctic_ice_area_thick_pack_resistance_exponent=4.0); _,l4=model._advance_arctic_ice_concentration(**kwargs)
    assert l4["supported_volume_deficit"][0] < l1["supported_volume_deficit"][0]; np.testing.assert_allclose(l1["next_equivalent_thickness_m"],l4["next_equivalent_thickness_m"],atol=1e-12); np.testing.assert_allclose(l4["next_equivalent_thickness_m"],np.array([0.9]),atol=1e-12)

def test_forced_ocean_heat_convergence_is_active_and_conservative_above_onset() -> None:
    model=ProcessClimateModel(_small_config()); model.enable_arctic_process_ledger(); warming=model.config.arctic_forced_ocean_heat_convergence_onset_warming_c+1.0
    model.state.land_anomaly_c[:]=warming; model.state.atlantic_ocean_anomaly_c[:]=warming; model.state.non_atlantic_ocean_anomaly_c[:]=warming; model.state.atlantic_deep_ocean_anomaly_c[:]=warming; model.state.non_atlantic_deep_ocean_anomaly_c[:]=warming
    model.step(0.0,dt_years=model.config.dt_years); ledger=model.get_arctic_process_ledger(); changes=[np.asarray(e["forced_ocean_heat_convergence_energy_change_wyr_m2"],dtype=float) for e in ledger]; assert any(np.any(c>0.0) for c in changes)
    evaluation=evaluate_arctic_process_ledger(ledger,require_activity=False); assert evaluation["energy_budget_closed"] is True; assert evaluation["actual_receiving_reservoirs_verified"] is True
