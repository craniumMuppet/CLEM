# v2.13 validation summary

The v2.13 release uses the dynamics that passed the v2.11 full physics suite and the v2.12 held-out validation. v2.13 itself only repairs CLI/release consistency; the validated core-model AST is unchanged.

Headline verified results:

- Equilibrium ECS: 3.273 C
- TCR: 1.923 C
- Forced energy-closure residual: 0.0435%
- SSP2-4.5 2081-2100 warming: 2.671 C at 10 deg; 2.655 C at 5 deg
- SSP2-4.5 AMOC decline: 41.87% at 10 deg; 38.60% at 5 deg
- 100-year hosing final AMOC: 13.78 Sv at 0.1 Sv, 9.51 Sv at 0.2 Sv, 4.13 Sv at 0.3 Sv
- 0.5 Sv hosing reaches the collapsed branch with an approximately -3.12 C short-term North Atlantic cold anomaly
- Pycnocline volume imbalance converges to approximately 5.7e-7 Sv
- Salt conservation passes to reported precision

The large raw numerical outputs are intentionally distributed as the separate GitHub Release asset `CLEM-v2.13-validation-results.zip`, not committed to the repository.
