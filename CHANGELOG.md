# Changelog

## Unreleased

### AMOC seawater-density physics

- Promoted matched-pathway TEOS-10/GSW seawater density to the production AMOC
  closure. This changes the equation of state on the established North Atlantic
  stratification pathway; the fixed-alpha/beta and literal prognostic-water-mass
  branches remain structural sensitivities.
- Kept the preindustrial AMOC control at 17 Sv and retained the same thermal
  pathway, water-mass geometry, initial salinities, and hydraulic coefficients;
  no AMOC output offset or RAPID-period calibration term was added.
- At the production 0.05-year integration step, the 2004–2020 mean increases
  from the released ~14.17/~14.32 Sv at 10°/5° to ~15.74/~15.86 Sv, within
  the 16.9 ± 1.2 Sv RAPID comparison interval. Salt conservation remains at
  roundoff.
- Declared `gsw` as a normal runtime dependency and added regression coverage
  for exact control-state normalization and selected-EOS density-margin
  screening.
- Rejected literal prognostic-water-mass TEOS, South-Atlantic-upper geometry,
  canonical-hydraulic, and idealized aerosol-pattern candidates because
  independent SSP/hosing checks failed or the forcing pattern lacked an
  independent spatial constraint. Documented the retained closure's weaker
  SSP2-4.5 and hosing response as an open limitation.

### All-SSP batch execution

- Added sequential, resumable one-click/CLI execution of SSP1-2.6, SSP2-4.5,
  SSP4-6.0, and SSP5-8.5 with shared settings and per-scenario output folders.
- Added combined global near-surface-air temperature, AMOC, FovS, and Northern
  Hemisphere sea-ice area/extent CSVs and comparison figures, plus a long-form
  combined CSV containing every normal time-series field for all four SSPs.
- Preserved the complete ordinary output set in each scenario subfolder and
  added a Northern Hemisphere sea-ice area/extent time-series figure to normal
  deterministic output.

## 2.29.29 — 2026-09-01

CLEM v2.29.29 is the public release of the physics-repair and validation work carried out after the v2.29.28-r13 baseline. The version bump itself does not retune the final governing equations; the numerical evidence produced during the repair line remains recorded under the v2.29.28 version that actually generated it.

### Greenland freshwater and salt conservation

- Changed Greenland land-ice loss from a zero-net compensated redistribution to an **uncompensated freshwater/mass addition to the represented ocean** by default. Ocean volume now increases with realized land-ice melt, salinity dilutes consistently, and physical salt mass is conserved.
- Propagated represented ocean volume through checkpoints/restarts so the freshwater-mass correction survives resumable integrations.
- Kept hydrological redistribution separate from land-ice mass addition, and made artificial freshwater hosing independently selectable as compensated or uncompensated for attribution experiments.
- Added a switchable Greenland surface-elevation feedback: thinning lowers the ice surface, increases local temperature through the lapse rate, and feeds back on PDD melt. Validation showed the effect is active but modest over the tested interval.

### AMOC physics and structural uncertainty

- Audited the hydraulic density geometry. A proposed North Atlantic versus **South-Atlantic upper-limb** default was tested and rejected: it made SSP2-4.5 AMOC strengthen slightly and made 0.1-0.3 Sv hosing far too weak. The production default therefore remains the validated **interhemispheric high-latitude density contrast**; the South-Atlantic-upper construction is retained only as an explicit structural-sensitivity branch.
- Added explicit structural AMOC controls for the density-transport exponent, pycnocline feedback strength, strong-state hydraulic saturation, and circulation reversal. The validation matrix now forces each branch into a regime where it actually changes the solution instead of merely checking dormant parameters.
- Added a reduced **TEOS-10/GSW density sensitivity** and fixed its geometry-specific coordinate/setup handling. A matched-pathway TEOS branch was then added so the nonlinear EOS can be compared without simultaneously changing the validated thermal-density pathway. TEOS remained substantially less sensitive to freshwater forcing than the validated linear alpha/beta closure, so the linear EOS remains the production default.
- Extended collapse/recovery experiments from simple collapse tests to a de-hosing map. Stronger recovery forcing can lift the reduced AMOC toward the intermediate branch, but removing the perturbation causes relapse when the state remains below the zero-hosing basin separator.
- Added an equilibrium diagnosis of the unchanged production AMOC subsystem. The reduced model contains a stable weak state, an unstable intermediate separator near **12.32 Sv**, and the stable **17 Sv** strong state; enabling reversal changes the weak attractor to a reversed branch rather than creating the bistability. No Boolean restart threshold or forced recovery term was added.

### Arctic mechanisms and parameter activity

- Made forced Arctic-ocean heat convergence, phase/seasonal restoring, and the extra unresolved lapse-rate feedback independently switchable and added explicit ablation experiments for each mechanism.
- The ablations confirmed that all three terms are dynamically active; the extra lapse-rate term had the largest isolated effect in the tested step-forcing experiment, while heat convergence was smaller and phase restoring acted as a damping contribution.
- Added parameter-activity auditing so compatibility-only/dead controls remain loadable for old configurations but are hidden from active priors/user controls when they no longer affect the equations.
- Classified `atlantic_gyre_heat_transport_pw` as diagnostic-only: it remains available for RAPID total-heat-transport scoring but does not drive climate tendencies.

### Sea-ice spatial representation and observation operator

- Replaced the earlier all-or-nothing coarse-cell extent treatment with an **unfitted conservative subgrid reconstruction** as an intermediate diagnostic. Validation showed that CLEM's two-sector concentration field is still too spatially diffuse for a credible satellite-style threshold-extent claim, so no empirical area-to-extent multiplier was fitted.
- Added a **mass-neutral prognostic sea-ice support fraction** for the unresolved ice footprint. Native prognostic concentration and latent-energy ice volume remain authoritative; support evolves from the existing formation, melt, divergence, compaction and mechanical-spreading process ledger and cannot create ice mass.
- Replaced the fixed 80% support compactness reference with a thermodynamic pack reference: the 80% pack/MIZ boundary remains the warm limit while cold pack approaches full support using the existing freezing and formation-temperature scales.
- Corrected the fixed-mask operator so **area** integrates native concentration while structural **extent** integrates fractional support occupancy.
- Corrected the NSIDC-style comparator to apply the **15% native-cell concentration threshold to both area and literal threshold extent**, and changed March/September sampling to the model record nearest the established mid-month target.
- The corrected R18.2 comparison showed that the previously inferred large sea-ice-area bias was mainly an observation-operator mismatch. Across 5°/10° March/September runs, corrected area RMSE is about **0.45-0.56 million km²** with correlations about **0.84-0.90**.
- Literal >=15% threshold extent on CLEM's coarse reconstructed cells remains resolution-limited and is **not** treated as satellite-resolution validation or a release gate. The fractional-support footprint remains the reduced-order structural extent diagnostic.

### Observational validation

- Integrated authentic **NSIDC-0611 EASE-Grid Sea Ice Age v4/v4.1** data for **1984-2024**: 41 annual NetCDF files, no missing years, processed with CLEM's existing definition into 82 March/September multiyear-ice records.
- Recorded SHA-256 provenance for all 41 original NSIDC files and packaged the processed diagnostic plus metadata; the raw NetCDF files are not redistributed.
- This completes the intended Arctic observational stack at **6/6 available sources**. The multiyear-ice comparison remains a structural diagnostic because observed age class and CLEM's thickness-based mature-ice fraction are related but not identical quantities.
- Retained the CryoSat-2 temporal-thickness result as an incomplete retrospective diagnostic rather than retuning thickness physics to force agreement with the short record.

### Validation and release logic

- Replaced manually satisfiable prospective-validation flags with an **evidence-driven evaluator** and froze the **2027-2036** prospective protocol. Until those genuinely future observations exist, the correct status is `not_available`, not failed and not passed.
- Fixed scientific-release logic so merely completing a future prospective evaluation cannot count as a pass if that evaluation fails.
- Kept the low-resolution sea-ice extent diagnostic non-release-blocking and separated retrospective/development-informed evidence from genuinely independent predictive validation.
- Fixed the R18 post-run finalizer error where the verifier called an undefined `ols()` helper after the numerical integrations had already completed.
- Added bounded, restartable local validation workflows with a maximum of **5 model years per child process**, checkpoint/source fingerprints, stale-process protection and resumable experiment state.

### Public release

- Merged the public README/reference work onto the validated repair tree and added `THIRD_PARTY_DATA.md` with dataset-specific attribution, including NSIDC-0611 and its U.S. Government Works metadata.
- Updated active runtime, package, GUI, CI, launcher, validator and release-tool identity to **CLEM v2.29.29**.
- Historical v2.29.28 numerical files and embedded version labels are intentionally retained under their true generation version. `V2_29_29_DYNAMICS_EQUIVALENCE.json` documents that the final v2.29.29 governing dynamics differ from the validated parent only by the active version identity.
- Independent prospective predictive validation is **not claimed** in this release; the preregistered future holdout cannot be evaluated yet.

### Release hardening and asset correction

- Corrected the public release layout to explicitly ship the clean v2.29.29 source and the large historical numerical-validation bundles as separate assets. The original Repair R11-R13 evidence bundle is 80,553,730 bytes and remains under its true v2.29.28 generation name; the R18.2 sea-ice operator evidence is likewise a separate historical asset.
- Updated stale legacy regression assertions that still encoded superseded AMOC/Greenland defaults, without changing the validated production physics.
- Updated R18/R18.2 source-provenance checks to use the documented version-neutral dynamics-equivalence rule for the `MODEL_VERSION`-only v2.29.29 identity change.
- Clarified current-versus-historical fingerprint/version documentation and removed transient test/bytecode caches from the public source package.
- Re-ran bounded post-merge release checks: 54 tests passed across current release semantics, fail-closed coupling, stale-default/provenance repairs, six-source Arctic handling and target/baseline safety; release identity and zero-year static physics checks also pass. The canonical `pytest==9.1.1` runner remains unclaimed in the assistant environment because only pytest 9.0.2 is available offline.

