from __future__ import annotations

import ast
import hashlib
import importlib.util
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]



def version_neutral_ast_sha256(path: Path) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    tree.body = [
        node for node in tree.body
        if not (
            isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "MODEL_VERSION" for t in node.targets)
        )
    ]
    return hashlib.sha256(ast.dump(tree, annotate_fields=True, include_attributes=False).encode("utf-8")).hexdigest()

def _runner():
    path = ROOT / "verify_r18_2_seaice_operator.py"
    spec = importlib.util.spec_from_file_location("verify_r18_2_seaice_operator_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_r18_2_governing_source_is_exact_r18_1() -> None:
    parent = ROOT / "provenance" / "r18.1-parent"
    assert sha256(parent / "climate_model.py") == "e1553c1baccd7a90974f7879dd664a8a4b447adec5bd93407bbc5dd0e2c9bd90"
    assert version_neutral_ast_sha256(ROOT / "climate_model.py") == version_neutral_ast_sha256(parent / "climate_model.py")
    for name in ("sea_ice_observation.py", "arctic_observation_operator.py", "sea_ice_validation.py"):
        assert sha256(ROOT / name) == sha256(parent / name)


def test_r18_2_reports_cell_threshold_and_support_operators_separately() -> None:
    runner = _runner()
    c = np.array([0.10, 0.20])
    o = np.array([0.50, 0.40])
    area = np.array([1_000_000.0, 2_000_000.0])
    got = runner._fixed_mask_four_diagnostics(c, o, area)
    assert abs(got["cell15_area_million_km2"] - 0.4) < 1e-12
    assert abs(got["cell15_extent_million_km2"] - 2.0) < 1e-12
    assert abs(got["support_conserving_area_million_km2"] - 0.5) < 1e-12
    assert abs(got["fractional_support_extent_million_km2"] - 1.3) < 1e-12


def test_r18_2_cell15_matches_established_fallback_operator() -> None:
    from arctic_observation_operator import ModelGridSampler, SpatialOperator, model_fixed_mask_area_extent
    runner = _runner()
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
    established = model_fixed_mask_area_extent(OldResult(), 0, operator, sampler)
    got = runner._fixed_mask_four_diagnostics(np.array([0.10, 0.20]), np.array([0.0, 0.0]), operator.cell_area_km2)
    assert abs(got["cell15_area_million_km2"] - established["area_million_km2"]) < 1e-12
    assert abs(got["cell15_extent_million_km2"] - established["extent_million_km2"]) < 1e-12


def test_r18_2_midmonth_selection_uses_nearest_005_year_record() -> None:
    runner = _runner()
    records = [{"year": 1979.0 + k * 0.05, "tag": k} for k in range(21)]
    march = runner._nearest_midmonth_rows(records, 3, 1979, 1979)[1979]
    target = 1979.0 + 2.5 / 12.0
    assert abs(march["year"] - target) <= 0.0250001
    assert march["fixed_mask_sample_offset_days"] <= 0.0250001 * 365.2425


def test_r18_2_suite_is_two_historical_runs_only() -> None:
    runner = _runner()
    assert runner.MAX_CHUNK_YEARS == 5.0
    assert len(runner.SEGMENTS) == 2
    assert set(runner.STAGE_SEGMENTS) == {"sea-ice"}
    for spec in runner.SEGMENTS.values():
        assert spec["duration"] == 175.0
        assert spec["record_interval_years"] == 0.05
        assert spec["config"]["dt_years"] == 0.05
        assert spec["config"]["scenario"] == "ssp245"


def test_r18_2_has_no_gsw_dependency_or_teos_segment() -> None:
    runner = _runner()
    text = (ROOT / "verify_r18_2_seaice_operator.py").read_text(encoding="utf-8")
    assert "import gsw" not in text
    assert all("teos" not in name.lower() for name in runner.SEGMENTS)


def test_r18_2_provenance_gate_passes() -> None:
    runner = _runner()
    result = runner.validate_r18_2_provenance(runner.sha256(runner.SOURCE))
    assert all(result["checks"].values())


def test_r18_2_static_worker_has_no_recovery_stage_dependency() -> None:
    runner = _runner()
    result = runner.static_worker()
    design = result["r18_validation_design"]
    assert design["experiment_count"] == 2
    assert design["stage_counts"] == {"sea-ice": 2}
    assert design["pass_two_historical_seaice_runs_only"] is True
