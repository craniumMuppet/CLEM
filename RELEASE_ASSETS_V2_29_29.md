# CLEM v2.29.29 release assets

## Public release assets

CLEM v2.29.29 is distributed as a **multi-asset release** rather than one oversized source archive:

- `CLEM-v2.29.29-source.zip` — clean current source tree. Its SHA-256 is published in the accompanying `.sha256`/release asset manifest.
- `CLEM-v2.29.28-physics-repair-r13-validation-results.zip` — **80,553,730 bytes**, SHA-256 `3ebb04a5c6d609184f9576a77592c422e26d9956774ab0537111c2324708befb`. This is the large inherited Repair R11-R13 numerical evidence bundle. Its v2.29.28 name is preserved because that is the version that generated the evidence.
- `CLEM_v2.29.28_R17_validation_results.zip` — **44,545,789 bytes**, SHA-256 `c386edc134992a6e0ae45d8b7d0ecae1d726645729aa7ff2d03c86a09f1fd950`. This is the accepted R17 structural AMOC/TEOS-matched/recovery and paired 5°/10° sea-ice evidence bundle.
- `CLEM_v2.29.28_R18_validation_results_finalized.zip` — **29,314,682 bytes**, SHA-256 `69f0d2d8095e084e6464c291ca978417d9891d759ca0649106c6cee434dce4c8`. This is the finalized R18 structural/observation-operator validation bundle.
- `CLEM_v2.29.28_R18_2_seaice_operator_results.zip` — **25,318,048 bytes**, SHA-256 `d6506dfbec839528ad3c4e633c1563cf18c1fc6caf6dd94fd44dfe5ec36e0f06`. This contains the completed R18.2 5°/10° sea-ice observation-operator numerical comparison. Its historical version label is likewise preserved.

The raw NSIDC-0611 NetCDF archive is **not** a CLEM release asset. CLEM ships the processed diagnostic and full source-file SHA-256 provenance instead. Historical numerical assets are inherited by the explicit dynamics-equivalence record; they are not relabelled as newly generated v2.29.29 runs.

