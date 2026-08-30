# Model limitations

## Historical AMOC mean state

The retained v2.13 release underestimates the RAPID-era absolute AMOC strength in the SSP2-4.5 historical trajectory.

- CLEM 2004-2020 mean: approximately 14.17 Sv at 10 degrees and 14.32 Sv at 5 degrees.
- RAPID 26.5 N comparison used during review: 16.9 +/- 1.2 Sv.

This bias is intentionally documented rather than post-hoc tuned after the held-out validation. See `V2_12_RESULTS_REVIEW.md` for the full validation context.

## Interpretation

CLEM is a reduced-complexity climate model. Passing the included conservation, sensitivity, AMOC, hosing, cross-resolution and SSP2-4.5 tests does not make it a substitute for a comprehensive coupled Earth-system model or observational product.
