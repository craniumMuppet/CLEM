from __future__ import annotations

import ast
import hashlib
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()



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

def _load_runner():
    path = ROOT / "provenance" / "r18.1-parent" / "verify_r18_local.py"
    spec = importlib.util.spec_from_file_location("verify_r18_local_hotfix", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_finalizer_uses_existing_linear_fit_not_undefined_ols() -> None:
    source = (ROOT / "provenance" / "r18.1-parent" / "verify_r18_local.py").read_text(encoding="utf-8")
    assert "model_slope, _ = linear_fit(" in source
    assert "obs_slope, _ = linear_fit(" in source
    assert "model_slope, _ = ols(" not in source
    assert "obs_slope, _ = ols(" not in source


def test_series_metrics_hotfix_executes() -> None:
    runner = _load_runner()
    result = runner._series_metrics([1.0, 2.0, 3.0], [1.1, 2.1, 3.1], [2000, 2001, 2002])
    assert result["records"] == 3
    assert abs(result["model_ols_trend_million_km2_per_decade"] - 10.0) < 1.0e-12
    assert abs(result["observed_ols_trend_million_km2_per_decade"] - 10.0) < 1.0e-12


def test_r18_1_does_not_change_governing_physics_files() -> None:
    parent = ROOT / "provenance" / "r18-parent"
    expected_parent = "e1553c1baccd7a90974f7879dd664a8a4b447adec5bd93407bbc5dd0e2c9bd90"
    # Parent evidence remains exact R18. Current v2.29.29 may differ only in MODEL_VERSION.
    assert (parent / "climate_model.py").exists()
    assert sha256(parent / "climate_model.py") == expected_parent
    assert version_neutral_ast_sha256(ROOT / "climate_model.py") == version_neutral_ast_sha256(parent / "climate_model.py")
