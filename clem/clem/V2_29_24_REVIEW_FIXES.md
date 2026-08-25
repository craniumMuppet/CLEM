# v2.29.24 review fixes

This version addresses the seven issues found in the review of the v2.29.23 sea-ice-fix derivative. The changes below are active model/engineering changes, not diagnostic-only additions.

## 1. Separate local thickness geometry from latent-energy storage

The former 4.5 m parameter was used simultaneously as a local unresolved-pack thickness bound and as a maximum grid-equivalent latent-energy reservoir. v2.29.24 separates these concepts:

- `arctic_max_equivalent_thickness_m = 8.0` is an emergency grid-equivalent latent-energy storage safeguard.
- `arctic_max_local_ice_thickness_m = 12.0` is an independent emergency local floe/ridge geometry safeguard.
- A regression constructs a 6 m grid-equivalent latent reservoir and verifies that the 12 m local geometry safeguard does not clip or transfer that latent energy.
- `arctic_ice_area_thick_pack_resistance_exponent = 4.0` smoothly suppresses anomaly-only fixed-volume area retreat when surviving floes are thicker than the periodic-control pack. This removes the mechanism that concentrated remaining volume into a cap-driven thick remnant.

Final September 2100 safeguard contact is negligible for SSP2-4.5: 0% of represented ice area at 5° and about 0.0005% at 10°. Under SSP5-8.5 it is about 1.20% at 5° and 0% at 10°, while the area-weighted mean local thickness remains about 2.85–3.06 m. The bulk future pack is therefore not controlled by the 12 m safeguard.

## 2. Increase the historical September-skill margin

The final v2.29.24 production-timestep validation gives:

| Resolution | September skill vs persistence | September skill vs expanding trend | 2021–2025 September RMSE | March skill vs persistence | March skill vs trend |
|---|---:|---:|---:|---:|---:|
| 5° | +0.1148 | +0.0884 | 0.2232 million km² | +0.1129 | +0.1972 |
| 10° | +0.1623 | +0.1374 | 0.2657 million km² | +0.1273 | +0.2102 |

The rolling historical evaluation remains explicitly labelled as development-informed rather than prospective independent validation. The important regression criterion here is that the model now beats both simple September baselines at both supported resolutions with materially larger margins than the reviewed v2.29.23 derivative.

## 3. Remove hidden phase-restoring calibration constants

The depleted-pack restoring controls are explicit `ModelConfig` parameters:

- `arctic_phase_restoring_deficit_saturation_fraction = 0.14` controls the saturation transition scale.
- `arctic_phase_restoring_max_deficit_flux_wm2 = 2.5` independently limits maximum reverse cooling/regrowth flux before the Arctic blend factor.

Both are validated, exposed in the CLI, Streamlit and desktop GUI, described in setting metadata, and included in Monte Carlo priors. Separating the transition scale from the maximum flux avoids the review regression in which changing the saturation scale silently increased the physical maximum restoring flux.

## 4. Complete interface parity for new Arctic controls

The warming-driven ocean-convergence onset and all other v2.29.24 Arctic controls are exposed consistently through:

- `ModelConfig`;
- command-line arguments;
- Streamlit controls;
- desktop GUI defaults and command construction;
- setting metadata/tooltips;
- Monte Carlo physical-parameter priors.

Focused parity and GUI-startup regressions pass.

## 5. Give the changed physical model a unique version

The physical model and package metadata now identify as `2.29.24`. Historical evidence whose filenames contain `V2_29_23` is retained only as historical baseline material and is not presented as current v2.29.24 validation. The stale generic `REVIEW_CORRECTED_STATUS.json` from v2.29.23 is not carried forward as current evidence.

## 6. Correct canonical test accounting

Six calibration wrappers that explicitly run very long equilibrium calculations are marked `slow`. The two GUI legacy-entrypoint wrappers remain in normal coverage. `run_tests.py --fast` selects the repository's actual `not slow` suite rather than excluding a whole legacy-entrypoint file.

Final canonical result:

- 375 tests collected;
- 323 non-slow tests selected;
- 323 passed;
- 0 failed;
- 0 errors;
- 52 correctly deselected slow tests;
- 2 expected deprecation warnings;
- runtime: 1065.01 s.

See `TEST_RESULTS_V2_29_24.json` and `TEST_RESULTS_V2_29_24.txt`.

## 7. Restore the stronger conservation mutation

The conservation regression again mutates the production implementation by suppressing the actual Arctic mixed-layer receiving reservoir. The process-ledger gate must detect that missing receiver. The weaker post-hoc ledger-corruption replacement is no longer used as the primary mutation test.

## Final future scenario checks

September Northern Hemisphere sea-ice area in 2100 is strictly ordered with forcing at both resolutions:

| Scenario | 5° | 10° |
|---|---:|---:|
| SSP1-2.6 | 2.3646 million km² | 2.2516 million km² |
| SSP2-4.5 | 1.5164 million km² | 1.4127 million km² |
| SSP4-6.0 | 1.2041 million km² | 1.1406 million km² |
| SSP5-8.5 | 0.5952 million km² | 0.5559 million km² |

The 200-year unforced runs remain stable at numerical-roundoff scale. March/September area drift is approximately 2–3 × 10^-10 million km², and GMST/TOA anomalies remain around 10^-15 in their native units.

Machine-readable evidence is in `VALIDATION_SUMMARY_V2_29_24.json` and `validation/v22924/`.
