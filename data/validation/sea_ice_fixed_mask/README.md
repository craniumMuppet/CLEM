# Primary fixed-mask sea-ice area calibration

The primary target is generated from NOAA/NSIDC G02202 Version 6 gridded monthly sea-ice concentration. The acquisition tool constructs an explicit permanent Northern Hemisphere support from the G02202 ancillary masks: ocean cells are retained and every cell inside the Nimbus-7 SMMR pole-hole bit is excluded. March and September are then restricted to the same finite support and evaluated with a 15% concentration threshold.

Required processed files:

- `N_03_fixed_mask.csv`
- `N_09_fixed_mask.csv`
- `MODEL_OBSERVATION_OPERATOR.npz`
- `METADATA.json`

Each CSV contains `year,area,extent,source`; scientific calibration uses `area`. `MODEL_OBSERVATION_OPERATOR.npz` contains the exact retained observation-cell centers and cell areas. EGCM concentration is sampled on those same cells at runtime before area is integrated. Therefore a CSV without its matching operator is invalid scientific evidence.

The coarse full-domain EGCM extent remains diagnostic-only and is not made into an observation-equivalent quantity through fitted multipliers.

`METADATA.json` must declare `fixed_mask=true`, `concentration_threshold=0.15`, identify the runtime exact-support observation operator, and contain source/output provenance hashes. Raw Sea Ice Index area is never substituted when these files are absent.