## Internal repair history (v2.29.28 R15-R18.5.1)

## R18.5 public-release merge - 2026-09-01

- No governing physics or observation-operator change from R18.4.
- Merged the user repository's post-R13 public README expansion and `THIRD_PARTY_DATA.md` attribution/citation document onto the validated R18.4 tree.
- Updated public README sea-ice metrics and validation wording to the completed R18.2/R18.4 evidence state rather than reverting to older R13-era Arctic operator numbers.
- Synchronized active release metadata, public validation summary, and model-limitations documentation.
- Removed one generated `__pycache__` bytecode artifact from the packaged source tree.
- No climate integration rerun is required.

## R18.4 NSIDC-0611 observational integration - 2026-09-01

- Integrated authentic NSIDC-0611 v4/v4.1 annual EASE-Grid Sea Ice Age inputs for 1984-2024.
- Generated March/September multiyear-ice structural diagnostics and recorded SHA-256 provenance for all 41 annual source files.
- Completed the intended Arctic observational stack at 6/6 products.
- Kept the NSIDC-0611 diagnostic structural/non-release-blocking and preserved the frozen 2027-2036 prospective holdout as `not_available`.
- No governing physics change and no climate integration rerun required.

## R18.3 release finalization - 2026-09-01

- No governing physics change; `climate_model.py`, `sea_ice_observation.py`, `arctic_observation_operator.py`, and `sea_ice_validation.py` remain byte-identical to the numerically evaluated R18.2 candidate.
- Records the completed R18.2 sea-ice result review: corrected 15% cell-threshold area no longer shows the previously inferred large mean-state bias, so no additional sea-ice retune is justified.
- Keeps native 15% cell-threshold extent explicitly resolution-limited/non-release-blocking and retains fractional-support extent as the reduced-order structural footprint diagnostic.
- Fixes the active v2.29.28 package root/name to `CLEM-v2.29.28-source`.
- Fixes prospective release logic so scientific release requires both current engineering/physics prerequisites and a **passed** frozen prospective evaluation; merely completing a failed future evaluation can never set the scientific release pass flag.
- Updates the current v2.29.28 finalizer to consume the evidence-driven frozen prospective evaluator instead of the historical hard-coded prospective Boolean.
- No user-local numerical rerun is required.

## R18.2 observation-operator hotfix — 2026-09-01

- Leaves `climate_model.py`, sea-ice physics, and AMOC physics byte-identical to R18.1.
- Separates the NSIDC-compatible `concentration >= 0.15` native-cell area/extent comparator from the R18 fractional-support structural diagnostic.
- Scores March and September at the nearest native 0.05-year model record to the established mid-month target rather than reconstructing months from coarse summary boundaries.
- Restricts local rerun scope to two historical sea-ice evaluation branches (10° and 5°); no TEOS, AMOC recovery, or future branch is repeated.
- Preserves the <=5-model-year resumable child-process protocol and exact R18.1 parent provenance.

## R18 physics candidate — 2026-09-01

- Keeps CLEM runtime version 2.29.28 and the validated linear/high-latitude AMOC default unchanged.
- Replaces R17's fixed 80% control-orbit support compactness with an unfitted thermodynamic reference: 80% remains the warm MIZ/pack boundary while cold pack approaches 100%, using the existing freezing temperature and ice-formation temperature scale.
- Keeps the support state geometric/mass-neutral: native prognostic concentration and latent ice volume remain authoritative.
- Fixes the scientific fixed-mask operator so extent integrates fractional prognostic support occupancy while area integrates native concentration; legacy results without support retain the old threshold fallback.
- Corrects validation metadata to describe the separate coarse support geometry without claiming satellite-resolution or independent predictive validation.
- Retains R17 matched-TEOS results as structural sensitivity evidence and does not rerun or promote TEOS; linear remains the production EOS.
- Extends the AMOC recovery map from one shared +0.8 Sv collapsed checkpoint to -0.25/-0.30/-0.35/-0.40 Sv de-hosing branches and a zero-hosing persistence hold after the -0.40 branch. No restart threshold is added.
- Adds exact monthly packaged NSIDC fixed-mask area/extent diagnostics and 1979-2024 March/September metrics to the local R18 result bundle.
- Numerical acceptance of the new R18 sea-ice/recovery changes remains pending the user-run R18 result bundle.

## R17 physics candidate — 2026-08-31

- Keeps CLEM runtime version 2.29.28 and the validated linear/high-latitude AMOC default unchanged.
- Adds a mass-neutral prognostic Arctic sea-ice support fraction used for the 15% extent footprint while leaving prognostic ice concentration and latent-energy mass/volume equations authoritative.
- Uses the fixed 15% extent and 80% pack/MIZ concentration definitions without fitting an area-to-extent multiplier.
- Adds `teos10_matched`, which changes the nonlinear EOS while preserving the validated linear thermal-density pathway; the R16.2 direct surface-watermass TEOS formulation remains sensitivity-only.
- Adds a resumable recovery/hysteresis matrix that collapses once and branches the exact checkpoint into -0.05, -0.10, and -0.20 Sv de-hosing experiments; no restart threshold or forced recovery term is added.
- Migrates older safe checkpoints with zero support anomaly for the new mass-neutral state.
- Adds staged R17 Windows launchers and exact R16.2 parent provenance.
- Numerical acceptance of the new R17 physics remains pending the user-run R17 result bundle.

## 2.29.28 — 2026-08-21

- Restores the inherited preindustrial Arctic March/September reference-cycle bounds.
- Tightens 1979–2020 fixed-mask gates to 0.80–1.25 trend ratios plus overlapping model/observed OLS 95% trend intervals.
- Replaces unbounded warming-driven Arctic Ocean heat convergence with a smooth saturating, ice-cover-weighted conservative response.
- Adds a bounded winter formation-support floor to prevent depleted-pack refreezing runaway.
- Changes active cold-season transport, compactness, anomaly-area response, sea-ice export, surface heat loss, and bounded ocean-heat convergence defaults.
- Exact 1850-start 10° result: G02202 March/September RMSE 0.504/0.529 M km2; trend ratios 0.968/0.961 with overlapping 95% intervals; 2021–2025 RMSE 0.370/0.358.
- PIOMAS nRMSE improves to 0.1883 and ICESat-2 bias/correlation to +0.283 m/+0.692. CryoSat-2 correlation is -0.123 and explicitly keeps full temporal thickness validation incomplete.
- Adds a volume-conserving 12 m grid-cell mean local-thickness deformation/spreading constraint and scales prognostic area tendencies through the 55–66 N module transition; exact 5° and 10° SSP2-4.5 trajectories remain stable through 2100.
- Reclassifies CryoSat-2, ICESat-2, and OSI SAF as development-informed constraints/diagnostics rather than independent validation.
- Adds fail-closed current-version 5°/10° coupled validation, mandatory cross-resolution comparison, and members-first/summary-last publication whose commit record hashes every canonical member.
- Fresh 5°/10° Arctic→Greenland→AMOC runs pass all engineering and cross-resolution gates; scientific release remains false because predictive/prospective skill and CryoSat-2 temporal response remain failed or incomplete.
- Restores the broader release regression regimen and records it through one unchanged-tree pytest invocation with hashed NDJSON and JUnit evidence; the finalizer checks exact counts, exit codes, unique node IDs, raw-evidence hashes, and the test-bound tree fingerprint.
- Makes final ZIP creation transactional and verifies every archived payload against both the manifest and the test-bound fingerprint before replacing an existing release archive.
- Enforces the 12 m mechanical-spreading thickness as a strict production-state limit: a full-cover state that cannot hold the conserved volume within the limit now fails fast.
- Refreshes dependency-lock provenance and installed-content hashes for the recorded Windows / Python 3.13.13 release environment.
- Removes the invalid 1979 retrospective fold and uses a fixed prior-derived candidate grid with pre-cutoff-only fold selection for 1989/1999/2009 cutoffs. The exercise remains method-development evidence and does not authorize a predictive-skill claim.
- Fixes synthetic/missing observation-operator flags to fail closed instead of raising a KeyError.
- Keeps NSIDC-0611 and 2027+ untouched prospective validation explicitly incomplete.

## 2.29.27 — 2026-08-19

- Recalibrated Arctic young-ice geometry and surface heat loss: 0.22 m young ice, 0.60 concentration exponent, and 49.5 W/m2 nonsolar ice heat loss.
- OSI SAF September independent area RMSE improves from about 1.125 to 0.932 M km2 and now passes the 1.0 gate.
- PIOMAS common-domain volume nRMSE improves from about 0.24989 to 0.24583 while CryoSat-2 and ICESat-2 gates remain passing.
- Added retrospective fold-specific hindcast evidence; predictive skill remains fail-closed because not all folds beat all simple baselines and untouched prospective validation has not occurred.
- Added HadCRUT5 5.1.0.0 annual evidence used only for the temperature-regression hindcast baseline.
- Enforced processed observational-data hashes at runtime.
- Release finalization now verifies the tested-code fingerprint before packaging and derives scientific status from packaged evidence rather than hard-coded booleans.
- Synchronized the declared release-test dependency to `pytest==9.0.2`, the version used for the recorded verification.


