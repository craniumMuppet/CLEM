# CLEM physics repair v2.13

CLEM is a physically based reduced-complexity Earth-system model coupling global climate, ocean heat transport, Arctic sea ice, Greenland, freshwater forcing, and the AMOC.

## Current status

The v2.11 climate dynamics passed the full local physics suite and the v2.12 held-out validation suite. v2.13 is a release-consistency repair only: it makes the public CLI defaults reproduce the already-validated `ModelConfig` and corrects stale AMOC salt-loop documentation. The core-model AST is identical to the validated v2.11/v2.12 source when only the public `build_parser()` function is excluded.

See:

- `V2_12_RESULTS_REVIEW.md` - held-out SSP2-4.5, cross-resolution, hosing dose-response results, and the remaining RAPID-era AMOC limitation.
- `PHYSICS_REPAIR_V2_13.md` - exact release-consistency changes and dynamics-equivalence hashes.
- `clem/clem/V2_13_DYNAMICS_EQUIVALENCE.json` - machine-readable provenance.

## Local verification

For the complete <=5-model-year checkpointed physics suite:

`clem\\clem\\RUN_PHYSICS_VERIFICATION.cmd`

For the held-out v2.12 SSP2-4.5 / hosing validation:

`clem\\clem\\RUN_V2_12_OUT_OF_SAMPLE_VALIDATION.cmd`

For a zero-integration release-consistency check:

`clem\\clem\\RUN_V2_13_RELEASE_CONSISTENCY.cmd`
