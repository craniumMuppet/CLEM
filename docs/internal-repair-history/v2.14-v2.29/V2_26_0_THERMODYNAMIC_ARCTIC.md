# v2.26.0 Thermodynamic seasonal Arctic implementation

## Purpose

v2.26.0 replaces the partially prescribed v2.25.2 Arctic seasonal cycle with an explicit reduced-complexity thermodynamic subsystem. It retains the global annual-mean energy-balance and AMOC architecture while resolving subannual Arctic insolation, atmosphere, ocean-interface enthalpy, sea ice, delayed heat release, and Greenland runoff timing.

## Physical state and forcing

### Orbital insolation

Daily-mean top-of-atmosphere insolation is calculated from latitude, solar declination, sunset hour angle, polar-night/midnight-sun limits, and a first-order Earth–Sun distance correction. The model no longer prescribes the month or amplitude of the Arctic ice minimum or maximum.

### Ocean–ice interface enthalpy

The interface state is expressed as energy per unit area. Negative enthalpy is latent sea-ice energy and maps to equivalent ice thickness and concentration. While enthalpy is negative, interface temperature is fixed at the seawater freezing point, −1.8°C by default. Positive enthalpy warms a shallow interface layer after local ice has melted.

### Thermodynamic reference cycle

The anomaly model requires a stable periodic control climatology. v2.26 generates that cycle by integrating seasonally varying absorbed shortwave energy with interactive ice/open-water albedo around the inherited annual-mean ice mass. The annual-mean absorbed shortwave component is removed because it is already represented by the parent annual climatology. A six-hour reference grid eliminates interpolation drift at the default 0.05-year integration step.

### Coupled anomalies

Climate anomalies exchange energy among:

- Arctic near-surface air;
- the bulk mixed-layer ocean anomaly;
- the latent/sensible interface reservoir;
- the non-Arctic source region supplying anomalous poleward atmospheric heat convergence.

Air–ocean exchange is solved implicitly. Interface clipping returns excess energy to the mixed layer. Sea-ice anomaly relaxation is two-sided and energy conserving.

### Delayed heat release

Open-water heat release depends on thermodynamic ice deficit and polar darkness. This delays the strongest ocean-to-air pulse until autumn after the late-summer ice minimum rather than applying it simultaneously with summer melt.

## Greenland forcing

Greenland surface warming combines a geographic Greenland land-temperature proxy with simulated instantaneous Arctic marine air. The long-term discharge state responds over the configured Greenland timescale. A configurable portion of positive discharge is then routed through a normalized insolation-derived melt-season function. The routing has unit annual mean and therefore changes timing without changing the 0.005 Sv/K annual sensitivity.

Outputs distinguish:

- `greenland_temperature_driver_c`;
- `greenland_annual_mean_freshwater_sv`;
- `greenland_freshwater_sv`, the seasonally applied ocean flux;
- `greenland_melt_season_weight`;
- `greenland_seasonal_routing_factor`.

## Legacy multiplier removal

The v2.24 empirical fields remain accepted only to read old configuration files:

- `arctic_air_local_warming_multiplier` defaults to 1.0;
- `arctic_sea_ice_air_warming_c_per_fraction_loss` defaults to 0.0.

They are absent from Streamlit, the desktop GUI, shared setting metadata, and normal CLI help. Tests confirm that extreme values produce exactly zero difference when the v2.26 seasonal subsystem is enabled.

## Default freshwater coefficients

- Hydrological freshwater sensitivity: **0.006 Sv/K**.
- Greenland freshwater sensitivity: **0.005 Sv/K**.
- Monte Carlo ordinary ranges: **0.002–0.012 Sv/K** hydrological and **0.002–0.010 Sv/K** Greenland.

The temporary 0.023/0.017 Sv/K development experiment is rejected and is not active in the model.

## Validation results

### Development-regression metrics

| Metric | v2.26.0 |
|---|---:|
| 2011–2020 warming relative to 1850–1900 | 1.1869°C |
| 1971–2018 ocean heat gain | 363.02 ZJ |
| 1979–2021 annual Arctic amplification | 3.4888× |
| SSP2-4.5 late-century AMOC weakening | 20.05% |

### Seasonal Arctic behavior

| Diagnostic | Result |
|---|---:|
| Control ice maximum | February–March, full cover |
| Control ice minimum | September, 0.459 fraction north of 66°N |
| Late-century ice minimum | September, 0.115 fraction |
| Late-century winter maximum | March, full cover |
| Heat-release maximum | October |
| DJF amplification | 3.850× |
| MAM amplification | 3.687× |
| JJA amplification | 3.196× |
| SON amplification | 3.408× |
| Ice-covered interface temperature | −1.8°C |

### Stability and conservation

- 500-year unforced GMST drift: approximately −3.1×10⁻¹⁴°C.
- 500-year AMOC drift: approximately +1.1×10⁻¹⁴ Sv.
- Salt-conservation error: zero in the 500-year control.
- Full SSP2-4.5 resolved-energy versus integrated-TOA residual: −0.0424%.
- Both warm/thin-ice and cold/thick-ice perturbations return to the control seasonal state.
- A 40-year 0.1 Sv hosing pulse weakens AMOC to 14.63 Sv and recovers to 17.07 Sv after 100 years.
- SSP5-8.5 late-century AMOC weakening is 41.04%.
- The 450-year hybrid SSP5-8.5-to-SSP2-4.5 experiment reaches a 9.90 Sv minimum and recovers to 12.67 Sv.
- AMOC thermal-density coupling is 0.71; hydrological and Greenland freshwater remain fixed at 0.006/0.005 Sv/K.

## Scope limits

This remains a reduced-complexity emulator. It does not resolve weather, ice dynamics, ocean currents beneath ice, snow-layer thermodynamics, melt ponds, leads, explicit atmospheric humidity, or a spatial Greenland ice-sheet energy balance. Seasonal amplification and runoff timing are physically generated within the reduced state space, but regional predictions should not be interpreted as comprehensive-model forecasts.
