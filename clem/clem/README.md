# Emergent-Sensitivity Global Climate Model v2.29.28

> **Current model:** v2.29.28. This release repairs the Arctic historical-trend regression and the validation semantics found in the v2.29.27 review.

## Arctic sea-ice result

The canonical 10-degree, `dt=0.05` exact run from 1850 uses:

- `arctic_new_ice_local_thickness_m = 0.22 m`
- `arctic_ice_concentration_exponent = 0.56`
- `arctic_ice_nonsolar_heat_loss_wm2 = 47.8 W m-2`
- `arctic_ice_area_formation_volume_sensitivity = 11.5`
- `arctic_ice_area_formation_support_floor = 0.59`
- `arctic_forced_ocean_heat_convergence_wm2_per_k = 7.5 W m-2 K-1`
- `arctic_forced_ocean_heat_convergence_onset_warming_c = 0.45 C`
- `arctic_forced_ocean_heat_convergence_saturation_scale_c = 0.32 C`
- `arctic_forced_ocean_heat_convergence_ice_fraction_exponent = 1.0`

G02202 1979-2020 fixed-mask area passes both the original RMSE gates and explicit trend-fidelity gates: March RMSE **0.919 M km2**, September RMSE **0.929 M km2**, with model/observed trend-magnitude ratios **0.680** and **0.700** respectively. The 2021-2025 development-period RMSE is **0.702 M km2** in March and **0.735 M km2** in September. PIOMAS volume nRMSE is **0.2471**; CryoSat-2 and ICESat-2 thickness gates also pass.

The preindustrial periodic reference cycle remains inside its inherited physical bounds: March area about **14.32 M km2**, September about **6.78 M km2**, with a seasonal retreat of about **7.54 M km2**.

## Validation interpretation

OSI SAF is a **cross-dataset development diagnostic, not independent validation**, because it was inspected during method development. Its March RMSE is about **0.530 M km2** and its September RMSE is about **1.174 M km2**; the September mismatch is reported, not tuned away.

Retrospective fold-local evaluation now uses only the valid 1989, 1999 and 2009 calibration cutoffs, a fixed prior-derived candidate grid declared before that bank was scored, and only pre-cutoff observations for candidate selection and baseline fitting. It remains method-development evidence because the model architecture itself was developed with the historical record visible. The model does not beat every required simple baseline, so no predictive-skill claim is allowed.

**Scientific predictive validation remains fail-closed.** NSIDC-0611 v4 is still unavailable in-package and genuinely untouched prospective evaluation is reserved for 2027 onward.

## Evidence integrity

Processed observational evidence is SHA-256 checked at runtime. The tested-code fingerprint binds code, runtime scientific inputs, calibration evidence, retrospective-development evidence, test results, and release metadata. Release packaging refuses a tree that no longer matches the tested fingerprint.

Current v2.29.28 evidence is `ARCTIC_OBSERVATIONAL_RECALIBRATION_10DEG_2026.json`, `ARCTIC_FOLD_LOCAL_CANDIDATES_V2_29_28.json`, `RETROSPECTIVE_FOLD_LOCAL_ARCTIC_HINDCAST_V2_29_28.json`, `TEST_RESULTS_V2_29_28.*`, `TESTED_CODE_FINGERPRINT_V2_29_28.json`, `PACKAGE_INFO_V2_29_28.json`, and `PACKAGE_MANIFEST_V2_29_28.json`. Older evidence is retained for provenance only.
