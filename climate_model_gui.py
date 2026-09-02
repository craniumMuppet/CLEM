#!/usr/bin/env python3
"""Desktop GUI for the Coupled Low-complexity Earth Model.

The interface is intentionally implemented with Python's standard-library
Tkinter package so no additional GUI framework is required. The GUI launches
``climate_model.py`` as a child process, streams its console output, and keeps
the interface responsive while the simulation is running.
"""

from __future__ import annotations

import json
import os
import queue
import shlex
import signal
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

from run_state import describe_run_state, load_run_state
from setting_metadata import setting_tooltip
from climate_model import (
    ARCTIC_MINIMUM_EFFECTIVE_WARM_DAMPING_WM2_K,
    MODEL_NAME,
    MODEL_VERSION,
    ModelConfig,
)

APP_TITLE = f"{MODEL_NAME} {MODEL_VERSION}"
BASE_DIR = Path(__file__).resolve().parent
MODEL_SCRIPT = BASE_DIR / "climate_model.py"
MONTE_CARLO_SCRIPT = BASE_DIR / "monte_carlo.py"
CO2_TARGET_SWEEP_SCRIPT = BASE_DIR / "co2_target_sweep.py"

SCENARIOS = [
    "constant",
    "linear",
    "one_percent",
    "percent_ramp_hold",
    "overshoot",
    "step_2x",
    "ssp126",
    "ssp245",
    "ssp460",
    "ssp585",
    "hybrid_ssp",
]
SSP_SCENARIOS = {"ssp126", "ssp245", "ssp460", "ssp585"}
FORCING_MODES = ["total_effective", "co2_only"]
CO2_FORCING_FORMULAS = ["logarithmic", "meinshausen2020"]
COMPENSATION_MODES = ["external", "atlantic"]
AMOC_SOUTHERN_OCEAN_STRUCTURES = ["fixed", "warming_sensitive"]
AMOC_INDO_PACIFIC_MODES = ["none", "diagnostic", "interactive"]
MODEL_DEFAULT_CONFIG = ModelConfig()


def terminate_process_tree(
    process: subprocess.Popen[str],
    *,
    graceful_timeout_seconds: float = 3.0,
) -> tuple[bool, str]:
    """Terminate a subprocess and every descendant process.

    Monte Carlo runs create a parent Python process plus a pool of worker
    processes. Calling ``Popen.terminate()`` only stops the parent on Windows,
    leaving the worker pool alive. This helper starts every simulation in its
    own process group and then terminates that whole group/tree.

    Returns ``(success, details)``. A process that has already exited is
    treated as successfully stopped.
    """

    if process.poll() is not None:
        return True, "Process had already exited."

    pid = process.pid
    try:
        if os.name == "nt":
            # /T includes all descendants; /F is required because Python
            # multiprocessing workers do not reliably handle CTRL_BREAK.
            completed = subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            try:
                process.wait(timeout=graceful_timeout_seconds)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=graceful_timeout_seconds)
            output = (completed.stdout or "").strip()
            success = process.poll() is not None
            details = output or (
                "Process tree terminated." if success else "taskkill returned no output."
            )
            return success, details

        # POSIX: the child is started in a new session, so its PID is also the
        # process-group ID. SIGTERM allows orderly cleanup; SIGKILL is fallback.
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except ProcessLookupError:
            return True, "Process group had already exited."
        try:
            process.wait(timeout=graceful_timeout_seconds)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=graceful_timeout_seconds)
        return process.poll() is not None, "Process group terminated."
    except (OSError, subprocess.SubprocessError) as exc:
        # Last-resort direct kill of the parent. This is not sufficient by
        # itself for a worker pool, but avoids leaving the main process alive.
        try:
            process.kill()
            process.wait(timeout=graceful_timeout_seconds)
        except (OSError, subprocess.TimeoutExpired):
            pass
        return process.poll() is not None, str(exc)

MONTE_CARLO_SAMPLING = ["uniform", "triangular", "loguniform"]
MONTE_CARLO_DESIGNS = ["sobol", "latin_hypercube", "random"]
MONTE_CARLO_CONSTRAINT_MODES = ["none", "ar6", "ar6_amoc"]

# id, ModelConfig field, label, default minimum, default maximum, units/help
MC_RANGE_SPECS: list[tuple[str, str, str, str, str, str]] = [
    ("co2_erf", "co2_doubling_erf_wm2", "CO2 forcing per doubling", "3.55", "4.32", "W/m2"),
    ("longwave_factor", "longwave_spectral_factor", "Longwave spectral factor", "0.92", "1.04", "fraction"),
    ("relative_humidity", "relative_humidity", "Relative humidity", "0.72", "0.84", "fraction"),
    ("lapse_weight", "moist_lapse_rate_weight", "Moist lapse-rate weight", "0.20", "0.55", "fraction"),
    ("water_vapor", "water_vapor_emission_height_km_per_lnq", "Water-vapour emission-height response", "0.75", "1.25", "km per ln(q/q0)"),
    ("low_cloud", "low_cloud_loss_fraction_per_k", "Low-cloud loss", "0.001", "0.010", "fraction/K"),
    ("low_cloud_moisture", "low_cloud_moisture_gain_fraction_per_lnq", "Low-cloud moisture response", "0.002", "0.018", "fraction/ln(q/q0)"),
    ("high_cloud", "high_cloud_temperature_coupling", "High-cloud temperature coupling", "0.15", "0.45", "fraction"),
    ("sea_ice_albedo", "sea_ice_albedo", "Sea-ice albedo", "0.45", "0.70", "fraction"),
    ("snow_albedo", "snow_albedo", "Snow albedo", "0.50", "0.80", "fraction"),
    ("sea_ice_transition", "sea_ice_transition_c", "Sea-ice transition centre", "-2.2", "-1.4", "degC"),
    ("sea_ice_width", "sea_ice_transition_width_c", "Sea-ice transition width", "2.0", "5.0", "degC"),
    ("winter_lead_closure", "arctic_winter_lead_closure_fraction", "Optional winter mechanical lead closure", "0.00", "0.60", "fraction"),
    ("snow_transition", "snow_transition_c", "Snow transition centre", "-2.5", "0.5", "degC"),
    ("snow_width", "snow_transition_width_c", "Snow transition width", "2.0", "5.0", "degC"),
    ("mixed_capacity", "ocean_mixed_layer_heat_capacity_wyr_m2_k", "Mixed-layer heat capacity", "6.0", "12.0", "W yr/m2/K"),
    ("deep_capacity", "deep_ocean_heat_capacity_wyr_m2_k", "Deep-ocean heat capacity", "80", "160", "W yr/m2/K"),
    ("ocean_exchange", "ocean_heat_exchange_wm2_k", "Surface-deep ocean exchange", "0.80", "2.00", "W/m2/K"),
    ("meridional", "meridional_diffusion_wm2_k", "Meridional heat diffusion", "0.35", "0.75", "W/m2/K"),
    ("hydrological_fw", "hydrological_freshwater_sv_per_k", "Hydrological-cycle freshwater sensitivity", "0.002", "0.012", "Sv/K"),
    ("hydrological_north_fraction", "hydrological_freshwater_north_fraction", "Hydrological freshwater routed north", "0.50", "0.90", "fraction"),
    ("greenland_fw", "greenland_freshwater_sv_per_k", "Greenland freshwater sensitivity", "0.002", "0.010", "Sv/K"),
    ("greenland_adjust", "greenland_freshwater_adjustment_years", "Greenland freshwater response time", "30", "150", "years"),
    ("greenland_depletion", "greenland_depletion_exponent", "Greenland depletion exponent", "0.5", "2.0", ""),
    ("greenland_max_flux", "greenland_max_freshwater_sv", "Maximum Greenland freshwater flux", "0.005", "0.040", "Sv"),
    ("greenland_dynamic_share", "greenland_dynamic_discharge_fraction", "Greenland dynamic-discharge share", "0.00", "0.30", "fraction"),
    ("greenland_pdd", "greenland_pdd_melt_factor_gt_per_degree_day", "Greenland PDD melt factor", "0.20", "0.70", "Gt/degree-day"),
    ("greenland_retention", "greenland_meltwater_retention_fraction", "Greenland meltwater retention", "0.15", "0.55", "fraction"),
    ("hosing", "freshwater_hosing_sv", "Explicit freshwater hosing", "0.000", "0.200", "Sv"),
    ("amoc_reference", "amoc_reference_sv", "Reference AMOC", "14.0", "19.0", "Sv"),
    ("amoc_temp", "amoc_temperature_density_coupling", "AMOC northern-stratification coupling", "0.40", "1.00", "fraction"),
    ("amoc_adjust", "amoc_adjustment_years", "AMOC adjustment time", "3.0", "20.0", "years"),
    ("amoc_heat", "amoc_heat_transport_pw_per_sv", "Overturning heat transport", "0.035", "0.050", "PW/Sv"),
    ("amoc_surface_heat", "amoc_surface_heat_coupling_fraction", "Surface AMOC heat coupling", "0.025", "0.20", "fraction"),
    ("amoc_heat_damping", "amoc_heat_response_damping_wm2_k", "AMOC temperature damping", "0.8", "2.5", "W/m2/K"),
    ("amoc_density", "amoc_density_transport_exponent", "AMOC density exponent", "0.8", "2.5", ""),
    ("amoc_depth", "amoc_hydraulic_depth_exponent", "AMOC hydraulic depth exponent", "0.5", "1.2", ""),
    ("pyc_feedback", "amoc_pycnocline_feedback_strength", "Pycnocline AMOC feedback strength", "0.00", "0.30", "fraction"),
    ("conv_scale", "amoc_convection_density_scale_factor", "Convection density scale factor", "1.2", "6.0", "factor"),
    ("conv_min", "amoc_convection_minimum_fraction", "Residual convection fraction", "0.00", "0.15", "fraction"),
    ("conv_mix", "amoc_convective_mixing_reference_sv", "Convective salt exchange", "1.0", "10.0", "Sv"),
    ("conv_mix_exp", "amoc_convective_mixing_exponent", "Convective mixing exponent", "1.0", "4.0", ""),
    ("conv_feedback", "amoc_convection_entrainment_feedback", "Convective entrainment feedback", "0.00", "0.22", "ratio"),
    ("conv_adjust", "amoc_convection_adjustment_years", "Convection weakening time", "10", "40", "years"),
    ("conv_recover", "amoc_convection_recovery_years", "Convection recovery time", "10", "300", "years"),
    ("amoc_eddy", "amoc_eddy_depth_exponent", "AMOC eddy depth exponent", "1.0", "2.5", ""),
    ("pycnocline", "amoc_initial_pycnocline_depth_m", "Initial pycnocline depth", "550", "850", "m"),
    ("ekman", "amoc_ekman_inflow_sv", "Southern Ocean Ekman inflow", "20.0", "30.0", "Sv"),
    ("upwelling", "amoc_upwelling_reference_sv", "Low-latitude upwelling", "3.0", "7.0", "Sv"),
    ("eddy_outflow", "amoc_eddy_outflow_reference_sv", "Southern Ocean eddy outflow", "9.0", "16.0", "Sv"),
    ("north_gyre", "amoc_north_tropical_gyre_sv", "Northern gyre exchange", "2.0", "8.0", "Sv"),
    ("south_gyre", "amoc_tropical_southern_gyre_sv", "Southern gyre exchange", "5.0", "15.0", "Sv"),
    ("initial_fovs", "initial_fovs_sv", "Initial FovS at 34.5 S", "-0.33", "0.03", "Sv"),
    ("southern_salinity", "initial_southern_salinity_psu", "Initial Southern Ocean salinity", "34.20", "34.90", "PSU"),
    ("north_salinity", "initial_north_salinity_psu", "Initial northern/deep salinity", "34.85", "35.45", "PSU"),
]

