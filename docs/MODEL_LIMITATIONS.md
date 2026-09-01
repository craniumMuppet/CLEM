# Model limitations

## Historical AMOC mean state

CLEM v2.29.29 underestimates the RAPID-era absolute AMOC strength in the validated historical trajectory.

- CLEM 2004-2020 mean: approximately **14.17 Sv at 10°** and **14.32 Sv at 5°**.
- RAPID-era comparison used during review: **16.9 ± 1.2 Sv**.

This bias is intentionally documented rather than removed using a post-hoc AMOC offset.

## Sea-ice geography and extent

CLEM is a reduced spatial model and does not resolve satellite-scale Arctic coastline and ice-edge geometry. The corrected R18.2 >=15% native-cell **area** comparison performs well enough that another sea-ice physics retune is not justified, but a literal >=15% coarse-cell **extent** remains resolution-limited.

The fractional-support extent diagnostic is therefore retained as a reduced-order structural footprint quantity and is explicitly non-release-blocking. It must not be described as satellite-resolution extent validation.

## Arctic observational interpretation

The intended six-source Arctic stack is available as of R18.4, including NSIDC-0611 sea-ice age. Historical/recent products were inspected during development and are therefore development/calibration/structural evidence rather than untouched prospective validation.

CryoSat-2 mean-state diagnostics are usable, but its short-record temporal correlation remains poor in the reviewed configuration. No post-hoc thickness-physics tuning was performed to force that correlation positive.

## AMOC tipping interpretation

CLEM contains nonlinear reduced-order AMOC dynamics and supports collapse, recovery, and hysteresis experiments. Exact collapse/recovery thresholds remain closure-dependent and should not be interpreted as precise real-world tipping thresholds or calendar-year forecasts.

## Reduced atmosphere and ocean dynamics

CLEM does not explicitly resolve synoptic weather, atmospheric jets/storm tracks, full 3-D clouds, mesoscale ocean eddies, complete gyre dynamics, western boundary currents, detailed bathymetry, or eddy-resolving convection. Relevant effects are represented through reduced-order parameterizations.

## Prospective predictive validation

The frozen 2027-2036 prospective holdout is not yet available. Its current status is **`not_available`** because the observations do not yet exist. This is an evidence-timing limitation, not a numerical or physics failure.

## Interpretation

CLEM is a reduced-complexity climate model. Passing the included engineering, conservation, physics, structural, and observational-development checks does not make it a substitute for a comprehensive coupled Earth-system model or observational product.