## 2.29.26 — 2026-08-18 Arctic observational recalibration release

- Finalized the previously post-v2.29.25 recalibration work as release v2.29.26 and synchronized package identity, release documentation, scientific-use metadata, and current-version regression expectations.
- Integrated the corrected five-source Arctic validation stack: G02202 fixed-mask concentration/area, PIOMAS common-domain volume, CryoSat-2 thickness, ICESat-2 thickness, and OSI SAF independent area cross-check.
- Recalibrated the default Arctic area/volume geometry and ocean coupling to `new_ice=0.23 m`, `full_cover=3.70 m`, `concentration_exponent=0.50`, `basal_ocean_exchange=6.0 W m-2 K-1`, and forced-OHT onset `2.0 C`.
- Canonical 10-degree, dt=0.05 production validation now passes G02202 calibration, 2021-2025 development evaluation, PIOMAS volume, CryoSat-2 thickness, and ICESat-2 thickness gates.
- OSI SAF March passes; September remains an intentionally untuned independent miss (RMSE 1.125 million km2 versus the 1.0 gate).
- NSIDC-0611 sea-ice age and true nested fold-specific hindcast validation remain pending, so scientific predictive validation remains fail-closed.
- Updated state-dependent observation-stack tests to reflect the now-complete core five data stack.

## 2.29.25 — 2026 Arctic observation-operator correction

- Applied the G02202 permanent fixed support to both observations and EGCM; the common mask now excludes the largest historical SMMR pole-hole footprint via the v6 ancillary bitmask.
- Added reusable spatial and temporal Arctic observation operators and made operator files mandatory evidence for every spatial validation source.
- Corrected NSIDC-0611 categorical handling so land/unclassified codes cannot enter multiyear-ice statistics.
- Rebuilt CryoSat-2 and ICESat-2 thickness scoring around source-specific retrieval footprints and record-specific concentration-area weights; ICESat-2 now prefers the primary thickness field and uses its <=88°N comparison domain.
- Replaced scalar PIOMAS total-volume validation with gridded `heff` integration on an explicit common >=60°N ocean domain applied identically to EGCM.
- Kept the validation gate fail-closed when raw data required to construct the operators are unavailable.
- Added focused regression coverage for exact-support area, common-domain volume, record-specific satellite weighting, and ice-age category exclusion.

## 2.29.25

- Converted equivalent/local ice safeguards into non-corrective fail-fast numerical thresholds (20 m equivalent, 500 m local).
- Removed both safety thresholds from Monte Carlo physical/science priors.
- Removed production area remapping by the local-thickness threshold; retained only a private periodic-reference convergence regularizer.
- Added direct behavioral tests for thick-pack resistance and safeguard independence.
- Added canonical reproducible tested-input fingerprinting including release documentation inspected by tests.
- Regenerated current pytest evidence from the final v2.29.25 package path.

## 2.29.24

- Separated the grid-equivalent latent-energy safeguard (8 m) from the unresolved local ice-thickness safeguard (12 m), so a local geometry bound can no longer clip latent ice energy.
- Added a thick-pack resistance exponent (default 4.0) that smoothly suppresses anomaly-only fixed-volume area retreat when surviving floes become thicker than the periodic-control pack.
- Made the depleted-pack phase-restoring saturation an explicit validated parameter (default 0.14) and exposed it across CLI, Streamlit, desktop GUI, setting metadata, and Monte Carlo priors.
- Separated the depleted-pack saturation shape from an explicit maximum reverse phase-restoring flux (default 2.5 W/m²), preserving the established deficit-side safety bound while keeping both controls configurable and interface-visible.
- Exposed the forced Arctic ocean heat-convergence onset across the same interfaces.
- Assigned the changed physical model a unique v2.29.24 identity in source and package metadata.
- Corrected normal-suite accounting: six explicitly long calibration wrappers are marked `slow`; GUI wrappers remain in the canonical `not slow` suite.
- Restored the stronger implementation-level Arctic mixed-layer receiver mutation regression.
- Added lean production-timestep validation under `tools/validate_v22924_lean.py` and `validation/v22924/`.

## 2.29.23

### Sea-ice actual-fix derivative

- Replaced the diagnostics-only detour with active sea-ice behavior changes that make September rolling-origin skill positive against persistence and an expanding linear trend at both 5° and 10°.
- Added conservative warming-driven Arctic ocean heat convergence above a 1°C onset, with equal-and-opposite lower-latitude ocean compensation and production-ledger accounting.
- Smoothly bounded the ice-deficit side of phase restoring, reduced basal ice/ocean exchange to 10 W/m²/K, reduced area-formation volume sensitivity to 4, and set the periodic-control polar reference-air value to −9.5°C.
- Set the unresolved local-thickness support ceiling to 4.5 m. This preserves the inherited reference-cycle safety margin while preventing the artificial 7–8 m remnant.
- Added configuration/prior guards for the 4.5 m support geometry, exposed the warming-driven ocean term consistently in CLI/GUI/metadata, and corrected the duplicate desktop-GUI row.
- Reduced SSP2-4.5 September area in 2100 to 1.247 million km² at 5° and 1.175 million km² at 10°, while preserving positive March skill, all existing sea-ice release gates, conservation, and 200-year unforced stability.
- Verified monotonic response across SSP1-2.6, SSP2-4.5, SSP4-6.0, and SSP5-8.5 at both supported resolutions.
- Passed the complete 320-test normal repository suite with 0 failures, 0 errors, and 0 skips; separately documented four inherited standalone legacy assertions that reproduce on the untouched original tree.
- Measured a clean matched runtime change of +0.33% (fixed versus original median), below the 5% regression limit.
- Added `ACTUAL_SEA_ICE_FIX.md`, `SEA_ICE_FIX_VALIDATION.json`, derivative status/test/runtime records, normalized evidence under `validation/sea_ice_fix/`, and `tools/validate_sea_ice_fix.py`.
- Retained the original v2.29.23 evidence files as historical baseline artifacts; they are not presented as results from the modified source.

- Bound the complete non-slow pytest evidence to a canonical pre/post release-tree SHA-256 fingerprint and required exact reproduction by finalization and packaging.
- Covered executable source, GUI, tests, validation and packaging tools, dependencies/configuration, release-facing documentation, and packaged runtime data.
- Added compileall, import, GUI command-builder, and desktop-GUI construction gates to original and relocated packaging workflows.
- Made the documented finalizer and packager commands directly executable from the release root by bootstrapping root-level imports, with subprocess regression coverage.
- Made packaging independent of preinstalled optional web-UI dependencies by compiling the Streamlit app, verifying its exact dependency pin in both project and lock metadata, and importing the real core/desktop/validation modules.
- Closed Arctic normalization/remap/cleanup transfers against actual mixed-layer ocean state changes.
- Closed phase-restoring and mechanical-export compensation against actual final Atlantic and non-Atlantic lower-latitude ocean reservoirs, including spatial routing.
- Replaced ledger-record corruption checks with production implementation mutants that suppress, reverse, and misroute transfers.
- Corrected README, changelog, current setting guide, package metadata, and semantic version regressions to v2.29.23.
- Retained `engineering_only` and `scientific_release=false`; retrospective calibration remains non-prospective evidence.

## 2.29.21

- Restored CLI and desktop-GUI output generation by carrying the Arctic module blend into `SimulationResult`.
- Replaced the microscopic young-ice transition with a bounded monotonic correction and recalibrated the mature compact-pack exponent to 0.40 without changing validation thresholds.
- Added independent process budgets for ice formation, melt, ridging, divergence, export, phase conversion, and coupled-ocean heat transfer.
- Added self-contained engineering-test and combined-validation workflows with complete v2.29.21 evidence names.
- Expanded scientific fingerprint coverage to runtime provenance, trusted validation-pickle handling, AMOC continuation, and OISST acquisition/processing dependencies.
- Corrected current documentation, GUI metadata, package identity, and retained regression expectations.
- Kept the release classification `engineering_only`; retrospective evidence cannot substitute for prospective untouched temporal validation.

## 2.29.20

- Replaced volume-diagnosed sea-ice compactness with independent prognostic Atlantic and non-Atlantic concentration states coupled to the existing latent-energy volume reservoirs.
- Added explicit new-ice spreading, vertical growth, lateral area melt, ridging/rafting, divergence, complete loss, and ice-free recovery while preserving ice volume and latent heat.
- Enforced concentration bounds, non-negative volume, exact area-volume-thickness identity, 0.25 m default young-ice thickness, and an 8 m local-thickness ceiling without a discontinuous `max(pack, thin)` law.
- Reduced default Arctic winter atmospheric-transport enhancement from 88 to 10 W/m2/K, added cold-state and darkness gating, and imposed a 25 W/m2/K scientific-release ceiling.
- Rebuilt the Greenland temperature driver around Greenland/high-latitude land warming with a 10% low-pass maritime contribution; reduced slow dynamic discharge to 10% of the public coefficient and retained the freshwater cap only as a safety bound.
- Corrected resolution-weighted Arctic integration and recalibrated one shared 5-degree/10-degree physical default.
- Made recent-period September skill, coupled Arctic/Greenland/AMOC behavior, structural ice loss/recovery, and cross-resolution agreement release-blocking.
- Added version-matched 5-degree and 10-degree sea-ice, Arctic-air/ocean diagnostics, Greenland sanity checks, AMOC, structural, software-integrity, manifest, and ZIP validation outputs.
- Separated observation-file verification, engineering integrity, historical calibration, recent-period evaluation, cross-resolution, Arctic-air, Greenland, AMOC, and scientific-release status fields.
- Preserved v2.29.18 checkpoint, reference-cache, GUI-startup, and per-target CO2 sweep survival fixes.