DEFAULTS: dict[str, Any] = {
    "scenario": "ssp245",
    "run_all_ssp": False,
    "resume_all_ssp": False,
    "start_year": "1850",
    "years": "250",
    "dt": "0.05",
    "output": "outputs_ssp245",
    "forcing_mode": "total_effective",
    "co2_doubling_erf": "3.93",
    "co2_forcing_formula": MODEL_DEFAULT_CONFIG.co2_forcing_formula,
    "co2_forcing_reference_n2o": "270.1",
    "co2_start": "278.3",
    "co2_end": "450",
    "co2_peak": "700",
    "one_percent_cap": "",
    "co2_growth_cap": "1200",
    "co2_hold_years": "200",
    "percent_ramp_compare_rates": "0.5,1,2,3,5",
    "peak_fraction": "0.60",
    "ssp_before": "ssp585",
    "ssp_after": "ssp245",
    "switch_year": "2020",
    "transition_years": "0",
    "additional_forcing": "0",
    "relative_humidity": "0.78",
    "moist_lapse_rate_weight": "0.30",
    "seasonal_arctic_enabled": bool(MODEL_DEFAULT_CONFIG.seasonal_arctic_enabled),
    "arctic_lapse_rate_feedback": f"{MODEL_DEFAULT_CONFIG.arctic_lapse_rate_feedback_wm2_k:.2f}",
    "arctic_module_start_latitude": f"{MODEL_DEFAULT_CONFIG.arctic_module_start_latitude_deg:.1f}",
    "arctic_reference_air_seasonal_amplitude": f"{MODEL_DEFAULT_CONFIG.arctic_reference_air_seasonal_amplitude_c:.1f}",
    "arctic_moisture_transport": f"{MODEL_DEFAULT_CONFIG.arctic_moisture_transport_wm2_per_k:.2f}",
    "arctic_winter_transport_enhancement": f"{MODEL_DEFAULT_CONFIG.arctic_winter_transport_enhancement:.1f}",
    "arctic_winter_transport_temperature_scale": f"{MODEL_DEFAULT_CONFIG.arctic_winter_transport_temperature_scale_c:.1f}",
    "arctic_dry_static_transport": f"{MODEL_DEFAULT_CONFIG.arctic_dry_static_transport_wm2_k:.2f}",
    "arctic_open_water_stable_exchange": f"{MODEL_DEFAULT_CONFIG.arctic_open_water_stable_exchange_wm2_k:.2f}",
    "arctic_open_water_unstable_exchange": f"{MODEL_DEFAULT_CONFIG.arctic_open_water_unstable_exchange_wm2_k:.1f}",
    "arctic_open_water_exchange_transition": f"{MODEL_DEFAULT_CONFIG.arctic_open_water_exchange_transition_c:.2f}",
    "arctic_transient_shortwave_scale": f"{MODEL_DEFAULT_CONFIG.arctic_transient_shortwave_scale:.2f}",
    "arctic_interface_longwave_damping": f"{MODEL_DEFAULT_CONFIG.arctic_interface_longwave_damping_wm2_k:.2f}",
    "arctic_ice_surface_exchange": f"{MODEL_DEFAULT_CONFIG.arctic_ice_surface_exchange_wm2_k:.2f}",
    "arctic_basal_ocean_exchange": f"{MODEL_DEFAULT_CONFIG.arctic_basal_ocean_exchange_wm2_k:.2f}",
    "arctic_open_water_ocean_exchange": f"{MODEL_DEFAULT_CONFIG.arctic_open_water_ocean_exchange_wm2_k:.2f}",
    "arctic_lateral_ocean_heat_transport": f"{MODEL_DEFAULT_CONFIG.arctic_lateral_ocean_heat_transport_wm2_per_ice_fraction:.1f}",
    "arctic_forced_ocean_heat_convergence": f"{MODEL_DEFAULT_CONFIG.arctic_forced_ocean_heat_convergence_wm2_per_k:.2f}",
    "arctic_forced_ocean_heat_convergence_onset": f"{MODEL_DEFAULT_CONFIG.arctic_forced_ocean_heat_convergence_onset_warming_c:.2f}",
    "arctic_forced_ocean_heat_convergence_saturation_scale": f"{MODEL_DEFAULT_CONFIG.arctic_forced_ocean_heat_convergence_saturation_scale_c:.2f}",
    "arctic_forced_ocean_heat_convergence_ice_fraction_exponent": f"{MODEL_DEFAULT_CONFIG.arctic_forced_ocean_heat_convergence_ice_fraction_exponent:.2f}",
    "arctic_phase_restoring_deficit_saturation": f"{MODEL_DEFAULT_CONFIG.arctic_phase_restoring_deficit_saturation_fraction:.2f}",
    "arctic_phase_restoring_max_deficit_flux": f"{MODEL_DEFAULT_CONFIG.arctic_phase_restoring_max_deficit_flux_wm2:.2f}",
    "arctic_new_ice_local_thickness": f"{MODEL_DEFAULT_CONFIG.arctic_new_ice_local_thickness_m:.2f}",
    "arctic_full_cover_equivalent_thickness": f"{MODEL_DEFAULT_CONFIG.arctic_full_cover_equivalent_thickness_m:.2f}",
    "arctic_max_equivalent_thickness": f"{MODEL_DEFAULT_CONFIG.arctic_max_equivalent_thickness_m:.2f}",
    "arctic_max_local_ice_thickness": f"{MODEL_DEFAULT_CONFIG.arctic_max_local_ice_thickness_m:.2f}",
    "arctic_ice_concentration_exponent": f"{MODEL_DEFAULT_CONFIG.arctic_ice_concentration_exponent:.2f}",
    "arctic_ice_area_formation_temperature_scale": f"{MODEL_DEFAULT_CONFIG.arctic_ice_area_formation_temperature_scale_c:.2f}",
    "arctic_ice_area_formation_volume_sensitivity": f"{MODEL_DEFAULT_CONFIG.arctic_ice_area_formation_volume_sensitivity:.2f}",
    "arctic_ice_area_formation_support_floor": f"{MODEL_DEFAULT_CONFIG.arctic_ice_area_formation_support_floor:.2f}",
    "arctic_ice_area_melt_thickness": f"{MODEL_DEFAULT_CONFIG.arctic_ice_area_melt_thickness_m:.2f}",
    "arctic_ice_area_lateral_melt_efficiency": f"{MODEL_DEFAULT_CONFIG.arctic_ice_area_lateral_melt_efficiency:.2f}",
    "arctic_ice_area_thinning_melt_amplification": f"{MODEL_DEFAULT_CONFIG.arctic_ice_area_thinning_melt_amplification:.2f}",
    "arctic_ice_area_thick_pack_resistance_exponent": f"{MODEL_DEFAULT_CONFIG.arctic_ice_area_thick_pack_resistance_exponent:.2f}",
    "arctic_ice_area_compaction_years": f"{MODEL_DEFAULT_CONFIG.arctic_ice_area_compaction_years:.3f}",
    "arctic_ice_area_ridging_threshold": f"{MODEL_DEFAULT_CONFIG.arctic_ice_area_ridging_threshold:.2f}",
    "arctic_ice_area_ridging_rate": f"{MODEL_DEFAULT_CONFIG.arctic_ice_area_ridging_fraction_per_year:.2f}",
    "arctic_ice_area_divergence_rate": f"{MODEL_DEFAULT_CONFIG.arctic_ice_area_divergence_fraction_per_year:.3f}",
    "arctic_ice_area_thin_pack_divergence_rate": f"{MODEL_DEFAULT_CONFIG.arctic_ice_area_thin_pack_divergence_fraction_per_year:.2f}",
    "arctic_greenland_marine_influence": f"{MODEL_DEFAULT_CONFIG.arctic_greenland_marine_influence:.2f}",
    "arctic_winter_lead_closure_fraction": f"{MODEL_DEFAULT_CONFIG.arctic_winter_lead_closure_fraction:.2f}",
    "arctic_winter_lead_closure_onset_fraction": f"{MODEL_DEFAULT_CONFIG.arctic_winter_lead_closure_onset_fraction:.3f}",
    "arctic_winter_lead_closure_temperature_scale": f"{MODEL_DEFAULT_CONFIG.arctic_winter_lead_closure_temperature_scale_c:.1f}",
    "arctic_atlantic_reference_ocean_temperature": f"{MODEL_DEFAULT_CONFIG.arctic_atlantic_reference_ocean_temperature_c:.2f}",
    "arctic_non_atlantic_reference_ocean_temperature": f"{MODEL_DEFAULT_CONFIG.arctic_non_atlantic_reference_ocean_temperature_c:.2f}",
    "arctic_reference_ocean_heat_capacity": f"{MODEL_DEFAULT_CONFIG.arctic_reference_ocean_heat_capacity_wyr_m2_k:.1f}",
    "arctic_reference_ocean_restoring": f"{MODEL_DEFAULT_CONFIG.arctic_reference_ocean_restoring_wm2_k:.1f}",
    "arctic_air_memory_years": f"{MODEL_DEFAULT_CONFIG.arctic_air_low_pass_years:.2f}",
    "longwave_spectral_factor": "0.98",
    "water_vapor_height": f"{MODEL_DEFAULT_CONFIG.water_vapor_emission_height_km_per_lnq:g}",
    "low_cloud_loss": "0.0045",
    "high_cloud_coupling": "0.25",
    "ocean_exchange": "1.45",
    "meridional_diffusion": "0.52",
    "freshwater_hosing": "0",
    "warming_freshwater": "",
    "hydrological_freshwater": "0.006",
    "hydrological_freshwater_north_fraction": "0.70",
    "greenland_freshwater": "0.005",
    "greenland_freshwater_threshold": "0.0",
    "greenland_freshwater_adjustment_years": "45",
    "greenland_initial_ice_mass_gt": "2.85e6",
    "greenland_depletion_exponent": "1.0",
    "greenland_max_freshwater_sv": f"{MODEL_DEFAULT_CONFIG.greenland_max_freshwater_sv:g}",
    "greenland_surface_mass_balance_enabled": True,
    "greenland_dynamic_discharge_fraction": "0.10",
    "greenland_reference_annual_temperature_c": "-10.5",
    "greenland_reference_seasonal_amplitude_c": "13.5",
    "greenland_pdd_melt_factor_gt_per_degree_day": "0.38",
    "greenland_baseline_precipitation_gt_per_year": "700",
    "greenland_precipitation_fraction_per_k": "0.05",
    "greenland_snow_rain_transition_c": "1.0",
    "greenland_snow_rain_transition_width_c": "2.0",
    "greenland_meltwater_retention_fraction": "0.35",
    "greenland_retention_loss_fraction_per_k": "0.04",
    "amoc_temperature_coupling": "1.0",
    "amoc_adjustment_years": "8.0",
    "amoc_heat_transport": "0.040",
    "amoc_surface_heat_coupling": f"{MODEL_DEFAULT_CONFIG.amoc_surface_heat_coupling_fraction:g}",
    "amoc_heat_response_damping": f"{MODEL_DEFAULT_CONFIG.amoc_heat_response_damping_wm2_k:g}",
    "atlantic_gyre_heat_transport": "0.52",
    "amoc_density_exponent": f"{MODEL_DEFAULT_CONFIG.amoc_density_transport_exponent:.2f}",
    "amoc_depth_exponent": "1.00",
    "amoc_pycnocline_feedback_strength": f"{MODEL_DEFAULT_CONFIG.amoc_pycnocline_feedback_strength:g}",
    "amoc_convection_density_scale_factor": f"{MODEL_DEFAULT_CONFIG.amoc_convection_density_scale_factor:.2f}",
    "amoc_convection_minimum_fraction": "0.02",
    "amoc_convective_mixing_reference_sv": "5.0",
    "amoc_convective_mixing_exponent": "2.0",
    "amoc_convection_entrainment_feedback": "0.00",
    "amoc_convection_adjustment_years": "20",
    "amoc_convection_recovery_years": f"{MODEL_DEFAULT_CONFIG.amoc_convection_recovery_years:g}",
    "amoc_eddy_depth_exponent": "2.00",
    "amoc_pycnocline_depth": "700",
    "amoc_pycnocline_area": "1.0e14",
    "amoc_ekman_inflow": "25.0",
    "amoc_upwelling": "5.0",
    "amoc_eddy_outflow": "13.0",
    "amoc_north_gyre": "5.0",
    "amoc_southern_gyre": "10.0",
    "amoc_southern_external_exchange": "5.0",
    "amoc_south_atlantic_external_exchange": f"{MODEL_DEFAULT_CONFIG.amoc_south_atlantic_external_exchange_sv:g}",
    "initial_fovs": "-0.15",
    "fovs_reference_salinity": "35.0",
    "freshwater_start_fraction": "0.25",
    "freshwater_ramp_years": "40",
    "freshwater_compensation_mode": "external",
    "freshwater_compensation_tropical_fraction": "0.70",
    "amoc_collapse_threshold": "6.0",
    "amoc_reference_density_driver": f"{MODEL_DEFAULT_CONFIG.amoc_reference_density_driver:.8g}",
    "amoc_minimum_initial_density_ratio": "0.68",
    "amoc_maximum_initial_density_ratio": "1.25",
    "amoc_enforce_initial_density_constraint": True,
    "amoc_allow_reversal": False,
    "amoc_coupling_scheme": "euler",
    "amoc_southern_ocean_structure": "fixed",
    "amoc_southern_wind_sensitivity": "0.06",
    "amoc_southern_upwelling_sensitivity": "0.04",
    "amoc_southern_response_min": "0.50",
    "amoc_southern_response_max": "1.75",
    "amoc_indo_pacific_compensation": "none",
    "amoc_indo_pacific_compensation_fraction": "0.50",
    "amoc_indo_pacific_compensation_max": "10.0",
    "auto_initialize_from_1850": True,
    "run_diagnostics": True,
    "equilibrium_years": "1200",
    "run_amoc_hysteresis": False,
    "hysteresis_max_hosing": "0.7",
    "hysteresis_step": "0.05",
    "hysteresis_years_per_step": "80",
    "hysteresis_spinup_years": "200",
    "monte_carlo_enabled": False,
    "mc_runs": "512",
    "mc_seed": "0",
    "mc_workers": "0",
    "mc_member_timeout_seconds": "7200",
    "mc_heartbeat_seconds": "30",
    "mc_resume": False,
    "mc_retry_failed_on_resume": True,
    "mc_sampling": "triangular",
    "mc_design": "sobol",
    "mc_constraint_mode": "none",
    "mc_use_science_defaults": False,
    "mc_run_calibration_experiments": False,
    "mc_correlated_priors": True,
    "mc_max_plotted": "0",
    "mc_save_long_csv": False,
    "mc_no_plots": False,
    "mc_diagnose_each": False,
    "mc_co2_target_sweep_enabled": False,
    "mc_sweep_start_ppm": "278.3",
    "mc_sweep_target_mode": "increments",
    "mc_sweep_step_ppm": "50",
    "mc_sweep_max_ppm": "1200",
    "mc_sweep_specific_targets": "200,300,600,1200",
    "mc_sweep_initial_equilibration_years": "1000",
    "mc_sweep_ramp_years": "100",
    "mc_sweep_hold_years": "200",
    "mc_sweep_collapse_window_years": "30",
    "mc_sweep_persistence_fraction": "0.95",
    "mc_sweep_recovery_years": "5",
    "mc_sweep_bootstrap_samples": "1000",
    "mc_sweep_confidence_level": "0.90",
    "mc_sweep_plot_mode": "mean",
    "mc_sweep_allow_exploratory_target_counts": False,
}

for _range_id, _config_field, _label, _minimum, _maximum, _help in MC_RANGE_SPECS:
    DEFAULTS[f"mc_{_range_id}_enabled"] = _range_id in {
        "co2_erf",
        "longwave_factor",
        "water_vapor",
        "lapse_weight",
        "low_cloud",
        "high_cloud",
        "ocean_exchange",
        "hydrological_fw",
        "hydrological_north_fraction",
        "greenland_fw",
        "greenland_adjust",
        "greenland_depletion",
        "greenland_max_flux",
        "amoc_temp",
    }
    DEFAULTS[f"mc_{_range_id}_min"] = _minimum
    DEFAULTS[f"mc_{_range_id}_max"] = _maximum

