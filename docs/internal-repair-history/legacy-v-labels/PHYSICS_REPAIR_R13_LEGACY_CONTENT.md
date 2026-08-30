# CLEM physics repair v2.13 - release consistency

v2.13 does not change the validated climate dynamics.

The v2.12 held-out suite passed SSP2-4.5 warming, AMOC decline-without-collapse, 5 degree versus 10 degree consistency, monotonic 0.1/0.2/0.3 Sv hosing response, and salt conservation. The earlier v2.11 full suite also passed ECS, TCR, energy, salt, timestep, pycnocline, cryosphere-freshwater, hosing-collapse, and persistent-branch gates.

## Release bug fixed

The public command-line parser still contained several pre-repair hard-coded defaults even though `ModelConfig` had the validated values. A normal CLI run could therefore differ materially from the model that was verified.

Fixed defaults:

- `--water-vapor-height`: 0.80 -> `ModelConfig().water_vapor_emission_height_km_per_lnq` = 0.98
- `--amoc-convection-critical-density-ratio`: 0.91 -> ModelConfig = 0.00
- `--amoc-convection-transition-width`: 0.035 -> ModelConfig = 0.10
- `--amoc-convection-density-scale-factor`: 4.00 -> ModelConfig = 1.00
- `--amoc-convection-transport-exponent`: 1.0 -> ModelConfig = 0.00

The AMOC salt-loop comment was also corrected to match the validated Deep -> South Atlantic upper limb -> Tropical -> North -> Deep advective loop, with the Southern surface box used as the density reference rather than an advective limb.

## Dynamics equivalence

Validated v2.11/v2.12 source SHA-256:
`f08e901aac796c7fd757a52345709b0d9e3d20ec34c92f6afc0d53d8f7a824b9`

v2.13 source SHA-256 after CLI/documentation repair:
`7cf8458b1622f4afc28eeb0cd9b133bb50b5500094521e029d8b66f08b6df248`

Core Python AST SHA-256 with only top-level `build_parser()` excluded:
`e84dbff3f68b3e0e6a69a3d2aa140e10a7c59097bfaab9e801e00d04662e7b89`

The core AST hash is identical before and after v2.13. The numerical equations, `ModelConfig` defaults, prognostic state evolution, and diagnostics outside the CLI parser are unchanged.

## Remaining scientific limitation

The SSP2-4.5 run underestimates the RAPID-era absolute AMOC mean: about 14.2 Sv for 2004-2020 versus RAPID 16.9 +/- 1.2 Sv. This is retained as a documented limitation rather than post-hoc tuned after held-out validation. See `V2_12_RESULTS_REVIEW.md`.
