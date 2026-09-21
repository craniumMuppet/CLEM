# v2.29.28 — Arctic trend and validation integrity

The post-review v2.29.28 source correction addresses the scientific and coupled-integrity issues identified in review:

1. Restores the inherited preindustrial March/September sea-ice climatology bounds.
2. Requires 0.80–1.25 historical trend ratios and overlapping model/observed OLS 95% trend intervals; passing RMSE alone is insufficient.
3. Replaces unbounded warming-driven Arctic Ocean heat convergence with a conservative saturating response and equal-and-opposite lower-latitude energy tendency.
4. Adds a bounded winter formation-support floor so severe pack depletion cannot numerically suppress thermodynamic refreezing to zero.
5. Relabels OSI SAF as development evidence, not independent validation.
6. Removes the invalid 1979 retrospective fold and replaces the globally outcome-selected candidate bank with a fixed prior-derived bank scored separately inside each valid cutoff.
7. Keeps retrospective evidence and 2027+ prospective evidence explicitly separate; predictive skill remains fail-closed.
8. Keeps processed observational hashes fail-closed and release fingerprints bound to scientific evidence inputs.
9. Recalibrates active atmospheric transport, area/volume partition, mechanical export, and bounded ocean-heat convergence. The exact 10° run reaches historical trend ratios 0.968/0.961 and recent RMSE 0.370/0.358 M km2.
10. Adds current-version 5°/10° validators and a cross-resolution combiner. Canonical members are published only after all required gates pass, then a summary containing every member hash is committed last; the finalizer rejects interrupted or mixed generations.
11. Separates passing physical mean-state gates from temporal response. CryoSat-2 temporal correlation still fails, so full volume/thickness validation remains incomplete.
12. Scales area processes consistently through the 55–66 N module transition and adds an explicit volume-conserving 12 m deformation/spreading constraint before the 500 m emergency abort. Production states that cannot satisfy 12 m even at full concentration fail fast. Both validated resolutions are stable through 2100.
13. Replaces hand-authored regression summaries with one unchanged-tree pytest runner, hashed per-test NDJSON and JUnit evidence, strict count/exit-code checks, and a fingerprint that cannot be regenerated without passing evidence.
14. Builds the ZIP through a temporary archive and verifies every member against the manifest and test-bound fingerprint before atomic replacement.

The calibration candidate is an exact 1850-start integration, not a continuation-only screening result. Fresh current-source 5°/10° coupled results pass, including cross-resolution differences of 0.189/0.024 M km2 for late March/September area and 0.252 Sv for 2100 AMOC. Final-source regression evidence is machine-generated and bound to one unchanged source tree; this does not change the explicitly incomplete scientific-predictive status.
