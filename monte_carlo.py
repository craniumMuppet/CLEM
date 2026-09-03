#!/usr/bin/env python3
"""Scientifically constrained Monte Carlo ensembles for the climate model.

This module supports selected-scenario ensembles and optional posterior calibration.

* ``none``: run only the scenario chosen by the user, with equal member weights.
* ``ar6``: importance-weight members against AR6 climate diagnostics.
* ``ar6_amoc``: add AMOC, total Atlantic heat-transport, and FovS targets.

Selecting an AR6 mode is the explicit opt-in and automatically runs the
calibration experiments required by that mode. Science-informed parameter
ranges remain separately opt-in through ``--mc-use-science-priors``; otherwise
the exact min/max ranges supplied by the user are used.

Outputs include all-member spaghetti plots and weighted 1-99%, 5-95%, and
17-83% bands for temperature anomalies, AMOC, AMOC decline, FovS/salt
advection, FovS change, freshwater forcing, salinity contrast, pycnocline
state, and energy imbalance. Weighted endpoint distributions and p01/p05/p50/
p95/p99 maps are also exported.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import traceback
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Iterable, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import numpy as np
import pandas as pd
from scipy.stats import beta as beta_distribution, lognorm, norm, qmc, truncnorm

from amoc_outcomes import collapse_duration_diagnostics
from climate_model import (
    AMOC_SIX_SV_REFERENCE,
    MODEL_NAME,
    MODEL_VERSION,
    ModelConfig,
    ProcessClimateModel,
    build_parser,
    config_from_args,
    diagnose_climate_sensitivity,
    initial_amoc_density_diagnostics,
    parse_percent_ramp_rates,
    prepare_output_directory,
    resolved_scenario_config,
)

from run_state import (
    RUN_STATE_FORMAT,
    RUN_STATE_VERSION,
    compatible_checkpoint_count,
    initialize_run_state,
    load_run_state,
    output_directory_run_lock,
    saved_seed_for_resume,
    update_run_state,
)
from runtime_provenance import runtime_provenance
from worker_supervision import run_supervised_tasks, stable_fingerprint

MONTE_CARLO_VERSION = MODEL_VERSION
CONSTRAINT_MODES = ("none", "ar6", "ar6_amoc", "exploratory")
SAMPLING_DESIGNS = ("random", "latin_hypercube", "sobol")
SAMPLING_DISTRIBUTIONS = ("uniform", "triangular", "loguniform")
PERCENTILES = (1.0, 5.0, 17.0, 50.0, 83.0, 95.0, 99.0)
MINIMUM_SUCCESSFUL_ENSEMBLE_MEMBERS = 2
MAXIMUM_FAILED_MEMBER_FRACTION = 0.20
MINIMUM_QUANTITATIVE_UNCERTAINTY_MEMBERS = 20
MINIMUM_POSTERIOR_EFFECTIVE_SAMPLE_SIZE = 10.0
MINIMUM_POSTERIOR_EFFECTIVE_SAMPLE_FRACTION = 0.10


def validate_ensemble_survival(
    requested_members: int,
    successful_members: int,
    failed_members: int,
) -> dict[str, float | int]:
    """Reject ensembles whose realized sample is too truncated to interpret."""

    requested = int(requested_members)
    successful = int(successful_members)
    failed = int(failed_members)
    if requested <= 0 or successful < 0 or failed < 0 or successful + failed != requested:
        raise RuntimeError(
            "Ensemble accounting is inconsistent: "
            f"requested={requested}, successful={successful}, failed={failed}."
        )
    survival_fraction = successful / requested
    failed_fraction = failed / requested
    failures: list[str] = []
    if successful < MINIMUM_SUCCESSFUL_ENSEMBLE_MEMBERS:
        failures.append(
            f"only {successful} successful member(s); at least "
            f"{MINIMUM_SUCCESSFUL_ENSEMBLE_MEMBERS} are required"
        )
    if failed_fraction > MAXIMUM_FAILED_MEMBER_FRACTION + 1.0e-12:
        failures.append(
            f"failed-member fraction {failed_fraction:.3f} exceeds the release gate "
            f"of {MAXIMUM_FAILED_MEMBER_FRACTION:.3f}"
        )
    if failures:
        raise RuntimeError(
            "Ensemble uncertainty products were rejected: " + "; ".join(failures)
        )
    return {
        "requested_members": requested,
        "successful_members": successful,
        "failed_members": failed,
        "survival_fraction": float(survival_fraction),
        "failed_fraction": float(failed_fraction),
    }


def assess_ensemble_quality(
    requested_members: int,
    successful_members: int,
    failed_members: int,
    effective_sample_size: float,
    posterior_weighting_enabled: bool,
) -> dict[str, Any]:
    """Classify whether exported intervals support quantitative uncertainty use."""

    survival = validate_ensemble_survival(
        requested_members, successful_members, failed_members
    )
    successful = int(successful_members)
    ess = float(effective_sample_size)
    required_ess = (
        max(
            MINIMUM_POSTERIOR_EFFECTIVE_SAMPLE_SIZE,
            MINIMUM_POSTERIOR_EFFECTIVE_SAMPLE_FRACTION * successful,
        )
        if posterior_weighting_enabled
        else float(MINIMUM_QUANTITATIVE_UNCERTAINTY_MEMBERS)
    )
    member_gate = successful >= MINIMUM_QUANTITATIVE_UNCERTAINTY_MEMBERS
    ess_gate = ess >= required_ess - 1.0e-12
    uncertainty_valid = bool(member_gate and ess_gate)
    warnings: list[str] = []
    if not member_gate:
        warnings.append(
            f"Only {successful} successful members are available; quantitative "
            f"uncertainty products require at least "
            f"{MINIMUM_QUANTITATIVE_UNCERTAINTY_MEMBERS}."
        )
    if not ess_gate:
        warnings.append(
            f"Effective sample size {ess:.3f} is below the required {required_ess:.3f}."
        )
    return {
        **survival,
        "effective_sample_size": ess,
        "effective_sample_fraction": ess / successful,
        "minimum_successful_members_for_quantitative_uncertainty": (
            MINIMUM_QUANTITATIVE_UNCERTAINTY_MEMBERS
        ),
        "minimum_required_effective_sample_size": float(required_ess),
        "posterior_weighting_enabled": bool(posterior_weighting_enabled),
        "survival_gate_passed": True,
        "member_count_gate_passed": bool(member_gate),
        "effective_sample_size_gate_passed": bool(ess_gate),
        "uncertainty_products_valid_for_quantitative_use": uncertainty_valid,
        "quality_classification": (
            "quantitative_uncertainty_valid"
            if uncertainty_valid
            else "exploratory_only_invalid_quantitative_uncertainty"
        ),
        "warnings": warnings,
    }

def normalize_constraint_mode(mode: str) -> str:
    """Normalize the legacy exploratory name to the explicit no-weighting mode."""
    return "none" if mode == "exploratory" else mode


def constraints_enabled(mode: str) -> bool:
    return normalize_constraint_mode(mode) in {"ar6", "ar6_amoc"}



def resolve_random_seed(seed: int) -> tuple[int, str]:
    """Return a NumPy/SciPy-compatible seed and its provenance.

    A user-supplied nonzero seed is preserved exactly for reproducibility.
    Seed 0 is reserved for a clock-derived seed. The generated value is kept
    within the unsigned 32-bit range supported by NumPy and SciPy samplers and
    is written to the ensemble summary so the run can be reproduced later.
    """

    if seed < 0:
        raise ValueError(
            "Random seed cannot be negative. Use 0 to derive it from the system clock."
        )
    if seed != 0:
        return int(seed), "user"

    # Mix wall-clock and monotonic clock nanoseconds. The wall clock provides
    # the requested system-clock behavior, while the monotonic component avoids
    # accidental duplicates if two ensembles start within the same clock tick.
    clock_value = time.time_ns() ^ time.perf_counter_ns() ^ (os.getpid() << 16)
    resolved = int(clock_value % (2**32))
    if resolved == 0:
        resolved = 1
    return resolved, "system_clock"

# Friendly aliases accepted by --mc-range. Dataclass field names are accepted
# directly as well.
PARAMETER_ALIASES: dict[str, str] = {
    "co2_doubling_erf": "co2_doubling_erf_wm2",
    "relative_humidity": "relative_humidity",
    "longwave_spectral_factor": "longwave_spectral_factor",
    "moist_lapse_rate_weight": "moist_lapse_rate_weight",
    "water_vapor_height": "water_vapor_emission_height_km_per_lnq",
    "low_cloud_loss": "low_cloud_loss_fraction_per_k",
    "low_cloud_moisture_gain": "low_cloud_moisture_gain_fraction_per_lnq",
    "high_cloud_coupling": "high_cloud_temperature_coupling",
    "sea_ice_albedo": "sea_ice_albedo",
    "snow_albedo": "snow_albedo",
    "sea_ice_transition": "sea_ice_transition_c",
    "sea_ice_transition_width": "sea_ice_transition_width_c",
    "snow_transition": "snow_transition_c",
    "snow_transition_width": "snow_transition_width_c",
    "mixed_layer_heat_capacity": "ocean_mixed_layer_heat_capacity_wyr_m2_k",
    "deep_ocean_heat_capacity": "deep_ocean_heat_capacity_wyr_m2_k",
    "ocean_exchange": "ocean_heat_exchange_wm2_k",
    "land_ocean_exchange": "land_ocean_exchange_wm2_k",
    "meridional_diffusion": "meridional_diffusion_wm2_k",
    "freshwater_hosing": "freshwater_hosing_sv",
    "warming_freshwater": "hydrological_freshwater_sv_per_k",
    "hydrological_freshwater": "hydrological_freshwater_sv_per_k",
    "greenland_freshwater": "greenland_freshwater_sv_per_k",
    "greenland_adjustment_years": "greenland_freshwater_adjustment_years",
    "greenland_response_years": "greenland_freshwater_adjustment_years",
    "greenland_ice_mass_gt": "greenland_initial_ice_mass_gt",
    "greenland_depletion_exponent": "greenland_depletion_exponent",
    "greenland_max_freshwater": "greenland_max_freshwater_sv",
    "greenland_dynamic_discharge_fraction": "greenland_dynamic_discharge_fraction",
    "greenland_pdd_melt_factor": "greenland_pdd_melt_factor_gt_per_degree_day",
    "greenland_meltwater_retention_fraction": "greenland_meltwater_retention_fraction",
    "hydrological_north_fraction": "hydrological_freshwater_north_fraction",
    "amoc_reference": "amoc_reference_sv",
    "amoc_temperature_coupling": "amoc_temperature_density_coupling",
    "amoc_adjustment_years": "amoc_adjustment_years",
    "amoc_heat_transport": "amoc_heat_transport_pw_per_sv",
    "amoc_surface_heat_coupling": "amoc_surface_heat_coupling_fraction",
    "amoc_heat_response_damping": "amoc_heat_response_damping_wm2_k",
    "atlantic_gyre_heat_transport": "atlantic_gyre_heat_transport_pw",
    "amoc_density_exponent": "amoc_density_transport_exponent",
    "amoc_depth_exponent": "amoc_hydraulic_depth_exponent",
    "amoc_pycnocline_feedback_strength": "amoc_pycnocline_feedback_strength",
    "amoc_convection_density_scale_factor": "amoc_convection_density_scale_factor",
    "amoc_convection_minimum_fraction": "amoc_convection_minimum_fraction",
    "amoc_convective_mixing_reference": "amoc_convective_mixing_reference_sv",
    "amoc_convective_mixing_exponent": "amoc_convective_mixing_exponent",
    "amoc_convection_entrainment_feedback": "amoc_convection_entrainment_feedback",
    "amoc_convection_adjustment_years": "amoc_convection_adjustment_years",
    "amoc_convection_recovery_years": "amoc_convection_recovery_years",
    "amoc_eddy_depth_exponent": "amoc_eddy_depth_exponent",
    "amoc_pycnocline_depth": "amoc_initial_pycnocline_depth_m",
    "amoc_ekman_inflow": "amoc_ekman_inflow_sv",
    "amoc_upwelling": "amoc_upwelling_reference_sv",
    "amoc_eddy_outflow": "amoc_eddy_outflow_reference_sv",
    "amoc_north_gyre": "amoc_north_tropical_gyre_sv",
    "amoc_southern_gyre": "amoc_tropical_southern_gyre_sv",
    "amoc_southern_external_exchange": "amoc_southern_external_exchange_sv",
    "amoc_south_atlantic_external_exchange": "amoc_south_atlantic_external_exchange_sv",
    "initial_north_salinity": "initial_north_salinity_psu",
    "initial_tropical_salinity": "initial_tropical_salinity_psu",
    "initial_southern_salinity": "initial_southern_salinity_psu",
    "initial_fovs": "initial_fovs_sv",
    "initial_deep_salinity": "initial_deep_salinity_psu",
    "cryosphere_adjustment": "cryosphere_adjustment_years",
}

# Only physical/process parameters may be sampled. Experiment controls such as
# timestep, grid resolution, scenario, duration, forcing pathway, CO2 targets,
# switch years, and output cadence are intentionally excluded so one ensemble
# represents one experiment rather than a mixture of different experiments.
MONTE_CARLO_PHYSICAL_PARAMETERS = frozenset(
    {
        # Climate/radiative process parameters.
        "co2_doubling_erf_wm2",
        "relative_humidity",
        "representative_pressure_pa",
        "equatorial_emission_height_km",
        "polar_emission_height_km",
        "moist_lapse_rate_weight",
        "arctic_lapse_rate_feedback_wm2_k",
        "water_vapor_emission_height_km_per_lnq",
        "longwave_spectral_factor",
        "land_heat_capacity_wyr_m2_k",
        "ocean_mixed_layer_heat_capacity_wyr_m2_k",
        "deep_ocean_heat_capacity_wyr_m2_k",
        "ocean_heat_exchange_wm2_k",
        "land_ocean_exchange_wm2_k",
        "meridional_diffusion_wm2_k",
        "ocean_open_water_albedo",
        "sea_ice_albedo",
        "bare_land_albedo",
        "snow_albedo",
        "surface_shortwave_transmission",
        "sea_ice_transition_c",
        "sea_ice_transition_width_c",
        "snow_transition_c",
        "snow_transition_width_c",
        "cryosphere_adjustment_years",
        "arctic_module_start_latitude_deg",
        "arctic_reference_air_seasonal_amplitude_c",
        "arctic_moisture_transport_wm2_per_k",
        "arctic_dry_static_transport_wm2_k",
        "arctic_open_water_stable_exchange_wm2_k",
        "arctic_open_water_unstable_exchange_wm2_k",
        "arctic_open_water_exchange_transition_c",
        "arctic_transient_shortwave_scale",
        "arctic_interface_longwave_damping_wm2_k",
        "arctic_ice_nonsolar_heat_loss_wm2",
        "arctic_open_water_nonsolar_heat_loss_wm2",
        "arctic_reference_bare_ice_albedo",
        "arctic_basal_ocean_exchange_wm2_k",
        "arctic_open_water_ocean_exchange_wm2_k",
        "arctic_lateral_ocean_heat_transport_wm2_per_ice_fraction",
        "arctic_summer_lateral_ocean_heat_transport_wm2_per_ice_fraction",
        "arctic_forced_ocean_heat_convergence_wm2_per_k",
        "arctic_forced_ocean_heat_convergence_onset_warming_c",
        "arctic_forced_ocean_heat_convergence_saturation_scale_c",
        "arctic_forced_ocean_heat_convergence_ice_fraction_exponent",
        "arctic_phase_restoring_deficit_saturation_fraction",
        "arctic_phase_restoring_max_deficit_flux_wm2",
        "arctic_winter_lead_closure_fraction",
        "arctic_winter_lead_closure_onset_fraction",
        "arctic_winter_lead_closure_temperature_scale_c",
        "arctic_full_cover_equivalent_thickness_m",
        "arctic_new_ice_local_thickness_m",
        "arctic_ice_concentration_exponent",
        "arctic_ice_area_formation_temperature_scale_c",
        "arctic_ice_area_formation_volume_sensitivity",
        "arctic_ice_area_formation_support_floor",
        "arctic_ice_area_melt_thickness_m",
        "arctic_ice_area_lateral_melt_efficiency",
        "arctic_ice_area_thinning_melt_amplification",
        "arctic_ice_area_thick_pack_resistance_exponent",
        "arctic_ice_area_compaction_years",
        "arctic_ice_area_ridging_threshold",
        "arctic_ice_area_ridging_fraction_per_year",
        "arctic_ice_area_divergence_fraction_per_year",
        "arctic_ice_area_thin_pack_divergence_fraction_per_year",
        "arctic_ice_mechanical_max_local_thickness_m",
        "arctic_ice_export_onset_equivalent_thickness_m",
        "arctic_ice_export_timescale_years",
        "arctic_ice_export_anomaly_coupling_fraction",
        "arctic_winter_ice_export_anomaly_coupling_fraction",
        "arctic_ice_export_anomaly_darkness_exponent",
        "arctic_atlantic_reference_ocean_temperature_c",
        "arctic_non_atlantic_reference_ocean_temperature_c",
        "arctic_reference_ocean_heat_capacity_wyr_m2_k",
        "arctic_reference_ocean_restoring_wm2_k",
        "arctic_air_low_pass_years",
        "arctic_greenland_marine_influence",
        "arctic_winter_transport_enhancement",
        "arctic_winter_transport_temperature_scale_c",
        "arctic_ice_surface_exchange_wm2_k",
        "low_cloud_loss_fraction_per_k",
        "low_cloud_moisture_gain_fraction_per_lnq",
        "low_cloud_adjustment_years",
        "cloud_shortwave_reflectivity",
        "low_cloud_longwave_wm2_per_fraction",
        "high_cloud_tropical_fraction",
        "high_cloud_top_temperature_k",
        "high_cloud_temperature_coupling",
        # AMOC state, transport, and feedback parameters.
        "amoc_reference_sv",
        "amoc_adjustment_years",
        "thermal_expansion_per_k",
        "amoc_temperature_density_coupling",
        "haline_contraction_per_psu",
        "amoc_density_transport_exponent",
        "amoc_hydraulic_depth_exponent",
        "amoc_hydraulic_transport_max_sv",
        "amoc_pycnocline_feedback_strength",
        "amoc_eddy_depth_exponent",
        "amoc_convection_density_scale_factor",
        "amoc_convection_minimum_fraction",
        "amoc_convection_adjustment_years",
        "amoc_convection_recovery_years",
        "amoc_convective_mixing_reference_sv",
        "amoc_convective_mixing_exponent",
        "amoc_convection_entrainment_feedback",
        "amoc_reference_density_driver",
        "amoc_north_box_volume_m3",
        "amoc_tropical_box_volume_m3",
        "amoc_south_atlantic_upper_box_volume_m3",
        "amoc_southern_box_volume_m3",
        "amoc_deep_box_volume_m3",
        "amoc_external_box_volume_m3",
        "initial_north_salinity_psu",
        "initial_tropical_salinity_psu",
        "initial_southern_salinity_psu",
        "initial_deep_salinity_psu",
        "initial_external_salinity_psu",
        "initial_fovs_sv",
        "fovs_reference_salinity_psu",
        "amoc_southern_external_exchange_sv",
        "amoc_south_atlantic_external_exchange_sv",
        "amoc_initial_pycnocline_depth_m",
        "amoc_pycnocline_area_m2",
        "amoc_ekman_inflow_sv",
        "amoc_upwelling_reference_sv",
        "amoc_eddy_outflow_reference_sv",
        "amoc_north_tropical_gyre_sv",
        "amoc_tropical_southern_gyre_sv",
        "amoc_heat_transport_pw_per_sv",
        "atlantic_gyre_heat_transport_pw",
        "amoc_heat_response_damping_wm2_k",
        "amoc_surface_heat_coupling_fraction",
        # Freshwater feedback parameters, not experiment hosing controls.
        "hydrological_freshwater_sv_per_k",
        "hydrological_freshwater_north_fraction",
        "greenland_freshwater_sv_per_k",
        "greenland_freshwater_threshold_c",
        "greenland_freshwater_adjustment_years",
        "greenland_initial_ice_mass_gt",
        "greenland_depletion_exponent",
        "greenland_max_freshwater_sv",
        "greenland_dynamic_discharge_fraction",
        "greenland_reference_annual_temperature_c",
        "greenland_reference_seasonal_amplitude_c",
        "greenland_pdd_melt_factor_gt_per_degree_day",
        "greenland_baseline_precipitation_gt_per_year",
        "greenland_precipitation_fraction_per_k",
        "greenland_snow_rain_transition_c",
        "greenland_snow_rain_transition_width_c",
        "greenland_meltwater_retention_fraction",
        "greenland_retention_loss_fraction_per_k",
        # Explicit numeric parameters inside opt-in structural families.
        "amoc_southern_wind_sensitivity_per_k",
        "amoc_southern_upwelling_sensitivity_per_k",
        "amoc_southern_response_min_multiplier",
        "amoc_southern_response_max_multiplier",
        "amoc_indo_pacific_compensation_fraction",
        "amoc_indo_pacific_compensation_max_sv",
    }
)

MONTE_CARLO_EXPERIMENT_CONTROLS = frozenset(
    {
        "start_year",
        "duration_years",
        "dt_years",
        "record_every_years",
        "resolution_deg",
        "co2_reference_ppm",
        "co2_start_ppm",
        "co2_end_ppm",
        "co2_peak_ppm",
        "one_percent_cap_ppm",
        "co2_growth_rate_percent_per_year",
        "co2_growth_cap_ppm",
        "co2_hold_years",
        "co2_ramp_years",
        "peak_time_fraction",
        "additional_forcing_wm2",
        "ssp_switch_year",
        "ssp_transition_years",
        "freshwater_hosing_sv",
        "freshwater_start_fraction",
        "freshwater_ramp_years",
        "amoc_collapse_threshold_sv",
    }
)

# Built-in priors are deliberately broader than the observational likelihoods.
# This prevents the same evidence from being imposed once through the prior and
# again through posterior weighting. Marginal shapes follow parameter support:
# bounded fractions use beta distributions, positive scales use log-normal
# distributions, measured signed quantities use truncated normals, and poorly
# constrained emulator coefficients use weak uniform distributions.
@dataclass(frozen=True)
class PriorSpec:
    lower: float
    upper: float
    distribution: str
    mode: float | None = None
    concentration: float = 8.0
    source: str = ""
    rationale: str = ""
    point_mass_at_zero: float = 0.0


PHYSICAL_CLIMATE_PRIORS: dict[str, PriorSpec] = {
    "co2_doubling_erf_wm2": PriorSpec(3.0, 5.0, "uniform", None, source="radiative-transfer physics", rationale="Broad forcing prior; AR6 ERF enters only through the likelihood."),
    "longwave_spectral_factor": PriorSpec(0.80, 1.15, "truncated_normal", 0.98, source="longwave spectral response", rationale="Dimensionless correction around unity."),
    "relative_humidity": PriorSpec(0.60, 0.90, "beta", 0.78, 10.0, "tropospheric humidity", "Physically bounded fraction."),
    "moist_lapse_rate_weight": PriorSpec(0.10, 0.70, "beta", 0.30, 7.0, "moist-adiabatic response", "Bounded emulator mixing fraction."),
    "arctic_lapse_rate_feedback_wm2_k": PriorSpec(0.0, 1.8, "beta", 1.10, 6.0, "unresolved Arctic inversion and lapse-rate response", "Low-confidence tuning-informed local feedback is sampled explicitly rather than held fixed."),
    "water_vapor_emission_height_km_per_lnq": PriorSpec(0.40, 1.80, "lognormal", 1.00, source="water-vapour radiative response", rationale="Positive length scale."),
    "low_cloud_loss_fraction_per_k": PriorSpec(0.0002, 0.020, "loguniform", None, source="cloud-process uncertainty", rationale="Positive fractional sensitivity with weak prior information."),
    "low_cloud_moisture_gain_fraction_per_lnq": PriorSpec(0.0002, 0.035, "loguniform", None, source="cloud-process uncertainty", rationale="Positive fractional sensitivity with weak prior information."),
    "high_cloud_temperature_coupling": PriorSpec(0.02, 0.80, "uniform", None, "cloud-process uncertainty", "Bounded coupling coefficient."),
    "sea_ice_albedo": PriorSpec(0.30, 0.85, "beta", 0.54, 10.0, "surface optical properties", "Physically bounded albedo."),
    "snow_albedo": PriorSpec(0.35, 0.90, "beta", 0.60, 10.0, "surface optical properties", "Physically bounded albedo."),
    "sea_ice_transition_c": PriorSpec(-3.0, -0.5, "truncated_normal", -1.8, source="freezing-transition physics", rationale="Signed transition temperature."),
    "sea_ice_transition_width_c": PriorSpec(1.0, 8.0, "lognormal", 3.5, source="sub-grid sea-ice heterogeneity", rationale="Positive transition width."),
    "snow_transition_c": PriorSpec(-5.0, 2.0, "truncated_normal", -1.0, source="snow-cover climatology", rationale="Signed transition temperature."),
    "snow_transition_width_c": PriorSpec(1.0, 8.0, "lognormal", 3.5, source="sub-grid snow heterogeneity", rationale="Positive transition width."),
    "ocean_mixed_layer_heat_capacity_wyr_m2_k": PriorSpec(3.0, 20.0, "lognormal", 10.0, source="mixed-layer depth and seawater heat capacity", rationale="Positive thermal inertia."),
    "deep_ocean_heat_capacity_wyr_m2_k": PriorSpec(40.0, 300.0, "lognormal", 110.0, source="effective ventilated ocean volume", rationale="Positive thermal inertia."),
    "ocean_heat_exchange_wm2_k": PriorSpec(0.40, 2.20, "loguniform", None, source="ocean heat-uptake dynamics", rationale="Positive exchange coefficient."),
    "meridional_diffusion_wm2_k": PriorSpec(0.15, 1.20, "loguniform", None, source="atmosphere-ocean meridional transport", rationale="Positive effective diffusivity."),
    "arctic_module_start_latitude_deg": PriorSpec(50.0, 60.0, "truncated_normal", 52.0, source="reduced Arctic geometry", rationale="Samples the calibrated lower-latitude transition of the two-sector Arctic module."),
    "arctic_reference_air_seasonal_amplitude_c": PriorSpec(10.0, 18.0, "truncated_normal", 12.0, source="prescribed Arctic reference climatology", rationale="Samples the tuning-informed sinusoidal control-cycle amplitude explicitly."),
    "arctic_moisture_transport_wm2_per_k": PriorSpec(0.05, 1.0, "lognormal", 0.22, source="Arctic atmospheric energy convergence", rationale="Warm-season background moisture convergence; cold-season enhancement is diagnosed separately from polar darkness."),
    "arctic_winter_transport_enhancement": PriorSpec(0.0, 25.0, "truncated_normal", 10.0, source="cold-season Arctic energy transport", rationale="Physically constrained forcing-like transport response with explicit support for low values; joint darkness and cold-state gating prevents shoulder-season activation."),
    "arctic_winter_transport_temperature_scale_c": PriorSpec(10.0, 22.0, "truncated_normal", 15.0, source="seasonality of Arctic atmospheric energy transport", rationale="Controls how sharply the winter enhancement is suppressed in warm shoulder seasons."),
    "arctic_dry_static_transport_wm2_k": PriorSpec(0.5, 2.5, "lognormal", 1.55, source="meridional dry-static energy transport", rationale="Positive restoring transport."),
    "arctic_open_water_stable_exchange_wm2_k": PriorSpec(0.1, 2.0, "loguniform", None, source="stable Arctic boundary-layer exchange", rationale="Weak exchange when air is warmer than open water."),
    "arctic_open_water_unstable_exchange_wm2_k": PriorSpec(2.0, 10.0, "lognormal", 5.0, source="unstable Arctic boundary-layer exchange", rationale="Stronger exchange when water is warmer than air."),
    "arctic_open_water_exchange_transition_c": PriorSpec(0.1, 1.5, "loguniform", None, source="boundary-layer stability transition", rationale="Positive smooth transition width."),
    "arctic_transient_shortwave_scale": PriorSpec(0.50, 1.00, "truncated_normal", 1.00, source="cloud masking of sea-ice albedo anomalies", rationale="Bounded effective shortwave anomaly factor after introducing independent prognostic ice area."),
    "arctic_interface_longwave_damping_wm2_k": PriorSpec(1.5, 4.5, "truncated_normal", 2.2, source="net Arctic surface longwave response", rationale="Samples temperature-dependent net longwave cooling rather than holding it fixed."),
    "arctic_ice_surface_exchange_wm2_k": PriorSpec(3.0, 8.0, "truncated_normal", 5.0, source="Arctic ice-atmosphere sensible exchange", rationale="Samples the tuning-informed coupling between the prognostic air column and thermodynamic ice surface; the calibrated default is interior to the support."),
    "arctic_ice_nonsolar_heat_loss_wm2": PriorSpec(38.0, 51.0, "truncated_normal", 44.2, source="Arctic ice-surface control energy budget", rationale="Treats the fitted control-state turbulent and radiative loss as uncertain."),
    "arctic_ice_mechanical_max_local_thickness_m": PriorSpec(8.0, 20.0, "truncated_normal", 12.0, source="unresolved sea-ice deformation and floe dispersion", rationale="Bounds grid-cell mean thickness over the ice-covered fraction below implausible narrow-remnant states while conserving volume."),
    "arctic_open_water_nonsolar_heat_loss_wm2": PriorSpec(60.0, 80.0, "truncated_normal", 70.0, source="Arctic open-water control energy budget", rationale="Treats the fitted open-water non-solar loss as uncertain."),
    "arctic_reference_bare_ice_albedo": PriorSpec(0.54, 0.66, "truncated_normal", 0.602, source="Arctic bare-ice optical properties", rationale="Samples uncertainty in the fitted reference bare-ice albedo."),
    "arctic_basal_ocean_exchange_wm2_k": PriorSpec(6.0, 30.0, "lognormal", 10.0, source="under-ice ocean heat exchange", rationale="Positive basal exchange linking prognostic ocean temperature to ice-volume melt after the area-volume separation."),
    "arctic_open_water_ocean_exchange_wm2_k": PriorSpec(10.0, 45.0, "lognormal", 25.0, source="shallow Arctic ocean exchange", rationale="Conservative two-way exchange between open water and the bulk ocean."),
    "arctic_lateral_ocean_heat_transport_wm2_per_ice_fraction": PriorSpec(2.0, 40.0, "truncated_normal", 25.0, source="lateral Arctic Ocean heat convergence", rationale="Twenty percent of the prior is an explicit disabled structural branch; the remaining support samples positive conservative convergence.", point_mass_at_zero=0.20),
    "arctic_summer_lateral_ocean_heat_transport_wm2_per_ice_fraction": PriorSpec(0.0, 5.0, "uniform", 0.0, source="summer Arctic Ocean heat convergence", rationale="Allows weak summer phase-restoring heat transport while retaining a zero default."),
    "arctic_forced_ocean_heat_convergence_wm2_per_k": PriorSpec(0.0, 8.0, "truncated_normal", 4.0, source="warming-driven Arctic Ocean heat convergence", rationale="Samples conservative lower-latitude ocean heat import after onset; production uses bounded warming response and native ice-cover weighting."),
    "arctic_forced_ocean_heat_convergence_onset_warming_c": PriorSpec(0.25, 2.0, "truncated_normal", 1.0, source="warming threshold for enhanced Arctic Ocean heat convergence", rationale="Positive onset avoids changing the unforced periodic control while allowing uncertainty in when the transient convergence strengthens."),
    "arctic_forced_ocean_heat_convergence_saturation_scale_c": PriorSpec(0.15, 1.5, "lognormal", 0.50, source="finite Arctic Ocean heat-convergence response", rationale="Bounds the enhanced warming response instead of allowing unbounded linear growth."),
    "arctic_forced_ocean_heat_convergence_ice_fraction_exponent": PriorSpec(0.0, 1.0, "uniform", 0.5, source="under-ice geometry of enhanced Arctic Ocean heat convergence", rationale="Weights anomalous convergence by remaining native ice cover while retaining a zero-attenuation structural branch."),
    "arctic_phase_restoring_deficit_saturation_fraction": PriorSpec(0.05, 0.35, "truncated_normal", 0.14, source="depleted-pack phase-restoring saturation", rationale="Samples the transition scale for reverse-sign ocean restoring; the maximum reverse flux is independently bounded."),
    "arctic_phase_restoring_max_deficit_flux_wm2": PriorSpec(1.0, 4.0, "truncated_normal", 2.5, source="depleted-pack phase-restoring flux safety bound", rationale="Samples uncertainty in the maximum reverse cooling/regrowth flux independently of the saturation shape."),
    "arctic_winter_lead_closure_fraction": PriorSpec(0.0, 0.60, "beta", 0.10, 7.0, source="optional winter sea-ice mechanical redistribution", rationale="Includes the null structural branch and no longer tunes the default against the discontinuous raw March-area trend.", point_mass_at_zero=0.35),
    "arctic_full_cover_equivalent_thickness_m": PriorSpec(3.0, 4.5, "truncated_normal", 4.0, source="native sea-ice concentration-volume relation", rationale="Full-pack equivalent/local thickness scale with independent emergency local- and equivalent-thickness safeguards."),
    "arctic_new_ice_local_thickness_m": PriorSpec(0.05, 0.30, "truncated_normal", 0.25, source="nilas and young-ice thickness", rationale="Sets the physically thin local-thickness limit as equivalent volume approaches zero."),
    "arctic_ice_concentration_exponent": PriorSpec(0.25, 2.5, "truncated_normal", 0.50, source="native compact-pack concentration relation", rationale="Controls the calibrated compact-pack curve; the mapping remains monotonic and reaches full cover only at the declared full-cover thickness across the complete support."),
    "arctic_ice_area_formation_temperature_scale_c": PriorSpec(0.20, 1.20, "lognormal", 0.50, source="new-ice thermodynamic formation", rationale="Smooth freezing-temperature gate for lateral new-ice spreading over open water."),
    "arctic_ice_area_formation_volume_sensitivity": PriorSpec(0.0, 12.0, "truncated_normal", 4.0, source="seasonal ice-volume support for new area", rationale="Limits lateral winter recovery smoothly as the seasonal ice-volume reservoir declines."),
    "arctic_ice_area_formation_support_floor": PriorSpec(0.0, 0.75, "beta", 0.50, 4.0, source="bounded winter refreezing support", rationale="Prevents a depleted pack from mathematically eliminating winter new-ice formation while leaving the control orbit unchanged."),
    "arctic_ice_area_melt_thickness_m": PriorSpec(0.15, 1.20, "lognormal", 0.70, source="lateral versus vertical sea-ice melt", rationale="Thin local ice preferentially loses area while thick ice preferentially loses volume."),
    "arctic_ice_area_lateral_melt_efficiency": PriorSpec(0.20, 1.00, "truncated_normal", 0.62, source="thermodynamic lateral melt partition", rationale="Partitions conservative melt energy between area retreat and vertical thinning."),
    "arctic_ice_area_thinning_melt_amplification": PriorSpec(0.0, 10.0, "truncated_normal", 4.0, source="reference-relative pack vulnerability", rationale="Strengthens lateral retreat as the transient pack loses volume support relative to its periodic control."),
    "arctic_ice_area_thick_pack_resistance_exponent": PriorSpec(0.0, 8.0, "truncated_normal", 0.0, source="deprecated empirical thick-pack resistance", rationale="Disabled in the production default; explicit nonzero experiments require independent thickness/volume justification."),
    "arctic_ice_area_compaction_years": PriorSpec(0.05, 1.0, "lognormal", 0.207, source="compact-pack mechanical relaxation", rationale="Only removes unsupported excess area and cannot close leads or create latent heat."),
    "arctic_ice_area_ridging_threshold": PriorSpec(0.70, 0.95, "truncated_normal", 0.80, source="ridging onset in compact pack", rationale="Bounded concentration threshold for cold-season ridging and rafting."),
    "arctic_ice_area_ridging_fraction_per_year": PriorSpec(0.0, 0.50, "truncated_normal", 0.25, source="ridging and rafting", rationale="Fixed-volume reduction of compact-pack area that increases local thickness."),
    "arctic_ice_area_divergence_fraction_per_year": PriorSpec(0.0, 0.15, "uniform", 0.0, source="background lead opening and divergence", rationale="Optional background fixed-volume area reduction with an explicit zero default.", point_mass_at_zero=0.40),
    "arctic_ice_area_thin_pack_divergence_fraction_per_year": PriorSpec(0.0, 1.5, "truncated_normal", 0.80, source="reference-relative thin-pack deformation", rationale="Seasonally weighted deformation and lead opening activated only by transient loss of pack support."),
    "arctic_ice_export_onset_equivalent_thickness_m": PriorSpec(0.65, 1.05, "truncated_normal", 0.82, source="mechanical sea-ice export onset", rationale="Export activates continuously only after a finite compact-pack thickness."),
    "arctic_ice_export_timescale_years": PriorSpec(0.09, 0.24, "lognormal", 0.14, source="mechanical sea-ice export timescale", rationale="Positive continuous export timescale; replaces the former hard thickness ceiling."),
    "arctic_ice_export_anomaly_coupling_fraction": PriorSpec(0.0, 0.20, "beta", 0.02, 8.0, source="summer anomalous sea-ice export", rationale="Weak during fragmented summer pack."),
    "arctic_winter_ice_export_anomaly_coupling_fraction": PriorSpec(0.70, 1.00, "beta", 0.95, 8.0, source="winter anomalous sea-ice export", rationale="Strong compact-pack export feedback in polar night."),
    "arctic_ice_export_anomaly_darkness_exponent": PriorSpec(2.0, 7.0, "truncated_normal", 4.0, source="seasonality of anomalous sea-ice export", rationale="Concentrates the feedback in the compact winter pack."),
    "arctic_atlantic_reference_ocean_temperature_c": PriorSpec(-0.5, 1.5, "truncated_normal", 0.20, source="Atlantic-sector Arctic Ocean control climatology", rationale="Reference target is sampled independently of the transient exchange coefficient."),
    "arctic_non_atlantic_reference_ocean_temperature_c": PriorSpec(-1.5, 0.0, "truncated_normal", -0.80, source="central-Arctic Ocean control climatology", rationale="Reference target remains above seawater freezing and independent of coupling strength."),
    "arctic_reference_ocean_heat_capacity_wyr_m2_k": PriorSpec(2.0, 15.0, "lognormal", 6.0, source="effective Arctic shallow-ocean depth", rationale="Positive thermal inertia of the periodic reference-ocean state."),
    "arctic_reference_ocean_restoring_wm2_k": PriorSpec(5.0, 20.0, "lognormal", 12.0, source="Arctic ocean heat convergence", rationale="Positive restoring that closes the periodic reference-ocean budget."),
    "arctic_greenland_marine_influence": PriorSpec(0.0, 0.25, "beta", 0.10, 7.0, source="Greenland maritime temperature influence", rationale="Modest low-pass Arctic maritime contribution; the raw marine-air anomaly is never used as the dominant Greenland driver."),
    "arctic_air_low_pass_years": PriorSpec(0.05, 0.50, "loguniform", None, source="near-surface-air diagnostic memory", rationale="Short atmospheric memory without smearing winter anomalies into summer."),
}

PHYSICAL_AMOC_PRIORS: dict[str, PriorSpec] = {
    "amoc_heat_transport_pw_per_sv": PriorSpec(0.015, 0.080, "loguniform", None, source="temperature contrast times seawater heat capacity", rationale="Positive heat transported per unit overturning."),
    "amoc_surface_heat_coupling_fraction": PriorSpec(0.02, 0.80, "beta", 0.10, 5.0, "surface expression of overturning heat transport", "Bounded fraction; low values avoid excessive cold-blob restoration."),
    "amoc_heat_response_damping_wm2_k": PriorSpec(0.20, 5.0, "loguniform", None, source="regional radiative and turbulent damping", rationale="Positive damping rate."),
    "atlantic_gyre_heat_transport_pw": PriorSpec(0.10, 1.00, "loguniform", None, source="wind-driven Atlantic heat transport", rationale="Positive transport scale."),
    "hydrological_freshwater_sv_per_k": PriorSpec(0.002, 0.012, "loguniform", None, source="P-E, runoff and Arctic export response", rationale="Narrowed to avoid implicit hosing-like compensation."),
    "hydrological_freshwater_north_fraction": PriorSpec(0.25, 0.98, "beta", 0.70, 7.0, "freshwater spatial partition", "Bounded fraction."),
    "greenland_freshwater_sv_per_k": PriorSpec(0.002, 0.010, "loguniform", None, source="Greenland surface-mass-balance response", rationale="Independently constrained by historical mass loss and sea-level contribution."),
    "greenland_freshwater_adjustment_years": PriorSpec(5.0, 250.0, "lognormal", 45.0, source="ice-sheet and routing response time", rationale="Positive response timescale."),
    "greenland_depletion_exponent": PriorSpec(0.5, 2.0, "uniform", 1.0, source="finite-reservoir geometry", rationale="Controls how discharge declines as ice mass is depleted."),
    "greenland_max_freshwater_sv": PriorSpec(0.005, 0.040, "lognormal", 0.025, source="bounded Greenland discharge", rationale="Caps combined reduced-SMB runoff and slow dynamic discharge."),
    "greenland_dynamic_discharge_fraction": PriorSpec(0.0, 0.30, "beta", 0.10, 6.0, "partition of the public Greenland coefficient", "Keeps slow dynamic discharge modest and separates it from the explicit surface-mass-balance branch."),
    "greenland_pdd_melt_factor_gt_per_degree_day": PriorSpec(0.20, 0.70, "truncated_normal", 0.38, source="reduced positive-degree-day melt", rationale="Controls the explicit surface-melt anomaly while avoiding routine overlap with the separately prognostic dynamic-discharge component."),
    "greenland_meltwater_retention_fraction": PriorSpec(0.15, 0.55, "beta", 0.35, 6.0, "firn and refreezing retention", "Bounded fraction of meltwater retained before runoff."),
    "greenland_retention_loss_fraction_per_k": PriorSpec(0.01, 0.08, "uniform", None, source="warming-dependent firn retention", rationale="Allows retention to decline gradually with warming."),
    "amoc_temperature_density_coupling": PriorSpec(0.40, 1.00, "beta", 0.95, 10.0, "thermal contribution to density contrast", "Retains support for reduced coupling while concentrating mass near the restored full-coupling v2.29.6 default; freshwater coefficients remain fixed."),
    "amoc_adjustment_years": PriorSpec(1.0, 30.0, "lognormal", 7.0, source="large-scale overturning adjustment", rationale="Positive response timescale."),
    "amoc_initial_pycnocline_depth_m": PriorSpec(300.0, 1200.0, "lognormal", 700.0, source="Atlantic thermocline depth", rationale="Positive depth scale."),
    "amoc_density_transport_exponent": PriorSpec(0.8, 2.5, "beta", 1.5, 6.0, source="hydraulic scaling", rationale="Jointly calibrated density-response exponent."),
    "amoc_hydraulic_depth_exponent": PriorSpec(0.2, 2.0, "uniform", None, source="hydraulic scaling", rationale="Positive depth exponent."),
    "amoc_hydraulic_transport_max_sv": PriorSpec(19.6, 24.0, "truncated_normal", 20.0, source="extreme-regime hydraulic closure", rationale="Samples uncertainty in the positive AMOC saturation while remaining above the built-in reference prior support."),
    "amoc_pycnocline_feedback_strength": PriorSpec(0.0, 0.50, "uniform", None, "pycnocline-overturning feedback", "Bounded feedback fraction; strong cancellation is disfavoured by stability tests."),
    "amoc_convection_density_scale_factor": PriorSpec(1.2, 6.0, "lognormal", 4.0, source="local density normalization", rationale="v2.28 validated density normalization; the support contains the public default and allows structural uncertainty."),
    "amoc_convection_minimum_fraction": PriorSpec(0.0, 0.30, "beta", 0.02, 8.0, "residual mixing under weak convection", "Near-zero convection is permitted while background ocean mixing remains elsewhere in the model."),
    "amoc_convective_mixing_reference_sv": PriorSpec(1.0, 12.0, "lognormal", 5.0, source="northern convective entrainment", rationale="Positive vertical salt-exchange scale; strong convection replenishes northern salinity."),
    "amoc_convective_mixing_exponent": PriorSpec(1.0, 4.0, "uniform", None, source="nonlinear convective entrainment", rationale="Controls how rapidly vertical salt exchange disappears as convection weakens."),
    "amoc_convection_entrainment_feedback": PriorSpec(0.0, 0.12, "beta", 0.0, 10.0, "optional density-memory feedback", "Default zero avoids double-counting prognostic convection-dependent salt mixing."),
    "amoc_convection_adjustment_years": PriorSpec(2.0, 80.0, "lognormal", 20.0, source="convection adjustment", rationale="Positive response timescale."),
    "amoc_convection_recovery_years": PriorSpec(10.0, 300.0, "lognormal", 80.0, source="salinity and convection recovery", rationale="Positive response timescale; support includes fast and slow recovery regimes."),
    "amoc_reference_density_driver": PriorSpec(4.0e-4, 1.5e-3, "lognormal", 7.5e-4, source="absolute control-state density margin", rationale="Contains the validated control density driver while rejecting physically fragile initial hydrography through the joint constraint."),
    "amoc_eddy_depth_exponent": PriorSpec(0.5, 4.0, "uniform", None, source="Southern Ocean eddy compensation", rationale="Positive response exponent."),
    "amoc_ekman_inflow_sv": PriorSpec(10.0, 40.0, "lognormal", 25.0, source="Southern Ocean wind-driven inflow", rationale="Positive volume transport."),
    "amoc_upwelling_reference_sv": PriorSpec(1.0, 12.0, "lognormal", 5.0, source="low-latitude diapycnal upwelling", rationale="Positive volume transport."),
    "amoc_eddy_outflow_reference_sv": PriorSpec(4.0, 25.0, "lognormal", 13.0, source="Southern Ocean eddy outflow", rationale="Positive volume transport."),
    "amoc_north_tropical_gyre_sv": PriorSpec(1.0, 12.0, "lognormal", 5.0, source="subtropical gyre salt exchange", rationale="Effective diffusive exchange; posterior response constraints limit excessive damping of salt-advection feedback."),
    "amoc_tropical_southern_gyre_sv": PriorSpec(3.0, 22.0, "lognormal", 10.0, source="South Atlantic gyre salt exchange", rationale="Effective diffusive exchange; posterior response constraints limit excessive damping of salt-advection feedback."),
    "initial_fovs_sv": PriorSpec(-0.60, 0.30, "uniform", None, source="physically possible signed freshwater transport", rationale="Broad signed prior; observational estimate enters only as likelihood."),
    "initial_southern_salinity_psu": PriorSpec(32.70, 33.30, "truncated_normal", 33.00, source="Southern Ocean high-latitude source-water salinity", rationale="Centered on the current interhemispheric control hydrography and constrained jointly by the absolute AMOC density margin."),
    "initial_north_salinity_psu": PriorSpec(34.85, 35.45, "truncated_normal", 35.15, source="North Atlantic source-water salinity", rationale="Hydrographic prior constrained jointly by the absolute AMOC density margin."),
}

SCIENCE_PRIOR_SPECS: dict[str, PriorSpec] = {
    **PHYSICAL_CLIMATE_PRIORS,
    **PHYSICAL_AMOC_PRIORS,
}
# Compatibility dictionaries retained for callers that only need bounds/modes.
AR6_CLIMATE_PRIOR_RANGES: dict[str, tuple[float, float]] = {
    key: (spec.lower, spec.upper) for key, spec in PHYSICAL_CLIMATE_PRIORS.items()
}
AR6_AMOC_PRIOR_RANGES: dict[str, tuple[float, float]] = {
    key: (spec.lower, spec.upper) for key, spec in PHYSICAL_AMOC_PRIORS.items()
}
SCIENCE_PRIOR_MODES: dict[str, float] = {
    key: float(spec.mode) for key, spec in SCIENCE_PRIOR_SPECS.items() if spec.mode is not None
}

# The control-state overturning strength is an initial-condition/calibration
# anchor, not a process uncertainty. Sampling it from the former broad 5-19.5
# Sv support shifted an otherwise 17 Sv default ensemble to about 14 Sv at the
# first output year. Built-in science-prior ensembles now keep this anchor at
# the configured base value. Users can still sample it deliberately with an
# explicit --mc-range when built-in science priors are disabled.
FIXED_SCIENCE_PRIOR_PARAMETERS: dict[str, str] = {
    "amoc_reference_sv": (
        "Control-state AMOC anchor fixed at the configured base value; use an "
        "explicit custom range to study uncertain initial overturning strength."
    ),
    "arctic_ice_area_thick_pack_resistance_exponent": (
        "Deprecated empirical closure fixed at the production default of zero. "
        "Re-enable only in an explicit experiment constrained by independent "
        "sea-ice thickness/volume observations."
    ),
}

# Primary time-series outputs. Values are stored for every member and plotted
# with all curves plus weighted percentile bands.
TIME_SERIES_METRICS: dict[str, tuple[str, str, bool]] = {
    "global_surface_warming_c": (
        "Global surface-temperature anomaly",
        "Temperature anomaly (degC)",
        False,
    ),
    "land_warming_c": ("Land temperature anomaly", "Temperature anomaly (degC)", False),
    "ocean_warming_c": ("Ocean temperature anomaly", "Temperature anomaly (degC)", False),
    "deep_ocean_warming_c": (
        "Deep-ocean temperature anomaly",
        "Temperature anomaly (degC)",
        False,
    ),
    "arctic_warming_c": ("Arctic temperature anomaly", "Temperature anomaly (degC)", False),
    "antarctic_warming_c": (
        "Antarctic temperature anomaly",
        "Temperature anomaly (degC)",
        False,
    ),
    "north_atlantic_warming_c": (
        "North Atlantic temperature anomaly",
        "Temperature anomaly (degC)",
        False,
    ),
    "sea_ice_area_fraction": (
        "Global sea-ice area fraction",
        "Area fraction",
        False,
    ),
    "snow_area_fraction": (
        "Global snow-covered land fraction",
        "Area fraction",
        False,
    ),
    "amoc_sv": ("AMOC transport", "AMOC (Sv)", True),
    "fovs_sv": ("Overturning freshwater transport (FovS)", "FovS (Sv)", True),
    "amoc_heat_transport_pw": (
        "AMOC-associated Atlantic heat transport",
        "Heat transport (PW)",
        True,
    ),
    "total_anomalous_freshwater_sv": (
        "North Atlantic anomalous freshwater forcing",
        "Freshwater forcing (Sv)",
        True,
    ),
    "greenland_freshwater_sv": (
        "Greenland freshwater discharge",
        "Freshwater forcing (Sv)",
        True,
    ),
    "greenland_remaining_fraction": (
        "Remaining Greenland ice fraction",
        "Fraction of initial reservoir",
        False,
    ),
    "greenland_cumulative_sea_level_mm": (
        "Cumulative Greenland sea-level equivalent",
        "Sea-level equivalent (mm)",
        False,
    ),
    "north_minus_southern_salinity_psu": (
        "North-minus-Southern Atlantic salinity contrast",
        "Salinity contrast (PSU)",
        True,
    ),
    "south_atlantic_upper_salinity_psu": (
        "South Atlantic upper-limb salinity at 34.5 S",
        "Salinity (PSU)",
        True,
    ),
    "south_atlantic_upper_minus_deep_salinity_psu": (
        "South Atlantic upper-minus-deep salinity contrast",
        "Salinity contrast (PSU)",
        True,
    ),
    "pycnocline_depth_m": ("Atlantic pycnocline depth", "Depth (m)", False),
    "amoc_northern_stratification_anomaly_c": (
        "Northern Atlantic upper-ocean stratification anomaly",
        "Surface-minus-deep anomaly (degC)",
        True,
    ),
    "amoc_temperature_density_term": (
        "AMOC thermal density contribution",
        "Density-driver term",
        True,
    ),
    "amoc_salinity_density_term": (
        "AMOC salinity density contribution",
        "Density-driver term",
        True,
    ),
    "amoc_density_driver_ratio": (
        "AMOC density driver relative to control",
        "Control ratio",
        True,
    ),
    "amoc_convection_efficiency": (
        "North Atlantic deep-convection efficiency",
        "Fraction of control",
        False,
    ),
    "amoc_convection_target": (
        "Deep-convection equilibrium target",
        "Fraction of control",
        False,
    ),
    "amoc_convection_transport_multiplier": (
        "Deep-convection AMOC multiplier",
        "Transport multiplier",
        False,
    ),
    "amoc_pycnocline_transport_multiplier": (
        "Limited pycnocline AMOC multiplier",
        "Transport multiplier",
        False,
    ),
    "toa_imbalance_wm2": (
        "Top-of-atmosphere energy imbalance",
        "Energy imbalance (W/m2)",
        True,
    ),
}

# Only these three primary line figures stay beside the raw output files.
# Every other PNG is written to the diagnostics subfolder.
MAIN_FIGURE_METRICS = {
    "global_surface_warming_c",
    "amoc_sv",
    "fovs_sv",
}

# Important derived figures that belong beside the primary outputs.
MAIN_DERIVED_FIGURE_METRICS = {
    "amoc_decline_percent",
}

DERIVED_METRICS: dict[str, tuple[str, str, str, str]] = {
    # name: source, operation, title, ylabel
    "amoc_decline_percent": (
        "amoc_sv",
        "signed_percent_change_from_baseline",
        "AMOC weakening from initial baseline",
        "AMOC change from initial baseline (%)",
    ),
    "fovs_change_sv": (
        "fovs_sv",
        "difference_from_baseline",
        "FovS change from initial baseline",
        "FovS change (Sv)",
    ),
    "amoc_heat_transport_decline_percent": (
        "amoc_heat_transport_pw",
        "decline_percent_from_baseline",
        "Atlantic heat-transport decline from initial baseline",
        "Heat-transport decline (%)",
    ),
    "salinity_contrast_change_psu": (
        "north_minus_southern_salinity_psu",
        "difference_from_baseline",
        "Atlantic salinity-contrast change",
        "Salinity-contrast change (PSU)",
    ),
    "south_atlantic_limb_contrast_change_psu": (
        "south_atlantic_upper_minus_deep_salinity_psu",
        "difference_from_baseline",
        "South Atlantic upper-minus-deep salinity change",
        "Salinity-contrast change (PSU)",
    ),
}


@dataclass(frozen=True)
class ConstraintTarget:
    key: str
    label: str
    center: float
    lower: float
    upper: float
    probability: float = 0.90
    strength: float = 1.0
    source: str = ""
    role: str = "calibration"


AR6_TARGETS: tuple[ConstraintTarget, ...] = (
    ConstraintTarget(
        "co2_doubling_erf_wm2",
        "2xCO2 effective radiative forcing",
        3.93,
        3.55,
        4.32,
        0.90,
        1.0,
        "IPCC AR6 WGI Chapter 7",
    ),
    ConstraintTarget(
        "feedback_planck_wm2_k",
        "Planck response",
        -3.22,
        -3.40,
        -3.00,
        0.90,
        0.75,
        "IPCC AR6 WGI Chapter 7",
    ),
    ConstraintTarget(
        "feedback_wv_lr_wm2_k",
        "Water-vapour plus lapse-rate feedback",
        1.30,
        1.10,
        1.50,
        0.90,
        0.75,
        "IPCC AR6 WGI Chapter 7",
    ),
    ConstraintTarget(
        "feedback_surface_albedo_wm2_k",
        "Surface-albedo feedback",
        0.35,
        0.10,
        0.60,
        0.90,
        0.50,
        "IPCC AR6 WGI Chapter 7",
    ),
    ConstraintTarget(
        "feedback_cloud_wm2_k",
        "Net cloud feedback",
        0.42,
        -0.10,
        0.94,
        0.90,
        0.60,
        "IPCC AR6 WGI Chapter 7",
    ),
    ConstraintTarget(
        "equilibrium_ecs_c",
        "Equilibrium climate sensitivity",
        3.0,
        2.0,
        5.0,
        0.90,
        1.0,
        "IPCC AR6 WGI Chapter 7",
    ),
    ConstraintTarget(
        "tcr_c",
        "Transient climate response",
        1.8,
        1.2,
        2.4,
        0.90,
        1.0,
        "IPCC AR6 WGI Chapter 7",
    ),
    ConstraintTarget(
        "historical_warming_2011_2020_c",
        "Observed 2011-2020 warming relative to 1850-1900",
        1.09,
        0.95,
        1.20,
        0.90,
        1.0,
        "IPCC AR6 WGI SPM",
    ),
    ConstraintTarget(
        "historical_eei_2006_2018_wm2",
        "Earth energy imbalance, 2006-2018",
        0.79,
        0.52,
        1.06,
        0.90,
        0.70,
        "IPCC AR6 WGI Chapter 7",
    ),
    ConstraintTarget(
        "historical_ohue_1970_2019_wm2_k",
        "Historical ocean heat-uptake efficiency",
        0.58,
        0.42,
        0.74,
        0.95,
        0.50,
        "Observation-based OHUE assessment",
    ),
)

AMOC_TARGETS: tuple[ConstraintTarget, ...] = (
    ConstraintTarget(
        "historical_amoc_2004_2023_sv",
        "Present-day AMOC strength",
        16.9,
        14.0,
        19.0,
        0.90,
        0.35,
        "RAPID 26.5N",
    ),
    ConstraintTarget(
        "historical_mht_2004_2023_pw",
        "Total Atlantic heat transport at 26.5N",
        1.20,
        0.90,
        1.50,
        0.90,
        0.35,
        "RAPID heat transport",
    ),
    ConstraintTarget(
        "historical_fovs_2004_2023_sv",
        "South Atlantic overturning freshwater transport",
        -0.15,
        -0.33,
        0.03,
        0.95,
        0.18,
        "Observation-based FovS estimate",
    ),
    ConstraintTarget(
        "ssp585_amoc_decline_2100_percent",
        "SSP5-8.5 AMOC decline by 2100",
        30.0,
        15.0,
        45.0,
        0.90,
        0.45,
        "CMIP6 response range and observationally constrained projections",
    ),
    ConstraintTarget(
        "hosing_0p1_amoc_decline_40yr_percent",
        "AMOC decline after 40 years of 0.1 Sv hosing",
        25.0,
        10.0,
        40.0,
        0.90,
        0.30,
        "Coupled-model freshwater-hosing experiments",
    ),
)

# Diagnostics within a group are physically or mathematically correlated.
# Their log likelihoods are averaged before groups are combined, preventing
# feedback components, net feedback, ECS/TCR, and historical response metrics
# from being counted as if they were fully independent observations.
CONSTRAINT_GROUPS: dict[str, str] = {
    "co2_doubling_erf_wm2": "forcing",
    "feedback_planck_wm2_k": "feedback_decomposition",
    "feedback_wv_lr_wm2_k": "feedback_decomposition",
    "feedback_surface_albedo_wm2_k": "feedback_decomposition",
    "feedback_cloud_wm2_k": "feedback_decomposition",
    "feedback_net_wm2_k": "feedback_decomposition",
    "equilibrium_ecs_c": "sensitivity",
    "tcr_c": "sensitivity",
    "historical_warming_2011_2020_c": "historical_climate",
    "historical_eei_2006_2018_wm2": "historical_climate",
    "historical_ohue_1970_2019_wm2_k": "historical_climate",
    "historical_amoc_2004_2023_sv": "amoc_state",
    "historical_mht_2004_2023_pw": "amoc_state",
    "historical_fovs_2004_2023_sv": "amoc_state",
    "ssp585_amoc_decline_2100_percent": "amoc_response",
    "hosing_0p1_amoc_decline_40yr_percent": "amoc_response",
}

# Correlations are applied simultaneously through one Gaussian-copula
# correlation matrix. This avoids the order dependence of sequential pairwise
# transforms. Only relationships with a clear physical basis are included.
PRIOR_CORRELATIONS: tuple[tuple[str, str, float], ...] = (
    ("water_vapor_emission_height_km_per_lnq", "moist_lapse_rate_weight", 0.55),
    ("ocean_heat_exchange_wm2_k", "deep_ocean_heat_capacity_wyr_m2_k", 0.30),
    ("amoc_reference_sv", "amoc_initial_pycnocline_depth_m", 0.45),
    ("amoc_ekman_inflow_sv", "amoc_eddy_outflow_reference_sv", 0.55),
    ("amoc_convection_adjustment_years", "amoc_convection_recovery_years", 0.35),
)

CONSTRAINT_GROUP_WEIGHTS: dict[str, float] = {
    "forcing": 0.50,
    "feedback_decomposition": 0.90,
    "sensitivity": 0.75,
    "historical_climate": 1.00,
    "amoc_state": 0.50,
    "amoc_response": 1.00,
}

# These diagnostics are deliberately excluded from posterior weighting. They
# are intended for held-out and structural validation scripts so calibration
# targets are not presented as independent validation evidence.
HELD_OUT_VALIDATION_DIAGNOSTICS: tuple[str, ...] = (
    "ssp245_amoc_decline_2100_percent",
    "hosing_0p2_amoc_decline_40yr_percent",
    "hosing_0p1_recovery_100yr_percent",
    "cross_resolution_control_consistency",
    "amoc_structural_family_spread",
)


def science_default_ranges(mode: str) -> dict[str, tuple[float, float]]:
    """Return broad process-prior bounds with control anchors held fixed.

    Sampled process bounds are intentionally wider than observational
    likelihoods so present-day evidence is not counted in both the prior and
    posterior. Initial-condition/calibration anchors listed in
    ``FIXED_SCIENCE_PRIOR_PARAMETERS`` retain the configured base value.
    """
    normalized = normalize_constraint_mode(mode)
    ranges = dict(AR6_CLIMATE_PRIOR_RANGES)
    if normalized in {"none", "ar6_amoc"}:
        ranges.update(AR6_AMOC_PRIOR_RANGES)
    for name in FIXED_SCIENCE_PRIOR_PARAMETERS:
        ranges.pop(name, None)
    return ranges


def _resolve_parameter_name(name: str, base_config: ModelConfig) -> str:
    cleaned = name.strip().replace("-", "_")
    resolved = PARAMETER_ALIASES.get(cleaned, cleaned)
    if resolved not in base_config.__dataclass_fields__:
        valid = sorted(
            alias
            for alias, target in PARAMETER_ALIASES.items()
            if target in MONTE_CARLO_PHYSICAL_PARAMETERS
        )
        valid.extend(sorted(MONTE_CARLO_PHYSICAL_PARAMETERS))
        valid = sorted(set(valid))
        raise ValueError(
            f"Unknown Monte Carlo parameter {name!r}. Valid physical parameter "
            "examples include: "
            + ", ".join(valid[:30])
            + (" ..." if len(valid) > 30 else "")
        )
    if resolved not in MONTE_CARLO_PHYSICAL_PARAMETERS:
        if resolved in MONTE_CARLO_EXPERIMENT_CONTROLS:
            raise ValueError(
                f"Monte Carlo parameter {resolved!r} is an experiment control, "
                "not a physical/process parameter. Keep it fixed for the ensemble."
            )
        raise ValueError(
            f"Monte Carlo parameter {resolved!r} is not on the explicit physical "
            "parameter whitelist. Add it deliberately to "
            "MONTE_CARLO_PHYSICAL_PARAMETERS before sampling it."
        )
    current = getattr(base_config, resolved)
    if isinstance(current, bool) or not isinstance(current, (int, float)):
        raise ValueError(
            f"Monte Carlo parameter {resolved!r} is not a numeric physical setting."
        )
    return resolved


def parse_ranges(
    raw_ranges: Iterable[list[str]] | None,
    base_config: ModelConfig,
    constraint_mode: str,
    use_science_priors: bool,
) -> dict[str, tuple[float, float]]:
    ranges: dict[str, tuple[float, float]] = {}
    for item in raw_ranges or []:
        if len(item) != 3:
            raise ValueError("Each --mc-range requires PARAMETER MIN MAX")
        raw_name, raw_minimum, raw_maximum = item
        name = _resolve_parameter_name(raw_name, base_config)
        try:
            minimum = float(raw_minimum)
            maximum = float(raw_maximum)
        except ValueError as exc:
            raise ValueError(
                f"Monte Carlo range for {raw_name!r} must use numeric bounds."
            ) from exc
        if not math.isfinite(minimum) or not math.isfinite(maximum):
            raise ValueError(f"Range for {raw_name!r} must be finite.")
        if minimum > maximum:
            raise ValueError(
                f"Range minimum exceeds maximum for {raw_name!r}: "
                f"{minimum} > {maximum}."
            )
        ranges[name] = (minimum, maximum)
    if ranges and use_science_priors:
        raise ValueError(
            "Do not combine --mc-use-science-priors with explicit --mc-range "
            "arguments. Choose the built-in prior or your own min/max ranges."
        )
    if use_science_priors:
        ranges = science_default_ranges(constraint_mode)
    if not ranges:
        raise ValueError(
            "Select at least one --mc-range PARAMETER MIN MAX, or explicitly "
            "enable --mc-use-science-priors."
        )
    return ranges


def _unit_design(runs: int, dimensions: int, seed: int, design: str) -> np.ndarray:
    if design == "random":
        return np.random.default_rng(seed).random((runs, dimensions))
    if design == "latin_hypercube":
        return qmc.LatinHypercube(d=dimensions, scramble=True, seed=seed).random(runs)
    if design == "sobol":
        sampler = qmc.Sobol(d=dimensions, scramble=True, seed=seed)
        power = int(math.ceil(math.log2(runs)))
        return sampler.random_base2(power)[:runs]
    raise ValueError(f"Unsupported sampling design: {design}")


def _apply_gaussian_copula_correlations(
    unit: np.ndarray,
    parameter_names: Sequence[str],
    enabled: bool,
) -> np.ndarray:
    if not enabled or unit.shape[1] < 2:
        return unit
    clipped = np.clip(unit, 1.0e-10, 1.0 - 1.0e-10)
    z = norm.ppf(clipped)
    index = {name: idx for idx, name in enumerate(parameter_names)}
    correlation = np.eye(len(parameter_names), dtype=float)
    for first, second, rho in PRIOR_CORRELATIONS:
        if first not in index or second not in index:
            continue
        i = index[first]
        j = index[second]
        correlation[i, j] = correlation[j, i] = float(rho)

    # Numerical projection to a positive-semidefinite correlation matrix.
    eigenvalues, eigenvectors = np.linalg.eigh(correlation)
    eigenvalues = np.clip(eigenvalues, 1.0e-8, None)
    correlation = eigenvectors @ np.diag(eigenvalues) @ eigenvectors.T
    scale = np.sqrt(np.diag(correlation))
    correlation = correlation / np.outer(scale, scale)
    cholesky = np.linalg.cholesky(correlation + np.eye(len(parameter_names)) * 1.0e-12)
    correlated_z = z @ cholesky.T
    return np.clip(norm.cdf(correlated_z), 1.0e-10, 1.0 - 1.0e-10)


def _inverse_marginal(
    u: float,
    minimum: float,
    maximum: float,
    base_value: float,
    distribution: str,
) -> float:
    if minimum == maximum:
        return minimum
    if distribution == "uniform":
        return float(minimum + u * (maximum - minimum))
    if distribution == "loguniform":
        if minimum <= 0.0 or maximum <= 0.0:
            raise ValueError("Log-uniform sampling requires positive bounds.")
        return float(math.exp(math.log(minimum) + u * (math.log(maximum) - math.log(minimum))))
    if distribution == "triangular":
        mode = float(np.clip(base_value, minimum, maximum))
        span = maximum - minimum
        c = (mode - minimum) / span
        if c <= 0.0:
            return float(maximum - math.sqrt((1.0 - u) * span * span))
        if c >= 1.0:
            return float(minimum + math.sqrt(u * span * span))
        if u < c:
            return float(minimum + math.sqrt(u * span * (mode - minimum)))
        return float(maximum - math.sqrt((1.0 - u) * span * (maximum - mode)))
    raise ValueError(f"Unsupported sampling distribution: {distribution}")



def _inverse_physical_prior(u: float, spec: PriorSpec) -> float:
    u = float(np.clip(u, 1.0e-10, 1.0 - 1.0e-10))
    point_mass = float(spec.point_mass_at_zero)
    if not 0.0 <= point_mass < 1.0:
        raise ValueError("point_mass_at_zero must be in [0, 1)")
    if point_mass > 0.0:
        if u <= point_mass:
            return 0.0
        u = (u - point_mass) / (1.0 - point_mass)
        u = float(np.clip(u, 1.0e-10, 1.0 - 1.0e-10))
    lower, upper = float(spec.lower), float(spec.upper)
    if lower == upper:
        return lower
    mode = float(spec.mode if spec.mode is not None else 0.5 * (lower + upper))
    if spec.distribution == "uniform":
        return lower + u * (upper - lower)
    if spec.distribution == "truncated_normal":
        sigma = max((upper - lower) / (2.0 * 1.6448536269514722), 1.0e-12)
        a = (lower - mode) / sigma
        b = (upper - mode) / sigma
        return float(truncnorm.ppf(u, a, b, loc=mode, scale=sigma))
    if spec.distribution == "loguniform":
        if lower <= 0.0 or upper <= 0.0:
            raise ValueError("Log-uniform physical priors require positive support.")
        return float(math.exp(math.log(lower) + u * (math.log(upper) - math.log(lower))))
    if spec.distribution == "lognormal":
        if lower <= 0.0 or upper <= 0.0 or mode <= 0.0:
            raise ValueError("Log-normal physical priors require positive support and mode.")
        sigma_log = max((math.log(upper) - math.log(lower)) / (2.0 * 1.6448536269514722), 0.05)
        distribution = lognorm(s=sigma_log, scale=mode)
        cdf_lower = float(distribution.cdf(lower))
        cdf_upper = float(distribution.cdf(upper))
        return float(distribution.ppf(cdf_lower + u * (cdf_upper - cdf_lower)))
    if spec.distribution == "beta":
        position = float(np.clip((mode - lower) / (upper - lower), 1.0e-4, 1.0 - 1.0e-4))
        concentration = max(float(spec.concentration), 0.1)
        alpha = 1.0 + concentration * position
        beta_value = 1.0 + concentration * (1.0 - position)
        fraction = float(beta_distribution.ppf(u, alpha, beta_value))
        return lower + fraction * (upper - lower)
    raise ValueError(f"Unsupported physical-prior distribution: {spec.distribution}")


def _joint_prior_state_is_physical(sampled: dict[str, float], base_config: ModelConfig) -> bool:
    """Screen the exact sampled configuration used by model workers."""

    try:
        config = replace(base_config, **sampled)
        config.validate()
        diagnostics = initial_amoc_density_diagnostics(config)
    except (TypeError, ValueError, ZeroDivisionError, OverflowError):
        return False

    reference_amoc = float(config.amoc_reference_sv)
    deep_salinity = float(config.initial_north_salinity_psu)
    south_upper = float(diagnostics["south_atlantic_upper_salinity_psu"])
    if reference_amoc <= 0.0:
        return False
    if not 33.0 <= south_upper <= 36.5:
        return False
    if abs(south_upper - deep_salinity) > 1.0:
        return False
    southern = float(config.initial_southern_salinity_psu)
    # The current interhemispheric control hydrography has a 2.15 PSU
    # north/deep-to-Southern-Ocean contrast (35.15 versus 33.00 PSU).
    # Keep a finite plausibility screen without rejecting the control state
    # around which the built-in hydrographic prior is defined.
    if abs(deep_salinity - southern) > 2.5:
        return False
    if diagnostics["density_driver"] <= 0.0:
        return False
    if config.amoc_enforce_initial_density_constraint and not (
        config.amoc_minimum_initial_density_ratio
        <= diagnostics["density_ratio"]
        <= config.amoc_maximum_initial_density_ratio
    ):
        return False
    return True

def generate_samples(
    base_config: ModelConfig,
    ranges: dict[str, tuple[float, float]],
    runs: int,
    seed: int,
    distribution: str,
    design: str,
    correlated_priors: bool,
    science_modes: bool = False,
) -> list[dict[str, float]]:
    if runs < 2:
        raise ValueError("Monte Carlo mode requires at least two runs.")
    names = list(ranges)
    unit = _unit_design(runs, len(names), seed, design)
    unit = _apply_gaussian_copula_correlations(unit, names, correlated_priors)
    samples: list[dict[str, float]] = []
    fallback_rng = np.random.default_rng(seed + 9173)
    for member in range(runs):
        sampled = {
            name: (
                _inverse_physical_prior(float(unit[member, column]), SCIENCE_PRIOR_SPECS[name])
                if science_modes and name in SCIENCE_PRIOR_SPECS
                else _inverse_marginal(
                    float(unit[member, column]),
                    ranges[name][0],
                    ranges[name][1],
                    float(getattr(base_config, name)),
                    distribution,
                )
            )
            for column, name in enumerate(names)
        }
        # The control loop requires northern sinking and deep water to
        # share the same initial salinity. Treat them as one latent parameter.
        if "initial_north_salinity_psu" in sampled:
            sampled["initial_deep_salinity_psu"] = sampled["initial_north_salinity_psu"]
        elif "initial_deep_salinity_psu" in sampled:
            sampled["initial_north_salinity_psu"] = sampled["initial_deep_salinity_psu"]
        for attempt in range(101):
            try:
                replace(base_config, **sampled).validate()
                if not _joint_prior_state_is_physical(sampled, base_config):
                    raise ValueError("joint hydrographic prior constraint failed")
                break
            except ValueError:
                if attempt == 100:
                    raise ValueError(
                        "Unable to draw a valid parameter combination after 100 "
                        f"fallback attempts for member {member}. Tighten the ranges."
                    )
                # Redraw rejected members in the same Gaussian-copula space as
                # the primary design. Independent per-parameter fallback draws
                # silently erased the configured physical prior correlations
                # whenever joint validity screening rejected a Sobol/LHS row.
                fallback_unit = fallback_rng.random((1, len(names)))
                fallback_unit = _apply_gaussian_copula_correlations(
                    fallback_unit,
                    names,
                    correlated_priors,
                )[0]
                sampled = {
                    name: (
                        _inverse_physical_prior(
                            float(fallback_unit[column]),
                            SCIENCE_PRIOR_SPECS[name],
                        )
                        if science_modes and name in SCIENCE_PRIOR_SPECS
                        else _inverse_marginal(
                            float(fallback_unit[column]),
                            bounds[0],
                            bounds[1],
                            float(getattr(base_config, name)),
                            distribution,
                        )
                    )
                    for column, (name, bounds) in enumerate(ranges.items())
                }
                if "initial_north_salinity_psu" in sampled:
                    sampled["initial_deep_salinity_psu"] = sampled["initial_north_salinity_psu"]
                elif "initial_deep_salinity_psu" in sampled:
                    sampled["initial_north_salinity_psu"] = sampled["initial_deep_salinity_psu"]
        samples.append(sampled)
    return samples


def _window_mean(frame: pd.DataFrame, column: str, start: float, end: float) -> float:
    subset = frame[(frame["year"] >= start) & (frame["year"] <= end)]
    if subset.empty:
        return float("nan")
    return float(subset[column].mean())


def _historical_diagnostics(config: ModelConfig) -> dict[str, float]:
    historical_config = replace(
        config,
        start_year=1850.0,
        duration_years=173.0,
        scenario="ssp245",
        forcing_mode="total_effective",
        additional_forcing_wm2=0.0,
        freshwater_hosing_sv=0.0,
        freshwater_start_fraction=1.0,
        record_every_years=1.0,
    )
    result = ProcessClimateModel(historical_config).run()
    frame = result.dataframe
    baseline = _window_mean(frame, "global_surface_warming_c", 1850.0, 1900.0)
    warming = _window_mean(frame, "global_surface_warming_c", 2011.0, 2020.0) - baseline
    eei = _window_mean(frame, "toa_imbalance_wm2", 2006.0, 2018.0)

    ohue_frame = frame[(frame["year"] >= 1970.0) & (frame["year"] <= 2019.0)].copy()
    temperature = ohue_frame["global_surface_warming_c"].to_numpy(dtype=float) - baseline
    ocean_uptake = ohue_frame["ocean_heat_uptake_wm2"].to_numpy(dtype=float)
    valid = np.isfinite(temperature) & np.isfinite(ocean_uptake) & (temperature > 0.05)
    if np.sum(valid) >= 5 and float(np.sum(temperature[valid] ** 2)) > 0.0:
        ohue = float(
            np.sum(temperature[valid] * ocean_uptake[valid])
            / np.sum(temperature[valid] ** 2)
        )
    else:
        ohue = float("nan")

    amoc = _window_mean(frame, "amoc_sv", 2004.0, 2023.0)
    fovs = _window_mean(frame, "fovs_sv", 2004.0, 2023.0)
    mht = (
        amoc * config.amoc_heat_transport_pw_per_sv
        + config.atlantic_gyre_heat_transport_pw
    )
    return {
        "historical_warming_2011_2020_c": warming,
        "historical_eei_2006_2018_wm2": eei,
        # Historical key retained for output compatibility. This is now
        # calculated from explicit mixed-layer-to-deep-ocean heat uptake, not
        # from total TOA imbalance.
        "historical_ohue_1970_2019_wm2_k": ohue,
        "historical_ocean_heat_uptake_efficiency_1970_2019_wm2_k": ohue,
        "historical_amoc_2004_2023_sv": amoc,
        "historical_mht_2004_2023_pw": mht,
        "historical_fovs_2004_2023_sv": fovs,
    }


def _amoc_response_diagnostics(config: ModelConfig) -> dict[str, float]:
    """Standardized transient constraints on AMOC response, not initial state."""
    high_config = replace(
        config,
        start_year=1850.0,
        duration_years=250.0,
        scenario="ssp585",
        forcing_mode="total_effective",
        additional_forcing_wm2=0.0,
        freshwater_hosing_sv=0.0,
        record_every_years=1.0,
        auto_initialize_from_1850=False,
    )
    high = ProcessClimateModel(high_config).run().dataframe
    baseline = _window_mean(high, "amoc_sv", 1995.0, 2014.0)
    endpoint = _window_mean(high, "amoc_sv", 2081.0, 2100.0)
    decline = 100.0 * (1.0 - endpoint / baseline) if baseline > 0.0 else float("nan")

    hosing_config = replace(
        config,
        start_year=1850.0,
        duration_years=80.0,
        scenario="constant",
        co2_start_ppm=config.co2_reference_ppm,
        additional_forcing_wm2=0.0,
        freshwater_hosing_sv=0.1,
        freshwater_start_fraction=0.0,
        freshwater_ramp_years=0.0,
        warming_freshwater_sv_per_k=0.0,
        record_every_years=1.0,
        auto_initialize_from_1850=False,
    )
    hosing = ProcessClimateModel(hosing_config).run().dataframe
    initial = float(hosing.iloc[0]["amoc_sv"])
    year40 = _window_mean(hosing, "amoc_sv", 1885.0, 1895.0)
    hosing_decline = 100.0 * (1.0 - year40 / initial) if initial > 0.0 else float("nan")
    return {
        "ssp585_amoc_decline_2100_percent": float(decline),
        "hosing_0p1_amoc_decline_40yr_percent": float(hosing_decline),
    }


def _member_worker(
    payload: tuple[
        int,
        dict[str, Any],
        dict[str, float],
        str,
        bool,
        bool,
        float,
    ]
) -> dict[str, Any]:
    (
        member_id,
        config_dict,
        sampled,
        constraint_mode,
        diagnose_each,
        run_calibration_experiments,
        equilibrium_years,
    ) = payload
    try:
        config = ModelConfig(**config_dict)
        result = ProcessClimateModel(config).run()
        frame = result.dataframe

        diagnostic_summary: dict[str, Any] = {
            "co2_doubling_erf_wm2": config.co2_doubling_erf_wm2,
        }
        if diagnose_each or run_calibration_experiments:
            diagnostics = diagnose_climate_sensitivity(
                config,
                equilibrium_years=equilibrium_years,
                maximum_equilibrium_years=equilibrium_years,
                auto_extend_equilibrium=False,
            )
            feedbacks = diagnostics.feedbacks_wm2_k
            diagnostic_summary.update(
                diagnostics.summary()
            )
            diagnostic_summary.update(
                {
                    "feedback_planck_wm2_k": float(feedbacks["Planck"]),
                    "feedback_lapse_rate_wm2_k": float(feedbacks["Lapse rate"]),
                    "feedback_water_vapor_wm2_k": float(feedbacks["Water vapor"]),
                    "feedback_wv_lr_wm2_k": float(
                        feedbacks["Water vapor"] + feedbacks["Lapse rate"]
                    ),
                    "feedback_surface_albedo_wm2_k": float(feedbacks["Surface albedo"]),
                    "feedback_cloud_wm2_k": float(feedbacks["Cloud"]),
                    "feedback_net_wm2_k": float(feedbacks["Net feedback"]),
                }
            )
        if run_calibration_experiments and constraints_enabled(constraint_mode):
            diagnostic_summary.update(_historical_diagnostics(config))
            if normalize_constraint_mode(constraint_mode) == "ar6_amoc":
                diagnostic_summary.update(_amoc_response_diagnostics(config))

        required = [name for name in TIME_SERIES_METRICS if name != "amoc_heat_transport_pw"]
        missing = [name for name in required if name not in frame]
        if missing:
            raise KeyError("Model output is missing metrics: " + ", ".join(missing))

        series: dict[str, np.ndarray] = {}
        for metric in TIME_SERIES_METRICS:
            if metric == "amoc_heat_transport_pw":
                series[metric] = (
                    frame["amoc_sv"].to_numpy(dtype=np.float32)
                    * np.float32(config.amoc_heat_transport_pw_per_sv)
                )
            else:
                series[metric] = frame[metric].to_numpy(dtype=np.float32)

        final_map = result.map_at_index(-1, absolute=False).astype(np.float32)
        final_sea_ice_map = result.sea_ice_map_at_index(-1).astype(np.float32)
        final_snow_map = result.snow_map_at_index(-1).astype(np.float32)
        summary = result.summary()
        summary.update(diagnostic_summary)
        return {
            "member": member_id,
            "status": "ok",
            "sampled": sampled,
            "years": frame["year"].to_numpy(dtype=np.float64),
            "series": series,
            "final_map": final_map,
            "final_sea_ice_map": final_sea_ice_map,
            "final_snow_map": final_snow_map,
            "summary": summary,
        }
    except Exception as exc:
        return {
            "member": member_id,
            "status": "failed",
            "sampled": sampled,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(limit=12),
        }


def _automatic_worker_count(requested: int) -> int:
    if requested > 0:
        return requested
    cpu_count = os.cpu_count() or 1
    return max(1, min(8, cpu_count - 1 if cpu_count > 1 else 1))


def _normal_z_for_central_probability(probability: float) -> float:
    if not 0.0 < probability < 1.0:
        raise ValueError("Constraint probability must be between zero and one.")
    return float(norm.ppf(0.5 + probability / 2.0))


def _split_normal_loglike(value: float, target: ConstraintTarget) -> float:
    if not math.isfinite(value):
        return float("-inf")
    z = _normal_z_for_central_probability(target.probability)
    sigma_minus = max((target.center - target.lower) / z, 1.0e-12)
    sigma_plus = max((target.upper - target.center) / z, 1.0e-12)
    sigma = sigma_minus if value < target.center else sigma_plus
    return float(-0.5 * target.strength * ((value - target.center) / sigma) ** 2)


def _hard_filter_reason(summary: dict[str, Any], constraint_mode: str) -> str:
    """Return an unconditional numerical/physical rejection reason.

    Scenario-safety diagnostics are mandatory in every Monte Carlo mode.
    Calibration diagnostics are required only for posterior modes, but are
    still checked whenever a caller supplies them. This keeps observational
    weighting optional without allowing invalid members to receive weight.
    """
    basic_required = [
        "maximum_absolute_salt_conservation_error_ppm",
        "maximum_pre_projection_salt_conservation_error_ppm",
        "cumulative_absolute_salt_projection_correction_ppm",
        "initial_amoc_density_driver_ratio",
        "maximum_arctic_open_water_temperature_c",
        "maximum_arctic_open_water_temperature_c_at_5pct_open",
        "maximum_dormant_arctic_open_water_heat_wyr_m2",
        "arctic_reference_periodic_closure_wyr_m2",
        "arctic_reference_spinup_convergence_wyr_m2",
        "arctic_reference_convergence_tolerance_wyr_m2",
    ]
    for key in basic_required:
        value = summary.get(key)
        if value is None or not math.isfinite(float(value)):
            return f"non-finite or missing {key}"

    post_salt_error = abs(
        float(summary["maximum_absolute_salt_conservation_error_ppm"])
    )
    pre_salt_error = abs(
        float(summary["maximum_pre_projection_salt_conservation_error_ppm"])
    )
    cumulative_projection = abs(
        float(summary["cumulative_absolute_salt_projection_correction_ppm"])
    )
    initial_density_ratio = float(summary["initial_amoc_density_driver_ratio"])
    maximum_arctic_open_temperature = float(
        summary["maximum_arctic_open_water_temperature_c"]
    )
    maximum_arctic_open_temperature_5pct = float(
        summary["maximum_arctic_open_water_temperature_c_at_5pct_open"]
    )
    maximum_dormant_open_heat = float(
        summary["maximum_dormant_arctic_open_water_heat_wyr_m2"]
    )
    reference_closure = abs(
        float(summary["arctic_reference_periodic_closure_wyr_m2"])
    )
    reference_convergence = abs(
        float(summary["arctic_reference_spinup_convergence_wyr_m2"])
    )
    reference_tolerance = float(
        summary["arctic_reference_convergence_tolerance_wyr_m2"]
    )

    if post_salt_error > 1.0e-3:
        return "salt conservation error exceeds 0.001 ppm"
    if pre_salt_error > 1.0e-8 * (1.0 + 1.0e-9):
        return "pre-projection salt residual exceeds the roundoff ceiling"
    if cumulative_projection > 1.0e-4:
        return "cumulative salt roundoff projection exceeds 0.0001 ppm"
    if not 0.68 <= initial_density_ratio <= 1.25:
        return "absolute initial AMOC density margin outside calibrated bounds"
    if maximum_arctic_open_temperature > 30.0:
        return "Arctic local open-water temperature exceeds 30 C"
    if maximum_arctic_open_temperature_5pct > 20.0:
        return "Arctic open-water temperature exceeds 20 C where open fraction is at least 5%"
    if maximum_dormant_open_heat > 1.0e-10:
        return "positive Arctic open-water heat remains under effectively closed ice cover"
    if reference_closure > reference_tolerance * (1.0 + 1.0e-9):
        return "Arctic reference cycle exceeds its periodic-closure tolerance"
    if reference_convergence > reference_tolerance * (1.0 + 1.0e-9):
        return "Arctic reference spin-up exceeds its convergence tolerance"

    calibration_keys = [
        "equilibrium_ecs_c",
        "tcr_c",
        "feedback_net_wm2_k",
        "equilibrium_toa_imbalance_wm2",
    ]
    calibration_required = constraints_enabled(constraint_mode)
    calibration_present = any(key in summary for key in calibration_keys)
    if calibration_required or calibration_present:
        for key in calibration_keys:
            value = summary.get(key)
            if value is None or not math.isfinite(float(value)):
                return f"non-finite or missing {key}"
        if (
            "equilibrium_converged" in summary
            and not bool(summary["equilibrium_converged"])
        ):
            return "abrupt-2xCO2 experiment did not satisfy the TOA convergence criterion"
        ecs = float(summary["equilibrium_ecs_c"])
        tcr = float(summary["tcr_c"])
        net = float(summary["feedback_net_wm2_k"])
        residual = abs(float(summary["equilibrium_toa_imbalance_wm2"]))
        if not 0.5 <= ecs <= 10.0:
            return "ECS outside numerical plausibility bounds"
        if not 0.3 <= tcr <= 5.0:
            return "TCR outside numerical plausibility bounds"
        if net >= -0.10:
            return "non-stabilizing net feedback"
        if residual > 1.0:
            return "2xCO2 equilibrium residual exceeds 1.0 W/m2"
    return ""


def compute_importance_weights(
    successful: list[dict[str, Any]],
    constraint_mode: str,
) -> tuple[np.ndarray, np.ndarray, list[str], list[ConstraintTarget]]:
    member_count = len(successful)
    if member_count == 0:
        raise RuntimeError("No successful ensemble members were provided.")

    reasons = [
        _hard_filter_reason(result["summary"], constraint_mode)
        for result in successful
    ]
    valid = np.array([not reason for reason in reasons], dtype=bool)
    if not np.any(valid):
        raise RuntimeError(
            "No ensemble member passed the unconditional numerical/physical "
            "safety filters. Inspect monte_carlo_members.csv."
        )

    if not constraints_enabled(constraint_mode):
        weights = np.zeros(member_count, dtype=float)
        weights[valid] = 1.0 / float(np.sum(valid))
        logweights = np.full(member_count, float("-inf"), dtype=float)
        logweights[valid] = 0.0
        return weights, logweights, reasons, []

    targets = list(AR6_TARGETS)
    if constraint_mode == "ar6_amoc":
        targets.extend(AMOC_TARGETS)

    logweights = np.full(member_count, float("-inf"), dtype=float)
    for index, result in enumerate(successful):
        if not valid[index]:
            continue
        summary = result["summary"]
        grouped_loglikes: dict[str, list[float]] = {}
        missing = False
        for target in targets:
            if target.key not in summary:
                reasons[index] = f"missing diagnostic {target.key}"
                missing = True
                break
            group = CONSTRAINT_GROUPS.get(target.key, target.key)
            target_loglike = _split_normal_loglike(float(summary[target.key]), target)
            summary[f"constraint_loglike_target_{target.key}"] = target_loglike
            grouped_loglikes.setdefault(group, []).append(target_loglike)
        if missing:
            continue
        group_scores = {
            group: float(np.mean(values))
            for group, values in grouped_loglikes.items()
        }
        weighted_group_scores: dict[str, float] = {}
        for group, score in group_scores.items():
            group_weight = float(CONSTRAINT_GROUP_WEIGHTS.get(group, 1.0))
            weighted_score = group_weight * score
            summary[f"constraint_loglike_{group}"] = score
            summary[f"constraint_weighted_loglike_{group}"] = weighted_score
            weighted_group_scores[group] = weighted_score
        logweights[index] = float(sum(weighted_group_scores.values()))

    finite = np.isfinite(logweights)
    if not np.any(finite):
        raise RuntimeError(
            "No constrained ensemble member passed the physical filters and "
            "diagnostic likelihood calculation. Broaden the priors or inspect "
            "monte_carlo_members.csv."
        )
    shifted = np.zeros_like(logweights)
    shifted[finite] = np.exp(logweights[finite] - np.max(logweights[finite]))
    total = float(np.sum(shifted))
    if total <= 0.0 or not math.isfinite(total):
        raise RuntimeError("Importance weights underflowed or became non-finite.")
    weights = shifted / total
    return weights, logweights, reasons, targets


def weighted_quantile(
    values: np.ndarray,
    weights: np.ndarray,
    quantiles: Sequence[float],
) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    quantiles_array = np.asarray(quantiles, dtype=float)
    valid = np.isfinite(values) & np.isfinite(weights) & (weights > 0.0)
    if not np.any(valid):
        return np.full(len(quantiles_array), np.nan, dtype=float)
    v = values[valid]
    w = weights[valid]
    order = np.argsort(v)
    v = v[order]
    w = w[order]
    cumulative = np.cumsum(w)
    cumulative /= cumulative[-1]
    # Midpoint convention avoids assigning the whole first weight to q=0.
    midpoint = cumulative - 0.5 * w / cumulative[-1]
    midpoint = np.clip(midpoint, 0.0, 1.0)
    return np.interp(quantiles_array, midpoint, v, left=v[0], right=v[-1])


def weighted_percentile_timeseries(
    values: np.ndarray,
    weights: np.ndarray,
    percentiles: Sequence[float] = PERCENTILES,
) -> np.ndarray:
    q = np.asarray(percentiles, dtype=float) / 100.0
    output = np.empty((len(q), values.shape[1]), dtype=float)
    for time_index in range(values.shape[1]):
        output[:, time_index] = weighted_quantile(values[:, time_index], weights, q)
    return output


def weighted_percentile_maps(
    maps: np.ndarray,
    weights: np.ndarray,
    percentiles: Sequence[float],
) -> np.ndarray:
    q = np.asarray(percentiles, dtype=float) / 100.0
    output = np.empty((len(q), maps.shape[1], maps.shape[2]), dtype=np.float32)
    for latitude_index in range(maps.shape[1]):
        for longitude_index in range(maps.shape[2]):
            output[:, latitude_index, longitude_index] = weighted_quantile(
                maps[:, latitude_index, longitude_index], weights, q
            )
    return output


def _line_alpha(member_count: int) -> float:
    if member_count <= 30:
        return 0.24
    if member_count <= 100:
        return 0.11
    if member_count <= 500:
        return 0.035
    if member_count <= 2000:
        return 0.014
    return 0.007


def make_ensemble_line_figure(
    years: np.ndarray,
    values: np.ndarray,
    weights: np.ndarray,
    title: str,
    ylabel: str,
    max_plotted: int = 0,
    seed: int = 0,
    zero_line: bool = False,
    weighted: bool = False,
    reference_line: float | None = None,
    reference_label: str = "",
) -> plt.Figure:
    member_count = values.shape[0]
    if max_plotted > 0 and member_count > max_plotted:
        rng = np.random.default_rng(seed)
        selected = np.sort(rng.choice(member_count, size=max_plotted, replace=False))
        plotted = values[selected]
        plotted_note = f"Randomly plotted {max_plotted:,} of {member_count:,} prior members"
    else:
        plotted = values
        plotted_note = f"All {member_count:,} successful prior members plotted"

    quantiles = weighted_percentile_timeseries(values, weights, PERCENTILES)
    q01, q05, q17, q50, q83, q95, q99 = quantiles
    fig, ax = plt.subplots(figsize=(11.5, 6.5), constrained_layout=True)
    alpha = _line_alpha(len(plotted))
    for row in plotted:
        ax.plot(
            years,
            row,
            linewidth=0.50,
            alpha=alpha,
            color="#5f6b76",
            rasterized=True,
        )
    ax.fill_between(years, q01, q99, alpha=0.10, color="#4c78a8", label="1-99%")
    ax.fill_between(years, q05, q95, alpha=0.15, color="#4c78a8", label="5-95%")
    ax.fill_between(years, q17, q83, alpha=0.24, color="#4c78a8", label="17-83%")
    ax.plot(years, q50, linewidth=2.1, color="black", label="Weighted median" if weighted else "Median")
    if reference_line is not None:
        ax.axhline(
            float(reference_line),
            linewidth=1.0,
            color="black",
            linestyle="--",
            label=reference_label or f"{reference_line:g} reference",
        )
    if zero_line:
        ax.axhline(0.0, linewidth=0.85, color="black", linestyle=":")
    ax.set_xlabel("Year")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True, alpha=0.22)
    ax.legend(loc="best")
    ax.text(
        0.01,
        0.01,
        plotted_note + ("; bands are importance-weighted" if weighted else ""),
        transform=ax.transAxes,
        fontsize=8.3,
        va="bottom",
        ha="left",
        bbox={"facecolor": "white", "alpha": 0.78, "edgecolor": "none"},
    )
    return fig


def make_endpoint_histogram(
    values: np.ndarray,
    weights: np.ndarray,
    title: str,
    xlabel: str,
    weighted: bool,
    reference_line: float | None = None,
    reference_label: str = "",
) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(8.9, 5.7), constrained_layout=True)
    finite_values = np.asarray(values, dtype=float)
    finite_values = finite_values[np.isfinite(finite_values)]
    if finite_values.size == 0:
        raise ValueError(f"No finite values are available for histogram: {title}")
    data_min = float(np.min(finite_values))
    data_max = float(np.max(finite_values))
    data_span = data_max - data_min
    near_constant_tolerance = max(abs(data_min), abs(data_max), 1.0) * 1.0e-9
    if data_span <= near_constant_tolerance:
        padding = max(abs(data_min) * 0.02, 0.05)
        bins: int | np.ndarray = np.array([data_min - padding, data_max + padding])
    else:
        target_bins = int(np.clip(np.sqrt(len(values)) * 2.0, 3, 80))
        bins = np.linspace(data_min, data_max, target_bins + 1, dtype=np.float64)
        bins[0] = np.nextafter(bins[0], -np.inf)
        bins[-1] = np.nextafter(bins[-1], np.inf)
    ax.hist(
        values,
        bins=bins,
        weights=weights if weighted else None,
        density=weighted,
        alpha=0.78,
    )
    q01, q05, median, q95, q99 = weighted_quantile(
        values, weights, [0.01, 0.05, 0.50, 0.95, 0.99]
    )
    ax.axvline(median, color="black", linewidth=1.5, label=f"Median {median:.3g}")
    if reference_line is not None:
        ax.axvline(
            float(reference_line),
            color="black",
            linewidth=1.0,
            linestyle="--",
            label=reference_label or f"{reference_line:g} reference",
        )
    ax.axvspan(q01, q99, alpha=0.08, label=f"1-99%: {q01:.3g} to {q99:.3g}")
    ax.axvspan(q05, q95, alpha=0.14, label=f"5-95%: {q05:.3g} to {q95:.3g}")
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Posterior probability density" if weighted else "Members")
    ax.set_title(title)
    ax.grid(True, axis="y", alpha=0.22)
    ax.legend()
    return fig


def make_endpoint_scatter(
    warming: np.ndarray,
    amoc: np.ndarray,
    weights: np.ndarray,
    weighted: bool,
) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(8.6, 6.1), constrained_layout=True)
    if weighted:
        scaled = weights / max(float(np.max(weights)), 1.0e-15)
        sizes = 8.0 + 90.0 * np.sqrt(scaled)
        alpha = 0.15 + 0.65 * np.sqrt(scaled)
        for x, y, size, point_alpha in zip(warming, amoc, sizes, alpha):
            ax.scatter([x], [y], s=float(size), alpha=float(point_alpha))
    else:
        ax.scatter(warming, amoc, s=18, alpha=0.45)
    ax.axhline(
        AMOC_SIX_SV_REFERENCE,
        color="black",
        linewidth=1.0,
        linestyle="--",
        label="6 Sv reference",
    )
    ax.axhline(0.0, color="black", linewidth=0.8, linestyle=":")
    ax.set_xlabel("Final global warming (degC)")
    ax.set_ylabel("Final AMOC (Sv)")
    ax.set_title("Monte Carlo endpoint relationship")
    ax.grid(True, alpha=0.22)
    ax.legend(loc="best")
    return fig


def make_ensemble_map_figure(
    grid: Any,
    field: np.ndarray,
    title: str,
    label: str,
    diverging: bool | None = None,
) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(12.0, 6.1), constrained_layout=True)
    extent = [
        float(grid.lon_edges[0]),
        float(grid.lon_edges[-1]),
        float(grid.lat_edges[0]),
        float(grid.lat_edges[-1]),
    ]
    finite = field[np.isfinite(field)]
    if finite.size == 0:
        raise ValueError("Cannot plot an empty Monte Carlo map field.")
    if diverging is None:
        diverging = bool(float(np.nanmin(finite)) < 0.0 < float(np.nanmax(finite)))
    if diverging:
        limit = max(
            abs(float(np.nanpercentile(finite, 1.0))),
            abs(float(np.nanpercentile(finite, 99.0))),
            0.1,
        )
        image = ax.imshow(
            field,
            origin="lower",
            extent=extent,
            aspect="auto",
            interpolation="bilinear",
            cmap="coolwarm",
            norm=TwoSlopeNorm(vmin=-limit, vcenter=0.0, vmax=limit),
        )
    else:
        vmin = float(np.nanpercentile(finite, 1.0))
        vmax = float(np.nanpercentile(finite, 99.0))
        if math.isclose(vmin, vmax):
            vmax = vmin + 1.0e-6
        image = ax.imshow(
            field,
            origin="lower",
            extent=extent,
            aspect="auto",
            interpolation="bilinear",
            cmap="inferno" if vmin >= 0.0 else "viridis",
            vmin=vmin,
            vmax=vmax,
        )
    for segment in grid.coastline_polygons:
        coordinates = np.asarray(segment, dtype=float)
        ax.plot(coordinates[:, 0], coordinates[:, 1], color="black", linewidth=0.5)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title(title)
    colorbar = fig.colorbar(image, ax=ax, shrink=0.86)
    colorbar.set_label(label)
    return fig


def _flatten_summary(summary: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in summary.items():
        if key == "feedbacks_wm2_k" and isinstance(value, dict):
            for feedback_name, feedback_value in value.items():
                normalized = feedback_name.lower().replace(" ", "_")
                output[f"feedback_raw_{normalized}_wm2_k"] = feedback_value
        elif isinstance(value, (str, int, float, bool)) or value is None:
            output[key] = value
    return output


def _derive_stack(source: np.ndarray, operation: str) -> np.ndarray:
    baseline_count = min(10, source.shape[1])
    baseline = np.nanmean(source[:, :baseline_count], axis=1)[:, None]
    if operation == "difference_from_baseline":
        return source - baseline
    if operation == "percent_from_baseline":
        denominator = np.where(np.abs(baseline) > 1.0e-8, baseline, np.nan)
        return 100.0 * (source / denominator - 1.0)
    if operation == "decline_percent_from_baseline":
        denominator = np.where(np.abs(baseline) > 1.0e-8, baseline, np.nan)
        return 100.0 * (1.0 - source / denominator)
    if operation == "signed_percent_change_from_baseline":
        denominator = np.where(np.abs(baseline) > 1.0e-8, baseline, np.nan)
        return 100.0 * (source / denominator - 1.0)
    raise ValueError(f"Unsupported derived metric operation: {operation}")


def _weighted_endpoint_stats(values: np.ndarray, weights: np.ndarray) -> dict[str, float]:
    q = weighted_quantile(values, weights, [0.01, 0.05, 0.17, 0.50, 0.83, 0.95, 0.99])
    return {
        "minimum": float(np.nanmin(values)),
        "p01": float(q[0]),
        "p05": float(q[1]),
        "p17": float(q[2]),
        "median": float(q[3]),
        "p83": float(q[4]),
        "p95": float(q[5]),
        "p99": float(q[6]),
        "maximum": float(np.nanmax(values)),
        "weighted_mean": float(np.nansum(values * weights)),
    }


def _stack_values_at_year(
    years: np.ndarray,
    stack: np.ndarray,
    target_year: float,
) -> np.ndarray | None:
    """Interpolate every ensemble member to one calendar year."""

    years = np.asarray(years, dtype=float)
    stack = np.asarray(stack, dtype=float)
    if years.ndim != 1 or stack.ndim != 2 or stack.shape[1] != years.size:
        raise ValueError("Time-series stack must have shape (members, years).")
    if years.size < 1 or target_year < years[0] or target_year > years[-1]:
        return None
    if years.size > 1 and np.any(np.diff(years) <= 0.0):
        raise ValueError("Monte Carlo time coordinates must be strictly increasing.")

    right = int(np.searchsorted(years, target_year, side="left"))
    if right < years.size and math.isclose(
        years[right], target_year, rel_tol=0.0, abs_tol=1.0e-9
    ):
        return stack[:, right].astype(float, copy=True)
    if right == 0 or right >= years.size:
        return None
    left = right - 1
    fraction = (target_year - years[left]) / (years[right] - years[left])
    return stack[:, left] + fraction * (stack[:, right] - stack[:, left])


def _stack_trailing_time_mean(
    years: np.ndarray,
    stack: np.ndarray,
    window_years: float,
) -> tuple[np.ndarray | None, float, float]:
    """Return time-weighted member means over the final calendar-year window."""

    years = np.asarray(years, dtype=float)
    stack = np.asarray(stack, dtype=float)
    if window_years <= 0.0:
        raise ValueError("Trailing averaging window must be positive.")
    if years.ndim != 1 or stack.ndim != 2 or stack.shape[1] != years.size:
        raise ValueError("Time-series stack must have shape (members, years).")
    if years.size < 2 or np.any(np.diff(years) <= 0.0):
        return None, float("nan"), float("nan")

    end_year = float(years[-1])
    start_year = end_year - float(window_years)
    if start_year < float(years[0]) - 1.0e-9:
        return None, start_year, end_year

    start_values = _stack_values_at_year(years, stack, start_year)
    end_values = _stack_values_at_year(years, stack, end_year)
    if start_values is None or end_values is None:
        return None, start_year, end_year

    interior = (years > start_year) & (years < end_year)
    integration_years = np.concatenate(
        ([start_year], years[interior], [end_year])
    )
    integration_values = np.concatenate(
        (
            start_values[:, None],
            stack[:, interior],
            end_values[:, None],
        ),
        axis=1,
    )
    means = np.trapezoid(integration_values, integration_years, axis=1) / window_years
    return means, start_year, end_year


def _normalized_weight_fraction(
    condition: np.ndarray,
    valid: np.ndarray,
    weights: np.ndarray,
) -> float | None:
    local_weights = np.asarray(weights, dtype=float)[valid]
    if local_weights.size == 0 or np.sum(local_weights) <= 0.0:
        return None
    local_weights = local_weights / np.sum(local_weights)
    return float(np.sum(local_weights * np.asarray(condition, dtype=float)[valid]))


def build_amoc_completion_counts(
    years: np.ndarray,
    amoc_stack: np.ndarray,
    weights: np.ndarray,
    target_year: float = 2100.0,
    target_threshold_sv: float = 10.0,
    final_window_years: float = 30.0,
    collapse_threshold_sv: float = AMOC_SIX_SV_REFERENCE,
    persistence_fraction: float = 0.95,
    recovery_years: float = 5.0,
    posterior_weighting_enabled: bool = False,
) -> dict[str, Any]:
    """Build the requested AMOC completion counts for an ensemble."""

    years = np.asarray(years, dtype=float)
    amoc_stack = np.asarray(amoc_stack, dtype=float)
    weights = np.asarray(weights, dtype=float)
    if amoc_stack.ndim != 2 or amoc_stack.shape[0] != weights.size:
        raise ValueError("AMOC stack and member weights are inconsistent.")

    target_values = _stack_values_at_year(years, amoc_stack, target_year)
    target_record: dict[str, Any] = {
        "available": target_values is not None,
        "year": float(target_year),
        "criterion": f"AMOC < {target_threshold_sv:g} Sv",
        "threshold_sv": float(target_threshold_sv),
        "count_under_threshold": None,
        "count_not_under_threshold": None,
        "unclassified_members": None,
        "fraction_under_threshold": None,
        "conditional_weighted_fraction_under_threshold": None,
        "posterior_weight_sum_under_threshold": None,
        "posterior_weight_sum_not_under_threshold": None,
        "posterior_weight_sum_unclassified": None,
    }
    if target_values is not None:
        valid = np.isfinite(target_values)
        under = target_values < target_threshold_sv
        valid_count = int(np.sum(valid))
        under_count = int(np.sum(under & valid))
        target_record.update(
            {
                "count_under_threshold": under_count,
                "count_not_under_threshold": valid_count - under_count,
                "unclassified_members": int(target_values.size - valid_count),
                "fraction_under_threshold": (
                    float(under_count / valid_count) if valid_count else None
                ),
                "conditional_weighted_fraction_under_threshold": _normalized_weight_fraction(
                    under, valid, weights
                ),
                "posterior_weight_sum_under_threshold": float(
                    np.sum(weights[under & valid])
                ),
                "posterior_weight_sum_not_under_threshold": float(
                    np.sum(weights[(~under) & valid])
                ),
                "posterior_weight_sum_unclassified": float(
                    np.sum(weights[~valid])
                ),
            }
        )

    window_end = float(years[-1]) if years.size else float("nan")
    window_start = window_end - final_window_years
    window_available = bool(
        years.size >= 2 and math.isfinite(window_start) and window_start >= years[0] - 1.0e-9
    )
    final_record: dict[str, Any] = {
        "available": window_available,
        "window_years": float(final_window_years),
        "window_start_year": float(window_start) if window_available else None,
        "window_end_year": float(window_end) if window_available else None,
        "criterion_collapsed": (
            f"final state in [0, {collapse_threshold_sv:g}] Sv, at least "
            f"{100.0 * persistence_fraction:g}% of the final {final_window_years:g} years "
            f"collapsed, and no active recovery lasting {recovery_years:g} years"
        ),
        "criterion_reversed": "final AMOC < 0 Sv",
        "criterion_active": f"final AMOC > {collapse_threshold_sv:g} Sv",
        "criterion_not_collapsed": f"final AMOC > {collapse_threshold_sv:g} Sv",
        "collapse_threshold_sv": float(collapse_threshold_sv),
        "persistence_required_fraction": float(persistence_fraction),
        "recovery_disqualifying_years": float(recovery_years),
        "collapsed_count": None,
        "reversed_count": None,
        "active_count": None,
        "not_collapsed_count": None,
        "unclassified_members": None,
        "collapsed_fraction": None,
        "reversed_fraction": None,
        "active_fraction": None,
        "conditional_weighted_collapse_fraction": None,
        "conditional_weighted_reversal_fraction": None,
        "conditional_weighted_active_fraction": None,
        "posterior_weight_sum_collapsed": None,
        "posterior_weight_sum_reversed": None,
        "posterior_weight_sum_active": None,
        "posterior_weight_sum_not_collapsed": None,
        "posterior_weight_sum_unclassified": None,
        "mean_final_window_collapsed_fraction": None,
        "median_longest_continuous_collapse_years": None,
    }
    if window_available:
        diagnostics: list[dict[str, Any] | None] = []
        for row in amoc_stack:
            try:
                diagnostics.append(
                    collapse_duration_diagnostics(
                        row,
                        years,
                        collapse_threshold_sv,
                        final_window_years,
                        persistence_fraction,
                        recovery_years,
                    )
                )
            except ValueError:
                diagnostics.append(None)
        valid = np.asarray([item is not None for item in diagnostics], dtype=bool)
        collapsed = np.asarray(
            [bool(item and item["persistent_collapsed"]) for item in diagnostics],
            dtype=bool,
        )
        reversed_state = np.asarray(
            [bool(item and item["reversed"]) for item in diagnostics],
            dtype=bool,
        )
        active = np.asarray(
            [bool(item and item["active"]) for item in diagnostics],
            dtype=bool,
        )
        not_collapsed = active
        valid_count = int(np.sum(valid))
        collapsed_count = int(np.sum(collapsed & valid))
        reversed_count = int(np.sum(reversed_state & valid))
        active_count = int(np.sum(active & valid))
        collapse_fractions = np.asarray(
            [
                float(item["final_window_collapsed_fraction"])
                if item is not None
                else np.nan
                for item in diagnostics
            ]
        )
        longest_durations = np.asarray(
            [
                float(item["longest_continuous_collapse_years"])
                if item is not None
                else np.nan
                for item in diagnostics
            ]
        )
        final_record.update(
            {
                "collapsed_count": collapsed_count,
                "reversed_count": reversed_count,
                "active_count": active_count,
                "not_collapsed_count": active_count,
                "unclassified_members": int(amoc_stack.shape[0] - valid_count),
                "collapsed_fraction": (
                    float(collapsed_count / valid_count) if valid_count else None
                ),
                "reversed_fraction": (
                    float(reversed_count / valid_count) if valid_count else None
                ),
                "active_fraction": (
                    float(active_count / valid_count) if valid_count else None
                ),
                "conditional_weighted_collapse_fraction": _normalized_weight_fraction(
                    collapsed, valid, weights
                ),
                "conditional_weighted_reversal_fraction": _normalized_weight_fraction(
                    reversed_state, valid, weights
                ),
                "conditional_weighted_active_fraction": _normalized_weight_fraction(
                    active, valid, weights
                ),
                "posterior_weight_sum_collapsed": float(
                    np.sum(weights[collapsed & valid])
                ),
                "posterior_weight_sum_reversed": float(
                    np.sum(weights[reversed_state & valid])
                ),
                "posterior_weight_sum_active": float(
                    np.sum(weights[active & valid])
                ),
                "posterior_weight_sum_not_collapsed": float(
                    np.sum(weights[not_collapsed & valid])
                ),
                "posterior_weight_sum_unclassified": float(np.sum(weights[~valid])),
                "mean_final_window_collapsed_fraction": (
                    float(np.nanmean(collapse_fractions)) if valid_count else None
                ),
                "median_longest_continuous_collapse_years": (
                    float(np.nanmedian(longest_durations)) if valid_count else None
                ),
            }
        )


    return {
        "successful_members": int(amoc_stack.shape[0]),
        "posterior_weighting_enabled": bool(posterior_weighting_enabled),
        "posterior_weight_sum_all_members": float(np.sum(weights)),
        "at_2100": target_record,
        "final_30_year_duration": final_record,
    }


def _format_amoc_completion_counts(counts: dict[str, Any]) -> str:
    lines = [
        "AMOC completion counts",
        f"Successful members: {counts['successful_members']:,}",
    ]
    at_2100 = counts["at_2100"]
    if at_2100["available"]:
        lines.append(
            f"At 2100, AMOC < 10 Sv: {at_2100['count_under_threshold']:,} "
            f"of {counts['successful_members']:,} members"
        )
        if counts.get("posterior_weighting_enabled", False):
            weight_sum = at_2100["posterior_weight_sum_under_threshold"]
            conditional_fraction = at_2100["conditional_weighted_fraction_under_threshold"]
            if weight_sum is not None and conditional_fraction is not None:
                lines.append(
                    f"  Posterior weight under 10 Sv: {weight_sum:.6f} "
                    f"(conditional ensemble fraction {100.0 * conditional_fraction:.2f}%)"
                )
    else:
        lines.append("At 2100, AMOC < 10 Sv: unavailable (2100 is outside the run)")

    final_window = counts["final_30_year_duration"]
    if final_window["available"]:
        lines.extend(
            [
                (
                    f"Final 30-year duration classification ({final_window['window_start_year']:g}-"
                    f"{final_window['window_end_year']:g}):"
                ),
                (
                    f"  Collapsed/weak (0 to {final_window['collapse_threshold_sv']:g} Sv): {final_window['collapsed_count']:,} "
                    f"of {counts['successful_members']:,} members"
                ),
                (
                    f"  Reversed (< 0 Sv): {final_window['reversed_count']:,} "
                    f"of {counts['successful_members']:,} members"
                ),
                (
                    f"  Active (> {final_window['collapse_threshold_sv']:g} Sv): {final_window['active_count']:,} "
                    f"of {counts['successful_members']:,} members"
                ),
            ]
        )
        if counts.get("posterior_weighting_enabled", False):
            collapsed_weight = final_window["posterior_weight_sum_collapsed"]
            reversed_weight = final_window["posterior_weight_sum_reversed"]
            active_weight = final_window["posterior_weight_sum_active"]
            collapse_fraction = final_window["conditional_weighted_collapse_fraction"]
            reversal_fraction = final_window["conditional_weighted_reversal_fraction"]
            active_fraction = final_window["conditional_weighted_active_fraction"]
            if (
                collapsed_weight is not None
                and reversed_weight is not None
                and active_weight is not None
                and collapse_fraction is not None
                and reversal_fraction is not None
                and active_fraction is not None
            ):
                lines.extend(
                    [
                        (
                            f"  Posterior weight collapsed/weak: {collapsed_weight:.6f} "
                            f"(conditional ensemble fraction {100.0 * collapse_fraction:.2f}%)"
                        ),
                        (
                            f"  Posterior weight reversed: {reversed_weight:.6f} "
                            f"(conditional ensemble fraction {100.0 * reversal_fraction:.2f}%)"
                        ),
                        (
                            f"  Posterior weight active: {active_weight:.6f} "
                            f"(conditional ensemble fraction {100.0 * active_fraction:.2f}%)"
                        ),
                    ]
                )
    else:
        lines.append(
            "Final 30-year duration classification: unavailable "
            "(simulation is shorter than 30 years)"
        )
    return "\n".join(lines)


def save_ensemble_outputs(
    output_dir: Path,
    base_config: ModelConfig,
    ranges: dict[str, tuple[float, float]],
    results: list[dict[str, Any]],
    requested_runs: int,
    seed_requested: int,
    seed_used: int,
    seed_source: str,
    distribution: str,
    design: str,
    constraint_mode: str,
    correlated_priors: bool,
    use_science_priors: bool,
    run_calibration_experiments: bool,
    max_plotted: int,
    save_long_csv: bool,
    create_plots: bool = True,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    diagnostics_dir = output_dir / "diagnostics"
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    extreme_percentiles_dir = diagnostics_dir / "1_99_percentiles"
    extreme_percentiles_dir.mkdir(parents=True, exist_ok=True)
    successful = sorted(
        [result for result in results if result["status"] == "ok"],
        key=lambda item: item["member"],
    )
    failed = sorted(
        [result for result in results if result["status"] != "ok"],
        key=lambda item: item["member"],
    )
    validate_ensemble_survival(requested_runs, len(successful), len(failed))

    years = np.asarray(successful[0]["years"], dtype=float)
    for result in successful[1:]:
        if not np.array_equal(years, np.asarray(result["years"], dtype=float)):
            raise RuntimeError("Monte Carlo members returned different time axes.")

    weights, logweights, hard_filter_reasons, targets = compute_importance_weights(
        successful, constraint_mode
    )
    weighted_mode = constraints_enabled(constraint_mode)
    effective_sample_size = float(1.0 / np.sum(np.square(weights)))
    positive_weights = weights[weights > 0.0]
    weight_entropy = float(-np.sum(positive_weights * np.log(positive_weights)))
    weight_perplexity = float(math.exp(weight_entropy))
    maximum_member_weight = float(np.max(weights))
    ensemble_quality = assess_ensemble_quality(
        requested_runs,
        len(successful),
        len(failed),
        effective_sample_size,
        weighted_mode,
    )
    if not weighted_mode:
        weight_quality = "not_applicable"
    elif effective_sample_size < max(20.0, 0.10 * len(successful)):
        weight_quality = "poor"
    elif effective_sample_size < max(50.0, 0.25 * len(successful)):
        weight_quality = "limited"
    else:
        weight_quality = "adequate"

    member_rows: list[dict[str, Any]] = []
    for index, result in enumerate(successful):
        row: dict[str, Any] = {
            "member": result["member"],
            "status": "ok",
            "posterior_weight": float(weights[index]),
            "log_importance_weight": float(logweights[index]),
            "hard_filter_reason": hard_filter_reasons[index],
            **result["sampled"],
            **_flatten_summary(result["summary"]),
        }
        member_rows.append(row)
    for result in failed:
        member_rows.append(
            {
                "member": result["member"],
                "status": "failed",
                "posterior_weight": 0.0,
                "log_importance_weight": float("-inf"),
                **result["sampled"],
                "error": result.get("error", "Unknown failure"),
            }
        )
    members_frame = pd.DataFrame(member_rows).sort_values("member")
    members_frame.to_csv(output_dir / "monte_carlo_members_weighted.csv", index=False)
    # Compatibility filename retained.
    members_frame.to_csv(output_dir / "monte_carlo_members.csv", index=False)

    if failed:
        pd.DataFrame(
            [
                {
                    "member": item["member"],
                    "error": item.get("error", ""),
                    "traceback": item.get("traceback", ""),
                }
                for item in failed
            ]
        ).to_csv(output_dir / "monte_carlo_failures.csv", index=False)

    stacks: dict[str, np.ndarray] = {}
    percentile_columns: dict[str, np.ndarray] = {"year": years}
    npz_payload: dict[str, Any] = {
        "year": years,
        "posterior_weight": weights.astype(np.float64),
    }

    for metric, (title, ylabel, zero_line) in TIME_SERIES_METRICS.items():
        stack = np.stack([item["series"][metric] for item in successful]).astype(np.float32)
        stacks[metric] = stack
        npz_payload[metric] = stack
        quantiles = weighted_percentile_timeseries(stack, weights, PERCENTILES)
        for percentile, values in zip(PERCENTILES, quantiles):
            percentile_columns[f"{metric}_p{int(percentile):02d}"] = values
        if create_plots:
            figure = make_ensemble_line_figure(
                years,
                stack,
                weights,
                title=f"Monte Carlo: {title}",
                ylabel=ylabel,
                max_plotted=max_plotted,
                seed=seed_used,
                zero_line=zero_line,
                weighted=weighted_mode,
                reference_line=(
                    AMOC_SIX_SV_REFERENCE if metric == "amoc_sv" else None
                ),
                reference_label="6 Sv reference",
            )
            figure_directory = (
                output_dir if metric in MAIN_FIGURE_METRICS else diagnostics_dir
            )
            figure.savefig(figure_directory / f"monte_carlo_{metric}_all.png", dpi=190)
            plt.close(figure)

    for metric, (source_name, operation, title, ylabel) in DERIVED_METRICS.items():
        stack = _derive_stack(stacks[source_name], operation)
        stacks[metric] = stack.astype(np.float32)
        npz_payload[metric] = stack.astype(np.float32)
        quantiles = weighted_percentile_timeseries(stack, weights, PERCENTILES)
        for percentile, values in zip(PERCENTILES, quantiles):
            percentile_columns[f"{metric}_p{int(percentile):02d}"] = values
        if create_plots:
            figure = make_ensemble_line_figure(
                years,
                stack,
                weights,
                title=f"Monte Carlo: {title}",
                ylabel=ylabel,
                max_plotted=max_plotted,
                seed=seed_used + 19,
                zero_line=True,
                weighted=weighted_mode,
            )
            figure_directory = (
                output_dir
                if metric in MAIN_DERIVED_FIGURE_METRICS
                else diagnostics_dir
            )
            figure.savefig(figure_directory / f"monte_carlo_{metric}_all.png", dpi=190)
            plt.close(figure)

    np.savez_compressed(output_dir / "monte_carlo_timeseries_weighted.npz", **npz_payload)
    np.savez_compressed(output_dir / "monte_carlo_timeseries.npz", **npz_payload)
    pd.DataFrame(percentile_columns).to_csv(
        output_dir / "monte_carlo_weighted_percentiles.csv", index=False
    )
    pd.DataFrame(percentile_columns).to_csv(
        output_dir / "monte_carlo_percentiles.csv", index=False
    )

    if save_long_csv:
        long_frames: list[pd.DataFrame] = []
        for index, result in enumerate(successful):
            frame = pd.DataFrame({"year": years})
            frame.insert(0, "posterior_weight", weights[index])
            frame.insert(0, "member", result["member"])
            for metric, stack in stacks.items():
                frame[metric] = stack[index]
            long_frames.append(frame)
        pd.concat(long_frames, ignore_index=True).to_csv(
            output_dir / "monte_carlo_timeseries_long.csv", index=False
        )

    final_warming = stacks["global_surface_warming_c"][:, -1]
    final_amoc = stacks["amoc_sv"][:, -1]
    final_fovs = stacks["fovs_sv"][:, -1]
    if create_plots:
        endpoint_plots = [
            (
                make_endpoint_histogram(
                    final_warming,
                    weights,
                    "Final global-warming distribution",
                    "Final global warming (degC)",
                    weighted_mode,
                ),
                "monte_carlo_final_warming_histogram.png",
            ),
            (
                make_endpoint_histogram(
                    final_amoc,
                    weights,
                    "Final AMOC distribution",
                    "Final AMOC (Sv)",
                    weighted_mode,
                    reference_line=AMOC_SIX_SV_REFERENCE,
                    reference_label="6 Sv reference",
                ),
                "monte_carlo_final_amoc_histogram.png",
            ),
            (
                make_endpoint_histogram(
                    final_fovs,
                    weights,
                    "Final FovS distribution",
                    "Final FovS (Sv)",
                    weighted_mode,
                ),
                "monte_carlo_final_fovs_histogram.png",
            ),
            (
                make_endpoint_scatter(final_warming, final_amoc, weights, weighted_mode),
                "monte_carlo_final_warming_vs_amoc.png",
            ),
        ]
        for figure, filename in endpoint_plots:
            figure.savefig(diagnostics_dir / filename, dpi=190)
            plt.close(figure)
    diagnostic_plot_specs = {
        "equilibrium_ecs_c": ("Weighted ECS distribution", "ECS (degC)"),
        "tcr_c": ("Weighted TCR distribution", "TCR (degC)"),
        "feedback_planck_wm2_k": ("Planck-response distribution", "W/m2/K"),
        "feedback_wv_lr_wm2_k": ("Water-vapour plus lapse-rate feedback", "W/m2/K"),
        "feedback_surface_albedo_wm2_k": ("Surface-albedo feedback", "W/m2/K"),
        "feedback_cloud_wm2_k": ("Cloud-feedback distribution", "W/m2/K"),
        "feedback_net_wm2_k": ("Net-feedback distribution", "W/m2/K"),
        "historical_warming_2011_2020_c": ("Historical-warming diagnostic", "degC"),
        "historical_eei_2006_2018_wm2": ("Earth-energy-imbalance diagnostic", "W/m2"),
        "historical_ohue_1970_2019_wm2_k": ("Ocean heat-uptake efficiency", "W/m2/K"),
        "historical_amoc_2004_2023_sv": ("Present-day AMOC diagnostic", "Sv"),
        "historical_fovs_2004_2023_sv": ("Present-day FovS diagnostic", "Sv"),
    }
    successful_frame = members_frame[members_frame["status"] == "ok"].sort_values("member")
    if create_plots:
        for key, (title, xlabel) in diagnostic_plot_specs.items():
            if key not in successful_frame.columns:
                continue
            values = successful_frame[key].to_numpy(dtype=float)
            valid = np.isfinite(values)
            if np.sum(valid) < 2:
                continue
            local_weights = weights[valid]
            local_weights = local_weights / np.sum(local_weights)
            figure = make_endpoint_histogram(
                values[valid], local_weights, title, xlabel, weighted_mode
            )
            figure.savefig(diagnostics_dir / f"monte_carlo_diagnostic_{key}.png", dpi=190)
            plt.close(figure)
    final_maps = np.stack([item["final_map"] for item in successful]).astype(np.float32)
    final_sea_ice_maps = np.stack(
        [item["final_sea_ice_map"] for item in successful]
    ).astype(np.float32)
    final_snow_maps = np.stack(
        [item["final_snow_map"] for item in successful]
    ).astype(np.float32)
    map_percentiles = (1.0, 5.0, 50.0, 95.0, 99.0)
    map_stack = weighted_percentile_maps(final_maps, weights, map_percentiles)
    ice_stack = weighted_percentile_maps(final_sea_ice_maps, weights, map_percentiles)
    snow_stack = weighted_percentile_maps(final_snow_maps, weights, map_percentiles)
    map_p01, map_p05, map_p50, map_p95, map_p99 = map_stack
    ice_p01, ice_p05, ice_p50, ice_p95, ice_p99 = ice_stack
    snow_p01, snow_p05, snow_p50, snow_p95, snow_p99 = snow_stack
    map_mean = np.tensordot(weights, final_maps, axes=(0, 0))
    ice_mean = np.tensordot(weights, final_sea_ice_maps, axes=(0, 0))
    snow_mean = np.tensordot(weights, final_snow_maps, axes=(0, 0))
    map_width_99 = map_p99 - map_p01
    map_width_95 = map_p95 - map_p05
    ice_width_99 = ice_p99 - ice_p01
    snow_width_99 = snow_p99 - snow_p01
    reference_grid = ProcessClimateModel(base_config).grid
    map_products = [
        (map_mean, "Weighted mean final temperature anomaly", "Temperature anomaly (degC)", "monte_carlo_final_map_mean.png", None, diagnostics_dir),
        (map_p50, "Weighted median final temperature anomaly", "Temperature anomaly (degC)", "monte_carlo_final_map_median.png", None, diagnostics_dir),
        (map_p05, "5th-percentile final temperature anomaly", "Temperature anomaly (degC)", "monte_carlo_final_map_p05.png", None, diagnostics_dir),
        (map_p95, "95th-percentile final temperature anomaly", "Temperature anomaly (degC)", "monte_carlo_final_map_p95.png", None, diagnostics_dir),
        (map_width_95, "Final-map 5-95% uncertainty width", "Temperature range (degC)", "monte_carlo_final_map_p95_minus_p05.png", False, diagnostics_dir),
        (ice_mean, "Weighted mean final sea-ice fraction", "Sea-ice fraction", "monte_carlo_final_sea_ice_mean.png", False, diagnostics_dir),
        (ice_p50, "Weighted median final sea-ice fraction", "Sea-ice fraction", "monte_carlo_final_sea_ice_median.png", False, diagnostics_dir),
        (snow_mean, "Weighted mean final snow fraction", "Snow fraction", "monte_carlo_final_snow_mean.png", False, diagnostics_dir),
        (snow_p50, "Weighted median final snow fraction", "Snow fraction", "monte_carlo_final_snow_median.png", False, diagnostics_dir),
        (map_p01, "1st-percentile final temperature anomaly", "Temperature anomaly (degC)", "monte_carlo_final_map_p01.png", None, extreme_percentiles_dir),
        (map_p99, "99th-percentile final temperature anomaly", "Temperature anomaly (degC)", "monte_carlo_final_map_p99.png", None, extreme_percentiles_dir),
        (map_width_99, "Final-map 1-99% uncertainty width", "Temperature range (degC)", "monte_carlo_final_map_p99_minus_p01.png", False, extreme_percentiles_dir),
        (ice_p01, "1st-percentile final sea-ice fraction", "Sea-ice fraction", "monte_carlo_final_sea_ice_p01.png", False, extreme_percentiles_dir),
        (ice_p99, "99th-percentile final sea-ice fraction", "Sea-ice fraction", "monte_carlo_final_sea_ice_p99.png", False, extreme_percentiles_dir),
        (ice_width_99, "Final sea-ice 1-99% uncertainty width", "Fraction range", "monte_carlo_final_sea_ice_p99_minus_p01.png", False, extreme_percentiles_dir),
        (snow_p01, "1st-percentile final snow fraction", "Snow fraction", "monte_carlo_final_snow_p01.png", False, extreme_percentiles_dir),
        (snow_p99, "99th-percentile final snow fraction", "Snow fraction", "monte_carlo_final_snow_p99.png", False, extreme_percentiles_dir),
        (snow_width_99, "Final snow 1-99% uncertainty width", "Fraction range", "monte_carlo_final_snow_p99_minus_p01.png", False, extreme_percentiles_dir),
    ]
    if create_plots:
        for field, title, label, filename, diverging, destination in map_products:
            figure = make_ensemble_map_figure(
                reference_grid, field, title, label, diverging=diverging
            )
            figure.savefig(destination / filename, dpi=190)
            plt.close(figure)
    np.savez_compressed(
        output_dir / "monte_carlo_final_map_percentiles.npz",
        latitude=reference_grid.lat,
        longitude=reference_grid.lon,
        temperature_mean=map_mean.astype(np.float32),
        temperature_p01=map_p01.astype(np.float32),
        temperature_p05=map_p05.astype(np.float32),
        temperature_p50=map_p50.astype(np.float32),
        temperature_p95=map_p95.astype(np.float32),
        temperature_p99=map_p99.astype(np.float32),
        temperature_p99_minus_p01=map_width_99.astype(np.float32),
        temperature_p95_minus_p05=map_width_95.astype(np.float32),
        sea_ice_mean=ice_mean.astype(np.float32),
        sea_ice_p01=ice_p01.astype(np.float32),
        sea_ice_p05=ice_p05.astype(np.float32),
        sea_ice_p50=ice_p50.astype(np.float32),
        sea_ice_p95=ice_p95.astype(np.float32),
        sea_ice_p99=ice_p99.astype(np.float32),
        sea_ice_p99_minus_p01=ice_width_99.astype(np.float32),
        snow_mean=snow_mean.astype(np.float32),
        snow_p01=snow_p01.astype(np.float32),
        snow_p05=snow_p05.astype(np.float32),
        snow_p50=snow_p50.astype(np.float32),
        snow_p95=snow_p95.astype(np.float32),
        snow_p99=snow_p99.astype(np.float32),
        snow_p99_minus_p01=snow_width_99.astype(np.float32),
        # Backward-compatible aliases for temperature maps.
        p01=map_p01.astype(np.float32),
        p05=map_p05.astype(np.float32),
        p50=map_p50.astype(np.float32),
        p95=map_p95.astype(np.float32),
        p99=map_p99.astype(np.float32),
        p99_minus_p01=map_width_99.astype(np.float32),
        p95_minus_p05=map_width_95.astype(np.float32),
        land_fraction=reference_grid.land_fraction_map.astype(np.float32),
    )

    collapse_threshold = base_config.amoc_collapse_threshold_sv
    ever_collapsed = np.array(
        [np.nanmin(row) <= collapse_threshold for row in stacks["amoc_sv"]],
        dtype=bool,
    )
    conditional_weighted_collapse_fraction = float(np.sum(weights * ever_collapsed.astype(float)))
    amoc_completion_counts = build_amoc_completion_counts(
        years=years,
        amoc_stack=stacks["amoc_sv"],
        weights=weights,
        target_year=2100.0,
        target_threshold_sv=10.0,
        final_window_years=30.0,
        collapse_threshold_sv=AMOC_SIX_SV_REFERENCE,
        posterior_weighting_enabled=(
            normalize_constraint_mode(constraint_mode) != "none"
        ),
    )
    final_metrics = {
        metric: _weighted_endpoint_stats(stack[:, -1], weights)
        for metric, stack in stacks.items()
    }

    target_records = [
        {
            **asdict(target),
            "group": CONSTRAINT_GROUPS.get(target.key, target.key),
            "group_weight": CONSTRAINT_GROUP_WEIGHTS.get(
                CONSTRAINT_GROUPS.get(target.key, target.key), 1.0
            ),
        }
        for target in targets
    ]
    active_prior_specs = {
        name: asdict(SCIENCE_PRIOR_SPECS[name])
        for name in ranges
        if use_science_priors and name in SCIENCE_PRIOR_SPECS
    }
    fixed_science_prior_parameters = (
        {
            name: {
                "value": float(getattr(base_config, name)),
                "rationale": rationale,
            }
            for name, rationale in FIXED_SCIENCE_PRIOR_PARAMETERS.items()
        }
        if use_science_priors
        else {}
    )
    ensemble_summary = {
        "model": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "monte_carlo_version": MONTE_CARLO_VERSION,
        "scenario": base_config.scenario,
        "forcing_mode": base_config.forcing_mode,
        "constraint_mode": normalize_constraint_mode(constraint_mode),
        "science_informed_priors": use_science_priors,
        "extra_calibration_experiments": run_calibration_experiments,
        "plots_created": bool(create_plots),
        "selected_scenario_only": not run_calibration_experiments,
        "requested_members": requested_runs,
        "successful_members": len(successful),
        "failed_members": len(failed),
        "survival_fraction": ensemble_quality["survival_fraction"],
        "failed_member_fraction": ensemble_quality["failed_fraction"],
        "ensemble_quality": ensemble_quality,
        "uncertainty_products_valid_for_quantitative_use": ensemble_quality[
            "uncertainty_products_valid_for_quantitative_use"
        ],
        "hard_filtered_members": int(sum(bool(reason) for reason in hard_filter_reasons)),
        "zero_weight_members_after_normalization": int(np.sum(weights == 0.0)),
        "effective_sample_size": effective_sample_size,
        "effective_sample_fraction": effective_sample_size / len(successful),
        "weight_entropy": weight_entropy,
        "weight_perplexity": weight_perplexity,
        "maximum_member_weight": maximum_member_weight,
        "weight_quality": weight_quality,
        "seed": seed_used,
        "seed_requested": seed_requested,
        "seed_source": seed_source,
        "sampling_design": design,
        "sampling_distribution": (
            "mixed_physical_marginals" if use_science_priors else distribution
        ),
        "requested_sampling_distribution": distribution,
        "prior_profile": (
            "broad_physical_process_priors_with_fixed_control_anchors" if use_science_priors else "user_defined"
        ),
        "prior_specifications": active_prior_specs,
        "fixed_science_prior_parameters": fixed_science_prior_parameters,
        "correlated_priors": correlated_priors,
        "prior_correlations": [
            {"first": first, "second": second, "rho": rho}
            for first, second, rho in PRIOR_CORRELATIONS
            if first in ranges and second in ranges
        ],
        "constraint_group_weights": CONSTRAINT_GROUP_WEIGHTS,
        "parameter_ranges": {
            name: {"minimum": bounds[0], "maximum": bounds[1]}
            for name, bounds in ranges.items()
        },
        "constraint_targets": target_records,
        "calibration_targets": [record["key"] for record in target_records],
        "held_out_validation_diagnostics": list(HELD_OUT_VALIDATION_DIAGNOSTICS),
        "evidence_partition": {
            "calibration": {
                "used_for_posterior_weighting": True,
                "metrics": [record["key"] for record in target_records],
            },
            "held_out_validation": {
                "used_for_posterior_weighting": False,
                "metrics": list(HELD_OUT_VALIDATION_DIAGNOSTICS),
            },
        },
        "constraint_likelihood_groups": sorted(set(CONSTRAINT_GROUPS.values())),
        "percentile_bands": [1, 5, 17, 50, 83, 95, 99],
        "amoc_collapse_threshold_sv": collapse_threshold,
        "unweighted_fraction_ever_below_collapse_threshold": float(np.mean(ever_collapsed)),
        "conditional_weighted_fraction_ever_below_collapse_threshold": conditional_weighted_collapse_fraction,
        "number_ever_below_collapse_threshold": int(np.sum(ever_collapsed)),
        "amoc_completion_counts": amoc_completion_counts,
        "number_under_10_sv_at_2100": amoc_completion_counts["at_2100"]["count_under_threshold"],
        "posterior_weight_under_10_sv_at_2100": amoc_completion_counts["at_2100"]["posterior_weight_sum_under_threshold"],
        "conditional_ensemble_fraction_under_10_sv_at_2100": amoc_completion_counts["at_2100"]["conditional_weighted_fraction_under_threshold"],
        "number_collapsed_final_30_year_duration": amoc_completion_counts["final_30_year_duration"]["collapsed_count"],
        "number_reversed_final_30_year_duration": amoc_completion_counts["final_30_year_duration"]["reversed_count"],
        "number_active_final_30_year_duration": amoc_completion_counts["final_30_year_duration"]["active_count"],
        "number_not_collapsed_final_30_year_duration": amoc_completion_counts["final_30_year_duration"]["not_collapsed_count"],
        "posterior_weight_collapsed_final_30_year_duration": amoc_completion_counts["final_30_year_duration"]["posterior_weight_sum_collapsed"],
        "posterior_weight_reversed_final_30_year_duration": amoc_completion_counts["final_30_year_duration"]["posterior_weight_sum_reversed"],
        "posterior_weight_active_final_30_year_duration": amoc_completion_counts["final_30_year_duration"]["posterior_weight_sum_active"],
        "posterior_weight_not_collapsed_final_30_year_duration": amoc_completion_counts["final_30_year_duration"]["posterior_weight_sum_not_collapsed"],
        "conditional_ensemble_fraction_collapsed_final_30_year_duration": amoc_completion_counts["final_30_year_duration"]["conditional_weighted_collapse_fraction"],
        "conditional_ensemble_fraction_reversed_final_30_year_duration": amoc_completion_counts["final_30_year_duration"]["conditional_weighted_reversal_fraction"],
        "conditional_ensemble_fraction_active_final_30_year_duration": amoc_completion_counts["final_30_year_duration"]["conditional_weighted_active_fraction"],
        "final_metrics": final_metrics,
    }
    with (output_dir / "monte_carlo_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(ensemble_summary, handle, indent=2)
    with (output_dir / "monte_carlo_ensemble_quality.json").open(
        "w", encoding="utf-8"
    ) as handle:
        json.dump(ensemble_quality, handle, indent=2)
    with (output_dir / "monte_carlo_constraint_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "constraint_mode": normalize_constraint_mode(constraint_mode),
                "science_informed_priors": use_science_priors,
                "extra_calibration_experiments": run_calibration_experiments,
                "effective_sample_size": effective_sample_size,
                "effective_sample_fraction": effective_sample_size / len(successful),
                "weight_entropy": weight_entropy,
                "weight_perplexity": weight_perplexity,
                "maximum_member_weight": maximum_member_weight,
                "weight_quality": weight_quality,
                "prior_profile": (
                    "broad_physical_process_priors_with_fixed_control_anchors"
                    if use_science_priors
                    else "user_defined"
                ),
                "prior_specifications": active_prior_specs,
                "fixed_science_prior_parameters": fixed_science_prior_parameters,
                "constraint_group_weights": CONSTRAINT_GROUP_WEIGHTS,
                "targets": target_records,
            },
            handle,
            indent=2,
        )
    with (output_dir / "monte_carlo_base_config.json").open("w", encoding="utf-8") as handle:
        json.dump(asdict(base_config), handle, indent=2)
    with (output_dir / "monte_carlo_ranges.json").open("w", encoding="utf-8") as handle:
        json.dump(ensemble_summary["parameter_ranges"], handle, indent=2)
    with (output_dir / "monte_carlo_amoc_counts.json").open("w", encoding="utf-8") as handle:
        json.dump(amoc_completion_counts, handle, indent=2)
    with (output_dir / "monte_carlo_amoc_counts.txt").open("w", encoding="utf-8") as handle:
        handle.write(_format_amoc_completion_counts(amoc_completion_counts) + "\n")
    return ensemble_summary


def run_monte_carlo(
    base_config: ModelConfig,
    ranges: dict[str, tuple[float, float]],
    runs: int,
    seed: int,
    distribution: str,
    design: str,
    constraint_mode: str,
    correlated_priors: bool,
    use_science_priors: bool,
    run_calibration_experiments: bool,
    workers: int,
    output_dir: Path,
    max_plotted: int = 0,
    save_long_csv: bool = False,
    diagnose_each: bool = False,
    equilibrium_years: float = 1200.0,
    create_plots: bool = True,
    member_timeout_seconds: float = 7200.0,
    heartbeat_seconds: float = 30.0,
    resume: bool = False,
    retry_failed_on_resume: bool = True,
    command_arguments: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Run one ensemble under an exclusive output-directory ownership lock."""

    with output_directory_run_lock(Path(output_dir), run_kind="monte_carlo"):
        return _run_monte_carlo_unlocked(
            base_config=base_config,
            ranges=ranges,
            runs=runs,
            seed=seed,
            distribution=distribution,
            design=design,
            constraint_mode=constraint_mode,
            correlated_priors=correlated_priors,
            use_science_priors=use_science_priors,
            run_calibration_experiments=run_calibration_experiments,
            workers=workers,
            output_dir=output_dir,
            max_plotted=max_plotted,
            save_long_csv=save_long_csv,
            diagnose_each=diagnose_each,
            equilibrium_years=equilibrium_years,
            create_plots=create_plots,
            member_timeout_seconds=member_timeout_seconds,
            heartbeat_seconds=heartbeat_seconds,
            resume=resume,
            retry_failed_on_resume=retry_failed_on_resume,
            command_arguments=command_arguments,
        )


