# Arctic observational recalibration — v2.29.28

## Result

The selected canonical 10-degree, `dt=0.05` exact run changes the active Arctic physics and improves historical trend, recent-period area, PIOMAS volume, and ICESat-2 thickness together. Full temporal thickness validation remains incomplete because CryoSat-2 correlation fails.

## Selected defaults

| Parameter | v2.29.27 | v2.29.28 |
|---|---:|---:|
| `arctic_new_ice_local_thickness_m` | 0.22 m | **0.22 m** |
| `arctic_winter_transport_enhancement` | 10.0 W/m2/K | **19.0 W/m2/K** |
| `arctic_ice_concentration_exponent` | 0.56 | **1.00** |
| `arctic_ice_nonsolar_heat_loss_wm2` | 47.8 W/m2 | **51.0 W/m2** |
| `arctic_ice_area_thinning_melt_amplification` | 4.0 | **2.0** |
| `arctic_ice_area_thin_pack_divergence_fraction_per_year` | 0.80 | **0.30** |
| `arctic_ice_mechanical_max_local_thickness_m` | — | **12.0 m** |
| `arctic_ice_export_onset_equivalent_thickness_m` | 0.82 m | **0.90 m** |
| `arctic_ice_export_timescale_years` | 0.14 yr | **0.24 yr** |
| `arctic_ice_area_formation_volume_sensitivity` | 4.0 | **11.5** |
| `arctic_ice_area_formation_support_floor` | — | **0.59** |
| `arctic_forced_ocean_heat_convergence_wm2_per_k` | 7.5 | **8.0** |
| `arctic_forced_ocean_heat_convergence_onset_warming_c` | 0.45 C | **0.40 C** |
| `arctic_forced_ocean_heat_convergence_saturation_scale_c` | 0.32 C | **0.45 C** |
| `arctic_forced_ocean_heat_convergence_ice_fraction_exponent` | 1.0 | **1.0** |

## Exact 1850-start evidence

- G02202 1979–2020 March/September fixed-mask area RMSE: **0.5036 / 0.5293 M km2**.
- March trend: model **-0.3954** vs observed **-0.4085 M km2/decade**; ratio **0.9678**; 95% OLS intervals overlap.
- September trend: model **-0.8131** vs observed **-0.8461 M km2/decade**; ratio **0.9610**; 95% OLS intervals overlap.
- 2021–2025 March/September RMSE: **0.3703 / 0.3580 M km2**, both below 0.50.
- PIOMAS volume nRMSE **0.1883**, mean bias **-7.67%**, correlation **0.934**.
- CryoSat-2 thickness nRMSE **0.0903**, bias **-0.150 m**, correlation **-0.123** (temporal gate FAIL).
- ICESat-2 thickness nRMSE **0.1735**, bias **+0.283 m**, correlation **+0.692**.

The selected evidence is stored in `ARCTIC_OBSERVATIONAL_RECALIBRATION_10DEG_2026.json`.

## OSI SAF role

OSI SAF is explicitly **not independent validation** because it was inspected during method development. It is retained as a cross-dataset diagnostic. March/September RMSE is **1.0461 / 0.5448 M km2** and neither value is a release gate.

## Coupled resolution evidence

Fresh 5° and 10° integrations both run from 1850 through 2100 and both pass their historical, recent-period, structural, Greenland/AMOC, and source-integrity gates. The cross-resolution differences are 0.196 M km2 in late March area, 0.072 M km2 in late September area, 0.013 C in late GMST, 0.308 in Arctic amplification, and 0.252 Sv in 2100 AMOC; all are below the predeclared limits. `version_matched_arctic_greenland_amoc_validation_complete` is therefore **True**.

## Retrospective fold-local evaluation

The invalid 1979 fold is removed. The valid cutoffs are 1989, 1999 and 2009. A fixed prior-derived candidate grid is selected independently inside each fold using only pre-cutoff observations; fitted baselines likewise use only pre-cutoff information. The grid and model architecture were nevertheless developed after the historical record had already been inspected, so this is **retrospective method-development evidence, not independent nested validation**. The model does not beat every required baseline, so `scientific_predictive_skill_claim_allowed` remains **False**.

## Remaining scientific blockers

CryoSat-2 temporal response, NSIDC-0611 v4 sea-ice-age evidence, predictive skill, and genuinely untouched prospective evaluation remain unresolved. `scientific_validation_complete` and `scientific_volume_thickness_validation_complete` therefore remain **False** even though the version-matched coupled engineering validation is complete.
