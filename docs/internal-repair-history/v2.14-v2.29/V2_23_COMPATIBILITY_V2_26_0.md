# v2.23 compatibility and intentional v2.26 behavior changes

## Preservation result

The unchanged maintained v2.23 pytest suite was executed against the v2.26 source tree.

- **31 tests passed unchanged.**
- **2 assertions failed intentionally.**
- Optional Hypothesis properties were skipped because Hypothesis was not installed in the execution environment.

AMOC root finding, branch matching, pseudo-arclength continuation, stability classification, salt conservation, Greenland mass accounting, and ocean heat-content diagnostics passed. The original legacy smoke suite differs only in its hosing cold-blob amplitude threshold, described below.

## Intentional differences

### Evidence role

One unchanged v2.23 assertion expects the external benchmark metadata field `used_for_tuning` to be `false`. That statement became incorrect after v2.24–v2.26 parameters were adjusted using those ranges. v2.26 therefore reports `used_for_tuning=true` and describes the comparisons as development regressions rather than independent held-out validation.

### Hosing cold-blob amplitude

The original v2.23 smoke test requires the 0.5 Sv hosing experiment to cool the North Atlantic by at least 1.0°C more than the 0.1 Sv experiment. v2.23 produced a 1.91°C contrast; v2.26 produces 0.82°C while retaining a positive weak-hosing AMOC and near-zero strong-hosing AMOC. The smaller temperature contrast is an intentional consequence of reducing `amoc_surface_heat_coupling_fraction` from 0.20 to 0.075 and recalibrating `amoc_temperature_density_coupling` to 0.71. It is not repaired by increasing freshwater forcing and persists when the seasonal Arctic module is disabled.

These are versioned evidence/response changes, not hidden test relaxations.

## Default-behavior changes since v2.23

The following output changes are intentional and versioned:

1. Ocean vertical exchange is 1.10 W/m²/K rather than 0.85 W/m²/K.
2. The Arctic output is a prognostic seasonal near-surface-air state rather than a blended land/ocean mixed-layer diagnostic.
3. Arctic sea ice uses thermodynamic interface enthalpy and orbital insolation.
4. Greenland freshwater defaults to 0.005 Sv/K; hydrological freshwater remains 0.006 Sv/K.
5. Duplicate AMOC convection density-memory feedback is disabled by default.
6. AMOC greenhouse responses therefore differ numerically from v2.23 even though the v2.23 solver and conservation invariants are retained.
7. `greenland_freshwater_sv` is the seasonally routed applied flux in v2.26; `greenland_annual_mean_freshwater_sv` exposes the slow annual-mean state.

## Compatibility controls

- `seasonal_arctic_enabled=false` disables the thermodynamic seasonal subsystem for diagnostic comparisons.
- Legacy empirical Arctic multiplier fields are accepted from old configuration files but hidden from normal interfaces.
- When seasonal Arctic physics is enabled, legacy multiplier values have exactly zero numerical effect.
- Historical v2.23 documentation, tests, and validation records remain in the package unchanged.

## Interpretation

v2.26 is source- and workflow-compatible with the maintained v2.23 architecture, but it is not intended to reproduce every v2.23 trajectory. The differences above are explicit model-version changes and should be treated as a new calibrated structural family when comparing archived experiments.

## AMOC structural calibration

v2.26.0 uses `amoc_temperature_density_coupling = 0.71`. This is an intentional post-v2.23 structural calibration change. It jointly bounds SSP2-4.5, SSP5-8.5, hybrid-transition, hosing, and control behavior while retaining hydrological and Greenland freshwater sensitivities at 0.006 and 0.005 Sv/K.
