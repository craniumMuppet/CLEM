"""Regression checks for v2.29.29 validation semantics and interface parity."""
from __future__ import annotations

from dataclasses import fields
from pathlib import Path

import climate_model_gui
import monte_carlo
from climate_model import ModelConfig, build_parser, config_from_args

ROOT = Path(__file__).resolve().parents[1]


def _config_differences(left: ModelConfig, right: ModelConfig) -> dict[str, tuple[object, object]]:
    return {
        field.name: (getattr(left, field.name), getattr(right, field.name))
        for field in fields(ModelConfig)
        if getattr(left, field.name) != getattr(right, field.name)
    }


def test_cli_defaults_exactly_match_modelconfig() -> None:
    expected = ModelConfig()
    actual = config_from_args(build_parser().parse_args([]))
    assert _config_differences(expected, actual) == {}


def test_desktop_gui_has_no_physical_default_drift() -> None:
    expected = ModelConfig()
    command = climate_model_gui.build_cli_command(climate_model_gui.DEFAULTS)
    actual = config_from_args(build_parser().parse_args(command[2:]))
    differences = _config_differences(expected, actual)

    # The desktop app intentionally opens with a practical scenario and duration;
    # neither is a physical-parameter default. Every other field must be canonical.
    assert set(differences) <= {"scenario", "duration_years"}


def test_dead_pycnocline_relaxation_control_is_not_exposed_as_active_physics() -> None:
    dead = "amoc_pycnocline_relaxation_years"
    assert dead not in climate_model_gui.DEFAULTS
    assert dead not in climate_model_gui.CLI_MAP
    assert all(spec[1] != dead for spec in climate_model_gui.MC_RANGE_SPECS)
    assert dead not in monte_carlo.MONTE_CARLO_PHYSICAL_PARAMETERS
    assert dead not in monte_carlo.PHYSICAL_AMOC_PRIORS

    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "Pycnocline relaxation time (years)" not in app_source
    assert "pycnocline_relaxation_years = st.slider" not in app_source


def test_legacy_pycnocline_relaxation_cli_still_parses_but_is_hidden() -> None:
    parser = build_parser()
    assert "--amoc-pycnocline-relaxation-years" not in parser.format_help()
    config = config_from_args(
        parser.parse_args(["--amoc-pycnocline-relaxation-years", "200"])
    )
    assert config.amoc_pycnocline_relaxation_years == 200.0


def test_combiner_does_not_block_on_nonphysical_extent_or_retrospective_skill() -> None:
    source = (ROOT / "combine_v22923_validation.py").read_text(encoding="utf-8")
    start = source.index("current_validation_prerequisites_passed = bool(")
    end = source.index("independent_prospective_validation_available", start)
    conjunction = source[start:end]

    assert "positive_september_temporal_skill_passed" not in conjunction
    assert "extent_independently_validated" not in conjunction
    assert 'evaluate_r16_prospective' in source
    assert 'R16_PROSPECTIVE_EVIDENCE.json' in source
    assert "retrospective_temporal_skill_is_release_blocking" in source
    assert "extent_metrics_are_release_blocking" in source
    assert '"recent_period_september_failure_is_release_blocking": False' in source


def test_sea_ice_evaluator_exposes_nonblocking_extent_and_prospective_status() -> None:
    source = (ROOT / "sea_ice_validation.py").read_text(encoding="utf-8")
    assert '"historical_scores_are_release_blocking": False' in source
    assert '"extent_metrics_are_release_blocking": False' in source
    assert 'evaluate_r16_prospective' in source
    assert 'R16_PROSPECTIVE_EVIDENCE.json' in source
    assert '"temporal_correlation_is_release_blocking": False' in source
    assert '"temporal_correlation_role": "retrospective_development_diagnostic"' in source

def test_scientific_release_requires_passed_prospective_evidence_and_current_prerequisites() -> None:
    source = (ROOT / "combine_v22923_validation.py").read_text(encoding="utf-8")
    assert "independent_predictive_scientific_validation_passed = bool(" in source
    start = source.index("scientific_release_passed = bool(")
    end = source.index("release_classification", start)
    gate = source[start:end]
    assert "current_validation_prerequisites_passed" in gate
    assert "independent_predictive_scientific_validation_passed" in gate


def test_active_v22929_package_name_uses_clem_identity() -> None:
    from tools.v22929_release_integrity import PACKAGE_NAME
    assert PACKAGE_NAME == "CLEM-v2.29.29-source"


def test_prospective_evaluator_distinguishes_complete_failure_from_pass(tmp_path: Path) -> None:
    import json
    import prospective_validation_r16 as prospective

    protocol = json.loads(prospective.DEFAULT_PROTOCOL.read_text(encoding="utf-8"))
    years = list(range(2027, 2037))
    datasets = [{"name": "synthetic", "raw_sha256": "a" * 64, "processed_sha256": "b" * 64}]
    baseline_names = protocol["statistical_baselines"]

    def evidence(clem_rmse: float) -> dict[str, object]:
        results = {}
        for spec in protocol["variables"]:
            results[spec["name"]] = {
                "clem_rmse": clem_rmse,
                "baseline_rmse": {name: 1.0 for name in baseline_names},
                "metrics": {},
            }
        return {"complete_usable_years": years, "datasets": datasets, "results": results}

    failed_path = tmp_path / "failed.json"
    failed_path.write_text(json.dumps(evidence(2.0)), encoding="utf-8")
    failed = prospective.evaluate(failed_path)
    assert failed["independent_predictive_scientific_validation_complete"] is True
    assert failed["independent_predictive_scientific_validation_status"] == "failed"
    assert failed["independent_predictive_scientific_validation_passed"] is False

    passed_path = tmp_path / "passed.json"
    passed_path.write_text(json.dumps(evidence(0.5)), encoding="utf-8")
    passed = prospective.evaluate(passed_path)
    assert passed["independent_predictive_scientific_validation_complete"] is True
    assert passed["independent_predictive_scientific_validation_status"] == "passed"
    assert passed["independent_predictive_scientific_validation_passed"] is True

