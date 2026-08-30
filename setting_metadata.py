#!/usr/bin/env python3
"""Shared setting descriptions, uncertainty bases, and confidence ratings.

The confidence label describes how well the setting's physical interpretation
and uncertainty range are constrained. It is not a probability that a model
projection is correct. Operational controls are rated very high because their
meaning is exact, while their selected value remains a user choice.
"""

from __future__ import annotations

from dataclasses import dataclass


CONFIDENCE_SCALE = {
    "Very high": "Directly defined, numerically controlled, or tightly observed.",
    "High": "Supported by multiple observations or a major assessment.",
    "Medium": "Physically motivated, but effective or model dependent.",
    "Low": "Weakly constrained emulator coefficient or experimental assumption.",
}


@dataclass(frozen=True)
class SettingInfo:
    description: str
    interval: str
    basis: str
    confidence: str

    def tooltip(self, extra_note: str = "") -> str:
        text = (
            f"{self.description}\n\n"
            f"Uncertainty / interval: {self.interval}\n"
            f"Basis: {self.basis}\n"
            f"Confidence: {self.confidence} — {CONFIDENCE_SCALE[self.confidence]}"
        )
        if extra_note:
            text += f"\n\nNote: {extra_note}"
        return text


def _op(description: str, interval: str = "User-defined; no scientific confidence interval.", basis: str = "Experiment or software control.") -> SettingInfo:
    return SettingInfo(description, interval, basis, "Very high")


def _physical(description: str, interval: str, basis: str, confidence: str) -> SettingInfo:
    return SettingInfo(description, interval, basis, confidence)


