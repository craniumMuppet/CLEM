# Continuous AMOC formulation in v2.16.0

Version 2.16.0 removes the explicit AMOC collapse/restart state switch introduced in v2.15.

## Removed from the dynamics

The following v2.15 operations no longer occur:

```python
if convection_density_ratio <= collapse_threshold:
    convection_collapsed = True

if convection_collapsed:
    convection_target = min(convection_target, collapsed_fraction)
```

The legacy configuration keys remain in `ModelConfig` only so older JSON files can be loaded. They are ignored by the equations and are no longer exposed by the CLI, GUI, Streamlit application or Monte Carlo priors.

## Continuous mechanism

The local northern surface-to-deep density state sets a smooth convection target. The current convection state also contributes continuous entrainment support:

```text
effective density ratio
    = environmental density ratio
    + entrainment feedback * (convection efficiency - 1)
```

The target convection efficiency is a normalized logistic response of that effective ratio. No conditional branch changes the target.

Active convection additionally exchanges salt between the northern surface box and the deep Atlantic:

```text
convective exchange
    = reference exchange * convection efficiency ^ exponent
```

The salt tendency is conservative: salt gained by the northern box is removed from the deep box.

This creates the feedback:

```text
warming and freshwater lower northern density
-> convection weakens
-> vertical salt entrainment weakens
-> northern surface water freshens further
-> convection and AMOC weaken further
```

The AMOC-collapse flag in output is now diagnostic only. It is set when AMOC is below the reporting threshold and convection is weak, but it never changes a tendency, target or state transition.

## New default controls

```text
amoc_convection_critical_density_ratio = 0.88
amoc_convection_transition_width = 0.035
amoc_convective_mixing_reference_sv = 5.0
amoc_convective_mixing_exponent = 2.0
amoc_convection_entrainment_feedback = 0.10
```

These controls are available as deterministic settings and optional Monte Carlo adjustors.

## Validation with the uploaded experiment configurations

The old v2.15 AMOC parameters in the uploaded JSON files were migrated to the v2.16 defaults before validation.

### SSP5-8.5 central configuration

- Minimum AMOC: about 0.28 Sv
- First year below 2 Sv: about 2264
- Final AMOC in 2500: about 0.39 Sv
- Largest annual convection-target change: about 0.0089
- No one-timestep collapse command is involved

### 0.5% carbon pulse to 2200 ppm central configuration

- Minimum AMOC: about 13.92 Sv
- Final AMOC: about 17.63 Sv
- No collapse under the central v2.16 parameter set
- Largest annual convection-target change: about 0.00068

This is a scientifically meaningful change: the previous carbon-pulse collapse was largely created by the explicit branch switch. Under continuous physics, the central pulse run weakens and recovers instead. Monte Carlo members with stronger freshwater sensitivity, weaker convective entrainment or narrower convection transitions may still collapse.

## Interpretation

The transition is now emergent within the reduced equations, but the model remains an emulator rather than a resolved ocean GCM. The logistic convection closure and entrainment coefficients are still parameterizations and should be sampled in uncertainty experiments. A low-AMOC state should be interpreted as a property of this continuous box-model closure, not as a calibrated real-world tipping probability.
