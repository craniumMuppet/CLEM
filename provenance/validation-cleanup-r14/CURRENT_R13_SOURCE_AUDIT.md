# CLEM v2.29.28 - R13 current-source scientific audit

Audit basis: the user-supplied final source ZIP and R13 validation-results ZIP. No model physics was changed and no expensive climate integration was run.

## Package verification

| Artifact | Expected SHA-256 | Verified SHA-256 | Result |
|---|---|---|---|
| CLEM-v2.29.28-source.zip | cd28bd1c35c5031bc5fc50288462ffadf0c256880fa2093210b293dc20682a30 | cd28bd1c35c5031bc5fc50288462ffadf0c256880fa2093210b293dc20682a30 | PASS |
| CLEM-v2.29.28-physics-repair-r13-validation-results.zip | 3ebb04a5c6d609184f9576a77592c422e26d9956774ab0537111c2324708befb | 3ebb04a5c6d609184f9576a77592c422e26d9956774ab0537111c2324708befb | PASS |

Source ZIP file count: 694. Current `climate_model.py` SHA-256: `aa3e9d43cf77c400f105ea0c9c98585310081d85bc838b2bdfcaacbde442fd67`, matching the R13 source fingerprint. R13 dynamics-equivalence provenance reports the release core AST equivalent to the validated predecessor core.

## A. Scientific-release Boolean audit

### A1. Direct Boolean chain used by `scientific_release_passed`

All resolution-dependent values below are true at both 5 deg and 10 deg unless stated otherwise.

| Flag | Current value | Source / function | Immediate reason | Upstream dependencies | Status category |
|---|---:|---|---|---|---|
| `observation_files_verified` | true | `combine_v22923_validation.py:162-167`, `combine_validation`; source value from `validate_v22923.py:1122-1124` | Packaged G02202 March/September files match recorded hashes | `dataset_metadata.packaged_file_hashes_match` | already passed |
| `engineering_integrity_passed` | true | `combine_v22923_validation.py:250-270`, `combine_validation` | `TEST_RESULTS_V2_29_28.json`: 146 passed, 0 failed, 0 errors | canonical bounded engineering suite | already passed |
| `historical_calibration_passed` | true | `combine_v22923_validation.py:168-173`; `sea_ice_validation.py:1139-1175`, `calibration_passes` | All 16 calibration gates pass at both resolutions | calibration gates listed below | already passed |
| `recent_period_evaluation_passed` | true | `combine_v22923_validation.py:174-179`; `sea_ice_validation.py:1177-1206`, `development_evaluation_passes` | All 8 2021-2025 development-evaluation gates pass | recent-period gates listed below | already passed |
| `cross_resolution_passed` | true | `combine_v22923_validation.py:128-160`, `combine_validation` | All five 5 deg vs 10 deg convergence gates pass | cross-resolution gates below | already passed |
| `structural_area_volume_passed` | true | `combine_v22923_validation.py:194-199`; `validate_v22923.py:461-703`, `structural_area_volume_experiments` | All three structural checks pass at both resolutions | structural checks below | already passed |
| `arctic_air_engineering_checks_passed` | true | `combine_v22923_validation.py:200-216`, `gate_subset` | All seven selected Arctic coupled gates pass at both resolutions | Arctic coupled gates below | already passed |
| `greenland_engineering_checks_passed` | true | `combine_v22923_validation.py:217-225`, `gate_subset` | All five Greenland coupled gates pass at both resolutions | Greenland coupled gates below | already passed |
| `positive_september_temporal_skill_passed` | false | `combine_v22923_validation.py:180-185`; source field hard-coded at `sea_ice_validation.py:1636` | Both resolutions expose `scientific_temporal_skill_gate_passed=false`; retrospective folds do not beat all baselines and are explicitly non-independent | retrospective fold-local manifest; prospective period not available | obsolete/dead validation logic as a release blocker |
| `extent_independently_validated` | false | `combine_v22923_validation.py:186-193` | Combiner requests `area_operator.extent_independent_validation_evidence`, a key the current operator intentionally does not provide; native extent is not an independently prognostic spatial field | native two-sector concentration diagnostic | logically inappropriate for CLEM as currently resolved |
| `amoc_validation_passed` | true | `combine_v22923_validation.py:240-248`, `gate_subset` | Initial-strength, decline/collapse, and salt-conservation gates pass at both resolutions | four AMOC/salt gates below | already passed |
| `independent_prospective_validation_available` | false | `combine_v22923_validation.py:285` | Hard-coded false; future untouched observations are not yet sufficient | reserved prospective period | requires future observations |
| `scientific_release_passed` | false | `combine_v22923_validation.py:272-288` | First conjunction is blocked by temporal-skill and extent flags; second conjunction additionally hard-requires future prospective availability | all rows above | obsolete/misleading composite until gate semantics are repaired; genuine independent predictive validation still requires future observations |

