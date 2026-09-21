# Arctic sea-ice scientific review fixes — 2026 patch

This patch addresses the scientific-validation problems identified in the review of the v2.29.25 Arctic component. It deliberately follows the review's recommended order: correct the observation/validation contract first, add independent physical constraints, and only then consider additional sea-ice mechanisms after recalibration shows what residual problem remains.

## What is fixed in this patch

### 1. Raw NSIDC area is no longer a calibration or skill target

`sea_ice_validation.py` now treats the packaged NSIDC Sea Ice Index raw `area` column as provenance-only data. It is not used for:

- historical calibration gates;
- trend-skill scores;
- rolling-origin area scores;
- release classification;
- headline September area skill.

The raw values remain available under explicit `*_raw_area_excluded` fields so the observational discontinuity can be audited without silently influencing optimization.

Scientific area validation now fails closed until a homogeneous concentration-derived fixed-mask area dataset is supplied in `data/validation/sea_ice_fixed_mask/`.

### 2. The historical fitted area-to-extent multiplier is removed from active outputs

The production model no longer converts native area to extent with the historical March/September zero-intercept coefficients.

The old coefficients remain only in `sea_ice_observation.py` as explicit legacy reproduction helpers. They are not used by model output, validation, or release gates.

The current 15% extent output is a direct threshold diagnostic of the native coarse zonal concentration field. Because the model does not resolve satellite-scale spatial concentration, this extent is explicitly **diagnostic only** and is excluded from scientific pass/fail gates. This prevents the patch from replacing the old fitted operator with a new false extent-skill claim.

### 3. Physical area and concentration-product area are separated

The sea-ice observation layer now reports distinct quantities:

- native physical Northern Hemisphere ice area: all prognostic concentration;
- 15%-thresholded area: concentration integrated only where native concentration is at least 0.15;
- 15%-threshold extent: ocean-cell area where native concentration is at least 0.15.

This makes the observational definition explicit and prevents an area/extent mapping from being hidden inside one reported metric.

### 4. Independent volume/thickness validation is implemented

`SimulationResult.northern_sea_ice_volume_thickness_at_index()` now exposes native Northern Hemisphere:

- sea-ice volume;
- mean ice thickness;
- area of ice with local thickness >= 2 m;
- thick-ice area fraction.

`sea_ice_validation.py` can ingest independent monthly physical observations from `data/validation/sea_ice_physical/volume_thickness_monthly.csv`.

Scientific validation fails closed if no independent volume/thickness constraint is supplied. When supplied, all available physical metrics must pass predeclared normalized-RMSE gates rather than merely existing.

### 5. Fixed-mask area validation has an explicit schema and like-for-like guard

`data/validation/sea_ice_fixed_mask/README.md` defines the required March/September files and metadata. Validation requires metadata declaring:

- `fixed_mask=true`;
- concentration threshold 0.15;
- `model_domain_compatible=true`;
- both March and September tables present.

The compatibility flag must document that the observation and model cover like-for-like ocean area. A permanent observational hole cannot simply be ignored when comparing mean area levels.

### 6. The empirical thick-pack resistance is disabled in production

`arctic_ice_area_thick_pack_resistance_exponent` now defaults to `0.0` instead of `4.0`.

The closure remains available for explicit structural sensitivity experiments, but the built-in science-prior sampling path fixes it at zero. It should only be re-enabled after independent thickness/volume observations justify the functional form and exponent.

### 7. The built-in shrinking-ice attenuation of forced ocean heat convergence is disabled

A new control, `arctic_forced_ocean_heat_convergence_ice_fraction_exponent`, defaults to `0.0`.

The previous effective square-root ice-fraction dependence can be reproduced with an exponent of `0.5` for a labelled sensitivity experiment, but it is no longer active by default. This removes the unvalidated mechanism that automatically weakened additional ocean heat convergence as the pack disappeared.

The 4 W m^-2 K^-1 strength and 1 C onset remain phenomenological structural uncertainties and still require observational heat-transport calibration.

### 8. Existing explicit ice export was retained

The model already contains continuous thickness-dependent sea-ice export through `_arctic_ice_export_flux_wm2`, with equal-and-opposite lower-latitude energy accounting for transient export anomalies. This patch therefore does not add a second duplicate export sink.

Whether the existing export law is quantitatively adequate should be assessed after the corrected area/volume calibration is available.

### 9. True nested hindcast infrastructure is added

`sea_ice_nested_hindcast.py` provides a strict fold-specific harness. For every fold it requires:

1. a new complete calibration call;
2. provenance showing the maximum training-data year;
3. no future-observation use;
4. a fold-specific calibrated configuration;
5. forecast-only scoring.

A fixed historical trajectory cannot pass as a nested hindcast. The release still makes no predictive-skill claim because the required fold-by-fold recalibrations have not yet been run with the missing corrected observations.

### 10. Scientific metadata, UI text, and current lean validator are corrected

Current runtime metadata and UI text no longer describe extent as a fitted observation-equivalent product. `tools/validate_v22925_lean.py` no longer inserts the raw NSIDC area column into `observed_area`.

The scientific-use declaration now states that Arctic scientific validation is incomplete until fixed-mask area, independent volume/thickness constraints, full recalibration, and nested hindcasts are completed.

## What is intentionally not claimed as fixed yet

The following items should not be implemented or tuned blindly before the corrected observational calibration exists:

- a new thin-ice / multiyear-ice category model;
- additional export tuning;
- snow-on-ice and melt-pond/albedo complexity;
- stochastic internal variability and probabilistic ice-free-year estimates;
- final late-century SSP sea-ice conclusions;
- a reduced/identified final Arctic parameter set.

Those are phase-two changes. The corrected validation framework is designed to reveal which of them are actually required instead of adding mechanisms to compensate for an observational artifact.

## Current scientific status

The software/engineering path is functional, but **Arctic scientific validation remains deliberately incomplete** because the source archive does not contain a homogeneous fixed-mask area dataset or independent volume/thickness observations, and complete nested historical recalibrations have not been run.

That is now represented as a failed/closed scientific gate rather than a positive skill claim.

## Six-source observational follow-up

The validation framework has now been extended to the six-product stack
requested after this patch: G02202 v6 fixed-mask area, PIOMAS v2.1 volume,
CryoSat-2 RDEFT4 v1 thickness, ICESat-2 IS2SITMOGR4 v4 thickness, OSI SAF
OSI-450-a1 v3.1 independent area cross-check, and NSIDC-0611 v4 sea-ice-age
structure. See `SIX_SOURCE_ARCTIC_VALIDATION_2026.md`.

Availability is fail-closed per source and requires provenance metadata. The
source archive currently contains processed PIOMAS evidence only; acquisition
scripts are provided for the remaining products rather than substituting data.
