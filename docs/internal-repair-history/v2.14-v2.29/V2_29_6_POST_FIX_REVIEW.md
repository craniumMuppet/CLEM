# v2.29.6 Post-Fix Review

## Independent-review findings addressed

| Finding | v2.29.6 resolution | Remaining scope limit |
|---|---|---|
| Native September ice was severely overestimated while the operator concealed the bias | Published area is now identical to native thermodynamic area; the native seasonal cycle and trend are directly calibrated and release-gated | The reduced geometry remains hemispheric/two-sector rather than spatially resolved |
| Exact-zero handling was discontinuous | Area identity and zero-intercept extent mapping are continuous, monotone and zero-preserving | Extent remains a diagnostic approximation because grid-cell concentration is unresolved |
| 2021-2025 was called independent after repeated inspection | Reclassified as validation-informed development evidence; future observations are explicitly reserved prospectively | A long untouched temporal evaluation does not yet exist |
| Winter ice was dominated by a 1.2 m cap | Emergency ceiling raised well above the reference state; cap occupancy is explicitly tested | Equivalent thickness remains a reduced thermodynamic state |
| Scientific regressions were weakened | Native climatology, amplitude, trend, area identity, near-zero continuity and cap-occupancy gates are explicit | Broad historical development ranges remain calibration checks, not independent validation |
| OISST comparison was not reproducible | Release claims are downgraded to broad external sanity metadata unless exact source hashes and processed output are packaged | No quantitative OISST validation claim is made in this release without source artifacts |
| AMOC coupling was reduced without new evidence | Default temperature-density coupling restored from 0.70 to 1.00 | AMOC remains suitable for sensitivity experiments rather than precise collapse timing |
| Native-ice retuning lowered annual Arctic amplification below the predeclared development range | Added an explicit 0.50 W/m²/K low-confidence Arctic inversion/lapse-rate closure; the benchmark was not widened | This parameter is tuning-informed and must not be treated as independent validation |
| Platform and provenance records were stale | Windows CI added; dependency records are version-correct and installed-file hashes are enforced only on the matching platform | Full numerical equivalence across every Python/platform combination is not claimed |
| Very long fixed-forcing recovery could overshoot to 25.5 Sv after collapse | Positive hydraulic targets now saturate smoothly at a documented 20 Sv while all weakening and reversal targets below the control strength remain unchanged | This is a low-confidence reduced hydraulic-drag closure, not a resolved prediction of transient AMOC strengthening |

## Scientific classification

- Global temperature and energy-balance behavior: suitable as a documented
  reduced-complexity emulator within its calibration domain.
- Native hemispheric Arctic area: quantitatively evaluated at the reduced-model
  scale, with published area no longer hidden by a statistical correction.
- Sea-ice extent and longitude-pattern displays: diagnostics, not resolved
  regional forecasts.
- Arctic open-water temperature: sector-scale plausibility output, not local or
  coastal validation.
- AMOC and Greenland: sensitivity experiments, not precise forecasts.

## Release decision rule

This document describes the implemented corrections. Release acceptance still
requires all generated validation checks, the complete regression record and
verification from an extracted archive. The generated JSON and test record are
the authoritative pass/fail evidence.
