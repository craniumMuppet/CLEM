# CLEM v2.29.28 R18.3 final release audit

## Bottom line

R18.3 is a **release/validation-semantics maintenance revision only**. The four governing/observation modules used by R18.2 are byte-identical, so no climate integration needs to be repeated. The R18.2 area-operator result removes the main rationale for another sea-ice retune. Remaining limitations are external/future evidence rather than repairable physics defects.

## Governing-source equivalence

| File | SHA-256 | R18.2 -> R18.3 |
|---|---|---|
| `climate_model.py` | `e1553c1baccd7a90974f7879dd664a8a4b447adec5bd93407bbc5dd0e2c9bd90` | byte-identical |
| `sea_ice_observation.py` | `ae630ba91d8eaf194c892b0a83c1b5286c354355c260daff47e7053d80f63d95` | byte-identical |
| `arctic_observation_operator.py` | `28d37a9505d9387434fd5a1157923b8eeed56a253600f2783e6bb31c53e421ba` | byte-identical |
| `sea_ice_validation.py` | `9ab60121dd17e305be548fed63541b505960e3f9d96468b7a152fff53289b05a` | byte-identical |

## R18.2 sea-ice disposition

| Resolution | Month | 15% area bias (M km2) | RMSE | Correlation | Model trend (M km2/dec) | Observed trend |
|---|---:|---:|---:|---:|---:|---:|
| 10 deg | March | +0.240 | 0.488 | 0.844 | -0.554 | -0.380 |
| 5 deg | March | +0.355 | 0.451 | 0.872 | -0.388 | -0.380 |
| 10 deg | September | -0.152 | 0.560 | 0.903 | -0.913 | -0.793 |
| 5 deg | September | -0.055 | 0.518 | 0.900 | -0.830 | -0.793 |

The previous large positive area-bias interpretation was an operator mismatch. Literal native-cell >=15% extent is still unsuitable at CLEM spatial resolution; the fractional-support extent diagnostic remains the reduced-order footprint quantity and is non-release-blocking.

## Original-review checklist reconciliation

| Original issue | Current status | Current evidence / source location | Scientific interpretation | Action |
|---|---|---|---|---|
| Scientific-release Boolean / contradictory gates | REPAIRED | combine_v22923_validation.py:279; sea_ice_validation.py:1660 | Extent and retrospective temporal skill are non-blocking. R18.3 additionally requires a *passed* prospective result plus current prerequisites. | Keep. No numerical rerun. |
| Sea-ice spatial extent representation | RESOLVED AS REDUCED-ORDER DIAGNOSTIC | R17/R18 support state; R18_2_RESULTS_REVIEW.md | Fractional support adds a conserved/mass-neutral geometric degree of freedom. Literal native-cell 15% extent remains resolution-limited. | Keep support diagnostic; do not claim satellite-resolution extent. No rerun. |
| NSIDC-0611 v4 sea-ice age | EXTERNAL DATA PENDING | arctic_validation_stack.py:119 | Acquisition/provenance tooling exists, but authentic processed files are absent. | Leave not_available until Earthdata-authenticated data + hashes are supplied. No physics change. |
| CryoSat-2 temporal thickness behavior | DIAGNOSED / NON-BLOCKING LIMITATION | R15_IMPLEMENTATION_AND_LOCAL_VALIDATION.md:25; sea_ice_validation.py | Operator/month/footprint handling was audited; mean-state constraints pass but retrospective temporal correlation remains poor (~-0.123 at 10 deg). | Do not tune thickness physics to the short inspected record. |
| AMOC density water-mass geometry | REPAIRED / STRUCTURAL ALTERNATIVE RETAINED | climate_model.py:569; R15_IMPLEMENTATION_AND_LOCAL_VALIDATION.md | Production geometry uses coherent high-latitude source/sink formulation; alternatives retained for attribution. | Keep validated default; no baseline offset tuning. |
| Reduced TEOS-10 EOS | IMPLEMENTED / SENSITIVITY ONLY | climate_model.py:575; R17_RESULTS_REVIEW.md | Matched-pathway TEOS branch isolates EOS sensitivity and is materially less AMOC-sensitive than production linear closure. | Keep linear default and TEOS as structural sensitivity. |
| AMOC structural uncertainty / hysteresis | MAPPED | climate_model.py:645; R18_RESULTS_REVIEW.md | Density exponent, pycnocline coupling, saturation, reversal and recovery branches were tested. R18 fixed-point diagnosis supports genuine bistability/separator. | Do not add restart trigger or retune coefficients. |
| Greenland freshwater compensation | REPAIRED | climate_model.py:767; R16_RESULTS_REVIEW.md | Land-ice loss is uncompensated ocean mass addition with salt conservation; artificial hosing remains selectable compensated/uncompensated. | Keep. No rerun. |
| Greenland elevation feedback | IMPLEMENTED | climate_model.py:770 | Thinning/lowering feedback is active and ablatable. | Keep; lower-priority multi-century uncertainty remains explicit. |
| Dead AMOC parameters | REPAIRED AS HIDDEN COMPATIBILITY | parameter_activity_r16.py:9 | Legacy no-op parameters remain parseable only for compatibility and are excluded from active UI/Monte Carlo surfaces. | Keep compatibility path; no numerical rerun. |
| Arctic empirical mechanism double-counting | MECHANISM-TESTED | climate_model.py:439/440/441; R16_RESULTS_REVIEW.md | Independent switches and user-local ablations demonstrate active, near-additive contributions. | Keep terms; no arbitrary retune. |
| Core/CLI/GUI default drift | REPAIRED / REGRESSION-GUARDED | tests/test_v22928_validation_semantics_and_interface_parity.py; verify_physics_local.py | CLI defaults match ModelConfig; desktop GUI has no physical default drift; dead controls are hidden. | Keep regression tests. |
| Prospective evaluator | REPAIRED / EVIDENCE-DRIVEN | prospective_validation_r16.py:19; validation/prospective/CLEM_R16_PROSPECTIVE_PROTOCOL.json | Status is not_available until exact 2027-2036 evidence exists; R18.3 separates complete from passed. | Wait for future observations; never manually flip a Boolean. |
| Prospective preregistration | COMPLETE | validation/prospective/CLEM_R16_PROSPECTIVE_PROTOCOL.json | Frozen years, variables, sources, operators, baselines, hashes and decision rule are recorded. | Any post-freeze model/protocol change invalidates holdout for that changed candidate. |
| Active model/package identity | REPAIRED | tools/v22928_release_integrity.py:12; run_gui.bat; launch_gui.pyw | Current package root is CLEM-v2.29.28-source and active GUI bootstrap/error surfaces use CLEM. Historical provenance is left untouched. | Keep historical old-name artifacts as provenance only. |
| R18.2 residual sea-ice area concern | RESOLVED | R18_2_RESULTS_REVIEW.md | Correct 15% area operator reduces mean-state biases to small values; 5 deg Sep bias is -0.055 M km2 and trend is close to observed. | Freeze sea-ice physics; no further candidate justified. |

