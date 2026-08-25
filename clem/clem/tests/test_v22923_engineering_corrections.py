"""Release-integrity regression coverage for v2.29.23."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from arctic_process_budget import evaluate_arctic_process_ledger
from climate_model import MODEL_VERSION, ModelConfig, ProcessClimateModel
from climate_model_gui import DEFAULTS
from release_tree_fingerprint import (
    compute_release_tree_fingerprint,
    fingerprint_mismatches,
)
from setting_metadata import setting_tooltip
from tools.finalize_v22923_status import (
    canonical_relative_path,
    verify_primary_documentation,
)
from tools.package_v22923 import verify_runtime_smoke
from validate_v22923 import structural_area_volume_experiments

ROOT = Path(__file__).resolve().parents[1]


def small_config() -> ModelConfig:
    return replace(
        ModelConfig(),
        duration_years=0.1,
        dt_years=0.05,
        record_every_years=0.05,
        resolution_deg=10.0,
        auto_initialize_from_1850=False,
    )


def production_ledger(
    model_type: type[ProcessClimateModel] = ProcessClimateModel,
) -> tuple[dict[str, object], ...]:
    model = model_type(small_config())
    model.enable_arctic_process_ledger()
    latent = model.arctic_latent_energy_per_m_wyr_m2
    model.state.arctic_atlantic_air_anomaly_c[:] = -3.0
    model.state.arctic_non_atlantic_air_anomaly_c[:] = 3.0
    model.state.arctic_atlantic_ice_energy_anomaly_wyr_m2[:] = -0.4 * latent
    model.state.arctic_non_atlantic_ice_energy_anomaly_wyr_m2[:] = 0.3 * latent
    model.state.arctic_atlantic_ice_concentration_anomaly[:] = 0.1
    model.state.arctic_non_atlantic_ice_concentration_anomaly[:] = -0.15
    model.step(0.0, dt_years=0.05)
    return model.get_arctic_process_ledger()


def test_v22923_identity_and_primary_documentation_are_semantically_current() -> None:
    assert MODEL_VERSION == "2.29.28"
    assert "version = \"2.29.28\"" in (ROOT / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    scientific_constraints = (ROOT / "SCIENTIFIC_CONSTRAINTS.md").read_text(
        encoding="utf-8"
    )
    assert readme.startswith("# Emergent-Sensitivity Global Climate Model v2.29.28")
    assert changelog.startswith("# Changelog\n\n## 2.29.28")
    assert "TEST_RESULTS_V2_29_22.json" not in readme
    assert scientific_constraints.startswith(
        "# Scientific constraints used by v2.29.28\n"
    )


def test_release_tree_fingerprint_covers_all_release_integrity_categories() -> None:
    fingerprint = compute_release_tree_fingerprint(ROOT)
    files = set(fingerprint["files"])
    required = {
        "climate_model.py",
        "climate_model_gui.py",
        "tests/test_v22923_engineering_corrections.py",
        "validate_v22923.py",
        "combine_v22923_validation.py",
        "run_v22923_engineering_tests.py",
        "tools/finalize_v22923_status.py",
        "tools/package_v22923.py",
        "README.md",
        "CHANGELOG.md",
        "SETTING_REFERENCE_GUIDE.md",
        "SCIENTIFIC_CONSTRAINTS.md",
        "pyproject.toml",
        "requirements.lock",
        "data/ssp_pathways_rcmip_v5_1_0.csv",
    }
    assert required <= files
    assert fingerprint["file_count"] == len(fingerprint["files"])
    assert len(fingerprint["aggregate_sha256"]) == 64


def test_release_tree_fingerprint_detects_post_test_source_mutation(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tools").mkdir()
    (tmp_path / "climate_model.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "climate_model_gui.py").write_text("GUI = True\n", encoding="utf-8")
    (tmp_path / "tests" / "test_release.py").write_text(
        "def test_ok():\n    assert True\n", encoding="utf-8"
    )
    (tmp_path / "tools" / "package.py").write_text("PASS = True\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Release\n", encoding="utf-8")
    before = compute_release_tree_fingerprint(tmp_path)
    (tmp_path / "climate_model_gui.py").write_text(
        "def broken(:\n", encoding="utf-8"
    )
    after = compute_release_tree_fingerprint(tmp_path)
    mismatches = fingerprint_mismatches(before, after)
    assert "climate_model_gui.py" in mismatches["changed"]
    assert before["aggregate_sha256"] != after["aggregate_sha256"]


def test_production_ledger_closes_actual_receiving_reservoirs() -> None:
    ledger = production_ledger()
    required_receiver_fields = {
        "initial_arctic_mixed_layer_ocean_heat_wyr_m2",
        "post_transfer_arctic_mixed_layer_ocean_heat_wyr_m2",
        "final_arctic_mixed_layer_ocean_heat_wyr_m2",
        "initial_lower_latitude_atlantic_ocean_heat_wyr_m2",
        "final_lower_latitude_atlantic_ocean_heat_wyr_m2",
        "initial_lower_latitude_non_atlantic_ocean_heat_wyr_m2",
        "final_lower_latitude_non_atlantic_ocean_heat_wyr_m2",
    }
    assert required_receiver_fields <= set(ledger[0])
    result = evaluate_arctic_process_ledger(ledger, require_activity=False)
    assert result["entry_count"] == 8
    assert result["actual_receiving_reservoirs_verified"] is True
    assert result["energy_budget_closed"] is True
    assert result["area_budget_closed"] is True
    assert result["maximum_energy_closure_residual_wyr_m2"] <= 1.0e-10
    assert (
        result["maximum_lower_latitude_compensation_spatial_residual_wyr_m2"]
        <= 1.0e-10
    )


def test_suppressed_production_ocean_receiver_is_detected() -> None:
    class SuppressedArcticOceanReceiver(ProcessClimateModel):
        def _apply_arctic_mixed_layer_internal_transfer(
            self,
            ocean_temperature_anomaly_c: np.ndarray,
            transfer_wyr_m2: np.ndarray,
        ) -> np.ndarray:
            return np.asarray(ocean_temperature_anomaly_c, dtype=float).copy()

    result = evaluate_arctic_process_ledger(
        production_ledger(SuppressedArcticOceanReceiver),
        require_activity=False,
    )
    assert result["passed"] is False
    assert result["actual_receiving_reservoirs_verified"] is False
    assert result["maximum_surface_to_arctic_ocean_residual_wyr_m2"] > 1.0e-10


def test_process_gate_uses_actual_receivers_and_implementation_mutants() -> None:
    result = structural_area_volume_experiments(ModelConfig(resolution_deg=10.0))
    budgets = result["process_budget_experiments"]
    assert (
        budgets["method"]
        == "production_ProcessClimateModel_step_actual_receiving_reservoir_ledger"
    )
    assert budgets["passed"] is True
    assert budgets["ledger_evaluation"]["actual_receiving_reservoirs_verified"] is True
    assert budgets["mutation_checks"] == {
        "suppressed_arctic_ocean_receiver_detected": True,
        "reversed_arctic_ocean_receiver_detected": True,
        "misrouted_lower_latitude_ocean_receiver_detected": True,
    }


def test_current_workflow_requires_tree_binding_and_packaging_smokes() -> None:
    runner = (ROOT / "run_v22923_engineering_tests.py").read_text(encoding="utf-8")
    finalizer = (ROOT / "tools" / "finalize_v22923_status.py").read_text(
        encoding="utf-8"
    )
    packager = (ROOT / "tools" / "package_v22923.py").read_text(encoding="utf-8")
    assert "compute_release_tree_fingerprint" in runner
    assert "tree_unchanged_during_pytest" in runner
    assert "verify_release_tree_fingerprint(root, tree_fingerprint)" in finalizer
    assert "verify_release_tree_fingerprint(ROOT, tree_fingerprint)" in packager
    assert "compileall" in packager
    assert "verify_streamlit_dependency_contract" in packager
    assert "core_import_smoke_passed" in packager
    assert "gui_startup_smoke_test.py" in packager
    assert "xvfb-run" in packager


def test_current_entrypoints_and_gui_metadata_are_complete() -> None:
    assert canonical_relative_path("validate_v22923.py") == Path("validate_v22923.py")
    with pytest.raises(SystemExit):
        canonical_relative_path("/mnt/data/build/validate_v22923.py")
    with pytest.raises(SystemExit):
        canonical_relative_path("../validate_v22923.py")
    assert "arctic_ice_area_formation_temperature_scale" in DEFAULTS
    assert "new-ice formation" in setting_tooltip(
        "arctic_ice_area_formation_temperature_scale"
    )
    runner = (ROOT / "run_v22923_engineering_tests.py").read_text(encoding="utf-8")
    combiner = (ROOT / "combine_v22923_validation.py").read_text(encoding="utf-8")
    packager = (ROOT / "tools" / "package_v22923.py").read_text(encoding="utf-8")
    assert "TEST_EVENTS_V2_29_23.ndjson" in runner
    assert "TEST_RESULTS_V2_29_23.junit.xml" in runner
    assert 'output_candidate = args.output_dir / "TEST_RESULTS_V2_29_23.json"' in combiner
    assert "skip-relocation-check" in packager


def test_documented_tool_entrypoints_import_from_release_root() -> None:
    for relative in (
        "tools/finalize_v22923_status.py",
        "tools/package_v22923.py",
    ):
        completed = subprocess.run(
            [sys.executable, str(ROOT / relative), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert completed.returncode == 0, (
            relative,
            completed.stdout,
            completed.stderr,
        )


def test_packaging_runtime_smoke_passes_in_minimal_release_environment() -> None:
    result = verify_runtime_smoke(ROOT)
    assert result["compileall_passed"] is True
    assert result["core_import_smoke_passed"] is True
    assert result["streamlit_dependency_contract_passed"] is True
    assert result["streamlit_dependency_pin"] == "streamlit==1.60.0"
    assert result["gui_command_builder_smoke_passed"] is True
    assert result["desktop_gui_startup_smoke_passed"] is True
