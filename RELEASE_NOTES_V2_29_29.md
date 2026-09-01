# CLEM v2.29.29

CLEM v2.29.29 is the public release of the physics-repair and validation work completed after the v2.29.28-r13 baseline. The important changes are scientific/model changes, not merely packaging.

## Main model changes

### Greenland freshwater is now a real mass input

Greenland land-ice melt is now routed as uncompensated freshwater/mass addition to the represented ocean by default. Ocean volume therefore increases and salinity dilutes while physical salt mass is conserved. Hydrological redistribution remains separate, and artificial hosing can still be run compensated or uncompensated for attribution. A switchable elevation-lapse feedback was also added.

### AMOC formulation was audited rather than simply retuned

The proposed South-Atlantic-upper-limb hydraulic source geometry was tested and rejected because it produced the wrong forced behaviour: SSP2-4.5 slightly strengthened the AMOC and freshwater hosing became much too weak. The validated interhemispheric high-latitude density contrast remains the production default; the South-Atlantic-upper geometry is retained only as a structural sensitivity.

The release adds active structural sensitivity branches for density exponent, pycnocline feedback, upper saturation and reversal. A reduced TEOS-10/GSW EOS branch and a matched-pathway TEOS branch were also tested. TEOS was markedly less sensitive to freshwater forcing than the validated linear closure, so linear alpha/beta remains the production EOS.

Collapse/recovery experiments were extended into a de-hosing map. A separate equilibrium diagnosis finds a stable weak state, an unstable separator near 12.32 Sv and the stable 17 Sv strong state in the production no-reversal configuration. This supports treating the reduced model's collapse/recovery behaviour as continuous bistability/hysteresis; no artificial restart threshold was added.

### Arctic feedback terms are now independently testable

Forced Arctic-ocean heat convergence, phase restoring and the extra unresolved lapse-rate feedback can each be disabled independently. The resulting ablation experiments confirm that all three terms are active and quantify their relative effects instead of leaving them as untested combined corrections.

Compatibility-only/dead parameters were also separated from active controls, and Atlantic gyre heat transport is now explicitly diagnostic-only rather than a hidden climate tendency.

### Sea-ice extent treatment was rebuilt

The repair line first tested a conservative subgrid threshold reconstruction and then added a mass-neutral prognostic support fraction for the unresolved ice footprint. Native concentration and latent ice volume remain the conserved/prognostic ice states; support only represents unresolved spatial occupancy.

R18 replaced the fixed support compactness with a thermodynamic pack reference, allowing cold pack to approach full support without fitting an empirical area-to-extent correction.

R18.2 then fixed the actual observation comparison: the NSIDC-style comparator now applies a 15% cell-concentration threshold consistently and March/September are sampled at the model record nearest the established mid-month target. The corrected area comparison showed that most of the apparent large area bias was an operator mismatch, not evidence that the sea-ice physics needed another retune. Corrected March/September area RMSE is about 0.45-0.56 million km² with correlations around 0.84-0.90 across the 5° and 10° historical runs.

Literal >=15% threshold extent on CLEM's coarse reconstructed cells remains resolution-limited and is not presented as satellite-resolution skill. Fractional support is retained as the reduced-order structural footprint diagnostic.

## New observational evidence

Authentic NSIDC-0611 EASE-Grid Sea Ice Age v4/v4.1 data for 1984-2024 are now integrated. All 41 annual NetCDF inputs were processed using the existing CLEM multiyear-ice definition into 82 March/September records, with source SHA-256 hashes preserved in metadata. The source package redistributes the processed diagnostic, not the raw NSIDC files.

This brings the intended Arctic observational stack to 6/6 available sources. NSIDC-0611 remains structural rather than a direct release gate because observed age class and CLEM's thickness-based mature-ice fraction are not identical physical quantities.

## Validation changes

- Prospective validation is now evidence-driven rather than controlled by a manual Boolean.
- The 2027-2036 prospective protocol is frozen in advance; current status is correctly `not_available` because those future observations do not exist yet.
- Scientific-release logic distinguishes prospective evaluation completion from prospective evaluation success.
- Sea-ice extent remains explicitly non-release-blocking at CLEM's present spatial resolution.
- CryoSat-2 temporal thickness skill remains an incomplete retrospective diagnostic; the model was not retuned merely to make that short record pass.
- Long local validation jobs are restartable and segmented into child runs of at most five model years.

