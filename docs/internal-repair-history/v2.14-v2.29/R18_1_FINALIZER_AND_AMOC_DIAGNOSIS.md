# CLEM v2.29.28 R18.1 — finalizer hotfix and AMOC basin diagnosis

R18.1 is an engineering/scientific-diagnosis maintenance update. It does **not** change the R18 governing climate physics.

## Permanent finalizer repair

The completed R18 local run exposed a post-run reporting bug in `verify_r18_local.py`: `_series_metrics()` called an undefined `ols()` helper even though the verifier already defines `linear_fit()`. Both calls are replaced with `linear_fit()`. The R18 integrations themselves were complete and unaffected.

## R18 numerical evidence retained

All 10 R18 experiments completed in 620 bounded child chunks with no chunk timeout/error. The corrected fixed-mask evaluation for 1979–2024 gave:

- 10° March extent: RMSE 0.3541 million km², correlation 0.8897, bias -0.1503 million km².
- 5° March extent: RMSE 0.3363 million km², correlation 0.8882, bias -0.0153 million km².
- 10° September extent: RMSE 0.5647 million km², correlation 0.9009, bias +0.0227 million km².
- 5° September extent: RMSE 0.5818 million km², correlation 0.8994, bias -0.0419 million km².

The R18 thermodynamic support state is therefore retained. It is not promoted to independent prospective validation; the fixed-mask record remains development evidence.

## AMOC recovery interpretation

R18 collapsed the AMOC with +0.80 Sv freshwater forcing. De-hosing branches to year 700 ended near:

- -0.25 Sv: 0.00 Sv AMOC
- -0.30 Sv: 0.24 Sv
- -0.35 Sv: 5.25 Sv
- -0.40 Sv: 9.87 Sv

When the -0.40 Sv salinifying perturbation was removed, AMOC fell to 1.70 Sv by year 900.

A targeted fixed-preindustrial equilibrium solve of the **unchanged R18 reduced AMOC subsystem at zero artificial hosing** finds three distinct production-configuration fixed points: a weak stable branch at the no-reversal boundary near 0 Sv, an unstable intermediate branch near 12.32 Sv, and the strong stable 17 Sv control branch. When reversal is enabled as a structural sensitivity, the weak-side attractor becomes a stable reversed circulation near -5.74 Sv while the same ~12.32 Sv unstable separator and 17 Sv strong branch remain. Thus reversal suppression changes the weak branch form but does not create the strong/weak basin separation.

The R18 state recovered to ~9.87 Sv but remained below the zero-hosing unstable separator; relapse toward the weak attractor is expected from the existing continuous salt-advection/convection equations. This is evidence of reduced-model bistability/hysteresis, not evidence that a Boolean restart trigger is missing. R18.1 therefore adds **no AMOC restart term and no coefficient retuning**.

The root solve is reproducible with `python r18_1_amoc_bistability_diagnosis.py`; its generated JSON records the exact roots, residuals, salt closure, and reduced-system Jacobian stability.