## 2.29.18

- Replaced the v2.29.17 compactness/local-thickness power law with a conservative two-regime relation that preserves the thin-new-ice limit and prevents full cover below the declared pack thickness.
- Recalibrated one Arctic default across 5° and 10° grids and passed every mandatory March/September historical calibration gate.
- Weighted cold-season atmospheric transport by both darkness and cold reference-air state.
- Included all Arctic configuration fields and exact grid geometry in the Arctic reference-cycle cache identity.
- Restricted compactness and Arctic heat-budget priors to structurally valid, default-containing support.
- Enforced ensemble survival and quantitative member counts independently at every CO2 target.
- Forced any below-20-member target product to exploratory-only classification, including explicit override exports.
- Exposed full-cover thickness and compactness exponent in CLI, desktop GUI, Streamlit, and tooltip metadata.
- Added version-matched 5° and 10° calibration evidence, focused regressions, and a corrected full explicit-target PowerShell command.

## 2.29.17 GUI startup hotfix

- Fixed desktop-GUI construction failure caused by missing tooltip metadata for `arctic_new_ice_local_thickness`.
- Added persistent startup traceback logging and a native error dialog to the windowed launcher.
- Added a console debug launcher and GUI-startup regression coverage.

## 2.29.17

- Continued independent CO2 targets after target-specific failures and represented incomplete paired members with explicit masks instead of discarding the member.
- Applied ensemble survival gates separately to baseline-member failures and target-simulation failures.
- Replaced the small-volume compactness asymptote with a configurable 0.15 m new-ice local-thickness limit.
- Disabled winter lead closure by default, included zero in its prior, and removed raw March area as a temporal calibration target.
- Activated temperature-dependent longwave damping for Arctic ice and open water.
- Made the Arctic internal cadence independent of common outer timesteps.
- Made highly compressible checkpoints writer/reader compatible and self-validating before atomic replacement.
- Added runtime provenance to validation task identity and restricted validation-only pickle transport to private trusted paths.
- Added v2.29.17 focused regression coverage and explicit engineering/scientific status separation.

## 2.29.16

- Bound resumable validation task JSON to a pre-execution snapshot of model version, validator hash, source-tree hash, task name, and task configuration.
- Reconstructed Arctic concentration from corrected energy after control-residual balancing, making subannual diagnostics exact.
- Aligned the invariant control manifold with the same closure-adjusted Arctic concentration mapping used by live integration.
- Promoted the Monte Carlo AMOC percentage figure to the primary output folder and changed weakening to negative percentages.
- Added weighted-mean final maps and separated 1st/99th-percentile products into `diagnostics/1_99_percentiles`.
- Expanded implementation-audit coverage to include the active packager and previously omitted Monte Carlo integrity test.

## 2.29.15

- Reconstructed saved Arctic local-thickness and open-water-temperature histories with the exact lead-closure-adjusted concentration used by integration.
- Added output-level state-consistency and ice-volume-identity regressions.
- Added a smooth available-volume taper to winter lead closure.
- Capped mechanically closed concentration by the area supportable at a 0.03 m minimum local ice thickness.
- Retained reference-air climatology for the seasonal envelope and added an actual transient-temperature near-melt gate, so severely warmed winters cannot inherit full closure from the unforced state.
- Retained the v2.29.14 recovery, deterministic-validation, packaging, and fixed 17 Sv built-in Monte Carlo AMOC anchor.

## 2.29.14

- Persisted failed CO2 target attempts as canonical nested checkpoints for exact checkpoint-only recovery.
- Made parallel validation JSON byte-deterministic with canonical sorted-key serialization.
- Excluded transient validation runner PID and log artifacts from release packaging.
- Added a conservative cold-season mechanical lead-closure process that changes compactness but not ice volume.
- Reduced the default March native-area trend response from about 3.17 times to about 1.46 times the observed trend while retaining essentially unchanged September trend response.
- Exposed the new process through CLI, Streamlit, desktop GUI, setting metadata, and Monte Carlo priors.
- Retained the 17 Sv built-in science-prior AMOC control anchor and all v2.29.13 lock/recovery fixes.
- Retained the explicit non-predictive classification for historical March year-to-year timing.

## 2.29.13

- Serialized stale-lock reclamation with a cross-platform OS advisory acquisition gate.
- Made semantically incompatible state backups fall through to checkpoint metadata.
- Counted readable compatible failed checkpoints during state reconstruction.
- Fixed the built-in science-prior AMOC start at the configured control anchor (17 Sv by default).
- Preserved explicit custom sampling of the AMOC reference strength.
- Added v2.29.13 adversarial lock, recovery, checkpoint-accounting, and AMOC-anchor regressions.
- Retained all v2.29.12 Monte Carlo quality gates and the disclosed March sea-ice limitation.

## 2.29.12

- Unified science-prior screening with the exact sampled AMOC density initialization used by workers.
- Added survivor-fraction, failure-fraction, member-count, and effective-sample-size uncertainty gates.
- Added exclusive output-directory ownership locks and transactional run-state updates.
- Added exact attempted/successful/failed/validated/pending progress accounting.
- Added corrupt-backup fallback to compatible checkpoint metadata.
- Enforced canonical ZIP compression/encryption rules and exact NPY payload lengths.
- Added focused v2.29.12 concurrency, recovery, prior-screen, ensemble-quality, and malformed-checkpoint regressions.
- Retained the prominent non-predictive March sea-ice temporal limitation without physical retuning.

## 2.29.11

- Preserved the configured common CO2 start for explicit target lists, including downward ramps to targets below 278.3 ppm.
- Replaced target-dependent first-ten-record AMOC denominators with one exact pre-forcing AMOC baseline per ensemble member.
- Made normal resume fail closed when the primary run-state manifest is absent.
- Added explicit recovery from a validated state backup or compatible checkpoint metadata.
- Hardened checkpoint loading with exact archive-member validation and compressed/uncompressed resource limits.
- Expanded runtime provenance to installed distribution-content hashes and numerical build/backend metadata.
- Added v2.29.11 focused regressions, validation provenance, implementation audit, and deterministic packaging.

## 2.29.10

- Replaced the canonical 5-degree AMOC initialization reference with native-grid fractional-overlap source-region means and restored a genuine native resolution-spread test.
- Replaced pickle checkpoints with a non-executable JSON/NumPy ZIP checkpoint format.
- Added runtime source, data, dependency, Python, platform, and numerical-package digests to resume compatibility.
- Retried failed/timed-out ordinary members and failed nested sweep diagnostics by default.
- Added directory `fsync()` after atomic state/checkpoint replacement.
- Accepted explicit targets below the requested start by lowering and recording the effective common start.
- Corrected the mean-timeseries CSV to contain only mean fields.
- Tightened March temporal scientific-adequacy diagnostics and retained them as non-release-blocking limitations.
- Replaced the self-authored Greenland development range with an external post-hoc 22–163 mm SSP2-4.5 sanity envelope.
- Expanded the implementation audit to the complete long-run integrity path.
- Lengthened convection recovery from 20 to 80 years to retain >80% hosing recovery without a >0.5 Sv/year millennium-hold restart overshoot.

## 2.29.9

- Corrected scientific-evidence labels: no independent historical temporal-skill claim; historical Arctic scores are descriptive and non-release-blocking.
- Added robust March trend diagnostics across predeclared periods with uncertainty and Theil-Sen estimates.
- Added conservative native-ice compactness physics and recalibrated Arctic/AMOC/Greenland defaults.
- Added a zero-restoring structural branch with a 20% Monte Carlo point mass.
- Reclassified OISST bounds as descriptive, non-reproduced and non-release-blocking.
- Synchronized public interface ranges with priors.
- Retained all v2.29.8 resumable-run, explicit CO2-target, and AMOC percentage-decline features.

## 2.29.8

- Added atomic `long_run_state.json` manifests for Monte Carlo and paired CO2 target-sweep runs.
- Persisted system-clock-resolved seeds so seed-0 runs resume the original sample rather than generating a new ensemble.
- Added per-target atomic checkpoints within each paired CO2 sweep member; failed or interrupted outer members can be retried from their completed targets.
- Added desktop **Load saved run** support that restores the exact original command and forces compatible checkpoint resume.
- Added regular-increment versus explicit-target selection for CO2 sweeps, including exact lists such as `200,300,600,1200`.
- Added AMOC decline as percent of each member-target initial ten-record baseline, with weighted 1-99%, 5-95%, and 17-83% intervals in summary, trajectory CSV, NPZ, and PNG outputs.
- Added focused regression coverage for seed persistence, failed-member retry, per-target resume, explicit target parsing, exact command restoration, and AMOC decline products.
- No physical or scientific calibration defaults were changed from v2.29.7.

## 2.29.7

