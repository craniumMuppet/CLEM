# NSIDC-0611 v4 acquisition fix — 2026-08-08

## Failure diagnosed

The six-source acquisition reached the final NSIDC sea-ice-age source and failed because `earthaccess.search_data(short_name="NSIDC-0611", version="4")` returned no granules.

This is a catalog/distribution mismatch rather than a missing dataset. NASA CMR lists EASE-Grid Sea Ice Age Version 4 (`NSIDC-0611`) but marks the collection directory as **No Granules**. NSIDC's current product page instead documents programmatic access through the NSIDC DAAC HTTPS file system. Therefore `earthaccess.search_data()` is not a valid discovery mechanism for this collection.

## Fix

`tools/acquire_arctic_validation_stack.py` now:

- acquires NSIDC-0611 directly from the official NSIDC DAAC HTTPS archive;
- uses `EARTHDATA_TOKEN` only as an in-memory `Authorization: Bearer` header;
- uses the official annual v4.1 NetCDF naming convention from 1984 through 2024;
- validates every downloaded payload as NetCDF/NetCDF-4 before processing;
- reuses already-downloaded valid annual files;
- rejects redirects back to Earthdata Login as an authentication failure;
- keeps the corrected `1..16` ice-age classes, excluding `20` (land) and `21` (age not calculated).

`tools/acquire_arctic_validation_stack.ps1` now prompts for the token with `Read-Host -AsSecureString` when `EARTHDATA_TOKEN` is absent, so the token is not echoed into normal PowerShell output.

## Scientific behavior unchanged

This hotfix changes only data acquisition. The observation-operator fixes remain unchanged:

- fixed-mask G02202 calibration support;
- common-domain gridded PIOMAS volume;
- source-specific CryoSat-2/ICESat-2 thickness operators;
- OSI SAF as an untuned cross-check;
- NSIDC sea-ice age as a structural multiyear-ice diagnostic.

## Resume behavior

A rerun of `tools/acquire_arctic_validation_stack.ps1` reuses valid raw files already downloaded by previous attempts. It does not require restarting the five successful acquisition paths from zero.
