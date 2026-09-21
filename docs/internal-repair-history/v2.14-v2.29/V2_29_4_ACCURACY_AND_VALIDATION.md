# v2.29.4 Accuracy and Validation

## Release purpose

v2.29.4 corrects six interpretation and implementation problems identified in the v2.29.3 accuracy review:

1. Excessive and non-observational Arctic sea-ice area.
2. A binary two-sector geometry that could not produce meaningful 15%-concentration extent.
3. An exact-zero control shortcut that bypassed ordinary integration.
4. Development ranges being described too much like independent validation.
5. Arctic open-water temperatures lacking an observational check and mandatory interpretation limit.
6. AMOC and Greenland magnitudes being presented without sufficiently prominent reduced-complexity limitations.

## Continuous control balancing

The v2.29.3 exact-reference branch has been removed. Every step now uses the ordinary model equations. A phase-dependent residual is calculated for the periodic reference state and subtracted continuously from the ordinary tendency. The same operation applies at exactly zero forcing and at arbitrarily small nonzero forcing.

Consequences:

- no forcing-specific integration bypass;
- machine-precision control stability;
- continuous response to small perturbations;
- normal heat, salt, AMOC and Arctic state updates remain active.

## Sea-ice architecture

The prognostic thermodynamic core remains two-sector and energy conserving. v2.29.4 does not pretend that this state dynamically resolves longitude. Instead, it adds an explicit observation operator with three distinct public products:

- **Native thermodynamic process field:** the original Atlantic/non-Atlantic latitude-sector ice-area state. It is used for process-localization tests and cannot define satellite-like extent.
- **Calibrated Northern Hemisphere area and extent:** hemispheric diagnostics fit to NOAA/NSIDC Sea Ice Index v4 March and September records during 1979–2020.
- **Statistical display reconstruction:** deterministic sub-grid occupancy that integrates exactly to the diagnosed area and 15%-concentration extent. Longitude placement has no regional forecast skill.

The output files preserve the legacy `sea_ice_fraction` alias while adding explicit names for statistical area, ocean-cell concentration, extent occupancy and the native process field.

## Evidence partition

| Evidence set | Period or scope | Used for fitting | Interpretation |
|---|---|---:|---|
| Development climate ranges | historical and SSP development metrics | Yes, during earlier versions | Regression/calibration consistency only |
| NSIDC sea-ice calibration | March and September 1979–2020 | Yes | Observation-operator calibration and development evaluation |
| NSIDC temporal holdout | March and September 2021–2025 | No | Independent temporal evaluation |
| NOAA OISST/Arctic Report Card envelopes | Arctic summer/September sector means | No | Broad external plausibility, not gridded SST skill |
| Conservation, control, timestep, resolution and software tests | structural | No | Numerical and implementation integrity |

## Frozen independent sea-ice holdout

The 2021–2025 period was not used to fit the observation-operator constants. All six predeclared gates pass.

| Holdout metric | Result |
|---|---:|
| March area RMSE | 0.351 million km² |
| March extent RMSE | 0.235 million km² |
| September area RMSE | 0.420 million km² |
| September extent RMSE | 0.762 million km² |
| September area correlation | 0.728 |
| September extent correlation | 0.573 |

Five years is a short temporal holdout. It is independent of the fit, but it is not equivalent to broad process validation across multiple observational products.

## Future September sea ice

| Scenario | 2081–2100 area | 2081–2100 extent | First area below 1 million km² | 2100 area |
|---|---:|---:|---:|---:|
| SSP2-4.5 | 1.050 million km² | 1.545 million km² | 2097 | 0.979 million km² |
| SSP5-8.5 | 0.374 million km² | 0.546 million km² | 2061 | 0.275 million km² |

These are tuning-informed calibrated hemispheric observation-operator projections. The post-2020 decay closure was selected for AR6 consistency, so these values are not independent predictive validation and are not longitude-resolved regional predictions.

## Arctic open-water temperature

The validation record compares summer and September Atlantic/non-Atlantic sector means north of 66°N with frozen broad NOAA observational plausibility envelopes. All checks pass. The product remains a reduced-sector diagnostic because the model does not resolve marginal seas, currents, coasts or local mixed-layer structure.

Mandatory interpretation: **do not use Arctic open-water temperature as a local, coastal or point forecast.**

## AMOC and Greenland interpretation

The AMOC module conserves salt, includes density and pycnocline feedbacks, and is suitable for controlled sensitivity and hosing experiments. Its collapse threshold, probability and timing are not precise forecasts.

The Greenland module produces aggregate surface-mass-balance and dynamic-discharge responses. It does not resolve evolving geometry, individual outlet glaciers, bed topography or regional ocean forcing. Its total contribution is a scenario-sensitivity output.

## Development metrics retained for regression

- Historical GMST, 2011–2020: 1.108°C.
- Ocean heat-content change, 1971–2018: 383.72 ZJ.
- Arctic amplification, 1979–2021: 3.409× annual, 4.540× DJF and 1.636× JJA.
- SSP2-4.5 AMOC weakening by 2100: 20.85%.
- SSP5-8.5 AMOC weakening by 2100: 39.96%.
- Abrupt-2×CO₂ energy residual: −0.0396%.

These ranges were involved in prior model tuning and are explicitly classified as tuning-informed development regressions.

## Release requirements

A release is valid only when:

- every v2.29.4 release gate is true;
- the active validation records match current source hashes;
- the full isolated regression inventory passes;
- the delivered ZIP passes clean extraction, startup, summary/export and Monte Carlo smoke tests;
- public map titles, download fields and summaries preserve the distinction between statistical and native sea ice.
