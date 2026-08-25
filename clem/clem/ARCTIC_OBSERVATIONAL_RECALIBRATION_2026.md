# Arctic observational recalibration — v2.29.28

## Result

The selected canonical 10-degree, `dt=0.05` exact run fixes the v2.29.27 weak historical decline while retaining the inherited preindustrial seasonal cycle and the PIOMAS/CryoSat-2/ICESat-2 physical gates.

## Selected defaults

| Parameter | v2.29.27 | v2.29.28 |
|---|---:|---:|
| `arctic_new_ice_local_thickness_m` | 0.22 m | **0.22 m** |
| `arctic_ice_concentration_exponent` | 0.60 | **0.56** |
| `arctic_ice_nonsolar_heat_loss_wm2` | 49.5 W/m2 | **47.8 W/m2** |
| `arctic_ice_area_formation_volume_sensitivity` | 4.0 | **11.5** |
| `arctic_ice_area_formation_support_floor` | — | **0.59** |
| `arctic_forced_ocean_heat_convergence_wm2_per_k` | 4.0 | **7.5** |
| `arctic_forced_ocean_heat_convergence_onset_warming_c` | 2.0 C | **0.45 C** |
| `arctic_forced_ocean_heat_convergence_saturation_scale_c` | — | **0.32 C** |
| `arctic_forced_ocean_heat_convergence_ice_fraction_exponent` | 1.0 | **1.0** |

## Exact 1850-start evidence

- G02202 1979-2020 March fixed-mask area RMSE: **0.91893 M km2** — PASS.
- G02202 1979-2020 September fixed-mask area RMSE: **0.92943 M km2** — PASS.
- March trend: model **-0.27772** vs observed **-0.40854 M km2/decade**; magnitude ratio **0.6798** — PASS against the >=2/3 gate.
- September trend: model **-0.59253** vs observed **-0.84615 M km2/decade**; magnitude ratio **0.7003** — PASS.
- 2021-2025 March RMSE: **0.70199 M km2** — PASS.
- 2021-2025 September RMSE: **0.73500 M km2** — PASS.
- PIOMAS volume nRMSE: **0.24708** — PASS against 0.25.
- CryoSat-2 thickness nRMSE: **0.05540** — PASS.
- ICESat-2 thickness nRMSE: **0.24609** — PASS.
- Preindustrial periodic-cycle March/September area: approximately **14.32 / 6.78 M km2** — PASS inherited climatology bounds.

The selected evidence is stored in `ARCTIC_OBSERVATIONAL_RECALIBRATION_10DEG_2026.json`.

## OSI SAF role

OSI SAF is explicitly **not independent validation** in v2.29.28 because the product was inspected during method development. It is retained as a cross-dataset development diagnostic. March RMSE is **0.52968 M km2**; September RMSE is **1.17400 M km2** and remains a disclosed mismatch.

## Retrospective fold-local evaluation

The invalid 1979 fold is removed. The valid cutoffs are 1989, 1999 and 2009. A fixed prior-derived candidate grid is selected independently inside each fold using only pre-cutoff observations; fitted baselines likewise use only pre-cutoff information. The grid and model architecture were nevertheless developed after the historical record had already been inspected, so this is **retrospective method-development evidence, not independent nested validation**. The model does not beat every required baseline, so `scientific_predictive_skill_claim_allowed` remains **False**.

## Remaining scientific blockers

NSIDC-0611 v4 sea-ice-age evidence is still absent and genuinely untouched prospective evaluation begins in 2027. `scientific_validation_complete` therefore remains **False**.
