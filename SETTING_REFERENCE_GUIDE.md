# Setting tooltip reference guide

Version 2.29.26 provides the same setting metadata in the desktop GUI and the Streamlit dashboard.

## What the confidence label means

- **Very high**: the control is exactly defined, numerically validated, or based on a tightly measured physical quantity. For experiment controls, the chosen value is still a user choice.
- **High**: the quantity or assessed range is supported by multiple observing systems or a major scientific assessment.
- **Medium**: the setting has a clear physical basis, but the value is an effective regional/global parameter or depends on model structure.
- **Low**: the setting is a weakly constrained emulator coefficient, spatial partition, response time, or idealized experiment assumption.

The label is not a probability that a projected temperature or AMOC trajectory is correct.

## Interval terminology

Tooltips distinguish among:

1. **Assessed interval** — a formal range from a scientific assessment, such as IPCC AR6.
2. **Observational interval** — a range or uncertainty derived from measurements.
3. **Built-in prior support** — deliberately broad bounds used for Monte Carlo sampling; not a confidence interval.
4. **Custom min-max range** — a user-selected uncertainty experiment.
5. **Numerical range** — a stability or convergence-tested software range.
6. **No formal interval** — the coefficient is emulator-specific or insufficiently constrained for a statistical confidence interval.

## Primary source groups

- IPCC AR6 WGI Chapter 7: effective radiative forcing, feedback decomposition, ECS, TCR, Earth energy imbalance, and two-layer emulator reference values.  
  https://www.ipcc.ch/report/ar6/wg1/chapter/chapter-7/
- IPCC AR6 synthesis/summary: observed 2011–2020 global warming relative to 1850–1900.  
  https://www.ipcc.ch/report/ar6/syr/longer-report/
- RAPID-MOCHA-WBTS at 26.5°N: AMOC transport and Atlantic heat transport observations.  
  https://rapid.ac.uk/data  
  https://rapid.ac.uk/data/heat-transport-data
- South Atlantic FovS/Mov observations: multi-data-set estimate near -0.15 ± 0.09 Sv.  
  https://doi.org/10.1029/2023JC020558
- North Atlantic Hosing Model Intercomparison Project: idealized freshwater-forcing experiment design and AMOC recovery behaviour.  
  https://doi.org/10.5194/gmd-16-1975-2023

## Important limitations

Many interface settings do not correspond one-to-one with observable quantities. Examples include AMOC surface heat coupling, regional heat damping, pycnocline feedback strength, convection transition width, gyre exchange coefficients, cloud-loss coefficients, and warming-to-freshwater sensitivities. Their tooltips therefore report broad prior support and low confidence rather than inventing a formal confidence interval.


## v2.17.0 additions

The Greenland reservoir controls define an initial finite ice mass, a depletion exponent and a maximum freshwater flux. These are broad emulator parameters, not formal ice-sheet projections.

The initial AMOC density-margin controls reject parameter combinations whose absolute hydrographic density driver is too weak or too strong relative to the reference state. The reversal option is disabled by default because negative scalar transport has not been calibrated as a physical reversed circulation.


## Percent-ramp-to-cap CO2 experiment

The `percent_ramp_hold` scenario compounds atmospheric CO2 by
`co2_growth_rate_percent_per_year` until `co2_growth_cap_ppm` is reached. It then
holds concentration at the cap for `co2_hold_years`. The simulation duration is
resolved automatically rather than taken from the generic duration field.

`percent_ramp_compare_rates` accepts comma-separated positive percentages, such
as `0.5,1,2,3,5`. Comparison outputs use the same physical configuration for
every rate and differ only in the prescribed CO2 growth rate and the resulting
time at which the common cap is reached. These are idealized forcing-rate
experiments, not emissions scenarios.

## v2.18.2 external-ocean salinity-anomaly exchange

### `amoc_southern_external_exchange_sv`
Effective conservative exchange between Southern Ocean surface salinity anomalies and the external-ocean reservoir. The default is 5 Sv. The control-state salinity contrast is subtracted, so this term is exactly zero in the calibrated initial state.

### `amoc_south_atlantic_external_exchange_sv`
Effective conservative exchange between South Atlantic upper-limb salinity anomalies and the external-ocean reservoir. The default is 2 Sv. This damps unresolved multi-century closed-box drift while preserving total salt.