SETTING_INFO: dict[str, SettingInfo] = {
    # Experiment and output controls.
    "preset": _op("Loads a complete, predefined combination of settings."),
    "scenario": _op("Selects the prescribed CO2 or SSP pathway used by the experiment."),
    "forcing_mode": _op("Chooses whether SSP experiments use total effective forcing or CO2 forcing alone."),
    "start_year": _op("Calendar year at which recorded output begins.", "User-defined; SSP data are limited to the pathway data period."),
    "years": _op("Length of the recorded transient simulation."),
    "duration_years": _op("Length of the recorded transient simulation."),
    "dt": _op("Numerical integration step. Smaller values improve convergence but increase runtime.", "Validated range 0.001–0.25 years; 0.05 years is the tested default.", "Numerical convergence tests."),
    "dt_years": _op("Numerical integration step. Smaller values improve convergence but increase runtime.", "Validated range 0.001–0.25 years; 0.05 years is the tested default.", "Numerical convergence tests."),
    "auto_initialize_from_1850": _op("For post-1850 SSP starts, first integrates continuously from 1850 so the run does not cold-start."),
    "output": _op("Folder where figures, CSV files, configuration, and summaries are written."),
    "co2_start": _op("Initial atmospheric CO2 concentration for idealized pathways."),
    "co2_start_ppm": _op("Initial atmospheric CO2 concentration for idealized pathways."),
    "co2_end": _op("Final atmospheric CO2 concentration for linear or overshoot pathways."),
    "co2_end_ppm": _op("Final atmospheric CO2 concentration for linear or overshoot pathways."),
    "co2_peak": _op("Peak atmospheric CO2 concentration in an overshoot pathway."),
    "co2_peak_ppm": _op("Peak atmospheric CO2 concentration in an overshoot pathway."),
    "one_percent_cap": _op("Optional concentration ceiling for the 1%-per-year CO2 pathway."),
    "one_percent_cap_ppm": _op("Optional concentration ceiling for the 1%-per-year CO2 pathway."),
    "co2_growth_rate_percent": _op("Annual compounded CO2 growth rate for the percent-ramp-to-cap experiment.", "Must be positive. Common idealized choices are 0.5%, 1%, 2%, 3%, and 5% per year."),
    "co2_growth_rate_percent_per_year": _op("Annual compounded CO2 growth rate for the percent-ramp-to-cap experiment.", "Must be positive. Common idealized choices are 0.5%, 1%, 2%, 3%, and 5% per year."),
    "co2_growth_cap": _op("CO2 concentration at which compound growth stops and the hold phase begins.", "Must be at least the starting CO2 concentration."),
    "co2_growth_cap_ppm": _op("CO2 concentration at which compound growth stops and the hold phase begins.", "Must be at least the starting CO2 concentration."),
    "co2_hold_years": _op("Number of years simulated after the CO2 cap is reached.", "The total run length is calculated automatically as time-to-cap plus this hold period."),
    "percent_ramp_compare_rates": _op("Comma-separated annual CO2 growth rates controlling the complete capped-ramp experiment.", "For example: 0.5,1,2,3,5. Supply one value for a single-rate experiment or several values for a comparison plot."),
    "co2_ramp_years": _op("Duration of the linear CO2 ramp before the concentration is held fixed."),
    "mc_co2_target_sweep_enabled": _op("Runs a paired Monte Carlo ensemble at a sequence of linearly ramped CO2 targets."),
    "mc_sweep_start_ppm": _op("Common initial CO2 concentration from which every target experiment begins. Increment mode also includes it as the control target.", "Positive concentration; default 278.3 ppm."),
    "mc_sweep_target_mode": _op("Chooses regular increment targets or an exact user-entered target list."),
    "mc_sweep_step_ppm": _op("CO2 increment between successive target experiments in increment mode.", "Positive concentration increment; default 50 ppm."),
    "mc_sweep_max_ppm": _op("Highest CO2 target included in increment mode. It is included exactly even when the increment does not land on it."),
    "mc_sweep_specific_targets": _op("Exact CO2 targets used in specific mode. Values may be separated by commas, spaces, or semicolons; duplicates are removed and targets are sorted. Targets below the common start use descending ramps."),
    "mc_sweep_initial_equilibration_years": _op("Constant-CO2 spinup used only when the common sweep start differs from the model reference concentration. All targets for a member reuse the resulting exact pre-forcing state.", "Non-negative whole years; default 1000."),
    "mc_sweep_ramp_years": _op("Number of years used to linearly increase CO2 from the starting concentration to each target."),
    "mc_sweep_hold_years": _op("Number of years each target concentration is held after the ramp."),
    "mc_sweep_collapse_window_years": _op("Final duration window used to classify persistent AMOC collapse."),
    "mc_sweep_persistence_fraction": _op("Minimum fraction of the final duration window that must remain below the AMOC collapse threshold.", "Accepted range (0, 1]; default 0.95."),
    "mc_sweep_recovery_years": _op("Minimum continuous recovery duration above the collapse threshold that disqualifies persistent collapse.", "Non-negative duration; default 5 years."),
    "mc_sweep_bootstrap_samples": _op("Number of weighted-member bootstrap replicates used for pointwise fraction and threshold intervals.", "Zero disables bootstrap intervals; default 1000 for production sweeps."),
    "mc_sweep_confidence_level": _op("Central confidence level reported for bootstrap intervals.", "Accepted range (0, 1); default 0.90."),
    "mc_sweep_plot_mode": _op("Chooses whether AMOC trajectory plots show ensemble means only or individual member curves plus means."),
    "mc_sweep_allow_exploratory_target_counts": _op(
        "Allows numerical sweep products with fewer than the release minimum number of valid members to be exported as explicitly exploratory-only outputs.",
        "Disabled by default. Enabling this option never upgrades an undersized target to quantitative or release-grade status.",
        "Operational classification control.",
    ),
    "peak_fraction": _op("Fraction of the run elapsed when the overshoot pathway reaches peak CO2.", "0.05–0.95 is accepted; this is a scenario design choice."),
    "peak_time_fraction": _op("Fraction of the run elapsed when the overshoot pathway reaches peak CO2.", "0.05–0.95 is accepted; this is a scenario design choice."),
    "additional_forcing": _op("Adds a constant radiative forcing perturbation on top of the selected pathway."),
    "additional_forcing_wm2": _op("Adds a constant radiative forcing perturbation on top of the selected pathway."),
    "ssp_before": _op("SSP pathway followed up to the hybrid branch year."),
    "ssp_after": _op("SSP whose future annual concentration and forcing change rates are adopted after the branch year; the accumulated level is retained."),
    "switch_year": _op("Calendar year at which the hybrid pathway starts changing its annual rates toward the second SSP."),
    "ssp_switch_year": _op("Calendar year at which the hybrid pathway starts changing its annual rates toward the second SSP."),
    "transition_years": _op("Duration of the smooth blend between the annual rates of the two SSP pathways; accumulated concentration and forcing remain continuous."),
    "ssp_transition_years": _op("Duration of the smooth blend between the annual rates of the two SSP pathways; accumulated concentration and forcing remain continuous."),
    "run_diagnostics": _op("Runs abrupt-2xCO2, Gregory-regression, and 1%-CO2 sensitivity diagnostics."),
    "equilibrium_years": _op("Duration of the abrupt-2xCO2 equilibrium diagnostic.", "400–1600 years offered; longer runs reduce residual disequilibrium.", "Numerical diagnostic design."),
    "map_year": _op("Selects which simulated year is displayed on the map."),
    "temperature_field_label": _op("Selects the bulk-surface, near-surface-air, or Arctic ocean-interface temperature product displayed on the map."),
    "absolute_map": _op("Switches the map between temperature anomaly and absolute temperature."),
    "cryosphere_kind": _op("Selects the primary native thermodynamic sea-ice field, its native two-sector concentration projection, coarse 15%-extent occupancy, or snow. The sea-ice maps do not claim longitude-resolved process skill or satellite-equivalent extent skill."),

    # Climate physics.
    "co2_doubling_erf_wm2": _physical(
        "Effective radiative forcing produced by doubling CO2 relative to the reference concentration.",
        "AR6 best estimate 3.93 W/m2; assessed 90% range approximately 3.55–4.32 W/m2. Built-in prior support: 3–5 W/m2.",
        "IPCC AR6 WGI Chapter 7 and its supplementary material.",
        "High",
    ),
    "co2_forcing_formula": _op(
        "Selects either the legacy logarithmic CO2 forcing equation or the concentration-dependent Meinshausen et al. (2020) formulation.",
        "Meinshausen et al. (2020) is the default. The logarithmic option remains available only for legacy-comparison experiments.",
        "Radiative-forcing formulation choice.",
    ),
    "co2_forcing_reference_n2o_ppb": _physical(
        "Reference nitrous-oxide concentration used for spectral-overlap terms in the Meinshausen CO2 forcing relationship.",
        "Must be positive; default 270.1 ppb represents the model reference state.",
        "Meinshausen et al. (2020) effective-radiative-forcing parameterization.",
        "High",
    ),
    "relative_humidity": _physical(
        "Effective free-tropospheric relative humidity used in the water-vapour calculation.",
        "No formal single global confidence interval. Built-in prior support: 0.60–0.90, centred near 0.78.",
        "Observed tropospheric humidity climatology, reduced to one global emulator parameter.",
        "Medium",
    ),
    "moist_lapse_rate_weight": _physical(
        "Weight given to moist-adiabatic lapse-rate changes in the combined water-vapour/lapse-rate response.",
        "No direct observational CI. Built-in prior support: 0.10–0.70; default 0.30 is calibrated against AR6 feedback decomposition.",
        "AR6 water-vapour plus lapse-rate feedback, mapped onto an emulator mixing coefficient.",
        "Low",
    ),
    "arctic_lapse_rate_feedback_wm2_k": _physical(
        "Optional unresolved local Arctic lapse-rate/inversion feedback applied to the prognostic surface energy budget.",
        "Bounded to 0–3 W/m2/K; default 1.10 W/m2/K is a low-confidence, tuning-informed closure for unresolved inversion/lapse-rate feedback after native sea-ice recalibration.",
        "Reduced representation of high-latitude lapse-rate and inversion feedback.",
        "Low",
    ),
    "antarctic_lapse_rate_feedback_wm2_k": _physical(
        "Optional unresolved local Antarctic lapse-rate feedback applied to the prognostic surface energy budget.",
        "Bounded to 0–3 W/m2/K; default 0.",
        "Reduced representation of high-latitude lapse-rate feedback.",
        "Low",
    ),
    "seasonal_arctic_enabled": _op(
        "Enables the prognostic seasonal Arctic near-surface atmosphere and latent sea-ice subsystem."
    ),
    "arctic_module_start_latitude_deg": _physical(
        "Latitude where the two-sector thermodynamic Arctic module begins blending into the Northern Hemisphere ocean field.",
        "No direct observational CI. Default 52.0 degrees N; it is a low-confidence structural geometry control sampled by the built-in Monte Carlo prior.",
        "Reduced representation of the marginal-ice-zone transition.",
        "Low",
    ),
    "arctic_reference_air_seasonal_amplitude_c": _physical(
        "Seasonal amplitude of the prescribed Arctic reference-air climatology used to generate the periodic control cycle.",
        "No direct observational CI for this reduced boundary condition. Default 12.0 degrees C; it is calibration-informed and sampled explicitly by Monte Carlo.",
        "Reduced sinusoidal Arctic atmospheric boundary condition.",
        "Low",
    ),
    "arctic_ocean_air_exchange_wm2_k": _physical(
        "Legacy compatibility input from the pre-v2.28 Arctic solver.",
        "Ignored by the active fractional Arctic solver; not sampled or shown in normal interfaces.",
        "Retained only so older configuration files still parse.",
        "Operational",
    ),
    "arctic_ocean_air_exchange": _physical(
        "Legacy compatibility input from the pre-v2.28 Arctic solver.",
        "Ignored by the active fractional Arctic solver; not sampled or shown in normal interfaces.",
        "Retained only so older configuration files still parse.",
        "Operational",
    ),
    "arctic_moisture_transport_wm2_per_k": _physical(
        "Warming-dependent atmospheric moisture and latent-energy convergence into the Arctic.",
        "Warm-season background coefficient; default 0.22 W/m2 per K of global warming. Cold-season enhancement is diagnosed separately from polar darkness.",
        "Calibrated against annual Arctic amplification while conserving the global redistribution integral.",
        "Low",
    ),
    "arctic_moisture_transport": _physical(
        "Warming-dependent atmospheric moisture and latent-energy convergence into the Arctic.",
        "Warm-season background coefficient; default 0.22 W/m2 per K of global warming. Cold-season enhancement is diagnosed separately from polar darkness.",
        "Calibrated against annual Arctic amplification while conserving the global redistribution integral.",
        "Low",
    ),
    "arctic_winter_transport_enhancement": _physical(
        "Additive cold-season Arctic energy-convergence coefficient multiplied by a joint darkness-and-cold-state index.",
        "The index is zero in warm shoulder seasons even when nights are dark, and strongest in the cold polar night. Default 19 W/m2/K; built-in prior support 0-25 W/m2/K.",
        "Seasonal atmospheric energy-transport closure calibrated jointly against March and September sea-ice climatology and trends.",
        "Low",
    ),
    "arctic_winter_transport_temperature_scale_c": _physical(
        "Reference-air temperature scale controlling the cold-state part of winter Arctic energy convergence.",
        "Positive; default 15 C. Smaller values confine the enhancement more sharply to the coldest reference months.",
        "Prevents a darkness-only winter term from acting strongly during the relatively warm September shoulder season.",
        "Low",
    ),
    "arctic_winter_transport_temperature_scale": _physical(
        "Reference-air temperature scale controlling the cold-state part of winter Arctic energy convergence.",
        "Positive; default 15 C. Smaller values confine the enhancement more sharply to the coldest reference months.",
        "Prevents a darkness-only winter term from acting strongly during the relatively warm September shoulder season.",
        "Low",
    ),
    "arctic_dry_static_transport_wm2_k": _physical(
        "Dry-static atmospheric transport that opposes excessive local Arctic air-temperature contrast.",
        "Effective coefficient; default 1.55 W/m2/K.",
        "Reduced meridional atmospheric energy-transport closure.",
        "Low",
    ),
    "arctic_dry_static_transport": _physical(
        "Dry-static atmospheric transport that opposes excessive local Arctic air-temperature contrast.",
        "Effective coefficient; default 1.55 W/m2/K.",
        "Reduced meridional atmospheric energy-transport closure.",
        "Low",
    ),
    "arctic_open_water_heat_release_wm2_per_fraction": _physical(
        "Legacy compatibility input from the pre-v2.28 Arctic solver.",
        "Ignored by the active fractional Arctic solver; not sampled or shown in normal interfaces.",
        "Retained only so older configuration files still parse.",
        "Operational",
    ),
    "arctic_open_water_heat_release": _physical(
        "Legacy compatibility input from the pre-v2.28 Arctic solver.",
        "Ignored by the active fractional Arctic solver; not sampled or shown in normal interfaces.",
        "Retained only so older configuration files still parse.",
        "Operational",
    ),
    "arctic_ice_air_exchange_wm2_k": _physical(
        "Legacy compatibility input from the pre-v2.28 Arctic solver.",
        "Ignored by the active fractional Arctic solver; not sampled or shown in normal interfaces.",
        "Retained only so older configuration files still parse.",
        "Operational",
    ),
    "arctic_ice_air_exchange": _physical(
        "Legacy compatibility input from the pre-v2.28 Arctic solver.",
        "Ignored by the active fractional Arctic solver; not sampled or shown in normal interfaces.",
        "Retained only so older configuration files still parse.",
        "Operational",
    ),
    "arctic_ice_ocean_exchange_wm2_k": _physical(
        "Legacy compatibility input from the pre-v2.28 Arctic solver.",
        "Ignored by the active fractional Arctic solver; not sampled or shown in normal interfaces.",
        "Retained only so older configuration files still parse.",
        "Operational",
    ),
    "arctic_ice_ocean_exchange": _physical(
        "Legacy compatibility input from the pre-v2.28 Arctic solver.",
        "Ignored by the active fractional Arctic solver; not sampled or shown in normal interfaces.",
        "Retained only so older configuration files still parse.",
        "Operational",
    ),
    "arctic_ice_relaxation_years": _physical(
        "Legacy compatibility input from the pre-v2.28 Arctic solver.",
        "Ignored by the active fractional Arctic solver; not sampled or shown in normal interfaces.",
        "Retained only so older configuration files still parse.",
        "Operational",
    ),
    "arctic_winter_thin_ice_years": _physical(
        "Legacy compatibility input from the pre-v2.28 Arctic solver.",
        "Ignored by the active fractional Arctic solver; not sampled or shown in normal interfaces.",
        "Retained only so older configuration files still parse.",
        "Operational",
    ),
    "longwave_spectral_factor": _physical(
        "Dimensionless correction for non-grey longwave spectral behaviour.",
        "No formal CI. Built-in prior support: 0.80–1.15, centred near 0.98.",
        "Radiative-transfer behaviour represented by a reduced grey-atmosphere correction.",
        "Medium",
    ),
    "water_vapor_height": _physical(
        "Increase in effective infrared emission height per logarithmic increase in water vapour.",
        "No direct CI. Built-in prior support: 0.40–1.80 km per ln(q/q0), centred near 1.0.",
        "Water-vapour radiative response calibrated against the AR6 combined water-vapour/lapse-rate feedback.",
        "Medium",
    ),
    "water_vapor_emission_height_km_per_lnq": _physical(
        "Increase in effective infrared emission height per logarithmic increase in water vapour.",
        "No direct CI. Built-in prior support: 0.40–1.80 km per ln(q/q0), centred near 1.0.",
        "Water-vapour radiative response calibrated against the AR6 combined water-vapour/lapse-rate feedback.",
        "Medium",
    ),
    "low_cloud_loss": _physical(
        "Fractional reduction of subtropical low cloud for each degree of local warming.",
        "No accepted observational CI. Built-in prior support: 0.0002–0.020 per K; custom GUI range 0.001–0.010 per K.",
        "Cloud-process uncertainty constrained indirectly by the AR6 net cloud-feedback range.",
        "Low",
    ),
    "low_cloud_loss_fraction_per_k": _physical(
        "Fractional reduction of subtropical low cloud for each degree of local warming.",
        "No accepted observational CI. Built-in prior support: 0.0002–0.020 per K; custom GUI range 0.001–0.010 per K.",
        "Cloud-process uncertainty constrained indirectly by the AR6 net cloud-feedback range.",
        "Low",
    ),
    "low_cloud_moisture_gain_fraction_per_lnq": _physical(
        "Compensating low-cloud increase associated with increasing atmospheric moisture.",
        "No accepted observational CI. Built-in prior support: 0.0002–0.035 per ln(q/q0).",
        "Emulator coefficient constrained indirectly by net cloud feedback.",
        "Low",
    ),
    "high_cloud_coupling": _physical(
        "Fraction of surface warming followed by high-cloud-top temperature.",
        "No direct CI. Built-in prior support: 0.02–0.80; custom GUI range 0.15–0.45.",
        "Cloud-top temperature response represented by an effective emulator coefficient.",
        "Low",
    ),
    "high_cloud_temperature_coupling": _physical(
        "Fraction of surface warming followed by high-cloud-top temperature.",
        "No direct CI. Built-in prior support: 0.02–0.80; custom GUI range 0.15–0.45.",
        "Cloud-top temperature response represented by an effective emulator coefficient.",
        "Low",
    ),
    "sea_ice_albedo": _physical(
        "Broadband shortwave albedo assigned to sea-ice-covered ocean.",
        "No single global CI because snow cover, melt ponds, season, and angle matter. Built-in prior support: 0.30–0.85; default 0.54.",
        "Observed surface optical properties aggregated to one effective value.",
        "High",
    ),
    "snow_albedo": _physical(
        "Broadband shortwave albedo assigned to snow-covered land.",
        "No single global CI. Built-in prior support: 0.35–0.90; default 0.60.",
        "Observed snow optical properties aggregated across age, vegetation, and season.",
        "High",
    ),
    "sea_ice_transition_c": _physical(
        "Temperature at the centre of the smooth sea-ice fraction transition.",
        "No formal CI for this grid-cell emulator parameter. Built-in prior support: -3.0 to -0.5 degC.",
        "Seawater freezing physics plus unresolved seasonal and sub-grid heterogeneity.",
        "Medium",
    ),
    "sea_ice_transition_width_c": _physical(
        "Temperature width over which a latitude-band sea-ice fraction changes from mostly ice-free to mostly ice-covered.",
        "No observational CI. Built-in prior support: 1–8 degC; wider values represent stronger sub-grid/seasonal averaging.",
        "Effective representation of seasonal and spatial sea-ice heterogeneity.",
        "Low",
    ),
    "snow_transition_c": _physical(
        "Temperature at the centre of the smooth snow-cover transition.",
        "No formal CI for this grid-cell emulator parameter. Built-in prior support: -5 to +2 degC.",
        "Snow-cover climatology and aggregation across precipitation and seasonality.",
        "Medium",
    ),
    "snow_transition_width_c": _physical(
        "Temperature width over which snow cover changes from low to high fraction.",
        "No observational CI. Built-in prior support: 1–8 degC.",
        "Effective sub-grid and seasonal snow heterogeneity.",
        "Low",
    ),
    "land_capacity": _physical(
        "Effective land-column heat capacity controlling how quickly land temperature responds.",
        "No unique global CI. GUI range 0.8–4.0 W yr/m2/K; default 1.7.",
        "Soil/vegetation thermal inertia represented as one global effective reservoir.",
        "Medium",
    ),
    "land_heat_capacity_wyr_m2_k": _physical(
        "Effective land-column heat capacity controlling how quickly land temperature responds.",
        "No unique global CI. GUI range 0.8–4.0 W yr/m2/K; default 1.7.",
        "Soil/vegetation thermal inertia represented as one global effective reservoir.",
        "Medium",
    ),
    "ocean_capacity": _physical(
        "Effective mixed-layer ocean heat capacity.",
        "Built-in prior support: 3–20 W yr/m2/K; AR6 emulator reference is about 8.1 W yr/m2/K and the model default is 10.",
        "Seawater heat capacity multiplied by an effective mixed-layer depth.",
        "High",
    ),
    "ocean_mixed_layer_heat_capacity_wyr_m2_k": _physical(
        "Effective mixed-layer ocean heat capacity.",
        "Built-in prior support: 3–20 W yr/m2/K; AR6 emulator reference is about 8.1 W yr/m2/K and the model default is 10.",
        "Seawater heat capacity multiplied by an effective mixed-layer depth.",
        "High",
    ),
    "deep_capacity": _physical(
        "Effective heat capacity of the ventilated deep-ocean reservoir.",
        "Built-in prior support: 40–300 W yr/m2/K; AR6 emulator reference is about 110 W yr/m2/K.",
        "AR6 two-layer emulator calibration and effective ventilated ocean volume.",
        "Medium",
    ),
    "deep_ocean_heat_capacity_wyr_m2_k": _physical(
        "Effective heat capacity of the ventilated deep-ocean reservoir.",
        "Built-in prior support: 40–300 W yr/m2/K; AR6 emulator reference is about 110 W yr/m2/K.",
        "AR6 two-layer emulator calibration and effective ventilated ocean volume.",
        "Medium",
    ),
    "ocean_exchange": _physical(
        "Linear heat-exchange coefficient between the surface mixed layer and deep ocean.",
        "No direct observational CI. Built-in prior support: 0.20–1.80 W/m2/K; AR6 emulator reference is about 0.64 W/m2/K.",
        "Historical ocean heat uptake and two-layer climate-emulator calibration.",
        "Medium",
    ),
    "ocean_heat_exchange_wm2_k": _physical(
        "Linear heat-exchange coefficient between the surface mixed layer and deep ocean.",
        "No direct observational CI. Built-in prior support: 0.20–1.80 W/m2/K; AR6 emulator reference is about 0.64 W/m2/K.",
        "Historical ocean heat uptake and two-layer climate-emulator calibration.",
        "Medium",
    ),
    "meridional_diffusion": _physical(
        "Effective poleward heat redistribution between latitude bands.",
        "No direct observational CI. Built-in prior support: 0.15–1.20 W/m2/K.",
        "Combined atmospheric and oceanic meridional transport compressed into a diffusive coefficient.",
        "Low",
    ),
    "meridional_diffusion_wm2_k": _physical(
        "Effective poleward heat redistribution between latitude bands.",
        "No direct observational CI. Built-in prior support: 0.15–1.20 W/m2/K.",
        "Combined atmospheric and oceanic meridional transport compressed into a diffusive coefficient.",
        "Low",
    ),

    "global_bulk_surface_warming_c": _physical(
        "Global area-weighted anomaly of the prognostic land and mixed-layer ocean state used by the surface energy balance.",
        "Diagnostic output; no uncertainty interval.",
        "Model-resolved bulk-surface temperature field.",
        "High",
    ),
    "global_near_surface_air_warming_c": _physical(
        "Global near-surface-air proxy. Outside the Arctic it uses the bulk-surface proxy; inside the Arctic ocean it uses the prognostic Arctic-air reservoir.",
        "Diagnostic output; no uncertainty interval. This is the global denominator used for Arctic amplification in v2.28.0.",
        "Consistent model near-surface-air diagnostic.",
        "Medium",
    ),
    "arctic_near_surface_air_warming_c": _physical(
        "Area-weighted near-surface-air anomaly north of 66°N from the same field used by the global SAT denominator.",
        "Diagnostic output; no uncertainty interval.",
        "Prognostic Arctic-air reservoir plus Arctic land temperature.",
        "Medium",
    ),
    "arctic_bulk_surface_warming_c": _physical(
        "Area-weighted Arctic land plus mixed-layer ocean anomaly north of 66°N.",
        "Diagnostic output; no uncertainty interval. This is the field represented by the bulk-surface map.",
        "Model-resolved land and mixed-layer state.",
        "High",
    ),
    "arctic_ocean_interface_temperature_c": _physical(
        "Area-weighted absolute temperature of the Arctic ice/ocean interface or shallow open-water interface.",
        "Diagnostic output bounded by the configured freezing and maximum interface temperatures.",
        "Thermodynamic Arctic interface enthalpy state.",
        "Medium",
    ),

    # Freshwater forcing.
    "freshwater_hosing": _op("User-imposed North Atlantic freshwater perturbation. 1 Sv equals 10^6 m3/s.", "User-defined. Typical model-intercomparison experiments use roughly 0.05–0.3 Sv; this is not a real-world confidence interval.", "Idealized freshwater-hosing experiment design."),
    "freshwater_hosing_sv": _op("User-imposed North Atlantic freshwater perturbation. 1 Sv equals 10^6 m3/s.", "User-defined. Typical model-intercomparison experiments use roughly 0.05–0.3 Sv; this is not a real-world confidence interval.", "Idealized freshwater-hosing experiment design."),
    "hydrological_freshwater": _physical(
        "Increase in effective Atlantic freshwater forcing per degree of positive global warming from precipitation, evaporation, runoff, and Arctic export.",
        "No assessed scalar CI. Built-in prior and GUI support: 0.002–0.012 Sv/K; default 0.006 Sv/K.",
        "Hydrological-cycle projections compressed into one effective Atlantic flux.",
        "Low",
    ),
    "hydrological_freshwater_sv_per_k": _physical(
        "Increase in effective Atlantic freshwater forcing per degree of positive global warming from precipitation, evaporation, runoff, and Arctic export.",
        "No assessed scalar CI. Built-in prior and GUI support: 0.002–0.012 Sv/K; default 0.006 Sv/K.",
        "Hydrological-cycle projections compressed into one effective Atlantic flux.",
        "Low",
    ),
    "hydrological_freshwater_north_fraction": _physical(
        "Fraction of hydrological freshwater forcing applied directly to the northern sinking box.",
        "No observational CI. Built-in prior support: 0.25–0.98; default 0.70.",
        "Effective spatial partition of precipitation, runoff, and Arctic freshwater pathways.",
        "Low",
    ),
    "greenland_freshwater": _physical(
        "Long-term Greenland meltwater sensitivity per degree above the selected warming threshold.",
        "No accepted linear CI. Built-in prior and GUI support: 0.002–0.010 Sv/K; default 0.005 Sv/K. In v2.27 this coefficient controls only the slow dynamic-discharge branch; surface mass balance is calculated separately.",
        "Ice-sheet mass-balance projections and idealized meltwater experiments; response is strongly state and pathway dependent.",
        "Low",
    ),
    "greenland_freshwater_sv_per_k": _physical(
        "Long-term Greenland meltwater sensitivity per degree above the selected warming threshold.",
        "No accepted linear CI. Built-in prior and GUI support: 0.002–0.010 Sv/K; default 0.005 Sv/K. In v2.27 this coefficient controls only the slow dynamic-discharge branch; surface mass balance is calculated separately.",
        "Ice-sheet mass-balance projections and idealized meltwater experiments; response is strongly state and pathway dependent.",
        "Low",
    ),
    "greenland_freshwater_threshold": _physical(
        "Global-warming anomaly below which the model applies no Greenland meltwater term.",
        "No assessed threshold for this linear emulator. It is a sensitivity assumption, not a Greenland tipping threshold.",
        "Simplified onset control for the meltwater parameterization.",
        "Low",
    ),
    "greenland_freshwater_threshold_c": _physical(
        "Global-warming anomaly below which the model applies no Greenland meltwater term.",
        "No assessed threshold for this linear emulator. It is a sensitivity assumption, not a Greenland tipping threshold.",
        "Simplified onset control for the meltwater parameterization.",
        "Low",
    ),
    "greenland_freshwater_adjustment_years": _physical(
        "E-folding response time with which Greenland freshwater approaches its warming-dependent target.",
        "No direct CI. Built-in prior support: 5–250 years; default 45 years.",
        "Aggregates ice-sheet response, routing, and ocean delivery timescales.",
        "Low",
    ),
    "greenland_initial_ice_mass_gt": _physical(
        "Initial finite Greenland ice reservoir available to the meltwater parameterization.",
        "Default 2.85 million Gt. This is a reservoir bound, not a claim that all ice is dynamically available on the simulated timescale.",
        "Greenland ice-sheet mass expressed as freshwater-equivalent gigatonnes.",
        "Medium",
    ),
    "greenland_depletion_exponent": _physical(
        "Exponent controlling how the warming-dependent Greenland discharge declines as the finite ice reservoir is depleted.",
        "Built-in prior support: 0.5–2.0; default 1.0.",
        "Reduced representation of shrinking melt area and finite ice availability.",
        "Low",
    ),
    "greenland_max_freshwater_sv": _physical(
        "Upper bound on Greenland freshwater discharge before the finite-reservoir mass limit is applied.",
        "Built-in prior support: 0.005–0.040 Sv; default 0.025 Sv.",
        "Numerical and physical cap preventing unbounded temperature-proportional discharge.",
        "Low",
    ),
    "greenland_surface_mass_balance_enabled": _op(
        "Enables the reduced seasonal Greenland surface-mass-balance calculation with snowfall, rain-snow partition, positive-degree-day melt, and meltwater retention."
    ),
    "greenland_dynamic_discharge_fraction": _physical(
        "Fraction of the legacy 0.005 Sv/K Greenland sensitivity assigned to slow dynamic discharge rather than surface mass balance.",
        "Bounded 0–1; default 0.10.",
        "Structural split between slow ice dynamics and seasonal surface processes.",
        "Low",
    ),
    "greenland_reference_annual_temperature_c": _physical(
        "Annual-mean reference surface temperature used by the reduced Greenland SMB seasonal cycle.",
        "No single ice-sheet-wide assessed interval; default -10.5 C and intended sensitivity range roughly -15 to -5 C.",
        "Reduced Greenland surface-temperature climatology.",
        "Low",
    ),
    "greenland_reference_seasonal_amplitude_c": _physical(
        "Amplitude of the reference Greenland seasonal surface-temperature cycle.",
        "No single ice-sheet-wide assessed interval; default 13.5 C.",
        "Reduced seasonal temperature climatology.",
        "Low",
    ),
    "greenland_pdd_melt_factor_gt_per_degree_day": _physical(
        "Reduced positive-degree-day conversion from above-freezing surface temperature to Greenland melt anomaly.",
        "No single assessed whole-ice-sheet CI; default 0.38 Gt per degree-day is calibrated jointly against recent mass loss and the 21st-century freshwater safety bound.",
        "Positive-degree-day surface-melt parameterization.",
        "Low",
    ),
    "greenland_baseline_precipitation_gt_per_year": _physical(
        "Reference annual Greenland precipitation used to calculate snowfall anomalies.",
        "No emulator-specific assessed CI; default 700 Gt/year.",
        "Whole-ice-sheet precipitation and accumulation estimates reduced to one annual scale.",
        "Low",
    ),
    "greenland_precipitation_fraction_per_k": _physical(
        "Fractional increase in Greenland precipitation per degree of regional warming.",
        "No single assessed scalar interval; default 0.05 per K.",
        "Clausius-Clapeyron-motivated reduced precipitation response.",
        "Low",
    ),
    "greenland_snow_rain_transition_c": _physical(
        "Surface temperature at the midpoint of the Greenland snowfall-to-rain partition.",
        "Default 1.0 C; an effective transition rather than a pointwise phase threshold.",
        "Logistic rain-snow partition in the reduced SMB model.",
        "Low",
    ),
    "greenland_snow_rain_transition_width_c": _physical(
        "Temperature width over which Greenland precipitation shifts between snow and rain.",
        "Must be positive; default 2.0 C.",
        "Logistic rain-snow partition in the reduced SMB model.",
        "Low",
    ),
    "greenland_meltwater_retention_fraction": _physical(
        "Fraction of positive surface melt initially retained in firn rather than released as runoff.",
        "Bounded 0–1; default 0.35, declining with positive temperature anomaly.",
        "Reduced firn retention and runoff-delay representation.",
        "Low",
    ),
    "greenland_retention_loss_fraction_per_k": _physical(
        "Reduction in Greenland meltwater retention fraction per degree of positive regional warming.",
        "Non-negative; default 0.04 per K, with total retention clipped to 0–1.",
        "Reduced representation of firn saturation and runoff expansion.",
        "Low",
    ),
    "warming_freshwater": _physical(
        "Legacy combined warming-to-freshwater coefficient. When supplied, it overrides separate hydrological and Greenland terms.",
        "No formal CI; retained only for backwards compatibility.",
        "Older aggregate parameterization.",
        "Low",
    ),
    "freshwater_start_fraction": _op("Fraction of the transient run elapsed before explicit hosing starts."),
    "freshwater_ramp_years": _op("Time taken for explicit hosing to rise from zero to its full value."),
    "freshwater_compensation_mode": _op("Chooses where virtual salt is added to compensate freshwater and conserve total salt.", "Method choice, not an observed interval. External compensation is best for transient sea-level-like forcing; Atlantic compensation is required by the equilibrium continuation diagnostic.", "Salt-conserving experiment design."),
    "freshwater_compensation_tropical_fraction": _physical(
        "When Atlantic compensation is selected, fraction of compensating salt placed in the tropical rather than Southern Atlantic box.",
        "No observational CI. Allowed range 0–1; default 0.70.",
        "Numerical spatial partition used for an idealized virtual-salt experiment.",
        "Low",
    ),

    # AMOC state, heat transport, and density closure.
    "amoc_reference": _physical(
        "Reference preindustrial/present-day AMOC strength used to calibrate the control state.",
        "RAPID 26.5N mean about 16.9 Sv with large interannual variability; posterior target 14–19 Sv. Built-in science-prior ensembles keep the configured control anchor fixed (17 Sv by default); explicit custom Monte Carlo ranges may sample it deliberately.",
        "RAPID-MOCHA observations at 26.5N.",
        "High",
    ),
    "amoc_reference_sv": _physical(
        "Reference preindustrial/present-day AMOC strength used to calibrate the control state.",
        "RAPID 26.5N mean about 16.9 Sv with large interannual variability; posterior target 14–19 Sv. Built-in science-prior ensembles keep the configured control anchor fixed (17 Sv by default); explicit custom Monte Carlo ranges may sample it deliberately.",
        "RAPID-MOCHA observations at 26.5N.",
        "High",
    ),
    "amoc_temperature_coupling": _physical(
        "Fraction of anomalous northern surface-temperature contrast allowed to affect the AMOC density driver.",
        "No direct observational CI. Built-in prior support: 0.40–1.00; v2.29.6 restores the unattenuated default of 1.00.",
        "Full anomalous thermal-density coupling is retained; reduced values remain available for sensitivity experiments and freshwater coefficients are held fixed.",
        "Low",
    ),
    "amoc_temperature_density_coupling": _physical(
        "Fraction of anomalous northern surface-temperature contrast allowed to affect the AMOC density driver.",
        "No direct observational CI. Built-in prior support: 0.40–1.00; v2.29.6 restores the unattenuated default of 1.00.",
        "Full anomalous thermal-density coupling is retained; reduced values remain available for sensitivity experiments and freshwater coefficients are held fixed.",
        "Low",
    ),
    "amoc_interhemispheric_temperature_coupling": _physical(
        "Contribution of the anomalous South-minus-North Atlantic surface-temperature contrast to the AMOC density driver.",
        "No direct observational CI. Built-in prior support: 0–0.20; default 0.08.",
        "Reduced representation of interhemispheric thermal-density control.",
        "Low",
    ),
    "amoc_adjustment": _physical(
        "E-folding time for overturning transport to approach its hydraulic density target.",
        "No direct CI. Built-in prior support: 1–30 years; default about 8 years.",
        "Large-scale ocean adjustment and reduced-model calibration.",
        "Medium",
    ),
    "amoc_adjustment_years": _physical(
        "E-folding time for overturning transport to approach its hydraulic density target.",
        "No direct CI. Built-in prior support: 1–30 years; default about 8 years.",
        "Large-scale ocean adjustment and reduced-model calibration.",
        "Medium",
    ),
    "amoc_heat_transport": _physical(
        "Overturning heat transport per Sverdrup of AMOC anomaly.",
        "No separately observed CI because RAPID constrains total heat transport. Built-in prior support: 0.015–0.080 PW/Sv; default 0.040.",
        "Seawater heat capacity times an effective upper/deep temperature contrast; checked against total RAPID heat transport near 1.2 PW.",
        "Medium",
    ),
    "amoc_heat_transport_pw_per_sv": _physical(
        "Overturning heat transport per Sverdrup of AMOC anomaly.",
        "No separately observed CI because RAPID constrains total heat transport. Built-in prior support: 0.015–0.080 PW/Sv; default 0.040.",
        "Seawater heat capacity times an effective upper/deep temperature contrast; checked against total RAPID heat transport near 1.2 PW.",
        "Medium",
    ),
    "amoc_surface_heat_coupling": _physical(
        "Fraction of diagnosed AMOC heat-transport anomaly applied directly to the surface mixed layer.",
        "No observational CI. Built-in prior support: 0.02–0.80; default 0.075.",
        "Unresolved partition between surface expression, gyres, atmosphere, and vertical redistribution.",
        "Low",
    ),
    "amoc_surface_heat_coupling_fraction": _physical(
        "Fraction of diagnosed AMOC heat-transport anomaly applied directly to the surface mixed layer.",
        "No observational CI. Built-in prior support: 0.02–0.80; default 0.075.",
        "Unresolved partition between surface expression, gyres, atmosphere, and vertical redistribution.",
        "Low",
    ),
    "amoc_heat_response_damping": _physical(
        "Conservative regional damping that transfers heat between Atlantic and non-Atlantic reservoirs when an AMOC temperature contrast develops.",
        "No direct observational CI. Built-in prior support: 0.20–5.0 W/m2/K; default 1.35.",
        "Unresolved atmospheric compensation, gyre exchange, and regional radiative damping.",
        "Low",
    ),
    "amoc_heat_response_damping_wm2_k": _physical(
        "Conservative regional damping that transfers heat between Atlantic and non-Atlantic reservoirs when an AMOC temperature contrast develops.",
        "No direct observational CI. Built-in prior support: 0.20–5.0 W/m2/K; default 1.35.",
        "Unresolved atmospheric compensation, gyre exchange, and regional radiative damping.",
        "Low",
    ),
    "atlantic_gyre_heat_transport": _physical(
        "Reference Atlantic heat transport attributed to wind-driven gyres rather than overturning.",
        "No single observational CI for the model decomposition. Built-in prior support: 0.10–1.00 PW; default 0.52 PW. Total RAPID transport is about 1.2 PW.",
        "RAPID total heat transport plus a reduced overturning/gyre decomposition.",
        "Medium",
    ),
    "atlantic_gyre_heat_transport_pw": _physical(
        "Reference Atlantic heat transport attributed to wind-driven gyres rather than overturning.",
        "No single observational CI for the model decomposition. Built-in prior support: 0.10–1.00 PW; default 0.52 PW. Total RAPID transport is about 1.2 PW.",
        "RAPID total heat transport plus a reduced overturning/gyre decomposition.",
        "Medium",
    ),
    "amoc_density_exponent": _physical(
        "Power-law sensitivity of hydraulic overturning transport to signed density contrast.",
        "No observational CI. Built-in prior support: 0.8–2.5; default 1.50.",
        "Hydraulic scaling in conceptual and reduced-complexity overturning models.",
        "Low",
    ),
    "amoc_density_transport_exponent": _physical(
        "Power-law sensitivity of hydraulic overturning transport to signed density contrast.",
        "No observational CI. Built-in prior support: 0.8–2.5; default 1.50.",
        "Hydraulic scaling in conceptual and reduced-complexity overturning models.",
        "Low",
    ),
    "amoc_depth_exponent": _physical(
        "Power-law dependence of hydraulic overturning transport on pycnocline depth.",
        "No direct CI. Built-in prior support: 0.2–2.0; default 1.0.",
        "Pycnocline-theory scaling reduced to one exponent.",
        "Low",
    ),
    "amoc_hydraulic_transport_max_sv": _physical(
        "Smooth upper bound for positive hydraulic AMOC targets after collapse or strong salinity rebound.",
        "No direct observational CI. Default 20 Sv; values below the 17 Sv control strength are unchanged and stronger targets saturate smoothly.",
        "Reduced hydraulic-drag and source-water-depletion closure.",
        "Low",
    ),
    "amoc_hydraulic_depth_exponent": _physical(
        "Power-law dependence of hydraulic overturning transport on pycnocline depth.",
        "No direct CI. Built-in prior support: 0.2–2.0; default 1.0.",
        "Pycnocline-theory scaling reduced to one exponent.",
        "Low",
    ),
    "amoc_eddy_depth_exponent": _physical(
        "Power-law dependence of Southern Ocean eddy outflow on pycnocline depth.",
        "No direct CI. Built-in prior support: 0.5–4.0; default 2.0.",
        "Southern Ocean eddy-compensation scaling.",
        "Low",
    ),
    "amoc_collapse_threshold": _physical(
        "Diagnostic threshold below which output is labelled collapsed. It does not alter the dynamics.",
        "No universal observational threshold. Default 6 Sv is the weak/collapsed reporting convention used by the ensemble outputs.",
        "Diagnostic classification choice.",
        "Low",
    ),
    "amoc_collapse_threshold_sv": _physical(
        "Diagnostic threshold below which output is labelled collapsed. It does not alter the dynamics.",
        "No universal observational threshold. Default 6 Sv is the weak/collapsed reporting convention used by the ensemble outputs.",
        "Diagnostic classification choice.",
        "Low",
    ),
    "amoc_reference_density_driver": _physical(
        "Fixed absolute density-driver scale used to screen control-state hydrography before per-member anomaly normalization.",
        "Built-in prior support: 4.0e-4–1.5e-3; default 7.5e-4 in the model's nondimensional linear equation-of-state units.",
        "Canonical control-state north-south thermal and salinity density contrast.",
        "Medium",
    ),
    "amoc_minimum_initial_density_ratio": _physical(
        "Minimum accepted absolute initial density margin relative to the reference density driver.",
        "Default 0.68. Members below this value are rejected as physically fragile before simulation.",
        "Joint hydrographic prior constraint.",
        "Medium",
    ),
    "amoc_maximum_initial_density_ratio": _physical(
        "Maximum accepted absolute initial density margin relative to the reference density driver.",
        "Default 1.25. This prevents unrealistically over-stable initial hydrography.",
        "Joint hydrographic prior constraint.",
        "Medium",
    ),
    "amoc_enforce_initial_density_constraint": _op(
        "Rejects initial salinity combinations whose absolute AMOC density margin lies outside the configured physical range."
    ),
    "amoc_allow_reversal": _op(
        "Allows the scalar hydraulic closure to produce negative AMOC. Disabled by default because reversed circulation requires separate physical validation."
    ),
    "amoc_coupling_scheme": _op(
        "Chooses the integration scheme for the coupled Greenland freshwater, salinity, convection, pycnocline and AMOC state. Euler reproduces v2.17.0; Heun is a predictor-corrector structural-uncertainty experiment."
    ),

    # Convection and pycnocline closure.
    "amoc_convection_critical_density_ratio": _physical(
        "Local northern surface-to-deep density ratio at the midpoint of the continuous deep-convection response.",
        "No observational CI. Built-in prior support: 0.84–0.97; default 0.91 after joint SSP5-8.5 and hosing calibration.",
        "Reduced-model convection response centre; it does not trigger a discrete collapsed state.",
        "Low",
    ),
    "amoc_convection_transition_width": _physical(
        "Width of the smooth density interval over which deep-convection efficiency changes.",
        "No observational CI. Built-in prior support: 0.015–0.12; default 0.035.",
        "Represents spatial and temporal heterogeneity of deep-convection weakening.",
        "Low",
    ),
    "amoc_convection_density_scale_factor": _physical(
        "Normalization scale applied to the local northern surface-to-deep density anomaly.",
        "No direct observational CI. Built-in prior support: 1.2–6.0; v2.28.1 default 4.00.",
        "Maps box-model density anomalies onto a nondimensional convection stability metric.",
        "Low",
    ),
    "amoc_convection_minimum_fraction": _physical(
        "Residual diagnosed convection efficiency under strongly stratified conditions.",
        "No direct CI. Built-in prior support: 0–0.30; default 0.02.",
        "Background mixing and incomplete shutdown represented as an emulator floor.",
        "Low",
    ),
    "amoc_convection_transport_exponent": _physical(
        "Exponent linking prognostic deep-convection efficiency directly to overturning transport.",
        "No observational CI. Built-in prior support: 0.5–1.5; default 1.0.",
        "Required coupling between sinking efficiency and AMOC transport in this reduced model.",
        "Low",
    ),
    "amoc_convective_mixing_reference_sv": _physical(
        "Maximum continuous salt exchange between the northern surface box and deep Atlantic caused by active convection.",
        "No direct observational CI. Built-in prior support: 1–12 Sv; default 5 Sv.",
        "Represents entrainment of saline deep water during active deep-water formation.",
        "Low",
    ),
    "amoc_convective_mixing_exponent": _physical(
        "Exponent controlling how rapidly convective salt exchange disappears as convection efficiency weakens.",
        "No direct observational CI. Built-in prior support: 1–4; default 2.",
        "Continuous nonlinear closure for convective entrainment.",
        "Low",
    ),
    "amoc_convection_entrainment_feedback": _physical(
        "Continuous density support supplied by active convective entrainment and lost as convection weakens.",
        "No direct observational CI. Built-in prior support: 0–0.25; default 0.10.",
        "Allows nonlinear convection-memory behaviour without a Boolean collapse or restart command.",
        "Low",
    ),
    "amoc_convection_adjustment_years": _physical(
        "E-folding time for convection efficiency to weaken after density conditions deteriorate.",
        "No direct CI. Built-in prior support: 2–80 years; default 20.",
        "Observed/modelled convection variability aggregated into one timescale.",
        "Low",
    ),
    "amoc_convection_recovery_years": _physical(
        "E-folding time for convection efficiency to recover after density conditions improve.",
        "No direct CI. Built-in prior support: 10–300 years; default 80.",
        "Calibrated to retain at least 80% idealized hosing recovery while avoiding abrupt multi-century restart overshoot.",
        "Low",
    ),
    "amoc_pycnocline_depth": _physical(
        "Initial effective depth of the Atlantic pycnocline/thermocline reservoir.",
        "No single observational CI for this model quantity. Built-in prior support: 300–1200 m; default 700 m.",
        "Atlantic thermocline structure compressed into one effective depth.",
        "Medium",
    ),
    "amoc_initial_pycnocline_depth_m": _physical(
        "Initial effective depth of the Atlantic pycnocline/thermocline reservoir.",
        "No single observational CI for this model quantity. Built-in prior support: 300–1200 m; default 700 m.",
        "Atlantic thermocline structure compressed into one effective depth.",
        "Medium",
    ),
    "amoc_pycnocline_area": _physical(
        "Effective horizontal area used to convert pycnocline volume convergence into depth change.",
        "No formal CI. Default 1e14 m2 is an order-of-magnitude Atlantic area scale.",
        "Atlantic basin geometry represented by one effective area.",
        "Medium",
    ),
    "amoc_pycnocline_area_m2": _physical(
        "Effective horizontal area used to convert pycnocline volume convergence into depth change.",
        "No formal CI. Default 1e14 m2 is an order-of-magnitude Atlantic area scale.",
        "Atlantic basin geometry represented by one effective area.",
        "Medium",
    ),
    "amoc_pycnocline_feedback_strength": _physical(
        "Fraction of the pycnocline-depth anomaly allowed to feed back onto northern sinking transport.",
        "No observational CI. Built-in prior support: 0–0.50; default 0.10.",
        "Reduced feedback coefficient chosen to avoid unrealistic algebraic self-restoration.",
        "Low",
    ),
    "amoc_pycnocline_relaxation_years": _physical(
        "E-folding time for pycnocline depth to relax toward its transport-balance target.",
        "No direct CI. Built-in prior support: 40–500 years; default 150.",
        "Thermocline adjustment in reduced pycnocline models.",
        "Low",
    ),
    "amoc_ekman_inflow": _physical(
        "Reference Southern Ocean wind-driven inflow into the Atlantic pycnocline budget.",
        "Built-in prior support: 10–40 Sv; default 25 Sv. Local Ekman components are observed, but this basin-integrated emulator transport is model dependent.",
        "Southern Ocean wind stress and pycnocline-model transport budgets.",
        "Medium",
    ),
    "amoc_ekman_inflow_sv": _physical(
        "Reference Southern Ocean wind-driven inflow into the Atlantic pycnocline budget.",
        "Built-in prior support: 10–40 Sv; default 25 Sv. Local Ekman components are observed, but this basin-integrated emulator transport is model dependent.",
        "Southern Ocean wind stress and pycnocline-model transport budgets.",
        "Medium",
    ),
    "amoc_upwelling": _physical(
        "Reference low-latitude diapycnal upwelling from the deep reservoir into the upper ocean.",
        "No direct CI. Built-in prior support: 1–12 Sv; default 5 Sv.",
        "Global overturning water-mass budget and reduced pycnocline theory.",
        "Low",
    ),
    "amoc_upwelling_reference_sv": _physical(
        "Reference low-latitude diapycnal upwelling from the deep reservoir into the upper ocean.",
        "No direct CI. Built-in prior support: 1–12 Sv; default 5 Sv.",
        "Global overturning water-mass budget and reduced pycnocline theory.",
        "Low",
    ),
    "amoc_eddy_outflow": _physical(
        "Reference Southern Ocean eddy outflow opposing Ekman inflow in the pycnocline budget.",
        "No direct CI. Built-in prior support: 4–25 Sv; default 13 Sv.",
        "Southern Ocean eddy compensation in reduced pycnocline models.",
        "Medium",
    ),
    "amoc_eddy_outflow_reference_sv": _physical(
        "Reference Southern Ocean eddy outflow opposing Ekman inflow in the pycnocline budget.",
        "No direct CI. Built-in prior support: 4–25 Sv; default 13 Sv.",
        "Southern Ocean eddy compensation in reduced pycnocline models.",
        "Medium",
    ),
    "amoc_north_gyre": _physical(
        "Symmetric salt exchange between the northern and tropical Atlantic boxes.",
        "No direct observational CI. Built-in prior support: 1–12 Sv; default 5 Sv.",
        "Effective gyre and diffusive salt exchange; constrained mainly by model response.",
        "Low",
    ),
    "amoc_north_tropical_gyre_sv": _physical(
        "Symmetric salt exchange between the northern and tropical Atlantic boxes.",
        "No direct observational CI. Built-in prior support: 1–12 Sv; default 5 Sv.",
        "Effective gyre and diffusive salt exchange; constrained mainly by model response.",
        "Low",
    ),
    "amoc_southern_gyre": _physical(
        "Symmetric salt exchange between tropical and southern Atlantic surface boxes.",
        "No direct observational CI. Built-in prior support: 3–22 Sv; default 10 Sv.",
        "Effective South Atlantic gyre and diffusive salt exchange.",
        "Low",
    ),
    "amoc_tropical_southern_gyre_sv": _physical(
        "Symmetric salt exchange between tropical and southern Atlantic surface boxes.",
        "No direct observational CI. Built-in prior support: 3–22 Sv; default 10 Sv.",
        "Effective South Atlantic gyre and diffusive salt exchange.",
        "Low",
    ),
    "amoc_southern_external_exchange_sv": _physical(
        "Conservative exchange of Southern Ocean salinity anomalies with the large external-ocean reservoir. The control-state salinity contrast is subtracted, so the calibrated initial equilibrium is unchanged.",
        "No directly observed box-model coefficient. Default 5 Sv; exploratory range 0–15 Sv.",
        "Represents unresolved Southern Ocean ventilation, eddy stirring, and exchange with ocean basins outside the reduced Atlantic box system.",
        "Low",
    ),
    "amoc_south_atlantic_external_exchange_sv": _physical(
        "Conservative exchange of South Atlantic upper-limb salinity anomalies with the external-ocean reservoir. It damps multi-century closed-box drift without restoring absolute salinity directly.",
        "No directly observed box-model coefficient. Default 2 Sv; exploratory range 0–10 Sv.",
        "Represents unresolved basin-boundary mixing and interbasin exchange affecting the upper limb entering the Atlantic.",
        "Low",
    ),
    "amoc_southern_ocean_structure": _op(
        "Chooses a fixed Southern Ocean closure or an explicit warming-sensitive Ekman/upwelling structural family.",
        "Structural model choice; the fixed option preserves legacy behaviour.",
        "Reduced-complexity AMOC structural uncertainty experiment.",
    ),
    "amoc_southern_wind_sensitivity_per_k": _physical(
        "Fractional increase in Southern Ocean Ekman inflow per degree of Southern Ocean warming in the warming-sensitive structure.",
        "Exploratory coefficient; default 0.06 K-1 and GUI range 0–0.20 K-1.",
        "Idealized representation of changing Southern Ocean winds and wind-driven transport.",
        "Low",
    ),
    "amoc_southern_upwelling_sensitivity_per_k": _physical(
        "Fractional increase in low-latitude/Southern Ocean upwelling per degree of Southern Ocean warming in the warming-sensitive structure.",
        "Exploratory coefficient; default 0.04 K-1 and GUI range 0–0.20 K-1.",
        "Idealized representation of changing overturning compensation and upwelling.",
        "Low",
    ),
    "amoc_southern_response_min_multiplier": _op(
        "Lower numerical bound applied to warming-sensitive Southern Ocean transport multipliers.",
        "Accepted interval (0, 1]; default 0.50.",
        "Structural experiment safeguard.",
    ),
    "amoc_southern_response_max_multiplier": _op(
        "Upper numerical bound applied to warming-sensitive Southern Ocean transport multipliers.",
        "Must be at least 1; default 1.75.",
        "Structural experiment safeguard.",
    ),
    "amoc_indo_pacific_compensation_mode": _op(
        "Chooses no Indo-Pacific compensation, diagnostic-only compensation, or an interactive compensation term in the pycnocline volume budget.",
        "Structural model choice; none preserves legacy behaviour and diagnostic mode does not alter the trajectory.",
        "Reduced-complexity interbasin overturning structural uncertainty experiment.",
    ),
    "amoc_indo_pacific_compensation_fraction": _physical(
        "Fraction of lost positive Atlantic overturning represented as compensating Indo-Pacific overturning.",
        "Accepted range 0–1; default 0.50.",
        "Exploratory structural coefficient rather than a calibrated forecast parameter.",
        "Low",
    ),
    "amoc_indo_pacific_compensation_max_sv": _physical(
        "Maximum diagnosed or interactive Indo-Pacific overturning compensation.",
        "Non-negative; default 10 Sv and GUI range 0–30 Sv.",
        "Exploratory structural cap.",
        "Low",
    ),
    "initial_fovs": _physical(
        "Initial overturning freshwater transport at about 34.5S. Negative values mean the overturning imports salt into the Atlantic.",
        "Observation-based estimate about -0.15 ± 0.09 Sv; model posterior interval -0.33 to +0.03 Sv. Built-in prior support: -0.60 to +0.30 Sv.",
        "Repeated XBT, Argo, reanalysis, and inverse estimates of South Atlantic freshwater transport.",
        "Medium",
    ),
    "initial_fovs_sv": _physical(
        "Initial overturning freshwater transport at about 34.5S. Negative values mean the overturning imports salt into the Atlantic.",
        "Observation-based estimate about -0.15 ± 0.09 Sv; model posterior interval -0.33 to +0.03 Sv. Built-in prior support: -0.60 to +0.30 Sv.",
        "Repeated XBT, Argo, reanalysis, and inverse estimates of South Atlantic freshwater transport.",
        "Medium",
    ),
    "fovs_reference_salinity": _physical(
        "Reference salinity S0 in the FovS freshwater-transport definition.",
        "No statistical CI is required; 35 PSU is a conventional reference near Atlantic mean salinity. GUI range 34–36 PSU.",
        "Definition of equivalent freshwater transport.",
        "High",
    ),
    "fovs_reference_salinity_psu": _physical(
        "Reference salinity S0 in the FovS freshwater-transport definition.",
        "No statistical CI is required; 35 PSU is a conventional reference near Atlantic mean salinity. GUI range 34–36 PSU.",
        "Definition of equivalent freshwater transport.",
        "High",
    ),
    "initial_southern_salinity_psu": _physical(
        "Initial Southern Ocean surface-box salinity.",
        "Built-in prior support: 34.20–34.90 PSU and an additional absolute density-margin rejection filter.",
        "Hydrographic observations aggregated into a basin-scale box.",
        "High",
    ),
    "initial_north_salinity_psu": _physical(
        "Initial northern/deep source-water salinity used by the box model.",
        "Built-in prior support: 34.85–35.45 PSU and an additional absolute density-margin rejection filter.",
        "North Atlantic hydrography aggregated into a box-model state.",
        "High",
    ),

    # Hysteresis experiment.
    "run_amoc_hysteresis": _op("Runs the equilibrium root-continuation and Jacobian-stability diagnostic rather than a transient ramp."),
    "hysteresis_max_hosing": _op("Largest Atlantic-compensated freshwater forcing searched by the equilibrium continuation."),
    "hysteresis_step": _op("Freshwater forcing increment used to map equilibrium branches.", "User-defined numerical resolution; 0.025–0.10 Sv options. Smaller steps resolve fold thresholds more precisely.", "Continuation-grid resolution."),
    "hysteresis_years_per_step": _op("Legacy transient-ramp duration. It is not used by the equilibrium root solver."),
    "hysteresis_spinup_years": _op("Legacy transient-ramp spin-up. It is not used by the equilibrium root solver."),

    # Monte Carlo controls.
    "monte_carlo_enabled": _op("Runs an ensemble in which selected parameters are sampled rather than held fixed."),
    "mc_constraint_mode": _op("Selects no weighting, AR6 climate weighting, or AR6 climate plus AMOC weighting.", "Method choice. Weight quality is reported using effective sample size and weight concentration.", "Bayesian-style calibration design."),
    "mc_runs": _op("Number of sampled ensemble members.", "Numerical choice. Hundreds may explore a few parameters; high-dimensional posterior work commonly needs thousands or more."),
    "mc_workers": _op("Number of parallel worker processes. Zero selects automatically, capped by the application."),
    "mc_member_timeout_seconds": _op("Maximum wall-clock time allowed for one ensemble member. A stalled member is terminated, recorded as failed, and checkpointed so the ensemble can continue."),
    "mc_heartbeat_seconds": _op("Maximum interval between progress messages while workers are active, including periods when no member completes."),
    "mc_resume": _op("Reuses compatible atomic checkpoints from the selected output folder. Monte Carlo runs resume by member; CO2 sweeps additionally resume each completed member-target simulation. Checkpoints with a different configuration fingerprint are rejected."),
    "mc_retry_failed_on_resume": _op("Retries failed or timed-out member checkpoints when a saved run is resumed. Successful member and target checkpoints remain reusable.", "Enabled by default; disable only when preserved failures should remain final."),
    "mc_seed": _op("Random or quasi-random sequence seed. A nonzero value makes sampling reproducible."),
    "mc_design": _op("Space-filling design used to generate unit-cube samples: Sobol, Latin hypercube, or pseudorandom."),
    "mc_sampling": _op("Marginal distribution used for custom min-max ranges when built-in physical priors are disabled."),
    "mc_use_science_defaults": _op("Replaces the custom range table with the built-in broad climate and AMOC prior set. Each parameter uses its own physically appropriate distribution, such as beta, log-normal, truncated normal, log-uniform, or uniform."),
    "mc_correlated_priors": _op("Applies documented Gaussian-copula correlations between selected physically related parameters. It changes which parameter combinations occur together but does not change their individual marginal ranges."),
    "mc_max_plotted": _op("Maximum number of individual ensemble curves drawn. Zero draws all successful members."),
    "mc_save_long_csv": _op("Writes every member-year result, which can create a large file."),
    "mc_no_plots": _op("Skips PNG rendering and writes numerical ensemble products only."),
    "mc_diagnose_each": _op("Runs extra ECS/TCR diagnostic experiments for every prior member even without posterior weighting."),
}


