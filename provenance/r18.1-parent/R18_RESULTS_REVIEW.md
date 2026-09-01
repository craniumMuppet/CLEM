# CLEM v2.29.28 R18 numerical review

## Execution integrity

The user-local R18 suite completed all 10 requested experiments in 620 bounded child chunks. Maximum advancement per child was 5 model years. No integration child timed out or failed. The only runtime failure occurred after all integrations completed, in final summary generation: `_series_metrics()` called undefined `ols()` instead of the existing `linear_fit()` helper. The corrected finalizer reproduced the complete result summary from the saved chunks without rerunning climate integrations.

Finalized R18 results ZIP SHA-256: `69f0d2d8095e084e6464c291ca978417d9891d759ca0649106c6cee434dce4c8`.

## Sea-ice spatial support

R18 retained the prognostic ice-area/energy state and changed only the independent support/footprint representation used for extent. The 1979–2024 packaged fixed-mask evaluation gives:

| Resolution | Month | Area bias | Area RMSE | Area corr. | Extent bias | Extent RMSE | Extent corr. |
|---|---:|---:|---:|---:|---:|---:|---:|
| 10° | March | +0.863 | 0.906 | 0.873 | -0.150 | 0.354 | 0.890 |
| 5° | March | +1.068 | 1.103 | 0.873 | -0.015 | 0.336 | 0.888 |
| 10° | September | +0.533 | 0.738 | 0.905 | +0.023 | 0.565 | 0.901 |
| 5° | September | +0.531 | 0.741 | 0.905 | -0.042 | 0.582 | 0.899 |

Units for bias/RMSE are million km².

Extent/compactness is therefore substantially improved and the R18 support-state change is retained. The underlying prognostic area has not been retuned and still has a positive mean-state bias, especially in March. That limitation remains explicit rather than being absorbed into the extent operator.

The fixed-mask record has been used during development, so these statistics are retrospective development evidence, not independent prospective validation.

## AMOC recovery/hysteresis

After a +0.80 Sv collapse forcing to year 250, the R18 de-hosing branches ended at year 700 near:

- -0.25 Sv: 0.00 Sv AMOC
- -0.30 Sv: 0.24 Sv
- -0.35 Sv: 5.25 Sv
- -0.40 Sv: 9.87 Sv

The -0.40 Sv branch crossed 6 Sv around year 631. When artificial de-hosing was removed at year 700, AMOC fell to 1.70 Sv by year 900.

This relapse is not evidence for a missing restart switch. A targeted fixed-preindustrial root solve of the unchanged R18 reduced AMOC subsystem at zero artificial hosing finds:

### Production configuration (`amoc_allow_reversal = false`)

- ~0 Sv: linearly stable weak/boundary equilibrium
- 12.3198 Sv: linearly unstable intermediate equilibrium
- 17.0000 Sv: linearly stable strong control equilibrium

### Reversal-enabled structural sensitivity

- -5.7389 Sv: linearly stable reversed equilibrium
- 12.3198 Sv: linearly unstable intermediate equilibrium
- 17.0000 Sv: linearly stable strong equilibrium

Thus the ~12.32 Sv unstable separator survives when reversal is enabled. The R18 -0.40 Sv recovered state (~9.87 Sv) remained below that zero-hosing separator, so returning the forcing to zero placed it back in the weak-side basin. The no-reversal default changes the weak branch from a reversed circulation to a zero-flow boundary branch, but it does not create the strong/weak basin separation.

No AMOC restart trigger or coefficient retuning is justified by these results. The exact fixed-point calculation is stored in `R18_1_AMOC_BISTABILITY_DIAGNOSIS.json` and is reproducible with `r18_1_amoc_bistability_diagnosis.py`.

## TEOS-10 disposition

R17 already showed that matched-pathway TEOS-10 is substantially less sensitive than the validated linear closure under both hosing and SSP2-4.5 forcing. R18 did not rerun TEOS. The linear EOS remains the production default and the TEOS branches remain structural sensitivities.

## Release disposition

- Keep the R18 thermodynamic sea-ice support state.
- Keep the validated linear AMOC closure as production default.
- Keep no-reversal as an explicit default structural choice; reversal remains a sensitivity branch.
- Do not add a restart threshold.
- Do not retune AMOC coefficients from the R18 recovery experiment.
- Permanently fix the R18 finalizer `ols()` NameError.
- Scientific release status must still respect the existing prospective/independent-validation limitations; R18 retrospective improvements do not make those future-data gates disappear.
