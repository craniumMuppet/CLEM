"""Run retained standalone regressions in hard-isolated subprocesses.

Several historical scripts execute many independent model experiments from one
Python interpreter. This module preserves the same regression functions while
giving every function a fresh interpreter. Pytest setup, the test call, fixture
teardown, finalizers, and interpreter shutdown all complete normally; no forced
process exit is used.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def run_script(name: str, timeout: int = 600) -> None:
    script = str(ROOT / name)
    expression = f"import runpy; runpy.run_path({script!r}, run_name='__main__')"
    command = [sys.executable, "-u", "-c", expression]
    if (
        name in {"gui_smoke_test.py", "gui_layout_test.py"}
        and os.name != "nt"
        and shutil.which("xvfb-run")
    ):
        command = ["xvfb-run", "-a", *command]
    subprocess.run(command, cwd=ROOT, check=True, timeout=timeout)


def run_function(module: str, function: str, timeout: int = 1200) -> None:
    expression = (
        f"import {module} as module_under_test; "
        f"module_under_test.{function}(); "
        f"print('PASS: {module}.{function}', flush=True)"
    )
    subprocess.run(
        [sys.executable, "-u", "-c", expression],
        cwd=ROOT,
        check=True,
        timeout=timeout,
    )


SMOKE_FUNCTIONS = [
    ("smoke_test", "test_control_stability"),
    ("smoke_test", "test_amoc_heat_redistribution_is_conservative"),
    ("smoke_test", "test_salt_conservation_and_freshwater_routing"),
    ("smoke_test", "test_directional_advection_and_fovs"),
    ("smoke_test", "test_nonlinear_hosing_response"),
    ("smoke_test", "test_physical_atlantic_localization"),
    ("smoke_test", "test_post_1850_initialization_matches_continuous_run"),
    ("smoke_test", "test_separated_freshwater_components_and_legacy_override"),
    ("smoke_test", "test_nondivisible_timestep_and_summary_compatibility"),
]

SLOW_FUNCTIONS = [
    ("amoc_dynamics_fix_test", "test_control_equilibrium"),
    ("amoc_dynamics_fix_test", "test_hybrid_ssp_has_material_2100_weakening_and_bounded_long_horizon"),
    ("amoc_dynamics_fix_test", "test_annual_arctic_compatibility_family_retains_legacy_hybrid_range"),
    ("amoc_dynamics_fix_test", "test_ssp585_weakens_more_than_hybrid_mitigation"),
    ("amoc_persistent_collapse_test", "test_no_boolean_collapse_command_controls_dynamics"),
    ("amoc_persistent_collapse_test", "test_one_percent_ramp_collapses_continuously"),
    ("amoc_persistent_collapse_test", "test_control_branch_remains_active"),
    ("long_hold_salinity_exchange_test", "test_validation"),
    ("long_hold_salinity_exchange_test", "test_control_state_is_exactly_unchanged"),
    ("long_hold_salinity_exchange_test", "test_long_capped_co2_hold_has_no_restart_overshoot"),
    ("structural_fixes_v2_17_0_test", "test_finite_greenland_reservoir"),
    ("structural_fixes_v2_17_0_test", "test_absolute_density_margin_screening"),
    ("structural_fixes_v2_17_0_test", "test_reversal_is_explicit_opt_in"),
    ("structural_fixes_v2_17_0_test", "test_joint_amoc_calibration_targets"),
    ("structural_fixes_v2_17_0_test", "test_long_term_ssp245_structural_branch"),
    ("v2_17_1_validation_test", "test_missing_validation_checks"),
    ("v2_17_1_validation_test", "test_cross_resolution_initialization_and_control"),
    ("v2_17_1_validation_test", "test_default_five_degree_migrated_compatibility"),
    ("v2_17_1_validation_test", "test_optional_heun_coupling"),
    ("hybrid_ssp_transition_test", "test_preserves_switch_level"),
    ("hybrid_ssp_transition_test", "test_late_switch_does_not_reset_to_low_pathway"),
    ("hybrid_ssp_transition_test", "test_identical_pathways_are_unchanged"),
    ("hybrid_ssp_transition_test", "test_full_response_has_no_switch_cooling_or_amoc_rebound"),
    ("co2_target_sweep_test", "test_linear_ramp_hold"),
    ("co2_target_sweep_test", "test_target_sequence"),
    ("co2_target_sweep_test", "test_gui_command"),
    ("co2_target_sweep_test", "test_small_sweep"),
    ("full_regression_test", "test_equilibrium_continuation_is_continuous_and_conservative"),
    ("full_regression_test", "test_long_ramp_hold_has_no_discrete_target_jump"),
    ("full_regression_test", "test_ssp585_transient_response"),
    ("review_fixes_v2_21_0_test", "test_whole_domain_equilibrium_salt_closure"),
    ("review_fixes_v2_21_0_test", "test_smooth_stability_and_transient_validation"),
    ("review_fixes_v2_21_0_test", "test_collapse_threshold_semantics"),
    ("review_fixes_v2_21_0_test", "test_calibration_outputs_are_not_labeled_validation"),
    ("review_fixes_v2_21_0_test", "test_reversible_regional_freshwater_and_regrowth"),
]

CALIBRATION_FUNCTIONS = [
    ("calibration_fix_test", "test_default_feedback_decomposition"),
    ("calibration_fix_test", "test_total_atlantic_heat_transport_definition"),
    ("calibration_fix_test", "test_ohue_uses_explicit_ocean_heat_uptake"),
    ("calibration_fix_test", "test_grouped_likelihood_outputs"),
    ("calibration_fix_test", "test_physical_priors_do_not_duplicate_likelihood_intervals"),
    ("calibration_fix_test", "test_parameter_specific_prior_marginals_and_correlations"),
]


@pytest.mark.slow
@pytest.mark.parametrize(("module", "function"), SMOKE_FUNCTIONS)
def test_legacy_smoke_functions(module: str, function: str) -> None:
    run_function(module, function, timeout=600)


@pytest.mark.slow
@pytest.mark.parametrize(("module", "function"), SLOW_FUNCTIONS)
def test_legacy_scientific_functions(module: str, function: str) -> None:
    run_function(module, function, timeout=1500)


@pytest.mark.slow
@pytest.mark.parametrize(
    "script",
    ["percent_ramp_hold_test.py", "sensitivity_convergence_test.py"],
)
def test_legacy_scientific_scripts_without_test_functions(script: str) -> None:
    run_script(script, timeout=1500)


@pytest.mark.slow
@pytest.mark.calibration
@pytest.mark.parametrize(("module", "function"), CALIBRATION_FUNCTIONS)
def test_legacy_calibration_functions(module: str, function: str) -> None:
    # The 400-year equilibrium diagnostic can exceed 25 minutes on a single
    # shared CI core.  Keep a bounded timeout while allowing the calculation
    # to finish without converting a healthy run into a false failure.
    run_function(module, function, timeout=2400)


@pytest.mark.gui
@pytest.mark.parametrize("script", ["gui_smoke_test.py", "gui_layout_test.py"])
def test_legacy_gui_scripts(script: str) -> None:
    run_script(script, timeout=300)
