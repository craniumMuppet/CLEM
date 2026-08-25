# Six-source Arctic validation integration — 2026

This patch extends the earlier scientific-review fix into a six-product Arctic evidence stack and adds explicit source-specific observation operators.

## Integrated products

1. NOAA/NSIDC G02202 v6 — primary fixed-mask concentration-derived area.
2. PIOMAS v2.1 — common-domain monthly volume constraint from gridded `heff`.
3. CryoSat-2 RDEFT4 v1 — development-informed satellite thickness constraint.
4. ICESat-2 IS2SITMOGR4 v4 — development-informed satellite thickness constraint.
5. EUMETSAT OSI SAF OSI-450-a1 v3.1 — cross-dataset development area diagnostic; not independent validation.
6. NSIDC-0611 v4 — multiyear-ice structural diagnostic.

## Scientific separation

The stack is intentionally not one blended objective. G02202 is the primary area calibration target. PIOMAS constrains volume. CryoSat-2 and ICESat-2 are scored separately as satellite thickness constraints. Both satellite products and OSI SAF were inspected during method development; none is labelled independent validation. Sea-ice age is a structural diagnostic rather than a thickness observation.

Every spatial product now carries an explicit observation operator. EGCM is sampled on the same retained observation-cell centers and integrated or averaged with the same observation-cell areas/record weights used to construct the target. A processed CSV without the required operator is not accepted as scientific evidence.

## Items 1–4 correction

- **G02202 fixed-mask area:** the permanent support is constructed from the ancillary ocean mask while excluding the largest historical SMMR pole-hole footprint. The exact support is saved as `MODEL_OBSERVATION_OPERATOR.npz` and applied to EGCM at scoring time.
- **NSIDC-0611 ice age:** only integer age classes 1–16 count as sea ice; multiyear ice is 2–16. Codes 20 (land) and 21 (age not calculated) are excluded.
- **CryoSat-2 / ICESat-2 thickness:** each monthly record stores its own concentration × cell-area weighting. EGCM local thickness is sampled at the same cells and averaged with those exact weights. ICESat-2 uses the primary `ice_thickness` field before any interpolated fallback and limits the comparison to <=88°N.
- **PIOMAS volume:** the scalar published volume series is no longer accepted as the validation target. The acquisition path uses gridded monthly `heff` and PIOMAS grid metrics to construct a common >=60°N ocean support. PIOMAS and EGCM are integrated over those same cells and cell areas.

## Acquisition and transfer

`tools/acquire_arctic_validation_stack.py` acquires/processes the products. `tools/acquire_arctic_validation_stack.ps1` is the Windows workflow. `tools/export_arctic_validation_bundle.py` exports only model-ready evidence/operator/provenance files, excluding raw NetCDF/HDF5 data and credentials.

The source archive used to build this patch does not contain the raw files needed to construct the new spatial operators. The legacy scalar PIOMAS CSV remains only as provenance and no longer counts as available. Consequently the corrected validation stack currently reports 0/6 sources rather than accepting mismatched evidence.

## Validation status

All five present products pass file and observation-operator integrity checks. Mean-state PIOMAS/CryoSat-2/ICESat-2 gates pass, but full temporal volume/thickness validation remains incomplete because the CryoSat-2 correlation gate fails. NSIDC-0611 is still absent, retrospective fold-local development evaluation does not establish independent predictive skill, and the reserved untouched prospective period begins in 2027.
