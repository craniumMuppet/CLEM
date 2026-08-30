# v2.29.27 Arctic validation and release integrity

## Scientific changes

- Selected Arctic defaults: 0.22 m young ice, 0.60 concentration exponent, 49.5 W/m2 nonsolar ice-surface loss.
- OSI SAF September RMSE: 0.932 M km2, passing the 1.0 gate.
- PIOMAS common-domain volume nRMSE: 0.245834, passing the 0.25 gate with more margin than v2.29.26.
- CryoSat-2 and ICESat-2 normalized-RMSE gates remain passing.
- Retrospective nested hindcasts were scored and fail the required all-baseline predictive-skill condition.
- NSIDC-0611 remains unavailable; untouched prospective validation begins in 2027.

## Integrity changes

- Runtime validation now rejects processed observational evidence whose metadata SHA-256 does not match the packaged file.
- The tested fingerprint includes the canonical recalibration JSON, nested-hindcast manifest, HadCRUT baseline, runtime data, tests, tools, configuration and source.
- Finalization verifies that fingerprint immediately before packaging.
- Package scientific booleans are derived from packaged evidence rather than hard-coded.
- Test evidence records the Python/pytest versions, exact commands and exact selected pytest node IDs.
- The declared pytest test dependency is synchronized to the verified release environment (`pytest==9.0.2`).
