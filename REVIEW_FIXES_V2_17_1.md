# Independent-review fixes in v2.17.1

## Compatibility

The default configuration remains **5-degree resolution with the Euler coupled-AMOC update**. That path reproduces v2.17.0 deterministic trajectories to floating-point precision. Existing v2.17.0 posterior ensembles therefore remain usable under the same structural settings.

A new posterior is required when changing to the optional Heun coupling scheme, enabling reversal, changing freshwater compensation family, or otherwise changing the model equations/priors.

## 1. Resolution-independent AMOC regions

The old AMOC regional means selected latitude bands by their centres. At 10-degree resolution, the 60-70 N band was counted in full even though only 60-65 N belongs to the sinking region. This produced an excessively cold northern baseline and an initial density ratio of about 1.55.

v2.17.1 integrates the fractional spherical area of every grid band inside the fixed regions:

- Tropical Atlantic: 10-30 N
- Northern sinking region: 50-65 N
- Southern source region: 65-45 S

The 10-degree initial density ratio is now about 1.185, inside the unchanged 0.75-1.25 screen. At 5 degrees, the region boundaries coincide with cell edges, so the calculation and trajectories are unchanged.

## 2. Configuration validation

`ModelConfig.validate()` now rejects:

- `amoc_external_box_volume_m3 <= 0`
- external-reservoir salinity outside 0-50 PSU

## 3. ECS equilibrium status

`diagnose_climate_sensitivity()` now requires a final-tail mean TOA imbalance at or below a configurable tolerance (default 0.05 W m-2) before reporting the experiment as equilibrated. It reports:

- `equilibrium_converged`
- `equilibrium_simulation_years`
- `equilibrium_tail_years`
- `equilibrium_toa_tolerance_wm2`
- `equilibrium_toa_imbalance_wm2`

Interactive deterministic diagnostics can automatically extend the run up to a configured maximum. Monte Carlo diagnostics retain fixed cost and hard-filter explicitly non-converged members.

## 4. Gregory naming

The positive magnitude is now named `gregory_restoring_coefficient_wm2_k`. The old `gregory_feedback_wm2_k` key/property is retained as a backward-compatible alias.

## 5. Coupled AMOC integration

`amoc_coupling_scheme` supports:

- `euler`: compatibility default; reproduces v2.17.0
- `heun`: predictor-corrector structural variant

The Heun update averages conservative salinity tendencies and jointly predicts/corrects Greenland discharge, salinity, AMOC, convection and pycnocline depth. Salt conservation remains at floating-point precision.

## 6. Calibration versus validation

The Monte Carlo summary now labels likelihood inputs as calibration targets and lists held-out diagnostics separately. Matching SSP5-8.5 weakening and 0.1 Sv hosing is therefore not described as independent validation.

New tools:

- `held_out_amoc_validation.py`: SSP2-4.5 response, 0.2 Sv hosing, recovery and cross-resolution checks excluded from weighting.
- `amoc_structural_family_analysis.py`: treats reversal, compensation and Euler/Heun choices as separate model families.
- `amoc_identifiability_analysis.py`: weighted rank correlations, ESS and a design-matrix condition diagnostic for equifinality.

## Remaining scientific limitation

These changes improve correctness, transparency and testing. They do not independently validate real-world AMOC-collapse probabilities. Collapse estimates remain conditional on the reduced equations, priors, calibration targets and structural family.
