from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_runner():
    path = ROOT / "verify_r16_local.py"
    spec = importlib.util.spec_from_file_location("verify_r16_local_r162", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r16_2_climate_source_is_exact_r16_1_teos_hotfix():
    assert _sha256(ROOT / "climate_model.py") == "08662fef5d83154d8bc43420705a937c6acbc4b52b4677a6e20536d73193506e"


def test_r16_2_delta_provenance_accepts_exact_parent_and_current():
    runner = _load_runner()
    source_hash = runner.sha256(ROOT / "climate_model.py")
    info = runner.validate_r16_teos_delta_provenance(source_hash)
    assert info["r16_parent_source_zip_sha256"] == "e4a890150dc95f8bbb8a4340676b5d1e795c064503299ac258ec154dce5c8ab7"
    assert info["r16_parent_climate_model_sha256"] == "ddcd2272bf2d10ed9d9eacb9fabdc5e65db7fdfc3e3e23a09e85d5bfffc2ba40"
    assert info["r16_1_climate_model_sha256"] == source_hash
    assert info["excluded_changed_top_level_symbols"] == ["validate_initial_amoc_density_margin"]


def test_provenance_manifest_does_not_claim_full_dynamics_equivalence():
    payload = json.loads((ROOT / "R16_TEOS_DELTA_PROVENANCE.json").read_text(encoding="utf-8"))
    assert payload["unchanged_ast_equal"] is True
    assert payload["default_linear_eos_physics_changed"] is False
    assert payload["teos_branch_changed"] is True
    assert payload["excluded_changed_top_level_symbols"] == ["validate_initial_amoc_density_margin"]


def test_r16_2_launcher_selects_teos_delta_only():
    text = (ROOT / "run_r16_2_teos_validation.bat").read_text(encoding="utf-8")
    assert "--validation-only" in text
    assert 'python -c "import gsw"' in text
    runner_text = (ROOT / "verify_r16_local.py").read_text(encoding="utf-8")
    assert "Bundled verified baseline uses a different climate_model.py" not in runner_text
    assert "R16.2 TEOS delta provenance accepted" in runner_text
