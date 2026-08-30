# Repair R12 out-of-sample validation review

## Verdict

The Repair R11 physics passes the Repair R12 held-out validation suite at both 10 degree and 5 degree resolution. No physics coefficient was changed for Repair R12.

### SSP2-4.5, 1850-2100

| Metric | 10 deg | 5 deg |
|---|---:|---:|
| 2011-2020 warming vs 1850-1900 | 1.027 C | 1.020 C |
| 2081-2100 warming vs 1850-1900 | 2.671 C | 2.655 C |
| AMOC 1995-2014 | 14.88 Sv | 14.98 Sv |
| AMOC 2081-2100 | 8.65 Sv | 9.20 Sv |
| AMOC decline | 41.87% | 38.60% |
| Minimum AMOC | 8.25 Sv | 8.83 Sv |
| Final FovS | -0.097 Sv | -0.102 Sv |
| Maximum salt error | 0 ppm | 0 ppm |

Cross-resolution differences are small: 0.016 C in late-century warming, 0.55 Sv in late AMOC, and 3.27 percentage points in AMOC decline.

### Untuned 100-year hosing dose response

| Hosing | Final/minimum AMOC | Minimum North Atlantic anomaly |
|---|---:|---:|
| 0.1 Sv | 13.78 Sv | -0.56 C |
| 0.2 Sv | 9.51 Sv | -1.27 C |
| 0.3 Sv | 4.13 Sv | -2.17 C |

The response is monotonic in both AMOC weakening and North Atlantic cooling. The 0.1 Sv experiment does not jump to the collapsed branch, and all three runs conserve salt to reported precision.

## Known remaining limitation: RAPID-era absolute AMOC strength

The SSP2-4.5 trajectory gives a 2004-2020 mean AMOC of about 14.17 Sv at 10 degree and 14.32 Sv at 5 degree. Johns et al. (2023) report a RAPID 26.5 N mean of 16.9 +/- 1.2 Sv for April 2004-December 2020. The model is therefore low by roughly 2.6-2.7 Sv if its scalar AMOC is compared directly with RAPID.

This is deliberately reported as a limitation rather than retuned after the held-out validation. The future SSP2-4.5 weakening, hosing dose response, ECS/TCR, conservation, and cross-resolution results should not be invalidated merely to force a post-hoc fit to this one observed mean. A future physics revision should investigate the historical AMOC mean-state/thermal-response bias independently, ideally using a temperature-dependent seawater equation of state and/or explicit latitude/vertical AMOC diagnostic rather than an empirical offset.

## Release decision

The Repair R11 dynamics are acceptable as the current physics candidate for the tested scope. Repair R13 is a release-consistency repair only: it fixes stale public CLI defaults and documentation while preserving the validated core-model AST exactly.
