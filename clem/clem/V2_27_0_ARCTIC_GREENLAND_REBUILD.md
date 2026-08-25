# v2.27.0 Arctic and Greenland structural rebuild

## Release status

v2.27.0 is a corrected reduced-complexity experimental model release. It fixes the nonphysical absolute Arctic ocean climatology, removes inherited annual-mean sea-ice mass from the seasonal reference state, adds a reduced Greenland surface-mass-balance branch, and synchronizes the model interfaces and release metadata.

The literature ranges bundled with the package remain **tuning-informed development regression checks**. They are not independent validation and must not be presented as such.

## Arctic climatology and sea ice

### Absolute ocean climatology

Land and ocean reference temperatures are now constructed separately. This prevents cold coastal land values from leaking into the zonal ocean climatology. The ocean field is blended to the configured seawater freezing point between the seasonal-Arctic module start and full latitudes, and is exactly -1.8 C north of 66 N. A compensating offset on unconstrained land and non-Arctic ocean cells preserves the 14 C global reference mean.

### Periodic zero-layer reference cycle

The v2.26 inherited annual ice mass and latitude-by-latitude annual-mean absorbed-shortwave subtraction were removed. The control cycle is obtained by spinning up a periodic zero-layer energy balance with:

- daily-mean orbital insolation, polar night and midnight sun;
- snow-covered, bare-ice, melt-pond and open-water albedo states;
- nonlinear surface heat exchange and non-solar heat loss;
- conductive heat transfer through ice and an effective snow resistance;
- basal ocean heat flux;
- latent heat of growth and melt;
- an open-water mixed-layer heat reservoir.

At the default resolution the reference cycle closes to better than 1e-10 W yr/m2. It produces full late-winter cover and a September minimum near one-half of the Arctic ocean-area-weighted reference cover. Ice-covered interface cells remain at -1.8 C; open-water cells may warm above freezing after melt.

### Seasonal amplification

The prognostic anomaly subsystem remains conservative, but the cold-season energy transport is now an additive coefficient weighted by diagnosed polar darkness rather than an opaque multiplier. The default response is strongly winter-dominant and much weaker in summer. The exact versioned seasonal ratios are recorded in `VALIDATION_SUMMARY_V2_27_0.json`.

## Greenland surface mass balance

Greenland freshwater is split into two physically distinct branches.

1. **Seasonal surface mass balance** calculates a control-relative positive-degree-day melt anomaly, snowfall/rain partition, precipitation response, warming-dependent retention, runoff and net accumulation.
2. **Slow dynamic discharge** retains the 45-year response reservoir and uses 40% of the public 0.005 Sv/K Greenland coefficient.

The surface branch is calculated independently rather than being added to a full-strength legacy temperature-to-freshwater reservoir. Component diagnostics are reported before their shared cap; the total diagnostic is the actually applied combined flux after the 0.025 Sv and finite-reservoir limits. The finite Greenland ice reservoir bounds cumulative net loss and permits negative freshwater anomalies during net accumulation. The public hydrological and Greenland freshwater coefficients remain 0.006 and 0.005 Sv/K respectively.

The legacy combined `warming_freshwater_sv_per_k` override still disables the separated Greenland response, including the new SMB branch, so archived workflows retain their intended one-coefficient behavior.

## AMOC structural recalibration

Correcting the Arctic ocean climatology changes the control density margin. The default AMOC anomaly-density coupling is therefore versioned as:

- `amoc_temperature_density_coupling = 1.0`;
- `amoc_convection_density_scale_factor = 4.0`;
- `amoc_reference_density_driver = 7.5e-4`.

This is a structural thermal/stratification recalibration. Hydrological and Greenland freshwater coefficients were not increased to recover the target response.

## Interface and release synchronization

The following surfaces now use the v2.27 defaults and controls:

- core `ModelConfig` and CLI;
- Streamlit application;
- desktop GUI and generated CLI command;
- Monte Carlo physical whitelist, aliases and science priors;
- setting metadata and tooltips;
- package version and dependency-lock metadata;
- validation provenance and regression tests.

`run_tests.py` now executes every selected test case in a separate subprocess with an explicit timeout. This avoids the prior failure mode where assertions completed but the combined interpreter remained alive during shutdown.

## Default development metrics

The exact machine-readable values are in `VALIDATION_SUMMARY_V2_27_0.json` and `DEEP_VALIDATION_V2_27_0.json`. The default v2.27 run is approximately:

| Diagnostic | Result |
|---|---:|
| Historical warming, 2011-2020 vs 1850-1900 | 1.166 C |
| Ocean heat gain, 1971-2018 | 356.15 ZJ |
| Annual Arctic amplification, 1979-2021 | 3.758x |
| SSP2-4.5 AMOC weakening by 2081-2100 | 19.99% |
| SSP5-8.5 AMOC weakening by 2081-2100 | 40.34% |
| Greenland loss, 2011-2020 | about 218 Gt/year |
| Greenland sea-level equivalent by 2100 under SSP2-4.5 | about 90.0 mm |

All four bundled development-regression ranges pass. Because these ranges informed calibration, passing them is a reproducibility check rather than independent evidence of predictive accuracy.

## Numerical checks

Default deep validation includes:

- 500-year constant-forcing control;
- warm and cold Arctic perturbation recovery;
- 0.1 Sv transient hosing and 100-year recovery;
- 2.5, 5 and 10 degree cross-resolution controls and abrupt-2xCO2 runs;
- SSP2-4.5 timestep checks at 0.10, 0.05 and 0.025 years;
- exact benchmark and source-file SHA-256 provenance.

The 500-year default control has effectively zero GMST, AMOC, heat and salt drift. The transient 0.1 Sv hosing experiment recovers about 87% of its initial AMOC loss after 100 years without hosing.

## Compatibility

The dedicated v2.23 continuation, branch-assignment, stability, provenance and ocean-heat tests pass. Source and workflow compatibility are retained, but v2.27 is not intended to reproduce v2.23 numerical trajectories because the Arctic climatology, sea-ice reference state, Greenland forcing and AMOC thermal normalization are explicitly versioned structural changes.

See `V2_23_COMPATIBILITY_V2_27_0.md` for the detailed compatibility classification.

## Remaining scientific limits

- Sea-ice dynamics, ridging, export and resolved ocean circulation are not represented.
- The zero-layer solver is an annual reference energy balance, not a spatially resolved sea-ice model.
- Greenland firn hydrology, elevation feedback, outlet-glacier geometry, calving and dynamic ice flow remain reduced emulator terms.
- The AMOC is a salt-conserving box model with parameterized convection and pycnocline dynamics.
- The SSP5-8.5 AMOC response is toward the strong end of published broad envelopes and should be treated as structural model behavior, not a probability forecast.
- Local map values are reduced-model diagnostics and are not suitable for local impact assessment.
