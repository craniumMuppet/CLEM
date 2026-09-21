# EGCM v2.29.21 engineering corrections

## Classification

v2.29.21 is an **engineering-only** build. Scientific release remains disabled because no prospective untouched temporal validation is yet available, regardless of retrospective gate results.

## Output-generation correction

`SimulationResult.near_surface_air_map_at_index()` requires the latitude-dependent Arctic module blend. v2.29.20 kept that array only on `ProcessClimateModel`, so `save_outputs()` could raise `AttributeError` after simulation completion. v2.29.21 adds `arctic_module_blend` to `SimulationResult` and copies the model array into every returned result.

Regression coverage exercises both formerly failing output representations and a direct CLI smoke run that writes the normal NPZ, CSV, plot, configuration, summary, and timeseries outputs.

## Low-volume sea-ice correction

The rejected mapping used a transition scale of `arctic_new_ice_local_thickness_m * 1e-4`. With the 0.25 m default, the young-ice branch was effectively exhausted after 0.025 mm of equivalent ice. At physically relevant low volumes, the model reverted to a compact-pack curve with local thickness near the 8 m numerical ceiling.

v2.29.21 adds a bounded monotonic correction to the compact-pack relation:

- its zero-volume slope gives `equivalent thickness / concentration -> young-ice thickness`;
- its dimensionless cap is the configured young/full thickness ratio;
- it cannot produce a non-monotonic concentration curve;
- its influence decreases relative to the compact-pack relation as mature cover develops;
- full cover is still reached only at the configured full-cover equivalent thickness.

The mature compact-pack exponent is recalibrated from 0.50 to 0.40 against the unchanged historical and 2021–2025 validation gates. No threshold was changed.

With production defaults:

| Equivalent thickness | Concentration | Diagnosed local thickness |
|---:|---:|---:|
| 0.000001 m | 0.0000040 | 0.250001 m |
| 0.0001 m | 0.0003998 | 0.250101 m |
| 0.001 m | 0.0039795 | 0.251291 m |
| 0.01 m | 0.0344281 | 0.290461 m |
| 0.10 m | 0.0683064 | 1.463991 m |

A cold, dark, fixed-volume 0.01 m experiment finishes one simulated year at approximately 0.290 m local thickness. The former experiment exceeded 6 m.

## Process-budget conservation

The former `equivalent / concentration` followed by multiplication by concentration was an algebraic representation identity, not a process-conservation test. It is no longer a release gate.

The v2.29.21 structural validator independently checks:

- equivalent-thickness budgets during formation and melt;
- unchanged latent energy while ridging and divergence alter area;
- volume loss calculated independently from mechanical export flux;
- enthalpy conservation during freezing and over-melt phase normalization;
- enthalpy conservation when open-water contraction transfers sensible heat to the coupled ocean;
- ordinary `ProcessClimateModel.step()` loss and ice-free recovery paths.

The representation identity remains reported only to detect zero-area/nonzero-volume inconsistencies.

## Self-contained validation workflow

`run_v22921_engineering_tests.py` executes the complete repository-defined non-slow suite and writes `TEST_RESULTS_V2_29_21.json` and `.txt` in the selected output directory. `combine_v22921_validation.py` resolves that JSON automatically unless an explicit `--test-results` path is supplied.

## Fingerprint coverage

The version-matched validation fingerprint covers:

- the model, validator, combiner, sea-ice evaluation, segmentation, and evidence modules;
- runtime provenance and trusted validation-pickle handling;
- AMOC continuation implementation;
- external benchmark definitions and NSIDC inputs;
- packaged NOAA OISST acquisition and processing scripts.

The archive manifest separately hashes every packaged file.

## Documentation and compatibility

Primary documentation and metadata use v2.29.21. Former v2.29.20 reports are retained only as explicit superseded-lineage notices. Compatibility entry points named `validate_v22920.py` and `combine_v22920_validation.py` delegate to the v2.29.21 implementation and do not recreate v2.29.20 evidence.


## Regression modernization

Retained regressions now follow the v2.29.21 state definitions rather than freezing superseded releases. In particular:

- saved winter fields are reconstructed from independent prognostic concentration plus latent-volume energy, not from the retired energy-to-area diagnostic;
- current default locks identify the actual v2.29.21 calibrated controls;
- archived v2.29.16 evidence is checked for internal consistency rather than falsely required to identify as a later release;
- the strict short abrupt-2x heat-budget closure test isolates the core land/ocean reservoirs. With the seasonal Arctic module enabled, `toa_imbalance_wm2` is a radiative diagnostic (bulk TOA plus the Arctic external-surface anomaly), not a complete boundary budget for the additional reference-manifold, export, and transition terms. The Arctic radiative addition is tested separately and exactly.

## Remaining scientific limitations

Extent remains multiplier-derived. OISST and Greenland magnitude checks remain tuning-informed or post-hoc sanity checks. Historical and 2021–2025 sea-ice observations are retrospective development evidence, not independent prospective validation. The positive September temporal-skill criterion is not satisfied, and no prospective untouched temporal validation is available. The package therefore remains `engineering_only`.


## Final verification

The frozen v2.29.21 tree completed the complete repository-defined non-slow inventory with **320/320 tests passed**, **0 failed**, and **0 skipped**. Two failures found during isolated shard execution were corrected and rerun on the final tree: missing GUI tooltip metadata and a stale regression expectation for the superseded 0.50 compactness exponent.

Complete 1850–2100 SSP2-4.5 production and matched no-Greenland-freshwater trajectories were regenerated at both **5°** and **10°** resolution. At both resolutions, historical calibration, 2021–2025 evaluation, structural process budgets, and coupled Arctic/Greenland/AMOC checks passed. Cross-resolution validation passed. All four validation JSON files verify the same **18/18 scientific source fingerprints** against the packaged tree.

A direct final-tree CLI simulation exited successfully and wrote the normal field, map, plot, configuration, summary, and timeseries outputs, confirming that the former post-simulation output-generation crash is resolved.

The combined evidence keeps `release_classification` at `engineering_only` and `scientific_release_passed` at `false`. Multiplier-derived extent is not independent validation, the positive September temporal-skill criterion remains unsatisfied, and prospective untouched validation is unavailable.
