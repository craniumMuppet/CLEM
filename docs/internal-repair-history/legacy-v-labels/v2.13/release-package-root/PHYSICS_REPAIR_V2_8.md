# CLEM physics repair v2.8

v2.8 is a narrow follow-up to the fully completed v2.7 local verification.
Long climate integrations are intentionally not run during package construction;
all verification remains on the user's computer in <=5-model-year child chunks.

## What v2.7 established

- TCR: 1.9218 C (passes AR6 likely range).
- Gregory 1-150 effective ECS: 2.848 C.
- 1200-y step-2x tail temperature: 3.210 C, but NOT equilibrated: tail TOA -0.510 W/m2.
- Planck: -3.266 W/m2/K.
- WV: +1.810 W/m2/K.
- resolved LR: -0.464 W/m2/K; polar inversion closure +0.032 W/m2/K.
- WV+LR+polar: +1.378 W/m2/K.
- cloud: +0.436 W/m2/K; albedo: +0.293 W/m2/K; net feedback: -1.159 W/m2/K.
- 0.5-Sv hosing collapse and -4.09 C 180-y cold blob pass.
- Energy residual: 0.034%; salt conservation and seasonal-Arctic dt convergence pass.
- Pycnocline closure converges to ~2e-6 Sv.
- Reference residual is negligible (~1e-16 W/m2 equivalent).

## Remaining v2.7 problems

1. The 1200-y 2xCO2 run is not a clean ECS equilibrium. TOA crosses zero and becomes
   increasingly negative while AMOC weakens from ~9 Sv at year 300 to 1.66 Sv at year 1200.
2. The latent-energy sea-ice export closure implied a raw reference mass export of ~0.209 Sv
   in the actual seasonal-Arctic configuration, substantially above the observational-scale
   ~0.06-0.09 Sv cited in the physics review. Direct conversion therefore overcoupled sea-ice
   export anomalies into AMOC salinity.
3. The old `thermal_only` test was contaminated by sea-ice freshwater/brine coupling.
4. The persistent zero-hosing collapsed branch reached -10.98 C in the cold-blob diagnostic.

## v2.8 changes

- Adds `arctic_ice_export_freshwater_reference_sv = 0.075`.
- Computes the model's raw annual reference ice-export freshwater equivalent once at setup.
  For 10-degree seasonal Arctic this is 0.20894 Sv; the salinity-only scale is therefore
  0.35896. The Arctic latent-energy transport itself is unchanged.
- Adds `arctic_sea_ice_salinity_coupling_enabled` so the verifier can isolate pure thermal
  AMOC response without disabling Arctic thermodynamics/albedo/energy exchange.
- `thermal_only_step2x_150y` now disables every freshwater route into the AMOC boxes.
- Adds `thermal_plus_seaice_step2x_150y` with only the normalized sea-ice salinity pathway,
  allowing its contribution to be measured directly.
- Increases conservative Atlantic/non-Atlantic heat compensation from 0.75 to
  1.75 W m-2 K-1. This does not change global heat content; it limits the equilibrium
  regional cold-blob amplitude without weakening the thermohaline density pathway.
- Tightens long collapsed-branch cold-blob gate to >= -8 C.
- ECS convergence now requires all three: |tail TOA| <= 0.05 W/m2,
  |GMST trend| <= 0.02 C/century, and |AMOC trend| <= 0.10 Sv/century.
- Adds raw/scaled ice-export diagnostics and explicit pure-thermal vs thermal+sea-ice AMOC
  comparison.

No WV, cloud, albedo, Planck, hydrological, Greenland, salt-loop topology, pycnocline,
energy-accounting, or AMOC density coefficients are changed in v2.8.
