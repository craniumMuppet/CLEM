# v2.29.26 Arctic observational recalibration release

## Purpose

v2.29.26 finalizes the 2026-08-11 Arctic observational recalibration as a coherent release. The prior tree contained the new calibration and repaired observation files while still identifying itself as v2.29.25 and had stale release-integrity/scientific-evidence regressions.

## Integrated repaired evidence

The supplied PIOMAS/OSI SAF repair transfer is authoritative for seven processed files under `data/validation/sea_ice_physical/` and `data/validation/sea_ice_crosscheck/osi_saf_osi450a1/`. v2.29.26 integrates those files byte-for-byte and pins their hashes in `tests/test_v22926_release_finalization.py`.

## Selected Arctic defaults

- new-ice local thickness: **0.23 m**
- full-cover equivalent thickness: **3.70 m**
- concentration exponent: **0.50**
- basal ocean exchange: **6.0 W m-2 K-1**
- forced Arctic ocean heat-convergence onset: **2.0 C**

## Preserved scientific result

The scientific result is unchanged from `ARCTIC_OBSERVATIONAL_RECALIBRATION_2026.md`: G02202 calibration and 2021-2025 development gates pass, PIOMAS/CryoSat-2/ICESat-2 physical gates pass, OSI SAF March passes, and OSI SAF September fails the independent 1.0 M km2 RMSE gate at about 1.125 M km2.

Scientific predictive validation remains **incomplete/fail-closed** because NSIDC-0611 is pending and nested fold-specific historical hindcasts were not run. No v2.29.26 release metadata upgrades those development/calibration results into an independent predictive claim.

## Engineering repairs

- synchronized `MODEL_VERSION`, package metadata, README, changelog, setting guide, scientific constraints, and current-version tests to v2.29.26;
- bumped the Arctic periodic-reference identity so cached/reference provenance cannot masquerade as the previous version;
- corrected stale `scientific_evidence.py` statements that claimed fixed-mask area and independent volume/thickness evidence were not bundled;
- retained historical v2.29.25 evidence files as provenance rather than rewriting them.
