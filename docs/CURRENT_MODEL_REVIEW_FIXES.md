# Current-model review corrections — 2026-09-11

**September 12 recovery follow-up:** the year-3,000 continuation passes the
unchanged pycnocline thresholds. See `RECOVERY_EXTENSION_RESULTS_2026_09_12.md`
for the remaining drift, recovery interpretation and checkpoint provenance.

**Numerical follow-up completed:** all 19 planned experiments now have current
results. Of 99 explicit pass flags, 98 pass; the long-recovery pycnocline
equilibrium check remains unresolved. See
`CURRENT_MODEL_VALIDATION_RESULTS_2026_09_11.md`. The regression-only scope
described below records the checks performed before that full run.

These changes apply to the Unreleased checkout after v2.29.29. They change
TEOS-10 trajectories and diagnostic definitions. Previously generated numerical
outputs and release-equivalence manifests remain historical evidence and are
not regenerated or relabelled by this correction.

## Temperature diagnostics

ECS, TCR, the Gregory fit and its plot, and feedback normalization now use
`global_near_surface_air_warming_c`, the model's global near-surface air proxy.
The sensitivity summary declares the temperature field. The same experiments
also report `bulk_surface_equilibrium_response_c` and
`bulk_surface_transient_response_c` for explicit comparison with older outputs.
The existing bulk field in ordinary time series retains its original meaning.
Monte Carlo sensitivity and feedback scoring consume the corrected diagnostics.

For context only, re-expressing the saved, pre-correction 5-degree SSP batch's
sensitivity experiments in their existing air-temperature field gives about
3.482 degrees C versus 3.272 degrees C for the equilibrium response, and
2.069 degrees C versus 1.909 degrees C for the transient response. These are
temperature-definition comparisons on old trajectories, not new runs of the
corrected physics. No calibration targets were fitted to these values.

The model's air-temperature field is still a reduced spatial proxy rather
than a fully resolved atmosphere. This correction makes diagnostic definitions
consistent; it does not establish independent predictive skill.

## Convection and the hydraulic EOS

The retained local convection equation computes a linear surface-to-deep
density anomaly. Previously its normalization used the selected *hydraulic*
control density. Switching from linear density to TEOS-10 therefore changed
both the hydraulic response and the scale of local convection.

The local normalization now derives its reference from the same control
hydrography using the linear EOS, independent of the hydraulic EOS selection.
The linear configuration retains its previous reference, while TEOS-10 no
longer introduces an additional rescaling of the linear convection equation.
No freely adjustable density reference was added. The existing local scale
factor continues to multiply the reference. The AMOC diagnostic exposes
`amoc_convection_reference_density_driver` for inspection.

At default hydrography, a 0.2 PSU northern freshening now gives the same local
convection target, approximately 0.704526, for linear and matched TEOS-10
hydraulics. Before correction, TEOS-10 gave approximately 0.878049. Hydraulic
targets still differ between the equations of state, as intended. Regression
tests isolate both freshening and thermal stratification at 5 and 10 degrees.

The local convection closure remains linear. The broader AMOC geometry,
normalization and transport laws remain structural assumptions. Historical
AMOC, hosing, recovery, equilibrium branches and SSP responses need refreshed
numerical validation before a new tagged release; the earlier historical mean
and approximately 17–18% SSP2-4.5 decline are pre-correction results.

## Monte Carlo parameter activity

`amoc_reference_density_driver` is excluded from built-in ranges whenever it
does not affect initial-density screening. Explicit custom ranges and direct
sampling calls reject the inactive parameter with an explanation. It remains
available for the linear high-latitude geometry with initial-density screening
enabled. Existing configuration files can still retain the compatibility field.
Other prior distributions are unchanged.

## Historical and current validation

R18.2 provenance tests now audit the frozen R18.1 source snapshot against its
original hashes. The historical runner continues to reject changed governing
physics by default; an explicit source directory is an audit target, not a
switch for executing a different model. Tests cover rejection of current
physics and of an incorrect supplied source hash.

The current static verifier evaluates the thermal density effect with a
fixed-salinity comparison under TEOS-10. It no longer treats unavailable linear
alpha/beta decomposition terms as evidence of a failed thermal-sign check.
CI now executes current-model behavioral tests in addition to collecting the
historical test inventory.

The older control-stability regression now selects the equilibrium nearest
the configured 17 Sv control transport. The root finder orders solutions by
transport, so taking the first solution tested the weak branch instead. The
linear and transient stability assertions themselves are retained.

## Verification scope

The focused regression selection covers temperature metrics and plots,
hydraulic/local-convection isolation, Monte Carlo activity, frozen provenance,
CLI/GUI default parity, sea-ice observation operators and current static checks.
It passes 49 tests. A five-year 0.2 Sv hosing regression uses the production
0.05-year time step with the seasonal Arctic disabled to isolate AMOC behavior;
it weakens AMOC and preserves salt before and after roundoff projection.

Broader checks cover 18 seasonal-Arctic integrations spanning compensated
freshwater routing modes, hosing strengths and time steps, plus Greenland
units and ensemble-integrity behavior. The sensitivity-convergence script
also passes actual integrations, exercising both automatic extension of an
unconverged experiment and explicit convergence reporting. Release identity,
compilation of changed Python files, and collection of all 529 tests pass.
Together, the focused and broader selections pass 70 distinct tests after
correcting the control-branch selection. Repeating the branch probe with the
previous normalization reproduced the same weak-branch test failure; the
17 Sv branch passes both linear and transient checks under both normalizations.

The complete multi-century release-validation matrix is not part of this local
regression result. In particular, passing these checks does not carry forward
the old AMOC tipping thresholds or confirm the old historical fit under the
corrected dynamics.
