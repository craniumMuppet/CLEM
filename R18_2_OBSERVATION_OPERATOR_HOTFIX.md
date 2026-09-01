# CLEM v2.29.28 R18.2 observation-operator hotfix

R18.2 is an **evaluation-only** child of R18.1. `climate_model.py`, `sea_ice_observation.py`, `arctic_observation_operator.py`, and `sea_ice_validation.py` remain byte-identical to R18.1. No AMOC or Arctic governing coefficient is changed.

## Why R18.2 is needed

The R18 local runner reported fixed-mask sea-ice area as the integral of all sampled model concentration, while the packaged NSIDC metadata and the established CLEM fixed-mask comparator define satellite-compatible area/extent after a **15% cell-concentration threshold**. R18 also summarized monthly-boundary records instead of selecting the model state nearest the established month-centred validation target `year + (month - 0.5)/12`.

Those differences make the apparent residual area bias non-comparable with the earlier v2.29.28 calibration and are not evidence, by themselves, for a new sea-ice physics retune.

## R18.2 diagnostics

Every 0.05-model-year record carries both operator families:

1. **NSIDC-compatible cell-threshold comparator**
   - area: concentration-weighted area only where sampled concentration >= 0.15
   - extent: full cell area only where sampled concentration >= 0.15

2. **R18 fractional-support structural diagnostic**
   - area: integral of all sampled concentration
   - extent: integral of fractional support occupancy

The finalizer evaluates March and September by selecting the nearest available 0.05-year model record to the established mid-month target. Maximum allowed sampling offset is 0.025 model years.

## Local run scope

Only two integrations are requested:
- 1850-2025 SSP2-4.5 at 10 degrees
- 1850-2025 SSP2-4.5 at 5 degrees

Each child process advances at most 5 model years. No GSW/TEOS dependency is required. No AMOC recovery run is repeated.

Run `run_r18_2_seaice_operator_validation.bat` and upload `CLEM_v2.29.28_R18_2_seaice_operator_results.zip`.
