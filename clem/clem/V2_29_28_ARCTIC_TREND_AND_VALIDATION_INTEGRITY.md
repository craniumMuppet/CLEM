# v2.29.28 — Arctic trend and validation integrity

v2.29.28 fixes the scientific issues identified in review of v2.29.27:

1. Restores the inherited preindustrial March/September sea-ice climatology bounds.
2. Adds explicit fixed-mask historical trend-direction and trend-magnitude gates; passing RMSE alone is no longer sufficient.
3. Replaces unbounded warming-driven Arctic Ocean heat convergence with a conservative saturating response and equal-and-opposite lower-latitude energy tendency.
4. Adds a bounded winter formation-support floor so severe pack depletion cannot numerically suppress thermodynamic refreezing to zero.
5. Relabels OSI SAF as development evidence, not independent validation.
6. Removes the invalid 1979 retrospective fold and replaces the globally outcome-selected candidate bank with a fixed prior-derived bank scored separately inside each valid cutoff.
7. Keeps retrospective evidence and 2027+ prospective evidence explicitly separate; predictive skill remains fail-closed.
8. Keeps processed observational hashes fail-closed and release fingerprints bound to scientific evidence inputs.

The production candidate is an exact 1850-start integration, not a continuation-only screening result.
