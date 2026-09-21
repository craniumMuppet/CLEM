# v2.29.7 Native Arctic Integrity

## Purpose

v2.29.7 addresses the remaining temporal-skill, open-water-temperature, uncertainty-surface, and provenance findings identified after the independent v2.29.6 review. The native thermodynamic sea-ice state remains the primary process output: published area is the direct hemispheric integral of that state, while 15% extent is a separate bounded, continuous, zero-preserving diagnostic.

## Selected default configuration

The selected calibration changes only explicit physical or structural controls already present in the model:

| Control | v2.29.7 default |
|---|---:|
| Arctic module transition start | 52.0°N |
| Reference-air seasonal amplitude | 12.0°C |
| Unresolved Arctic lapse/inversion closure | 1.20 W m⁻² K⁻¹ |
| Basal ocean–ice exchange | 4.00 W m⁻² K⁻¹ |
| Open-water/bulk-ocean exchange | 30.0 W m⁻² K⁻¹ |
| Conservative lateral ocean restoring | 27.5 W m⁻² per ice-fraction anomaly |
| Transient sea-ice shortwave scale | 1.00 |
| AMOC convection recovery | 150 years |

Each tuning-informed control is available through the normal interfaces where appropriate and is represented in the built-in Monte Carlo uncertainty system. The default AMOC hydraulic ceiling remains a smooth 20 Sv saturation and is also sampled.

The 150-year convection-recovery default is a small adjustment from the prior 160-year value. It preserves the unchanged release requirement that the standard 40-year, 0.1 Sv freshwater-hosing experiment recover at least 80% of its AMOC loss after 100 years without hosing.

## Selected-candidate diagnostics

The frozen selected-candidate record is `V2_29_7_SELECTED_PHYSICS_DIAGNOSTICS.json`.

- 1979–2020 March native area: 13.125 million km².
- 1979–2020 September native area: 4.006 million km².
- September native-area trend: −0.334 million km² per decade, approximately 68% of the observed trend.
- 2021–2025 September native-area RMSE: 0.238 million km².
- Annual Arctic amplification: 3.125×; DJF 4.018×; JJA 1.996×.
- All four raw annual rolling-origin persistence skill scores are positive.
- All four broad OISST development-temperature bounds pass.
- Maximum dormant open-water heat is zero.
- Reference-cycle closure and convergence residuals are zero at recorded precision.
- The unforced reference cycle contains more March and September ice than the warmed 1979–2020 historical state, while its March–September amplitude remains within 1 million km² of the historical model amplitude. The release no longer treats modern observed means as direct targets for the preindustrial reference cycle.

These values are development diagnostics, not independent predictive validation.

## Integrity constraints retained from v2.29.6

- No intercept-based sea-ice area correction.
- Exact identity between native and published sea-ice area.
- Continuous, monotone, bounded and zero-preserving extent mapping.
- No active winter equivalent-thickness calibration cap; the 8 m limit remains an inactive emergency guard.
- No legacy Northern Hemisphere sea-ice double counting.
- Equal-and-opposite Arctic surface/ocean and lateral-ocean energy transfers.
- Whole-domain salt projection limited to numerical roundoff, with the pre-projection residual reported.
- Smooth AMOC hydraulic saturation prevents unphysical restart overshoot.

## Remaining scientific scope

The Arctic reference atmosphere is still a prescribed reduced sinusoidal climatology. The prognostic ice, open-water, interface, atmosphere-anomaly and ocean states evolve thermodynamically relative to that control, but this is not a fully coupled atmospheric control climate. Native sea-ice projections and Arctic open-water temperatures therefore remain reduced-complexity sensitivity outputs rather than precise regional forecasts.
