# EGCM v2.29.18 — Arctic calibration and CO2-target survival integrity

## Release status

- Engineering regression status: **PASS** for the focused v2.29.18 correction suite and retained integrity batches listed in `TEST_RESULTS_V2_29_18.txt`.
- Mandatory tuning-informed historical sea-ice calibration: **PASS at both 5° and 10°**.
- Independent predictive Arctic validation: **not claimed**. The historical records used here were inspected during development.
- Strict development-only sea-ice checks: **not all passed**. They remain non-release-blocking and are reported in the version-matched validation JSON.

## Corrected release blockers

### 1. Conservative compactness without premature full cover

v2.29.17 forced the local thickness toward 0.15 m by replacing the compactness law with a power-law local-thickness target. For much of its sampled exponent range, that made concentration reach one at only a few tenths of a metre and destroyed the March/September calibration.

v2.29.18 uses a two-regime conservative mapping. For equivalent thickness `h`, full-pack thickness `H`, exponent `n`, new-ice thickness `h_new`, and a fixed thin-branch transition concentration `C_t = 0.05`:

```text
C_pack = 1 - (1 - h/H)^n
C_thin = C_t * tanh[h / (h_new * C_t)]
C      = max(C_pack, C_thin), for 0 <= h < H
C      = 1, for h >= H
h_local = h / C
```

Properties now enforced across the complete prior support:

- `h_local -> h_new` as equivalent volume approaches zero;
- concentration is monotonic;
- concentration remains strictly below one for every `h < H`;
- full coverage occurs only at the declared full-pack equivalent thickness;
- `C * h_local = h`, so equivalent ice volume and latent heat are conserved;
- the calibrated compact-pack curve is retained outside the small new-ice branch.

The common 5°/10° calibrated defaults are:

```text
arctic_new_ice_local_thickness_m       = 0.15
arctic_full_cover_equivalent_thickness_m = 3.70
arctic_ice_concentration_exponent      = 2.00
```

The corresponding science priors are restricted to structurally valid support:

```text
new-ice local thickness: 0.08–0.30 m
full-cover equivalent thickness: 3.0–4.6 m
compact-pack exponent: 1.5–2.5
```

### 2. March and September transport are no longer tied to darkness alone

The former winter transport enhancement was weighted only by darkness. September can be dark while the reference air column remains comparatively warm, so increasing the March response also removed too much September ice.

v2.29.18 applies the enhancement only where the reference state is both dark and cold:

```text
coldness = clip[(T_freeze - T_reference_air) / T_scale, 0, 1]
winter_weight = darkness * coldness
```

This preserves deep-winter atmospheric energy convergence while strongly suppressing the nominal winter term during the warm autumn shoulder season.

Common calibrated defaults:

```text
arctic_winter_transport_enhancement          = 88.0 W/m2/K
arctic_winter_transport_temperature_scale_c  = 15.0 C
arctic_ice_surface_exchange_wm2_k             = 5.0 W/m2/K
arctic_transient_shortwave_scale              = 0.40
arctic_winter_lead_closure_fraction           = 0.0
```

The optional mechanical lead-closure branch remains disabled by default and its prior retains an explicit point mass at zero.

### 3. Arctic reference cache identity is complete

The v2.29.17 cache key omitted the newly active longwave damping coefficient. A model could therefore reuse a reference climatology generated under a different longwave setting.

v2.29.18 hashes a canonical serialization of every `arctic_*` configuration field together with the non-Arctic optical controls and exact grid geometry used by the reference solver. Different longwave, compactness, transport, grid, or reference-state settings now create separate cache entries.

### 4. CO2-target survival is mandatory per target

Target-specific failures are still isolated: one failed target does not discard successful targets from the same member. However, v2.29.18 now applies the ensemble failure gate independently to every requested target.

For each target:

- more than 20% unavailable members rejects the sweep;
- a run requested as quantitative must retain at least 20 usable members at every target;
- an explicit exploratory override may export a lower-count target, but the complete uncertainty product is forcibly classified `exploratory_only_invalid_quantitative_uncertainty`;
- target success counts and masks are stored in CSV, NPZ, summary, and run-state products.

A total-cell average can no longer hide complete failure at an extreme CO2 target.

## Version-matched sea-ice calibration

Historical SSP2-4.5 runs cover 1850–2027 with `dt = 0.05 years`. March temporal calibration uses the homogeneous post-1988 extent diagnostic; the discontinuous raw full-period March area slope is explicitly excluded as a calibration target.

### 5° default grid

| Metric | Model | Observed | Gate result |
|---|---:|---:|---|
| March area mean | 13.018 Mkm2 | 13.130 Mkm2 | PASS |
| March area RMSE | 0.445 Mkm2 | — | PASS |
| March extent mean | 15.139 Mkm2 | 15.272 Mkm2 | PASS |
| March extent RMSE | 0.332 Mkm2 | — | PASS |
| March extent trend | -0.274 Mkm2/dec | -0.406 Mkm2/dec | Robust trend suite PASS |
| September area mean | 3.685 Mkm2 | 4.155 Mkm2 | PASS |
| September area RMSE | 0.671 Mkm2 | — | PASS |
| September area trend | -0.562 Mkm2/dec | -0.492 Mkm2/dec | PASS |
| September extent RMSE | 0.863 Mkm2 | — | PASS |
| March–September area amplitude | 9.333 Mkm2 | 8.975 Mkm2 | PASS |

### 10° validation grid

| Metric | Model | Observed | Gate result |
|---|---:|---:|---|
| March area mean | 13.267 Mkm2 | 13.130 Mkm2 | PASS |
| March area RMSE | 0.461 Mkm2 | — | PASS |
| March extent mean | 15.428 Mkm2 | 15.272 Mkm2 | PASS |
| March extent RMSE | 0.332 Mkm2 | — | PASS |
| March extent trend | -0.291 Mkm2/dec | -0.406 Mkm2/dec | Robust trend suite PASS |
| September area mean | 3.741 Mkm2 | 4.155 Mkm2 | PASS |
| September area RMSE | 0.635 Mkm2 | — | PASS |
| September area trend | -0.583 Mkm2/dec | -0.492 Mkm2/dec | PASS |
| September extent RMSE | 0.797 Mkm2 | — | PASS |
| March–September area amplitude | 9.525 Mkm2 | 8.975 Mkm2 | PASS |

All predeclared mandatory calibration gates pass at both resolutions. The stricter development-only 0.60 Mkm2 September RMSE checks do not all pass and remain disclosed in:

- `SEA_ICE_VALIDATION_V2_29_18_5DEG.json`
- `SEA_ICE_VALIDATION_V2_29_18_10DEG.json`
- `VALIDATION_SUMMARY_V2_29_18.json`

## Interface and operational changes

- Full-cover equivalent thickness and compact-pack exponent are now exposed through the CLI, desktop GUI, and Streamlit interface.
- All new fields have setting metadata and tooltip coverage.
- `rerun_co2_target_sweep_v22918.ps1` contains the complete corrected command for the previously failed explicit-target experiment.
- GUI startup logging and the v2.29.17 visible-error hotfix are retained.
- Safe-checkpoint self-validation, uncompressed high-ratio arrays, runtime provenance, and fixed Arctic substepping are retained.

## Interpretation limits

This remains a reduced-complexity sensitivity emulator. Passing tuning-informed historical gates demonstrates internal calibration consistency, not independent forecast skill. Arctic regional geometry, March extent, ice-free timing, AMOC collapse thresholds, and Greenland contributions should be interpreted as scenario and parameter sensitivities rather than precise predictions.