- Retuned only existing thermodynamic Arctic controls to improve the historical native September-area trend from about 41% to about 68% of observed without a statistical area or trend correction.
- Reduced selected-candidate March and September native-area biases and the 2021–2025 September-area RMSE to 0.238 million km².
- Added release gates requiring positive raw rolling-origin persistence skill for all four sea-ice metrics and at least 60% representation of the observed September trend.
- Corrected Arctic open-water exchange so all four broad OISST development bounds pass; reclassified those ranges explicitly as tuning-informed rather than independent validation.
- Exposed and uncertainty-sampled the tuned Arctic geometry, seasonal reference amplitude, lapse closure, basal/open-water/lateral ocean exchange, shortwave response and AMOC hydraulic ceiling.
- Added explicit March 2026 reporting while retaining 2027 onward as the next untouched temporal evaluation period.
- Added deterministic OISST source acquisition/hash tooling without fabricating unavailable source hashes or processed artifacts.
- Synchronized development dependency provenance and added a complete packaged-file SHA-256 manifest.
- Added v2.29.7 independent-review regressions, validation, audit, documentation and packaging workflows.
- Selected a 150-year AMOC convection-recovery timescale so the retuned model retains at least 80% recovery after the standard 40-year, 0.1 Sv hosing experiment.
- Replaced the stale direct comparison between the preindustrial Arctic reference cycle and modern observations with a control-to-historical consistency gate that requires warming-related ice loss and preserves the seasonal amplitude.
- Synchronized retained compatibility tests with v2.29.7 evidence roles, preindustrial-reference semantics, 2081–2100 mean versus single-year AMOC diagnostics, and the validated resolution envelope.
- Added desktop metadata aliases for the tuned Arctic lapse-rate, module-latitude, and reference seasonal-amplitude controls.

## 2.29.6

- Removed the intercept-based seasonal sea-ice area observation operator and made published area identical to the native thermodynamic integral.
- Retained only a bounded, zero-intercept seasonal area-to-15%-extent ratio; added continuity, monotonicity, zero, and small-positive-value regressions.
- Retuned native March and September area, seasonal amplitude, and historical trend without a statistical area correction.
- Replaced the active 1.2 m equivalent-thickness cap with continuous mechanical export and an inactive 8 m emergency guard.
- Removed Northern Hemisphere legacy annual-ice double counting beneath the seasonal Arctic module.
- Restored the AMOC temperature-density coupling default to 1.00 without changing the 0.006/0.005 Sv/K freshwater defaults.
- Reclassified 2021–2025 as validation-informed development data, added rolling-origin historical diagnostics, and reserved 2027 onward prospectively.
- Updated OISST processing to use the model Atlantic mask and removed any packaged claim of reproduced numerical validation when source files and hashes are absent.
- Added native RMSE/trend/amplitude, winter coverage, cap occupancy, future forcing-order, evidence-role, and map-role release gates.
- Added Windows CI/startup/Monte Carlo coverage, synchronized dependency metadata to v2.29.6, and limited installed-file hash checks to the recorded platform.
- Added v2.29.6 validation, audit, review, packaging, and native-Arctic integrity tests.
- Preserved Gaussian-copula prior correlations during physical rejection redraws and aligned the built-in AMOC-reference prior with the default 20 Sv hydraulic upper bound.

## 2.29.5

- Retuned native fractional-Arctic thermodynamics and open-water damping so March/September control ice and sector temperatures are physically plausible without relying on the statistical observation operator.
- Removed the post-2020 sea-ice projection closure and retained only a frozen 1979-2020 historical observation operator over prognostic native ice.
- Added exact-zero area, extent, concentration-map and occupancy-map behavior.
- Added native-control sea-ice gates and native future area/forcing-order checks.
- Added frozen-2020 persistence baselines to all four independent 2021-2025 NSIDC March/September area/extent holdout gates.
- Added deterministic NOAA OISST processing code, exact source locators, file-hash provenance, and an open-water benchmark README.
- Added corrected and uncorrected 500-year control-drift reporting without changing which trajectory defines release stability.
- Synchronized retuned defaults and uncertainty ranges across public interfaces and Monte Carlo priors.
- Added v2.29.5 physical-integrity tests, validation records, post-fix review, and extracted-package verification.

## 2.29.4

- Replaced the exact zero-forcing reference-manifold advance with continuous phase-dependent reference-tendency balancing inside the ordinary equations.
- Added a calibrated Northern Hemisphere sea-ice area and 15%-extent observation operator over the conserved two-sector thermodynamic state.
- Added deterministic sub-grid extent occupancy and clearly separated it from both the native process field and the longitude display reconstruction.
- Frozen NSIDC v4 March/September 1979–2020 calibration data and 2021–2025 independent temporal holdout data with predeclared gates.
- Added broad NOAA OISST/Arctic Report Card sector-temperature plausibility checks and mandatory non-local interpretation warnings.
- Separated tuning-informed development ranges, independent holdout evidence, external plausibility checks, and structural tests in validation records.
- Labelled AMOC and Greenland outputs as sensitivity experiments rather than precise forecasts.
- Added explicit statistical/native sea-ice fields to summaries, NPZ/CSV downloads, maps and Streamlit, with no-longitude-skill warnings.
- Added subannual September sampling enforcement and SSP5-8.5 versus SSP2-4.5 physical ordering release gates.
- Updated retained compatibility tests to use the native thermodynamic field for process localization and the active v2.29.4 provenance records.

## 2.29.3

- Made Meinshausen et al. (2020) the synchronized default CO2 forcing formula across public interfaces.
- Added explicit overwrite confirmation and protected-path rejection so existing results and source directories cannot be silently deleted.
- Added spawn-isolated worker timeouts, heartbeats, atomic checkpoints, deterministic resume, and stale temporary-file cleanup.
- Added whole-process-tree termination and closed the desktop GUI close-during-launch orphan-process race.
- Raised the unresolved Arctic-lead threshold from 1% to 5%, conservatively exporting sensible heat to the coupled ocean and eliminating a 47.43°C tiny-lead singularity.
- Added an exact zero-forcing seasonal-reference manifold advance, eliminating accumulated control drift without suppressing real perturbations.
- Recomputed interpolated Arctic interface temperature from interpolated ice/open-water states, preserving nonlinear diagnostic consistency and strict internal heat conservation.
- Precomputed immutable Greenland geographic melt weights, preserving equations while restoring full-period validation performance.
- Added operational-safety regressions and an 18-gate v2.29.3 validation and packaging pipeline.

## 2.29.2

- Added adaptive Arctic reference-cycle spin-up with a configurable hard maximum and mandatory closure/convergence enforcement.
- Added pre-projection salt-residual diagnostics and structural-leak rejection before roundoff-only whole-domain salt projection.
- Made physical and numerical Monte Carlo safety filters unconditional in every constraint mode.
- Replaced the one-sided excess-ice ocean heat closure with a signed, equal-and-opposite phase-restoring exchange.
- Synchronized Arctic interface defaults, added stable/unstable exchange cross-validation, and used the configured Arctic diagnostic latitude consistently.
- Skipped seasonal reference-cycle construction when the seasonal Arctic module is disabled.
- Replaced the forced-exit isolated pytest hook with normal per-test subprocess execution and made the complete test inventory the default.
- Replaced optional Hypothesis-only conservation coverage with deterministic property-style parameter grids and seeded samples.
- Added public-range convergence, honest salt-accounting, unconditional Monte Carlo safety, and complete-suite release gates.

## 2.29.1

- Conservatively remapped fractional open-water enthalpy during phase-area changes.
- Eliminated dormant sensible heat beneath complete or sub-grid ice cover.
- Added a 1% effective-open threshold for unresolved leads and conservative ocean heat transfer.
- Applied transient phase remapping relative to the periodic control cycle to preserve unforced invariance.
- Separated Arctic reference-ocean temperature targets from exchange coefficients.
- Required strictly positive open-water/ocean exchange.
- Added online internal-timestep Arctic temperature and dormant-heat diagnostics.
- Added hard release and Monte Carlo filters for thermodynamic validity and convergence.
- Corrected the double application of the winter transport blend.
- Split reference-cycle energy and temperature closure diagnostics and made validator failures return nonzero.
- Routed conservative excess-ice heat convergence from the lower-latitude ocean source region, restoring hosing recovery without weakening phase-anomaly recovery.
- Added synchronized CLI, desktop, Streamlit, metadata, documentation, and regression coverage.

## 2.29.0

- Coupled the fractional Arctic surface bidirectionally to prognostic sector-ocean temperature.
- Added ocean-temperature-dependent basal ice heat flux and two-way open-water/ocean exchange.
- Added sector-specific periodic shallow reference-ocean states with conservative heat accounting.
- Removed the active 4°C open-water clipping behavior.
- Synchronized new controls across CLI, desktop, Streamlit, metadata, and Monte Carlo priors.
- Added SSP1-2.6 and SSP4-6.0 supplementary pathway checks, Arctic resolution metrics, and 16-task validation.

## 2.28.1

- Synchronized desktop, Streamlit, CLI metadata, and Monte Carlo defaults with the validated model configuration.
- Fixed the GUI-generated Monte Carlo initial-density failure.
- Expanded uncertainty ranges and priors to include the validated AMOC defaults.
- Added the explicit fractional-Arctic external flux anomaly to resolved-system TOA accounting while retaining separate bulk-radiative and Arctic diagnostics.
- Standardized headline and timestep validation on a common 0.1-year sampling grid.
- Removed inactive pre-v2.28 Arctic controls from active desktop and Monte Carlo surfaces and marked hidden compatibility inputs as ignored.
- Corrected the Arctic SAT-memory naming and masked open-water maps where no open water exists.
- Added interface-parity, heat-budget, sampling, map-mask, and end-to-end Monte Carlo regression tests.

## 2.28.0

- Added separate conserved ice-latent and open-water-sensible Arctic reservoirs.
- Added fractional area-weighted ice/open-water surface fluxes and local-thickness ice conduction.
- Added separate Atlantic-influenced and central-Arctic periodic reference cycles.
- Reused the full surface energy balance in transient integrations.
- Added stability-dependent open-water exchange and conservative overflow to the bulk ocean.
- Added open-water-temperature and local-ice-thickness outputs and regression tests.
- Preserved hydrological and Greenland freshwater defaults.


## 2.27.1

