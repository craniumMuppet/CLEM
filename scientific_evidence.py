"""Scientific evidence roles and mandatory interpretation metadata for v2.29.29."""
from __future__ import annotations

from typing import Any

SCIENTIFIC_USE_METADATA: dict[str, Any] = {
    "model_class": "reduced_complexity_climate_and_amoc_emulator",
    "intended_use": [
        "scenario sensitivity experiments",
        "process exploration",
        "software and hypothesis testing",
    ],
    "not_intended_use": [
        "precise regional climate forecasts",
        "operational sea-ice navigation",
        "deterministic AMOC collapse timing",
        "outlet-glacier or local Greenland projections",
    ],
    "components": {
        "sea_ice": {
            "role": (
                "native two-sector prognostic Northern Hemisphere sea-ice "
                "concentration, area, latent volume and thickness diagnostics "
                "with an unfitted 15%-threshold extent diagnostic"
            ),
            "historical_extent_reference": (
                "NOAA/NSIDC Sea Ice Index v4 March/September extent, 1979-2020; "
                "reported only as a coarse-zonal historical diagnostic because "
                "the model does not resolve satellite-scale spatial concentration"
            ),
            "raw_area_status": (
                "NOAA/NSIDC raw monthly area is retained only for provenance "
                "and is excluded from calibration, trend skill, and release gates "
                "because the changing satellite pole-hole mask makes the series inhomogeneous"
            ),
            "required_area_validation": (
                "homogeneous NOAA/NSIDC G02202 v6 concentration-derived sea-ice area "
                "calculated with the bundled fixed spatial mask and exact observation operator"
            ),
            "required_physical_validation": (
                "bundled PIOMAS v2.1 common-domain volume plus source-specific CryoSat-2 "
                "RDEFT4 v1 and ICESat-2 IS2SITMOGR4 v4 thickness operators"
            ),
            "validation_informed_development_period": "2021-2025; inspected during development and not independent",
            "prospective_untouched_period": "2027 onward; March 2026 was already inspected",
            "future_projection_role": (
                "native prognostic area and volume are sensitivity outputs; thickness and the "
                "unfitted 15%-threshold extent are sensitivity outputs as well; no "
                "observational area-to-extent multiplier is applied"
            ),
            "longitude_skill": (
                "none; the map projection carries the native two-sector state and "
                "does not represent longitude-resolved process forecast skill"
            ),
            "scientific_validation_status": (
                "incomplete: G02202 fixed-mask RMSE, trend-ratio, and trend-interval gates "
                "plus PIOMAS/CryoSat-2/ICESat-2 mean-state gates pass; the CryoSat-2 "
                "temporal-correlation gate fails, and the satellite products and OSI SAF "
                "are development-only rather than independent validation; NSIDC-0611 is available as a structural multiyear-ice diagnostic, "
                "retrospective fold-local prior-grid evaluation does not beat every required "
                "simple baseline, and untouched prospective validation is reserved for 2027 onward"
            ),
        },
        "arctic_open_water_temperature": {
            "role": "reduced-sector diagnostic",
            "validation": (
                "tuning-informed broad NOAA OISST descriptive sanity bounds using "
                "the model-derived Atlantic fraction mask; not a reproduced quantitative observational validation"
            ),
            "warning": "Do not interpret as a local, coastal, or point forecast.",
        },
        "amoc": {
            "role": "sensitivity emulator with full anomalous thermal-density coupling restored",
            "warning": "Scenario weakening and hosing response are sensitivity results, not precise collapse probability or timing forecasts.",
        },
        "greenland": {
            "role": "aggregate surface-mass-balance and discharge emulator",
            "warning": "Total contribution is scenario-sensitive; regional geometry and outlet-glacier evolution are not resolved.",
        },
    },
    "evidence_partition": {
        "tuning_informed_development_regressions": "IPCC/literature ranges and historical records inspected during development; not independent validation",
        "historical_extent_diagnostics": "NSIDC extent comparisons are coarse-zonal diagnostics, descriptive only and non-release-blocking, and are excluded from scientific release gates",
        "raw_nsidc_area": "provenance-only inhomogeneous record; excluded from calibration and skill claims",
        "retrospective_fold_local_evaluation": "valid 1989/1999/2009 cutoffs use predeclared prior-grid, pre-cutoff-only fold selection; retrospective method-development evidence only, not untouched prospective validation, and the required baseline skill gate fails",
        "arctic_observational_recalibration_2026": "G02202 level/trend gates and PIOMAS/CryoSat-2/ICESat-2 mean-state gates pass; CryoSat-2 temporal correlation fails, and all satellite/OSI evidence is development-informed",
        "prospective_untouched_temporal_evaluation": "reserved from 2027 onward",
        "tuning_informed_external_sanity_check": "broad NOAA OISST open-water temperature ranges inspected during development; not independent validation",
        "structural_tests": "conservation, control stability, timestep, hosing, resolution, native sea-ice integrity and software regressions",
    },
}


def add_scientific_use_metadata(output: dict[str, Any]) -> dict[str, Any]:
    """Attach a copy-safe scientific-use declaration to a result dictionary."""
    import copy

    output["scientific_use"] = copy.deepcopy(SCIENTIFIC_USE_METADATA)
    output["amoc_projection_role"] = "sensitivity_experiment_not_precise_forecast"
    output["greenland_projection_role"] = "aggregate_sensitivity_experiment_not_precise_forecast"
    output["arctic_open_water_temperature_role"] = "sector_diagnostic_not_local_forecast"
    output["sea_ice_future_projection_role"] = "native_prognostic_area_volume_thickness_with_unfitted_15pct_extent_sensitivity"
    output["sea_ice_scientific_validation_complete"] = False
    return output
