# Structural AMOC fixes in v2.17.0

## Finite Greenland reservoir

The Greenland freshwater source now draws from a prognostic finite ice mass. The target flux depends on warming, remaining ice fraction and a configurable cap. Actual discharge cannot exceed the ice mass available during a timestep. Outputs include remaining mass, remaining fraction, cumulative melt and cumulative sea-level equivalent.

Default values:

- initial ice mass: 2.61345 million Gt (converted from 2.85 million km³ at 917 kg/m³; the original 2.85-million-Gt label was a unit error corrected after v2.17.0);
- depletion exponent: 1.0;
- maximum freshwater flux: 0.05 Sv.

This prevents an indefinitely sustained temperature-proportional flux, but it remains a reduced parameterization rather than a dynamic ice-sheet model.

## Absolute density-margin screening

The model still uses a normalized density ratio in the hydraulic response, but it now also evaluates the absolute initial density driver against a common reference. By default, members outside 0.75–1.25 of the reference margin are rejected before projection. The physical-prior sampler applies the same joint hydrographic rule.

## Collapse and reversal

The default dynamics prohibit negative AMOC. The signed hydraulic target remains available for diagnostics, and negative circulation may be enabled with `--amoc-allow-reversal` for explicit sensitivity experiments. Final-state reporting separates:

- active: AMOC > 6 Sv;
- weak/collapsed: 0 <= AMOC <= 6 Sv;
- reversed: AMOC < 0 Sv.

## Joint response calibration

The defaults were tuned against both configured AMOC-response diagnostics using their actual likelihood periods:

- SSP5-8.5: 1995–2014 mean compared with 2081–2100 mean;
- hosing: decline after approximately 40 years under 0.1 Sv freshwater forcing.

Validated central results:

- SSP5-8.5 weakening: 20.94%;
- 0.1 Sv hosing weakening: 12.26%;
- SSP2-4.5 minimum AMOC through 2500: 14.42 Sv;
- SSP2-4.5 final AMOC: 16.19 Sv.

These fall inside the model's configured calibration ranges while avoiding a default long-term SSP2-4.5 collapse.

## Posterior rerun requirement

All v2.16.x posterior weights and probabilities are invalid under v2.17.0 because the equations, rejection rules and priors changed. Run a new ensemble. For final inference, use built-in physical priors, `ar6_amoc` weighting and enough members to obtain a healthy effective sample size.

## Validation

The automated suite checks salt conservation, reservoir mass conservation, density screening, reversal opt-in, SSP pathway switching, continuous collapse, hosing response, completion reporting, GUI command generation and full transient regression. The Tk visual layout test could not run in the headless build environment; GUI command construction and tooltip coverage passed.
