# v2.29.12 — Monte Carlo and long-run integrity

v2.29.12 addresses the release-significant Monte Carlo, state-concurrency, recovery, and checkpoint-format findings from the independent v2.29.11 review. The corrected explicit-target CO2 semantics and common member AMOC percentage baseline from v2.29.11 are retained.

## Monte Carlo prior integrity

- The joint science-prior screen now builds the complete sampled `ModelConfig` and uses the same native-grid initial AMOC density calculation as `ProcessClimateModel`.
- Sampled `amoc_reference_density_driver`, thermal expansion, haline contraction, salinity, and other density-sensitive parameters are therefore screened exactly as workers initialize them.
- A deterministic regression covers the previously failing sampled density normalization case.

## Ensemble quality gates

- Runs with fewer than two successful members are rejected before percentile or confidence products are accepted.
- Runs are also rejected when more than 20% of requested members fail.
- Quantitative uncertainty use requires at least 20 successful members and a sufficient effective sample size. Smaller otherwise valid runs are explicitly classified as exploratory-only.
- Summary files now expose requested, successful, failed, survival-fraction, failed-fraction, effective-sample-size, and quantitative-validity fields.

## Exclusive run ownership and transactional state

- Monte Carlo and CO2 target sweep output folders now use an exclusive sibling lock before output preparation, initialization, resume, checkpoint aggregation, and final product writing.
- Lock metadata records PID, host, process-start marker, acquisition time, purpose, and output folder.
- Same-host dead processes and PID reuse are detected for stale-lock recovery; malformed and remote locks use conservative age limits.
- `long_run_state.json` read-modify-write operations now use a separate transaction lock, preventing lost updates between simultaneous writers.

## Honest progress accounting

- State records distinguish attempted, successful, failed, validated, and pending work.
- CO2 target sweeps count actual target attempts from worker results. A member rejected during baseline initialization no longer appears to have attempted every target.
- Completed runs with member failures use `completed_with_failures`; valid but undersized uncertainty runs use `completed_with_quality_warning`.

## Recovery and checkpoint strictness

- Explicit state recovery tries the validated backup first and then compatible checkpoint metadata if the backup exists but is corrupt or incompatible.
- Recovery records each failed source and the successful recovery source.
- Safe checkpoints permit only stored or deflated ZIP members, reject encryption flags, and require each NPY member to end exactly after its declared payload.
- LZMA-repacked checkpoints and NPY members with trailing bytes are rejected by focused regressions.

## Scientific classification retained

No Arctic physical parameter was retuned in this release. The March native-area temporal result remains scientifically inadequate for quantitative temporal use: the packaged v2.29.11 record reported a decline magnitude 3.17 times observed, correlation 0.1908, and RMSE 0.3776 million km2. This limitation remains prominent and non-predictive. AMOC, Greenland, future sea ice, and timing outputs remain reduced-complexity sensitivity experiments rather than precise forecasts.
