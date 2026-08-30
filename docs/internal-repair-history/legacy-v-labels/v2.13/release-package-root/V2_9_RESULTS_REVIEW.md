# v2.9 physics verification review

v2.9 resolved the millennial AMOC-collapse regression caused by the earlier sea-ice export routing error. The 1200-year abrupt-2xCO2 integration no longer collapses: AMOC is 11.45 Sv at year 1200 and its late trend is only +0.041 Sv/century. TCR remains 1.923 C and the feedback decomposition remains well behaved (Planck -3.254, WV 1.814, resolved LR -0.465, polar inversion +0.034, albedo +0.294, cloud +0.425 W m-2 K-1; combined WV+LR+polar 1.383; net -1.152).

The sea-ice mechanism split demonstrates that the corrected export routing now has the expected stabilizing sign under warming. Pure thermal weakening is 39.64%. Storage-only changes this by only +0.08 percentage points. Export-only reduces weakening by 3.22 percentage points, and storage+export reduces it by 3.14 percentage points. The salinity-equivalent export normalization remains 0.35896, corresponding to a 0.075 Sv reference export from a raw model-equivalent 0.20894 Sv.

Energy conservation over the densely sampled 100-year forced experiment remains excellent: 0.0439% relative residual. Salt conservation, seasonal-Arctic timestep convergence, pycnocline closure, cryosphere freshwater accounting and reference-residual checks all pass.

Two issues remain:

1. The 1200-year ECS convergence test falsely fails its TOA gate because it records once per year at one calendar phase. The seasonal Arctic external-flux anomaly has a strong annual cycle. In the existing dense 100-year energy run, years 80-100 give +1.314 W m-2 using 0.05-year sampling but only +0.794 W m-2 when subsampled annually at the same phase: a -0.520 W m-2 alias. This is the same order as the apparent -0.573 W m-2 late ECS imbalance. The model's resolved heat content is still increasing late in the 1200-year run, proving the negative annually sampled TOA value cannot be the actual annual-mean external energy imbalance.

2. The persistent collapsed branch remains slightly too cold: -8.397 C after the 0.4 Sv / 250-year hosing plus 800-year recovery experiment. The 180-year 0.5 Sv hosing fingerprint is -3.306 C and remains in the desired 3-8 C range.

v2.10 therefore changes no radiative feedback, salt-loop, sea-ice routing, hosing, Greenland or pycnocline parameter. It fixes seasonal aliasing in ECS diagnostics and makes a narrow conservative Atlantic/non-Atlantic heat-compensation adjustment.
