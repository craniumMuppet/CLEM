# Model limitations

## September 12 physics revision

The current default has changed again; the numerical AMOC discussion below
describes earlier configurations. See `PHYSICS_REVIEW_REPAIRS_2026_09_12.md`.
Historical and future fits must be re-established for the revised equations.

CLEM integrates anomalies about a prescribed analytic 1850 climatology. Its
unforced equilibrium is constructed, rather than obtained by balancing an
independently calculated absolute radiation budget. The main latitude-band
energy model is annual-mean; only the Arctic module and Greenland temperature
weighting have seasonality. Prescribed radiative forcing is spatially uniform.
Changing the solar constant changes reference insolation and feedback weights,
but does not constitute an imposed solar-forcing experiment.

The revised water-vapour optical-path weighting is a reduced closure, not a
radiative-transfer calculation or a new fit to radiative kernels. The analytic
land/SST climatology, common emission-height parameterization, broad Southern
Hemisphere sea-ice logistic, uniform deep-ocean heat exchange and missing
Antarctic ice sheet still limit regional interpretation.

The Arctic GMST heat-convergence and reference-phase-restoring closures and
extra winter GMST transport are off by default. The thickness-relaxation
export and concentration closures remain development parameterizations; their
absolute fluxes are not independently validated Fram Strait export. Exported
latent heat and its freshwater equivalent now use the same conversion without
a freshwater-only observational multiplier. Disabling empirical heating is
not evidence that the remaining Arctic trend is observationally accurate.

Greenland still uses one representative seasonal temperature cycle, a fixed
Gaussian daily temperature spread and simplified precipitation/discharge.
Correcting the PDD integral and reference runoff does not establish a present-day
mass-loss fit. Spatial accumulation zones and ocean-driven discharge need
separate development and validation.

The open Atlantic boundary uses a large boundary reservoir. Its control salinity
contrasts are solved from specified surface, northern-boundary and southern-gyre
freshwater-budget terms; neither FovS nor an upper/deep boundary salinity
contrast enters that solve. The resulting control FovS is -0.16 Sv. This is a
conditional equilibrium-budget prediction because CLEM does not calculate the
absolute evaporation, precipitation, runoff or azonal boundary circulation that
supply those inputs. The reported surface, non-overturning boundary and combined
virtual box fluxes are separate diagnostics. `fovs_sv` is the diagnosed overturning transport; the
historical SAU/deep value is named `amoc_internal_section_freshwater_sv`.
Hydraulic density/depth exponents, heat-transport coupling and the prescribed
control freshwater components remain structural assumptions.
The September 14 revision adds a separate forced-heat sinking-capacity state.
Its 5.10 Sv response scale uses the final-decade FAFMIP 50% North Atlantic
heat-flux ensemble mean as a benchmark. Its 20-year response time is a heuristic
interpretation of the reported qualitative stabilization, not a fitted FAFMIP
timescale. FAFMIP does not supply CLEM's mapping from instantaneous global
anthropogenic effective forcing to standardized North Atlantic heat input.
That mapping is an empirical emulator assumption. The model
reports this capacity, the hydraulic target, and the lower active target
separately. Passing an assessed SSP response range is development evidence,
not independent validation or a real-world forecast.
While the forced-heat capacity is the lower target, salinity and FovS remain
prognostic but cannot change AMOC unless their hydraulic target falls below
that capacity. Thus the default SSP AMOC trajectory is principally an empirical
forcing response with lag; it is not a salt-advection-controlled projection.
When the forcing-index capacity is the tighter SSP constraint, the AMOC
trajectory can be identical across latitude resolutions even though their
hydraulic targets and salinity/FovS trajectories differ. This is a deliberate
reduced-emulator limitation and must not be presented as cross-resolution
process agreement.
The South Atlantic salinity tracer supplies the hydraulic upper-limb salinity,
while its effective temperature anomaly follows northern surface-to-deep
stratification rather than the local 35 S surface anomaly. This prevents a
spurious TEOS-10 common-warming strengthening, but remains a reduced water-mass
transformation closure requiring process-level validation. The literal local
surface-temperature pathway remains available as the nondefault
`teos10_surface_watermass` structural sensitivity.

Northern convection controls salt mixing. Its additional direct transport
multiplier is off by default and available only as an explicit structural
experiment; its overlap with the hydraulic response has not been validated.
Convection normalization uses the magnitude of the north-surface/deep linear
control density contrast. This removes dependence on an unrelated southern
box, but the prescribed control temperatures and exponential anomaly law
remain reduced model assumptions, not a derived convective-onset criterion.
The 17–18% SSP decline from trial commit `eec6bcd` is superseded. See
`CONVECTION_REVIEW_FOLLOWUP_2026_09_14.md` for current results and validation limits.
The phase-space stability and recovery of the revised system must be assessed
afresh; a passing finite-duration run does not identify an equilibrium branch.

All previously inspected observations, including 2013–2024, remain development
evidence and cannot be relabelled an untouched holdout.

The AMOC numerical screening results below predate the current checkout's
convection-normalization correction. They describe the earlier EOS repair,
not the corrected model's validated historical or future response. Local
convection still uses a reduced linear density-anomaly closure; TEOS-10 applies
to the hydraulic density calculation. Its reference now uses the linear EOS
independently, so selecting a hydraulic EOS cannot also rescale local convection.
See `CURRENT_MODEL_REVIEW_FIXES.md` for verification scope.

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