## Numerical provenance

The final v2.29.29 identity was applied after the repair physics had already been numerically tested under v2.29.28 repair revisions. Those historical results keep their original filenames and embedded version labels. `V2_29_29_DYNAMICS_EQUIVALENCE.json` records that the v2.29.29 governing model is dynamically equivalent to the validated final parent apart from the active version identity, so the old runs are inherited honestly rather than relabelled.

## Public-release work

The public README and scientific references have been merged into the validated tree. `THIRD_PARTY_DATA.md` documents the observational/reanalysis inputs and their citation/licensing requirements, including NSIDC-0611. Active runtime, package, GUI, CI, launcher, validator and release-tool identity is now v2.29.29.

Independent prospective predictive validation is not claimed in this release and cannot be completed until the preregistered future holdout exists.

## Public release assets

CLEM v2.29.29 is distributed as a **multi-asset release** rather than one oversized source archive:

- `CLEM-v2.29.29-source.zip` — clean current source tree. Its SHA-256 is published in the accompanying `.sha256`/release asset manifest.
- `CLEM-v2.29.28-physics-repair-r13-validation-results.zip` — **80,553,730 bytes**, SHA-256 `3ebb04a5c6d609184f9576a77592c422e26d9956774ab0537111c2324708befb`. This is the large inherited Repair R11-R13 numerical evidence bundle. Its v2.29.28 name is preserved because that is the version that generated the evidence.
- `CLEM_v2.29.28_R17_validation_results.zip` — **44,545,789 bytes**, SHA-256 `c386edc134992a6e0ae45d8b7d0ecae1d726645729aa7ff2d03c86a09f1fd950`. This is the accepted R17 structural AMOC/TEOS-matched/recovery and paired 5°/10° sea-ice evidence bundle.
- `CLEM_v2.29.28_R18_validation_results_finalized.zip` — **29,314,682 bytes**, SHA-256 `69f0d2d8095e084e6464c291ca978417d9891d759ca0649106c6cee434dce4c8`. This is the finalized R18 structural/observation-operator validation bundle.
- `CLEM_v2.29.28_R18_2_seaice_operator_results.zip` — **25,318,048 bytes**, SHA-256 `d6506dfbec839528ad3c4e633c1563cf18c1fc6caf6dd94fd44dfe5ec36e0f06`. This contains the completed R18.2 5°/10° sea-ice observation-operator numerical comparison. Its historical version label is likewise preserved.

The raw NSIDC-0611 NetCDF archive is **not** a CLEM release asset. CLEM ships the processed diagnostic and full source-file SHA-256 provenance instead. Historical numerical assets are inherited by the explicit dynamics-equivalence record; they are not relabelled as newly generated v2.29.29 runs.


## Release hardening

- Updated legacy regression assertions that still froze superseded pre-R15 AMOC/Greenland defaults; tests now assert the final validated v2.29.29 defaults rather than forcing physics backward.
- Updated R18/R18.2 provenance tests and verifier logic to recognize the documented `MODEL_VERSION`-only identity bump through version-neutral dynamics equivalence instead of requiring the obsolete literal v2.29.28 `climate_model.py` hash.
- Clarified that `SOURCE_FINGERPRINT.json` is retained as historical/frozen repair-line provenance; `V2_29_29_RELEASE_TREE_FINGERPRINT.json` is the current release-tree identity.
- Removed transient pytest/bytecode caches from public packaging and re-audited path, case, archive and manifest safety.
- Post-merge bounded verification records **54 passing tests with zero failures** across current-release semantics, coupled fail-closed behavior, repaired-default/provenance assertions, six-source Arctic handling, and target/baseline safety, plus a passing zero-year static physics check. The full canonical runner is still pinned to `pytest==9.1.1`; this assistant environment has 9.0.2 and could not install 9.1.1 offline, so no false canonical pass is claimed.
