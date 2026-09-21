# CLEM v2.29.28 — R16 user-run validation review

## Verdict

R16 restores the validated R13/R12 default AMOC response and the new Greenland/salt-routing changes behave correctly, but R16 is **not fully complete** because all three TEOS-10 experiments were blocked during setup by a guard that was calibrated only for the linear alpha/beta EOS. The R16.1 hotfix removes that inappropriate cross-EOS gate while leaving the linear default physics unchanged.

The R16 sea-ice 15% extent reconstruction is conservative and unfitted, but the user-run SSP output still demonstrates that the native two-sector concentration field is too spatially diffuse for a quantitatively credible extent claim. Extent therefore remains diagnostic/non-release-blocking; no empirical area-to-extent fit is introduced in R16.1.

## Execution integrity

- 34 experiments requested.
- 31 experiments completed numerically.
- 3 TEOS-10 experiments failed during setup, before year 0.
- 840 numerical child chunks completed.
- Maximum child advancement: exactly 5.0 model years.
- No numerical child timeout or integration error occurred.
- R16 `climate_model.py` SHA-256 in the bundle matches the delivered R16 source: `ddcd2272bf2d10ed9d9eacb9fabdc5e65db7fdfc3e3e23a09e85d5bfffc2ba40`.

## Default AMOC response

R16 successfully rejects the R15.1 South-Atlantic-upper default and restores the validated high-latitude closure.

| Experiment | Final AMOC |
|---|---:|
| Control | 17.000 Sv |
| 0.1 Sv hosing, 100 y | 13.777 Sv |
| 0.2 Sv hosing, 100 y | 9.510 Sv |
| 0.3 Sv hosing, 100 y | 4.126 Sv |
| SSP2-4.5 2100, 10 deg | 8.246 Sv |
| SSP2-4.5 2100, 5 deg | 8.831 Sv |
| South-Atlantic-upper sensitivity, 0.2 Sv | 14.961 Sv |
| South-Atlantic-upper sensitivity, SSP2-4.5 2100 | 17.505 Sv |

The standard 0.1/0.2/0.3 Sv dose response and SSP2-4.5 10/5-degree behavior reproduce the Repair R12 validated values to reported precision. The South-Atlantic-upper branch remains strongly inconsistent with the validated weakening response and is correctly retained only as a sensitivity branch.

## SSP2-4.5 cross-resolution

The R16 default reproduces the Repair R12 late-century behavior:

- 10 deg late-century warming: about 2.671 C vs 1850-1900.
- 5 deg late-century warming: about 2.655 C.
- 10 deg 2081-2100 AMOC: about 8.64 Sv.
- 5 deg 2081-2100 AMOC: about 9.19 Sv.
- AMOC decline from the 1995-2014 mean: about 41.7% at 10 deg and 38.4% at 5 deg.

## Timestep convergence

The 40-year step-2x runs are tightly converged:

| dt | AMOC | GMST | Arctic warming |
|---|---:|---:|---:|
| 0.10 y | 10.864 Sv | 2.035 C | 7.724 C |
| 0.05 y | 10.843 Sv | 2.038 C | 7.741 C |
| 0.025 y | 10.832 Sv | 2.039 C | 7.750 C |

The 0.10-to-0.025-year AMOC difference is only about 0.032 Sv.

## Greenland freshwater / salt conservation

The new uncompensated land-ice routing behaves as intended:

- Default step-2x 150 y adds about `3.798e13 m3` of represented ocean freshwater.
- Legacy compensated comparison adds zero represented ocean volume.
- Both retain salt conservation at numerical roundoff (`<= 2.22e-10 ppm` reported extrema).
- Default Greenland cumulative sea-level contribution is about 104.92 mm after 150 y.
- Disabling elevation feedback reduces this to about 103.52 mm, so the elevation feedback is active but modest over this test.

The physical mass-routing correction therefore passes its intended attribution test.

## Arctic ablations

At 100 years after step-2x forcing:

| Branch | Arctic warming | AMOC |
|---|---:|---:|
| All mechanisms | 8.089 C | 9.887 Sv |
| No extra lapse feedback | 7.293 C | 10.655 Sv |
| No forced ocean heat convergence | 7.860 C | 10.125 Sv |
| No phase restoring | 8.294 C | 9.777 Sv |
| Resolved-only (all three disabled) | 7.266 C | 10.819 Sv |

The three terms are nearly additive over this experiment. The extra lapse feedback is the largest of them (~0.80 C effect), heat convergence contributes ~0.23 C, and the phase-restoring term damps warming by ~0.21 C. This demonstrates that the terms are active; it does not by itself establish that they are double-counted.

## AMOC structural sensitivity

The structural experiments now enter the regimes they were designed to test:

- density exponent 1.0 under 0.3 Sv hosing: 3.751 Sv after 120 y;
- density exponent 2.0: 0.338 Sv;
- pycnocline feedback 0.0: 0.971 Sv;
- pycnocline feedback 0.7: 1.258 Sv;
- 20 Sv strengthening cap: 19.984 Sv;
- 24 Sv cap: 21.577 Sv;
- no-reversal under 0.8 Sv hosing: approaches 0 Sv;
- reversal-enabled branch: -18.671 Sv.

Thus collapse strength is structurally sensitive, especially to the density exponent. These are sensitivity results, not evidence that any alternate branch is better constrained than the validated default.

The 700-year collapse/recovery experiment remains on a persistent collapsed branch after hosing is removed at year 250. That behavior is consistent with the earlier Repair R11 collapse/recovery classification and should be treated as model hysteresis, not a new R16 regression.

## TEOS-10 failure diagnosis

All three TEOS-10 experiments fail at model construction with:

`AMOC absolute initial density margin is outside the accepted range: ratio=2.6930, allowed=[0.6800, 1.2500]`.

This is a validation-guard error. The `[0.68, 1.25]` envelope was calibrated for the linear alpha/beta dimensional density contrast. The AMOC hydraulic equations normalize the active EOS by `baseline_density_driver`, so applying the linear absolute margin envelope to the TEOS-10 dimensional density difference is not physically meaningful. R16.1 retains the positive-density sanity check but applies the absolute ratio envelope only to the linear EOS.

## Sea-ice extent

The R16 conservative meridional subgrid reconstruction does not solve the spatial-resolution limitation. The local SSP output still has extent much larger than area (for example late-century September at 10 deg is roughly 4.5 million km2 area versus 11.8 million km2 extent). This is evidence that the two-sector concentration field remains too diffuse for a satellite-like 15% extent product.

R16.1 therefore does **not** fit an empirical multiplier. Quantitative extent remains non-release-blocking until CLEM carries enough independent spatial sea-ice concentration degrees of freedom (or an independently justified subgrid pack-state closure) to support an extent claim.