def _run_monte_carlo_unlocked(
    base_config: ModelConfig,
    ranges: dict[str, tuple[float, float]],
    runs: int,
    seed: int,
    distribution: str,
    design: str,
    constraint_mode: str,
    correlated_priors: bool,
    use_science_priors: bool,
    run_calibration_experiments: bool,
    workers: int,
    output_dir: Path,
    max_plotted: int = 0,
    save_long_csv: bool = False,
    diagnose_each: bool = False,
    equilibrium_years: float = 1200.0,
    create_plots: bool = True,
    member_timeout_seconds: float = 7200.0,
    heartbeat_seconds: float = 30.0,
    resume: bool = False,
    retry_failed_on_resume: bool = True,
    command_arguments: Sequence[str] | None = None,
) -> dict[str, Any]:
    base_config = resolved_scenario_config(base_config)
    base_config.validate()
    constraint_mode = normalize_constraint_mode(constraint_mode)
    # The posterior mode itself is the explicit opt-in. Diagnostics required by
    # AR6 or AR6+AMOC weighting are enabled automatically, while mode=none runs
    # only the selected experiment unless --mc-diagnose-each is requested.
    run_calibration_experiments = constraints_enabled(constraint_mode)
    output_dir = Path(output_dir)
    seed_requested = int(seed)
    saved_seed, saved_seed_source, _saved_state = saved_seed_for_resume(
        output_dir,
        run_kind="monte_carlo",
        requested_seed=seed_requested,
        resume=bool(resume),
    )
    if saved_seed is None:
        seed_used, seed_source = resolve_random_seed(seed_requested)
    else:
        seed_used = int(saved_seed)
        seed_source = str(saved_seed_source)
    samples = generate_samples(
        base_config,
        ranges,
        runs,
        seed_used,
        distribution,
        design,
        correlated_priors,
        science_modes=use_science_priors,
    )
    worker_count = _automatic_worker_count(workers)
    print(
        f"Starting {runs:,} Monte Carlo members with {worker_count} worker(s).",
        flush=True,
    )
    if seed_source == "system_clock":
        print(
            f"Random seed 0 requested; system-clock seed selected: {seed_used}",
            flush=True,
        )
    else:
        print(f"Random seed: {seed_used}", flush=True)
    print(
        f"Posterior weighting={constraint_mode}; design={design}; marginal={'mixed physical' if use_science_priors else distribution}; "
        f"science_priors={use_science_priors}; correlated_priors={correlated_priors}",
        flush=True,
    )
    print(
        "Sampled ranges: "
        + ", ".join(
            f"{name}=[{bounds[0]:g}, {bounds[1]:g}]"
            for name, bounds in ranges.items()
        ),
        flush=True,
    )
    if use_science_priors:
        print(
            "Fixed science-prior anchors: "
            + ", ".join(
                f"{name}={float(getattr(base_config, name)):g}"
                for name in FIXED_SCIENCE_PRIOR_PARAMETERS
            ),
            flush=True,
        )
    if run_calibration_experiments:
        print(
            f"Posterior mode {constraint_mode} requires ECS, TCR and historical "
            "diagnostics; these calibration experiments will run automatically.",
            flush=True,
        )
    elif diagnose_each:
        print(
            "EXPLICIT DIAGNOSTICS ENABLED: each member will additionally run "
            "abrupt-2xCO2 ECS and 1%-CO2 TCR experiments.",
            flush=True,
        )
    else:
        print(
            f"Selected-scenario-only mode: each member runs only {base_config.scenario} "
            f"from {base_config.start_year:g} to "
            f"{base_config.start_year + base_config.duration_years:g}.",
            flush=True,
        )

    config_payloads = [
        (
            member_id,
            asdict(replace(base_config, **sampled)),
            sampled,
            constraint_mode,
            diagnose_each,
            run_calibration_experiments,
            equilibrium_years,
        )
        for member_id, sampled in enumerate(samples)
    ]
    progress_interval = max(1, runs // 100)
    state_path: Path | None = None

    def report_progress(
        completed: int, total: int, resumed_count: int, elapsed: float
    ) -> None:
        completed_this_run = max(completed - resumed_count, 0)
        rate = completed_this_run / max(elapsed, 1.0e-9)
        remaining = max(total - completed, 0)
        eta_seconds = remaining / rate if rate > 0.0 else float("inf")
        eta_text = (
            f"{eta_seconds / 3600.0:.1f} h"
            if math.isfinite(eta_seconds) and eta_seconds >= 3600.0
            else (
                f"{eta_seconds / 60.0:.1f} min"
                if math.isfinite(eta_seconds)
                else "unknown"
            )
        )
        if state_path is not None:
            update_run_state(
                state_path,
                completed_work_units=int(completed),
                attempted_work_units=int(completed),
                pending_work_units=int(max(total - completed, 0)),
                resumed_work_units=int(resumed_count),
                elapsed_seconds=float(elapsed),
            )
        if completed == 1 or completed == total or completed % progress_interval == 0:
            print(
                f"Completed {completed:,}/{total:,} members "
                f"({100.0 * completed / total:.1f}%) | "
                f"{rate:.3f} members/s | ETA {eta_text}",
                flush=True,
            )

    provenance = runtime_provenance()
    run_fingerprint = stable_fingerprint(
        {
            "model_version": MODEL_VERSION,
            "runtime_provenance_digest": provenance["combined_digest_sha256"],
            "base_config": asdict(base_config),
            "ranges": ranges,
            "runs": runs,
            "seed_used": seed_used,
            "distribution": distribution,
            "design": design,
            "constraint_mode": constraint_mode,
            "correlated_priors": correlated_priors,
            "use_science_priors": use_science_priors,
            "diagnose_each": diagnose_each,
            "run_calibration_experiments": run_calibration_experiments,
            "equilibrium_years": equilibrium_years,
        }
    )
    checkpoint_directory = output_dir / "monte_carlo_checkpoints"
    state_settings = {
        "base_config": asdict(base_config),
        "parameter_ranges": {name: list(bounds) for name, bounds in ranges.items()},
        "runs": int(runs),
        "distribution": distribution,
        "design": design,
        "constraint_mode": constraint_mode,
        "correlated_priors": bool(correlated_priors),
        "use_science_priors": bool(use_science_priors),
        "diagnose_each": bool(diagnose_each),
        "run_calibration_experiments": bool(run_calibration_experiments),
        "equilibrium_years": float(equilibrium_years),
        "retry_failed_on_resume": bool(retry_failed_on_resume),
        "command_arguments": list(command_arguments or []),
    }
    created_unix_seconds = time.time()
    state_template = {
        "format": RUN_STATE_FORMAT,
        "state_version": RUN_STATE_VERSION,
        "run_kind": "monte_carlo",
        "model_version": MODEL_VERSION,
        "status": "interrupted",
        "fingerprint": run_fingerprint,
        "seed_requested": int(seed_requested),
        "seed_used": int(seed_used),
        "seed_source": str(seed_source),
        "checkpoint_directory": checkpoint_directory.name,
        "total_work_units": int(runs),
        "completed_work_units": 0,
        "attempted_work_units": 0,
        "successful_work_units": 0,
        "failed_work_units": 0,
        "validated_work_units": 0,
        "pending_work_units": int(runs),
        "resumed_work_units": 0,
        "work_unit_name": "members",
        "settings": state_settings,
        "created_unix_seconds": created_unix_seconds,
        "updated_unix_seconds": created_unix_seconds,
        "completed_unix_seconds": None,
        "resume_count": 0,
        "last_error": None,
        "runtime_provenance": provenance,
        "checkpoint_format": "safe_json_npy_zip_v2_bounded",
    }
    checkpoint_metadata = {
        "run_kind": "monte_carlo",
        "model_version": MODEL_VERSION,
        "fingerprint": run_fingerprint,
        "seed_used": int(seed_used),
        "runtime_provenance_digest": provenance["combined_digest_sha256"],
        "command_arguments": list(command_arguments or []),
        "state_template": state_template,
    }
    state_path = initialize_run_state(
        output_dir,
        run_kind="monte_carlo",
        model_version=MODEL_VERSION,
        fingerprint=run_fingerprint,
        seed_requested=seed_requested,
        seed_used=seed_used,
        seed_source=seed_source,
        checkpoint_directory=checkpoint_directory.name,
        total_work_units=int(runs),
        work_unit_name="members",
        resume=bool(resume),
        settings=state_settings,
        extra={
            "runtime_provenance": provenance,
            "checkpoint_format": "safe_json_npy_zip_v2_bounded",
        },
    )
    tasks = [(member_id, payload) for member_id, payload in enumerate(config_payloads)]
    try:
        results = run_supervised_tasks(
            tasks,
            _member_worker,
            max_workers=worker_count,
            timeout_seconds=member_timeout_seconds,
            heartbeat_seconds=heartbeat_seconds,
            checkpoint_dir=checkpoint_directory,
            fingerprint=run_fingerprint,
            resume=resume,
            retry_failed_on_resume=bool(retry_failed_on_resume),
            label="Monte Carlo members",
            progress_callback=report_progress,
            checkpoint_metadata=checkpoint_metadata,
        )

        successful_results = [result for result in results if result.get("status") == "ok"]
        failed_results = [result for result in results if result.get("status") != "ok"]
        state_snapshot = load_run_state(output_dir)
        validated_results = (
            compatible_checkpoint_count(output_dir, state_snapshot)
            if state_snapshot is not None
            else 0
        )
        update_run_state(
            state_path,
            completed_work_units=int(runs),
            attempted_work_units=int(runs),
            successful_work_units=int(len(successful_results)),
            failed_work_units=int(len(failed_results)),
            validated_work_units=int(validated_results),
            pending_work_units=0,
        )

        summary = save_ensemble_outputs(
            output_dir=output_dir,
            base_config=base_config,
            ranges=ranges,
            results=results,
            requested_runs=runs,
            seed_requested=seed_requested,
            seed_used=seed_used,
            seed_source=seed_source,
            distribution=distribution,
            design=design,
            constraint_mode=constraint_mode,
            correlated_priors=correlated_priors,
            use_science_priors=use_science_priors,
            run_calibration_experiments=run_calibration_experiments,
            max_plotted=max_plotted,
            save_long_csv=save_long_csv,
            create_plots=create_plots,
        )
        final_status = (
            "completed_with_failures"
            if int(summary["failed_members"]) > 0
            else (
                "completed"
                if bool(summary["uncertainty_products_valid_for_quantitative_use"])
                else "completed_with_quality_warning"
            )
        )
        update_run_state(
            state_path,
            status=final_status,
            completed_work_units=int(runs),
            attempted_work_units=int(runs),
            successful_work_units=int(summary["successful_members"]),
            failed_work_units=int(summary["failed_members"]),
            validated_work_units=int(validated_results),
            pending_work_units=0,
            ensemble_quality=summary["ensemble_quality"],
            summary_file="monte_carlo_summary.json",
        )
        return summary
    except BaseException as exc:
        update_run_state(
            state_path,
            status="interrupted" if isinstance(exc, (KeyboardInterrupt, SystemExit)) else "failed",
            last_error=f"{type(exc).__name__}: {exc}",
        )
        raise


def build_monte_carlo_parser() -> argparse.ArgumentParser:
    parser = build_parser()
    parser.description = (
        "Run selected-scenario Monte Carlo ensembles with optional science "
        "priors and grouped posterior calibration."
    )
    parser.add_argument(
        "--monte-carlo-runs",
        type=int,
        default=512,
        help="Number of prior ensemble members.",
    )
    parser.add_argument(
        "--mc-range",
        nargs=3,
        action="append",
        metavar=("PARAMETER", "MIN", "MAX"),
        help=(
            "Sample a numeric ModelConfig parameter between MIN and MAX. May be "
            "repeated. These exact user ranges are never replaced unless "
            "--mc-use-science-priors is explicitly selected."
        ),
    )
    parser.add_argument(
        "--mc-seed",
        type=int,
        default=0,
        help=(
            "Random seed. Use 0 (default) to generate one from the system clock; "
            "use a nonzero integer for an exactly reproducible ensemble."
        ),
    )
    parser.add_argument(
        "--mc-workers",
        type=int,
        default=0,
        help="Parallel worker processes; 0 selects up to eight automatically.",
    )
    parser.add_argument(
        "--mc-member-timeout-seconds",
        type=float,
        default=7200.0,
        help="Maximum wall-clock seconds for one member before termination.",
    )
    parser.add_argument(
        "--mc-heartbeat-seconds",
        type=float,
        default=30.0,
        help="Progress heartbeat interval while members are still running.",
    )
    parser.add_argument(
        "--mc-resume",
        action="store_true",
        help="Resume compatible completed member checkpoints in the output folder.",
    )
    parser.add_argument(
        "--mc-retry-failed-on-resume",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Retry failed, timed-out, or interrupted checkpoints when resuming "
            "(default: enabled). Use --no-mc-retry-failed-on-resume to preserve "
            "saved failures as final results."
        ),
    )
    parser.add_argument(
        "--mc-sampling",
        choices=SAMPLING_DISTRIBUTIONS,
        default="triangular",
        help="Marginal for user-defined ranges. Built-in physical priors use parameter-specific marginals.",
    )
    parser.add_argument(
        "--mc-design",
        choices=SAMPLING_DESIGNS,
        default="sobol",
        help="Space-filling design used to generate unit-cube samples.",
    )
    parser.add_argument(
        "--mc-constraint-mode",
        choices=CONSTRAINT_MODES,
        default="none",
        help=(
            "Posterior weighting mode. 'none' runs only the selected scenario. "
            "AR6 modes automatically run their required calibration experiments."
        ),
    )
    parser.add_argument(
        "--mc-use-science-priors",
        action="store_true",
        help=(
            "Use broad physically motivated priors with parameter-specific "
            "marginals (beta, log-normal, truncated normal, or uniform). Their "
            "support is deliberately wider than the posterior likelihood targets."
        ),
    )
    parser.add_argument(
        "--mc-run-calibration-experiments",
        action="store_true",
        help=(
            "Deprecated compatibility flag. AR6 modes now enable their required "
            "abrupt-2xCO2, 1%%-CO2, and historical experiments automatically."
        ),
    )
    parser.add_argument(
        "--mc-no-correlated-priors",
        action="store_true",
        help="Disable the Gaussian-copula correlations used in constrained priors.",
    )
    parser.add_argument(
        "--mc-max-plotted",
        type=int,
        default=0,
        help="Maximum individual prior curves per plot; 0 plots every member.",
    )
    parser.add_argument(
        "--mc-save-long-csv",
        action="store_true",
        help="Also write every member-year row to a potentially large CSV file.",
    )
    parser.add_argument(
        "--mc-no-plots",
        action="store_true",
        help="Write numerical ensemble products without rendering PNG figures.",
    )
    parser.add_argument(
        "--mc-diagnose-each",
        action="store_true",
        help="Explicitly run extra ECS/TCR diagnostics for every member.",
    )
    return parser


