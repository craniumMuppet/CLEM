#!/usr/bin/env python3
"""Streamlit dashboard for the current Coupled Low-complexity Earth Model."""

from __future__ import annotations

from dataclasses import asdict
import io
import json
import zipfile

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

from setting_metadata import setting_tooltip

from climate_model import (
    AMOC_SIX_SV_REFERENCE,
    MODEL_NAME,
    MODEL_VERSION,
    ModelConfig,
    amoc_hysteresis_summary,
    make_amoc_hysteresis_figure,
    make_cryosphere_map_figure,
    make_feedback_figure,
    make_gregory_figure,
    make_temperature_map_figure,
    parse_percent_ramp_rates,
    run_model,
    run_percent_ramp_comparison,
)


DEFAULT_MODEL_CONFIG = ModelConfig()


st.set_page_config(
    page_title=MODEL_NAME,
    page_icon="🌍",
    layout="wide",
)


@st.cache_data(show_spinner=False, max_entries=24)
def run_cached(
    config_json: str,
    equilibrium_years: float,
    run_hysteresis: bool,
    hysteresis_max_hosing: float,
    hysteresis_step: float,
    hysteresis_years_per_step: float,
    hysteresis_spinup_years: float,
):
    config = ModelConfig(**json.loads(config_json))
    return run_model(
        config,
        diagnose=True,
        equilibrium_years=equilibrium_years,
        run_hysteresis=run_hysteresis,
        hysteresis_max_hosing_sv=hysteresis_max_hosing,
        hysteresis_step_sv=hysteresis_step,
        hysteresis_years_per_step=hysteresis_years_per_step,
        hysteresis_spinup_years=hysteresis_spinup_years,
    )


@st.cache_data(show_spinner=False, max_entries=12)
def run_percent_comparison_cached(config_json: str, rates_text: str):
    config = ModelConfig(**json.loads(config_json))
    rates = parse_percent_ramp_rates(rates_text)
    detail, summary, figure = run_percent_ramp_comparison(config, rates)
    image = io.BytesIO()
    figure.savefig(image, format="png", dpi=170)
    plt.close(figure)
    return detail, summary, image.getvalue()