- Bounded the Arctic reference-cycle cache with an eight-entry LRU policy and included every cycle-generating configuration input in its key.
- Extended the seawater-freezing lower bound through the entire 55–66 N transition zone while preserving the global 14 C baseline.
- Added explicit bulk-surface, near-surface-air, and Arctic ocean-interface temperature histories, maps, CSV outputs, figures, and UI selection.
- Replaced the mixed-variable Arctic amplification comparison with a like-for-like near-surface-air numerator and denominator.
- Corrected Arctic exchange priors, tooltip defaults, version metadata, dependency metadata, and release documentation.
- Added 2.5, 5, and 10 degree reference-cycle regressions plus cache-key, LRU-bound, and temperature-product consistency tests.

## 2.27.0

- Separated land and ocean absolute climatologies and bounded the Arctic mixed-layer ocean baseline to the configured seawater freezing point north of 66 N while preserving the 14 C global mean.
- Replaced inherited annual-mean sea ice and annual-mean shortwave subtraction with a periodic zero-layer reference energy balance including orbital insolation, surface exchange, ice/snow conduction, basal ocean heat, albedo evolution, and open-water heat storage.
- Recalibrated seasonal Arctic transport so the historical response is strongly winter-dominant and substantially weaker in summer, without reintroducing legacy multiplier controls.
- Added a reduced Greenland surface-mass-balance branch with positive-degree-day melt, snowfall/rain partition, precipitation response, retention, runoff, accumulation, and a finite ice reservoir.
- Separated slow Greenland dynamic discharge from immediate surface mass balance while retaining the public 0.005 Sv/K Greenland coefficient and the 0.006 Sv/K hydrological coefficient.
- Updated AMOC thermal-stratification coupling and convection-density normalization after the corrected Arctic climatology; no freshwater compensation retuning was used.
- Synchronized the CLI, desktop GUI, Streamlit app, Monte Carlo priors, setting metadata, package and dependency metadata, validation provenance, and documentation.
- Added structural Arctic/Greenland regressions and an isolated per-test pytest runner to avoid combined-process shutdown hangs.
- Reclassified all literature-range comparisons explicitly as tuning-informed development regression checks rather than independent validation.
- Updated the legacy 1200 ppm long-hold regression to test the original restart-pulse defect directly through recovery-rate and overshoot bounds; v2.27 no longer falsely requires a crossing below the fixed 6 Sv reference.

## 2.26.0

- Replaced the cosine Arctic reference cycle with daily-mean orbital insolation that resolves polar night and midnight sun.
- Added a near-freezing latent/sensible ocean-interface enthalpy state and thermodynamically generated sea-ice thickness and concentration.
- Added conservative atmosphere–interface–ocean heat exchange, delayed cold-season open-water heat release, and explicit interface-energy overflow return to the mixed layer.
- Corrected seasonal phasing so winter amplification is strongest, autumn amplification exceeds summer, and the heat-release pulse follows the summer ice minimum.
- Added normalized summer-dominant Greenland runoff routing while preserving the 0.005 Sv/K annual sensitivity and the slow annual-mean discharge state.
- Kept hydrological freshwater at 0.006 Sv/K; no 0.023/0.017 Sv/K compensation values are used by defaults or ordinary priors.
- Set AMOC thermal-density coupling to 0.71 after joint SSP2-4.5, SSP5-8.5, and hybrid-pathway calibration with freshwater coefficients fixed.
- Removed legacy empirical Arctic multiplier controls from normal interfaces and retained only hidden, neutral backward-compatible CLI/config inputs.
- Added v2.26 thermodynamic-Arctic, conservation, seasonal-phasing, legacy-neutrality, and freshwater anti-inflation regressions.
- Documented the two intentional v2.23 compatibility differences: the corrected tuning-evidence label and the reduced hosing cold-blob amplitude after the versioned AMOC heat-coupling recalibration.

## 2.25.2

- Replaced the empirical Arctic near-surface-air closure with prognostic seasonal Arctic air and latent sea-ice-energy states in Atlantic and non-Atlantic sectors.
- Added conservative implicit ocean–air exchange, seasonal ice reference states, winter open-water heat release, atmospheric moisture/dry-static transport, and energy-conserving two-sided ice anomaly relaxation.
- Added exact time-weighted annual averaging for validation and separate instantaneous, one-year low-pass, blended-surface, and heat-content Arctic diagnostics.
- Restored hydrological freshwater to 0.006 Sv/K and independently calibrated Greenland freshwater to 0.005 Sv/K; narrowed default GUI and ensemble ranges to prevent compensation by hosing-like values.
- Removed duplicate convection density-memory feedback by default while retaining convection-dependent salt mixing, full anomalous thermal-density coupling, and the tested 3.0 convection density scale factor.
- Added long-control, two-sided perturbation-recovery, hosing-recovery, annual-mean, and no-freshwater-compensation regressions.
- Updated the core, CLI, desktop GUI, Streamlit app, Monte Carlo configuration, metadata, validation, documentation, and release tests.

## 2.24.0

- Fixed the 2011–2020 GMST reference-period error by subtracting the simulated 1850–1900 mean.
- Raised the default vertical ocean heat-exchange coefficient to 1.10 W/m2/K.
- Rebalanced AMOC freshwater, thermal-density, and regional heat-feedback parameters for plausible SSP2-4.5 and SSP5-8.5 transient weakening.
- Added a diagnostic Arctic near-surface-air closure and retained the original prognostic blended surface-state output under an explicit name.
- Added matching CLI, desktop, Streamlit, metadata, Monte Carlo, and validation settings.
- Reclassified the v2.24 literature-range comparisons as tuning-informed development regression checks rather than independent held-out validation.
- Added v2.24 regression tests and updated structural hosing expectations.



## 2.23.0

- Replaced the misleading all-seeds-converged completeness flag with reproducible root-count saturation, randomized seed expansion, confidence metadata and structured failure diagnostics.
- Switched root deduplication to dimensionless equilibrium distance.
- Replaced greedy branch identity with Hungarian global assignment and secant prediction.
- Added true augmented pseudo-arclength branch tracing through parameter folds, including unstable branches and saddle-node candidate flags.
- Strengthened nonlinear stability acceptance to sustained multi-window decay and added real/imaginary complex-eigenmode perturbations.
- Expanded frozen held-out validation to GMST, ocean heat content, Arctic amplification and AMOC decline with calibration-registry separation and SHA-256 provenance.
- Added ocean heat-content output fields, a fully resolved exact-version runtime graph, an environment-integrity manifest, and hash-lock regeneration tooling.


## 2.22.0

- Removed unstable-root fallback from equilibrium branch selection.
- Added adaptive continuation refinement, branch identity and explicit incomplete-result reporting, with pure branch-topology helpers extracted to `amoc_continuation.py`.
- Made equilibrium bounds configurable and report bound contact.
- Added multiscale Jacobian and nonlinear timestep-converged reduced-subsystem stability tests, including bounded contracting-envelope detection for damped non-normal transients.
- Renamed the equilibrium output to state its fixed-preindustrial-climate assumption.
- Added Greenland-specific temperature weighting and separate gross melt, gross accumulation and net ice-loss accounting.
- Added source-backed held-out benchmark evaluation, an optional strict benchmark exit code, and pytest collection of legacy regression entrypoints.


## 2.21.0

- Reformulated AMOC equilibrium continuation using whole-domain salt conservation and full six-box tendency acceptance tests.
- Smoothed the convection adjustment/recovery timescale transition and replaced the one-sided Jacobian with central differences.
- Added nonlinear signed perturbation validation for equilibrium roots.
- Unified collapse-threshold semantics while retaining the fixed 6 Sv reference as a separate named indicator.
- Added explicit calibration and held-out validation evidence partitions.
- Added reversible hydrological freshwater, regional Greenland temperature forcing, signed accumulation/regrowth and net ice-loss accounting.
- Updated regression expectations for the new regional Greenland response and added v2.21.0 scientific-fix tests.


## 2.20.0

- Fixed hybrid SSP switch-year validation and SSP4-6.0 automatic-initialization reporting.
- Replaced mean-only final-window collapse labels with duration, continuity, recovery, and reversal diagnostics.
- Renamed weighted AMOC outcome outputs to conditional ensemble fractions.
- Added weighted bootstrap confidence intervals, monotonicity diagnostics, isotonic threshold estimates, and non-monotonicity warnings to CO2 target sweeps.
- Added an explicit Monte Carlo physical-parameter whitelist and rejection of experiment/numerical controls.
- Added the normalized Meinshausen et al. (2020) CO2 forcing option.
- Added warming-sensitive Southern Ocean and Indo-Pacific compensation AMOC structural families.
- Added locked runtime/development dependencies, GitHub Actions CI, and Hypothesis conservation properties.
- Updated the CLI, desktop GUI, Streamlit dashboard, setting metadata, documentation, and regression tests.

## 2.19.0

- Added `co2_target_sweep.py` for paired Monte Carlo AMOC experiments across stepped CO₂ targets.
- Added the `linear_ramp_hold` core scenario and `co2_ramp_years` setting.
- Added desktop-GUI controls and a ready-made CO₂ target-sweep preset.
- Added ever-collapse and persistent-collapse conditional ensemble-fraction curves, target threshold estimates, member tables, mean/all trajectory plots, and compressed sweep trajectories.
- Reuses each parameter draw at every target and calculates posterior calibration diagnostics only once per paired member.

## 2.18.2

