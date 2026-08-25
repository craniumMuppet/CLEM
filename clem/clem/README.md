# Emergent-Sensitivity Global Climate Model v2.29.28

> **Current corrected source:** fresh current-source 5°/10° coupled evidence and the post-change 143-test fingerprint pass. The package is an engineering release with observational recalibration; scientific predictive validation remains explicitly incomplete.

## Arctic sea-ice result

The canonical 10-degree, `dt=0.05` exact run from 1850 uses:

- `arctic_new_ice_local_thickness_m = 0.22 m`
- `arctic_winter_transport_enhancement = 19.0 W m-2 K-1`
- `arctic_ice_concentration_exponent = 1.00`
- `arctic_ice_nonsolar_heat_loss_wm2 = 51.0 W m-2`
- `arctic_ice_area_thinning_melt_amplification = 2.0`
- `arctic_ice_area_thin_pack_divergence_fraction_per_year = 0.30 yr-1`
- `arctic_ice_mechanical_max_local_thickness_m = 12.0 m`
- `arctic_ice_export_onset_equivalent_thickness_m = 0.90 m`
- `arctic_ice_export_timescale_years = 0.24 yr`
- `arctic_ice_area_formation_volume_sensitivity = 11.5`
- `arctic_ice_area_formation_support_floor = 0.59`
- `arctic_forced_ocean_heat_convergence_wm2_per_k = 8.0 W m-2 K-1`
- `arctic_forced_ocean_heat_convergence_onset_warming_c = 0.40 C`
- `arctic_forced_ocean_heat_convergence_saturation_scale_c = 0.45 C`
- `arctic_forced_ocean_heat_convergence_ice_fraction_exponent = 1.0`

The exact 1850-start 10° run gives G02202 1979–2020 RMSE of **0.504 M km2** in March and **0.529 M km2** in September. Model trends are **-0.395** and **-0.813 M km2/decade**, versus **-0.409** and **-0.846** observed; ratios are **0.968/0.961**, and both model 95% OLS trend intervals overlap the observed intervals. The inspected 2021–2025 RMSE is **0.370/0.358 M km2**, passing the restored 0.50 guards.

PIOMAS nRMSE improves to **0.1883**, mean volume bias to **-7.67%**, and correlation to **0.934**. ICESat-2 bias/correlation improve to **+0.283 m/+0.692**. CryoSat-2 mean-state nRMSE/bias are **0.0903/-0.150 m**, but temporal correlation is **-0.123**. The mean-state thickness/volume constraints pass; full temporal volume/thickness validation remains explicitly incomplete because the CryoSat-2 correlation gate fails.

The coarse-grid March extent remains about **28.5 M km2** and is diagnostic-only. No satellite-equivalent extent claim is made.

## Validation interpretation

OSI SAF is a **cross-dataset development diagnostic, not independent validation**, because it was inspected during method development. Its March RMSE is about **1.046 M km2** and its September RMSE about **0.545 M km2**; both values are reported and neither is a release gate.

Retrospective fold-local evaluation now uses only the valid 1989, 1999 and 2009 calibration cutoffs, a fixed prior-derived candidate grid declared before that bank was scored, and only pre-cutoff observations for candidate selection and baseline fitting. It remains method-development evidence because the model architecture itself was developed with the historical record visible. The model does not beat every required simple baseline, so no predictive-skill claim is allowed.

**Scientific predictive validation remains fail-closed.** NSIDC-0611 v4 is still unavailable in-package and genuinely untouched prospective evaluation is reserved for 2027 onward.

## Evidence integrity

Processed observational evidence is SHA-256 checked at runtime. `validate_v22928_coupled.py` stages exact 5° and 10° production runs, promotes canonical files only after both runs pass, and invokes a cross-resolution combiner. The finalizer independently requires passing per-resolution, cross-resolution, and current-source-hash evidence. Failed coupled JSON files cannot set completion.

Current 10° recalibration evidence is `ARCTIC_OBSERVATIONAL_RECALIBRATION_10DEG_2026.json`. The canonical 5°/10° result files and `VALIDATION_SUMMARY_V2_29_28.json` pass all engineering, recent-period, structural, coupled-attribution, and cross-resolution gates. The declared regression run is 143/143 passing and `TESTED_CODE_FINGERPRINT_V2_29_28.json` binds that evidence to the final source. Package info, manifest, and ZIP are emitted only by the strict named-root finalizer; their scientific-predictive status remains false.
