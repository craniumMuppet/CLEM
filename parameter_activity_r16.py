"""R16 registry for user-facing physical controls.

Compatibility-only keys remain accepted by ModelConfig/CLI so old configurations
load, but they are excluded from active UI and uncertainty surfaces because the
current equations do not read them.
"""
from __future__ import annotations

DEPRECATED_COMPATIBILITY_PARAMETERS = frozenset({
    "amoc_pycnocline_relaxation_years",
    "amoc_stratification_saturation_c",
    "amoc_interhemispheric_temperature_coupling",
    "amoc_convection_critical_density_ratio",
    "amoc_convection_transition_width",
    "amoc_convection_transport_exponent",
    "amoc_convection_collapse_density_ratio",
    "amoc_convection_restart_density_ratio",
    "amoc_collapsed_convection_fraction",
})

R16_STRUCTURAL_CONTROLS = frozenset({
    "amoc_density_geometry",
    "amoc_density_eos",
    "amoc_density_transport_exponent",
    "amoc_hydraulic_depth_exponent",
    "amoc_pycnocline_feedback_strength",
    "amoc_hydraulic_transport_max_sv",
    "amoc_allow_reversal",
    "freshwater_hosing_compensated",
    "greenland_uncompensated_freshwater_enabled",
    "greenland_elevation_feedback_enabled",
    "arctic_forced_ocean_heat_convergence_enabled",
    "arctic_phase_restoring_enabled",
    "arctic_extra_lapse_rate_feedback_enabled",
})

def is_deprecated_compatibility_parameter(name: str) -> bool:
    return name in DEPRECATED_COMPATIBILITY_PARAMETERS


DIAGNOSTIC_ONLY_PARAMETERS = frozenset({"atlantic_gyre_heat_transport_pw"})