- Added conservative control-anomaly salinity exchange with the external ocean for the Southern Ocean and South Atlantic upper-limb boxes.
- Eliminated the artificial approximately 37 Sv AMOC restart pulse in 1000-year 1200 ppm hold experiments.
- Preserved the calibrated control state and global salt conservation to floating-point precision.
- Added CLI, desktop GUI, Streamlit, metadata and custom Monte Carlo range support for the exchange strengths.
- Added long-hold rebound diagnostics and regression tests.
- Marked older long-term posterior results as structurally version-specific.

## 2.18.1

- Simplified the percent-ramp scenario so the comma-separated growth-rate list controls the entire experiment.
- Removed the redundant single growth-rate field from the desktop and Streamlit interfaces.
- A one-rate experiment is now represented by a one-item rate list.
- The first sorted rate drives the standard single-run files; every listed rate appears in the comparison outputs.
- Retained the old scalar CLI argument as a hidden backward-compatibility alias.

## 2.18.0

- Added the generalized `percent_ramp_hold` CO2 pathway with configurable annual compound growth rate, ppm cap and post-cap hold duration.
- Added automatic experiment-duration resolution from time-to-cap plus hold years.
- Added multi-rate comparison output with a combined CO2, global-temperature and AMOC plot.
- Added comparison summary/timeseries CSV files and JSON metadata.
- Added CLI, desktop GUI, Streamlit and setting-metadata support.
- Added regression tests for cap timing, hold behavior, validation, GUI command generation and comparison exports.

## 2.17.1

- Fixed 10-degree AMOC initialization using fractional spherical-area integration over fixed latitude regions, without relaxing the absolute-density screen.
- Added missing validation for `amoc_external_box_volume_m3` and `initial_external_salinity_psu`.
- Added cross-resolution control and forced-response regression tests.
- Added explicit ECS equilibrium convergence criteria, convergence metadata and optional automatic extension.
- Renamed the positive Gregory restoring magnitude while retaining the legacy output alias.
- Added an optional Heun predictor-corrector coupled AMOC update; Euler remains the compatibility default.
- Separated calibration-target metadata from held-out and structural validation diagnostics.
- Added held-out AMOC validation, structural-family comparison and posterior identifiability-analysis scripts.

## 2.17.0

- Added a finite Greenland ice reservoir with cumulative melt, remaining mass and sea-level-equivalent diagnostics.
- Added absolute initial AMOC density-margin screening to prevent normalization from hiding hydrographically fragile members.
- Disabled negative AMOC by default and separated active, weak/collapsed and reversed states in outputs and posterior reporting; reversal remains an explicit opt-in experiment.
- Jointly recalibrated the default continuous AMOC response against the configured SSP5-8.5 1995–2014 to 2081–2100 weakening range and the 40-year 0.1 Sv hosing-response range.
- Updated AMOC, salinity and Greenland physical priors for the new formulation.
- Added structural regression tests for reservoir mass conservation, density screening, reversal opt-in and joint calibration.
- Existing v2.16.x posterior weights are not transferable and must be recomputed.

## 2.16.4

- Added posterior weight sums and posterior probabilities to the AMOC completion report whenever AR6 or AR6+AMOC weighting is active.
- Added weighted final-30-year collapsed and non-collapsed diagnostics to JSON summaries.
- Clarified the built-in physical-prior and correlated-prior controls in the desktop interface and tooltips.

## 2.16.3

- Added an end-of-run AMOC count at 2100 for members with AMOC below 10 Sv.
- Added final-state classification from each member's time-weighted mean AMOC over the last 30 simulation years.
- Reports collapsed members at or below 6 Sv and non-collapsed members above 6 Sv.
- Writes the counts to the console, `monte_carlo_summary.json`, `monte_carlo_amoc_counts.json`, and `monte_carlo_amoc_counts.txt`.

## 2.16.2

- Added a labeled horizontal 6 Sv reference line to deterministic AMOC time-series plots.
- Added the same 6 Sv reference to AMOC dynamical-target and equilibrium-continuation figures.
- Added a 6 Sv line to Monte Carlo AMOC ensembles, the final-AMOC histogram, and the final warming-versus-AMOC scatter.
- Added the 6 Sv reference series to the Streamlit AMOC chart.

## 2.16.0

- Removed the Boolean deep-convection collapse and restart switch from the AMOC dynamics.
- Removed the forced collapsed-branch convection target.
- Added continuous northern surface-to-deep convective salt exchange.
- Added continuous convective entrainment support to the local density response.
- Reclassified `amoc_convection_collapsed` as a diagnostic output only; it never changes the equations.
- Added the new continuous-feedback controls to the CLI, desktop GUI, Streamlit dashboard, metadata and Monte Carlo priors.
- Retained the old collapse/restart configuration keys as ignored compatibility fields for previous JSON files.
- Added regression tests for smooth target evolution, emergent low-AMOC states and salt conservation.

## 2.15.1

- Exposed hydrological north-routing and Greenland response time as custom Monte Carlo adjustors.
- Updated freshwater custom ranges and enabled all four freshwater adjustors by default when custom ranges are used.
- Added CLI aliases, documentation, and regression tests.
- Updated the bundled GUI settings example to use the corrected convection exponent and non-extreme freshwater defaults.

## 2.15.0

- Set the default AMOC convection transport exponent to 1.0 so sinking efficiency directly controls overturning transport.
- Added a local northern surface-to-deep density diagnostic for deep-convection stability, separate from the basin-scale hydraulic density gradient.
- Added stateful collapse/restart hysteresis with distinct density thresholds and a configurable residual collapsed-branch convection fraction.
- Prevented slow deep-ocean equilibration or Southern Ocean salinity changes from automatically restarting a locally stratified northern sinking branch.
- Added collapsed-branch state and local convection-density diagnostics to transient outputs and summaries.
- Added CLI, desktop GUI, Streamlit, metadata and Monte Carlo support for the new hysteresis parameters.
- Updated equilibrium continuation to solve active and collapsed convection branches separately.

## 2.14.0

- Added hover help for every desktop GUI setting and every Streamlit control.
- Added shared `setting_metadata.py` descriptions with uncertainty/interval basis and confidence ratings.
- Distinguished assessed or observational intervals from broad prior support and user-defined experiment ranges.
- Added tooltip coverage for every custom Monte Carlo min-max parameter.
- Added `SETTING_REFERENCE_GUIDE.md` with confidence definitions and scientific source groups.
- Added automated metadata and interface coverage tests.

## 2.13.0

- Restored a signed Stommel-type salt-advection multiple-equilibrium structure in the AMOC subsystem.
- Removed deep-convection efficiency as a default multiplicative suppression of the already density-driven hydraulic transport; the optional exponent remains configurable.
- Lowered the residual convection floor, narrowed its transition, shortened transient recovery and reduced pycnocline cancellation.
- Replaced the fixed-duration freshwater ramp with nonlinear equilibrium continuation using multi-start least-squares root finding.
- Added exact active-Atlantic salt reduction, local Jacobian stability classification and explicit stable-root branch tracking.
- Added output fields for convergence, residual norm, maximum real eigenvalue, number of stable equilibria, bistable interval and stable branch separation.
- Forced active-Atlantic compensation in the equilibrium diagnostic so permanent freshwater forcing can reach a stationary salt budget.
- Retained the old finite-rate loop as `diagnose_amoc_transient_loop()` and relabelled it as transient memory.
- Added regression tests proving two stable equilibria under the same forcing and distinct equilibrium collapse and recovery thresholds.
- Updated CLI, desktop GUI, Streamlit, priors, figures and documentation for the new formulation.

## 2.12.0

- Replaced built-in triangular priors with parameter-specific beta, truncated-normal, log-normal, log-uniform and uniform marginals.
- Broadened prior support so observational evidence is applied once through the likelihood rather than duplicated in the prior.
- Removed deterministic net feedback from the independent likelihood targets.
- Replaced sequential pairwise correlations with a simultaneous positive-semidefinite Gaussian-copula matrix.
- Added target-level likelihoods, group weights, entropy, maximum-weight and effective-sample-quality diagnostics.
- Added joint hydrographic rejection rules preventing unrealistic FovS/AMOC/salinity combinations.
- Added separate prognostic Atlantic and non-Atlantic mixed-layer, deep-ocean, sea-ice and low-cloud states.
- Made AMOC regional temperature changes physically active in radiation, cryosphere, land-ocean exchange, ocean uptake and density feedbacks rather than localizing only the final map.
- Added automatic 1850-to-start-year initialization for post-1850 SSP and hybrid runs, with a CLI and GUI opt-out.
- Split warming freshwater into immediate hydrological and lagged Greenland components while retaining the legacy combined override.
- Replaced the hidden interhemispheric temperature multiplier with an explicit parameter.
- Added transient SSP5-8.5 and 0.1 Sv hosing response diagnostics to optional AMOC posterior weighting.
- Added backward-compatible summary fields and the legacy AMOC tracer-history property.
- Added `--mc-no-plots` for fast numerical ensemble generation and regression testing.
- Updated desktop and Streamlit controls, validation metadata, sample outputs and documentation.
- Replaced the slow monolithic smoke test with fast and full regression suites.
- Replaced the slow bundled eight-member 1850-2300 validation with a fast four-member SSP5-8.5 regression through 2100 that completes in about 13 seconds in the validation container.
- Corrected the tiny numerical residual removal in conservative AMOC heat redistribution.
- Corrected the historical ocean heat-uptake-efficiency diagnostic to regress explicit mixed-layer-to-deep-ocean heat uptake, not total TOA imbalance.

## 2.10.0