Important internal contradiction: `sea_ice_validation.py:1638-1639` explicitly sets `historical_scores_are_release_blocking=false` and `extent_metrics_are_release_blocking=false`, yet the combiner at `combine_v22923_validation.py:281-282` requires both corresponding false flags.

### A2. Historical calibration leaves (both 5 deg / 10 deg)

Source: `sea_ice_validation.py:1139-1175`, `calibration_passes`.

| Upstream Boolean | 5 deg | 10 deg | Feeds | Status |
|---|---:|---:|---|---|
| `raw_nsidc_area_excluded_from_calibration` | true | true | `historical_calibration_passed` | already passed |
| `extent_operator_contains_no_observational_fit` | true | true | same | already passed |
| `march_fixed_mask_area_rmse_le_1p00` | true | true | same | already passed |
| `september_fixed_mask_area_rmse_le_1p00` | true | true | same | already passed |
| `march_fixed_mask_area_trend_direction_matches` | true | true | same | already passed |
| `september_fixed_mask_area_trend_direction_matches` | true | true | same | already passed |
| `march_fixed_mask_area_trend_magnitude_ratio_in_range` | true | true | same | already passed |
| `september_fixed_mask_area_trend_magnitude_ratio_in_range` | true | true | same | already passed |
| `march_fixed_mask_area_ols_95pct_trend_intervals_overlap` | true | true | same | already passed |
| `september_fixed_mask_area_ols_95pct_trend_intervals_overlap` | true | true | same | already passed |
| `coarse_zonal_extent_excluded_from_scientific_release_gate` | true | true | same | already passed; contradicts combiner extent requirement |
| `homogeneous_fixed_mask_area_dataset_available` | true | true | same | already passed |
| `piomas_and_both_satellite_thickness_sources_available` | true | true | same | already passed |
| `source_separated_physical_constraints_pass` | true | true | same | already passed |
| `march_exact_fixed_mask_operator_applied` | true | true | same | already passed |
| `september_exact_fixed_mask_operator_applied` | true | true | same | already passed |

### A3. Recent-period development-evaluation leaves (both resolutions)

Source: `sea_ice_validation.py:1177-1206`, `development_evaluation_passes`.

| Upstream Boolean | 5 deg | 10 deg | Feeds | Status |
|---|---:|---:|---|---|
| `raw_nsidc_area_excluded_from_development_score` | true | true | `recent_period_evaluation_passed` | already passed |
| `coarse_zonal_extent_excluded_from_development_score` | true | true | same | already passed |
| `march_homogeneous_fixed_mask_area_available` | true | true | same | already passed |
| `september_homogeneous_fixed_mask_area_available` | true | true | same | already passed |
| `march_fixed_mask_area_rmse_le_0p50` | true | true | same | already passed |
| `september_fixed_mask_area_rmse_le_0p50` | true | true | same | already passed |
| `march_exact_fixed_mask_operator_applied` | true | true | same | already passed |
| `september_exact_fixed_mask_operator_applied` | true | true | same | already passed |

### A4. Cross-resolution leaves

Source: `combine_v22923_validation.py:128-160`, `combine_validation`.

| Upstream Boolean | Value | Feeds | Status |
|---|---:|---|---|
| `gmst_difference_le_0p10c` | true | `cross_resolution_passed` | already passed |
| `arctic_air_amplification_difference_le_0p50` | true | same | already passed |
| `amoc_2100_difference_le_1sv` | true | same | already passed |
| `march_area_difference_le_0p30_mkm2` | true | same | already passed |
| `september_area_difference_le_0p30_mkm2` | true | same | already passed |

### A5. Structural area/volume leaves

Source: `validate_v22923.py:658-703`, `structural_area_volume_experiments`.

| Upstream Boolean | 5 deg | 10 deg | Feeds | Status |
|---|---:|---:|---|---|
| `production_process_ledger_closed` | true | true | `structural_area_volume_passed` | already passed |
| `integrated_production_path_checks_passed` | true | true | same | already passed |
| `no_zero_area_nonzero_volume_state` | true | true | same | already passed |

