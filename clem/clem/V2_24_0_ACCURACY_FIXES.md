# Accuracy remediation in v2.24.0

## Implemented corrections

1. **Historical GMST reference period**
   The 2011–2020 metric now subtracts the simulated 1850–1900 mean. The former calculation compared an absolute model anomaly with an observation already referenced to 1850–1900.

2. **Ocean heat uptake**
   The default mixed-layer/deep-ocean exchange coefficient is 1.10 W/m2/K instead of 0.85 W/m2/K. This increases 1971–2018 ocean heat gain without changing equilibrium climate sensitivity.

3. **Arctic output semantics**
   Ocean grid cells contain mixed-layer water temperature, not two-metre air temperature. v2.24 therefore reports both:
   - `arctic_blended_surface_state_warming_c`: the original prognostic land/ocean surface-state average;
   - `arctic_near_surface_air_warming_c`: an annual-mean diagnostic closure for the faster atmospheric response and simulated sea-ice loss.

   `arctic_warming_c` is retained as a compatibility alias for the near-surface-air diagnostic. The diagnostic does not add energy to the ocean or alter the prognostic climate state. A seasonal atmosphere/sea-ice module would still be required for mechanistic Arctic seasonality.

4. **Transient AMOC response**
   The default parameter balance now uses:
   - hydrological freshwater sensitivity: 0.015 Sv/K;
   - Greenland freshwater sensitivity: 0.010 Sv/K;
   - northern thermal-density coupling: 0.80;
   - direct surface expression of AMOC heat-transport anomalies: 0.075.

   This strengthens transient buoyancy forcing and reduces excessive cold-blob restoration while retaining conservative heat redistribution and exact salt accounting.

## Default regression results

| Metric | v2.23 | v2.24 | Regression range |
|---|---:|---:|---:|
| 2011–2020 GMST relative to 1850–1900 | 1.306 degC (incorrect reference) | 1.154 degC | 0.95–1.20 |
| 1971–2018 ocean heat gain | 328.5 ZJ | 350.7 ZJ | 350–500 |
| 1979–2021 Arctic/global trend ratio | 1.36 | 3.06 | 3.0–4.5 |
| SSP2-4.5 AMOC decline, 2081–2100 | 8.72% | 20.14% | 15–50% |
| SSP5-8.5 AMOC decline, 2081–2100 | 22.43% | 42.31% | existing 15–45% calibration envelope |

## Evidence status

The four ranges above were used while developing v2.24. They are therefore **development regression checks, not independent held-out validation**. Independent assessment requires new observations or model-comparison targets that were not used to choose these defaults.
