from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys

import numpy as np
import pytest

import climate_model as cm
from sea_ice_observation import (
    MINIMUM_EXTENT_CONCENTRATION,
    PACK_ICE_CONCENTRATION_THRESHOLD,
    reconstruct_concentration_and_occupancy,
)


def test_r17_default_amoc_is_unchanged_linear_high_latitude():
    cfg = cm.ModelConfig(resolution_deg=10.0, auto_initialize_from_1850=False)
    assert cfg.amoc_density_eos == "linear"
    assert cfg.amoc_density_geometry == "interhemispheric_high_latitude"
    d = cm.initial_amoc_density_diagnostics(cfg)
    assert d["density_driver"] == pytest.approx(4.34e-4, abs=2e-8)
    assert d["density_ratio"] == pytest.approx(1.0, abs=2e-3)


def _bare_model(eos: str = "linear"):
    model = cm.ProcessClimateModel.__new__(cm.ProcessClimateModel)
    model.config = cm.ModelConfig(
        resolution_deg=10.0,
        auto_initialize_from_1850=False,
        amoc_density_eos=eos,
    )
    model.baseline_amoc_north_c = 5.0
    model.baseline_amoc_southern_c = -1.0
    return model


def test_teos10_matched_preserves_linear_thermal_pathway(monkeypatch):
    calls = []

    def fake_driver(**kwargs):
        calls.append(kwargs)
        return 0.123

    import amoc_density_r16 as density
    monkeypatch.setattr(density, "teos10_density_driver", fake_driver)

    model = _bare_model("teos10_matched")
    model._density_driver_from_values(
        north_temperature_c=8.0,
        southern_temperature_c=3.0,
        north_salinity_psu=35.1,
        southern_salinity_psu=34.2,
        north_surface_anomaly_c=2.0,
        north_deep_anomaly_c=0.5,
    )
    call = calls[-1]
    # baseline delta T = -6 C; stratification anomaly = +1.5 C; with the
    # default unit thermal coupling, the effective source-minus-north delta is
    # -7.5 C. The actual Southern temperature (3 C) is deliberately ignored.
    assert call["source_temperature_c"] == pytest.approx(8.0 - 7.5)
    assert call["source_temperature_c"] != pytest.approx(3.0)


def test_teos10_surface_watermass_preserves_r16_direct_source_branch(monkeypatch):
    calls = []

    def fake_driver(**kwargs):
        calls.append(kwargs)
        return 0.123

    import amoc_density_r16 as density
    monkeypatch.setattr(density, "teos10_density_driver", fake_driver)
    model = _bare_model("teos10_surface_watermass")
    model._density_driver_from_values(
        north_temperature_c=8.0,
        southern_temperature_c=3.0,
        north_salinity_psu=35.1,
        southern_salinity_psu=34.2,
        north_surface_anomaly_c=2.0,
        north_deep_anomaly_c=0.5,
    )
    assert calls[-1]["source_temperature_c"] == pytest.approx(3.0)


def test_reference_support_uses_fixed_pack_boundary_and_obeys_extent_bounds():
    c = np.array([0.0, 0.08, 0.40, 0.80, 0.95])
    s = cm.ProcessClimateModel._arctic_reference_ice_support_fraction(c)
    expected = np.array([0.0, 0.10, 0.50, 1.0, 1.0])
    assert PACK_ICE_CONCENTRATION_THRESHOLD == pytest.approx(0.80)
    assert MINIMUM_EXTENT_CONCENTRATION == pytest.approx(0.15)
    assert np.allclose(s, expected)
    assert np.all(s >= c - 1e-12)
    assert np.all(s <= np.minimum(1.0, c / MINIMUM_EXTENT_CONCENTRATION) + 1e-12)


def test_support_advance_uses_process_ledger_but_does_not_change_ice_mass_state():
    model = cm.ProcessClimateModel.__new__(cm.ProcessClimateModel)
    previous_support = np.array([0.50, 0.90])
    next_concentration = np.array([0.30, 0.70])
    original_concentration = next_concentration.copy()
    ledger = {
        "formation_area_change": np.array([0.02, 0.00]),
        "melt_area_change": np.array([-0.01, -0.02]),
        "ridging_area_change": np.array([-0.03, -0.03]),
        "divergence_area_change": np.array([-0.02, -0.01]),
        "compaction_area_change": np.array([-0.01, 0.00]),
        "mechanical_spreading_area_change": np.array([0.01, 0.00]),
        "support_area_change": np.array([0.00, 0.02]),
    }
    support = model._advance_arctic_ice_support(previous_support, next_concentration, ledger)
    assert np.array_equal(next_concentration, original_concentration)
    assert np.all(support >= next_concentration - 1e-12)
    assert np.all(support <= np.minimum(1.0, next_concentration / 0.15) + 1e-12)
    # Ridging is intentionally not an outer-support transport process.
    ledger_no_ridging = dict(ledger)
    ledger_no_ridging["ridging_area_change"] = np.zeros(2)
    support_no_ridging = model._advance_arctic_ice_support(previous_support, next_concentration, ledger_no_ridging)
    assert np.allclose(support, support_no_ridging)


