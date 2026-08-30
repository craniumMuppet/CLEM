# Physics repair v2.10

## Purpose

v2.10 addresses the only two failures left by the v2.9 local verification bundle without retuning the now-successful AMOC salt physics or radiative feedback decomposition.

## 1. Seasonally unbiased ECS / TOA diagnosis

The previous equilibrium experiment recorded once per year. With the seasonal Arctic module enabled, that samples effectively one calendar phase and aliases the Arctic external surface-flux anomaly. The dense v2.9 energy experiment proves the problem quantitatively: over years 80-100, 0.05-year sampling gives +1.314 W m-2 mean TOA, while one-phase annual sampling gives +0.794 W m-2.

Changes:

- Local verifier equilibrium experiment renamed to `ecs_step2x_1400y`.
- Duration increased from 1200 to 1400 years so the slow deep-ocean tail has additional time to settle.
- Record interval changed from 1.0 to 0.2 years (five evenly spaced samples/year).
- The equilibrium gate now also compares the phase-averaged TOA flux with the independently diagnosed resolved-heat-content tendency; the absolute mismatch must be <=0.03 W m-2.
- The core `diagnose_climate_sensitivity()` function also records abrupt-2xCO2 at 0.2-year cadence, preventing the same seasonal alias outside the local verifier.

The strict equilibrium requirements remain:

- |annual-mean TOA| <= 0.05 W m-2
- |GMST trend| <= 0.02 C/century
- |AMOC trend| <= 0.10 Sv/century
- late TOA/heat-tendency mismatch <= 0.03 W m-2
- final AMOC > 5 Sv

## 2. Persistent collapsed cold-branch amplitude

`amoc_heat_response_damping_wm2_k` changes from 2.10 to 2.50. This term is conservative: heat removed from the Atlantic anomaly is added to the non-Atlantic ocean according to ocean area, so the change affects the regional AMOC fingerprint rather than the global heat budget.

Measured v2.8 -> v2.9 response provides a direct local estimate:

- short hosing cold blob: -3.458 -> -3.306 C as damping 1.75 -> 2.10
- long collapsed branch: -8.787 -> -8.397 C

Linear interpolation of those measured responses predicts approximately:

- short 180-year cold blob at 2.50: -3.13 C
- persistent collapsed branch at 2.50: -7.95 C

The local run remains authoritative; these are only pre-run estimates.

## Frozen physics

v2.10 leaves unchanged:

- AMOC hydraulic density formulation
- North/deep thermal-stratification coupling
- AMOC surface heat coupling fraction
- sea-ice export salinity normalization and corrected Arctic -> North routing
- sea-ice storage/brine routing
- South Atlantic upper-limb salt topology
- hosing amplitude
- hydrological and Greenland freshwater forcing
- pycnocline closure
- deep-ocean heat capacity
- Planck, water-vapor, lapse-rate, polar-inversion, cloud and albedo parameters
- convection transport exponent and density-driven convection law

## Execution

Run `clem\\clem\\RUN_PHYSICS_VERIFICATION.cmd` on the local machine. Every child process is still limited to <=5 model years, is checkpointed after each committed chunk, and can be resumed by rerunning the same command.