## Scientific-release state

- Engineering/physics verification: **passing** in the version-matched v2.29.28 evidence plus R15-R18.2 follow-up runs.
- NSIDC-0611 v4 structural diagnostic: **not available** (external authenticated data absent).
- Frozen independent prospective period: **2027-2036**, evaluate only once the complete preregistered evidence exists.
- Independent predictive scientific validation: **not_available**, not failed.
- `scientific_release_passed`: **false** until a future frozen prospective evaluation actually **passes** and current prerequisites remain satisfied.
- Extent and retrospective temporal-skill diagnostics do **not** enter that conjunction.

## R18.3 release-side repairs

1. Fixed the prospective pass/complete semantic bug: a completed-but-failed holdout can no longer set `scientific_release_passed=true`.
2. Bound scientific release to both current engineering/physics prerequisites and a passed frozen prospective result.
3. Updated the current v2.29.28 finalizer to call the evidence-driven prospective evaluator instead of reading the historical hard-coded prospective Boolean.
4. Changed the active v2.29.28 package identity to `CLEM-v2.29.28-source`.
5. Corrected active Windows GUI bootstrap/error branding to CLEM.
6. Updated `RELEASE_METADATA.json` to the current R18.3 source/validation state.

## Verification performed in R18.3

- Parsed 244 Python files: **0 parse failures**.
- `check_release_identity.py`: **PASS**.
- `verify_physics_local.py --worker-mode static`: **PASS**; zero climate years advanced.
- Targeted release/semantics/setup tests: **55 passed, 0 failed**.
- Governing files remain byte-identical to R18.2.
- This assistant runtime has pytest **9.0.2**, while the historical canonical v2.29.28 release-evidence runner declares pytest **9.1.1**. I therefore did **not** regenerate or falsify canonical `TEST_RESULTS_V2_29_28` evidence; R18.3 records fresh targeted/static evidence separately.

## Final disposition

Freeze the current R18 physics. Do not rerun AMOC, TEOS, sea ice, Greenland, or the full validation suite for R18.3. The next scientifically meaningful events are acquisition of authentic NSIDC-0611 v4 data, if desired for the structural age diagnostic, and eventual execution of the frozen 2027-2036 prospective evaluation when the observations actually exist.