def build_download_bundle(result) -> bytes:
    final_anomaly = result.map_at_index(-1, absolute=False)
    final_absolute = result.map_at_index(-1, absolute=True)
    sea_ice_native_area = result.native_sea_ice_map_at_index(-1)
    sea_ice_display_area = result.sea_ice_display_map_at_index(-1)
    sea_ice_statistical_concentration = result.sea_ice_concentration_map_at_index(-1)
    sea_ice_extent_occupancy = result.sea_ice_extent_occupancy_map_at_index(-1)
    sea_ice_thermodynamic = result.thermodynamic_sea_ice_map_at_index(-1)
    map_frame = pd.DataFrame(
        {
            "latitude": result.grid.lat2d.ravel(),
            "longitude": result.grid.lon2d.ravel(),
            "land": result.grid.land_mask.ravel().astype(int),
            "land_fraction": result.grid.land_fraction_map.ravel(),
            "atlantic_ocean_fraction": result.grid.atlantic_ocean_fraction_map.ravel(),
            "temperature_anomaly_c": final_anomaly.ravel(),
            "absolute_temperature_c": final_absolute.ravel(),
            "sea_ice_native_area_fraction": sea_ice_native_area.ravel(),
            "sea_ice_display_area_fraction": sea_ice_display_area.ravel(),
            "sea_ice_statistical_area_fraction": sea_ice_display_area.ravel(),
            "sea_ice_statistical_concentration_fraction_of_ocean_cell": (
                sea_ice_statistical_concentration.ravel()
            ),
            "sea_ice_extent_occupancy_fraction_of_ocean_cell": (
                sea_ice_extent_occupancy.ravel()
            ),
            "thermodynamic_two_sector_ice_area_fraction": (
                sea_ice_thermodynamic.ravel()
            ),
            # Backward-compatible alias now points to the native physical field.
            "sea_ice_fraction": sea_ice_native_area.ravel(),
            "snow_fraction": result.snow_map_at_index(-1).ravel(),
        }
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("timeseries.csv", result.dataframe.to_csv(index=False))
        archive.writestr("final_map.csv", map_frame.to_csv(index=False))
        archive.writestr("config.json", json.dumps(asdict(result.config), indent=2))
        archive.writestr("summary.json", json.dumps(result.summary(), indent=2))
        if result.diagnostics is not None:
            archive.writestr(
                "abrupt_2xco2_diagnostic.csv",
                result.diagnostics.abrupt_2x.to_csv(index=False),
            )
            archive.writestr(
                "one_percent_co2_diagnostic.csv",
                result.diagnostics.one_percent.to_csv(index=False),
            )
            archive.writestr(
                "sensitivity_diagnostics.json",
                json.dumps(result.diagnostics.summary(), indent=2),
            )
        if result.amoc_hysteresis is not None:
            archive.writestr(
                "amoc_hysteresis.csv",
                result.amoc_hysteresis.to_csv(index=False),
            )
            archive.writestr(
                "amoc_hysteresis_summary.json",
                json.dumps(
                    amoc_hysteresis_summary(
                        result.amoc_hysteresis,
                        collapse_threshold_sv=result.config.amoc_collapse_threshold_sv,
                    ),
                    indent=2,
                ),
            )
    return buffer.getvalue()


st.title(f"{MODEL_NAME} v{MODEL_VERSION}")
st.caption(
    "Latitude-band climate feedbacks coupled to a salt-conserving Atlantic overturning "
    "model with directional advection, an external compensation reservoir, dynamic "
    "pycnocline depth, Atlantic-only heat redistribution, and continuous convective salt feedbacks."
)
st.warning(
    "Scientific-use limits: the primary sea-ice map is the native two-sector "
    "thermodynamic state; optional longitude display and 15%-extent maps are "
    "diagnostic reconstructions without regional forecast skill. Arctic open-water "
    "temperatures are sector diagnostics; AMOC and Greenland results are "
    "sensitivity experiments, not precise regional or collapse forecasts."
)

with st.sidebar:
    st.header("Experiment")
    scenario_label = st.selectbox('CO₂ pathway', ['Overshoot then decline', 'Linear concentration change', '1% annual growth', 'Percent ramp to cap, then hold', 'Constant concentration', 'Abrupt doubled CO₂', 'SSP1-2.6', 'SSP2-4.5', 'SSP4-6.0', 'SSP5-8.5', 'Hybrid SSP switch'], index=0, help=setting_tooltip('scenario_label'))
    scenario_lookup = {
        "Overshoot then decline": "overshoot",
        "Linear concentration change": "linear",
        "1% annual growth": "one_percent",
        "Percent ramp to cap, then hold": "percent_ramp_hold",
        "Constant concentration": "constant",
        "Abrupt doubled CO₂": "step_2x",
        "SSP1-2.6": "ssp126",
        "SSP2-4.5": "ssp245",
        "SSP4-6.0": "ssp460",
        "SSP5-8.5": "ssp585",
        "Hybrid SSP switch": "hybrid_ssp",
    }
    start_year = st.number_input('Start year', min_value=0, max_value=3000, value=int(DEFAULT_MODEL_CONFIG.start_year), help=setting_tooltip('start_year'))
    auto_initialize_from_1850 = st.checkbox('Initialize post-1850 SSP runs from 1850', value=bool(DEFAULT_MODEL_CONFIG.auto_initialize_from_1850), help=setting_tooltip('auto_initialize_from_1850', extra_note='Prevents a cold-start when an SSP experiment begins after 1850. Disable only for a deliberate zero-anomaly or externally restarted run.'))
    duration_years = st.slider('Duration (years)', 50, 650, int(DEFAULT_MODEL_CONFIG.duration_years), 10, help=setting_tooltip('duration_years'))
    co2_start = st.number_input('Starting CO₂ (ppm)', 150.0, 3000.0, float(DEFAULT_MODEL_CONFIG.co2_start_ppm), 5.0, help=setting_tooltip('co2_start'))
    co2_peak = st.number_input('Peak CO₂ (ppm)', 150.0, 5000.0, float(DEFAULT_MODEL_CONFIG.co2_peak_ppm), 10.0, help=setting_tooltip('co2_peak'))
    co2_end = st.number_input('Ending CO₂ (ppm)', 150.0, 5000.0, float(DEFAULT_MODEL_CONFIG.co2_end_ppm), 10.0, help=setting_tooltip('co2_end'))
    if scenario_label == "1% annual growth":
        cap_one_percent = st.checkbox('Cap the 1% pathway', value=True, help=setting_tooltip('cap_one_percent'))
        one_percent_cap = st.number_input('1% pathway cap (ppm)', min_value=150.0, max_value=1000000.0, value=1113.2, step=10.0, disabled=not cap_one_percent, help=setting_tooltip('one_percent_cap'))
    else:
        cap_one_percent = False
        one_percent_cap = 1113.2
    if scenario_label == "Percent ramp to cap, then hold":
        percent_ramp_compare_rates = st.text_input(
            'CO2 growth rates (%/year)', value='0.5,1,2,3,5',
            help=setting_tooltip('percent_ramp_compare_rates')
        )
        try:
            parsed_percent_ramp_rates = parse_percent_ramp_rates(
                percent_ramp_compare_rates
            )
        except ValueError as exc:
            st.error(str(exc))
            st.stop()
        if not parsed_percent_ramp_rates:
            st.error('Enter at least one positive CO2 growth rate.')
            st.stop()
        co2_growth_rate_percent = parsed_percent_ramp_rates[0]
        co2_growth_cap = st.number_input(
            'CO2 ramp cap (ppm)', min_value=150.0, max_value=1000000.0,
            value=float(DEFAULT_MODEL_CONFIG.co2_growth_cap_ppm), step=10.0, help=setting_tooltip('co2_growth_cap')
        )
        co2_hold_years = st.number_input(
            'Post-cap hold (years)', min_value=0.0, max_value=5000.0,
            value=float(DEFAULT_MODEL_CONFIG.co2_hold_years), step=10.0, help=setting_tooltip('co2_hold_years')
        )
    else:
        co2_growth_rate_percent = 1.0
        co2_growth_cap = 1200.0
        co2_hold_years = 200.0
        percent_ramp_compare_rates = ''
    peak_fraction = st.slider('Overshoot peak position', 0.1, 0.9, float(DEFAULT_MODEL_CONFIG.peak_time_fraction), 0.05, help=setting_tooltip('peak_fraction'))
    forcing_mode_label = st.selectbox('SSP forcing mode', ['Full effective forcing', 'CO₂ concentration only'], index=0, help=setting_tooltip('forcing_mode_label'))
    forcing_mode_lookup = {
        "Full effective forcing": "total_effective",
        "CO₂ concentration only": "co2_only",
    }
    ssp_label_lookup = {
        "SSP1-2.6": "ssp126",
        "SSP2-4.5": "ssp245",
        "SSP4-6.0": "ssp460",
        "SSP5-8.5": "ssp585",
    }
    if scenario_label == "Hybrid SSP switch":
        st.subheader("Hybrid SSP pathway")
        ssp_before_label = st.selectbox('Scenario before switch', list(ssp_label_lookup), index=3, help=setting_tooltip('ssp_before_label'))
        ssp_after_label = st.selectbox('Scenario after switch', list(ssp_label_lookup), index=1, help=setting_tooltip('ssp_after_label'))
        ssp_switch_year = st.number_input('Switch year', min_value=1750, max_value=2500, value=int(DEFAULT_MODEL_CONFIG.ssp_switch_year), step=1, help=setting_tooltip('ssp_switch_year'))
        ssp_transition_years = st.slider('Transition duration (years)', 0, 100, int(DEFAULT_MODEL_CONFIG.ssp_transition_years), 1, help=setting_tooltip('ssp_transition_years'))
    else:
        ssp_before_label = "SSP5-8.5"
        ssp_after_label = "SSP2-4.5"
        ssp_switch_year = 2020
        ssp_transition_years = 0
    additional_forcing = st.slider('Additional forcing added on top (W/m²)', -4.0, 6.0, float(DEFAULT_MODEL_CONFIG.additional_forcing_wm2), 0.1, help=setting_tooltip('additional_forcing'))

    st.header("Radiative processes")
    water_vapor_height = st.slider('Water-vapour emission-height response (km per ln q)', 0.0, 1.8, float(DEFAULT_MODEL_CONFIG.water_vapor_emission_height_km_per_lnq), 0.02, help=setting_tooltip('water_vapor_height'))
    moist_lapse_weight = st.slider('Moist-adiabatic lapse-rate influence', 0.0, 1.0, float(DEFAULT_MODEL_CONFIG.moist_lapse_rate_weight), 0.02, help=setting_tooltip('moist_lapse_weight'))
    arctic_lapse_rate_feedback = st.slider('Unresolved Arctic inversion/lapse-rate feedback (W/m²/K)', 0.0, 1.8, float(DEFAULT_MODEL_CONFIG.arctic_lapse_rate_feedback_wm2_k), 0.05, help=setting_tooltip('arctic_lapse_rate_feedback_wm2_k'))
    low_cloud_loss = st.slider('Subtropical low-cloud loss per °C', 0.0, 0.025, float(DEFAULT_MODEL_CONFIG.low_cloud_loss_fraction_per_k), 0.0005, help=setting_tooltip('low_cloud_loss'))
    high_cloud_coupling = st.slider('High-cloud-top warming / surface warming', 0.0, 1.0, float(DEFAULT_MODEL_CONFIG.high_cloud_temperature_coupling), 0.02, help=setting_tooltip('high_cloud_coupling'))

    st.header("Cryosphere and ocean")
    sea_ice_albedo = st.slider('Sea-ice albedo', 0.3, 0.8, float(DEFAULT_MODEL_CONFIG.sea_ice_albedo), 0.01, help=setting_tooltip('sea_ice_albedo'))
    ice_transition_width = st.slider('Sea-ice transition width (°C)', 2.0, 12.0, float(DEFAULT_MODEL_CONFIG.sea_ice_transition_width_c), 0.5, help=setting_tooltip('ice_transition_width'))
    seasonal_arctic_enabled = st.checkbox('Enable prognostic seasonal Arctic atmosphere and sea ice', value=bool(DEFAULT_MODEL_CONFIG.seasonal_arctic_enabled), help=setting_tooltip('seasonal_arctic_enabled'))
    arctic_module_start_latitude = st.slider('Arctic module transition start latitude (°N)', 50.0, 64.0, float(DEFAULT_MODEL_CONFIG.arctic_module_start_latitude_deg), 0.5, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_module_start_latitude_deg'))
    arctic_reference_air_seasonal_amplitude = st.slider('Prescribed Arctic reference seasonal amplitude (°C)', 10.0, 22.0, float(DEFAULT_MODEL_CONFIG.arctic_reference_air_seasonal_amplitude_c), 0.5, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_reference_air_seasonal_amplitude_c'))
    arctic_moisture_transport = st.slider('Arctic moisture/latent heat convergence (W/m²/K global warming)', 0.0, 6.0, float(DEFAULT_MODEL_CONFIG.arctic_moisture_transport_wm2_per_k), 0.01, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_moisture_transport_wm2_per_k'))
    arctic_winter_transport_enhancement = st.slider('Cold-season Arctic transport enhancement (W/m²/K)', 0.0, 25.0, float(DEFAULT_MODEL_CONFIG.arctic_winter_transport_enhancement), 0.5, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_winter_transport_enhancement'))
    arctic_winter_transport_temperature_scale = st.slider('Cold-state transport temperature scale (°C)', 5.0, 30.0, float(DEFAULT_MODEL_CONFIG.arctic_winter_transport_temperature_scale_c), 0.5, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_winter_transport_temperature_scale_c'))
    arctic_dry_static_transport = st.slider('Arctic dry-static restoring (W/m²/K)', 0.0, 4.0, float(DEFAULT_MODEL_CONFIG.arctic_dry_static_transport_wm2_k), 0.05, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_dry_static_transport_wm2_k'))
    arctic_open_water_stable_exchange = st.slider('Stable open-water/air exchange (W/m²/K)', 0.0, 3.0, float(DEFAULT_MODEL_CONFIG.arctic_open_water_stable_exchange_wm2_k), 0.05, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_open_water_stable_exchange_wm2_k'))
    arctic_open_water_unstable_exchange = st.slider(
        'Unstable open-water/air exchange (W/m²/K)',
        min_value=max(float(arctic_open_water_stable_exchange), 1.0),
        max_value=15.0,
        value=max(
            float(DEFAULT_MODEL_CONFIG.arctic_open_water_unstable_exchange_wm2_k),
            max(float(arctic_open_water_stable_exchange), 1.0),
        ),
        step=0.1,
        disabled=not seasonal_arctic_enabled,
        help=setting_tooltip('arctic_open_water_unstable_exchange_wm2_k'),
    )
    arctic_open_water_exchange_transition = st.slider('Open-water stability transition (°C)', 0.05, 2.0, float(DEFAULT_MODEL_CONFIG.arctic_open_water_exchange_transition_c), 0.05, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_open_water_exchange_transition_c'))
    arctic_transient_shortwave_scale = st.slider('Transient sea-ice shortwave anomaly scale', 0.0, 1.0, float(DEFAULT_MODEL_CONFIG.arctic_transient_shortwave_scale), 0.05, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_transient_shortwave_scale'))
    arctic_interface_longwave_damping = st.slider('Net Arctic surface longwave damping (W/m²/K)', 0.0, 6.0, float(DEFAULT_MODEL_CONFIG.arctic_interface_longwave_damping_wm2_k), 0.1, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_interface_longwave_damping_wm2_k'))
    arctic_ice_surface_exchange = st.slider('Ice-surface/air exchange (W/m²/K)', 0.5, 10.0, float(DEFAULT_MODEL_CONFIG.arctic_ice_surface_exchange_wm2_k), 0.1, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_ice_surface_exchange_wm2_k'))
    arctic_basal_ocean_exchange = st.slider('Basal ice/ocean exchange (W/m²/K)', 5.0, 45.0, float(DEFAULT_MODEL_CONFIG.arctic_basal_ocean_exchange_wm2_k), 0.5, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_basal_ocean_exchange_wm2_k'))
    arctic_open_water_ocean_exchange = st.slider('Open-water/ocean exchange (W/m²/K)', 1.0, 45.0, float(DEFAULT_MODEL_CONFIG.arctic_open_water_ocean_exchange_wm2_k), 0.05, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_open_water_ocean_exchange_wm2_k'))
    arctic_lateral_ocean_heat_transport = st.slider('Signed lower-latitude ocean heat convergence per ice-fraction anomaly (W/m²)', 0.0, 40.0, float(DEFAULT_MODEL_CONFIG.arctic_lateral_ocean_heat_transport_wm2_per_ice_fraction), 0.5, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_lateral_ocean_heat_transport_wm2_per_ice_fraction'))
    arctic_forced_ocean_heat_convergence = st.slider('Warming-driven Arctic ocean heat convergence (W/m²/K)', 0.0, 8.0, float(DEFAULT_MODEL_CONFIG.arctic_forced_ocean_heat_convergence_wm2_per_k), 0.05, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_forced_ocean_heat_convergence_wm2_per_k'))
    arctic_forced_ocean_heat_convergence_onset = st.slider('Forced Arctic ocean convergence onset warming (°C)', 0.0, 3.0, float(DEFAULT_MODEL_CONFIG.arctic_forced_ocean_heat_convergence_onset_warming_c), 0.05, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_forced_ocean_heat_convergence_onset_warming_c'))
    arctic_forced_ocean_heat_convergence_saturation_scale = st.slider('Forced Arctic ocean convergence saturation scale (°C)', 0.10, 2.0, float(DEFAULT_MODEL_CONFIG.arctic_forced_ocean_heat_convergence_saturation_scale_c), 0.01, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_forced_ocean_heat_convergence_saturation_scale_c'))
    arctic_phase_restoring_deficit_saturation = st.slider('Depleted-pack phase-restoring saturation fraction', 0.01, 0.50, float(DEFAULT_MODEL_CONFIG.arctic_phase_restoring_deficit_saturation_fraction), 0.01, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_phase_restoring_deficit_saturation_fraction'))
    arctic_phase_restoring_max_deficit_flux = st.slider('Maximum depleted-pack restoring flux (W/m²)', 0.5, 6.0, float(DEFAULT_MODEL_CONFIG.arctic_phase_restoring_max_deficit_flux_wm2), 0.1, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_phase_restoring_max_deficit_flux_wm2'))
    arctic_new_ice_local_thickness = st.slider('New-ice local thickness scale (m)', 0.05, 0.30, float(DEFAULT_MODEL_CONFIG.arctic_new_ice_local_thickness_m), 0.01, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_new_ice_local_thickness_m'))
    arctic_full_cover_equivalent_thickness = st.slider('Full-cover equivalent thickness (m)', 2.5, 5.5, float(DEFAULT_MODEL_CONFIG.arctic_full_cover_equivalent_thickness_m), 0.05, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_full_cover_equivalent_thickness_m'))
    arctic_max_equivalent_thickness = st.number_input('Emergency grid-equivalent ice-energy abort threshold (m)', min_value=4.0, max_value=100.0, value=float(DEFAULT_MODEL_CONFIG.arctic_max_equivalent_thickness_m), step=1.0, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_max_equivalent_thickness_m'))
    arctic_max_local_ice_thickness = st.number_input('Emergency local ice-thickness abort threshold (m)', min_value=20.0, max_value=5000.0, value=float(DEFAULT_MODEL_CONFIG.arctic_max_local_ice_thickness_m), step=10.0, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_max_local_ice_thickness_m'))
    arctic_ice_concentration_exponent = st.slider('Reference compact-pack concentration exponent', 0.25, 2.5, float(DEFAULT_MODEL_CONFIG.arctic_ice_concentration_exponent), 0.05, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_ice_concentration_exponent'))
    arctic_ice_area_formation_temperature_scale = st.slider('New-ice formation temperature scale (°C)', 0.20, 1.20, float(DEFAULT_MODEL_CONFIG.arctic_ice_area_formation_temperature_scale_c), 0.05, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_ice_area_formation_temperature_scale_c'))
    arctic_ice_area_formation_volume_sensitivity = st.slider('Formation volume-support sensitivity', 0.0, 12.0, float(DEFAULT_MODEL_CONFIG.arctic_ice_area_formation_volume_sensitivity), 0.1, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_ice_area_formation_volume_sensitivity'))
    arctic_ice_area_formation_support_floor = st.slider('Minimum winter formation support', 0.0, 0.75, float(DEFAULT_MODEL_CONFIG.arctic_ice_area_formation_support_floor), 0.01, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_ice_area_formation_support_floor'))
    arctic_ice_area_melt_thickness = st.slider('Lateral-melt thickness scale (m)', 0.10, 1.20, float(DEFAULT_MODEL_CONFIG.arctic_ice_area_melt_thickness_m), 0.01, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_ice_area_melt_thickness_m'))
    arctic_ice_area_lateral_melt_efficiency = st.slider('Lateral-melt efficiency', 0.0, 1.0, float(DEFAULT_MODEL_CONFIG.arctic_ice_area_lateral_melt_efficiency), 0.01, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_ice_area_lateral_melt_efficiency'))
    arctic_ice_area_thinning_melt_amplification = st.slider('Thin-pack lateral-melt amplification', 0.0, 10.0, float(DEFAULT_MODEL_CONFIG.arctic_ice_area_thinning_melt_amplification), 0.1, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_ice_area_thinning_melt_amplification'))
    arctic_ice_area_thick_pack_resistance_exponent = st.slider('Thick-pack area-loss resistance exponent', 0.0, 8.0, float(DEFAULT_MODEL_CONFIG.arctic_ice_area_thick_pack_resistance_exponent), 0.1, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_ice_area_thick_pack_resistance_exponent'))
    arctic_ice_area_compaction_years = st.slider('Excess-area compaction timescale (years)', 0.05, 2.0, float(DEFAULT_MODEL_CONFIG.arctic_ice_area_compaction_years), 0.001, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_ice_area_compaction_years'))
    arctic_ice_area_ridging_threshold = st.slider('Ridging onset concentration', 0.70, 0.99, float(DEFAULT_MODEL_CONFIG.arctic_ice_area_ridging_threshold), 0.01, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_ice_area_ridging_threshold'))
    arctic_ice_area_ridging_rate = st.slider('Ridging area-reduction rate (/year)', 0.0, 0.30, float(DEFAULT_MODEL_CONFIG.arctic_ice_area_ridging_fraction_per_year), 0.01, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_ice_area_ridging_fraction_per_year'))
    arctic_ice_area_divergence_rate = st.slider('Lead-opening divergence rate (/year)', 0.0, 0.12, float(DEFAULT_MODEL_CONFIG.arctic_ice_area_divergence_fraction_per_year), 0.005, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_ice_area_divergence_fraction_per_year'))
    arctic_ice_area_thin_pack_divergence_rate = st.slider('Thin-pack deformation/divergence rate (/year)', 0.0, 1.5, float(DEFAULT_MODEL_CONFIG.arctic_ice_area_thin_pack_divergence_fraction_per_year), 0.01, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_ice_area_thin_pack_divergence_fraction_per_year'))
    arctic_greenland_marine_influence = st.slider('Greenland maritime Arctic influence', 0.0, 0.25, float(DEFAULT_MODEL_CONFIG.arctic_greenland_marine_influence), 0.01, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_greenland_marine_influence'))
    arctic_winter_lead_closure_fraction = st.slider('Optional cold-season mechanical lead closure fraction', 0.0, 1.0, float(DEFAULT_MODEL_CONFIG.arctic_winter_lead_closure_fraction), 0.01, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_winter_lead_closure_fraction'))
    arctic_winter_lead_closure_onset_fraction = st.slider('Winter lead-closure onset deficit', 0.0, 0.05, float(DEFAULT_MODEL_CONFIG.arctic_winter_lead_closure_onset_fraction), 0.001, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_winter_lead_closure_onset_fraction'))
    arctic_winter_lead_closure_temperature_scale = st.slider('Winter lead-closure temperature scale (°C)', 5.0, 30.0, float(DEFAULT_MODEL_CONFIG.arctic_winter_lead_closure_temperature_scale_c), 0.5, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_winter_lead_closure_temperature_scale_c'))
    arctic_atlantic_reference_ocean_temperature = st.slider('Atlantic Arctic reference-ocean temperature (°C)', -1.8, 3.0, float(DEFAULT_MODEL_CONFIG.arctic_atlantic_reference_ocean_temperature_c), 0.05, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_atlantic_reference_ocean_temperature_c'))
    arctic_non_atlantic_reference_ocean_temperature = st.slider('Central Arctic reference-ocean temperature (°C)', -1.8, 3.0, float(DEFAULT_MODEL_CONFIG.arctic_non_atlantic_reference_ocean_temperature_c), 0.05, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_non_atlantic_reference_ocean_temperature_c'))
    arctic_reference_ocean_heat_capacity = st.slider('Reference shallow-ocean heat capacity (W yr/m²/K)', 1.0, 20.0, float(DEFAULT_MODEL_CONFIG.arctic_reference_ocean_heat_capacity_wyr_m2_k), 0.5, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_reference_ocean_heat_capacity_wyr_m2_k'))
    arctic_reference_ocean_restoring = st.slider('Reference shallow-ocean restoring (W/m²/K)', 2.0, 25.0, float(DEFAULT_MODEL_CONFIG.arctic_reference_ocean_restoring_wm2_k), 0.5, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_reference_ocean_restoring_wm2_k'))
    arctic_air_memory_years = st.slider('Arctic SAT diagnostic memory (years)', 0.05, 1.0, float(DEFAULT_MODEL_CONFIG.arctic_air_low_pass_years), 0.05, disabled=not seasonal_arctic_enabled, help=setting_tooltip('arctic_air_low_pass_years'))
    ocean_exchange = st.slider('Surface-to-deep ocean exchange (W/m²/K)', 0.1, 2.0, float(DEFAULT_MODEL_CONFIG.ocean_heat_exchange_wm2_k), 0.02, help=setting_tooltip('ocean_exchange'))
    meridional_diffusion = st.slider('Meridional heat diffusion (W/m²/K)', 0.0, 1.5, float(DEFAULT_MODEL_CONFIG.meridional_diffusion_wm2_k), 0.02, help=setting_tooltip('meridional_diffusion'))

    st.header("AMOC and freshwater")
    hosing = st.slider('Added North Atlantic freshwater (Sv)', 0.0, 1.0, float(DEFAULT_MODEL_CONFIG.freshwater_hosing_sv), 0.01, help=setting_tooltip('hosing'))
    hydrological_freshwater = st.slider('Hydrological-cycle freshwater increase (Sv/°C)', 0.0, 0.012, float(DEFAULT_MODEL_CONFIG.hydrological_freshwater_sv_per_k), 0.0005, help=setting_tooltip('hydrological_freshwater'))
    hydrological_north_fraction = st.slider('Hydrological freshwater share entering North Atlantic', 0.0, 1.0, float(DEFAULT_MODEL_CONFIG.hydrological_freshwater_north_fraction), 0.05, help=setting_tooltip('hydrological_north_fraction'))
    greenland_freshwater = st.slider('Greenland freshwater sensitivity (Sv/°C)', 0.0, 0.010, float(DEFAULT_MODEL_CONFIG.greenland_freshwater_sv_per_k), 0.0005, help=setting_tooltip('greenland_freshwater'))
    greenland_threshold = st.slider('Greenland freshwater warming threshold (°C)', 0.0, 3.0, float(DEFAULT_MODEL_CONFIG.greenland_freshwater_threshold_c), 0.1, help=setting_tooltip('greenland_threshold'))
    greenland_response_years = st.slider('Greenland freshwater response time (years)', 1.0, 200.0, float(DEFAULT_MODEL_CONFIG.greenland_freshwater_adjustment_years), 1.0, help=setting_tooltip('greenland_response_years'))
    greenland_initial_ice_mass_gt = st.number_input('Initial Greenland ice reservoir (Gt)', 1.0e5, 5.0e6, float(DEFAULT_MODEL_CONFIG.greenland_initial_ice_mass_gt), 5.0e4, help=setting_tooltip('greenland_initial_ice_mass_gt'))
    greenland_depletion_exponent = st.slider('Greenland depletion exponent', 0.0, 3.0, float(DEFAULT_MODEL_CONFIG.greenland_depletion_exponent), 0.1, help=setting_tooltip('greenland_depletion_exponent'))
    greenland_max_freshwater_sv = st.slider('Maximum Greenland freshwater flux (Sv)', 0.005, 0.10, float(DEFAULT_MODEL_CONFIG.greenland_max_freshwater_sv), 0.005, help=setting_tooltip('greenland_max_freshwater_sv'))
    greenland_smb_enabled = st.checkbox('Enable reduced Greenland surface mass balance', value=bool(DEFAULT_MODEL_CONFIG.greenland_surface_mass_balance_enabled), help=setting_tooltip('greenland_surface_mass_balance_enabled'))
    greenland_dynamic_discharge_fraction = st.slider('Greenland slow dynamic-discharge share', 0.0, 1.0, float(DEFAULT_MODEL_CONFIG.greenland_dynamic_discharge_fraction), 0.05, disabled=not greenland_smb_enabled, help=setting_tooltip('greenland_dynamic_discharge_fraction'))
    greenland_pdd_melt_factor = st.slider('Greenland PDD melt factor (Gt/degree-day)', 0.0, 1.5, float(DEFAULT_MODEL_CONFIG.greenland_pdd_melt_factor_gt_per_degree_day), 0.05, disabled=not greenland_smb_enabled, help=setting_tooltip('greenland_pdd_melt_factor_gt_per_degree_day'))
    greenland_meltwater_retention_fraction = st.slider('Greenland meltwater retention fraction', 0.0, 1.0, float(DEFAULT_MODEL_CONFIG.greenland_meltwater_retention_fraction), 0.05, disabled=not greenland_smb_enabled, help=setting_tooltip('greenland_meltwater_retention_fraction'))
    freshwater_start_fraction = st.slider('Hosing start position in run', 0.0, 1.0, float(DEFAULT_MODEL_CONFIG.freshwater_start_fraction), 0.05, help=setting_tooltip('freshwater_start_fraction'))
    freshwater_ramp_years = st.slider('Hosing ramp duration (years)', 0.0, 150.0, float(DEFAULT_MODEL_CONFIG.freshwater_ramp_years), 5.0, help=setting_tooltip('freshwater_ramp_years'))
    temperature_density_coupling = st.slider('Anomalous surface-temperature coupling to sinking density', 0.0, 1.0, float(DEFAULT_MODEL_CONFIG.amoc_temperature_density_coupling), 0.01, help=setting_tooltip('temperature_density_coupling', extra_note="v2.29.6 restores full anomalous thermal-density coupling; freshwater coefficients remain unchanged."))
    freshwater_compensation_label = st.selectbox('Freshwater compensation location', ['External global-ocean reservoir', 'Tropical and Southern Atlantic'], index=0, help=setting_tooltip('freshwater_compensation_label', extra_note='External compensation conserves global salt without directly salinifying the Atlantic source waters feeding the AMOC.'))
    freshwater_compensation_mode = (
        "external"
        if freshwater_compensation_label == "External global-ocean reservoir"
        else "atlantic"
    )
    amoc_heat_transport = st.slider('Overturning heat transport (PW/Sv)', 0.0, 0.1, float(DEFAULT_MODEL_CONFIG.amoc_heat_transport_pw_per_sv), 0.005, help=setting_tooltip('amoc_heat_transport'))
    amoc_surface_heat_coupling = st.slider('Surface AMOC heat coupling fraction', 0.0, 1.0, float(DEFAULT_MODEL_CONFIG.amoc_surface_heat_coupling_fraction), 0.025, help=setting_tooltip('amoc_surface_heat_coupling', extra_note='Fraction of the diagnosed overturning heat-transport anomaly applied to the prognostic surface mixed layer.'))
    amoc_heat_response_damping = st.slider('AMOC regional temperature damping (W/m2/K)', 0.25, 4.0, float(DEFAULT_MODEL_CONFIG.amoc_heat_response_damping_wm2_k), 0.05, help=setting_tooltip('amoc_heat_response_damping'))
    atlantic_gyre_heat_transport = float(DEFAULT_MODEL_CONFIG.atlantic_gyre_heat_transport_pw)
    initial_fovs = st.slider('Initial FovS at 34.5 S (Sv)', -0.5, 0.2, float(DEFAULT_MODEL_CONFIG.initial_fovs_sv), 0.01, help=setting_tooltip('initial_fovs', extra_note='Negative values mean the overturning imports salinity into the Atlantic. The South Atlantic upper-limb salinity is derived from this target rather than from the Southern Ocean surface box.'))

    st.subheader("AMOC hysteresis")
    run_hysteresis = st.checkbox('Run equilibrium AMOC continuation', value=False, help=setting_tooltip('run_hysteresis', extra_note='Solves and stability-tests all discoverable preindustrial AMOC equilibria at each freshwater level.'))
    hysteresis_max_hosing = st.slider('Maximum equilibrium hosing (Sv)', 0.2, 1.5, 0.7, 0.05, disabled=not run_hysteresis, help=setting_tooltip('hysteresis_max_hosing'))
    hysteresis_step = st.select_slider('Equilibrium forcing step (Sv)', options=[0.025, 0.05, 0.1], value=0.05, disabled=not run_hysteresis, help=setting_tooltip('hysteresis_step'))
    hysteresis_years_per_step = 80.0
    hysteresis_spinup_years = 200.0
    if run_hysteresis:
        st.caption(
            "This is an equilibrium root-and-stability calculation. Fixed years-per-step "
            "and spin-up settings are no longer used."
        )

    with st.expander("Numerics and advanced controls"):
        dt_years = st.select_slider('Time step (years)', options=[0.025, 0.05, 0.1], value=0.05, help=setting_tooltip('dt_years'))
        equilibrium_years = st.select_slider('ECS equilibrium diagnostic length (years)', options=[400, 600, 800, 1200, 1600], value=1200, help=setting_tooltip('equilibrium_years'))
        land_capacity = st.slider('Land heat capacity (W yr/m²/K)', 0.8, 4.0, float(DEFAULT_MODEL_CONFIG.land_heat_capacity_wyr_m2_k), 0.1, help=setting_tooltip('land_capacity'))
        ocean_capacity = st.slider('Mixed-layer ocean heat capacity (W yr/m²/K)', 3.0, 20.0, float(DEFAULT_MODEL_CONFIG.ocean_mixed_layer_heat_capacity_wyr_m2_k), 0.2, help=setting_tooltip('ocean_capacity'))
        deep_capacity = st.slider('Deep-ocean heat capacity (W yr/m²/K)', 40.0, 250.0, float(DEFAULT_MODEL_CONFIG.deep_ocean_heat_capacity_wyr_m2_k), 5.0, help=setting_tooltip('deep_capacity'))
        co2_erf = st.slider('ERF for doubled CO₂ (W/m²)', 3.0, 5.0, float(DEFAULT_MODEL_CONFIG.co2_doubling_erf_wm2), 0.05, help=setting_tooltip('co2_erf'))
        co2_forcing_formula_label = st.selectbox(
            'CO₂ forcing formulation',
            ['Logarithmic', 'Meinshausen et al. (2020)'],
            index=(0 if DEFAULT_MODEL_CONFIG.co2_forcing_formula == 'logarithmic' else 1),
            help=setting_tooltip('co2_forcing_formula'),
        )
        co2_forcing_formula = (
            'logarithmic'
            if co2_forcing_formula_label == 'Logarithmic'
            else 'meinshausen2020'
        )
        co2_forcing_reference_n2o = st.number_input(
            'Reference N₂O for CO₂ forcing overlap (ppb)',
            min_value=100.0,
            max_value=1000.0,
            value=float(DEFAULT_MODEL_CONFIG.co2_forcing_reference_n2o_ppb),
            step=1.0,
            disabled=co2_forcing_formula != 'meinshausen2020',
            help=setting_tooltip('co2_forcing_reference_n2o_ppb'),
        )
        amoc_adjustment = st.slider('AMOC hydraulic adjustment time (years)', 1.0, 30.0, float(DEFAULT_MODEL_CONFIG.amoc_adjustment_years), 1.0, help=setting_tooltip('amoc_adjustment'))
        pycnocline_depth = st.slider('Initial Atlantic pycnocline depth (m)', 300.0, 1500.0, float(DEFAULT_MODEL_CONFIG.amoc_initial_pycnocline_depth_m), 25.0, help=setting_tooltip('pycnocline_depth'))
        ekman_inflow = st.slider('Southern Ocean Ekman inflow (Sv)', 5.0, 45.0, float(DEFAULT_MODEL_CONFIG.amoc_ekman_inflow_sv), 1.0, help=setting_tooltip('ekman_inflow'))
        upwelling = st.slider('Reference low-latitude upwelling (Sv)', 0.0, 15.0, float(DEFAULT_MODEL_CONFIG.amoc_upwelling_reference_sv), 0.5, help=setting_tooltip('upwelling'))
        eddy_outflow = st.slider('Reference Southern Ocean eddy outflow (Sv)', 0.0, 30.0, float(DEFAULT_MODEL_CONFIG.amoc_eddy_outflow_reference_sv), 0.5, help=setting_tooltip('eddy_outflow'))
        north_gyre = st.slider('Northern gyre salt exchange (Sv)', 0.0, 20.0, float(DEFAULT_MODEL_CONFIG.amoc_north_tropical_gyre_sv), 0.5, help=setting_tooltip('north_gyre'))
        southern_gyre = st.slider('Southern gyre salt exchange (Sv)', 0.0, 25.0, float(DEFAULT_MODEL_CONFIG.amoc_tropical_southern_gyre_sv), 0.5, help=setting_tooltip('southern_gyre'))
        southern_external_exchange = st.slider(
            'Southern Ocean–external anomaly exchange (Sv)',
            0.0,
            15.0,
            float(DEFAULT_MODEL_CONFIG.amoc_southern_external_exchange_sv),
            0.5,
            help=setting_tooltip('amoc_southern_external_exchange_sv'),
        )
        south_atlantic_external_exchange = st.slider(
            'South Atlantic–external anomaly exchange (Sv)',
            0.0,
            10.0,
            float(DEFAULT_MODEL_CONFIG.amoc_south_atlantic_external_exchange_sv),
            0.5,
            help=setting_tooltip('amoc_south_atlantic_external_exchange_sv'),
        )
        amoc_southern_ocean_structure_label = st.selectbox(
            'Southern Ocean overturning structure',
            ['Fixed', 'Warming-sensitive'],
            index=0,
            help=setting_tooltip('amoc_southern_ocean_structure'),
        )
        amoc_southern_ocean_structure = (
            'fixed'
            if amoc_southern_ocean_structure_label == 'Fixed'
            else 'warming_sensitive'
        )
        amoc_southern_wind_sensitivity = st.slider(
            'Southern Ocean wind response per °C',
            0.0,
            0.20,
            float(DEFAULT_MODEL_CONFIG.amoc_southern_wind_sensitivity_per_k),
            0.01,
            disabled=amoc_southern_ocean_structure != 'warming_sensitive',
            help=setting_tooltip('amoc_southern_wind_sensitivity_per_k'),
        )
        amoc_southern_upwelling_sensitivity = st.slider(
            'Southern Ocean upwelling response per °C',
            0.0,
            0.20,
            float(DEFAULT_MODEL_CONFIG.amoc_southern_upwelling_sensitivity_per_k),
            0.01,
            disabled=amoc_southern_ocean_structure != 'warming_sensitive',
            help=setting_tooltip('amoc_southern_upwelling_sensitivity_per_k'),
        )
        amoc_southern_response_min = st.slider(
            'Minimum Southern Ocean response multiplier',
            0.10,
            1.00,
            float(DEFAULT_MODEL_CONFIG.amoc_southern_response_min_multiplier),
            0.05,
            disabled=amoc_southern_ocean_structure != 'warming_sensitive',
            help=setting_tooltip('amoc_southern_response_min_multiplier'),
        )
        amoc_southern_response_max = st.slider(
            'Maximum Southern Ocean response multiplier',
            1.00,
            3.00,
            float(DEFAULT_MODEL_CONFIG.amoc_southern_response_max_multiplier),
            0.05,
            disabled=amoc_southern_ocean_structure != 'warming_sensitive',
            help=setting_tooltip('amoc_southern_response_max_multiplier'),
        )
        amoc_indo_pacific_mode_label = st.selectbox(
            'Indo-Pacific overturning compensation',
            ['None', 'Diagnostic only', 'Interactive'],
            index=0,
            help=setting_tooltip('amoc_indo_pacific_compensation_mode'),
        )
        amoc_indo_pacific_compensation_mode = {
            'None': 'none',
            'Diagnostic only': 'diagnostic',
            'Interactive': 'interactive',
        }[amoc_indo_pacific_mode_label]
        amoc_indo_pacific_compensation_fraction = st.slider(
            'Indo-Pacific compensation fraction',
            0.0,
            1.0,
            float(DEFAULT_MODEL_CONFIG.amoc_indo_pacific_compensation_fraction),
            0.05,
            disabled=amoc_indo_pacific_compensation_mode == 'none',
            help=setting_tooltip('amoc_indo_pacific_compensation_fraction'),
        )
        amoc_indo_pacific_compensation_max = st.slider(
            'Maximum Indo-Pacific compensation (Sv)',
            0.0,
            30.0,
            float(DEFAULT_MODEL_CONFIG.amoc_indo_pacific_compensation_max_sv),
            0.5,
            disabled=amoc_indo_pacific_compensation_mode == 'none',
            help=setting_tooltip('amoc_indo_pacific_compensation_max_sv'),
        )
        fovs_reference_salinity = st.slider('FovS reference salinity S0 (PSU)', 34.0, 36.0, float(DEFAULT_MODEL_CONFIG.fovs_reference_salinity_psu), 0.05, help=setting_tooltip('fovs_reference_salinity'))
        density_exponent = st.slider('AMOC density-response exponent', 0.5, 3.0, float(DEFAULT_MODEL_CONFIG.amoc_density_transport_exponent), 0.05, help=setting_tooltip('density_exponent'))
        depth_exponent = st.slider('Hydraulic pycnocline-depth exponent', 0.0, 2.5, float(DEFAULT_MODEL_CONFIG.amoc_hydraulic_depth_exponent), 0.05, help=setting_tooltip('depth_exponent'))
        pycnocline_feedback_strength = st.slider('Pycnocline AMOC feedback strength', 0.0, 1.0, float(DEFAULT_MODEL_CONFIG.amoc_pycnocline_feedback_strength), 0.05, help=setting_tooltip('pycnocline_feedback_strength'))
        convection_density_scale_factor = st.slider('Convection density normalization scale', 1.0, 6.0, float(DEFAULT_MODEL_CONFIG.amoc_convection_density_scale_factor), 0.01, help=setting_tooltip('convection_density_scale_factor'))
        convection_minimum_fraction = st.slider('Residual deep-convection fraction', 0.0, 0.7, float(DEFAULT_MODEL_CONFIG.amoc_convection_minimum_fraction), 0.01, help=setting_tooltip('convection_minimum_fraction'))
        convective_mixing_reference = st.slider('Convective salt exchange (Sv)', 0.0, 15.0, float(DEFAULT_MODEL_CONFIG.amoc_convective_mixing_reference_sv), 0.5, help=setting_tooltip('convective_mixing_reference'))
        convective_mixing_exponent = st.slider('Convective mixing exponent', 0.5, 5.0, float(DEFAULT_MODEL_CONFIG.amoc_convective_mixing_exponent), 0.1, help=setting_tooltip('convective_mixing_exponent'))
        convection_entrainment_feedback = st.slider('Convective entrainment feedback', 0.0, 0.35, float(DEFAULT_MODEL_CONFIG.amoc_convection_entrainment_feedback), 0.01, help=setting_tooltip('convection_entrainment_feedback'))
        convection_adjustment_years = st.slider('Convection weakening adjustment (years)', 1.0, 80.0, float(DEFAULT_MODEL_CONFIG.amoc_convection_adjustment_years), 1.0, help=setting_tooltip('convection_adjustment_years'))
        convection_recovery_years = st.slider('Convection recovery adjustment (years)', 10.0, 300.0, float(DEFAULT_MODEL_CONFIG.amoc_convection_recovery_years), 10.0, help=setting_tooltip('convection_recovery_years'))
        eddy_depth_exponent = st.slider('Eddy-outflow depth exponent', 0.5, 3.5, float(DEFAULT_MODEL_CONFIG.amoc_eddy_depth_exponent), 0.05, help=setting_tooltip('eddy_depth_exponent'))
        amoc_reference_density_driver = st.number_input('Reference absolute AMOC density driver', 1.0e-5, 5.0e-3, float(DEFAULT_MODEL_CONFIG.amoc_reference_density_driver), 1.0e-5, format='%.6f', help=setting_tooltip('amoc_reference_density_driver'))
        amoc_minimum_initial_density_ratio = st.slider('Minimum initial density-margin ratio', 0.2, 0.99, float(DEFAULT_MODEL_CONFIG.amoc_minimum_initial_density_ratio), 0.01, help=setting_tooltip('amoc_minimum_initial_density_ratio'))
        amoc_maximum_initial_density_ratio = st.slider('Maximum initial density-margin ratio', 1.01, 2.0, float(DEFAULT_MODEL_CONFIG.amoc_maximum_initial_density_ratio), 0.01, help=setting_tooltip('amoc_maximum_initial_density_ratio'))
        amoc_enforce_initial_density_constraint = st.checkbox('Enforce absolute initial density-margin constraint', value=bool(DEFAULT_MODEL_CONFIG.amoc_enforce_initial_density_constraint), help=setting_tooltip('amoc_enforce_initial_density_constraint'))
        amoc_allow_reversal = st.checkbox('Allow exploratory negative AMOC reversal', value=bool(DEFAULT_MODEL_CONFIG.amoc_allow_reversal), help=setting_tooltip('amoc_allow_reversal'))
        amoc_coupling_scheme = st.selectbox('Coupled AMOC integration scheme', ['euler', 'heun'], index=0, help=setting_tooltip('amoc_coupling_scheme'))

scenario = scenario_lookup[scenario_label]
config = ModelConfig(
    start_year=float(start_year),
    duration_years=float(duration_years),
    dt_years=float(dt_years),
    scenario=scenario,
    co2_start_ppm=float(co2_start),
    co2_peak_ppm=float(co2_peak),
    co2_end_ppm=float(co2_end),
    one_percent_cap_ppm=(float(one_percent_cap) if cap_one_percent else None),
    co2_growth_rate_percent_per_year=float(co2_growth_rate_percent),
    co2_growth_cap_ppm=float(co2_growth_cap),
    co2_hold_years=float(co2_hold_years),
    peak_time_fraction=float(peak_fraction),
    additional_forcing_wm2=float(additional_forcing),
    forcing_mode=forcing_mode_lookup[forcing_mode_label],
    ssp_before=ssp_label_lookup[ssp_before_label],
    ssp_after=ssp_label_lookup[ssp_after_label],
    ssp_switch_year=float(ssp_switch_year),
    ssp_transition_years=float(ssp_transition_years),
    co2_doubling_erf_wm2=float(co2_erf),
    co2_forcing_formula=str(co2_forcing_formula),
    co2_forcing_reference_n2o_ppb=float(co2_forcing_reference_n2o),
    water_vapor_emission_height_km_per_lnq=float(water_vapor_height),
    moist_lapse_rate_weight=float(moist_lapse_weight),
    arctic_lapse_rate_feedback_wm2_k=float(arctic_lapse_rate_feedback),
    seasonal_arctic_enabled=bool(seasonal_arctic_enabled),
    arctic_module_start_latitude_deg=float(arctic_module_start_latitude),
    arctic_reference_air_seasonal_amplitude_c=float(arctic_reference_air_seasonal_amplitude),
    arctic_moisture_transport_wm2_per_k=float(arctic_moisture_transport),
    arctic_winter_transport_enhancement=float(arctic_winter_transport_enhancement),
    arctic_winter_transport_temperature_scale_c=float(arctic_winter_transport_temperature_scale),
    arctic_dry_static_transport_wm2_k=float(arctic_dry_static_transport),
    arctic_open_water_stable_exchange_wm2_k=float(arctic_open_water_stable_exchange),
    arctic_open_water_unstable_exchange_wm2_k=float(arctic_open_water_unstable_exchange),
    arctic_open_water_exchange_transition_c=float(arctic_open_water_exchange_transition),
    arctic_transient_shortwave_scale=float(arctic_transient_shortwave_scale),
    arctic_interface_longwave_damping_wm2_k=float(arctic_interface_longwave_damping),
    arctic_ice_surface_exchange_wm2_k=float(arctic_ice_surface_exchange),
    arctic_basal_ocean_exchange_wm2_k=float(arctic_basal_ocean_exchange),
    arctic_open_water_ocean_exchange_wm2_k=float(arctic_open_water_ocean_exchange),
    arctic_lateral_ocean_heat_transport_wm2_per_ice_fraction=float(arctic_lateral_ocean_heat_transport),
    arctic_forced_ocean_heat_convergence_wm2_per_k=float(arctic_forced_ocean_heat_convergence),
    arctic_forced_ocean_heat_convergence_onset_warming_c=float(arctic_forced_ocean_heat_convergence_onset),
    arctic_forced_ocean_heat_convergence_saturation_scale_c=float(arctic_forced_ocean_heat_convergence_saturation_scale),
    arctic_phase_restoring_deficit_saturation_fraction=float(arctic_phase_restoring_deficit_saturation),
    arctic_phase_restoring_max_deficit_flux_wm2=float(arctic_phase_restoring_max_deficit_flux),
    arctic_new_ice_local_thickness_m=float(arctic_new_ice_local_thickness),
    arctic_full_cover_equivalent_thickness_m=float(arctic_full_cover_equivalent_thickness),
    arctic_max_equivalent_thickness_m=float(arctic_max_equivalent_thickness),
    arctic_max_local_ice_thickness_m=float(arctic_max_local_ice_thickness),
    arctic_ice_concentration_exponent=float(arctic_ice_concentration_exponent),
    arctic_ice_area_formation_temperature_scale_c=float(arctic_ice_area_formation_temperature_scale),
    arctic_ice_area_formation_volume_sensitivity=float(arctic_ice_area_formation_volume_sensitivity),
    arctic_ice_area_formation_support_floor=float(arctic_ice_area_formation_support_floor),
    arctic_ice_area_melt_thickness_m=float(arctic_ice_area_melt_thickness),
    arctic_ice_area_lateral_melt_efficiency=float(arctic_ice_area_lateral_melt_efficiency),
    arctic_ice_area_thinning_melt_amplification=float(arctic_ice_area_thinning_melt_amplification),
    arctic_ice_area_thick_pack_resistance_exponent=float(arctic_ice_area_thick_pack_resistance_exponent),
    arctic_ice_area_compaction_years=float(arctic_ice_area_compaction_years),
    arctic_ice_area_ridging_threshold=float(arctic_ice_area_ridging_threshold),
    arctic_ice_area_ridging_fraction_per_year=float(arctic_ice_area_ridging_rate),
    arctic_ice_area_divergence_fraction_per_year=float(arctic_ice_area_divergence_rate),
    arctic_ice_area_thin_pack_divergence_fraction_per_year=float(arctic_ice_area_thin_pack_divergence_rate),
    arctic_greenland_marine_influence=float(arctic_greenland_marine_influence),
    arctic_winter_lead_closure_fraction=float(arctic_winter_lead_closure_fraction),
    arctic_winter_lead_closure_onset_fraction=float(arctic_winter_lead_closure_onset_fraction),
    arctic_winter_lead_closure_temperature_scale_c=float(arctic_winter_lead_closure_temperature_scale),
    arctic_atlantic_reference_ocean_temperature_c=float(arctic_atlantic_reference_ocean_temperature),
    arctic_non_atlantic_reference_ocean_temperature_c=float(arctic_non_atlantic_reference_ocean_temperature),
    arctic_reference_ocean_heat_capacity_wyr_m2_k=float(arctic_reference_ocean_heat_capacity),
    arctic_reference_ocean_restoring_wm2_k=float(arctic_reference_ocean_restoring),
    arctic_air_low_pass_years=float(arctic_air_memory_years),
    low_cloud_loss_fraction_per_k=float(low_cloud_loss),
    high_cloud_temperature_coupling=float(high_cloud_coupling),
    sea_ice_albedo=float(sea_ice_albedo),
    sea_ice_transition_width_c=float(ice_transition_width),
    ocean_heat_exchange_wm2_k=float(ocean_exchange),
    meridional_diffusion_wm2_k=float(meridional_diffusion),
    freshwater_hosing_sv=float(hosing),
    warming_freshwater_sv_per_k=None,
    hydrological_freshwater_sv_per_k=float(hydrological_freshwater),
    hydrological_freshwater_north_fraction=float(hydrological_north_fraction),
    greenland_freshwater_sv_per_k=float(greenland_freshwater),
    greenland_freshwater_threshold_c=float(greenland_threshold),
    greenland_freshwater_adjustment_years=float(greenland_response_years),
    greenland_initial_ice_mass_gt=float(greenland_initial_ice_mass_gt),
    greenland_depletion_exponent=float(greenland_depletion_exponent),
    greenland_max_freshwater_sv=float(greenland_max_freshwater_sv),
    greenland_surface_mass_balance_enabled=bool(greenland_smb_enabled),
    greenland_dynamic_discharge_fraction=float(greenland_dynamic_discharge_fraction),
    greenland_pdd_melt_factor_gt_per_degree_day=float(greenland_pdd_melt_factor),
    greenland_meltwater_retention_fraction=float(greenland_meltwater_retention_fraction),
    auto_initialize_from_1850=bool(auto_initialize_from_1850),
    freshwater_start_fraction=float(freshwater_start_fraction),
    freshwater_ramp_years=float(freshwater_ramp_years),
    freshwater_compensation_mode=freshwater_compensation_mode,
    amoc_temperature_density_coupling=float(temperature_density_coupling),
    amoc_heat_transport_pw_per_sv=float(amoc_heat_transport),
    amoc_surface_heat_coupling_fraction=float(amoc_surface_heat_coupling),
    amoc_heat_response_damping_wm2_k=float(amoc_heat_response_damping),
    atlantic_gyre_heat_transport_pw=float(atlantic_gyre_heat_transport),
    amoc_adjustment_years=float(amoc_adjustment),
    amoc_density_transport_exponent=float(density_exponent),
    amoc_hydraulic_depth_exponent=float(depth_exponent),
    amoc_pycnocline_feedback_strength=float(pycnocline_feedback_strength),
    amoc_convection_density_scale_factor=float(convection_density_scale_factor),
    amoc_convection_minimum_fraction=float(convection_minimum_fraction),
    amoc_convective_mixing_reference_sv=float(convective_mixing_reference),
    amoc_convective_mixing_exponent=float(convective_mixing_exponent),
    amoc_convection_entrainment_feedback=float(
        convection_entrainment_feedback
    ),
    amoc_convection_adjustment_years=float(convection_adjustment_years),
    amoc_convection_recovery_years=float(convection_recovery_years),
    amoc_eddy_depth_exponent=float(eddy_depth_exponent),
    amoc_reference_density_driver=float(amoc_reference_density_driver),
    amoc_minimum_initial_density_ratio=float(amoc_minimum_initial_density_ratio),
    amoc_maximum_initial_density_ratio=float(amoc_maximum_initial_density_ratio),
    amoc_enforce_initial_density_constraint=bool(amoc_enforce_initial_density_constraint),
    amoc_allow_reversal=bool(amoc_allow_reversal),
    amoc_coupling_scheme=str(amoc_coupling_scheme),
    amoc_initial_pycnocline_depth_m=float(pycnocline_depth),
    amoc_ekman_inflow_sv=float(ekman_inflow),
    amoc_upwelling_reference_sv=float(upwelling),
    amoc_eddy_outflow_reference_sv=float(eddy_outflow),
    amoc_north_tropical_gyre_sv=float(north_gyre),
    amoc_tropical_southern_gyre_sv=float(southern_gyre),
    amoc_southern_external_exchange_sv=float(southern_external_exchange),
    amoc_south_atlantic_external_exchange_sv=float(
        south_atlantic_external_exchange
    ),
    amoc_southern_ocean_structure=str(amoc_southern_ocean_structure),
    amoc_southern_wind_sensitivity_per_k=float(amoc_southern_wind_sensitivity),
    amoc_southern_upwelling_sensitivity_per_k=float(
        amoc_southern_upwelling_sensitivity
    ),
    amoc_southern_response_min_multiplier=float(amoc_southern_response_min),
    amoc_southern_response_max_multiplier=float(amoc_southern_response_max),
    amoc_indo_pacific_compensation_mode=str(
        amoc_indo_pacific_compensation_mode
    ),
    amoc_indo_pacific_compensation_fraction=float(
        amoc_indo_pacific_compensation_fraction
    ),
    amoc_indo_pacific_compensation_max_sv=float(
        amoc_indo_pacific_compensation_max
    ),
    initial_fovs_sv=float(initial_fovs),
    fovs_reference_salinity_psu=float(fovs_reference_salinity),
    land_heat_capacity_wyr_m2_k=float(land_capacity),
    ocean_mixed_layer_heat_capacity_wyr_m2_k=float(ocean_capacity),
    deep_ocean_heat_capacity_wyr_m2_k=float(deep_capacity),
)

try:
    with st.spinner("Running climate and AMOC experiments..."):
        result = run_cached(
            json.dumps(asdict(config), sort_keys=True),
            float(equilibrium_years),
            bool(run_hysteresis),
            float(hysteresis_max_hosing),
            float(hysteresis_step),
            float(hysteresis_years_per_step),
            float(hysteresis_spinup_years),
        )
except (ValueError, FloatingPointError, RuntimeError) as exc:
    st.error(str(exc))
    st.stop()

summary = result.summary()
diagnostics = result.diagnostics
if diagnostics is None:
    st.error("Sensitivity diagnostics were not produced.")
    st.stop()

df = result.dataframe
comparison_detail = None
comparison_summary = None
comparison_png = None
if scenario == "percent_ramp_hold":
    try:
        comparison_detail, comparison_summary, comparison_png = run_percent_comparison_cached(
            json.dumps(asdict(config), sort_keys=True),
            str(percent_ramp_compare_rates),
        )
    except (ValueError, FloatingPointError, RuntimeError) as exc:
        st.warning(f"Comparison plot could not be created: {exc}")
metric_columns = st.columns(7)
metric_columns[0].metric("Equilibrium ECS", f"{diagnostics.equilibrium_ecs_c:.2f} °C")
metric_columns[1].metric("Gregory ECS", f"{diagnostics.gregory_effective_ecs_c:.2f} °C")
metric_columns[2].metric("TCR", f"{diagnostics.tcr_c:.2f} °C")
metric_columns[3].metric("Final warming", f"{summary['final_global_warming_c']:.2f} °C")
metric_columns[4].metric(
    "Final AMOC",
    f"{summary['final_amoc_sv']:.2f} Sv",
    f"{summary['final_amoc_change_percent']:.1f}%",
)
metric_columns[5].metric("Final FovS", f"{summary['final_fovs_sv']:.3f} Sv")
metric_columns[6].metric("Salt error", f"{summary['maximum_absolute_salt_conservation_error_ppm']:.2e} ppm")

if summary["amoc_collapsed"]:
    st.error(
        f"The final AMOC is below the configured collapse threshold of "
        f"{config.amoc_collapse_threshold_sv:g} Sv."
    )
else:
    st.info(
        "AMOC salinity is conserved across the five active Atlantic boxes plus an "
        "external compensation reservoir. Positive transport follows "
        "Southern surface → Tropical surface → Northern sinking → Deep → Southern surface; "
        "negative transport reverses the salt pathway."
    )

experiment_tab, sensitivity_tab, maps_tab, amoc_tab, hysteresis_tab, download_tab = st.tabs(
    [
        "Transient experiment",
        "Emergent sensitivity",
        "Maps",
        "AMOC diagnostics",
        "AMOC hysteresis",
        "Downloads",
    ]
)

with experiment_tab:
    left, right = st.columns(2)
    with left:
        chart = df.set_index("year")[[
            "global_bulk_surface_warming_c",
            "global_near_surface_air_warming_c",
            "arctic_near_surface_air_warming_c",
            "arctic_bulk_surface_warming_c",
            "deep_ocean_warming_c",
        ]]
        chart.columns = [
            "Global bulk surface",
            "Global near-surface air",
            "Arctic near-surface air",
            "Arctic bulk surface",
            "Deep ocean",
        ]
        st.line_chart(chart, x_label="Year", y_label="Temperature anomaly (°C)")
    with right:
        chart = df.set_index("year")[["amoc_sv", "amoc_hydraulic_target_sv"]].copy()
        chart.columns = ["AMOC", "Hydraulic density target"]
        chart["6 Sv reference"] = AMOC_SIX_SV_REFERENCE
        st.line_chart(chart, x_label="Year", y_label="Transport (Sv)")

    if comparison_png is not None and comparison_summary is not None:
        st.subheader("Percent-ramp comparison")
        st.image(comparison_png, width="stretch")
        st.dataframe(comparison_summary, hide_index=True, width="stretch")
        st.download_button(
            "Download comparison summary CSV",
            data=comparison_summary.to_csv(index=False),
            file_name="percent_ramp_comparison_summary.csv",
            mime="text/csv",
        )
        st.download_button(
            "Download comparison timeseries CSV",
            data=comparison_detail.to_csv(index=False),
            file_name="percent_ramp_comparison_timeseries.csv",
            mime="text/csv",
        )

    left, right = st.columns(2)
    with left:
        chart = df.set_index("year")[[
            "total_prescribed_forcing_wm2",
            "co2_forcing_wm2",
            "non_co2_and_additional_forcing_wm2",
            "toa_imbalance_wm2",
            "ocean_heat_uptake_wm2",
        ]]
        chart.columns = [
            "Total prescribed forcing",
            "CO₂ forcing",
            "Non-CO₂/additional forcing",
            "TOA imbalance",
            "Ocean heat uptake",
        ]
        st.line_chart(chart, x_label="Year", y_label="Energy flux (W/m²)")
    with right:
        sea_ice_chart = result.northern_sea_ice_area_extent_frame().set_index("year")[
            [
                "northern_hemisphere_sea_ice_area_million_km2",
                "northern_hemisphere_sea_ice_extent_million_km2",
            ]
        ]
        sea_ice_chart.columns = [
            "Native NH thermodynamic ice area",
            "Coarse-zonal NH 15% extent diagnostic",
        ]
        st.line_chart(
            sea_ice_chart, x_label="Year", y_label="Million km²"
        )
        st.caption(
            "Area is the direct native thermodynamic integral. Extent is a coarse-zonal "
            "15% threshold diagnostic only; it is not a satellite-equivalent skill target."
        )

with sensitivity_tab:
    left, right = st.columns(2)
    with left:
        figure = make_gregory_figure(diagnostics)
        st.pyplot(figure, width="stretch")
        plt.close(figure)
    with right:
        figure = make_feedback_figure(diagnostics)
        st.pyplot(figure, width="stretch")
        plt.close(figure)
    st.dataframe(
        pd.DataFrame(
            {
                "Feedback": list(diagnostics.feedbacks_wm2_k.keys()),
                "W/m²/K": list(diagnostics.feedbacks_wm2_k.values()),
            }
        ),
        hide_index=True,
        width="stretch",
    )

with maps_tab:
    map_year = st.slider('Map year', int(round(df['year'].iloc[0])), int(round(df['year'].iloc[-1])), int(round(df['year'].iloc[-1])), 1, help=setting_tooltip('map_year'))
    map_index = int(np.argmin(np.abs(df["year"].to_numpy() - map_year)))
    temperature_field_label = st.radio(
        'Temperature field',
        ['Bulk surface', 'Near-surface air', 'Arctic ocean interface'],
        horizontal=True,
        help=(
            'Bulk surface is land plus mixed-layer ocean. Near-surface air is the '
            'field used for Arctic amplification. The interface product is shown '
            'only over Arctic ocean cells.'
        ),
    )
    field_kind = {
        'Bulk surface': 'bulk_surface',
        'Near-surface air': 'near_surface_air',
        'Arctic ocean interface': 'arctic_interface',
    }[temperature_field_label]
    absolute_map = st.checkbox('Show absolute temperature', value=False, help=setting_tooltip('absolute_map'))
    figure = make_temperature_map_figure(
        result, map_index, absolute=absolute_map, field_kind=field_kind
    )
    st.pyplot(figure, width="stretch")
    plt.close(figure)
    cryosphere_kind = st.radio(
        'Cryosphere map',
        [
            'Native thermodynamic sea ice',
            'Native sector concentration projection',
            'Sea-ice 15% extent occupancy',
            'Snow',
        ],
        horizontal=True,
        help=setting_tooltip('cryosphere_kind'),
    )
    kind = {
        'Native thermodynamic sea ice': 'sea_ice',
        'Native sector concentration projection': 'sea_ice_display',
        'Sea-ice 15% extent occupancy': 'sea_ice_extent',
        'Snow': 'snow',
    }[cryosphere_kind]
    figure = make_cryosphere_map_figure(result, map_index, kind=kind)
    st.pyplot(figure, width="stretch")
    plt.close(figure)
    if kind.startswith('sea_ice'):
        st.caption(
            "The native field is the primary thermodynamic state. The optional "
            "sector projection and 15% extent occupancy are coarse diagnostics "
            "derived directly from that state; no longitude-resolved process "
            "skill or satellite-equivalent extent skill is claimed."
        )

with amoc_tab:
    left, right = st.columns(2)
    with left:
        chart = df.set_index("year")[[
            "north_salinity_psu",
            "tropical_salinity_psu",
            "southern_salinity_psu",
            "deep_salinity_psu",
        ]]
        chart.columns = ["Northern", "Tropical", "Southern", "Deep"]
        st.line_chart(chart, x_label="Year", y_label="Salinity (PSU)")
    with right:
        chart = df.set_index("year")[[
            "amoc_temperature_density_term",
            "amoc_salinity_density_term",
            "amoc_density_driver",
        ]]
        chart.columns = ["Thermal density term", "Haline density term", "Total driver"]
        st.line_chart(chart, x_label="Year", y_label="Relative density contribution")

    left, right = st.columns(2)
    with left:
        chart = df.set_index("year")[[
            "amoc_ekman_inflow_sv",
            "amoc_upwelling_sv",
            "amoc_eddy_outflow_sv",
            "amoc_sv",
        ]]
        chart.columns = ["Ekman inflow", "Upwelling", "Eddy outflow", "Northern sinking"]
        st.line_chart(chart, x_label="Year", y_label="Transport (Sv)")
    with right:
        amoc_structure_columns = ["fovs_sv", "pycnocline_depth_m"]
        if "amoc_indo_pacific_compensation_active_sv" in df.columns:
            amoc_structure_columns.append(
                "amoc_indo_pacific_compensation_active_sv"
            )
        chart = df.set_index("year")[amoc_structure_columns].copy()
        chart = chart.rename(
            columns={
                "fovs_sv": "FovS (Sv)",
                "pycnocline_depth_m": "Pycnocline depth (m)",
                "amoc_indo_pacific_compensation_active_sv": (
                    "Active Indo-Pacific compensation (Sv)"
                ),
            }
        )
        st.line_chart(chart, x_label="Year")

    st.latex(
        r"q_N^*=q_0\left(\frac{D}{D_0}\right)^2"
        r"\frac{\alpha c_T(T_S-T_N)+\beta(S_N-S_S)}{\Delta\rho_0/\rho_0}"
    )
    st.latex(
        r"A\frac{dD}{dt}=q_{Ek}+q_U(D)-q_e(D)-q_N,\qquad "
        r"F_{ovS}=-\frac{q_N(S_S-S_D)}{S_0}"
    )
    st.markdown(
        "The five active Atlantic salinity reservoirs exchange salt through direction-aware overturning "
        "and symmetric gyre exchange. Surface freshwater is compensated between boxes, "
        "so total ocean salt is conserved rather than being clipped."
    )

with hysteresis_tab:
    if result.amoc_hysteresis is None:
        st.info("Enable equilibrium AMOC continuation in the sidebar.")
    else:
        hysteresis_summary = amoc_hysteresis_summary(
            result.amoc_hysteresis,
            collapse_threshold_sv=config.amoc_collapse_threshold_sv,
        )
        cols = st.columns(4)
        collapse = hysteresis_summary["collapse_threshold_hosing_sv"]
        recovery = hysteresis_summary["recovery_threshold_hosing_sv"]
        bistable_min = hysteresis_summary["bistable_minimum_hosing_sv"]
        bistable_max = hysteresis_summary["bistable_maximum_hosing_sv"]
        cols[0].metric("Collapse threshold", "Not reached" if collapse is None else f"{collapse:.3f} Sv")
        cols[1].metric("Recovery threshold", "Not reached" if recovery is None else f"{recovery:.3f} Sv")
        cols[2].metric(
            "Bistable interval",
            "Not found" if bistable_min is None else f"{bistable_min:.3f}-{bistable_max:.3f} Sv",
        )
        cols[3].metric("Maximum branch separation", f"{hysteresis_summary['maximum_stable_branch_separation_sv']:.2f} Sv")
        figure = make_amoc_hysteresis_figure(result.amoc_hysteresis)
        st.pyplot(figure, width="stretch")
        plt.close(figure)
        st.dataframe(
            result.amoc_hysteresis[[
                "phase",
                "target_hosing_sv",
                "amoc_sv",
                "fovs_sv",
                "pycnocline_depth_m",
                "north_salinity_psu",
                "southern_salinity_psu",
                "equilibrium_stable",
                "stable_equilibria_count",
                "bistable",
                "maximum_real_eigenvalue_per_year",
            ]],
            hide_index=True,
            width="stretch",
        )

with download_tab:
    bundle = build_download_bundle(result)
    st.download_button(
        "Download all run data as ZIP",
        data=bundle,
        file_name="emergent_climate_model_run.zip",
        mime="application/zip",
    )
    st.download_button(
        "Download transient time series CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="timeseries.csv",
        mime="text/csv",
    )
    st.download_button(
        "Download configuration JSON",
        data=json.dumps(asdict(config), indent=2).encode("utf-8"),
        file_name="config.json",
        mime="application/json",
    )

st.warning(
    "This remains a reduced-complexity educational model. The AMOC module can "
    "produce nonlinear collapse, reversal, and stability-tested equilibrium hysteresis, but its numerical thresholds "
    "are model-dependent and are not forecasts of the real AMOC."
)