### A6. Coupled AMOC/Arctic/Greenland leaves

Source: `ARCTIC_GREENLAND_AMOC_VALIDATION_V2_29_28_{5,10}DEG.json`; selection logic in `combine_v22923_validation.py:200-248`.

| Upstream Boolean | 5 deg | 10 deg | Final aggregate | Status |
|---|---:|---:|---|---|
| `arctic_air_amplification_between_1p5_and_3p5` | true | true | Arctic engineering | already passed |
| `maximum_arctic_air_anomaly_le_15c` | true | true | Arctic engineering | already passed |
| `forcing_like_transport_coefficient_le_25_wm2_k` | true | true | Arctic engineering | already passed |
| `transport_power_upper_bound_lt_2pw` | true | true | Arctic engineering | already passed |
| `concentration_bounds_hold` | true | true | Arctic engineering | already passed |
| `local_ice_thickness_nonnegative` | true | true | Arctic engineering | already passed |
| `lead_closure_compensation_disabled` | true | true | Arctic engineering | already passed |
| `greenland_driver_uses_limited_low_pass_maritime_term` | true | true | Greenland engineering | already passed |
| `greenland_freshwater_weakens_or_does_not_strengthen_amoc` | true | true | Greenland engineering | already passed |
| `greenland_mass_identity_error_le_1e_minus_4_gt` | true | true | Greenland engineering | already passed |
| `greenland_requested_above_cap_le_5pct` | true | true | Greenland engineering | already passed |
| `greenland_target_cap_activation_le_5pct` | true | true | Greenland engineering | already passed |
| `initial_amoc_between_16p5_and_17p5_sv` | true | true | AMOC validation | already passed |
| `amoc_2100_above_collapse_threshold` | true | true | AMOC validation | already passed |
| `amoc_decline_between_0_and_50pct` | true | true | AMOC validation | already passed |
| `salt_conservation_error_le_0p1ppm` | true | true | AMOC validation | already passed |

### A7. Relevant booleans computed/reported but NOT actually included in the final conjunction

These matter for interpretation because the current architecture computes them but the final `scientific_release_passed` expression does not consume them directly.

| Flag | Value | Location | Note |
|---|---:|---|---|
| `arctic_ocean_sanity_checks_passed` | true | `combine_v22923_validation.py:226-232` | Computed from open-water benchmark, not in final conjunction |
| `greenland_posthoc_sanity_checks_passed` | true | `combine_v22923_validation.py:233-239` | Computed from external post-hoc benchmark, not in final conjunction |
| `all_current_sea_ice_engineering_gates_passed` | true | `sea_ice_validation.py:1545-1552,1633` | Per-resolution engineering summary |
| `observational_stack_complete` | false | `sea_ice_validation.py:1553-1557` | False because NSIDC-0611 v4 is missing |
| `prospective_untouched_validation_complete` | false | `sea_ice_validation.py:1558` | Hard-coded false pending future period |
| `scientific_validation_complete` | false | `sea_ice_validation.py:1559-1563` | Correctly remains false with incomplete six-source stack / no prospective evidence |
| `historical_scores_are_release_blocking` | false | `sea_ice_validation.py:1638` | Explicit semantic statement contradicted by combiner |
| `extent_metrics_are_release_blocking` | false | `sea_ice_validation.py:1639` | Explicit semantic statement contradicted by combiner |

## B. Review A / Review B current-source audit