def test_observation_operator_accepts_prognostic_support_and_conserves_native_area():
    lat = np.array([60.0, 80.0])
    lon = np.array([0.0, 180.0])
    lat2d = np.repeat(lat[:, None], 2, axis=1)
    lon2d = np.repeat(lon[None, :], 2, axis=0)
    ocean = np.ones((2, 2))
    atl = np.ones((2, 2))
    weights = np.full((2, 2), 0.25)
    native = np.array([0.10, 0.80])
    support = np.array([0.25, 1.00])
    concentration, occupancy, metrics = reconstruct_concentration_and_occupancy(
        atlantic_fraction=native,
        non_atlantic_fraction=native,
        lat=lat,
        lon=lon,
        lat2d=lat2d,
        lon2d=lon2d,
        atlantic_ocean_fraction_map=atl,
        ocean_fraction_map=ocean,
        map_area_weights=weights,
        warming_c=0.0,
        calendar_year=2020.0,
        atlantic_support_fraction=support,
        non_atlantic_support_fraction=support,
    )
    assert np.allclose(concentration[:, 0], native)
    assert np.allclose(occupancy[:, 0], support)
    assert metrics["extent_method"] == "prognostic_subgrid_ice_support_15pct_threshold"
    assert metrics["extent_is_separate_prognostic_state"] == 1.0
    assert metrics["extent_derived_from_native_concentration"] == 0.0
    assert metrics["extent_contains_observational_fit"] == 0.0
    assert abs(metrics["extent_reconstruction_native_area_error_million_km2"]) < 1e-12
    assert metrics["northern_hemisphere_sea_ice_extent_million_km2"] >= metrics[
        "northern_hemisphere_sea_ice_area_million_km2"
    ]


def test_no_support_preserves_r16_fallback_semantics():
    lat = np.array([60.0, 80.0])
    lon = np.array([0.0, 180.0])
    lat2d = np.repeat(lat[:, None], 2, axis=1)
    lon2d = np.repeat(lon[None, :], 2, axis=0)
    ocean = np.ones((2, 2))
    atl = np.ones((2, 2))
    weights = np.full((2, 2), 0.25)
    _, _, metrics = reconstruct_concentration_and_occupancy(
        atlantic_fraction=np.array([0.10, 0.80]),
        non_atlantic_fraction=np.array([0.10, 0.80]),
        lat=lat,
        lon=lon,
        lat2d=lat2d,
        lon2d=lon2d,
        atlantic_ocean_fraction_map=atl,
        ocean_fraction_map=ocean,
        map_area_weights=weights,
        warming_c=0.0,
        calendar_year=2020.0,
    )
    assert metrics["extent_method"] == "conservative_unfitted_meridional_subgrid_15pct_threshold"
    assert metrics["extent_is_separate_prognostic_state"] == 0.0


def test_r17_does_not_add_an_amoc_restart_threshold_or_retune_reference_strength():
    root = Path(__file__).resolve().parents[1]
    text = (root / "climate_model.py").read_text(encoding="utf-8")
    cfg = cm.ModelConfig(auto_initialize_from_1850=False)
    assert cfg.amoc_reference_sv == pytest.approx(17.0)
    for forbidden in (
        "amoc_restart_threshold",
        "forced_restart",
        "recovery_trigger",
    ):
        assert forbidden not in text


def test_record_and_simulation_history_share_prognostic_support_path():
    root = Path(__file__).resolve().parents[1]
    text = (root / "climate_model.py").read_text(encoding="utf-8")
    assert "def _effective_sea_ice_support_fractions(" in text
    record_start = text.index("    def record(")
    run_start = text.index("    def run(", record_start)
    record_text = text[record_start:run_start]
    assert "atlantic_support_fraction=atlantic_ice_support" in record_text
    assert "non_atlantic_support_fraction=non_atlantic_ice_support" in record_text
    assert "self._effective_sea_ice_support_fractions(state, elapsed_years)" in record_text


def test_r17_runner_is_staged_bounded_and_reuses_one_collapse_seed():
    import verify_r17_local as vr
    assert vr.MAX_CHUNK_YEARS == 5.0
    assert len(vr.SEGMENTS) == 11
    assert {k: len(v) for k, v in vr.STAGE_SEGMENTS.items()} == {
        "sea-ice": 4,
        "teos": 3,
        "recovery": 4,
    }
    seed = "r17_recovery_collapse_seed_250y"
    assert vr.SEGMENTS[seed]["duration"] == 250.0
    for suffix, expected in (("m0p05", -0.05), ("m0p10", -0.10), ("m0p20", -0.20)):
        name = next(n for n in vr.SEGMENTS if suffix in n)
        spec = vr.SEGMENTS[name]
        assert spec["inherits_from"] == seed
        assert spec["stages"][0]["start"] == 250.0
        assert spec["stages"][0]["overrides"]["freshwater_hosing_sv"] == pytest.approx(expected)
