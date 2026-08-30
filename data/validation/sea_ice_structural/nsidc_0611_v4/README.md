# NSIDC-0611 v4 sea-ice-age structural diagnostic

The processed file `multiyear_ice_annual.csv` reports March and September
multiyear-ice fraction derived from weekly EASE-Grid Sea Ice Age Version 4.
`METADATA.json` records source version, hashes, and processing choices.

EGCM compares this with the fraction of prognostic ice area whose local
thickness is at least 2 m. These quantities are related but not identical, so
the comparison is structural only and is not a direct RMSE release gate.
