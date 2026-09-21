# Repair R11 verified results review

The Repair R11 climate-model source in this package is byte-for-byte the source that produced the uploaded verification bundle reviewed on 2026-08-29.

Climate-model SHA-256: `f08e901aac796c7fd757a52345709b0d9e3d20ec34c92f6afc0d53d8f7a824b9`

## Verified headline results

- Equilibrium ECS: **3.273 C**.
- Gregory 1-150 y effective ECS: **3.461 C**.
- TCR: **1.923 C**.
- Equilibrium 2xCO2 AMOC: **11.059 Sv**.
- Equilibrium tail TOA: **+0.0395 W m-2**.
- Equilibrium tail GMST trend: **+0.0062 C/century**.
- Equilibrium tail AMOC trend: **-0.0996 Sv/century**.
- Late TOA-vs-heat-content residual: **0.0166 W m-2**.
- Net feedback: **-1.144 W m-2 K-1**.
- WV feedback: **+1.814 W m-2 K-1**.
- WV+LR+polar: **+1.384 W m-2 K-1**.
- Planck: **-3.255 W m-2 K-1**.
- Cloud: **+0.425 W m-2 K-1**.
- Surface albedo: **+0.302 W m-2 K-1**.
- Pure-thermal 150-y AMOC weakening: **41.95%**.
- Thermal+sea-ice AMOC weakening: **38.54%**.
- 0.5-Sv hosing minimum AMOC: **0.000001 Sv**.
- 0.5-Sv hosing cold blob: **-3.121 C**.
- Persistent collapsed-branch cold blob: **-7.984 C**.
- Forced energy closure residual: **0.0435%**.
- Pycnocline final volume imbalance: **5.701e-07 Sv**.
- Fine seasonal-Arctic timestep differences: **0.001474 C**, **0.010807 Sv**.

All explicit `pass_*` flags in the Repair R11 static and numerical science tests are true. The descriptive `recovered_to_within_10_percent_of_control` flag is false because the 0.4-Sv/250-y perturbation remains on a persistent collapsed branch; it is not a failed pass gate.

## Why Repair R12 is validation-only

The repaired tests above were repeatedly used while developing the physics. Passing them is necessary but not sufficient evidence against overfitting. Repair R12 therefore leaves `climate_model.py` unchanged and adds independent tests that were not used to tune Repair R11:

1. SSP2-4.5 from 1850-2100 at 10 degrees.
2. The same SSP2-4.5 trajectory at 5 degrees.
3. Untuned 0.1, 0.2, and 0.3 Sv hosing dose-response experiments.

The SSP2-4.5 temperature gate uses the IPCC AR6 2081-2100 very-likely range (2.1-3.5 C relative to 1850-1900). The AMOC comparison is intentionally broad: CMIP6 SSP2-4.5 mean weakening is about 29%, while an observationally constrained subset gives about 34-45%; Repair R12 only requires a material decline without collapse and reports the exact value.
