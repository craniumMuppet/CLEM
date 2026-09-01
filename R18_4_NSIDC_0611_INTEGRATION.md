# CLEM v2.29.28 R18.4 NSIDC-0611 data integration

## Bottom line

Authentic NSIDC-0611 v4/v4.1 sea-ice-age files supplied by the user have been processed and integrated. The Arctic observational stack is now **6/6 available**. This is a data/evidence update only: governing CLEM physics is unchanged and no climate integration is required. Independent predictive scientific validation remains **not_available** until the frozen 2027-2036 prospective holdout exists.

## NSIDC-0611 evidence

- Annual NetCDF files: **41** (1984-2024, no missing years).
- Dataset: NSIDC-0611, Version 4, annual files revision v4.1.
- DOI: `10.5067/UTAV7490FEPB`.
- Processing: existing CLEM definition; valid ice-age categories 1-16, multiyear categories 2-16, land=20 and unclassified=21 excluded; weekly March/September fractions averaged by year/month.
- Processed records: **82**.
- Processed CSV SHA-256: `06ab7be731d77a02ef92f95fb5f9c88225fe7dd16a6424e497551d48ba95adca`.
- Metadata SHA-256: `8371a8c11695cc7c79324323f8c9b47936e6b50069cda0bb9ef021f3a466f07d`.
- All 41 source-file SHA-256 values are recorded in `METADATA.json`.

Observed multiyear-ice fraction trend (structural diagnostic only):
- March: -0.0637 fraction/decade; 1984=0.445, 2024=0.221.
- September: -0.0529 fraction/decade; 1984=0.855, 2024=0.785.

## Verification

- `validation_stack_status()`: all six products available; missing sources = none.
- Focused regression suite after state transition: **26/26 passed**.
- No governing physics source changed.
- Raw NetCDF files are not redistributed in the source ZIP; the processed products plus complete source hashes/provenance are included.

## Scientific interpretation

NSIDC-0611 is an independent structural diagnostic. CLEM compares observed multiyear-ice fraction with the fraction of prognostic ice area having local thickness >=2 m. These are related but not physically identical, so this source does not become a direct RMSE release gate and does not make retrospective evidence prospective.
