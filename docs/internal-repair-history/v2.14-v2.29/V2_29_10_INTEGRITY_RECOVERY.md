# v2.29.10 — Integrity and recovery fixes

v2.29.10 addresses the remaining findings in the independent v2.29.9 review while retaining the v2.29.8/v2.29.9 long-run, explicit-target, and AMOC-percentage features.

## Native AMOC initialization

The active AMOC control temperatures are again calculated from each selected grid's own ocean climatology. The implementation uses fractional latitude-cell overlap across broad physical source regions:

- tropical Atlantic reference: 10–30°N;
- northern reference: 45–65°N;
- southern reference: 60–45°S.

No 5° control climatology is substituted into 2.5° or 10° runs. Validation records the native temperatures and density-driver ratios at every tested resolution. The initialization-spread gate therefore measures native-grid behavior rather than a prescribed identical reference.

## Historical March sea ice

The historical March trajectory remains tuning-informed and is not independent predictive validation. v2.29.10 no longer permits a large forced trend bias to be described as scientifically adequate merely because an absolute-error gate passes. The descriptive scientific-adequacy diagnostic now requires all of the following:

- trend-magnitude ratio no greater than 2.0;
- interannual correlation at least 0.30;
- predeclared-period absolute trend errors within the retained limit;
- matching decline direction in the predeclared periods.

This diagnostic is intentionally non-release-blocking. A failure must remain prominent and prevents quantitative temporal-skill claims.


## AMOC recovery smoothness

The convection-recovery e-folding time is 80 years. This retains more than 80% recovery after the standard idealized hosing experiment while keeping the maximum recovery rate in the 1200 ppm millennium hold below 0.5 Sv/year. The previous 20-year value produced an abrupt restart-like overshoot and is no longer the default. The timescale remains a calibration parameter rather than an observed constant.

## AMOC and Greenland evidence status

The exact defaults for AMOC convection recovery, stratification saturation, and Greenland marine influence are calibration parameters, not directly observed constants. v2.29.10 records that status explicitly. AMOC and Greenland outputs remain sensitivity results.

The former self-authored 60–105 mm Greenland range has been removed. The development report instead uses the published 22–163 mm SSP2-4.5 range for 2100 from *Extending the range and reach of physically-based Greenland ice sheet sea-level projections* (The Cryosphere, 2025) as a broad post-hoc sanity envelope. It is not a probability interval, tuning target, independent validation, or release gate.

## Safe resumable checkpoints

Python pickle is no longer used for long-run checkpoints. Checkpoints are ZIP containers containing:

- a JSON manifest;
- NumPy `.npy` arrays loaded with `allow_pickle=False`;
- strict type, array-name, path, shape, and dtype validation.

This prevents checkpoint loading from executing serialized Python objects. v2.29.8/v2.29.9 pickle checkpoints are deliberately not loaded by v2.29.10; old runs must be restarted or completed with the older release.

Atomic writes now flush and `fsync()` the file, replace it atomically, and `fsync()` the containing directory.

## Resume compatibility and recovery

Long-run fingerprints now include:

- SHA-256 hashes of runtime Python modules and required runtime data;
- dependency lock and project metadata hashes;
- Python implementation and version;
- platform and key numerical package versions.

A source or environment mismatch rejects resume even when `MODEL_VERSION` is unchanged.

Failed and timed-out ordinary Monte Carlo checkpoints are retried by default. Failed nested CO2-sweep diagnostics are also deleted and rerun, while successful members and targets remain reusable. The CLI offers `--no-mc-retry-failed-on-resume` when preserving failures is explicitly desired.

## Explicit CO2 targets and outputs

Specific target mode accepts lists such as `200,300,600,1200` with the normal 278.3 ppm starting-field default. When a listed target is lower, the effective common start is automatically lowered to the minimum requested target and both requested and effective starts are recorded.

`co2_target_sweep_mean_timeseries.csv` now contains mean columns only. Percentile columns remain in `co2_target_sweep_percentile_timeseries.csv`, and AMOC percentage intervals remain in `co2_target_sweep_amoc_percent_decline_timeseries.csv`.

## Audit coverage

The implementation audit now includes the checkpoint serializer, runtime provenance module, worker supervision, run-state module, Monte Carlo driver, and CO2-sweep driver in addition to the physical core and evidence modules.
