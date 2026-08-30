# Items 1–4 Arctic observation-operator fixes — 2026-08-08

## Result

Items 1–4 from the scientific review are implemented in the active validation path. The corrected validation design now requires source-specific spatial observation operators rather than comparing processed observations to a generic full-domain EGCM scalar.

## 1. G02202 fixed-mask area is now like-for-like

- The G02202 v6 ancillary file is mandatory.
- The support is restricted to `surface_type == 50` ocean cells.
- Cells carrying the Nimbus-7 SMMR pole-hole bit are permanently excluded, so the largest historical pole hole defines the common pole support.
- The retained support is further intersected across all processed March/September records so it is time invariant.
- The exact retained cell centers and cell areas are saved in `data/validation/sea_ice_fixed_mask/MODEL_OBSERVATION_OPERATOR.npz`.
- `sea_ice_validation.py` samples EGCM concentration at those exact observation-cell centers and calculates the 15%-thresholded area with the identical observation-cell areas.
- Full-Northern-Hemisphere EGCM area remains a process diagnostic and is not used as the G02202 score.

## 2. NSIDC-0611 categorical handling is corrected

`tools/acquire_arctic_validation_stack.py::ice_age_masks()` now accepts only integer sea-ice-age classes 1–16. Multiyear ice is classes 2–16. Codes 20 and 21 are excluded from both numerator and denominator. The processed metadata records the categorical contract explicitly.

## 3. CryoSat-2 and ICESat-2 use source-specific thickness operators

- Each accepted March satellite record saves its exact valid retrieval footprint and `concentration × cell_area` weights.
- EGCM local thickness is sampled at the identical satellite cell centers for that record and averaged with the identical weights.
- CryoSat-2 keeps its own retrieval/concentration support.
- ICESat-2 prefers the primary `ice_thickness` field before interpolated fallback fields and restricts the comparison operator to <=88°N.
- The two satellite products remain independent checks and are never merged into one synthetic target.

## 4. PIOMAS volume uses a common gridded domain

- The old published scalar PIOMAS total-volume series is no longer accepted as the validation target.
- Acquisition now uses annual gridded monthly `heff.H<year>.nc(.gz)` files plus the PIOMAS grid/mask utilities.
- A fixed PIOMAS ocean support at >=60°N is constructed and saved as `piomas_common_domain_operator.npz`.
- PIOMAS `heff` is integrated over that support with PIOMAS grid-cell areas.
- EGCM equivalent thickness is sampled at the same PIOMAS cell centers and integrated with the same cell areas.

## Validation rerun

### Software/regression evidence

Confirmed after the final edits:

- `tests/test_six_source_arctic_validation_stack.py`: 10/10 passed.
- `tests/test_2026_sea_ice_scientific_review_fixes.py` + `tests/test_sea_ice_actual_fix.py`: 12/12 passed.
- Targeted historical-label compatibility tests: 2/2 passed.
- Total confirmed focused tests: **24/24 passed**.
- Modified modules compile cleanly with `compileall`.

### Data-validation gate rerun

`tools/acquire_arctic_validation_stack.py --process-existing` was rerun. The corrected gate reports **0/6 currently available products** because this package does not contain the raw files needed to build the new exact observation operators:

- G02202: missing v6 ancillary pole-hole file.
- PIOMAS: missing gridded `heff.H<year>.nc(.gz)` inputs.
- CryoSat-2: no usable March raw thickness records present.
- ICESat-2: no usable March raw thickness records present.
- OSI SAF: no March/September raw concentration fields present.
- NSIDC-0611: no March/September raw ice-age records present.

This 0/6 result is intentional and stricter than the previous package: the legacy scalar PIOMAS CSV and any processed scalar without its matching operator cannot make a source appear valid.

The machine-readable rerun is stored in `ARCTIC_VALIDATION_STACK_STATUS_2026.json`; the processing messages are recorded in the accompanying validation evidence outside the project archive during this build.

### Long historical runner

The 10° historical validation runner was started successfully, but the complete integration did not finish within the execution window here. No historical skill result is claimed from that incomplete run. More importantly, with 0/6 operator-complete observational products the scientific gate correctly remains closed before recalibration.

## Next required action

Run `tools/acquire_arctic_validation_stack.ps1` on a machine with network access and local Earthdata authentication. It will download/process the raw products and build the new observation operators. After that, rerun calibration and the validation framework using those operator-complete datasets.