Setting both values to zero restores the v2.18.1 closed-box exchange structure for diagnostic comparison. Values are structural emulator coefficients rather than directly observed transports.


## v2.29 Arctic ocean coupling controls

- **Basal ice/ocean exchange** controls how strongly local shallow-ocean warming increases basal sea-ice melt.
- **Open-water/ocean exchange** transfers sensible heat bidirectionally between the explicit surface reservoir and prognostic ocean.
- **Reference shallow-ocean heat capacity** controls the seasonal thermal inertia of the periodic control ocean.
- **Reference shallow-ocean restoring** represents unresolved ocean heat convergence that closes the periodic reference budget.
- **Warming-driven Arctic ocean heat convergence** is a conservative transient term that becomes active above the configured global-warming onset. The 4 W/m²/K default scales with the square root of remaining ice concentration as an unresolved pack-edge proxy, and the same heat is removed from lower-latitude ocean.
- **Warming-onset threshold** sets the global-warming level at which the transient convergence starts. The 1°C default leaves the unforced periodic control unchanged.
- **Maximum equivalent thickness** is a 20 m fail-fast numerical threshold. It does not clip/transfer latent energy and is excluded from Monte Carlo science priors.
- **Maximum local ice thickness** is a separate 500 m fail-fast numerical threshold. It never remaps concentration/area and is excluded from Monte Carlo science priors.
- **Thick-pack area-loss resistance exponent** defaults to 4.0 and smoothly suppresses anomaly-only fixed-volume area retreat as surviving floes become thicker than the periodic-control pack.
- **Depleted-pack restoring saturation** defaults to 0.14 and controls the shape of the reverse-restoring transition. **Maximum depleted-pack restoring flux** is an independent 2.5 W/m² bound, so changing the saturation scale cannot silently increase maximum recovery forcing.

These are low-confidence reduced-model coefficients with broad Monte Carlo support, not direct observational confidence intervals.

## v2.28.1 temperature products

The model exposes three different temperature concepts and does not treat them as interchangeable:

- **Bulk surface**: the prognostic land-surface and ocean mixed-layer field. This is the compatibility target of the legacy generic map output.
- **Near-surface air**: a coherent global 2 m-air proxy. Arctic amplification uses Arctic and global values from this same field.
- **Arctic ocean interface**: the sea-ice/ocean interface temperature over the active Arctic ocean mask. It remains at the configured freezing point while ice is present and is not a near-surface-air product.

Absolute and anomaly maps are emitted separately for all three products. Comparisons with observed Arctic amplification should use the near-surface-air product, not the bulk-surface or interface products.

### v2.29.1 Arctic phase consistency

The open-water sensible-heat reservoir is conservatively remapped as fractional ice area changes. Open fractions below 5% are treated as unresolved leads pinned to freezing; their sensible heat is transferred to the coupled ocean. Atlantic and central-Arctic reference-ocean temperatures are independent controls at 0.20 C and -0.80 C, and open-water/ocean coupling must remain positive.

### v2.29.1 Arctic phase consistency

The open-water sensible-heat reservoir is conservatively remapped as fractional ice area changes. Open fractions below 5% are treated as unresolved leads pinned to freezing; their sensible heat is transferred to the coupled ocean. Atlantic and central-Arctic reference-ocean temperatures are independent controls at 0.20 C and -0.80 C, and open-water/ocean coupling must remain positive.

## v2.29.2 integrity constraints

- Arctic reference cycles are accepted only after adaptive closure and convergence satisfy the configured tolerance before the hard spin-up maximum.
- Whole-domain salt projection corrects floating-point roundoff only. The pre-projection residual is retained as a diagnostic and structural residuals terminate the run.
- Monte Carlo numerical and physical safety checks always apply, including when observational constraint weighting is disabled.
- Lateral Arctic phase-restoring ocean heat convergence is signed about the periodic reference ice fraction and is applied with an equal-and-opposite non-Arctic ocean tendency.
- Cold-season mechanical lead closure redistributes existing equivalent ice volume over unresolved leads; it does not create latent heat or ice mass. The default closes 65% of eligible winter concentration deficits after a one-percentage-point onset threshold, with a 15 C cold-season activation scale.
- Arctic summary diagnostics use `arctic_module_full_latitude_deg`; disabling the seasonal Arctic module bypasses reference-cycle generation.