| Review finding | Current R13 status | Exact current-source evidence | Physical/scientific significance | Recommended action | New numerical run? |
|---|---|---|---|---|---|
| A1. Arctic spatial extent is a physical failure | YES | `SEA_ICE_VALIDATION_V2_29_28_5DEG.json`: March mean 22.889, Sept mean 16.408; RMSE 7.638/10.407 million km2. At 10 deg RMSE 13.276/10.853. Operator metadata says two-sector native threshold diagnostic and non-independent field (`sea_ice_validation.py:1577-1596`). | Strong evidence that satellite-style extent is under-resolved even though area is much better (area RMSE about 0.50-0.53 million km2). | Keep extent diagnostic/non-release-blocking for v2.29.28. For a future physical improvement, add spatial degrees of freedom (e.g. additional latitude bands/sectors) with conservation; do not fit an area-to-extent multiplier. | Gate/claim cleanup: no. New spatial physics: yes. |
| A2. Independent Arctic temporal prediction not demonstrated | YES | `RETROSPECTIVE_FOLD_LOCAL_ARCTIC_HINDCAST_V2_29_28.json`: model RMSE 0.673/0.720/0.483 vs expanding-trend 0.507/0.659/0.451; `scientific_predictive_skill_claim_allowed=false`. `sea_ice_validation.py:1470-1514`. | Historical development evidence does not establish independent predictive skill. | Preserve retrospective scores as development diagnostics; preregister and wait for untouched prospective observations. | No physics run for terminology; future prospective evaluation needed. |
| A3. CryoSat-2 temporal behavior poor | YES | 5 deg correlation -0.14285; 10 deg -0.12274, 14 records. PIOMAS about 0.934 and ICESat-2 about 0.678/0.692. Metrics computed at `sea_ice_validation.py:1250-1359`. | Mean-state fit can be acceptable while temporal evolution is wrong or the observation operator/short record is problematic. | Diagnose month alignment, footprint/mask, weights, conversion, anomaly/trend treatment and seasonality before changing thickness physics. | Operator-only diagnosis: no coupled run unless operator changes outputs; physics change: yes. |
| A4. AMOC bifurcation structure remains closure-dependent | YES | `climate_model.py:8371-8448`: depth feedback strength 0.35, multiplier clipped 0.75-1.25, density exponent 1.50, positive-state smooth saturation to 20 Sv, reversal disabled by default (`:607`, `:8425-8428`). | Collapse/recovery/hysteresis can depend on reduced-order closure choices. | Structural-sensitivity branch over physically defensible closures; report threshold uncertainty instead of tuning a preferred result. | YES, staged user-side AMOC suite. |
| A5. Constant alpha/beta EOS remains | YES | `climate_model.py:513` alpha=2.0e-4 K-1; `:542` beta=7.6e-4 PSU-1; used directly at `:7564-7568`. | Density driver is a small residual of opposing terms, so linear EOS assumptions matter. | Add a diagnostic reduced TEOS-10 box-density alternative first; do not replace validated closure until sensitivity is quantified. | YES for comparison branch. |
| A6. Do not simply increase `amoc_reference_sv` | STILL VALID | Control pycnocline budget defaults: Ekman 25, upwelling 5, eddy 13, AMOC 17 (`climate_model.py:648-652` and pycnocline imbalance at `:8495-8501`). FovS control also derives SAU salinity from AMOC reference (`:3007-3012`). | Changing only reference transport would break coupled control consistency. | Fix density geometry/EOS/source-water consistency first; only then rebalance the entire control state if needed. | A later re-balance would require full AMOC validation. |
| A7. Some validation is calibration/development evidence | PARTIALLY FIXED | `sea_ice_validation.py` now explicitly labels retrospective development evidence and prospective reservation (`:1512-1514`, `:1617-1630`), but combiner still uses broad `scientific_release_passed` and `engineering_only` (`combine_v22923_validation.py:272-289`). | Terminology can overstate independence or incorrectly treat unavailable future evidence as model failure. | Split engineering, numerical verification, physics verification, development evaluation, structural validation and independent prospective validation. Add tri-state `not_available` for prospective validation while retaining compatibility aliases. | No numerical run. |
| B1. AMOC hydraulic density geometry mixes inconsistent water masses | YES | Hydraulic haline term is North minus Southern Ocean surface (`climate_model.py:7565-7567`, call at `:8321-8328`). FovS and upper-limb advection use South Atlantic Upper/deep (`:7633-7644`, `:8505-8522`). Initial North=35.15, Southern surface=33.00 (`:618-621`); FovS-derived SAU=35.4588 (`:3007-3012`). Current control terms reproduce alpha*dT=-0.00120, beta*dS=+0.001634, net +0.000434; North-South surface=+2.15 PSU vs North-SAU=-0.3088 PSU. | The hydraulic density driver uses a very fresh surface reference that is not the actual upper overturning limb, creating cancellation and potentially excessive sensitivity. | Redesign hydraulic thermal/haline source and sinking water masses coherently. Do not tune final AMOC strength during this stage. | YES, staged user-side AMOC suite. |
| B2. Greenland land-ice melt is compensated like redistribution | YES | `climate_model.py:8252` adds Greenland freshwater to North; `:8276` includes it in `total_anomaly`; `:8277-8282` removes the same freshwater from external or Atlantic boxes. | Land-ice melt adds water/mass to the ocean; artificial compensating freshwater deficit is conceptually wrong for Greenland melt. | Separate hydrological redistribution, selectable hosing compensation, and uncompensated Greenland land-ice addition with global-ocean dilution/mass bookkeeping. | YES: freshwater/salt conservation, drift, warming, coupled AMOC and hosing-distinction tests. |
| B3. `amoc_pycnocline_relaxation_years` is dead | YES | Defined/validated/CLI-mapped at `climate_model.py:556,1332-1333,13906-13907`; exposed in `app.py:489,617`, desktop GUI `climate_model_gui.py:179,313,527,2052`, Monte Carlo and metadata; no dynamical equation reads the field. | User-facing physical knob and Monte Carlo prior change nothing, misleading users and uncertainty analysis. | Remove/deprecate it from active interfaces and sampling while preserving backward-compatible config parsing if desired; do not invent a relaxation term merely to justify the setting. | No climate integration if dynamics remain unchanged; interface/static tests only. |
| B4. Arctic empirical/restoring terms require mechanism tests | YES AS MECHANISMS; DOUBLE COUNTING NOT PROVEN | Extra lapse feedback `climate_model.py:282,7355-7371`; forced heat convergence `:421-424,6261-6288`; phase restoring `:5875+`; reference ocean restoring `:434,5351+`. | These can overlap with resolved moist-lapse, transport and seasonal processes, but source inspection alone cannot prove double counting. | Run ablations: resolved lapse only, extra lapse only, both; heat convergence on/off; restoring on/off/range. Check energy, amplification, sea-ice cycle/trend and timestep stability. | YES for mechanism experiments on user's PC; no permanent change before results. |
| B5. Greenland elevation feedback missing/limited | YES | No Greenland elevation/surface-height state or melt-temperature elevation feedback exists in current model code; PDD/SMB and finite mass are present. | Lower priority for 21st century, more relevant for multi-century high-warming runs. | Design only after higher-priority freshwater/AMOC issues; couple thinning/lowering to local temperature conservatively. | YES if added. |
| B6. Core/GUI/default drift | YES, DESKTOP GUI ONLY FOR HIGHLIGHTED CURRENT CHECKS | CLI zero-argument `config_from_args` equals all 285 `ModelConfig` fields. Streamlit highlighted controls use `DEFAULT_MODEL_CONFIG` (`app.py:247,326,334,342-343,405,488-494`). Desktop GUI effective defaults differ in 10 physical fields: water-vapour height 0.98->1.00; AMOC interhemispheric coupling 0->0.02; pycnocline feedback 0.35->0.10; convection critical ratio 0->0.91; transition width 0.10->0.035; convection transport exponent 0->1.0; SAU external exchange 0.50->2.0; AMOC heat damping 2.60->1.35; surface heat coupling 0.50->0.075; Greenland max freshwater 0.10->0.025 (`climate_model_gui.py:291,304,307-318,333` plus water-vapour hardcode near `:280`). | Same nominal default model produces materially different physics depending on desktop GUI versus CLI/Streamlit. This is a release-consistency blocker. Some convection fields are legacy/no-op, but their UI disagreement is still misleading. | Make desktop GUI defaults derive from `MODEL_DEFAULT_CONFIG` and add an exhaustive GUI-command -> `ModelConfig` parity regression, excluding intentional run-control fields such as scenario/duration. | No expensive climate integration; compile/import/GUI command parity/zero-year checks. |

