# v2.29.4 Post-Fix Scientific and Implementation Review

## Verdict

v2.29.4 resolves the six requested release issues without converting the reduced-complexity model into a spatial Earth-system model. The release is suitable for scenario sensitivity, process experiments and educational/research prototyping when its evidence roles and scope limits are retained.

## Requested issues

| Finding | Resolution | Residual limitation |
|---|---|---|
| Arctic sea ice severely overestimated | Calibrated March/September hemispheric area and extent observation operator; historical calibration and frozen temporal holdout | Future results inherit an AR6-consistent tuning-informed statistical warming closure and are not independent predictive validation or a dynamical sea-ice-model projection |
| Two-sector geometry cannot calculate 15% extent | Explicit sub-grid ocean-cell occupancy integrates to diagnosed 15% extent; native field retained separately | Longitude occupancy is deterministic display reconstruction with no regional skill |
| Exact-zero control bypass | Removed; ordinary equations use continuous phase-dependent residual balancing | Reference-cycle residual correction remains a reduced-model calibration device and must stay visible in documentation |
| Tuning ranges called validation | Evidence roles split into tuning-informed development, independent temporal holdout, external plausibility and structural tests | The independent holdout is only five years |
| Open-water temperature lacks validation | Frozen broad NOAA sector-mean plausibility checks and mandatory warning | No gridded/local SST validation; sector temperatures are not coastal forecasts |
| AMOC and Greenland magnitudes simplified | Summary, metadata, desktop and Streamlit warnings label them as sensitivity outputs | Collapse timing, probabilities, outlet glaciers and regional geometry remain unresolved |

## Automatic rereview findings corrected

The post-fix review detected and corrected the following secondary issues:

1. The aggregate validation report initially retained a stale SSP5-8.5 sea-ice task. The report is rebuilt from current task files and now includes mandatory forcing-order gates.
2. Annual fixed-phase output sampling could silently select the wrong calendar phase for September. The validator now requires subannual sampling at 0.1-year cadence or finer.
3. A retained Atlantic-localization test used the statistical display field. It now uses the native thermodynamic process field.
4. Historical v2.29.3 provenance assertions incorrectly demanded that archived hashes equal current v2.29.4 source. Tests now verify the active v2.29.4 records.
5. Public maps and downloads did not clearly distinguish statistical area, extent occupancy and the native process state. Explicit names and warnings are now present.
6. README and changelog still described the removed zero-forcing shortcut. Active release documentation now describes continuous ordinary-equation balancing.

## Scientific interpretation

### Sea ice

The model now has quantitatively useful hemispheric March and September area/extent diagnostics for its intended reduced-complexity role. It still does not resolve drift, export, ridging, leads, basin geography or regional circulation. A map cell's longitude pattern is an observation-operator visualization, not a forecast.

### Control and conservation

The ordinary equations, not a forcing-specific shortcut, advance the control. Heat and salt diagnostics remain explicit, and the control response is continuous at zero forcing.

### Open-water temperature

Broad sector means are observationally plausible. Local values remain underdetermined by the two-sector geometry. Any use requiring Barents, Kara, Beaufort, Chukchi or coastal SST separately needs a spatial ocean model or a dedicated regional emulator.

### AMOC

The AMOC module is appropriate for controlled sensitivities, structural hysteresis exploration and freshwater experiments. It does not produce a calibrated probability distribution for collapse timing.

### Greenland

The aggregate sea-level response is plausible as a sensitivity output. It cannot represent outlet-specific retreat or geometry-driven feedbacks.

## Release classification

- **Software implementation:** strong, subject to the final isolated suite and extracted-package checks.
- **Numerical conservation:** strong.
- **Global climate response:** plausible reduced-complexity behavior.
- **Hemispheric sea-ice area/extent:** calibrated, with a limited independent temporal holdout.
- **Regional sea-ice maps:** visualization only.
- **AMOC and Greenland forecasts:** sensitivity experiments, not precise forecasts.
