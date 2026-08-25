# v2.29.0 coupled Arctic ocean release

## Scope

v2.29.0 completes the structural follow-up identified in the v2.28 review. It preserves the v2.28.1 global climate, AMOC, freshwater, and Greenland defaults while replacing one-way Arctic surface coupling and the active open-water ceiling.

## Structural changes

1. The local prognostic Atlantic or non-Atlantic ocean anomaly is added to a periodic sector-specific shallow reference-ocean temperature.
2. Basal sea-ice heat flux is proportional to the shallow-ocean temperature above the configured freezing point.
3. Open water exchanges sensible heat with the shallow ocean according to their temperature difference.
4. The complete ocean-to-surface flux anomaly is subtracted from the bulk ocean with equal magnitude.
5. The periodic reference ocean evolves under its own heat capacity, surface exchange, and restoring heat convergence.
6. Open-water sensible heat is no longer clipped at 4°C; the old maximum-temperature field is retained only for configuration compatibility.

## Default coupling controls

| Setting | Default | Meaning |
|---|---:|---|
| `arctic_basal_ocean_exchange_wm2_k` | 1.50 | Basal ice/ocean exchange |
| `arctic_open_water_ocean_exchange_wm2_k` | 1.50 | Open-water/ocean exchange |
| `arctic_reference_ocean_heat_capacity_wyr_m2_k` | 6.0 | Periodic shallow-ocean thermal inertia |
| `arctic_reference_ocean_restoring_wm2_k` | 12.0 | Unresolved reference-ocean heat convergence |

## Verification targets

The release workflow runs 16 isolated validation tasks: SSP2-4.5, SSP5-8.5, supplementary SSP1-2.6 and SSP4-6.0 pathways, a 20-year abrupt-2×CO₂ energy audit, the Arctic reference cycle, three timestep checks, 500-year control, warm/cold perturbation recovery, hosing recovery, and three grid resolutions.

The prescribed Arctic atmospheric control climatology remains a deliberate reduced-complexity boundary condition. The new shallow reference ocean is also a closure, not a resolved ocean circulation model.