## Additional current observations

### Extent vs area

| Resolution | March extent mean | September extent mean | March extent RMSE | September extent RMSE | March area RMSE | September area RMSE |
|---|---:|---:|---:|---:|---:|---:|
| 5 deg | 22.889 | 16.408 | 7.638 | 10.407 | 0.510 | 0.525 |
| 10 deg | 28.536 | 16.822 | 13.276 | 10.853 | 0.504 | 0.529 |

Units are million km2. This is the strongest evidence that the extent problem is spatial representation, not a one-parameter level calibration.

### Missing sixth Arctic product

`ARCTIC_VALIDATION_STACK_STATUS_2026.json` reports five available products and only `nsidc_0611_v4` as `missing_or_invalid`. The missing product is therefore a real current gap, not a stale review item.

### Desktop GUI effective default differences

The automated parity check parsed `climate_model_gui.build_cli_command(DEFAULTS)` through the canonical CLI parser and `config_from_args`, then compared the resulting dataclass against `ModelConfig()`. Twelve total differences were found: ten physical parameters plus the intentionally GUI-selected `scenario=ssp245` and `duration_years=250`. CLI zero-argument parity was 285/285 fields.

## Recommended immediate order after this audit

1. Repair scientific-validation semantics without changing physics: remove extent and retrospective historical skill from the independent prospective release conjunction, add an explicit `not_available` prospective state, and retain compatibility aliases where required.
2. Repair desktop GUI default parity and add exhaustive regression coverage.
3. Deprecate/remove the dead `amoc_pycnocline_relaxation_years` control from active user/Monte-Carlo surfaces without changing equations.
4. Acquire/process NSIDC-0611 v4 using the existing official acquisition path and provenance rules.
5. Diagnose CryoSat-2 observation/operator alignment before touching thickness physics.
6. Then start the first actual physics branch: AMOC water-mass-consistent density geometry, followed by reduced TEOS-10 sensitivity.
7. Greenland compensation is also a confirmed physics defect and should be repaired with explicit land-ice mass/freshwater treatment, followed by the dedicated user-run conservation/coupling suite.

