# Coupled Low-complexity Earth Model v2.29.28 validation summary

The current package uses Coupled Low-complexity Earth Model **2.29.28** dynamics that passed the Repair R11 full physics suite and the Repair R12 held-out validation. Repair R13 changed release/CLI consistency and provenance labeling, not the validated core dynamics.

Headline verified results:

- Equilibrium ECS: 3.273 °C
- TCR: 1.923 °C
- Forced energy-closure residual: 0.0435%
- SSP2-4.5 2081–2100 warming: 2.671 °C at 10°; 2.655 °C at 5°
- SSP2-4.5 AMOC decline: 41.87% at 10°; 38.60% at 5°
- 100-year hosing final AMOC: 13.78 Sv at 0.1 Sv, 9.51 Sv at 0.2 Sv, 4.13 Sv at 0.3 Sv
- 0.5 Sv hosing reaches the collapsed branch with an approximately −3.12 °C short-term North Atlantic cold anomaly
- Pycnocline volume imbalance converges to approximately 5.7e-7 Sv
- Salt conservation passes to reported precision

The large raw numerical outputs are distributed as the separate GitHub Release asset `CLEM-v2.29.28-physics-repair-r13-validation-results.zip`.

Repair-iteration labels R11/R12/R13 describe the validation workflow and do not replace the model version 2.29.28.
