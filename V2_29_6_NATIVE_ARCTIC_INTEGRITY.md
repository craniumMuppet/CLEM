# v2.29.6 Native Arctic Integrity

## Corrected publication semantics

Hemispheric sea-ice **area is native model output**. The reporting layer does
not fit an intercept, rescale area seasonally, or apply a post-2020 target. This
removes the v2.29.5 failure in which an over-iced native September state could
be transformed into apparent observational agreement.

Sea-ice **extent** remains a diagnostic conversion from native area because the
reduced two-sector geometry does not resolve grid-cell concentration patterns.
The conversion has a zero intercept, is continuous and monotone, and is bounded
by the physical minimum concentration used to define extent.

## Native calibration targets

The thermodynamic Arctic reference state is calibrated directly against March
and September area. Validation evaluates:

- March and September climatological means;
- March-to-September seasonal amplitude;
- September historical trend;
- 2021-2025 validation-informed performance;
- native-area projection ordering under SSP1-2.6, SSP2-4.5, SSP4-6.0 and
  SSP5-8.5;
- late-century and year-2100 area without a statistical future closure.

## Winter cap integrity

The former 1.2 m active ceiling has been removed from the calibrated state. The
current high ceiling is an emergency guard. The reference cycle must remain
comfortably below it, and validation explicitly measures occupancy rather than
inferring physical freedom from broad area bounds.

## Interpretation limits

The Arctic module resolves zonal fractions and thermodynamic reservoirs, not
real basin geography, ice export, ridging or regional concentration fields.
Longitude-pattern maps are visualizations and have no regional forecast skill.
The area time series can be interpreted at the hemispheric reduced-model scale;
15% extent, open-water temperature, AMOC and Greenland outputs retain the
limitations documented in the release review.

## Integrity tests

The v2.29.6 regression inventory includes direct assertions for:

- exact identity between published and native area;
- exact zero and near-zero continuity;
- monotonic and bounded extent conversion;
- freely evolving reference thickness and zero cap occupancy;
- synchronized CLI, desktop, Streamlit and Monte Carlo defaults;
- Windows and Linux startup coverage;
- version-correct, platform-aware dependency verification;
- restart-safe parallel validation and complete package inventory.
