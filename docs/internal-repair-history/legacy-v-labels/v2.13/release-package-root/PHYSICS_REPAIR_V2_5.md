# CLEM physics repair v2.5

This candidate keeps the v2.4 thermal, energy, pycnocline, cryosphere, and checkpointing repairs unchanged and fixes the remaining structural AMOC salt-loop problem identified by the v2.4 local verification run.

## Structural salt-loop repair

The Southern Ocean surface density-reference box is no longer inserted into the overturning salt-advection loop.

Positive AMOC salt advection now follows:

`deep return -> South Atlantic upper limb -> tropical Atlantic -> North Atlantic -> deep return`

Negative AMOC reverses the same four-box loop.

The separate Southern Ocean surface box remains prognostic and continues to enter the north-versus-south density calculation, but it is not treated as the water mass directly crossing 34.5 S in the northward upper limb. The existing FovS diagnostic already uses the South Atlantic upper-limb and deep tracers, so the diagnostic and the actual advective boundary transport now use the same two limbs.

## Control-state consequences

Setup-only static checks at 10-degree resolution give:

- initial FovS: -0.150 Sv
- AMOC control density ratio: 1.000
- North control freshwater flux: +0.314286 Sv
- Tropical control freshwater flux: -0.218908 Sv
- South Atlantic upper-limb control freshwater flux: -0.095378 Sv
- Southern surface control freshwater flux: approximately 0 Sv
- sum of control freshwater redistribution: approximately 0 Sv

This removes the v2.4 artificial pair of roughly +1.04 Sv Southern freshwater input and -1.14 Sv South-Atlantic-upper evaporation that had been required only because the fresh Southern surface box was being advected directly through the 17-Sv overturning loop.

## Verification workflow

Run `clem/clem/RUN_PHYSICS_VERIFICATION.cmd` on the local machine. Every model integration remains limited to at most five model years per child process and is checkpointed after every chunk. The final `physics_verification_bundle.zip` includes the full results and source fingerprints.
