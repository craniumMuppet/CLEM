# v2.29.1 Arctic Phase-Consistency Maintenance Release

## Purpose

v2.29.1 corrects a thermodynamic singularity introduced by the v2.29.0 two-way Arctic ocean coupling. In v2.29.0, positive sensible heat could remain attached to an open-water reservoir while the open-water fraction approached zero. Reopening a tiny area then divided the retained energy by a vanishing area and produced physically impossible local temperatures despite finite global energy.

## Corrections

- Conservatively remaps open-water sensible heat whenever fractional ice area changes.
- Transfers heat displaced by freeze-up into the coupled shallow/bulk ocean rather than retaining it beneath ice.
- Applies only the transient phase-remapping departure from the periodic reference cycle, preserving the calibrated unforced control.
- Treats openings below 1% of a grid cell as unresolved leads pinned to freezing and transfers their sensible heat to the coupled ocean.
- Tracks local open-water temperature and dormant heat at every internal timestep, independent of output cadence.
- Separates Atlantic and central-Arctic reference-ocean temperature targets from transient exchange coefficients.
- Requires strictly positive open-water/ocean exchange.
- Removes the accidental second application of the winter transport transition.
- Reports reference-cycle energy and temperature closure separately with consistent units.
- Adds hard release-validation and Monte Carlo filters for local Arctic temperature, dormant heat, timestep convergence, resolution convergence, control drift, and phase-cycle closure.
- Makes the release validator return a failing exit status whenever any required gate fails.
- Warns when deprecated compatibility-only Arctic controls are changed.

## Physical treatment

Open-water sensible heat is stored per unit grid-cell area. During freeze-up, the remaining open-water reservoir keeps its local temperature while the heat associated with the closed area is transferred conservatively to the coupled ocean. During transient integrations, this remapping is applied relative to the periodic reference phase change so the unforced reference cycle is not counted twice.

Open fractions below `ARCTIC_MINIMUM_SENSIBLE_OPEN_FRACTION = 0.01` are treated as unresolved leads. They do not retain an independent sensible-heat reservoir. This prevents hidden energy from reappearing as an arbitrarily large temperature when a very small lead reopens.

## New independent controls

- `arctic_atlantic_reference_ocean_temperature_c` — default 0.20°C.
- `arctic_non_atlantic_reference_ocean_temperature_c` — default −0.80°C.
- `arctic_open_water_ocean_exchange_wm2_k` remains the transient exchange strength and must be greater than zero.

The reference target is no longer calculated as freezing temperature plus basal flux divided by an exchange coefficient.

## Verification requirements

The release validator requires:

- no dormant positive open-water sensible heat under effective ice cover;
- bounded transient local Arctic open-water temperatures;
- convergent local temperatures at 0.1-, 0.05-, and 0.025-year timesteps;
- bounded cross-resolution local-temperature spread at 2.5°, 5°, and 10°;
- periodic reference-cycle closure in both energy and temperature units;
- stable 500-year control behavior;
- acceptable resolved heat-budget closure;
- successful hosing and perturbation recovery checks.

Final numerical results are stored in `VALIDATION_SUMMARY_V2_29_1.json`, `DEEP_VALIDATION_V2_29_1.json`, and `IMPLEMENTATION_AUDIT_V2_29_1.json`.

## Final validation results

Final default validation results are **1.106°C** historical GMST, **381.51 ZJ** ocean heat gain, **3.586×** annual Arctic amplification (**4.851× DJF**, **1.744× JJA**), **21.20%** SSP2-4.5 AMOC weakening, and **39.98%** SSP5-8.5 weakening. Peak internal-timestep Arctic open-water temperature is **13.05°C** under SSP2-4.5 and **17.89°C** under SSP5-8.5, with zero dormant sensible heat. The 20-year abrupt-2×CO2 energy residual is **-0.047%**, 500-year GMST drift is **9.97e-6°C**, whole-domain salt error is **0.0 ppm**, and AMOC recovery after the hosing test is **85.81%**. These are development-regression checks, not independent validation.
