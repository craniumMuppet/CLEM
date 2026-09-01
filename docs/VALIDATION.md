# Coupled Low-complexity Earth Model v2.29.29 validation summary

CLEM v2.29.29 retains the numerically validated physics lineage established by Repair R11/R12/R13 and subsequently audited through the R15-R18 structural-validation work. R18.3-R18.5 are no-physics-change release/data/documentation maintenance revisions.

## Headline verified results

- Equilibrium ECS: **3.273 °C**
- TCR: **1.923 °C**
- Forced energy-closure residual: **0.0435%**
- SSP2-4.5 2081-2100 warming: **2.671 °C at 10°; 2.655 °C at 5°**
- SSP2-4.5 AMOC decline: **41.87% at 10°; 38.60% at 5°**
- 100-year hosing final AMOC: **13.78 Sv at 0.1 Sv, 9.51 Sv at 0.2 Sv, 4.13 Sv at 0.3 Sv**
- 0.5 Sv hosing reaches the collapsed branch with an approximately **-3.12 °C** short-term North Atlantic cold anomaly
- Pycnocline volume imbalance converges to approximately **5.7e-7 Sv**
- Salt conservation passes to reported precision

## Public release assets

CLEM v2.29.29 is distributed as a **multi-asset release** rather than one oversized source archive:

- `CLEM-v2.29.29-source.zip` — clean current source tree. Its SHA-256 is published in the accompanying `.sha256`/release asset manifest.
- `CLEM-v2.29.28-physics-repair-r13-validation-results.zip` — **80,553,730 bytes**, SHA-256 `3ebb04a5c6d609184f9576a77592c422e26d9956774ab0537111c2324708befb`. This is the large inherited Repair R11-R13 numerical evidence bundle. Its v2.29.28 name is preserved because that is the version that generated the evidence.
- `CLEM_v2.29.28_R17_validation_results.zip` — **44,545,789 bytes**, SHA-256 `c386edc134992a6e0ae45d8b7d0ecae1d726645729aa7ff2d03c86a09f1fd950`. This is the accepted R17 structural AMOC/TEOS-matched/recovery and paired 5°/10° sea-ice evidence bundle.
- `CLEM_v2.29.28_R18_validation_results_finalized.zip` — **29,314,682 bytes**, SHA-256 `69f0d2d8095e084e6464c291ca978417d9891d759ca0649106c6cee434dce4c8`. This is the finalized R18 structural/observation-operator validation bundle.
- `CLEM_v2.29.28_R18_2_seaice_operator_results.zip` — **25,318,048 bytes**, SHA-256 `d6506dfbec839528ad3c4e633c1563cf18c1fc6caf6dd94fd44dfe5ec36e0f06`. This contains the completed R18.2 5°/10° sea-ice observation-operator numerical comparison. Its historical version label is likewise preserved.

The raw NSIDC-0611 NetCDF archive is **not** a CLEM release asset. CLEM ships the processed diagnostic and full source-file SHA-256 provenance instead. Historical numerical assets are inherited by the explicit dynamics-equivalence record; they are not relabelled as newly generated v2.29.29 runs.


## v2.29.29 evidence inheritance

The v2.29.29 release version bump changes release identity and public-release metadata, not governing dynamics. Numerical result files generated as v2.29.28 retain their original names and embedded version metadata. `V2_29_29_DYNAMICS_EQUIVALENCE.json` records the exact carry-forward basis; the old evidence is not renamed or represented as a new numerical run.

## R15-R18 structural and observational follow-up

The R15–R18.5.1 repair/validation line audited and tested coherent AMOC water-mass geometry, a reduced TEOS-10 sensitivity branch, AMOC closure/hysteresis sensitivity, Greenland freshwater routing, parameter activity, Arctic mechanism ablations, and sea-ice spatial/observation-operator behavior. Those completed changes are consolidated into the v2.29.29 public release.

The completed R18.2 sea-ice operator comparison shows that the corrected >=15% native-cell **area** mean state is close to observations at 5° (March bias +0.355 M km²; September bias -0.055 M km²). Literal >=15% coarse-cell **extent** is resolution-limited and is not treated as a satellite-resolution prediction. The fractional-support extent diagnostic remains a reduced-order, non-release-blocking structural diagnostic.

## Arctic observational stack

R18.4 completes the intended six-source observational stack:

1. NOAA/NSIDC fixed-mask sea-ice concentration/area
2. PIOMAS sea-ice volume
3. CryoSat-2 sea-ice thickness
4. ICESat-2 sea-ice thickness
5. OSI SAF sea-ice concentration/area cross-check
6. NSIDC-0611 v4/v4.1 EASE-Grid Sea Ice Age structural diagnostic

Authentic NSIDC-0611 annual NetCDF inputs for **1984-2024** were processed into March/September multiyear-ice fractions. The processed file and metadata contain source-file SHA-256 provenance.

CryoSat-2 temporal correlation remains a documented development limitation. It is not used as a reason for post-hoc tuning.

## Independent prospective validation

The preregistered **2027-2036** prospective holdout is intentionally future evidence. Until the required observations exist, the correct status is **`not_available`**, not failed and not passed. Retrospective/development evidence must not be substituted for this holdout.

See `R18_2_RESULTS_REVIEW.md`, `R18_4_NSIDC_0611_INTEGRATION.md`, `R18_5_PUBLIC_RELEASE_MERGE.md`, and `validation/prospective/`.