CLI_MAP = {
    "scenario": "--scenario",
    "start_year": "--start-year",
    "years": "--years",
    "dt": "--dt",
    "co2_start": "--co2-start",
    "co2_end": "--co2-end",
    "co2_peak": "--co2-peak",
    "co2_growth_cap": "--co2-growth-cap",
    "co2_hold_years": "--co2-hold-years",
    "percent_ramp_compare_rates": "--percent-ramp-compare-rates",
    "peak_fraction": "--peak-fraction",
    "ssp_before": "--ssp-before",
    "ssp_after": "--ssp-after",
    "switch_year": "--switch-year",
    "transition_years": "--transition-years",
    "forcing_mode": "--forcing-mode",
    "co2_doubling_erf": "--co2-doubling-erf",
    "co2_forcing_formula": "--co2-forcing-formula",
    "co2_forcing_reference_n2o": "--co2-forcing-reference-n2o",
    "additional_forcing": "--additional-forcing",
    "relative_humidity": "--relative-humidity",
    "moist_lapse_rate_weight": "--moist-lapse-rate-weight",
    "arctic_lapse_rate_feedback": "--arctic-lapse-rate-feedback",
    "arctic_module_start_latitude": "--arctic-module-start-latitude",
    "arctic_reference_air_seasonal_amplitude": "--arctic-reference-air-seasonal-amplitude",
    "arctic_moisture_transport": "--arctic-moisture-transport",
    "arctic_winter_transport_enhancement": "--arctic-winter-transport-enhancement",
    "arctic_winter_transport_temperature_scale": "--arctic-winter-transport-temperature-scale",
    "arctic_dry_static_transport": "--arctic-dry-static-transport",
    "arctic_open_water_stable_exchange": "--arctic-open-water-stable-exchange",
    "arctic_open_water_unstable_exchange": "--arctic-open-water-unstable-exchange",
    "arctic_open_water_exchange_transition": "--arctic-open-water-exchange-transition",
    "arctic_transient_shortwave_scale": "--arctic-transient-shortwave-scale",
    "arctic_interface_longwave_damping": "--arctic-interface-longwave-damping",
    "arctic_ice_surface_exchange": "--arctic-ice-surface-exchange",
    "arctic_basal_ocean_exchange": "--arctic-basal-ocean-exchange",
    "arctic_open_water_ocean_exchange": "--arctic-open-water-ocean-exchange",
    "arctic_lateral_ocean_heat_transport": "--arctic-lateral-ocean-heat-transport",
    "arctic_forced_ocean_heat_convergence": "--arctic-forced-ocean-heat-convergence",
    "arctic_forced_ocean_heat_convergence_onset": "--arctic-forced-ocean-heat-convergence-onset",
    "arctic_forced_ocean_heat_convergence_saturation_scale": "--arctic-forced-ocean-heat-convergence-saturation-scale",
    "arctic_forced_ocean_heat_convergence_ice_fraction_exponent": "--arctic-forced-ocean-heat-convergence-ice-fraction-exponent",
    "arctic_phase_restoring_deficit_saturation": "--arctic-phase-restoring-deficit-saturation",
    "arctic_phase_restoring_max_deficit_flux": "--arctic-phase-restoring-max-deficit-flux",
    "arctic_new_ice_local_thickness": "--arctic-new-ice-local-thickness",
    "arctic_full_cover_equivalent_thickness": "--arctic-full-cover-equivalent-thickness",
    "arctic_max_equivalent_thickness": "--arctic-max-equivalent-thickness",
    "arctic_max_local_ice_thickness": "--arctic-max-local-ice-thickness",
    "arctic_ice_concentration_exponent": "--arctic-ice-concentration-exponent",
    "arctic_ice_area_formation_temperature_scale": "--arctic-ice-area-formation-temperature-scale",
    "arctic_ice_area_formation_volume_sensitivity": "--arctic-ice-area-formation-volume-sensitivity",
    "arctic_ice_area_formation_support_floor": "--arctic-ice-area-formation-support-floor",
    "arctic_ice_area_melt_thickness": "--arctic-ice-area-melt-thickness",
    "arctic_ice_area_lateral_melt_efficiency": "--arctic-ice-area-lateral-melt-efficiency",
    "arctic_ice_area_thinning_melt_amplification": "--arctic-ice-area-thinning-melt-amplification",
    "arctic_ice_area_thick_pack_resistance_exponent": "--arctic-ice-area-thick-pack-resistance-exponent",
    "arctic_ice_area_compaction_years": "--arctic-ice-area-compaction-years",
    "arctic_ice_area_ridging_threshold": "--arctic-ice-area-ridging-threshold",
    "arctic_ice_area_ridging_rate": "--arctic-ice-area-ridging-rate",
    "arctic_ice_area_divergence_rate": "--arctic-ice-area-divergence-rate",
    "arctic_ice_area_thin_pack_divergence_rate": "--arctic-ice-area-thin-pack-divergence-rate",
    "arctic_greenland_marine_influence": "--arctic-greenland-marine-influence",
    "arctic_winter_lead_closure_fraction": "--arctic-winter-lead-closure-fraction",
    "arctic_winter_lead_closure_onset_fraction": "--arctic-winter-lead-closure-onset-fraction",
    "arctic_winter_lead_closure_temperature_scale": "--arctic-winter-lead-closure-temperature-scale",
    "arctic_atlantic_reference_ocean_temperature": "--arctic-atlantic-reference-ocean-temperature",
    "arctic_non_atlantic_reference_ocean_temperature": "--arctic-non-atlantic-reference-ocean-temperature",
    "arctic_reference_ocean_heat_capacity": "--arctic-reference-ocean-heat-capacity",
    "arctic_reference_ocean_restoring": "--arctic-reference-ocean-restoring",
    "arctic_air_memory_years": "--arctic-air-memory-years",
    "longwave_spectral_factor": "--longwave-spectral-factor",
    "water_vapor_height": "--water-vapor-height",
    "low_cloud_loss": "--low-cloud-loss",
    "high_cloud_coupling": "--high-cloud-coupling",
    "ocean_exchange": "--ocean-exchange",
    "meridional_diffusion": "--meridional-diffusion",
    "freshwater_hosing": "--freshwater-hosing",
    "warming_freshwater": "--warming-freshwater",
    "hydrological_freshwater": "--hydrological-freshwater",
    "hydrological_freshwater_north_fraction": "--hydrological-freshwater-north-fraction",
    "greenland_freshwater": "--greenland-freshwater",
    "greenland_freshwater_threshold": "--greenland-freshwater-threshold",
    "greenland_freshwater_adjustment_years": "--greenland-freshwater-adjustment-years",
    "greenland_initial_ice_mass_gt": "--greenland-initial-ice-mass-gt",
    "greenland_depletion_exponent": "--greenland-depletion-exponent",
    "greenland_max_freshwater_sv": "--greenland-max-freshwater-sv",
    "greenland_dynamic_discharge_fraction": "--greenland-dynamic-discharge-fraction",
    "greenland_reference_annual_temperature_c": "--greenland-reference-annual-temperature",
    "greenland_reference_seasonal_amplitude_c": "--greenland-reference-seasonal-amplitude",
    "greenland_pdd_melt_factor_gt_per_degree_day": "--greenland-pdd-melt-factor",
    "greenland_baseline_precipitation_gt_per_year": "--greenland-baseline-precipitation",
    "greenland_precipitation_fraction_per_k": "--greenland-precipitation-fraction-per-k",
    "greenland_snow_rain_transition_c": "--greenland-snow-rain-transition",
    "greenland_snow_rain_transition_width_c": "--greenland-snow-rain-transition-width",
    "greenland_meltwater_retention_fraction": "--greenland-meltwater-retention-fraction",
    "greenland_retention_loss_fraction_per_k": "--greenland-retention-loss-fraction-per-k",
    "amoc_temperature_coupling": "--amoc-temperature-coupling",
    "amoc_adjustment_years": "--amoc-adjustment-years",
    "amoc_heat_transport": "--amoc-heat-transport",
    "amoc_surface_heat_coupling": "--amoc-surface-heat-coupling",
    "amoc_heat_response_damping": "--amoc-heat-response-damping",
    "atlantic_gyre_heat_transport": "--atlantic-gyre-heat-transport",
    "amoc_density_exponent": "--amoc-density-exponent",
    "amoc_depth_exponent": "--amoc-depth-exponent",
    "amoc_pycnocline_feedback_strength": "--amoc-pycnocline-feedback-strength",
    "amoc_convection_density_scale_factor": "--amoc-convection-density-scale-factor",
    "amoc_convection_minimum_fraction": "--amoc-convection-minimum-fraction",
    "amoc_convective_mixing_reference_sv": "--amoc-convective-mixing-reference",
    "amoc_convective_mixing_exponent": "--amoc-convective-mixing-exponent",
    "amoc_convection_entrainment_feedback": "--amoc-convection-entrainment-feedback",
    "amoc_convection_adjustment_years": "--amoc-convection-adjustment-years",
    "amoc_convection_recovery_years": "--amoc-convection-recovery-years",
    "amoc_eddy_depth_exponent": "--amoc-eddy-depth-exponent",
    "amoc_pycnocline_depth": "--amoc-pycnocline-depth",
    "amoc_pycnocline_area": "--amoc-pycnocline-area",
    "amoc_ekman_inflow": "--amoc-ekman-inflow",
    "amoc_upwelling": "--amoc-upwelling",
    "amoc_eddy_outflow": "--amoc-eddy-outflow",
    "amoc_north_gyre": "--amoc-north-gyre",
    "amoc_southern_gyre": "--amoc-southern-gyre",
    "amoc_southern_external_exchange": "--amoc-southern-external-exchange",
    "amoc_south_atlantic_external_exchange": "--amoc-south-atlantic-external-exchange",
    "initial_fovs": "--initial-fovs",
    "fovs_reference_salinity": "--fovs-reference-salinity",
    "freshwater_start_fraction": "--freshwater-start-fraction",
    "freshwater_ramp_years": "--freshwater-ramp-years",
    "freshwater_compensation_mode": "--freshwater-compensation-mode",
    "freshwater_compensation_tropical_fraction": (
        "--freshwater-compensation-tropical-fraction"
    ),
    "amoc_collapse_threshold": "--amoc-collapse-threshold",
    "amoc_reference_density_driver": "--amoc-reference-density-driver",
    "amoc_minimum_initial_density_ratio": "--amoc-minimum-initial-density-ratio",
    "amoc_maximum_initial_density_ratio": "--amoc-maximum-initial-density-ratio",
    "amoc_coupling_scheme": "--amoc-coupling-scheme",
    "amoc_southern_ocean_structure": "--amoc-southern-ocean-structure",
    "amoc_southern_wind_sensitivity": "--amoc-southern-wind-sensitivity",
    "amoc_southern_upwelling_sensitivity": "--amoc-southern-upwelling-sensitivity",
    "amoc_southern_response_min": "--amoc-southern-response-min",
    "amoc_southern_response_max": "--amoc-southern-response-max",
    "amoc_indo_pacific_compensation": "--amoc-indo-pacific-compensation",
    "amoc_indo_pacific_compensation_fraction": "--amoc-indo-pacific-compensation-fraction",
    "amoc_indo_pacific_compensation_max": "--amoc-indo-pacific-compensation-max",
    "equilibrium_years": "--equilibrium-years",
    "hysteresis_max_hosing": "--hysteresis-max-hosing",
    "hysteresis_step": "--hysteresis-step",
    "hysteresis_years_per_step": "--hysteresis-years-per-step",
    "hysteresis_spinup_years": "--hysteresis-spinup-years",
    "output": "--output",
}

NUMERIC_KEYS = {
    key
    for key in CLI_MAP
    if key
    not in {
        "scenario",
        "forcing_mode",
        "co2_forcing_formula",
        "ssp_before",
        "ssp_after",
        "freshwater_compensation_mode",
        "amoc_coupling_scheme",
        "amoc_southern_ocean_structure",
        "amoc_indo_pacific_compensation",
        "percent_ramp_compare_rates",
        "output",
    }
}

PRESETS: dict[str, dict[str, Any]] = {
    "SSP1-2.6 to 2100": {
        "scenario": "ssp126",
        "start_year": "1850",
        "years": "250",
        "forcing_mode": "total_effective",
        "output": "outputs_ssp126",
    },
    "SSP2-4.5 to 2100": {
        "scenario": "ssp245",
        "start_year": "1850",
        "years": "250",
        "forcing_mode": "total_effective",
        "output": "outputs_ssp245",
    },
    "SSP4-6.0 to 2100": {
        "scenario": "ssp460",
        "start_year": "1850",
        "years": "250",
        "forcing_mode": "total_effective",
        "output": "outputs_ssp460",
    },
    "SSP5-8.5 to 2400": {
        "scenario": "ssp585",
        "start_year": "1850",
        "years": "550",
        "forcing_mode": "total_effective",
        "output": "outputs_ssp585",
    },
    "SSP5-8.5 + 0.1 Sv hosing": {
        "scenario": "ssp585",
        "start_year": "1850",
        "years": "550",
        "forcing_mode": "total_effective",
        "freshwater_hosing": "0.1",
        "output": "outputs_ssp585_hosing_0p1",
    },
    "Hybrid SSP5-8.5 to SSP2-4.5": {
        "scenario": "hybrid_ssp",
        "start_year": "1850",
        "years": "250",
        "ssp_before": "ssp585",
        "ssp_after": "ssp245",
        "switch_year": "2020",
        "transition_years": "10",
        "forcing_mode": "total_effective",
        "output": "outputs_hybrid_585_to_245",
    },
    "1% CO2 to 4x, then hold": {
        "scenario": "one_percent",
        "start_year": "1850",
        "years": "1000",
        "co2_start": "278.3",
        "one_percent_cap": "1113.2",
        "output": "outputs_one_percent_4x",
    },
    "Percent CO2 ramp comparison": {
        "scenario": "percent_ramp_hold",
        "start_year": "1850",
        "co2_start": "278.3",
            "co2_growth_cap": "1200",
        "co2_hold_years": "200",
        "percent_ramp_compare_rates": "0.5,1,2,3,5",
        "run_diagnostics": False,
        "output": "outputs_percent_ramp_comparison",
    },
    "Preindustrial control": {
        "scenario": "constant",
        "start_year": "1850",
        "years": "500",
        "co2_start": "278.3",
        "output": "outputs_control",
    },
    "Monte Carlo CO2 target sweep": {
        "scenario": "constant",
        "start_year": "1850",
        "co2_start": "278.3",
        "monte_carlo_enabled": True,
        "mc_co2_target_sweep_enabled": True,
        "mc_runs": "128",
        "mc_sweep_start_ppm": "278.3",
        "mc_sweep_target_mode": "increments",
        "mc_sweep_step_ppm": "50",
        "mc_sweep_max_ppm": "1200",
        "mc_sweep_specific_targets": "200,300,600,1200",
        "mc_sweep_initial_equilibration_years": "1000",
        "mc_sweep_ramp_years": "100",
        "mc_sweep_hold_years": "200",
        "mc_sweep_collapse_window_years": "30",
        "mc_sweep_plot_mode": "mean",
        "mc_use_science_defaults": True,
        "mc_constraint_mode": "none",
        "output": "outputs_co2_target_sweep",
    },
    "Monte Carlo SSP2-4.5 uncertainty": {
        "scenario": "ssp245",
        "start_year": "1850",
        "years": "250",
        "forcing_mode": "total_effective",
        "monte_carlo_enabled": True,
        "mc_runs": "512",
        "mc_seed": "0",
        "mc_workers": "0",
        "mc_sampling": "triangular",
        "mc_constraint_mode": "none",
        "mc_use_science_defaults": False,
        "mc_run_calibration_experiments": False,
        "output": "outputs_ssp245_monte_carlo",
    },
}


def preferred_python_executable() -> str:
    """Return a console-capable interpreter for the child process."""
    executable = Path(sys.executable)
    if os.name == "nt" and executable.name.lower() == "pythonw.exe":
        console_python = executable.with_name("python.exe")
        if console_python.exists():
            return str(console_python)
    return str(executable)


def build_cli_command(values: dict[str, Any]) -> list[str]:
    """Build the complete deterministic or Monte Carlo command."""

    monte_carlo = bool(values.get("monte_carlo_enabled", False))
    target_sweep = monte_carlo and bool(values.get("mc_co2_target_sweep_enabled", False))
    script = CO2_TARGET_SWEEP_SCRIPT if target_sweep else (MONTE_CARLO_SCRIPT if monte_carlo else MODEL_SCRIPT)
    command = [preferred_python_executable(), str(script)]

    for key, option in CLI_MAP.items():
        value = values.get(key, DEFAULTS.get(key, ""))
        if key == "one_percent_cap":
            continue
        if (
            key == "percent_ramp_compare_rates"
            and str(values.get("scenario", "")) != "percent_ramp_hold"
        ):
            continue
        if value is None or str(value).strip() == "":
            continue
        command.extend([option, str(value).strip()])

    if str(values.get("one_percent_cap", "")).strip():
        command.extend(["--one-percent-cap", str(values["one_percent_cap"]).strip()])
    if bool(values.get("run_all_ssp", False)) or bool(
        values.get("resume_all_ssp", False)
    ):
        command.append("--run-all-ssp")
    if bool(values.get("resume_all_ssp", False)):
        command.append("--resume-all-ssp")
    if not bool(values.get("seasonal_arctic_enabled", True)):
        command.append("--disable-seasonal-arctic")
    if not bool(values.get("greenland_surface_mass_balance_enabled", True)):
        command.append("--disable-greenland-smb")
    if not bool(values.get("auto_initialize_from_1850", True)):
        command.append("--no-auto-initialize-from-1850")
    if not bool(values.get("amoc_enforce_initial_density_constraint", True)):
        command.append("--amoc-no-initial-density-constraint")
    if bool(values.get("amoc_allow_reversal", False)):
        command.append("--amoc-allow-reversal")

    if monte_carlo:
        command.extend(["--monte-carlo-runs", str(values["mc_runs"]).strip()])
        command.extend(["--mc-seed", str(values["mc_seed"]).strip()])
        command.extend(["--mc-workers", str(values["mc_workers"]).strip()])
        command.extend(["--mc-member-timeout-seconds", str(values["mc_member_timeout_seconds"]).strip()])
        command.extend(["--mc-heartbeat-seconds", str(values["mc_heartbeat_seconds"]).strip()])
        if bool(values.get("mc_resume", False)):
            command.append("--mc-resume")
        if not bool(values.get("mc_retry_failed_on_resume", True)):
            command.append("--no-mc-retry-failed-on-resume")
        command.extend(["--mc-sampling", str(values["mc_sampling"]).strip()])
        command.extend(["--mc-design", str(values["mc_design"]).strip()])
        command.extend(
            ["--mc-constraint-mode", str(values["mc_constraint_mode"]).strip()]
        )
        if bool(values.get("mc_use_science_defaults", False)):
            command.append("--mc-use-science-priors")
        if str(values.get("mc_constraint_mode", "none")) != "none":
            command.append("--mc-run-calibration-experiments")
        command.extend(["--mc-max-plotted", str(values["mc_max_plotted"]).strip()])
        if not bool(values.get("mc_correlated_priors", True)):
            command.append("--mc-no-correlated-priors")
        if bool(values.get("mc_save_long_csv", False)):
            command.append("--mc-save-long-csv")
        if bool(values.get("mc_no_plots", False)):
            command.append("--mc-no-plots")
        if bool(values.get("mc_diagnose_each", False)):
            command.append("--mc-diagnose-each")
        if target_sweep:
            command.extend(["--sweep-start-ppm", str(values["mc_sweep_start_ppm"]).strip()])
            command.extend(["--sweep-target-mode", str(values["mc_sweep_target_mode"]).strip()])
            command.extend(["--sweep-step-ppm", str(values["mc_sweep_step_ppm"]).strip()])
            command.extend(["--sweep-max-ppm", str(values["mc_sweep_max_ppm"]).strip()])
            command.extend([
                "--sweep-specific-targets",
                str(values["mc_sweep_specific_targets"]).strip(),
            ])
            command.extend([
                "--sweep-initial-equilibration-years",
                str(values["mc_sweep_initial_equilibration_years"]).strip(),
            ])
            command.extend(["--sweep-ramp-years", str(values["mc_sweep_ramp_years"]).strip()])
            command.extend(["--sweep-hold-years", str(values["mc_sweep_hold_years"]).strip()])
            command.extend(["--sweep-collapse-window-years", str(values["mc_sweep_collapse_window_years"]).strip()])
            command.extend(["--sweep-persistence-fraction", str(values["mc_sweep_persistence_fraction"]).strip()])
            command.extend(["--sweep-recovery-years", str(values["mc_sweep_recovery_years"]).strip()])
            command.extend(["--sweep-bootstrap-samples", str(values["mc_sweep_bootstrap_samples"]).strip()])
            command.extend(["--sweep-confidence-level", str(values["mc_sweep_confidence_level"]).strip()])
            command.extend(["--sweep-plot-mode", str(values["mc_sweep_plot_mode"]).strip()])
            if bool(values.get("mc_sweep_allow_exploratory_target_counts", False)):
                command.append("--sweep-allow-exploratory-target-counts")
        if not bool(values.get("mc_use_science_defaults", False)):
            for range_id, config_field, _label, _minimum, _maximum, _help in MC_RANGE_SPECS:
                if not bool(values.get(f"mc_{range_id}_enabled", False)):
                    continue
                command.extend(
                    [
                        "--mc-range",
                        config_field,
                        str(values[f"mc_{range_id}_min"]).strip(),
                        str(values[f"mc_{range_id}_max"]).strip(),
                    ]
                )
    else:
        if not bool(values.get("run_diagnostics", True)):
            command.append("--skip-diagnostics")
        if bool(values.get("run_amoc_hysteresis", False)):
            command.append("--run-amoc-hysteresis")

    return command