- Replaced the zero-valued AMOC heat-flux placeholder with conservative anomalous tropical-to-subpolar Atlantic heat redistribution.
- Added a prognostic AMOC ocean-temperature tracer and latitude-band-conserving Atlantic map localization.
- Disabled the prescribed cold-blob fingerprint by default; the displayed North Atlantic response now comes from the integrated climate state.
- Coupled AMOC heat anomalies to radiation, deep-ocean uptake, sea ice, meridional transport and the density/stratification feedback.
- Added configurable surface-coupling fraction and regional-temperature damping parameters to CLI, GUI, Streamlit and Monte Carlo workflows.
- Reworked the integrator to shorten the final timestep and hit record/final times exactly for arbitrary valid `dt_years`.
- Added active-coupling, map-conservation and timestep-bookkeeping regression tests.

## 2.9.0

- Limited the AMOC transport response to pycnocline deepening and added pycnocline-depth relaxation.
- Added a prognostic nonlinear deep-convection efficiency state with fast weakening and slow recovery timescales.
- Changed the default warming-driven freshwater coefficient from `0.050` to `0.010 Sv/K`; the ensemble range remains `0.002-0.025 Sv/K`.
- Added GUI, CLI and Monte Carlo controls for the new convection and pycnocline parameters.
- Added convection and limited-depth diagnostic trajectories while keeping the primary AMOC-strength figure uncluttered.
- Added `amoc_dynamics_fix_test.py`.

## 2.8.9

- Recalibrated default longwave, water-vapour/lapse-rate, cloud, and ocean-exchange coefficients so the model's diagnosed feedback decomposition lies inside the AR6 target region.
- Added a separate Atlantic gyre heat-transport term and now compare total, rather than overturning-only, heat transport with the 26.5 N calibration target.
- Replaced the naive product of correlated diagnostic likelihoods with five grouped composite likelihoods and exported per-group log-likelihood columns.
- `ar6` and `ar6_amoc` now automatically run their required calibration experiments; the redundant GUI checkbox is removed.
- Updated built-in prior ranges, including warming-driven freshwater `0.002-0.025 Sv/K`.
- Added `calibration_fix_test.py`.

## 2.8.8

- Added a dedicated FovS time-series figure to the main output folder.
- Main output folders now retain only temperature anomaly, AMOC strength, FovS, and raw data files.
- All other PNG figures are written to a `diagnostics` subfolder.
- Raw CSV, JSON, and NPZ output paths remain unchanged for compatibility.

## 2.8.7

- Replaced the incorrect Southern-Ocean-versus-deep FovS approximation with a dedicated South Atlantic upper-limb tracer at 34.5 S.
- Added a fifth active Atlantic salinity box and preserved exact salt conservation.
- Defined FovS as `-q (S_upper - S_deep) / S0`, matching the standard overturning freshwater-transport sign convention.
- Added a configurable initial FovS target, defaulting to -0.15 Sv, and derived the corresponding upper-limb salinity.
- Added GUI and CLI controls for initial FovS and reference salinity.
- Added Monte Carlo priors and figures for upper-limb salinity and upper-minus-deep salinity contrast.
- Added regression tests for the FovS sign, value, transport limbs, control stability, and salt conservation.

## 2.8.6

- Restored Monte Carlo sea-ice and snow percentile maps and area-fraction trajectories.
- Removed the artificial AMOC cold-blob self-stabilization loop.
- Replaced the forced thermal AMOC term with northern surface-minus-deep stratification.
- Added AMOC thermal, haline, stratification and density-driver ensemble figures.
- Corrected AMOC decline and heat-transport decline signs so positive values mean weakening.
- Preserved user-selected scenario, ranges and calibration settings unchanged.

## 2.8.5

- Monte Carlo now runs only the scenario selected by the user by default.
- Removed all hidden abrupt-2xCO2, 1%-CO2, historical, ECS/TCR, and AMOC calibration experiments.
- Posterior weighting defaults to `none`.
- Science-informed prior ranges are opt-in and no longer replace user min/max settings unless explicitly enabled.
- AR6 and AR6+AMOC calibration require a separate explicit checkbox/CLI flag.
- Added continuous progress, throughput, and ETA reporting.
- Preserved all-member plots and 1-99%, 5-95%, and 17-83% bands.

## 2.8.4

- Fixed the Stop button so it terminates the complete simulation process tree.
- Windows now launches simulations in a new process group and uses `taskkill /T /F` to stop the parent and every parallel Monte Carlo worker.
- Linux and macOS now launch simulations in a new session and terminate the entire process group.
- A user-requested stop is reported as `Stopped` instead of as a failed simulation.
- Closing the GUI during a run now waits for the full worker tree to terminate before closing.

# Version 2.8.4

- Fixed the Windows Tkinter layout bug that allowed long help text to collapse editable Entry and Combobox controls to zero width.
- Monte Carlo members, workers, seed, sampling design, distribution, and constraint mode are now visibly editable.
- Field rows now use independent layout containers with guaranteed input widths and wrapped help text.
- Added a real GUI geometry/state regression test.

## Earlier changes

- The Monte Carlo random seed now defaults to `0`.
- Seed `0` is resolved from the system clock at run start.
- The resolved seed is printed and stored in `monte_carlo_summary.json`.
- Any nonzero seed remains exactly reproducible.
- Negative seed values are rejected by both GUI and CLI validation.

# v2.8.1

- Fixed Monte Carlo GUI state handling.
- Random seed, parallel workers, member count, sampling design, constraint mode, and export controls now remain editable at all times.
- Science-informed priors disable only the custom per-parameter min/max controls.
- Monte Carlo values are ignored unless the Monte Carlo checkbox is enabled.

# Version 2.8.0

- Replaced heuristic-only Monte Carlo defaults with science-informed climate and AMOC priors.
- Added `exploratory`, `ar6`, and `ar6_amoc` ensemble modes.
- Added split-normal importance weighting against emergent AR6 diagnostics.
- Added historical warming, Earth energy imbalance, ocean heat-uptake efficiency, present-day AMOC, Atlantic heat transport, and FovS diagnostics for every constrained member.
- Added Sobol and Latin-hypercube sampling designs.
- Added correlated Gaussian-copula priors for selected process blocks.
- Added posterior weights, log weights, hard-filter reasons, and effective sample size.
- Restored all-member AMOC and temperature plots.
- Restored and expanded salt-advection/FovS plots.
- Added weighted 1-99%, 5-95%, and 17-83% bands to every ensemble time series.
- Added AMOC decline, Atlantic heat-transport decline, FovS change, and salinity-contrast change plots.
- Added p01 and p99 final maps and p99-p01 uncertainty-width maps.
- Added weighted ECS, TCR, feedback, historical, AMOC, and FovS endpoint distributions.
- Updated the desktop GUI with constraint mode, Sobol/LHS design, science-prior, and correlated-prior controls.
- Retained mandatory realistic geography and explicit failure when the world-grid asset is absent.

### Six-source Arctic observational validation integration (2026)
- Added NOAA/NSIDC G02202 v6 fixed-mask concentration-derived area as the primary sea-ice area target.
- Added PIOMAS v2.1 as a separate long-record volume constraint.
- Added source-separated CryoSat-2 RDEFT4 v1 and ICESat-2 IS2SITMOGR4 v4 thickness checks.
- Added OSI SAF OSI-450-a1 v3.1 as an untuned area cross-check.
- Added NSIDC-0611 v4 multiyear-ice structural diagnostics.
- Added fail-closed provenance checks, acquisition/preprocessing tooling, and processed-data bundle export.

## 2026-08-08 — Arctic Earthdata acquisition hotfix
- Filter NASA Earthdata granule links to scientific NetCDF payloads before processing.
- Verify classic NetCDF / NetCDF-4 file signatures and reject sidecars explicitly.
- Use explicit xarray NetCDF backend fallbacks instead of backend auto-detection.
- Make process-existing discovery signature-based for CryoSat-2 and ICESat-2 downloads.
- Added regression coverage for Earthdata sidecar filtering and suffix-independent NetCDF opening.

## 2026-08-08 — NSIDC-0611 v4 direct acquisition hotfix

- Replaced invalid CMR/earthaccess granule discovery for NSIDC-0611 v4 with official NSIDC DAAC HTTPS acquisition.
- Added bearer-token protected direct annual NetCDF downloads for 1984–2024.
- Added NetCDF signature validation and resume/reuse of valid annual files.
- Changed the Windows acquisition launcher to securely prompt for `EARTHDATA_TOKEN` without echoing the token.
- Added focused regression coverage for the direct NSIDC DAAC path.

## R16.2 - TEOS delta provenance hotfix (2026-08-31)

- No `climate_model.py` change from R16.1.
- Replaced the inherited Repair-R11/R13 CLI/name-only equivalence gate in the TEOS-only validation path with an exact R16-parent provenance proof.
- Bundles the exact R16 parent `climate_model.py` snapshot and verifies AST identity everywhere except the intentionally changed `validate_initial_amoc_density_margin()` function.
- Adds `run_r16_2_teos_validation.bat`; the 31 completed non-TEOS R16 experiments are not repeated.

## R18.1 - finalizer hotfix and AMOC basin diagnosis (2026-09-01)

- Fixed the R18 post-run fixed-mask finalizer to call the existing `linear_fit()` helper instead of undefined `ols()`.
- Preserved `climate_model.py` byte-for-byte from R18; no governing AMOC, sea-ice, Greenland, forcing, or conservation physics changed.
- Added a reproducible fixed-preindustrial zero-hosing AMOC fixed-point diagnosis.
- The frozen R18 equations support a weak stable branch, an unstable intermediate basin boundary, and the strong stable control branch; the R18 -0.40 Sv recovery state remained below that boundary, explaining its relapse after de-hosing ended.
- No restart switch or AMOC coefficient retuning was introduced.