ALIASES: dict[str, str] = {
    "greenland_smb_enabled": "greenland_surface_mass_balance_enabled",
    "greenland_pdd_melt_factor": "greenland_pdd_melt_factor_gt_per_degree_day",
    # Streamlit/local names.
    "scenario_label": "scenario",
    "duration": "duration_years",
    "moist_lapse_weight": "moist_lapse_rate_weight",
    "hosing": "freshwater_hosing_sv",
    "forcing_mode_label": "forcing_mode",
    "ssp_before_label": "ssp_before",
    "ssp_after_label": "ssp_after",
    "cap_one_percent": "one_percent_cap_ppm",
    "ice_transition_width": "sea_ice_transition_width_c",
    "hydrological_north_fraction": "hydrological_freshwater_north_fraction",
    "greenland_threshold": "greenland_freshwater_threshold_c",
    "greenland_response_years": "greenland_freshwater_adjustment_years",
    "greenland_ice_mass_gt": "greenland_initial_ice_mass_gt",
    "greenland_max_freshwater": "greenland_max_freshwater_sv",
    "temperature_density_coupling": "amoc_temperature_density_coupling",
    "interhemispheric_temperature_coupling": "amoc_interhemispheric_temperature_coupling",
    "freshwater_compensation_label": "freshwater_compensation_mode",
    "run_hysteresis": "run_amoc_hysteresis",
    "pycnocline_depth": "amoc_initial_pycnocline_depth_m",
    "ekman_inflow": "amoc_ekman_inflow_sv",
    "upwelling": "amoc_upwelling_reference_sv",
    "eddy_outflow": "amoc_eddy_outflow_reference_sv",
    "north_gyre": "amoc_north_tropical_gyre_sv",
    "southern_gyre": "amoc_tropical_southern_gyre_sv",
    "southern_external_exchange": "amoc_southern_external_exchange_sv",
    "south_atlantic_external_exchange": "amoc_south_atlantic_external_exchange_sv",
    "amoc_southern_external_exchange": "amoc_southern_external_exchange_sv",
    "amoc_south_atlantic_external_exchange": "amoc_south_atlantic_external_exchange_sv",
    "density_exponent": "amoc_density_transport_exponent",
    "depth_exponent": "amoc_hydraulic_depth_exponent",
    "pycnocline_feedback_strength": "amoc_pycnocline_feedback_strength",
    "pycnocline_relaxation_years": "amoc_pycnocline_relaxation_years",
    "convection_critical_density_ratio": "amoc_convection_critical_density_ratio",
    "convection_transition_width": "amoc_convection_transition_width",
    "convection_density_scale_factor": "amoc_convection_density_scale_factor",
    "convection_minimum_fraction": "amoc_convection_minimum_fraction",
    "convection_transport_exponent": "amoc_convection_transport_exponent",
    "convective_mixing_reference": "amoc_convective_mixing_reference_sv",
    "convective_mixing_exponent": "amoc_convective_mixing_exponent",
    "convection_entrainment_feedback": "amoc_convection_entrainment_feedback",
    "convection_adjustment_years": "amoc_convection_adjustment_years",
    "convection_recovery_years": "amoc_convection_recovery_years",
    "eddy_depth_exponent": "amoc_eddy_depth_exponent",
    "co2_erf": "co2_doubling_erf_wm2",
    "co2_doubling_erf": "co2_doubling_erf_wm2",
    "co2_forcing_formula_label": "co2_forcing_formula",
    "co2_forcing_reference_n2o": "co2_forcing_reference_n2o_ppb",
    "arctic_lapse_rate_feedback": "arctic_lapse_rate_feedback_wm2_k",
    "arctic_module_start_latitude": "arctic_module_start_latitude_deg",
    "arctic_reference_air_seasonal_amplitude": "arctic_reference_air_seasonal_amplitude_c",
    "arctic_ice_area_melt_thickness": "arctic_ice_area_melt_thickness_m",
    "arctic_forced_ocean_heat_convergence_onset": "arctic_forced_ocean_heat_convergence_onset_warming_c",
    "arctic_forced_ocean_heat_convergence_saturation_scale": "arctic_forced_ocean_heat_convergence_saturation_scale_c",
    "arctic_phase_restoring_deficit_saturation": "arctic_phase_restoring_deficit_saturation_fraction",
    "arctic_phase_restoring_max_deficit_flux": "arctic_phase_restoring_max_deficit_flux_wm2",
    "arctic_max_local_ice_thickness": "arctic_max_local_ice_thickness_m",
    "arctic_max_equivalent_thickness": "arctic_max_equivalent_thickness_m",
    "arctic_ice_area_ridging_rate": "arctic_ice_area_ridging_fraction_per_year",
    "arctic_ice_area_divergence_rate": "arctic_ice_area_divergence_fraction_per_year",
    "arctic_ice_area_thin_pack_divergence_rate": "arctic_ice_area_thin_pack_divergence_fraction_per_year",
    "amoc_southern_ocean_structure_label": "amoc_southern_ocean_structure",
    "amoc_indo_pacific_mode_label": "amoc_indo_pacific_compensation_mode",
    "amoc_indo_pacific_compensation": "amoc_indo_pacific_compensation_mode",
    "amoc_southern_wind_sensitivity": "amoc_southern_wind_sensitivity_per_k",
    "amoc_southern_upwelling_sensitivity": "amoc_southern_upwelling_sensitivity_per_k",
    "amoc_southern_response_min": "amoc_southern_response_min_multiplier",
    "amoc_southern_response_max": "amoc_southern_response_max_multiplier",
    "amoc_indo_pacific_compensation_max": "amoc_indo_pacific_compensation_max_sv",
    "absolute_temperature": "absolute_map",
}