No process is running after this audit.

## C. Additional release-integrity finding discovered during the audit

### C1. Seven frozen validation CSVs were packaged with LF bytes while provenance recorded CRLF hashes

This is a **current source-package integrity defect**, not a numerical-physics defect. The untouched v2.29.28 source archive stores seven processed validation CSVs with LF line endings, while the frozen metadata records SHA-256 values for the same text serialized with CRLF. Re-encoding LF -> CRLF reproduces every recorded historical hash exactly; no numerical/text values change.

Affected files:

- `data/validation/sea_ice_fixed_mask/N_03_fixed_mask.csv`
- `data/validation/sea_ice_fixed_mask/N_09_fixed_mask.csv`
- `data/validation/sea_ice_physical/piomas_volume_monthly.csv`
- `data/validation/sea_ice_physical/cryosat2_rdeft4_monthly.csv`
- `data/validation/sea_ice_physical/icesat2_is2sitmogr4_monthly.csv`
- `data/validation/sea_ice_crosscheck/osi_saf_osi450a1/N_03_fixed_mask_crosscheck.csv`
- `data/validation/sea_ice_crosscheck/osi_saf_osi450a1/N_09_fixed_mask_crosscheck.csv`

Recommended/current candidate repair: restore the seven files to the provenance-bound CRLF byte representation and mark those exact frozen paths `-text` in `.gitattributes`, rather than rewriting historical metadata to match accidentally normalized package bytes.

Numerical rerun required: **no**. Re-run byte-integrity/release-finalization tests only.

## D. Non-physics validation-cleanup candidate status

The candidate created from this audit intentionally leaves the validated R13 climate dynamics unchanged. Its current changes are:

1. Remove coarse two-sector extent and retrospective temporal skill from the current engineering/physics prerequisite conjunction; preserve them as diagnostics.
2. Represent independent predictive scientific validation as `not_available` / incomplete until prospective evidence exists, while keeping `scientific_release_passed` as a backwards-compatible alias.
3. Repair desktop-GUI physical-default drift by sourcing physical defaults from `ModelConfig`.
4. Remove the dead `amoc_pycnocline_relaxation_years` setting from active desktop/Streamlit/Monte-Carlo controls while preserving hidden backwards-compatible CLI/config parsing.
5. Explicitly classify CryoSat/ICESat exact interannual temporal correlation as a retrospective development diagnostic and non-release-blocking; do not claim that the legacy full temporal-validation field passes.
6. Restore the seven frozen observational CSVs to their historical provenance-bound CRLF bytes and make Git preserve those bytes.
7. Add regression tests for validation semantics and interface parity.

Static/dynamics check: candidate `climate_model.py` is AST-identical to the R13 file when the deliberately changed CLI parser is excluded. No AMOC, Arctic, Greenland, EBM, radiation, ocean-heat, or sea-ice evolution equation has been altered by this candidate.

Lightweight tests completed successfully before packaging:

- validation semantics/interface parity
- GUI startup
- coupled fail-closed validation behavior
- v2.29.28 release finalization
- 2026 Arctic scientific-review fixes
- v2.29.23 engineering corrections (excluding the known slow packaging-runtime smoke)
- six-source Arctic acquisition tests
- core-five nonblocking acquisition tests

No expensive climate integration was run by the assistant.
