# v2.29.15 Winter Sea-Ice Integrity Fixes

## Scope

v2.29.15 addresses the two P1 findings in the independent review of v2.29.14. It does not retune the global climate, AMOC, Greenland, or sea-ice calibration parameters. The changes are restricted to winter lead-closure state reconstruction and the physical behavior of that closure as ice volume and transient winter temperature change.

## 1. Saved diagnostics now describe the integrated state

The v2.29.14 integration diagnosed concentration with the periodic reference concentration and winter lead-closure weight, but `ProcessClimateModel.run().append_record()` reconstructed local ice thickness and open-water temperature without those arguments. Saved maps could therefore combine closure-adjusted concentration with pre-closure local fields.

v2.29.15 records each Arctic sector by:

1. reconstructing total ice energy and open-water heat from the periodic reference plus the prognostic anomaly;
2. calculating the seasonal closure envelope from the periodic reference air temperature and applying the actual transient sector air temperature as a smooth near-melt gate;
3. calling `_arctic_ice_energy_to_state()` with the same reference concentration and closure weight used by integration;
4. calculating local thickness and open-water temperature from that reconstructed concentration.

The regression suite verifies at the final simulated state that:

- saved local thickness equals direct state reconstruction;
- saved open-water temperature equals direct state reconstruction;
- saved effective concentration equals the integrated seasonal concentration in fully active Arctic bands;
- saved concentration multiplied by saved local thickness equals grid-equivalent ice thickness in fully active Arctic bands.

## 2. Winter closure now vanishes continuously with ice volume

The v2.29.14 closure could restore a fixed fraction of the reference winter concentration for any positive equivalent thickness. An arbitrarily small volume could therefore cover most of a grid cell and disappear discontinuously at exactly zero volume.

v2.29.15 introduces two linked constraints:

- **Smooth volume taper:** the closure increment is multiplied by a cubic smoothstep support factor. The factor approaches zero continuously as equivalent thickness approaches zero and reaches one only when enough volume exists to support the closure target at the minimum local thickness.
- **Available-volume concentration cap:** concentration cannot exceed `equivalent_thickness / 0.03 m`, clipped to the physical range. The 0.03 m value is the same minimum local thickness already used by the thermodynamic conductive-flux calculation.

The mapping remains exactly volume-conserving because local thickness is always diagnosed as equivalent thickness divided by concentration.

## 3. Closure activation uses the transient thermal state

v2.29.14 calculated closure strength from the unforced reference-air climatology. Strong closure could therefore remain active during a severely warmed winter.

v2.29.15 retains the periodic reference-air coldness ramp as the seasonal envelope, then multiplies it by a smooth gate derived from actual transient Arctic air temperature. The gate is one while actual air remains at least one third of the configured seasonal temperature scale below freezing (5 C at the default), weakens continuously inside that near-melt interval, and reaches zero at the freezing point. The unforced control and ordinary cold winters retain the calibrated seasonal timing, while a severely warmed winter can no longer inherit full closure solely from the unforced climatology.

## Independent review reproduction

`V2_29_15_REVIEW_REPRODUCTION.json` repeats the review's 1850-2101 SSP2-4.5 run at 10-degree resolution. In fully active Arctic bands, saved local-thickness and open-water-temperature errors are exactly zero, saved concentration errors are below `3e-13`, and concentration-times-local-thickness volume errors are below `6e-13 m`. At `1e-9 m` equivalent thickness, concentration is about `5.0e-10` under both the default 0.65 and upper-prior 0.90 closure weights, rather than the former 0.637 and 0.882 finite-area states.

## March-response retention

The revised transient-temperature gate retains the v2.29.14 historical March behavior instead of using transient warming as the entire seasonal weight. In the canonical SSP2-4.5 validation run:

- March native-area trend: `-0.055998 million km2/decade`;
- observed fitted March-area trend: `-0.038174 million km2/decade`;
- trend-magnitude ratio: `1.467`;
- March area correlation: `0.143`;
- March area RMSE: `0.382 million km2`;
- March 15% extent trend: `-0.0651 million km2/decade`.

The trend improvement from v2.29.14 is therefore retained, but the weak correlation, RMSE, and extent-trend limitations are unchanged. These remain tuning-informed development diagnostics rather than independent predictive skill.

## Scientific interpretation

These fixes remove the diagnosed state inconsistency and the near-zero-volume finite-area artifact. They do not establish independent winter temporal skill. Historical March correlation, RMSE, area trend, and extent trend remain development diagnostics, and future winter ice timing remains a reduced-complexity sensitivity output.
