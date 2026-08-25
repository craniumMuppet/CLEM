# Arctic sea-ice volume/thickness validation inputs

The physical evidence streams are source-separated:

- `piomas_volume_monthly.csv` + `piomas_v2_1_metadata.json` — PIOMAS v2.1 monthly Arctic volume.
- `cryosat2_rdeft4_monthly.csv` + `cryosat2_rdeft4_v1_metadata.json` — CryoSat-2 RDEFT4 v1 March mean thickness.
- `icesat2_is2sitmogr4_monthly.csv` + `icesat2_is2sitmogr4_v4_metadata.json` — ICESat-2 IS2SITMOGR4 v4 March mean thickness.
- `SOURCES.json` — processed evidence manifest.

PIOMAS supplies the long historical volume constraint. CryoSat-2 and ICESat-2
are independent satellite-era thickness checks. Their observations are not
merged or averaged before scoring.

Run `python tools/acquire_arctic_validation_stack.py --all` to populate the
complete stack. Missing source data or missing provenance metadata keeps the
physical scientific gate closed.