def main() -> None:
    args = build_monte_carlo_parser().parse_args()
    if args.run_amoc_hysteresis:
        raise ValueError(
            "AMOC hysteresis is not run inside Monte Carlo members. Run a "
            "separate deterministic hysteresis experiment instead."
        )
    if not 2 <= args.monte_carlo_runs <= 100000:
        raise ValueError("monte_carlo_runs must be between 2 and 100,000.")
    if args.mc_workers < 0:
        raise ValueError("mc_workers cannot be negative.")
    if args.mc_seed < 0:
        raise ValueError(
            "mc_seed cannot be negative. Use 0 for a system-clock seed."
        )
    if args.mc_max_plotted < 0:
        raise ValueError("mc_max_plotted cannot be negative.")
    if args.mc_member_timeout_seconds <= 0.0:
        raise ValueError("mc_member_timeout_seconds must be positive.")
    if args.mc_heartbeat_seconds <= 0.0:
        raise ValueError("mc_heartbeat_seconds must be positive.")
    if args.scenario == "percent_ramp_hold":
        percent_ramp_rates = parse_percent_ramp_rates(
            args.percent_ramp_compare_rates
        )
        if len(percent_ramp_rates) != 1:
            raise ValueError(
                "Monte Carlo percent-ramp runs require exactly one value in "
                "--percent-ramp-compare-rates. Run separate ensembles for "
                "separate growth rates."
            )
    base_config = config_from_args(args)
    ranges = parse_ranges(
        args.mc_range,
        base_config,
        args.mc_constraint_mode,
        args.mc_use_science_priors,
    )
    requested_output = Path(args.output)
    with output_directory_run_lock(requested_output, run_kind="monte_carlo"):
        args.output = prepare_output_directory(
            requested_output,
            overwrite=bool(args.overwrite_output),
            resume=bool(args.mc_resume),
            prompt=True,
        )
        summary = _run_monte_carlo_unlocked(
            base_config=base_config,
            ranges=ranges,
            runs=args.monte_carlo_runs,
            seed=args.mc_seed,
            distribution=args.mc_sampling,
            design=args.mc_design,
            constraint_mode=args.mc_constraint_mode,
            correlated_priors=not args.mc_no_correlated_priors,
            use_science_priors=args.mc_use_science_priors,
            run_calibration_experiments=args.mc_run_calibration_experiments,
            workers=args.mc_workers,
            output_dir=args.output,
            max_plotted=args.mc_max_plotted,
            save_long_csv=args.mc_save_long_csv,
            diagnose_each=args.mc_diagnose_each,
            equilibrium_years=args.equilibrium_years,
            create_plots=not args.mc_no_plots,
            member_timeout_seconds=args.mc_member_timeout_seconds,
            heartbeat_seconds=args.mc_heartbeat_seconds,
            resume=args.mc_resume,
            retry_failed_on_resume=bool(args.mc_retry_failed_on_resume),
            command_arguments=[
                argument
                for argument in sys.argv[1:]
                if argument not in {"--overwrite-output", "--mc-resume"}
            ],
        )
    print(json.dumps(summary, indent=2))
    print("\n" + _format_amoc_completion_counts(summary["amoc_completion_counts"]))
    print(f"\nMonte Carlo outputs written to: {args.output.resolve()}")


if __name__ == "__main__":
    main()
