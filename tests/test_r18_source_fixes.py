from types import SimpleNamespace

import numpy as np

import climate_model as cm
from arctic_observation_operator import ModelGridSampler, SpatialOperator, model_fixed_mask_area_extent


def _support_probe(mode: str):
    probe = object.__new__(cm.ProcessClimateModel)
    probe.config = cm.ModelConfig(arctic_ice_support_reference_mode=mode)
    return probe


def test_r18_legacy_support_mode_reproduces_r17_fixed_80_percent_pack():
    c = np.array([0.08, 0.40, 0.80, 0.95])
    got = _support_probe("fixed_pack_80")._arctic_reference_ice_support_fraction(c)
    expected = np.clip(np.maximum(c, c / 0.80), 0.0, 1.0)
    np.testing.assert_allclose(got, expected, rtol=0.0, atol=1e-14)


def test_r18_thermodynamic_support_compacts_in_cold_air_without_changing_area():
    c = np.array([0.08, 0.40, 0.80, 0.95])
    probe = _support_probe("thermodynamic_pack")
    cold = probe._arctic_reference_ice_support_fraction(c, np.full_like(c, -20.0))
    warm = probe._arctic_reference_ice_support_fraction(c, np.full_like(c, 0.0))
    upper = np.minimum(1.0, c / 0.15)
    assert np.all(cold >= c - 1e-14)
    assert np.all(warm >= c - 1e-14)
    assert np.all(cold <= warm + 1e-14)
    assert np.all(warm <= upper + 1e-14)
    # Cold pack approaches 100% concentration, so its occupied support approaches native area.
    np.testing.assert_allclose(cold, c, rtol=0.0, atol=2e-12)


def test_r18_fixed_mask_operator_uses_fractional_support_even_below_native_15pct():
    operator = SpatialOperator(
        source_id="synthetic",
        latitude_deg=np.array([80.0, 82.0]),
        longitude_deg=np.array([0.0, 10.0]),
        cell_area_km2=np.array([1_000_000.0, 2_000_000.0]),
    )
    sampler = ModelGridSampler(flat_indices=np.array([0, 1]), angular_distance_deg=np.zeros(2), field_shape=(1, 2))

    class Result:
        def sea_ice_concentration_map_at_index(self, index):
            return np.array([[0.10, 0.20]])
        def sea_ice_extent_occupancy_map_at_index(self, index):
            return np.array([[0.50, 0.40]])

    got = model_fixed_mask_area_extent(Result(), 0, operator, sampler)
    assert got["extent_operator_method"] == "fractional_15pct_support_occupancy"
    assert abs(got["area_million_km2"] - 0.5) < 1e-12
    assert abs(got["extent_million_km2"] - 1.3) < 1e-12


def test_r18_fixed_mask_operator_retains_legacy_threshold_fallback():
    operator = SpatialOperator(
        source_id="synthetic",
        latitude_deg=np.array([80.0, 82.0]),
        longitude_deg=np.array([0.0, 10.0]),
        cell_area_km2=np.array([1_000_000.0, 2_000_000.0]),
    )
    sampler = ModelGridSampler(flat_indices=np.array([0, 1]), angular_distance_deg=np.zeros(2), field_shape=(1, 2))

    class OldResult:
        def sea_ice_concentration_map_at_index(self, index):
            return np.array([[0.10, 0.20]])

    got = model_fixed_mask_area_extent(OldResult(), 0, operator, sampler)
    assert got["extent_operator_method"] == "legacy_native_concentration_threshold"
    assert abs(got["area_million_km2"] - 0.4) < 1e-12
    assert abs(got["extent_million_km2"] - 2.0) < 1e-12


def test_production_amoc_uses_matched_teos_without_changing_control():
    cfg = cm.ModelConfig()
    assert cfg.amoc_reference_sv == 17.0
    assert cfg.amoc_density_geometry == "interhemispheric_high_latitude"
    assert cfg.amoc_density_eos == "teos10_matched"
    assert cfg.arctic_ice_support_reference_mode == "thermodynamic_pack"
    linear = cm.ModelConfig(amoc_density_eos="linear")
    assert linear.amoc_density_eos == "linear"


