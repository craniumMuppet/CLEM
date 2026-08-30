# Six-source Arctic observational validation stack

EGCM uses six observational/reanalysis products with deliberately separate roles and source-specific observation operators.

| Source | Role | Calibration? | Required observation operator |
|---|---|---|---|
| NOAA/NSIDC G02202 v6 | Primary homogeneous March/September sea-ice area | Yes | Permanent G02202 ocean/pole-hole support |
| PIOMAS v2.1 | Long-record sea-ice volume constraint | Yes | PIOMAS common-domain ocean grid |
| CryoSat-2 RDEFT4 v1 | Development-informed satellite thickness constraint | No | Record-specific satellite retrieval weights |
| ICESat-2 IS2SITMOGR4 v4 | Development-informed satellite thickness constraint | No | Record-specific satellite retrieval weights |
| EUMETSAT OSI SAF OSI-450-a1 v3.1 | Untuned area/concentration cross-check | No | Independent OSI SAF fixed support |
| NSIDC-0611 v4 | Multiyear-ice structural diagnostic | No | Categorical diagnostic; no thickness equivalence |

The raw NSIDC Sea Ice Index `area` column is not a target. G02202 area is reconstructed from gridded concentration on a permanent support that excludes the largest historical SMMR pole-hole footprint. The same saved support is applied to EGCM before any area score is calculated. OSI SAF has its own independent fixed support and is never used for tuning.

PIOMAS validation uses gridded `heff` (volume per unit area), not the published scalar total-volume series. A common PIOMAS ocean support at >=60°N is saved and EGCM equivalent thickness is sampled at the same cell centers and integrated with the same PIOMAS cell areas.

CryoSat-2 and ICESat-2 are scored separately. Each accepted satellite record stores its exact concentration × cell-area weights. EGCM local thickness is evaluated at the identical cell centers with the identical weights. ICESat-2 prefers the primary `ice_thickness` field and restricts the operator to <=88°N.

NSIDC sea-ice age uses classes 1–16 as valid ice and classes 2–16 as multiyear ice. Codes 20 (land) and 21 (age not calculated) are explicitly excluded. Sea-ice age is not equated numerically with model thickness.

## Acquisition

On Windows, from the project directory:

```powershell
powershell -ExecutionPolicy Bypass -File tools/acquire_arctic_validation_stack.ps1
```

Or manually:

```bash
python -m pip install -r requirements-validation-data.txt
python tools/acquire_arctic_validation_stack.py --all
python tools/export_arctic_validation_bundle.py
```

NASA/NSIDC DAAC products may trigger a local Earthdata Login prompt. The script uses `earthaccess.login(..., persist=False)` and does not write credentials into the project.

If raw files were downloaded manually, place them in the corresponding `data/validation/raw_observations/<source>/` directory and run:

```bash
python tools/acquire_arctic_validation_stack.py --process-existing
```

The scientific gate fails closed until the required processed evidence, matching observation operators, and provenance metadata are present; the primary calibration gates and independent cross-check pass; and nested historical hindcasts are complete.
