# Physics repair v2.9

v2.9 is a narrow follow-up to the returned v2.8 verification run.

## Physics changes

1. Correct Arctic sea-ice export freshwater geography/sign.
   - Positive export now adds freshwater to the northern sinking-region box.
   - Equal freshwater is removed from the external Arctic/global reservoir.
   - Export no longer touches the South-Atlantic upper-limb box.
   - The 0.075 Sv observational-scale export normalization introduced in v2.8 is retained unchanged.

2. Split sea-ice salinity coupling into independently switchable storage and export pathways.
   - `arctic_sea_ice_storage_salinity_coupling_enabled`
   - `arctic_sea_ice_export_salinity_coupling_enabled`
   - Existing master switch is retained for backward compatibility.

3. Increase `amoc_heat_response_damping_wm2_k` from 1.75 to 2.10.
   - This targets the slightly over-cold persistent collapsed branch.
   - AMOC heat-coupling fraction, density coupling, salt-loop topology, forcing amplitudes, radiative feedbacks, pycnocline closure and deep-ocean parameters are unchanged.

## Verification changes

- Adds thermal + sea-ice-storage-only 150-yr test.
- Adds thermal + sea-ice-export-only 150-yr test.
- Keeps pure-thermal and combined sea-ice tests.
- Reports signed storage/export freshwater anomalies and AMOC increments relative to pure thermal.
- Adds numerical static routing tests for +0.05 Sv export/storage perturbations.
- Adds explicit equilibrium `2xCO2` AMOC-not-collapsed gate (>5 Sv at year 1200) in addition to TOA/GMST/AMOC convergence requirements.
- All integration children remain hard-limited to <=5 model years and checkpoint after every completed chunk.

No long climate integration was run while producing this candidate.
