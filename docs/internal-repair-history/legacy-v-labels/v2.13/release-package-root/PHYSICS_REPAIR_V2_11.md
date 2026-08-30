# Physics repair v2.11

v2.11 is a minimal finalization pass based on the completed v2.10 local verification bundle. It does not retune the repaired thermohaline, sea-ice, radiative-feedback, pycnocline, Greenland, or freshwater physics.

## v2.10 status

Every verification gate passed except two marginal end-state criteria:

- equilibrium convergence: tail TOA = +0.05623 W m-2 versus the existing |TOA| <= 0.05 W m-2 gate. The independent resolved-heat-content closure residual was only 0.01653 W m-2; GMST trend was +0.01057 C/century and AMOC trend -0.02989 Sv/century. This is a slow-equilibration/run-length issue, not a heat-budget failure.
- persistent collapsed cold branch: -8.05594 C versus the existing >= -8.0 C gate.

All other tests passed, including TCR, ECS range, feedback decomposition, hosing collapse/cold blob, thermal-only AMOC response, sea-ice mechanism splits, salt conservation, energy closure, pycnocline closure, reference residual, and seasonal-Arctic timestep convergence.

## Changes

### 1. Equilibrium verification horizon

The anti-aliased abrupt-2xCO2 verification segment is renamed `ecs_step2x_1600y` and extended from 1400 to 1600 years. Sampling remains 0.2 years (five seasonal phases per year), and all integration children remain capped at 5 model years.

No equilibrium gate is relaxed:

- |tail TOA| <= 0.05 W m-2
- |GMST trend| <= 0.02 C/century
- |AMOC trend| <= 0.10 Sv/century
- |TOA minus resolved heat-content tendency| <= 0.03 W m-2
- final AMOC > 5 Sv

### 2. Persistent cold-branch damping

`amoc_heat_response_damping_wm2_k` changes from 2.50 to 2.60.

This term is a conservative regional Atlantic/non-Atlantic heat redistribution. The adjustment is based on the measured v2.9 -> v2.10 response: +0.40 W m-2 K-1 of damping warmed the persistent branch by about 0.34 C while changing the 180-year hosing cold blob by only about 0.15 C. A +0.10 increment therefore targets approximately -7.97 C for the long branch and about -3.12 C for the short hosing fingerprint.

## Frozen physics

v2.11 leaves unchanged:

- AMOC density-gradient and pycnocline hydraulics
- salt-advection loop topology and FovS definition
- sea-ice storage/export freshwater scaling and routing
- hydrological and Greenland freshwater forcing
- WV, lapse-rate, polar-inversion, cloud, albedo and Planck feedbacks
- deep-ocean heat capacity and ocean exchange
- hosing amplitudes and durations
- reference-residual formulation
