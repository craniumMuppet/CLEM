# Arctic validation bundle review and data-processing repair — 2026-08-09

## Uploaded bundle

The user-supplied `ARCTIC_VALIDATION_DATA_BUNDLE.zip` completed the CORE5 acquisition workflow and contained processed evidence plus explicit observation operators for:

- NOAA/NSIDC G02202 v6 fixed-mask March/September sea-ice area
- PIOMAS v2.1 common-domain volume
- CryoSat-2 RDEFT4 v1 March thickness
- ICESat-2 IS2SITMOGR4 v4 March thickness
- OSI SAF OSI-450-a1 v3.1 independent March/September area cross-check

NSIDC-0611 sea-ice age remains optional/pending.

Uploaded bundle SHA-256: `e01d7abb6aa2841a9be2ba021917026ea1cf6ef3568284224d2160f0be1b25df`.

## Data-processing defects found before recalibration

### 1. OSI SAF projected-coordinate units

The imported OSI SAF operator contained 97,777 cells but only 61.110625 km2 of total support, with each nominal 25 km EASE2 cell recorded as 0.000625 km2. The processing code had treated x/y coordinates expressed in kilometres as metres.

Fix:

- projected coordinate units are now read from the coordinate metadata;
- kilometre x/y axes are converted to metres before projection/geolocation and area calculation;
- a 25 km equal-area cell therefore evaluates to 625 km2;
- source availability now fails closed if OSI cell areas are catastrophically small.

### 2. OSI SAF temporal sampling

The raw directory produced by earlier acquisition attempts can contain both official monthly files and daily files. The generic processor previously accepted all of them and de-duplicated year/month records by keeping the last filename, which can select an end-of-month daily field instead of the monthly mean.

Fix:

- OSI processing now accepts official monthly-mean files only;
- daily files are explicitly rejected as substitutes for monthly means;
- processed metadata must declare `temporal_sampling = official_monthly_mean_files_only` or the source fails closed.

### 3. PIOMAS gridded volume background/unit failure

The imported PIOMAS common-domain series was approximately 0.86–0.88 million km3, whereas the project's official PSC scalar total-volume table is of order 0.004–0.033 million km3. The imported gridded series therefore contains a decisive nonphysical background/unit error and is not accepted for calibration.

Fix:

- acquisition now selects PSC's official `heff.H<yyyy>.gz` flat-binary single-precision files rather than the later `.nc.gz` conversion;
- byte order is detected fail-closed;
- PIOMAS scalar-grid cell metrics follow PSC's `heff_for_volume.f` construction:
  - `DXT = 0.5 * (HTN + next-j HTN)`
  - `DYT = 0.5 * (HTE + next-i HTE)`
  - cell area = `DXT * DYT` km2;
- the common-domain integral remains >=60N and the identical operator is applied to EGCM;
- the published scalar PIOMAS total-volume series is used only as a broad unit/background sanity check, never as the common-domain calibration target;
- any common-domain volume above 0.1 million km3 fails closed.

## Current trusted status after review

Until PIOMAS and OSI SAF are refreshed with the corrected processor, the trusted sources are:

- G02202 v6: available
- CryoSat-2 RDEFT4 v1: available
- ICESat-2 IS2SITMOGR4 v4: available

Temporarily rejected/pending:

- PIOMAS v2.1: rejected until corrected flat-binary refresh
- OSI SAF OSI-450-a1: rejected until corrected official-monthly refresh
- NSIDC-0611 v4: optional structural diagnostic pending

The core-five scientific gate therefore remains closed, deliberately.

## One-click correction

Run `RUN_PIOMAS_OSI_REFRESH.cmd` from the project root. This refresh:

1. requires no Earthdata token or password;
2. downloads/reprocesses only public PIOMAS and OSI SAF evidence;
3. leaves G02202, CryoSat-2, and ICESat-2 evidence untouched;
4. runs the data-processing regression tests;
5. exports `ARCTIC_VALIDATION_DATA_BUNDLE_CORRECTED.zip` only if the corrected core-five stack passes availability/sanity checks.

## Verification

Focused regression command:

```text
python -m pytest -q tests/test_2026_arctic_data_processing_repairs.py tests/test_six_source_arctic_validation_stack.py tests/test_arctic_core5_nonblocking_acquisition.py tests/test_2026_sea_ice_scientific_review_fixes.py
```

Result: **33 passed**.

A 10-degree 1850–2027 historical climate-model baseline was also attempted after the data review, but it exceeded the execution window before completion. No historical skill result is claimed from that incomplete run.