def resolve_setting_key(key: str) -> str:
    return ALIASES.get(key, key)


def setting_info(key: str) -> SettingInfo:
    resolved = resolve_setting_key(key)
    try:
        return SETTING_INFO[resolved]
    except KeyError as exc:
        raise KeyError(f"No tooltip metadata is defined for setting {key!r} (resolved to {resolved!r}).") from exc


# v2.29 structural Arctic controls.
SETTING_INFO.update({
    "arctic_basal_ocean_exchange_wm2_k": _physical(
        "Heat-exchange coefficient linking shallow Arctic ocean temperature to basal sea-ice melt.",
        "Default 10.0 W/m2/K; built-in prior support 6–30.", "Conservative ocean-to-ice transfer with equal-and-opposite bulk-ocean tendency.", "Low"),
    "arctic_basal_ocean_exchange": _physical(
        "Heat-exchange coefficient linking shallow Arctic ocean temperature to basal sea-ice melt.",
        "Default 10.0 W/m2/K; built-in prior support 6–30.", "Conservative ocean-to-ice transfer with equal-and-opposite bulk-ocean tendency.", "Low"),
    "arctic_open_water_ocean_exchange_wm2_k": _physical(
        "Two-way sensible-heat exchange between the explicit open-water reservoir and prognostic Arctic ocean.",
        "Default 25.0 W/m2/K; strictly positive and jointly constrained with unstable air-water exchange so warm open water remains physically damped.", "Replaces the former active 4 C open-water clipping behavior.", "Low"),
    "arctic_open_water_ocean_exchange": _physical(
        "Two-way sensible-heat exchange between the explicit open-water reservoir and prognostic Arctic ocean.",
        "Default 25.0 W/m2/K; strictly positive and jointly constrained with unstable air-water exchange so warm open water remains physically damped.", "Replaces the former active 4 C open-water clipping behavior.", "Low"),
    "arctic_lateral_ocean_heat_transport_wm2_per_ice_fraction": _physical(
        "Signed conservative lower-latitude ocean heat convergence proportional to Arctic ice-fraction anomaly.",
        "Default 25.0 W/m2 per unit ice fraction; zero disables the closure. The built-in prior assigns 20% probability to zero and otherwise samples 2–40 W/m2.",
        "Positive ice anomalies receive heat and negative ice anomalies export heat; the equal-and-opposite non-Arctic tendency preserves whole-domain energy while avoiding a one-sided recovery closure.", "Medium"),
    "arctic_lateral_ocean_heat_transport": _physical(
        "Signed conservative lower-latitude ocean heat convergence proportional to Arctic ice-fraction anomaly.",
        "Default 25.0 W/m2 per unit ice fraction; zero disables the closure. The built-in prior assigns 20% probability to zero and otherwise samples 2–40 W/m2.",
        "Positive ice anomalies receive heat and negative ice anomalies export heat; the equal-and-opposite non-Arctic tendency preserves whole-domain energy while avoiding a one-sided recovery closure.", "Medium"),
    "arctic_forced_ocean_heat_convergence_wm2_per_k": _physical(
        "Warming-driven conservative ocean heat convergence into the Arctic surface/ocean system.",
        "Default 8.0 W/m2/K; zero disables the forced convergence term.",
        "The response saturates with warming and is weighted by native ice cover; equal-and-opposite heat is removed from lower latitudes. Strength remains a phenomenological structural uncertainty.", "Medium"),
    "arctic_forced_ocean_heat_convergence": _physical(
        "Warming-driven conservative ocean heat convergence into the Arctic surface/ocean system.",
        "Default 8.0 W/m2/K; zero disables the forced convergence term.",
        "The response saturates with warming and is weighted by native ice cover; equal-and-opposite heat is removed from lower latitudes. Strength remains a phenomenological structural uncertainty.", "Medium"),
    "arctic_forced_ocean_heat_convergence_ice_fraction_exponent": _physical(
        "Optional exponent that attenuates warming-driven Arctic ocean heat convergence as native ice fraction decreases.",
        "Bounded [0,1]; default 1.0. The production response scales with remaining native ice cover; zero is retained as a no-attenuation sensitivity branch.",
        "Used with the bounded heat-convergence response so anomalous under-ice heat import declines as ice-covered receiving area disappears.", "Low"),
    "arctic_forced_ocean_heat_convergence_onset_warming_c": _physical(
        "Global-warming threshold above which forced conservative Arctic ocean heat convergence activates.",
        "Default 0.40 C; non-negative.",
        "Keeps the unforced/reference regime separate from the transient warming-driven convergence response.", "Medium"),
    "arctic_forced_ocean_heat_convergence_saturation_scale_c": _physical(
        "Saturation warming scale for enhanced Arctic Ocean heat convergence.",
        "Positive; default 0.45 C; built-in prior support 0.15-1.5 C.",
        "Makes the transient response approximately linear near onset but finite at larger warming.", "Low"
    ),
    "arctic_phase_restoring_deficit_saturation_fraction": _physical(
        "Ice-fraction scale that controls how quickly reverse-sign phase restoring saturates for a depleted transient pack.",
        "Default 0.14; valid range (0,1].",
        "Controls the transition away from the near-linear response; the maximum reverse flux is independently bounded.", "Medium"),
    "arctic_phase_restoring_max_deficit_flux_wm2": _physical(
        "Maximum magnitude of reverse-sign phase-restoring cooling applied to a depleted Arctic pack before the Arctic blend factor.",
        "Default 2.5 W/m2; must be positive.",
        "Separates the physical safety ceiling from the depletion saturation scale so tuning the transition cannot silently increase maximum regrowth forcing.", "Medium"),
    "arctic_winter_lead_closure_fraction": _physical(
        "Optional cold-season mechanical redistribution of existing sea-ice volume into unresolved leads when transient compactness falls below the control pack.",
        "Default 0.0; built-in prior includes an explicit zero branch and otherwise samples 0.0–0.60. One would close the eligible compactness deficit completely.",
        "Disabled by default because the former 0.65 calibration used an inhomogeneous raw March-area trend. When enabled, the operator conserves instantaneous volume but can alter subsequent conductive growth, so it is treated as structural uncertainty rather than an observationally calibrated process.", "Low"),
    "arctic_new_ice_local_thickness_m": _physical(
        "Small-volume local thickness approached by newly forming sea ice in the conservative concentration mapping.",
        "Default 0.25 m; built-in prior support 0.08–0.30 m.",
        "Prevents vanishing equivalent volume from being represented as isolated two-metre-thick ice. Concentration times local thickness remains exactly equal to grid-equivalent thickness.", "Medium"),
    "arctic_new_ice_local_thickness": _physical(
        "Small-volume local thickness approached by newly forming sea ice in the conservative concentration mapping.",
        "Default 0.25 m; built-in prior support 0.08–0.30 m.",
        "Prevents vanishing equivalent volume from being represented as isolated two-metre-thick ice. Concentration times local thickness remains exactly equal to grid-equivalent thickness.", "Medium"),
    "arctic_winter_lead_closure_onset_fraction": _physical(
        "Concentration deficit relative to the cold-season control pack allowed before mechanical lead closure begins.",
        "Default 0.01, corresponding to a one-percentage-point unresolved lead reserve.",
        "This avoids forcing small natural compactness changes back to the reference state while retaining a volume-conserving response to larger winter deficits.", "Low"),
    "arctic_winter_lead_closure_temperature_scale_c": _physical(
        "Temperature scale over which mechanical lead closure strengthens below the seawater freezing point.",
        "Default 15 C; the reference-air squared coldness ramp is nearly inactive in September and strongest in late winter. The actual-temperature gate becomes fully open one third of this scale below freezing (5 C at the default).",
        "Controls the seasonal envelope and near-melt suppression only; it does not add latent heat or ice volume.", "Low"),
    "arctic_winter_lead_closure_temperature_scale": _physical(
        "Temperature scale over which mechanical lead closure strengthens below the seawater freezing point.",
        "Default 15 C; the reference-air squared coldness ramp is nearly inactive in September and strongest in late winter. The actual-temperature gate becomes fully open one third of this scale below freezing (5 C at the default).",
        "Controls the seasonal envelope and near-melt suppression only; it does not add latent heat or ice volume.", "Low"),
    "arctic_atlantic_reference_ocean_temperature_c": _physical(
        "Reference shallow-ocean temperature for the Atlantic-influenced Arctic sector.",
        "Default 0.20 C; independent of exchange coefficients.",
        "Sets the control climatology while transient coupling strength is controlled separately.", "Low"),
    "arctic_atlantic_reference_ocean_temperature": _physical(
        "Reference shallow-ocean temperature for the Atlantic-influenced Arctic sector.",
        "Default 0.20 C; independent of exchange coefficients.",
        "Sets the control climatology while transient coupling strength is controlled separately.", "Low"),
    "arctic_non_atlantic_reference_ocean_temperature_c": _physical(
        "Reference shallow-ocean temperature for the central-Arctic sector.",
        "Default -0.80 C; independent of exchange coefficients.",
        "Sets the control climatology while transient coupling strength is controlled separately.", "Low"),
    "arctic_non_atlantic_reference_ocean_temperature": _physical(
        "Reference shallow-ocean temperature for the central-Arctic sector.",
        "Default -0.80 C; independent of exchange coefficients.",
        "Sets the control climatology while transient coupling strength is controlled separately.", "Low"),
    "arctic_reference_ocean_heat_capacity_wyr_m2_k": _physical(
        "Effective heat capacity of the sector-specific periodic shallow Arctic reference ocean.",
        "Default 6.0 W yr/m2/K.", "Controls seasonal reference-ocean thermal inertia without adding transient energy.", "Low"),
    "arctic_reference_ocean_heat_capacity": _physical(
        "Effective heat capacity of the sector-specific periodic shallow Arctic reference ocean.",
        "Default 6.0 W yr/m2/K.", "Controls seasonal reference-ocean thermal inertia without adding transient energy.", "Low"),
    "arctic_reference_ocean_restoring_wm2_k": _physical(
        "Restoring heat convergence that closes the periodic shallow Arctic reference-ocean budget.",
        "Default 12.0 W/m2/K.", "Balances the reference surface exchange while allowing a seasonal ocean cycle.", "Low"),
    "arctic_reference_ocean_restoring": _physical(
        "Restoring heat convergence that closes the periodic shallow Arctic reference-ocean budget.",
        "Default 12.0 W/m2/K.", "Balances the reference surface exchange while allowing a seasonal ocean cycle.", "Low"),
    "arctic_open_water_stable_exchange_wm2_k": _physical(
        "Open-water/air sensible exchange under stable stratification (air warmer than water).",
        "Default 0.50 W/m2/K; active v2.29 structural control.",
        "Smooth stability-dependent turbulent exchange.", "Low"),
    "arctic_open_water_stable_exchange": _physical(
        "Open-water/air sensible exchange under stable stratification (air warmer than water).",
        "Default 0.50 W/m2/K; active v2.29 structural control.",
        "Smooth stability-dependent turbulent exchange.", "Low"),
    "arctic_open_water_unstable_exchange_wm2_k": _physical(
        "Open-water/air sensible exchange when water is warmer than air.",
        "Default 5.0 W/m2/K; jointly constrained with open-water/ocean exchange by the public-configuration safety check.",
        "Smooth stability-dependent turbulent exchange.", "Low"),
    "arctic_open_water_unstable_exchange": _physical(
        "Open-water/air sensible exchange when water is warmer than air.",
        "Default 5.0 W/m2/K; jointly constrained with open-water/ocean exchange by the public-configuration safety check.",
        "Smooth stability-dependent turbulent exchange.", "Low"),
    "arctic_open_water_exchange_transition_c": _physical(
        "Temperature width of the stable-to-unstable open-water exchange transition.",
        "Default 0.50 C.", "Hyperbolic-tangent stability transition.", "Low"),
    "arctic_open_water_exchange_transition": _physical(
        "Temperature width of the stable-to-unstable open-water exchange transition.",
        "Default 0.50 C.", "Hyperbolic-tangent stability transition.", "Low"),
    "arctic_transient_shortwave_scale": _physical(
        "Fraction of the local sea-ice albedo anomaly that reaches the surface after cloud masking.",
        "Bounded [0,1.2]; default 1.00 with built-in prior support 0.50-1.20.", "Transient-only shortwave anomaly scaling; control climatology is unchanged.", "Low"),
    "arctic_interface_longwave_damping_wm2_k": _physical(
        "Temperature-dependent net longwave damping of Arctic ice and open-water surface anomalies.",
        "Default 2.2 W/m2/K; built-in prior support 1.5–4.5 W/m2/K.",
        "Represents the net upward longwave response after unresolved downwelling-atmospheric compensation; it is active in both ice-surface equilibrium and open-water heat loss.", "Medium"),
    "arctic_interface_longwave_damping": _physical(
        "Temperature-dependent net longwave damping of Arctic ice and open-water surface anomalies.",
        "Default 2.2 W/m2/K; built-in prior support 1.5–4.5 W/m2/K.",
        "Represents the net upward longwave response after unresolved downwelling-atmospheric compensation; it is active in both ice-surface equilibrium and open-water heat loss.", "Medium"),
    "arctic_ice_surface_exchange_wm2_k": _physical(
        "Sensible heat exchange between the Arctic air column and the ice/snow surface.",
        "Positive tuning-informed coefficient; default 5.0 W/m2/K with built-in prior support 3.0-8.0 W/m2/K.",
        "Controls how efficiently atmospheric warming reaches the thermodynamic ice surface without changing the control reference state.",
        "Low",
    ),
    "arctic_ice_surface_exchange": _physical(
        "Sensible heat exchange between the Arctic air column and the ice/snow surface.",
        "Positive tuning-informed coefficient; default 5.0 W/m2/K with built-in prior support 3.0-8.0 W/m2/K.",
        "Controls how efficiently atmospheric warming reaches the thermodynamic ice surface without changing the control reference state.",
        "Low",
    ),
    "arctic_air_low_pass_years": _physical(
        "Memory timescale of the reported Arctic near-surface-air diagnostic.",
        "Default 0.15 years.", "Exponential diagnostic filter; conserved instantaneous air energy is unchanged.", "Low"),
    "arctic_air_memory_years": _physical(
        "Memory timescale of the reported Arctic near-surface-air diagnostic.",
        "Default 0.15 years.", "Exponential diagnostic filter; conserved instantaneous air energy is unchanged.", "Low"),
    "arctic_full_cover_equivalent_thickness_m": _physical(
        "Equivalent grid-cell ice thickness corresponding to full compact pack coverage in the conservative compactness curve.",
        "Default 3.70 m; built-in prior support 3.0-4.5 m.",
        "Concentration changes without changing latent heat or equivalent ice volume.", "Low"),
    "arctic_full_cover_equivalent_thickness": _physical(
        "Equivalent grid-cell ice thickness corresponding to full compact pack coverage in the conservative compactness curve.",
        "Default 3.70 m; built-in prior support 3.0-4.5 m.",
        "Concentration changes without changing latent heat or equivalent ice volume.", "Low"),
    "arctic_max_equivalent_thickness_m": _op(
        "Emergency fail-fast threshold for pathological grid-equivalent latent-energy ice states. It never clips or transfers latent energy.",
        "Default 20 m; deliberately outside validated climate states and excluded from science priors.",
        "Numerical safety control; crossing the threshold aborts rather than changing the model state."),
    "arctic_max_local_ice_thickness_m": _op(
        "Emergency fail-fast threshold for pathological unresolved local ice thickness. It never increases concentration or projected ice area.",
        "Default 500 m; deliberately outside validated climate states and excluded from science priors.",
        "Numerical safety control; crossing the threshold aborts rather than changing the model state."),
    "arctic_ice_concentration_exponent": _physical(
        "Curvature exponent of the compact-pack concentration curve above the thin-new-ice branch.",
        "Default 1.00; built-in prior support 0.25–2.5.",
        "The mapping is monotonic, has the configured thin-ice local-thickness limit, and reaches full concentration only at the declared full-cover equivalent thickness throughout the prior support.", "Low"),
    "arctic_ice_area_formation_temperature_scale_c": _physical(
        "Temperature scale for thermodynamic new-ice formation over open water.",
        "Positive; default 0.50 C.",
        "Controls the smooth freezing gate for lateral area gain without altering latent-energy conservation.", "Low"),
    "arctic_ice_area_formation_temperature_scale": _physical(
        "Temperature scale for thermodynamic new-ice formation over open water.",
        "Positive; default 0.50 C.",
        "Controls the smooth freezing gate for lateral area gain without altering latent-energy conservation.", "Low"),
    "arctic_ice_area_formation_volume_sensitivity": _physical(
        "Sensitivity of lateral new-area formation to seasonal ice-volume support relative to the periodic control.",
        "Non-negative; default 11.5.",
        "Prevents a thinned winter pack from instantly recovering full area while preserving the latent-energy budget.", "Low"),
    "arctic_ice_area_formation_support_floor": _physical(
        "Minimum anomaly-side winter new-ice formation support.",
        "Bounded [0,0.75] in the science prior; default 0.59.",
        "Prevents a depleted pack from mathematically eliminating refreezing while leaving the control orbit unchanged.", "Low"
    ),
    "arctic_ice_area_melt_thickness_m": _physical(
        "Local-thickness scale separating lateral area melt from vertical volume melt.",
        "Positive; default 0.70 m.",
        "Thin ice preferentially loses area while thick ice preferentially loses volume.", "Low"),
    "arctic_ice_area_lateral_melt_efficiency": _physical(
        "Maximum fraction of conservative melt energy expressed as lateral area retreat for vulnerable thin ice.",
        "Bounded [0,1]; default 0.62.",
        "Changes area-volume partitioning without adding heat or removing latent energy.", "Low"),
    "arctic_ice_area_thinning_melt_amplification": _physical(
        "Additional lateral-melt sensitivity to reference-relative seasonal pack thinning.",
        "Non-negative; default 2.0.",
        "Allows transient area retreat to emerge from reduced pack support rather than stronger atmospheric forcing.", "Low"),
    "arctic_ice_area_thick_pack_resistance_exponent": _physical(
        "Deprecated empirical resistance exponent that suppresses anomaly-only area retreat after surviving floes thicken above the periodic-control pack.",
        "Non-negative; production default 0.0 (disabled).",
        "The former default of 4 was tuned without an independent historical thickness/volume constraint. It remains available only for explicit structural experiments and should not be retuned against September area alone.", "Low"),
    "arctic_ice_area_compaction_years": _physical(
        "Timescale for removing prognostic area unsupported by the smooth compact-pack envelope.",
        "Positive; default 0.207 years.",
        "The operator only removes area and cannot close leads or create ice volume.", "Low"),
    "arctic_ice_area_ridging_threshold": _physical(
        "Concentration threshold above which winter ridging and rafting reduce area at fixed volume.",
        "Bounded [0,1]; default 0.80.",
        "Represents mechanical thickening of compact pack at conserved ice volume.", "Low"),
    "arctic_ice_area_ridging_fraction_per_year": _physical(
        "Maximum fixed-volume area reduction from ridging and rafting.",
        "Non-negative; default 0.25 per year.",
        "Acts only in cold, dark, compact conditions.", "Low"),
    "arctic_ice_area_divergence_fraction_per_year": _physical(
        "Background lead-opening and divergence rate that reduces covered area at fixed volume.",
        "Non-negative; default 0.0 per year.",
        "Optional non-anomalous mechanical opening; disabled in the calibrated production defaults.", "Low"),
    "arctic_ice_area_thin_pack_divergence_fraction_per_year": _physical(
        "Reference-relative deformation and lead-opening rate for a seasonally weakened pack.",
        "Non-negative; default 0.30 per year.",
        "Responds to transient volume-support loss with cold-season weighting and remains inactive in the periodic control.", "Low"),
    "arctic_greenland_marine_influence": _physical(
        "Weight of Arctic marine temperature anomalies in the aggregate Greenland temperature driver.",
        "Bounded [0,0.25]; default 0.10 and sampled by the built-in Monte Carlo prior.",
        "Reduced coupling for scenario-sensitivity experiments, not outlet-glacier prediction.", "Low"),
    "amoc_stratification_saturation_c": _physical(
        "Smooth saturation scale for unresolved AMOC thermal stratification anomalies.",
        "Positive; default 0.60 C.",
        "Reduced closure representing compensating deep-ocean warming and mixing.", "Low"),
})

def setting_tooltip(key: str, extra_note: str = "") -> str:
    return setting_info(key).tooltip(extra_note=extra_note)
