# v2.25.2 Seasonal Arctic and AMOC corrections

## Purpose

v2.25.2 removes the empirical Arctic-air amplification diagnostic introduced in v2.24 and replaces it with a prognostic reduced-complexity seasonal subsystem. It also removes the temporary freshwater compensation used during development and restores independently defensible hydrological and Greenland terms.

## Seasonal Arctic state

For each latitude band in the Arctic blend region and for both Atlantic and non-Atlantic ocean sectors, the model integrates:

- near-surface-air temperature anomaly;
- a one-year low-pass air-temperature anomaly for annual diagnostics and Greenland marine influence;
- latent sea-ice energy anomaly relative to a seasonal reference cycle;
- resulting equivalent ice thickness and concentration.

The module blends from zero influence at 55°N to full influence at 66°N. It does not impose an amplified Arctic temperature pattern. Amplification emerges from the local air heat capacity, atmospheric transport, ocean–air exchange, winter open-water heat release, and sea-ice latent-energy response.

## Energy exchanges

Ocean and Arctic air are advanced with a two-state implicit solve. Ocean–air exchange therefore appears with equal magnitude and opposite sign in the two reservoirs. The following terms are also paired conservatively:

- winter open-water heat release: ocean loss and air gain;
- sea-ice growth/melt and unresolved two-sided ice relaxation: latent-energy change balanced against ocean or air;
- Arctic atmospheric heat convergence: removed from the non-Arctic source region.

The seasonal reference state is anomaly based. With zero external forcing, adding the seasonal module does not create an artificial annual-mean radiative or heat-content drift.

## Sea-ice formulation

Latent energy is converted to equivalent thickness using the volumetric latent heat of fusion. Concentration is a bounded power-law function of equivalent thickness. A symmetric anomaly relaxation represents unresolved export and mechanical redistribution. Thin-ice rebuilding is faster in winter, but both positive and negative perturbations are energy balanced and recover toward the same control state.

The module remains a reduced-complexity representation. It does not resolve snow-on-ice layers, leads, ridging categories, ice dynamics, clouds, or a full atmospheric column.

## Arctic outputs

- `arctic_instantaneous_near_surface_air_warming_c`: instantaneous area-weighted Arctic air anomaly.
- `arctic_one_year_low_pass_air_warming_c`: prognostic one-year low-pass air anomaly.
- `arctic_warming_c` and `arctic_near_surface_air_warming_c`: compatibility aliases for the low-pass air diagnostic.
- `arctic_blended_surface_state_warming_c`: original land plus ocean mixed-layer quantity.
- Arctic air and sea-ice heat-content fields: explicit contributions to the resolved heat inventory.

Validation uses exact time-weighted calendar-year means reconstructed from subannual output. It does not compare a single recurring seasonal phase against annual observations.

## Freshwater calibration

The release defaults are:

- hydrological freshwater sensitivity: **0.006 Sv/K**;
- Greenland freshwater sensitivity: **0.005 Sv/K**.

The temporary 0.023/0.017 Sv/K development experiment was rejected because it produced nearly 0.1 Sv of late-century northern freshwater forcing under SSP2-4.5 and effectively tuned AMOC weakening through a hosing experiment. The release narrows ordinary GUI and ensemble ranges to 0.002–0.012 Sv/K for hydrological forcing and 0.002–0.010 Sv/K for Greenland forcing.

Greenland forcing remains tied to a Greenland-specific land-temperature mask with a small configurable marine Arctic influence. It is calibrated independently from the AMOC target.

## AMOC structural correction

- `amoc_temperature_density_coupling = 1.0`: the anomalous sinking-region thermal stratification enters at full strength.
- `amoc_convection_density_scale_factor = 3.0`: retained after stress testing. A value of 1.0 made ordinary forcing and 0.1 Sv hosing unrealistically collapse the circulation.
- `amoc_convection_entrainment_feedback = 0.0`: disables a duplicate direct density-memory feedback. Convection-dependent salt mixing remains active, so the physical salt–convection feedback is preserved once rather than counted twice.

A 40-year 0.1 Sv hosing pulse weakens the circulation and then recovers after the forcing is removed, instead of continuing into a self-sustaining numerical decline caused by duplicate feedback.

## Default development checks

Using time-weighted annual means and the release defaults:

| Diagnostic | v2.25.2 result |
|---|---:|
| 2011–2020 warming relative to 1850–1900 | 1.168°C |
| 1971–2018 ocean heat gain | 357.5 ZJ |
| 1979–2021 Arctic/global trend ratio | 3.04× |
| SSP2-4.5 AMOC weakening, 2081–2100 vs 1995–2014 | 20.52% |

These checks were used during development and are not independent held-out validation.

## Stability and recovery checks

- Multi-century unforced control remains at the initialized climate and AMOC state to numerical precision.
- Warm/thin-ice and cold/thick-ice perturbations both decay back toward control.
- A finite 0.1 Sv, 40-year hosing pulse recovers after the perturbation is removed.
- The seasonal module can be disabled for compatibility comparisons.
- Salt conservation and the existing AMOC conservation tests remain active.

## Remaining limitations

The model is still an emulator, not an Earth-system or general-circulation model. The seasonal Arctic module is annual-cycle capable but does not resolve synoptic weather, explicit humidity storage, atmospheric vertical structure, sea-ice dynamics, ice-sheet flow, or regional ocean currents. AMOC thresholds and collapse fractions remain conditional on the selected structural family and parameter distributions.