def format_command(command: list[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(command)
    return shlex.join(command)


def validate_values(values: dict[str, Any]) -> None:
    """Perform fast GUI-side validation before launching the model."""

    for key in NUMERIC_KEYS:
        value = str(values.get(key, "")).strip()
        if value == "" and key in {
            "one_percent_cap", "warming_freshwater", "percent_ramp_compare_rates"
        }:
            continue
        if value == "":
            raise ValueError(f"{key.replace('_', ' ').title()} cannot be empty.")
        try:
            float(value)
        except ValueError as exc:
            raise ValueError(
                f"{key.replace('_', ' ').title()} must be a number: {value!r}"
            ) from exc

    start = float(values["start_year"])
    years = float(values["years"])
    dt = float(values["dt"])
    scenario = str(values["scenario"])
    run_all_ssp = bool(values.get("run_all_ssp", False))
    resume_all_ssp = bool(values.get("resume_all_ssp", False))
    if resume_all_ssp and not run_all_ssp:
        raise ValueError("Resume all SSP scenarios requires Run all SSP scenarios.")
    if run_all_ssp and bool(values.get("monte_carlo_enabled", False)):
        raise ValueError("All-SSP batch execution is available for deterministic runs only.")
    target_sweep = bool(values.get("monte_carlo_enabled", False)) and bool(
        values.get("mc_co2_target_sweep_enabled", False)
    )
    if bool(values.get("seasonal_arctic_enabled", False)):
        stable_exchange = float(values["arctic_open_water_stable_exchange"])
        unstable_exchange = float(values["arctic_open_water_unstable_exchange"])
        ocean_exchange = float(values["arctic_open_water_ocean_exchange"])
        moisture = float(values["arctic_moisture_transport"])
        winter = float(values["arctic_winter_transport_enhancement"])
        winter_temperature_scale = float(
            values["arctic_winter_transport_temperature_scale"]
        )
        shortwave = float(values["arctic_transient_shortwave_scale"])
        longwave_damping = float(values["arctic_interface_longwave_damping"])
        ice_surface_exchange = float(values["arctic_ice_surface_exchange"])
        new_ice_thickness = float(values["arctic_new_ice_local_thickness"])
        full_cover_thickness = float(values["arctic_full_cover_equivalent_thickness"])
        concentration_exponent = float(values["arctic_ice_concentration_exponent"])
        lead_closure = float(values["arctic_winter_lead_closure_fraction"])
        lead_onset = float(values["arctic_winter_lead_closure_onset_fraction"])
        lead_scale = float(values["arctic_winter_lead_closure_temperature_scale"])
        if not 0.01 <= new_ice_thickness < full_cover_thickness:
            raise ValueError(
                "New-ice local thickness must be positive and below the full-cover thickness."
            )
        if full_cover_thickness <= 0.0:
            raise ValueError("Full-cover equivalent thickness must be positive.")
        if concentration_exponent <= 0.0:
            raise ValueError("Ice-concentration exponent must be positive.")
        if winter_temperature_scale <= 0.0:
            raise ValueError(
                "Arctic winter-transport temperature scale must be positive."
            )
        if longwave_damping < 0.0:
            raise ValueError("Arctic interface longwave damping cannot be negative.")
        if ice_surface_exchange <= 0.0:
            raise ValueError("Arctic ice-surface exchange must be positive.")
        if not 0.0 <= lead_closure <= 1.0:
            raise ValueError("Cold-season mechanical lead closure must be in [0, 1].")
        if not 0.0 <= lead_onset <= 1.0:
            raise ValueError("Lead-closure onset deficit must be in [0, 1].")
        if lead_scale <= 0.0:
            raise ValueError("Lead-closure temperature scale must be positive.")
        if unstable_exchange < stable_exchange:
            raise ValueError(
                "Unstable open-water exchange must be at least the stable exchange."
            )
        required_damping = (
            ARCTIC_MINIMUM_EFFECTIVE_WARM_DAMPING_WM2_K
            + 0.05 * (moisture + winter) * shortwave
        )
        effective_damping = unstable_exchange + ocean_exchange
        if effective_damping < required_damping:
            raise ValueError(
                "Arctic open-water damping is too weak for the selected transport "
                f"and shortwave settings: {effective_damping:.3g} < "
                f"{required_damping:.3g} W/m2/K. Increase unstable air-water "
                "exchange or open-water/ocean exchange."
            )

    if target_sweep:
        try:
            sweep_start = float(str(values["mc_sweep_start_ppm"]))
            sweep_mode = str(values["mc_sweep_target_mode"]).strip().lower()
            sweep_step = float(str(values["mc_sweep_step_ppm"]))
            sweep_max = float(str(values["mc_sweep_max_ppm"]))
            sweep_ramp = float(str(values["mc_sweep_ramp_years"]))
            sweep_hold = float(str(values["mc_sweep_hold_years"]))
            sweep_window = float(str(values["mc_sweep_collapse_window_years"]))
            sweep_persistence = float(str(values["mc_sweep_persistence_fraction"]))
            sweep_recovery = float(str(values["mc_sweep_recovery_years"]))
            sweep_initial_equilibration = float(
                str(values["mc_sweep_initial_equilibration_years"])
            )
            sweep_bootstrap = int(float(str(values["mc_sweep_bootstrap_samples"])))
            sweep_confidence = float(str(values["mc_sweep_confidence_level"]))
        except ValueError as exc:
            raise ValueError("CO2 target-sweep controls must be numeric.") from exc
        if sweep_start <= 0.0:
            raise ValueError("Sweep start must be positive.")
        if sweep_mode not in {"increments", "specific"}:
            raise ValueError("Sweep target selection must be increments or specific.")
        if sweep_mode == "increments" and (sweep_step <= 0.0 or sweep_max < sweep_start):
            raise ValueError(
                "Increment-mode sweep step must be positive and maximum must be at least start."
            )
        if sweep_mode == "specific":
            raw_targets = str(values.get("mc_sweep_specific_targets", "")).strip()
            tokens = [
                token
                for token in raw_targets.replace(";", ",").replace(" ", ",").split(",")
                if token.strip()
            ]
            if not tokens:
                raise ValueError("Enter at least one specific CO2 target.")
            try:
                specific_targets = sorted({float(token) for token in tokens})
            except ValueError as exc:
                raise ValueError(
                    "Specific CO2 targets must be numbers separated by commas, spaces, or semicolons."
                ) from exc
            if any(target <= 0.0 for target in specific_targets):
                raise ValueError("Specific CO2 targets must be positive.")
            # Targets below the common start are valid descending ramps.
        if (
            sweep_initial_equilibration < 0.0
            or not float(sweep_initial_equilibration).is_integer()
        ):
            raise ValueError(
                "Sweep initial-equilibration years must be a non-negative whole number."
            )
        if sweep_ramp <= 0.0 or sweep_hold < 0.0:
            raise ValueError("Sweep ramp years must be positive and hold years cannot be negative.")
        if sweep_window <= 0.0 or sweep_window > sweep_ramp + sweep_hold:
            raise ValueError("Sweep collapse window must be positive and no longer than ramp plus hold.")
        if not 0.0 < sweep_persistence <= 1.0:
            raise ValueError("Sweep persistence fraction must be in (0, 1].")
        if sweep_recovery < 0.0 or sweep_recovery > sweep_window:
            raise ValueError("Sweep recovery duration must lie between zero and the collapse window.")
        if sweep_bootstrap < 0:
            raise ValueError("Sweep bootstrap samples cannot be negative.")
        if not 0.0 < sweep_confidence < 1.0:
            raise ValueError("Sweep confidence level must be in (0, 1).")

    if years <= 0:
        raise ValueError("Simulation years must be positive.")
    if not 0.001 <= dt <= 0.25:
        raise ValueError("Time step must be between 0.001 and 0.25 years.")
    if (
        run_all_ssp or scenario in SSP_SCENARIOS or scenario == "hybrid_ssp"
    ) and not target_sweep:
        end = start + years
        if start < 1750 or end > 2500:
            raise ValueError(
                f"SSP data cover 1750-2500. This setup ends in {end:g}."
            )
    if scenario == "hybrid_ssp" and not target_sweep:
        switch = float(values["switch_year"])
        if not start <= switch <= start + years:
            raise ValueError(
                "Hybrid switch year must lie between the simulation start and end."
            )
    if scenario == "percent_ramp_hold":
        cap = float(values["co2_growth_cap"])
        hold = float(values["co2_hold_years"])
        start_co2 = float(values["co2_start"])
        if cap < start_co2:
            raise ValueError("Ramp cap cannot be below starting CO2.")
        if hold < 0.0:
            raise ValueError("Post-cap hold years cannot be negative.")
        compare_text = str(values.get("percent_ramp_compare_rates", "")).strip()
        if not compare_text:
            raise ValueError("Enter at least one CO2 growth rate.")
        try:
            rates = [
                float(token.strip())
                for token in compare_text.replace(";", ",").split(",")
                if token.strip()
            ]
        except ValueError as exc:
            raise ValueError(
                "Growth rates must be comma-separated numbers."
            ) from exc
        if not rates or any(item <= 0.0 for item in rates):
            raise ValueError("All growth rates must be positive.")
        if bool(values.get("monte_carlo_enabled", False)) and len(set(rates)) != 1:
            raise ValueError(
                "Monte Carlo percent-ramp runs require exactly one growth rate. "
                "Run separate ensembles for separate rates."
            )
    if not str(values.get("output", "")).strip():
        raise ValueError("Choose an output folder.")

    if bool(values.get("monte_carlo_enabled", False)):
        runs = int(float(str(values["mc_runs"])))
        workers = int(float(str(values["mc_workers"])))
        seed = int(float(str(values["mc_seed"])))
        max_plotted = int(float(str(values["mc_max_plotted"])))
        member_timeout = float(str(values["mc_member_timeout_seconds"]))
        heartbeat = float(str(values["mc_heartbeat_seconds"]))
        if runs < 2 or runs > 100000:
            raise ValueError("Monte Carlo runs must be between 2 and 100,000.")
        if workers < 0:
            raise ValueError("Monte Carlo workers cannot be negative.")
        if seed < 0:
            raise ValueError(
                "Random seed cannot be negative. Use 0 for a system-clock seed."
            )
        if max_plotted < 0:
            raise ValueError("Maximum plotted members cannot be negative.")
        if member_timeout <= 0.0:
            raise ValueError("Monte Carlo member timeout must be positive.")
        if heartbeat <= 0.0:
            raise ValueError("Monte Carlo heartbeat interval must be positive.")
        use_science_defaults = bool(values.get("mc_use_science_defaults", False))
        constraint_mode = str(values.get("mc_constraint_mode", "none"))
        selected = 0
        if not use_science_defaults:
            for range_id, _config_field, label, _minimum, _maximum, _help in MC_RANGE_SPECS:
                if not bool(values.get(f"mc_{range_id}_enabled", False)):
                    continue
                selected += 1
                try:
                    minimum = float(str(values[f"mc_{range_id}_min"]))
                    maximum = float(str(values[f"mc_{range_id}_max"]))
                except ValueError as exc:
                    raise ValueError(f"Monte Carlo bounds for {label} must be numeric.") from exc
                if minimum > maximum:
                    raise ValueError(
                        f"Monte Carlo minimum exceeds maximum for {label}: "
                        f"{minimum} > {maximum}."
                    )
                if values["mc_sampling"] == "loguniform" and minimum <= 0.0:
                    raise ValueError(
                        f"Log-uniform sampling requires a positive minimum for {label}."
                    )
            if selected == 0:
                raise ValueError("Select at least one custom Monte Carlo parameter range.")


class ScrollableFrame(ttk.Frame):
    """A vertical scroll container for long parameter forms."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(
            self, orient="vertical", command=self.canvas.yview
        )
        self.content = ttk.Frame(self.canvas)
        self.window_id = self.canvas.create_window(
            (0, 0), window=self.content, anchor="nw"
        )
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.content.bind("<Configure>", self._on_content_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_content_configure(self, _event: tk.Event[Any]) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event[Any]) -> None:
        self.canvas.itemconfigure(self.window_id, width=event.width)

    def _on_mousewheel(self, event: tk.Event[Any]) -> None:
        if os.name == "nt":
            delta = int(-event.delta / 120)
        else:
            delta = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(delta, "units")


class HoverTooltip:
    """Small delayed tooltip that works with standard Tk and ttk widgets."""

    def __init__(
        self,
        widget: tk.Widget,
        text: str,
        *,
        delay_ms: int = 450,
        wraplength: int = 460,
    ) -> None:
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self.wraplength = wraplength
        self._after_id: str | None = None
        self._window: tk.Toplevel | None = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event: tk.Event[Any] | None = None) -> None:
        self._cancel_schedule()
        self._after_id = self.widget.after(self.delay_ms, self._show)

    def _cancel_schedule(self) -> None:
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

    def _show(self) -> None:
        self._after_id = None
        if self._window is not None or not self.text:
            return
        try:
            x = self.widget.winfo_rootx() + min(self.widget.winfo_width(), 36)
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        except tk.TclError:
            return
        window = tk.Toplevel(self.widget)
        window.wm_overrideredirect(True)
        window.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            window,
            text=self.text,
            justify="left",
            anchor="w",
            background="#fffbe6",
            foreground="#202020",
            relief="solid",
            borderwidth=1,
            padx=9,
            pady=7,
            wraplength=self.wraplength,
            font=("Segoe UI", 9),
        )
        label.pack()
        self._window = window

    def _hide(self, _event: tk.Event[Any] | None = None) -> None:
        self._cancel_schedule()
        if self._window is not None:
            try:
                self._window.destroy()
            except tk.TclError:
                pass
            self._window = None


class ClimateModelGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1180x820")
        self.root.minsize(980, 700)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.process: subprocess.Popen[str] | None = None
        self.launch_in_progress = False
        self.stop_requested = False
        self.closing_after_stop = False
        self.output_queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.variables: dict[str, tk.Variable] = {}
        self.widgets: dict[str, tk.Widget] = {}
        self.tooltips: list[HoverTooltip] = []
        self.loaded_resume_command_args: list[str] | None = None
        self.loaded_resume_script: Path | None = None
        self._loading_saved_progress = False

        self._configure_style()
        self._create_variables()
        self._build_interface()
        self._apply_defaults()
        self.update_scenario_state()
        self.refresh_command_preview()
        self.root.after(100, self.poll_output_queue)

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        available = style.theme_names()
        for candidate in ("vista", "clam"):
            if candidate in available:
                style.theme_use(candidate)
                break
        style.configure("Header.TLabel", font=("Segoe UI", 16, "bold"))
        style.configure("Subheader.TLabel", font=("Segoe UI", 10))
        style.configure("Section.TLabelframe.Label", font=("Segoe UI", 10, "bold"))
        style.configure("Run.TButton", font=("Segoe UI", 10, "bold"))

    def _create_variables(self) -> None:
        for key, default in DEFAULTS.items():
            if isinstance(default, bool):
                self.variables[key] = tk.BooleanVar(value=default)
            else:
                self.variables[key] = tk.StringVar(value=str(default))
        self.preset_var = tk.StringVar(value="SSP2-4.5 to 2100")
        self.status_var = tk.StringVar(value="Ready")
        self.command_preview_var = tk.StringVar(value="")

        for variable in self.variables.values():
            variable.trace_add("write", lambda *_args: self._on_value_changed())

    def _build_interface(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)

        header = ttk.Frame(self.root, padding=(14, 12, 14, 8))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)
        ttk.Label(header, text=APP_TITLE, style="Header.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w"
        )
        ttk.Label(
            header,
            text=(
                "Choose a deterministic experiment or Monte Carlo ranges, then run the "
                "model and inspect the generated output folder. AMOC and Greenland are "
                "sensitivity experiments; sea-ice longitude maps and Arctic open-water "
                "temperatures are not local forecasts."
            ),
            style="Subheader.TLabel",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(2, 10))
        preset_label = ttk.Label(header, text="Preset:")
        preset_label.grid(row=2, column=0, sticky="w")
        preset_box = ttk.Combobox(
            header,
            textvariable=self.preset_var,
            values=list(PRESETS),
            state="readonly",
            width=34,
        )
        preset_box.grid(row=2, column=1, sticky="w", padx=(8, 8))
        self._attach_tooltip(preset_label, "preset")
        self._attach_tooltip(preset_box, "preset")
        ttk.Button(header, text="Apply preset", command=self.apply_preset).grid(
            row=2, column=2, sticky="w"
        )

        command_frame = ttk.LabelFrame(
            self.root, text="Command preview", padding=(10, 6)
        )
        command_frame.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 8))
        command_frame.columnconfigure(0, weight=1)
        command_entry = ttk.Entry(
            command_frame,
            textvariable=self.command_preview_var,
            state="readonly",
        )
        command_entry.grid(row=0, column=0, sticky="ew")
        ttk.Button(
            command_frame, text="Copy", command=self.copy_command
        ).grid(row=0, column=1, padx=(8, 0))

        main = ttk.Panedwindow(self.root, orient="horizontal")
        main.grid(row=2, column=0, sticky="nsew", padx=14, pady=(0, 8))

        settings_panel = ttk.Frame(main)
        log_panel = ttk.Frame(main)
        main.add(settings_panel, weight=3)
        main.add(log_panel, weight=2)

        settings_panel.rowconfigure(0, weight=1)
        settings_panel.columnconfigure(0, weight=1)
        notebook = ttk.Notebook(settings_panel)
        notebook.grid(row=0, column=0, sticky="nsew")
        self.notebook = notebook

        self._build_experiment_tab(notebook)
        self._build_climate_tab(notebook)
        self._build_monte_carlo_tab(notebook)
        self._build_amoc_tab(notebook)
        self._build_hysteresis_tab(notebook)

        log_panel.rowconfigure(1, weight=1)
        log_panel.columnconfigure(0, weight=1)
        ttk.Label(log_panel, text="Simulation output", style="Header.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 6)
        )
        log_container = ttk.Frame(log_panel)
        log_container.grid(row=1, column=0, sticky="nsew")
        log_container.rowconfigure(0, weight=1)
        log_container.columnconfigure(0, weight=1)
        self.log_text = tk.Text(
            log_container,
            wrap="word",
            font=("Consolas", 9),
            state="disabled",
            undo=False,
        )
        log_scroll = ttk.Scrollbar(
            log_container, orient="vertical", command=self.log_text.yview
        )
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        log_scroll.grid(row=0, column=1, sticky="ns")

        log_buttons = ttk.Frame(log_panel)
        log_buttons.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(log_buttons, text="Clear log", command=self.clear_log).pack(
            side="left"
        )
        ttk.Button(
            log_buttons, text="Open output folder", command=self.open_output_folder
        ).pack(side="left", padx=(6, 0))

        footer = ttk.Frame(self.root, padding=(14, 4, 14, 12))
        footer.grid(row=3, column=0, sticky="ew")
        footer.columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(footer, mode="indeterminate", length=220)
        self.progress.grid(row=0, column=0, sticky="w")
        ttk.Label(footer, textvariable=self.status_var).grid(
            row=0, column=1, padx=(10, 12), sticky="e"
        )
        self.save_button = ttk.Button(
            footer, text="Save settings", command=self.save_settings
        )
        self.save_button.grid(row=0, column=2, padx=(0, 6))
        self.load_button = ttk.Button(
            footer, text="Load settings", command=self.load_settings
        )
        self.load_button.grid(row=0, column=3, padx=(0, 6))
        self.load_progress_button = ttk.Button(
            footer, text="Load saved run", command=self.load_saved_progress
        )
        self.load_progress_button.grid(row=0, column=4, padx=(0, 6))
        self.stop_button = ttk.Button(
            footer, text="Stop", command=self.stop_simulation, state="disabled"
        )
        self.stop_button.grid(row=0, column=5, padx=(0, 6))
        self.run_button = ttk.Button(
            footer,
            text="Run simulation",
            command=self.run_simulation,
            style="Run.TButton",
        )
        self.run_button.grid(row=0, column=6)

    def _attach_tooltip(self, widget: tk.Widget, key: str, extra_note: str = "") -> None:
        self.tooltips.append(
            HoverTooltip(widget, setting_tooltip(key, extra_note=extra_note))
        )

    def _new_tab(self, notebook: ttk.Notebook, title: str) -> ttk.Frame:
        wrapper = ttk.Frame(notebook)
        notebook.add(wrapper, text=title)
        wrapper.rowconfigure(0, weight=1)
        wrapper.columnconfigure(0, weight=1)
        scroll = ScrollableFrame(wrapper)
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.content.columnconfigure(0, weight=1)
        return scroll.content

    def _section(self, parent: ttk.Frame, title: str, row: int) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(
            parent, text=title, padding=10, style="Section.TLabelframe"
        )
        frame.grid(row=row, column=0, sticky="ew", padx=8, pady=(8, 0))
        # Most section rows are self-contained field frames. Keep the section
        # itself flexible so direct-grid rows such as the output-folder picker
        # also continue to expand correctly.
        frame.columnconfigure(0, weight=0)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=0)
        return frame

    def _field(
        self,
        parent: ttk.Frame,
        row: int,
        key: str,
        label: str,
        *,
        values: list[str] | None = None,
        width: int = 18,
        help_text: str = "",
    ) -> tk.Widget:
        row_frame = ttk.Frame(parent)
        row_frame.grid(row=row, column=0, columnspan=3, sticky="ew", pady=2)
        row_frame.columnconfigure(0, minsize=230)
        row_frame.columnconfigure(1, minsize=165, weight=1)
        row_frame.columnconfigure(2, minsize=24)

        label_widget = ttk.Label(row_frame, text=label)
        label_widget.grid(row=0, column=0, sticky="w", padx=(0, 8), pady=1)
        if values is None:
            widget: tk.Widget = ttk.Entry(
                row_frame, textvariable=self.variables[key], width=width
            )
        else:
            widget = ttk.Combobox(
                row_frame,
                textvariable=self.variables[key],
                values=values,
                state="readonly",
                width=width,
            )
        widget.grid(row=0, column=1, sticky="ew", padx=(0, 6), pady=1)
        info = ttk.Label(row_frame, text="ⓘ", foreground="#356aa0", cursor="question_arrow")
        info.grid(row=0, column=2, sticky="w", padx=(2, 0), pady=1)
        self._attach_tooltip(label_widget, key, help_text)
        self._attach_tooltip(widget, key, help_text)
        self._attach_tooltip(info, key, help_text)
        self.widgets[key] = widget
        return widget

    def _checkbox(
        self, parent: ttk.Frame, row: int, key: str, label: str, *, help_text: str = ""
    ) -> ttk.Checkbutton:
        row_frame = ttk.Frame(parent)
        row_frame.grid(row=row, column=0, columnspan=3, sticky="ew", pady=3)
        checkbox = ttk.Checkbutton(
            row_frame, text=label, variable=self.variables[key]
        )
        checkbox.grid(row=0, column=0, sticky="w")
        info = ttk.Label(row_frame, text="ⓘ", foreground="#356aa0", cursor="question_arrow")
        info.grid(row=0, column=1, sticky="w", padx=(6, 0))
        self._attach_tooltip(checkbox, key, help_text)
        self._attach_tooltip(info, key, help_text)
        self.widgets[key] = checkbox
        return checkbox

    def _build_experiment_tab(self, notebook: ttk.Notebook) -> None:
        tab = self._new_tab(notebook, "Experiment")

        general = self._section(tab, "Scenario and duration", 0)
        self._field(general, 0, "scenario", "Scenario", values=SCENARIOS)
        self._checkbox(
            general,
            1,
            "run_all_ssp",
            "Run all SSP scenarios sequentially",
            help_text=(
                "Runs SSP1-2.6, SSP2-4.5, SSP4-6.0, and SSP5-8.5 with the "
                "same settings and creates a combined near-surface-air temperature plot."
            ),
        )
        self._checkbox(
            general,
            2,
            "resume_all_ssp",
            "Resume an interrupted all-SSP batch",
            help_text="Skips complete, settings-compatible scenario subfolders.",
        )
        self._field(general, 3, "forcing_mode", "Forcing mode", values=FORCING_MODES)
        self._field(general, 4, "start_year", "Start year")
        self._field(general, 5, "years", "Simulation length (years)")
        self._field(general, 6, "dt", "Time step (years)", help_text="0.05 recommended")
        self._checkbox(
            general,
            7,
            "auto_initialize_from_1850",
            "Initialize post-1850 SSP runs from a continuous 1850 integration",
        )

        output = self._section(tab, "Output", 1)
        output_label = ttk.Label(output, text="Output folder")
        output_label.grid(row=0, column=0, sticky="w")
        output_entry = ttk.Entry(output, textvariable=self.variables["output"])
        output_entry.grid(row=0, column=1, sticky="ew", padx=(10, 0), pady=3)
        ttk.Button(output, text="Browse...", command=self.browse_output).grid(
            row=0, column=2, padx=(8, 0)
        )
        self._attach_tooltip(output_label, "output")
        self._attach_tooltip(output_entry, "output")
        self.widgets["output"] = output_entry

        co2 = self._section(tab, "CO2 pathway", 2)
        self._field(co2, 0, "co2_start", "Starting CO2 (ppm)")
        self._field(co2, 1, "co2_end", "Ending CO2 (ppm)")
        self._field(co2, 2, "co2_peak", "Peak CO2 (ppm)")
        self._field(
            co2,
            3,
            "one_percent_cap",
            "1% scenario cap (ppm)",
            help_text="Blank = no cap",
        )
        self._field(co2, 4, "co2_growth_cap", "Ramp cap (ppm)")
        self._field(co2, 5, "co2_hold_years", "Post-cap hold (years)")
        self._field(
            co2,
            6,
            "percent_ramp_compare_rates",
            "Growth rates (%/year)",
            help_text=(
                "Comma-separated, for example 0.5,1,2,3,5. These rates control "
                "the complete experiment and comparison plot."
            ),
        )
        self._field(co2, 7, "peak_fraction", "Overshoot peak fraction")
        self._field(co2, 8, "additional_forcing", "Additional forcing (W/m2)")
        self._field(co2, 9, "co2_doubling_erf", "ERF for doubled CO2 (W/m2)")
        self._field(
            co2, 10, "co2_forcing_formula", "CO2 forcing formula",
            values=CO2_FORCING_FORMULAS,
        )
        self._field(co2, 11, "co2_forcing_reference_n2o", "Reference N2O (ppb)")

        hybrid = self._section(tab, "Hybrid SSP switching", 3)
        self._field(
            hybrid, 0, "ssp_before", "Scenario before switch", values=sorted(SSP_SCENARIOS)
        )
        self._field(
            hybrid, 1, "ssp_after", "Scenario after switch", values=sorted(SSP_SCENARIOS)
        )
        self._field(hybrid, 2, "switch_year", "Switch year")
        self._field(hybrid, 3, "transition_years", "Transition duration (years)")

        diagnostics = self._section(tab, "Diagnostics", 4)
        self._checkbox(
            diagnostics,
            0,
            "run_diagnostics",
            "Run ECS, Gregory-regression and TCR diagnostics",
        )
        self._field(diagnostics, 1, "equilibrium_years", "ECS experiment length")

    def _build_climate_tab(self, notebook: ttk.Notebook) -> None:
        tab = self._new_tab(notebook, "Climate feedbacks")
        feedbacks = self._section(tab, "Atmosphere and cloud feedbacks", 0)
        self._field(feedbacks, 0, "relative_humidity", "Relative humidity")
        self._field(
            feedbacks, 1, "moist_lapse_rate_weight", "Moist lapse-rate weight"
        )
        self._field(
            feedbacks, 2, "longwave_spectral_factor", "Longwave spectral factor"
        )
        self._field(
            feedbacks,
            3,
            "water_vapor_height",
            "Water-vapour emission-height response",
        )
        self._field(feedbacks, 4, "low_cloud_loss", "Low-cloud loss per K")
        self._field(
            feedbacks,
            5,
            "high_cloud_coupling",
            "High-cloud temperature coupling",
        )

        transport = self._section(tab, "Ocean and heat transport", 1)
        self._field(transport, 0, "ocean_exchange", "Deep-ocean heat exchange")
        self._field(
            transport, 1, "meridional_diffusion", "Meridional heat diffusion"
        )

        arctic = self._section(tab, "Seasonal Arctic atmosphere and sea ice", 2)
        self._checkbox(
            arctic, 0, "seasonal_arctic_enabled",
            "Enable prognostic seasonal Arctic subsystem",
        )
        self._field(arctic, 1, "arctic_lapse_rate_feedback", "Arctic lapse-rate/inversion feedback (W/m2/K)")
        self._field(arctic, 2, "arctic_module_start_latitude", "Arctic module transition start (deg N)")
        self._field(arctic, 3, "arctic_reference_air_seasonal_amplitude", "Reference-air seasonal amplitude (deg C)")
        self._field(arctic, 4, "arctic_moisture_transport", "Moisture convergence (W/m2/K)")
        self._field(arctic, 5, "arctic_winter_transport_enhancement", "Cold-season transport enhancement (W/m2/K)")
        self._field(arctic, 6, "arctic_winter_transport_temperature_scale", "Cold-state transport temperature scale (deg C)")
        self._field(arctic, 7, "arctic_dry_static_transport", "Dry-static restoring (W/m2/K)")
        self._field(arctic, 8, "arctic_open_water_stable_exchange", "Stable open-water exchange (W/m2/K)")
        self._field(arctic, 9, "arctic_open_water_unstable_exchange", "Unstable open-water exchange (W/m2/K)")
        self._field(arctic, 10, "arctic_open_water_exchange_transition", "Stability transition (deg C)")
        self._field(arctic, 11, "arctic_transient_shortwave_scale", "Transient shortwave anomaly scale")
        self._field(arctic, 12, "arctic_interface_longwave_damping", "Net surface longwave damping (W/m2/K)")
        self._field(arctic, 13, "arctic_ice_surface_exchange", "Ice-surface/air exchange (W/m2/K)")
        self._field(arctic, 14, "arctic_basal_ocean_exchange", "Basal ice/ocean exchange (W/m2/K)")
        self._field(arctic, 15, "arctic_open_water_ocean_exchange", "Open-water/ocean exchange (W/m2/K)")
        self._field(arctic, 16, "arctic_lateral_ocean_heat_transport", "Signed lower-latitude ocean heat convergence (W/m2 per ice-fraction anomaly)")
        self._field(arctic, 17, "arctic_forced_ocean_heat_convergence", "Warming-driven Arctic ocean heat convergence (W/m2/K)")
        self._field(arctic, 18, "arctic_new_ice_local_thickness", "New-ice local thickness scale (m)")
        self._field(arctic, 19, "arctic_full_cover_equivalent_thickness", "Full-cover equivalent thickness (m)")
        self._field(arctic, 20, "arctic_ice_concentration_exponent", "Reference compact-pack concentration exponent")
        self._field(arctic, 21, "arctic_ice_area_formation_temperature_scale", "New-ice formation temperature scale (deg C)")
        self._field(arctic, 22, "arctic_ice_area_formation_volume_sensitivity", "Formation volume-support sensitivity")
        self._field(arctic, 23, "arctic_ice_area_melt_thickness", "Lateral-melt thickness scale (m)")
        self._field(arctic, 24, "arctic_ice_area_lateral_melt_efficiency", "Lateral-melt efficiency")
        self._field(arctic, 25, "arctic_ice_area_thinning_melt_amplification", "Thin-pack lateral-melt amplification")
        self._field(arctic, 26, "arctic_ice_area_compaction_years", "Excess-area compaction timescale (years)")
        self._field(arctic, 27, "arctic_ice_area_ridging_threshold", "Ridging onset concentration")
        self._field(arctic, 28, "arctic_ice_area_ridging_rate", "Ridging area-reduction rate (/year)")
        self._field(arctic, 29, "arctic_ice_area_divergence_rate", "Background lead-opening divergence rate (/year)")
        self._field(arctic, 30, "arctic_ice_area_thin_pack_divergence_rate", "Thin-pack deformation/divergence rate (/year)")
        self._field(arctic, 31, "arctic_greenland_marine_influence", "Greenland maritime Arctic influence")
        self._field(arctic, 32, "arctic_winter_lead_closure_fraction", "Legacy cold-season lead closure (disabled by default)")
        self._field(arctic, 33, "arctic_winter_lead_closure_onset_fraction", "Lead-closure onset deficit fraction")
        self._field(arctic, 34, "arctic_winter_lead_closure_temperature_scale", "Lead-closure temperature scale (deg C)")
        self._field(arctic, 35, "arctic_atlantic_reference_ocean_temperature", "Atlantic reference ocean temperature (deg C)")
        self._field(arctic, 36, "arctic_non_atlantic_reference_ocean_temperature", "Central-Arctic reference ocean temperature (deg C)")
        self._field(arctic, 37, "arctic_reference_ocean_heat_capacity", "Reference ocean heat capacity (W yr/m2/K)")
        self._field(arctic, 38, "arctic_reference_ocean_restoring", "Reference ocean restoring (W/m2/K)")
        self._field(arctic, 39, "arctic_air_memory_years", "SAT diagnostic memory (years)")
        self._field(arctic, 40, "arctic_forced_ocean_heat_convergence_onset", "Forced ocean convergence onset warming (C)")
        self._field(arctic, 41, "arctic_forced_ocean_heat_convergence_ice_fraction_exponent", "Forced ocean convergence ice-fraction exponent (0 disables last-ice attenuation)")
        self._field(arctic, 42, "arctic_forced_ocean_heat_convergence_saturation_scale", "Forced ocean convergence saturation scale (C)")
        self._field(arctic, 43, "arctic_ice_area_formation_support_floor", "Minimum winter formation support")
        self._field(arctic, 42, "arctic_phase_restoring_deficit_saturation", "Depleted-pack restoring saturation fraction")
        self._field(arctic, 43, "arctic_phase_restoring_max_deficit_flux", "Maximum depleted-pack restoring flux (W/m2)")
        self._field(arctic, 44, "arctic_max_equivalent_thickness", "Grid-equivalent abort threshold (m)")
        self._field(arctic, 45, "arctic_max_local_ice_thickness", "Local-thickness abort threshold (m)")
        self._field(arctic, 46, "arctic_ice_area_thick_pack_resistance_exponent", "Deprecated thick-pack resistance exponent (0 by default)")

    def _mc_range_row(
        self,
        parent: ttk.Frame,
        row: int,
        range_id: str,
        config_field: str,
        label: str,
        help_text: str,
    ) -> None:
        enabled_key = f"mc_{range_id}_enabled"
        minimum_key = f"mc_{range_id}_min"
        maximum_key = f"mc_{range_id}_max"
        checkbox = ttk.Checkbutton(parent, variable=self.variables[enabled_key])
        checkbox.grid(row=row, column=0, sticky="w", padx=(0, 6), pady=2)
        parameter_label = ttk.Label(parent, text=label)
        parameter_label.grid(row=row, column=1, sticky="w", pady=2)
        minimum = ttk.Entry(parent, textvariable=self.variables[minimum_key], width=12)
        maximum = ttk.Entry(parent, textvariable=self.variables[maximum_key], width=12)
        minimum.grid(row=row, column=2, sticky="ew", padx=(8, 4), pady=2)
        maximum.grid(row=row, column=3, sticky="ew", padx=(4, 8), pady=2)
        ttk.Label(parent, text=help_text, foreground="#666666").grid(
            row=row, column=4, sticky="w", pady=2
        )
        info = ttk.Label(parent, text="ⓘ", foreground="#356aa0", cursor="question_arrow")
        info.grid(row=row, column=5, sticky="w", padx=(6, 0), pady=2)
        range_note = (
            f"Custom min-max entries replace the built-in prior for this parameter. "
            f"Displayed units: {help_text or 'dimensionless'}."
        )
        for target in (checkbox, parameter_label, minimum, maximum, info):
            self._attach_tooltip(target, config_field, range_note)
        self.widgets[enabled_key] = checkbox
        self.widgets[minimum_key] = minimum
        self.widgets[maximum_key] = maximum

    def _build_monte_carlo_tab(self, notebook: ttk.Notebook) -> None:
        tab = self._new_tab(notebook, "Monte Carlo")
        controls = self._section(tab, "Ensemble controls", 0)
        self._checkbox(
            controls,
            0,
            "monte_carlo_enabled",
            "Run a Monte Carlo uncertainty ensemble",
        )
        self._field(
            controls,
            1,
            "mc_constraint_mode",
            "Posterior weighting",
            values=MONTE_CARLO_CONSTRAINT_MODES,
            help_text="None = run only the scenario selected in the Experiment tab",
        )
        ttk.Label(
            controls,
            text=(
                "AR6 modes automatically run the ECS, TCR and historical "
                "diagnostics required for posterior weighting."
            ),
            foreground="#666666",
            wraplength=760,
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(2, 6))
        self._field(controls, 3, "mc_runs", "Number of Monte Carlo simulations")
        self._field(
            controls,
            4,
            "mc_workers",
            "Parallel workers",
            help_text="0 = automatic, up to 8",
        )
        self._field(
            controls,
            14,
            "mc_member_timeout_seconds",
            "Member timeout (seconds)",
            help_text="A stalled worker is terminated and checkpointed",
        )
        self._field(
            controls,
            15,
            "mc_heartbeat_seconds",
            "Progress heartbeat (seconds)",
            help_text="Print progress even when no member has completed",
        )
        self._checkbox(
            controls,
            16,
            "mc_resume",
            "Resume from compatible member checkpoints",
        )
        self._checkbox(
            controls,
            17,
            "mc_retry_failed_on_resume",
            "Retry failed or timed-out checkpoints when resuming",
            help_text="Successful checkpoints are preserved; transient failures are rerun.",
        )
        self._field(
            controls,
            5,
            "mc_seed",
            "Random seed",
            help_text="0 = generate from the system clock; nonzero = reproducible",
        )
        self._field(
            controls,
            6,
            "mc_design",
            "Sampling design",
            values=MONTE_CARLO_DESIGNS,
            help_text="Sobol gives the most even coverage; powers of two are ideal",
        )
        self._field(
            controls,
            7,
            "mc_sampling",
            "Marginal distribution",
            values=MONTE_CARLO_SAMPLING,
        )
        self._checkbox(
            controls,
            8,
            "mc_use_science_defaults",
            "Use built-in broad physical priors (replaces custom ranges)",
            help_text=(
                "Samples the full built-in climate and AMOC parameter set using "
                "parameter-specific distributions instead of the custom range table."
            ),
        )
        self._checkbox(
            controls,
            9,
            "mc_correlated_priors",
            "Correlate physically related sampled parameters",
            help_text=(
                "Applies the documented Gaussian-copula correlations. This changes "
                "joint combinations, not individual parameter ranges."
            ),
        )
        self._field(
            controls,
            10,
            "mc_max_plotted",
            "Maximum individual curves",
            help_text="0 = plot every successful prior member",
        )
        self._checkbox(
            controls,
            11,
            "mc_save_long_csv",
            "Save every member-year row to a large CSV",
        )
        self._checkbox(
            controls,
            12,
            "mc_no_plots",
            "Write numerical ensemble products without rendering PNG figures",
        )
        self._checkbox(
            controls,
            13,
            "mc_diagnose_each",
            "Run extra ECS/TCR diagnostic experiments for every member",
        )
        ttk.Label(
            controls,
            text=(
                "Default behavior is selected-scenario only: an SSP5-8.5 ensemble "
                "runs SSP5-8.5 and nothing else. AR6 posterior weighting explicitly "
                "runs the calibration experiments required for its weights. "
                "Science-informed parameter ranges are opt-in and never replace "
                "your custom min/max table unless that option is checked. All ensemble "
                "plots retain 1-99%, 5-95%, and 17-83% bands."
            ),
            foreground="#555555",
            wraplength=720,
            justify="left",
        ).grid(row=13, column=0, columnspan=3, sticky="w", pady=(8, 2))

        sweep = self._section(tab, "CO2 target sweep", 1)
        self._checkbox(
            sweep, 0, "mc_co2_target_sweep_enabled",
            "Sweep linearly ramped CO2 targets with paired Monte Carlo members",
            help_text=(
                "Reuses each sampled parameter member at every target so changes "
                "in the conditional collapse fraction are attributable to CO2 rather than a new draw."
            ),
        )
        self._field(sweep, 1, "mc_sweep_start_ppm", "Starting CO2 (ppm)")
        self._field(
            sweep, 2, "mc_sweep_target_mode", "Target selection",
            values=["increments", "specific"],
            help_text="Choose regular increments or the exact target list below.",
        )
        self._field(sweep, 3, "mc_sweep_step_ppm", "Target increment (ppm)")
        self._field(sweep, 4, "mc_sweep_max_ppm", "Maximum target (ppm)")
        self._field(
            sweep, 5, "mc_sweep_specific_targets", "Set CO2 targets (ppm)",
            help_text=(
                "Comma, space, or semicolon separated, for example "
                "200,300,600,1200. Targets below the common start use descending ramps."
            ),
        )
        self._field(
            sweep, 6, "mc_sweep_initial_equilibration_years",
            "Non-reference start spinup (years)",
            help_text=(
                "Used only when Starting CO2 differs from the model reference. "
                "Every target then begins from the same equilibrated member state."
            ),
        )
        self._field(sweep, 7, "mc_sweep_ramp_years", "Ramp duration (years)")
        self._field(sweep, 8, "mc_sweep_hold_years", "Hold duration (years)")
        self._field(sweep, 9, "mc_sweep_collapse_window_years", "Final collapse window (years)")
        self._field(sweep, 10, "mc_sweep_persistence_fraction", "Persistence fraction")
        self._field(sweep, 11, "mc_sweep_recovery_years", "Disqualifying recovery (years)")
        self._field(sweep, 12, "mc_sweep_bootstrap_samples", "Bootstrap samples")
        self._field(sweep, 13, "mc_sweep_confidence_level", "Confidence level")
        self._field(
            sweep, 14, "mc_sweep_plot_mode", "Trajectory plot mode",
            values=["mean", "all"],
            help_text="Mean = one ensemble-mean line per target; all = member curves plus means.",
        )
        self._checkbox(
            sweep, 15, "mc_sweep_allow_exploratory_target_counts",
            "Allow fewer than 20 usable members at a target",
            help_text=(
                "Keeps the independent 80% survival gate, but permits explicitly "
                "exploratory output if a sweep requested at least 20 members and "
                "one target retains fewer than 20. Leave off for quantitative runs."
            ),
        )
        ttk.Label(
            sweep,
            text=(
                "The Number of Monte Carlo simulations above is interpreted as members "
                "per CO2 target. Increment mode includes the start concentration as a "
                "control target; specific mode runs exactly the listed targets. "
                "Targets below the common start use descending ramps without changing "
                "the shared pre-forcing state."
            ),
            foreground="#555555", wraplength=720, justify="left",
        ).grid(row=16, column=0, columnspan=3, sticky="w", pady=(6, 2))

        ranges = self._section(tab, "Custom parameter min-max ranges", 2)
        ranges.columnconfigure(1, weight=1)
        ttk.Label(
            ranges,
            text=(
                "These controls are used only when the built-in physical-prior "
                "prior checkbox is off."
            ),
            foreground="#555555",
            wraplength=700,
            justify="left",
        ).grid(row=0, column=0, columnspan=5, sticky="w", pady=(0, 6))
        ttk.Label(ranges, text="Use", font=("Segoe UI", 9, "bold")).grid(row=1, column=0, sticky="w")
        ttk.Label(ranges, text="Parameter", font=("Segoe UI", 9, "bold")).grid(row=1, column=1, sticky="w")
        ttk.Label(ranges, text="Minimum", font=("Segoe UI", 9, "bold")).grid(row=1, column=2, sticky="w", padx=(8, 4))
        ttk.Label(ranges, text="Maximum", font=("Segoe UI", 9, "bold")).grid(row=1, column=3, sticky="w", padx=(4, 8))
        ttk.Label(ranges, text="Units", font=("Segoe UI", 9, "bold")).grid(row=1, column=4, sticky="w")
        for row, (range_id, field_name, label, _minimum, _maximum, help_text) in enumerate(MC_RANGE_SPECS, start=2):
            self._mc_range_row(ranges, row, range_id, field_name, label, help_text)

    def _build_amoc_tab(self, notebook: ttk.Notebook) -> None:
        tab = self._new_tab(notebook, "AMOC and freshwater")

        freshwater = self._section(tab, "Freshwater forcing", 0)
        self._field(freshwater, 0, "freshwater_hosing", "Explicit hosing (Sv)")
        self._field(
            freshwater, 1, "hydrological_freshwater", "Hydrological freshwater (Sv/K)"
        )
        self._field(
            freshwater, 2, "hydrological_freshwater_north_fraction", "Hydrological share to North Atlantic"
        )
        self._field(
            freshwater, 3, "greenland_freshwater", "Greenland freshwater (Sv/K)"
        )
        self._field(
            freshwater, 4, "greenland_freshwater_threshold", "Greenland warming threshold (degC)"
        )
        self._field(
            freshwater, 5, "greenland_freshwater_adjustment_years", "Greenland response time (years)"
        )
        self._field(
            freshwater, 6, "greenland_initial_ice_mass_gt", "Initial Greenland ice reservoir (Gt)"
        )
        self._field(
            freshwater, 7, "greenland_depletion_exponent", "Greenland depletion exponent"
        )
        self._field(
            freshwater, 8, "greenland_max_freshwater_sv", "Maximum Greenland freshwater flux (Sv)"
        )
        self._checkbox(
            freshwater, 9, "greenland_surface_mass_balance_enabled",
            "Enable reduced Greenland surface mass balance",
        )
        self._field(freshwater, 10, "greenland_dynamic_discharge_fraction", "Greenland dynamic-discharge share")
        self._field(freshwater, 11, "greenland_reference_annual_temperature_c", "Greenland reference annual temperature (degC)")
        self._field(freshwater, 12, "greenland_reference_seasonal_amplitude_c", "Greenland seasonal temperature amplitude (degC)")
        self._field(freshwater, 13, "greenland_pdd_melt_factor_gt_per_degree_day", "Greenland PDD melt factor (Gt/degree-day)")
        self._field(freshwater, 14, "greenland_baseline_precipitation_gt_per_year", "Greenland baseline precipitation (Gt/year)")
        self._field(freshwater, 15, "greenland_precipitation_fraction_per_k", "Greenland precipitation response per K")
        self._field(freshwater, 16, "greenland_snow_rain_transition_c", "Greenland snow-rain transition (degC)")
        self._field(freshwater, 17, "greenland_snow_rain_transition_width_c", "Greenland snow-rain transition width (degC)")
        self._field(freshwater, 18, "greenland_meltwater_retention_fraction", "Greenland meltwater retention fraction")
        self._field(freshwater, 19, "greenland_retention_loss_fraction_per_k", "Greenland retention loss per K")
        self._field(
            freshwater, 20, "warming_freshwater", "Legacy total override (optional Sv/K)"
        )
        self._field(
            freshwater, 21, "freshwater_start_fraction", "Hosing start fraction"
        )
        self._field(
            freshwater, 22, "freshwater_ramp_years", "Hosing ramp duration (years)"
        )
        self._field(
            freshwater, 23, "freshwater_compensation_mode", "Compensation mode",
            values=COMPENSATION_MODES,
        )
        self._field(
            freshwater, 24, "freshwater_compensation_tropical_fraction",
            "Tropical compensation fraction",
        )

        dynamics = self._section(tab, "AMOC density and adjustment", 1)
        self._field(
            dynamics,
            0,
            "amoc_temperature_coupling",
            "Temperature-density coupling",
        )
        self._field(
            dynamics, 2, "amoc_adjustment_years", "Adjustment time (years)"
        )
        self._field(
            dynamics, 3, "amoc_heat_transport", "Overturning heat transport (PW/Sv)"
        )
        self._field(
            dynamics, 4, "amoc_surface_heat_coupling", "Surface heat coupling fraction"
        )
        self._field(
            dynamics, 5, "amoc_heat_response_damping", "AMOC temperature damping (W/m2/K)"
        )
        self._field(
            dynamics, 6, "atlantic_gyre_heat_transport", "Atlantic gyre heat transport (PW)"
        )
        self._field(
            dynamics, 7, "amoc_density_exponent", "Density transport exponent"
        )
        self._field(
            dynamics, 8, "amoc_depth_exponent", "Hydraulic depth exponent"
        )
        self._field(
            dynamics, 9, "amoc_eddy_depth_exponent", "Eddy depth exponent"
        )
        self._field(
            dynamics, 10, "amoc_collapse_threshold", "Collapse threshold (Sv)"
        )
        self._field(
            dynamics, 11, "amoc_reference_density_driver", "Reference absolute density driver"
        )
        self._field(
            dynamics, 12, "amoc_minimum_initial_density_ratio", "Minimum initial density-margin ratio"
        )
        self._field(
            dynamics, 13, "amoc_maximum_initial_density_ratio", "Maximum initial density-margin ratio"
        )
        self._checkbox(
            dynamics, 14, "amoc_enforce_initial_density_constraint",
            "Reject physically fragile initial density states"
        )
        self._checkbox(
            dynamics, 15, "amoc_allow_reversal",
            "Allow exploratory negative AMOC reversal"
        )
        self._field(
            dynamics, 16, "amoc_coupling_scheme",
            "Coupled AMOC integration scheme",
            values=["euler", "heun"],
        )

        convection = self._section(tab, "Deep convection response", 2)
        self._field(
            convection, 2, "amoc_convection_density_scale_factor",
            "Density normalization scale"
        )
        self._field(
            convection, 3, "amoc_convection_minimum_fraction",
            "Residual convection fraction"
        )
        self._field(
            convection, 5, "amoc_convective_mixing_reference_sv",
            "Convective salt exchange (Sv)"
        )
        self._field(
            convection, 6, "amoc_convective_mixing_exponent",
            "Convective mixing exponent"
        )
        self._field(
            convection, 7, "amoc_convection_entrainment_feedback",
            "Entrainment feedback"
        )
        self._field(
            convection, 8, "amoc_convection_adjustment_years",
            "Weakening adjustment (years)"
        )
        self._field(
            convection, 9, "amoc_convection_recovery_years",
            "Recovery adjustment (years)"
        )

        pycnocline = self._section(tab, "Pycnocline and transport", 3)
        self._field(
            pycnocline, 0, "amoc_pycnocline_depth", "Initial pycnocline depth (m)"
        )
        self._field(
            pycnocline, 1, "amoc_pycnocline_area", "Pycnocline area (m2)"
        )
        self._field(
            pycnocline, 2, "amoc_pycnocline_feedback_strength",
            "AMOC depth-feedback strength"
        )
        self._field(pycnocline, 4, "amoc_ekman_inflow", "Ekman inflow (Sv)")
        self._field(pycnocline, 5, "amoc_upwelling", "Reference upwelling (Sv)")
        self._field(
            pycnocline, 6, "amoc_eddy_outflow", "Reference eddy outflow (Sv)"
        )
        self._field(pycnocline, 7, "amoc_north_gyre", "Northern gyre exchange (Sv)")
        self._field(
            pycnocline, 8, "amoc_southern_gyre", "Southern gyre exchange (Sv)"
        )
        self._field(
            pycnocline,
            9,
            "amoc_southern_external_exchange",
            "Southern Ocean-external anomaly exchange (Sv)",
            help_text="Conservative exchange; zero tendency in the control state",
        )
        self._field(
            pycnocline,
            10,
            "amoc_south_atlantic_external_exchange",
            "South Atlantic-external anomaly exchange (Sv)",
            help_text="Damps closed-box salinity drift while conserving total salt",
        )
        self._field(
            pycnocline, 11, "amoc_southern_ocean_structure",
            "Southern Ocean structure", values=AMOC_SOUTHERN_OCEAN_STRUCTURES,
        )
        self._field(pycnocline, 12, "amoc_southern_wind_sensitivity", "Southern wind sensitivity per K")
        self._field(pycnocline, 13, "amoc_southern_upwelling_sensitivity", "Southern upwelling sensitivity per K")
        self._field(pycnocline, 14, "amoc_southern_response_min", "Southern response minimum multiplier")
        self._field(pycnocline, 15, "amoc_southern_response_max", "Southern response maximum multiplier")
        self._field(
            pycnocline, 16, "amoc_indo_pacific_compensation",
            "Indo-Pacific compensation", values=AMOC_INDO_PACIFIC_MODES,
        )
        self._field(pycnocline, 17, "amoc_indo_pacific_compensation_fraction", "Indo-Pacific compensation fraction")
        self._field(pycnocline, 18, "amoc_indo_pacific_compensation_max", "Maximum Indo-Pacific compensation (Sv)")

        fovs = self._section(tab, "South Atlantic salt-advection diagnostic", 4)
        self._field(
            fovs,
            0,
            "initial_fovs",
            "Initial FovS at 34.5 S (Sv)",
            help_text="Negative = overturning imports salinity into the Atlantic",
        )
        self._field(
            fovs,
            1,
            "fovs_reference_salinity",
            "FovS reference salinity S0 (PSU)",
        )

    def _build_hysteresis_tab(self, notebook: ttk.Notebook) -> None:
        tab = self._new_tab(notebook, "AMOC hysteresis")
        experiment = self._section(tab, "Equilibrium continuation", 0)
        self._checkbox(
            experiment,
            0,
            "run_amoc_hysteresis",
            "Run stability-tested AMOC equilibrium continuation",
        )
        self._field(
            experiment, 1, "hysteresis_max_hosing", "Maximum equilibrium hosing (Sv)"
        )
        self._field(experiment, 2, "hysteresis_step", "Equilibrium forcing increment (Sv)")
        ttk.Label(
            experiment,
            text=(
                "The solver finds fixed points and checks Jacobian stability. "
                "It does not use a fixed number of years per forcing step."
            ),
            foreground="#666666",
            wraplength=700,
            justify="left",
        ).grid(row=3, column=0, columnspan=3, sticky="w", pady=(8, 2))

    def _apply_defaults(self) -> None:
        for key, value in DEFAULTS.items():
            self.variables[key].set(value)

    def _on_value_changed(self) -> None:
        if self.loaded_resume_command_args is not None and not self._loading_saved_progress:
            self.loaded_resume_command_args = None
            self.loaded_resume_script = None
            self.status_var.set("Saved-run command cleared after settings changed")
        self.update_scenario_state()
        self.refresh_command_preview()

    def get_values(self) -> dict[str, Any]:
        return {key: variable.get() for key, variable in self.variables.items()}

    def set_values(self, values: dict[str, Any]) -> None:
        for key, value in values.items():
            if key in self.variables:
                self.variables[key].set(value)

    def apply_preset(self) -> None:
        preset_name = self.preset_var.get()
        preset = PRESETS.get(preset_name)
        if preset is None:
            return
        combined = dict(DEFAULTS)
        combined.update(preset)
        self.set_values(combined)
        self.append_log(f"Applied preset: {preset_name}\n")

    def update_scenario_state(self) -> None:
        if not self.widgets:
            return
        scenario = str(self.variables["scenario"].get())
        run_all_ssp = bool(self.variables["run_all_ssp"].get())
        is_ssp = run_all_ssp or scenario in SSP_SCENARIOS or scenario == "hybrid_ssp"
        is_hybrid = not run_all_ssp and scenario == "hybrid_ssp"
        is_one_percent = scenario == "one_percent"
        is_percent_ramp = scenario == "percent_ramp_hold"
        is_overshoot = scenario == "overshoot"
        is_linear = scenario == "linear"
        is_constant_or_step = scenario in {"constant", "step_2x"}

        self._set_widget_state("scenario", "disabled" if run_all_ssp else "readonly")
        self._set_widget_state("forcing_mode", "readonly" if is_ssp else "disabled")
        for key in ("ssp_before", "ssp_after"):
            self._set_widget_state(key, "readonly" if is_hybrid else "disabled")
        for key in ("switch_year", "transition_years"):
            self._set_widget_state(key, "normal" if is_hybrid else "disabled")

        self._set_widget_state("co2_start", "normal" if not is_ssp else "disabled")
        self._set_widget_state("co2_end", "normal" if is_linear or is_overshoot else "disabled")
        self._set_widget_state("co2_peak", "normal" if is_overshoot else "disabled")
        self._set_widget_state("peak_fraction", "normal" if is_overshoot else "disabled")
        self._set_widget_state(
            "one_percent_cap", "normal" if is_one_percent else "disabled"
        )
        for key in (
            "co2_growth_cap",
            "co2_hold_years",
            "percent_ramp_compare_rates",
        ):
            self._set_widget_state(key, "normal" if is_percent_ramp else "disabled")
        self._set_widget_state("years", "disabled" if is_percent_ramp else "normal")
        if is_constant_or_step:
            self._set_widget_state("co2_start", "normal")

        monte_carlo = bool(self.variables["monte_carlo_enabled"].get())
        self._set_widget_state(
            "run_all_ssp", "disabled" if monte_carlo else "normal"
        )
        self._set_widget_state(
            "resume_all_ssp",
            "normal" if (run_all_ssp and not monte_carlo) else "disabled",
        )
        target_sweep = monte_carlo and bool(self.variables["mc_co2_target_sweep_enabled"].get())
        self._set_widget_state("mc_co2_target_sweep_enabled", "normal" if monte_carlo else "disabled")
        sweep_mode = str(self.variables["mc_sweep_target_mode"].get())
        for key in (
            "mc_sweep_start_ppm", "mc_sweep_target_mode",
            "mc_sweep_step_ppm", "mc_sweep_max_ppm", "mc_sweep_specific_targets",
            "mc_sweep_initial_equilibration_years",
            "mc_sweep_ramp_years", "mc_sweep_hold_years",
            "mc_sweep_collapse_window_years", "mc_sweep_persistence_fraction",
            "mc_sweep_recovery_years", "mc_sweep_bootstrap_samples",
            "mc_sweep_confidence_level", "mc_sweep_plot_mode",
            "mc_sweep_allow_exploratory_target_counts",
        ):
            if not target_sweep:
                desired = "disabled"
            elif key in {"mc_sweep_target_mode", "mc_sweep_plot_mode"}:
                desired = "readonly"
            elif key == "mc_sweep_allow_exploratory_target_counts":
                desired = "normal"
            elif key in {"mc_sweep_step_ppm", "mc_sweep_max_ppm"}:
                desired = "normal" if sweep_mode == "increments" else "disabled"
            elif key == "mc_sweep_specific_targets":
                desired = "normal" if sweep_mode == "specific" else "disabled"
            else:
                desired = "normal"
            self._set_widget_state(key, desired)
        run_hysteresis = bool(self.variables["run_amoc_hysteresis"].get())
        for key in (
            "hysteresis_max_hosing",
            "hysteresis_step",
            "hysteresis_years_per_step",
            "hysteresis_spinup_years",
        ):
            self._set_widget_state(
                key, "normal" if (run_hysteresis and not monte_carlo) else "disabled"
            )

        # Keep the core ensemble controls editable even before Monte Carlo is
        # enabled. This avoids a confusing Windows/ttk state where the checkbox
        # can appear selected while seed and worker entries remain visually
        # disabled. These values are only used when monte_carlo_enabled is true.
        for key in (
            "mc_runs",
            "mc_workers",
            "mc_seed",
            "mc_sampling",
            "mc_design",
            "mc_constraint_mode",
            "mc_use_science_defaults",
            "mc_correlated_priors",
            "mc_max_plotted",
            "mc_save_long_csv",
            "mc_no_plots",
            "mc_diagnose_each",
        ):
            desired = (
                "readonly"
                if key in {"mc_sampling", "mc_design", "mc_constraint_mode"}
                else "normal"
            )
            self._set_widget_state(key, desired)
        use_science_defaults = bool(
            self.variables["mc_use_science_defaults"].get()
        )
        custom_ranges_active = monte_carlo and not use_science_defaults
        for range_id, _config_field, _label, _minimum, _maximum, _help in MC_RANGE_SPECS:
            enabled_key = f"mc_{range_id}_enabled"
            self._set_widget_state(
                enabled_key, "normal" if custom_ranges_active else "disabled"
            )
            range_enabled = custom_ranges_active and bool(
                self.variables[enabled_key].get()
            )
            self._set_widget_state(
                f"mc_{range_id}_min", "normal" if range_enabled else "disabled"
            )
            self._set_widget_state(
                f"mc_{range_id}_max", "normal" if range_enabled else "disabled"
            )

        self._set_widget_state(
            "run_amoc_hysteresis", "disabled" if monte_carlo else "normal"
        )
        run_diagnostics = bool(self.variables["run_diagnostics"].get())
        self._set_widget_state(
            "run_diagnostics", "disabled" if monte_carlo else "normal"
        )
        mc_extra_diagnostics = monte_carlo and (
            bool(self.variables["mc_diagnose_each"].get())
            or str(self.variables["mc_constraint_mode"].get()) != "none"
        )
        self._set_widget_state(
            "equilibrium_years",
            "normal" if (mc_extra_diagnostics or run_diagnostics) else "disabled",
        )

    def _set_widget_state(self, key: str, state: str) -> None:
        widget = self.widgets.get(key)
        if widget is None:
            return
        try:
            widget.configure(state=state)
        except tk.TclError:
            pass

    def refresh_command_preview(self) -> None:
        try:
            if self.loaded_resume_command_args is not None:
                command = self._build_loaded_resume_command(self.resolve_output_path())
            else:
                command = build_cli_command(self.get_values())
            self.command_preview_var.set(format_command(command))
        except Exception:
            self.command_preview_var.set("")

    def copy_command(self) -> None:
        command = self.command_preview_var.get()
        self.root.clipboard_clear()
        self.root.clipboard_append(command)
        self.status_var.set("Command copied")

    def browse_output(self) -> None:
        initial = self.resolve_output_path()
        selected = filedialog.askdirectory(
            parent=self.root,
            title="Choose output folder",
            initialdir=str(initial.parent if initial.name else BASE_DIR),
        )
        if selected:
            self.variables["output"].set(selected)

    def resolve_output_path(self) -> Path:
        raw = str(self.variables["output"].get()).strip()
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = BASE_DIR / path
        return path.resolve()

    def run_simulation(self) -> None:
        if self.process is not None or self.launch_in_progress:
            messagebox.showinfo(APP_TITLE, "A simulation is already running.")
            return
        values = self.get_values()
        loaded_resume = self.loaded_resume_command_args is not None
        if not loaded_resume:
            try:
                validate_values(values)
            except ValueError as exc:
                messagebox.showerror("Invalid settings", str(exc), parent=self.root)
                return

        output_path = self.resolve_output_path()
        resume = loaded_resume or (
            bool(values.get("monte_carlo_enabled", False))
            and bool(values.get("mc_resume", False))
        ) or bool(values.get("resume_all_ssp", False))
        overwrite = False
        if output_path.exists() and not resume:
            overwrite = messagebox.askyesno(
                "Output folder exists",
                f"The output folder already exists:\n\n{output_path}\n\n"
                "Overwrite it and delete its current contents?",
                parent=self.root,
                default=messagebox.NO,
            )
            if not overwrite:
                self.status_var.set("Run cancelled; existing output preserved")
                return

        if loaded_resume:
            command = self._build_loaded_resume_command(output_path)
        else:
            command = build_cli_command(values)
            if overwrite:
                command.append("--overwrite-output")
        self.stop_requested = False
        self.closing_after_stop = False
        self.launch_in_progress = True
        self.clear_log()
        self.append_log("Running command or ensemble:\n")
        self.append_log(format_command(command) + "\n\n")
        self.status_var.set("Running")
        self.progress.start(12)
        self.run_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.save_button.configure(state="disabled")
        self.load_button.configure(state="disabled")
        self.load_progress_button.configure(state="disabled")

        thread = threading.Thread(
            target=self._run_subprocess, args=(command,), daemon=True
        )
        thread.start()

    def _run_subprocess(self, command: list[str]) -> None:
        try:
            creationflags = 0
            popen_kwargs: dict[str, Any] = {}
            if os.name == "nt":
                creationflags = (
                    subprocess.CREATE_NO_WINDOW
                    | subprocess.CREATE_NEW_PROCESS_GROUP
                )
            else:
                popen_kwargs["start_new_session"] = True

            process = subprocess.Popen(
                command,
                cwd=str(BASE_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=creationflags,
                **popen_kwargs,
            )
            self.process = process
            self.output_queue.put(("started", process.pid))
            # The window can be closed while Popen is still starting. Honour
            # that request immediately after the process group becomes real.
            if self.stop_requested:
                success, details = terminate_process_tree(process)
                self.output_queue.put(("stop_result", (success, details)))
            assert process.stdout is not None
            for line in process.stdout:
                self.output_queue.put(("line", line))
            return_code = process.wait()
            self.output_queue.put(("done", return_code))
        except Exception as exc:
            self.output_queue.put(("error", str(exc)))

    def poll_output_queue(self) -> None:
        try:
            while True:
                kind, payload = self.output_queue.get_nowait()
                if kind == "started":
                    self.launch_in_progress = False
                elif kind == "line":
                    self.append_log(str(payload))
                elif kind == "done":
                    self._simulation_finished(int(payload))
                elif kind == "error":
                    self._simulation_error(str(payload))
                elif kind == "stop_result":
                    success, details = payload
                    self.append_log(str(details).rstrip() + "\n")
                    if not success:
                        self.status_var.set("Stop may have failed")
                        messagebox.showerror(
                            "Stop failed",
                            "The full process tree could not be confirmed stopped.\n\n"
                            + str(details),
                            parent=self.root,
                        )
        except queue.Empty:
            pass
        self.root.after(100, self.poll_output_queue)

    def _simulation_finished(self, return_code: int) -> None:
        was_stopped = self.stop_requested
        close_after_stop = self.closing_after_stop
        self.process = None
        self.launch_in_progress = False
        self.stop_requested = False
        self.closing_after_stop = False
        self.progress.stop()
        self.run_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.save_button.configure(state="normal")
        self.load_button.configure(state="normal")
        self.load_progress_button.configure(state="normal")

        if was_stopped:
            self.status_var.set("Stopped")
            self.append_log("\nSimulation and worker processes were stopped.\n")
            if close_after_stop:
                self.root.after(0, self.root.destroy)
            return

        if return_code == 0:
            self.status_var.set("Completed")
            self.append_log("\nSimulation completed successfully.\n")
            if messagebox.askyesno(
                "Simulation completed",
                "The simulation completed successfully. Open the output folder?",
                parent=self.root,
            ):
                self.open_output_folder()
        else:
            self.status_var.set(f"Failed with exit code {return_code}")
            self.append_log(f"\nSimulation failed with exit code {return_code}.\n")
            messagebox.showerror(
                "Simulation failed",
                f"The climate model exited with code {return_code}. See the log.",
                parent=self.root,
            )

    def _simulation_error(self, error: str) -> None:
        was_stopped = self.stop_requested
        close_after_stop = self.closing_after_stop
        self.process = None
        self.launch_in_progress = False
        self.stop_requested = False
        self.closing_after_stop = False
        self.progress.stop()
        self.run_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.save_button.configure(state="normal")
        self.load_button.configure(state="normal")
        self.load_progress_button.configure(state="normal")
        if was_stopped:
            self.status_var.set("Stopped")
            self.append_log("\nSimulation and worker processes were stopped.\n")
            if close_after_stop:
                self.root.after(0, self.root.destroy)
            return
        self.status_var.set("Launch failed")
        self.append_log(f"\nERROR: {error}\n")
        messagebox.showerror("Launch failed", error, parent=self.root)

    def stop_simulation(self) -> None:
        process = self.process
        if process is None and not self.launch_in_progress:
            return
        if not messagebox.askyesno(
            "Stop simulation",
            (
                "Terminate the running simulation and all parallel workers? "
                "Partial outputs may remain."
            ),
            parent=self.root,
        ):
            return

        self.stop_requested = True
        self.status_var.set("Stopping process tree")
        self.stop_button.configure(state="disabled")
        self.append_log("\nStopping simulation and all worker processes...\n")
        if process is None:
            self.append_log("Waiting for the launching process group to become available...\n")
            return
        threading.Thread(
            target=self._stop_process_tree_worker,
            args=(process,),
            daemon=True,
        ).start()

    def _stop_process_tree_worker(self, process: subprocess.Popen[str]) -> None:
        success, details = terminate_process_tree(process)
        self.output_queue.put(("stop_result", (success, details)))

    def append_log(self, text: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def clear_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def open_output_folder(self) -> None:
        path = self.resolve_output_path()
        path.mkdir(parents=True, exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except OSError as exc:
            messagebox.showerror("Cannot open folder", str(exc), parent=self.root)

    def _build_loaded_resume_command(self, output_path: Path) -> list[str]:
        if self.loaded_resume_command_args is None or self.loaded_resume_script is None:
            raise ValueError("No saved-run command is loaded.")
        source = [str(value) for value in self.loaded_resume_command_args]
        arguments: list[str] = []
        index = 0
        while index < len(source):
            argument = source[index]
            if argument in {"--overwrite-output", "--mc-resume"}:
                index += 1
                continue
            if argument == "--output":
                index += 2
                continue
            arguments.append(argument)
            index += 1
        arguments.extend(["--output", str(output_path), "--mc-resume"])
        return [preferred_python_executable(), str(self.loaded_resume_script), *arguments]

    def load_saved_progress(self) -> None:
        selected = filedialog.askdirectory(
            parent=self.root,
            title="Choose a saved Monte Carlo or CO2 sweep output folder",
            initialdir=str(self.resolve_output_path().parent),
        )
        if not selected:
            return
        output_path = Path(selected).expanduser().resolve()
        try:
            state = load_run_state(output_path)
            if state is None:
                raise ValueError(
                    "No long_run_state.json file was found in the selected folder."
                )
            run_kind = str(state.get("run_kind", ""))
            if run_kind == "monte_carlo":
                script = MONTE_CARLO_SCRIPT
            elif run_kind == "co2_target_sweep":
                script = CO2_TARGET_SWEEP_SCRIPT
            else:
                raise ValueError(f"Unsupported saved run kind: {run_kind!r}")
            settings = state.get("settings", {})
            if not isinstance(settings, dict):
                raise ValueError("The saved run does not contain valid settings metadata.")
            command_arguments = settings.get("command_arguments", [])
            if not isinstance(command_arguments, list) or not command_arguments:
                raise ValueError(
                    "This saved run predates exact command restoration. Resume it by "
                    "loading its original GUI settings and checking Resume, or start it "
                    "once with this release to create a fully loadable state."
                )

            self._loading_saved_progress = True
            try:
                self.variables["output"].set(str(output_path))
                self.variables["monte_carlo_enabled"].set(True)
                self.variables["mc_resume"].set(True)
                self.variables["mc_co2_target_sweep_enabled"].set(
                    run_kind == "co2_target_sweep"
                )
                self.variables["mc_seed"].set(str(state.get("seed_used", 0)))
                runs = settings.get("runs", state.get("total_members"))
                if runs is not None:
                    self.variables["mc_runs"].set(str(runs))
                sampling = settings.get("sampling", settings.get("distribution"))
                if sampling is not None:
                    self.variables["mc_sampling"].set(str(sampling))
                for setting_name, variable_name in (
                    ("design", "mc_design"),
                    ("constraint_mode", "mc_constraint_mode"),
                ):
                    if setting_name in settings:
                        self.variables[variable_name].set(str(settings[setting_name]))
                science_priors = settings.get(
                    "science_priors", settings.get("use_science_priors")
                )
                if science_priors is not None:
                    self.variables["mc_use_science_defaults"].set(bool(science_priors))
                if run_kind == "co2_target_sweep":
                    target_mode = str(settings.get("target_mode", "increments"))
                    self.variables["mc_sweep_target_mode"].set(target_mode)
                    targets = settings.get("targets_ppm", [])
                    if isinstance(targets, list) and targets:
                        base_config = settings.get("base_config", {})
                        start_value = (
                            base_config.get("co2_start_ppm", targets[0])
                            if isinstance(base_config, dict)
                            else targets[0]
                        )
                        self.variables["mc_sweep_start_ppm"].set(str(start_value))
                        self.variables["mc_sweep_max_ppm"].set(str(targets[-1]))
                        specific_input = settings.get("specific_targets_input")
                        self.variables["mc_sweep_specific_targets"].set(
                            str(specific_input)
                            if specific_input
                            else ",".join(f"{float(value):g}" for value in targets)
                        )
                        if len(targets) > 1:
                            self.variables["mc_sweep_step_ppm"].set(
                                f"{float(targets[1]) - float(targets[0]):g}"
                            )
                    for setting_name, variable_name in (
                        (
                            "initial_equilibration_years",
                            "mc_sweep_initial_equilibration_years",
                        ),
                        ("ramp_years", "mc_sweep_ramp_years"),
                        ("hold_years", "mc_sweep_hold_years"),
                        ("collapse_window_years", "mc_sweep_collapse_window_years"),
                        ("persistence_fraction", "mc_sweep_persistence_fraction"),
                        ("recovery_years", "mc_sweep_recovery_years"),
                    ):
                        if setting_name in settings:
                            self.variables[variable_name].set(str(settings[setting_name]))
                self.loaded_resume_command_args = [
                    str(argument) for argument in command_arguments
                ]
                self.loaded_resume_script = script
            finally:
                self._loading_saved_progress = False
            self.update_scenario_state()
            self.refresh_command_preview()
            description = describe_run_state(output_path)
            self.status_var.set("Saved run loaded; press Run simulation to resume")
            self.append_log(f"Loaded saved progress: {description}\n")
            messagebox.showinfo(
                "Saved run loaded",
                description + "\n\nPress Run simulation to resume from its atomic checkpoints.",
                parent=self.root,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            self.loaded_resume_command_args = None
            self.loaded_resume_script = None
            messagebox.showerror("Load saved run failed", str(exc), parent=self.root)

    def save_settings(self) -> None:
        selected = filedialog.asksaveasfilename(
            parent=self.root,
            title="Save climate-model settings",
            initialdir=str(BASE_DIR),
            initialfile="climate_model_settings.json",
            defaultextension=".json",
            filetypes=[("JSON settings", "*.json"), ("All files", "*.*")],
        )
        if not selected:
            return
        path = Path(selected)
        data = {
            "format": "emergent-climate-model-gui-settings",
            "version": 1,
            "settings": self.get_values(),
        }
        try:
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            self.status_var.set(f"Saved {path.name}")
        except OSError as exc:
            messagebox.showerror("Save failed", str(exc), parent=self.root)

    def load_settings(self) -> None:
        selected = filedialog.askopenfilename(
            parent=self.root,
            title="Load climate-model settings",
            initialdir=str(BASE_DIR),
            filetypes=[("JSON settings", "*.json"), ("All files", "*.*")],
        )
        if not selected:
            return
        path = Path(selected)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            settings = data.get("settings", data)
            if not isinstance(settings, dict):
                raise ValueError("The selected file does not contain settings.")
            self.set_values(settings)
            self.status_var.set(f"Loaded {path.name}")
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            messagebox.showerror("Load failed", str(exc), parent=self.root)

    def on_close(self) -> None:
        process = self.process
        if process is None and not self.launch_in_progress:
            self.root.destroy()
            return

        if not messagebox.askyesno(
            "Exit",
            "A simulation is running. Terminate it, stop all workers, and close?",
            parent=self.root,
        ):
            return

        self.stop_requested = True
        self.closing_after_stop = True
        self.status_var.set("Stopping before exit")
        self.run_button.configure(state="disabled")
        self.stop_button.configure(state="disabled")
        self.append_log("\nStopping simulation and all workers before exit...\n")
        if process is None:
            self.append_log("Waiting for the launching process group to become available...\n")
            return
        threading.Thread(
            target=self._stop_process_tree_worker,
            args=(process,),
            daemon=True,
        ).start()


def main() -> None:
    if not MODEL_SCRIPT.exists():
        raise FileNotFoundError(f"Missing model script: {MODEL_SCRIPT}")
    root = tk.Tk()
    ClimateModelGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
