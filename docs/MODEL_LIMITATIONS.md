# Model limitations

## Historical AMOC mean state

CLEM v2.29.29 underestimates the RAPID-era absolute AMOC strength in the
validated historical trajectory. The Unreleased worktree contains a
physics-based equation-of-state repair.

- Released fixed-alpha/beta CLEM mean: approximately **14.17 Sv at 10°** and
  **14.32 Sv at 5°**.
- Unreleased matched-pathway TEOS-10 mean at the production 0.05-year step:
  approximately **15.74 Sv at 10°** and **15.86 Sv at 5°**.
- RAPID 2004–2020 mean: **16.9 ± 1.2 Sv** ([Johns et al.,
  2023](https://doi.org/10.1098/rsta.2022.0188)).

Mechanism-isolation runs show that disabling anomalous historical freshwater
changes the mean by only about 0.025 Sv, while disabling the thermal-density
anomaly pathway removes almost all of the modeled decline. This is therefore a
thermal-response/mean-state bias, not a freshwater-forcing bias.

The old fixed-alpha/beta density driver is a fragile residual of opposing
thermal and haline terms. Its constant 2.0e-4 K^-1 expansion coefficient is
substantially larger than the TEOS-10 control-state values for the northern
(about 1.22e-4 K^-1) and cold source-coordinate (about 0.43e-4 K^-1) states.
The repair evaluates nonlinear density on the same established reduced-order
North Atlantic stratification pathway. This reduces the discrepancy to about
1.0–1.2 Sv, within RAPID's published uncertainty, without changing the initial
17 Sv transport, initial salinities, hydraulic coefficients, or applying any
post-integration output adjustment.

Four broader alternatives were explicitly rejected. Literal prognostic
high-latitude water-mass TEOS produced a historical mean near 16.34 Sv but only
about 6.5% SSP2-4.5 weakening, below the independently declared 15–50%
development range. Changing the source box to the South Atlantic upper limb
made SSP2-4.5 strengthen by about 10.9%.
Replacing the complete hydraulic closure with the canonical linear-density,
squared-depth law made the linear-EOS SSP2-4.5 run strengthen by about 8.5%;
its TEOS counterpart weakened by only about 9.8% and responded too weakly to
0.1 Sv hosing. An idealized hemispheric aerosol pattern improved the mean but
was not merged because its latitude shape was not independently constrained.

The retained TEOS repair still has structural limitations. In the 10° screening
suite, SSP2-4.5 weakens by about 18.4% from 1995–2014 to 2081–2100, and a 0.1 Sv
hosing run weakens by about 6.6% around year 40. Both responses are weaker than
the released linear-EOS configuration, so AMOC projection and tipping
sensitivity remain closure-dependent. The historical 10°/5° means above use
the production 0.05-year step; the SSP and hosing mechanism checks used a
0.25-year step and should be refreshed in the full release-validation matrix
before a new tagged release.

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