def test_r18_runner_matrix_has_no_teos_and_only_five_year_children():
    import importlib.util, pathlib
    path = pathlib.Path(__file__).resolve().parents[1] / "provenance" / "r18.1-parent" / "verify_r18_local.py"
    spec = importlib.util.spec_from_file_location("verify_r18_local_parent", path)
    runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)
    runner.ROOT = pathlib.Path(__file__).resolve().parents[1]
    runner.SOURCE = runner.ROOT / "climate_model.py"
    assert runner.MAX_CHUNK_YEARS == 5.0
    assert "teos" not in runner.STAGE_SEGMENTS
    assert len(runner.STAGE_SEGMENTS["sea-ice"]) == 4
    assert len(runner.STAGE_SEGMENTS["recovery"]) == 6
    assert runner.SEGMENTS["r18_recovery_m0p40_then_zero_to_900y"]["inherits_from"] == "r18_recovery_dehose_m0p40_to_700y"


def test_r18_validation_semantics_do_not_promote_extent_to_release_evidence():
    import sea_ice_validation as siv
    source = open(siv.__file__, encoding="utf-8").read()
    assert '"extent_is_separate_prognostic_state": True' in source
    assert '"extent_derived_from_native_concentration": False' in source
    assert '"extent_has_separate_prognostic_geometry_state": True' in source
    assert '"extent_independently_prognostic_spatial_field": False' in source
    assert '"used_for_scientific_release_gate": False' in source
    assert '"independent_predictive_validation": False' in source


def test_r18_runner_records_exact_fixed_mask_support_fields_without_full_constructor():
    import importlib.util, pathlib
    path = pathlib.Path(__file__).resolve().parents[1] / "provenance" / "r18.1-parent" / "verify_r18_local.py"
    spec = importlib.util.spec_from_file_location("verify_r18_local_parent_record", path)
    runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)
    runner.ROOT = pathlib.Path(__file__).resolve().parents[1]
    runner.SOURCE = runner.ROOT / "climate_model.py"

    class FakeModel:
        def __init__(self):
            self.config = SimpleNamespace(resolution_deg=10.0, start_year=1850.0, arctic_ice_support_reference_mode="thermodynamic_pack")
            self.state = SimpleNamespace(
                atlantic_sea_ice_fraction=np.array([0.10, 0.50]),
                non_atlantic_sea_ice_fraction=np.array([0.20, 0.60]),
            )
            self.grid = SimpleNamespace(
                lat=np.array([70.0, 85.0]),
                lon=np.array([0.0, 180.0]),
                lat2d=np.array([[70.0, 70.0], [85.0, 85.0]]),
                lon2d=np.array([[0.0, 180.0], [0.0, 180.0]]),
                atlantic_ocean_fraction_map=np.array([[1.0, 0.0], [1.0, 0.0]]),
                ocean_fraction_map=np.ones((2, 2)),
                map_area_weights=np.full((2, 2), 0.25),
            )
        def record(self, elapsed):
            return {"elapsed_years": elapsed, "year": self.config.start_year + elapsed, "global_surface_warming_c": 0.0}
        def _effective_sea_ice_support_fractions(self, state, elapsed):
            return np.array([0.20, 0.60]), np.array([0.30, 0.70])

    row = runner.record_model(FakeModel(), 129.0, {"stage": "sea-ice"})
    assert row["nsidc_fixed_mask_extent_operator_method"] == "fractional_15pct_support_occupancy"
    assert row["nsidc_fixed_mask_sea_ice_extent_million_km2"] >= row["nsidc_fixed_mask_sea_ice_area_million_km2"]
    assert 0.0 <= row["nsidc_fixed_mask_sea_ice_pack_concentration"] <= 1.0


def test_r18_month_mapping_selects_march_and_september_exactly():
    import importlib.util, pathlib
    path = pathlib.Path(__file__).resolve().parents[1] / "provenance" / "r18.1-parent" / "verify_r18_local.py"
    spec = importlib.util.spec_from_file_location("verify_r18_local_parent_month", path)
    runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)
    runner.ROOT = pathlib.Path(__file__).resolve().parents[1]
    runner.SOURCE = runner.ROOT / "climate_model.py"
    assert runner._calendar_year_month(1979.0 + 2.0 / 12.0) == (1979, 3)
    assert runner._calendar_year_month(1979.0 + 8.0 / 12.0) == (1979, 9)


def test_r18_cli_support_default_matches_model_config():
    args = cm.build_parser().parse_args([])
    assert args.arctic_ice_support_reference_mode == cm.ModelConfig().arctic_ice_support_reference_mode
