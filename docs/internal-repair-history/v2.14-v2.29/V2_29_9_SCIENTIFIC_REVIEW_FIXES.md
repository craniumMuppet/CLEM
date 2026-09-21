# v2.29.9 Scientific Review Fixes

## Scope

v2.29.9 addresses the scientific-evidence, calibration-gate, uncertainty-surface, and interface findings in the independent review of v2.29.7. It retains the v2.29.8 resumable-run system, explicit CO2 targets, and AMOC percentage-decline products.

This release does **not** claim independent temporal prediction skill. All Arctic observations available through March 2026 were inspected during development. Calendar year 2027 onward remains the prospective evaluation period.

## Evidence and release-language corrections

- Removed “temporal skill” from the release name and active scientific-evidence description.
- Reclassified all historical rolling-origin and blocked-baseline scores as descriptive, tuning-informed diagnostics rather than release gates.
- Replaced the overlapping trailing-five-year comparison with non-overlapping five-year target blocks.
- Labels future ice-free timing as a threshold-crossing sensitivity result, not a forecast.
- Labels future extent as a secondary statistical operator without quantitative future confidence.
- Reclassified the broad OISST envelopes as descriptive sanity bounds only. They are not advertised as a reproduced observational pass and are not release-blocking while processed release data and source hashes are unavailable.

## Robust March trend evaluation

The former absolute-error-only gate allowed a March area trend almost five times the observed magnitude to pass by a very small margin. v2.29.9 replaces it with a multi-part criterion:

- absolute OLS trend error no greater than 0.10 million km2 per decade;
- model/observed trend-magnitude ratio no greater than 3.5;
- median absolute OLS error across predeclared periods no greater than 0.12 million km2 per decade;
- maximum absolute OLS error across those periods no greater than 0.18 million km2 per decade;
- matching decline direction in at least 80% of periods;
- OLS standard errors and 95% confidence intervals;
- Theil-Sen slope and 95% interval as a robust companion diagnostic.

Predeclared periods are 1979-2020, 1985-2020, 1990-2020, 1979-2015, and 1985-2015.

With the v2.29.9 defaults, the 1979-2020 native March-area trend is -0.1212 million km2 per decade versus -0.0382 observed. The absolute error is 0.0831 and the magnitude ratio is 3.18. This is materially improved from the reviewed v2.29.7 value of approximately 4.90 times observed, but it remains a tuning-informed reduced-complexity result rather than independent predictive validation.

## Arctic structural and calibration changes

- Replaced the legacy concentration mapping with a conservative compactness curve:
  `concentration = 1 - (1 - normalized_equivalent_thickness)^exponent`.
- Preserves equivalent ice volume exactly through `concentration * local_thickness`.
- Increased full-cover equivalent thickness from 3.0 m to 4.0 m.
- Set compactness exponent to 2.0.
- Reduced lateral reference-restoring default from 27.5 to 25.0 W m-2 per unit ice-fraction anomaly.
- Reduced transient shortwave scale from 1.0 to 0.9.
- Reduced lapse/inversion closure from 1.2 to 1.0 W m-2 K-1.
- Reduced basal ocean-ice exchange from 4.0 to 3.5 W m-2 K-1.
- Reduced open-water/ocean exchange from 30 to 25 W m-2 K-1.

The native 1979-2020 metrics from the full default historical run are:

| Metric | v2.29.9 result |
|---|---:|
| March area mean | 13.123 million km2 |
| March area trend | -0.1212 million km2/decade |
| March area RMSE | 0.378 million km2 |
| September area mean | 4.554 million km2 |
| September area trend | -0.3645 million km2/decade |
| September observed trend | -0.4923 million km2/decade |
| September area RMSE | 0.640 million km2 |
| 2021-2025 September area RMSE | 0.533 million km2 |
| 2021-2025 September extent RMSE | 0.623 million km2 |

The 2021-2025 September extent RMSE exceeds the retained 0.60 development benchmark. This is disclosed as a non-release-blocking development miss; it is not recast as independent validation or hidden by widening a scientific gate.

## Structural uncertainty for lateral restoring

- Zero lateral restoring is now a valid normal configuration.
- Negative restoring remains invalid.
- The built-in Monte Carlo prior includes an explicit 20% point mass at zero.
- The remaining 80% samples a continuous 2-40 W m-2 branch with mode 25 W m-2.
- Desktop, CLI, Streamlit, metadata, and uncertainty interfaces accept and describe the disabled case.

This exposes the decisive restoring closure as a structural uncertainty rather than making it mandatory.

## Cross-domain recalibration and validation

The Arctic changes were rechecked against global temperature, ocean heat uptake, AMOC, Greenland, and hosing recovery. The AMOC thermal stratification saturation scale was set to 0.60 C and the convection-recovery timescale to 20 years. Greenland marine influence was set to 0.70.

Full-resolution default results:

| Diagnostic | v2.29.9 result | Active development range |
|---|---:|---:|
| Historical GMST, 2011-2020 | 1.162 C | 0.95-1.20 C |
| Ocean heat gain, 1971-2018 | 402.1 ZJ | 350-500 ZJ |
| SSP2-4.5 AMOC weakening | 26.76% | 15-40% |
| SSP5-8.5 AMOC weakening | 36.80% | 25-55% |
| Greenland SSP2-4.5 contribution by 2100 | 88.15 mm | 60-105 mm |
| Standard hosing recovery | 84.61% | at least 80% |

The hosing recovery result now has about 4.6 percentage points of margin above its gate rather than approximately 0.15 percentage points. The retained seasonal hybrid-pathway 2100 AMOC assertion has also been restored to the pre-v2.29.7 10-14 Sv range; the v2.29.9 default gives approximately 10.99 Sv. The SSP2-4.5 single-year 2100 AMOC floor is again 10 Sv.

AMOC absolute control temperatures now use the native 5-degree climatology as one canonical reference at every supported grid resolution. Prognostic anomalies still evolve on the selected grid, but the initial density margin no longer changes because a coarse coastline cell contains a different land/ocean fraction. The 2.5-10 degree initial-density-ratio spread is 0.0, restoring the former 0.20 maximum.

AMOC and Greenland remain reduced-complexity sensitivity outputs, not precise forecasts.

## Interface synchronization

Streamlit ranges now cover the documented configuration/prior surfaces:

- lapse/inversion closure: 0-1.8 W m-2 K-1;
- basal ocean-ice exchange: 0.5-5.0 W m-2 K-1;
- lateral restoring: 0-40 W m-2, with zero explicitly disabling it;
- convection recovery: 10-300 years.

The desktop Monte Carlo range for convection recovery is also 10-300 years.

## Retained v2.29.8 operational features

- Atomic long-run manifests and exact saved-run loading.
- Persisted resolved random seeds.
- Per-member and per-target checkpoints.
- Incremental or explicit CO2 target lists.
- AMOC percentage-decline trajectories and weighted uncertainty intervals.

## Scientific classification

- Software and numerical-integrity testing: release-blocking.
- Historical Arctic scores through March 2026: tuning-informed descriptive development evidence.
- OISST envelopes: descriptive sanity checks only.
- Future sea-ice area: sensitivity output.
- Future extent: secondary statistical output.
- Ice-free timing: threshold-crossing sensitivity, not a quantitative forecast.
- AMOC and Greenland: reduced-complexity sensitivity experiments.
- Independent Arctic temporal validation: not yet available; reserved prospectively from 2027 onward.
