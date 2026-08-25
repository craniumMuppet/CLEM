# v2.29.11 — Target baseline and checkpoint safety

v2.29.11 corrects the remaining issues identified in the independent v2.29.10 review while retaining the v2.29.10 physical configuration and all resumable long-run features.

## Specific CO2 target semantics

Explicit targets no longer rewrite the configured common starting concentration. A list such as `200,300,600,1200` retains the configured 278.3 ppm pre-forcing state for every target. Targets below the start use a downward ramp from that same equilibrated state; targets above it use an upward ramp. The requested start, actual common start, direction, target, ramp duration, and hold duration are recorded in the target metadata.

This avoids the former artificial transient created by relabelling a 278.3 ppm-equilibrated model state as a 200 ppm starting state.

## AMOC percentage baseline

AMOC percentage change now uses one exact common pre-forcing baseline per ensemble member. The denominator is captured before any target-specific forcing begins and is shared across all targets for that member:

`100 * (common_pre_forcing_AMOC - AMOC(t)) / common_pre_forcing_AMOC`

It is no longer inferred from the first ten already-forced output records, so target comparisons have a consistent denominator and the initial percentage change is exactly zero.

## Resume-state safety and recovery

Normal resume now fails closed when the primary `long_run_state.json` is missing. It will not start a new run inside a nonempty output directory containing stale checkpoints or products.

State updates preserve `long_run_state.backup.json`. Recovery is explicit through the recovery command and can use:

1. the validated backup state; or
2. compatible checkpoint metadata when both primary and backup state are unavailable.

Recovered state records its source and is validated before use.

## Checkpoint resource limits

The non-executable JSON/NumPy checkpoint reader now:

- requires the ZIP member set to exactly match the manifest;
- rejects duplicate, undeclared, missing, encrypted, or unsupported members;
- limits member count, compressed size, uncompressed size, compression ratio, array count, dimensions, and total elements;
- validates array dtype, shape, and byte count before reconstruction.

These controls address archive-expansion and oversized-array denial-of-service risks while preserving atomic checkpoints.

## Runtime provenance

Resume compatibility now records and hashes installed distribution contents for NumPy, pandas, SciPy, and Matplotlib. It also records NumPy/SciPy build configuration, CPU dispatch information, and BLAS/LAPACK metadata where exposed by the installed libraries.

## Scientific scope

No physical calibration defaults were changed from v2.29.10. Historical Arctic temporal behavior remains tuning-informed and non-predictive. The March native-area response remains scientifically inadequate for quantitative temporal use and is disclosed as such. Future sea ice, AMOC, and Greenland results remain reduced-complexity sensitivity outputs.
