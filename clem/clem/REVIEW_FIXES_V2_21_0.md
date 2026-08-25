# Scientific review fixes in v2.21.0

## 1. Whole-domain AMOC equilibrium continuation

The continuation state now contains five independent salinities, AMOC transport, convection efficiency and pycnocline depth. External-reservoir salinity is reconstructed from the conserved salt inventory of all six boxes.

Accepted roots must satisfy:

- the five independent salinity equations;
- the diagnosed external-reservoir salinity tendency;
- whole-domain salt closure;
- AMOC, convection and pycnocline tendencies.

The output records the maximum full salinity tendency, the external tendency and the salt-closure error for each branch point.

## 2. Differentiable stability system

The convection timescale no longer switches abruptly between weakening and recovery. A hyperbolic-tangent blend controlled by `amoc_convection_timescale_smoothing` creates a differentiable vector field.

The local Jacobian uses central differences. Stability is no longer determined from the Jacobian alone.

## 3. Nonlinear perturbation validation

Every candidate root is perturbed positively and negatively along every independent equilibrium coordinate. The reduced autonomous AMOC system is then integrated for 800 years with a Heun step. A root is labelled stable only if:

- the maximum real Jacobian eigenvalue is negative; and
- all signed nonlinear perturbations remain bounded and return toward the root.

The continuation CSV includes separate linear and transient stability fields.

## 4. Collapse-threshold semantics

`amoc_collapse_threshold_sv` is now the single semantic threshold for active and weak/collapsed labels. Reversal remains a separate negative-transport state.

The historical 6 Sv reference is retained only as `amoc_below_six_sv_reference` and as a plotting reference. Hysteresis summaries use the threshold stored in the experiment unless an explicit override is supplied.

## 5. Calibration and held-out validation

Sensitivity diagnostics are tagged as `calibrated_process_diagnostic` and explicitly state that they are not independent validation. Monte Carlo summaries contain an `evidence_partition` with separate calibration and held-out lists. Held-out validation exports are tagged `held_out_validation` and `used_for_posterior_weighting: false`.

## 6. Reversible and regional freshwater response

The separated freshwater formulation now supports:

- signed hydrological anomalies under cooling;
- a regional 60-85 N land-temperature proxy for Greenland forcing;
- negative Greenland freshwater flux as net accumulation;
- finite regrowth limited by missing ice mass;
- net ice-loss and sea-level-equivalent accounting.

The legacy `warming_freshwater_sv_per_k` override remains one-sided for backward compatibility.

## 7. Verification

The v2.21.0 regression suite directly checks:

- full six-box equilibrium salinity closure with active external exchange;
- smooth convection timescales and central-Jacobian stability;
- signed nonlinear root perturbations;
- custom collapse-threshold consistency;
- calibration-versus-validation metadata;
- cooling-driven hydrological reversal and Greenland regrowth.
