> **Historical v2.16 record.** The 0.004–0.020 Sv/K Greenland range below is obsolete and is not used by v2.27.0. Current normal interfaces and built-in priors use 0.002–0.010 Sv/K, with a 0.005 Sv/K default for the slow dynamic-discharge branch; surface mass balance is calculated separately.

# Freshwater Monte Carlo controls

Version 2.16.0 retains deterministic freshwater settings and additionally exposes their uncertain controls as optional Monte Carlo adjustors. In constraint mode `none`, enabling these ranges does not trigger historical, ECS, TCR, or AMOC calibration experiments.

| Control | Suggested minimum | Suggested maximum |
|---|---:|---:|
| Hydrological sensitivity | 0.003 Sv/K | 0.010 Sv/K |
| Northern routing fraction | 0.50 | 0.90 |
| Greenland sensitivity | 0.004 Sv/K | 0.020 Sv/K |
| Greenland response time | 30 years | 150 years |

The model still computes `hydrological_freshwater_sv`, `greenland_freshwater_sv`, total freshwater forcing, and AMOC as time-dependent outputs for each member.
