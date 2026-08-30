# NSIDC-0611 legacy Earthdata authentication fix — 2026

## Failure reproduced from the Windows acquisition log

The six-source acquisition reached the NSIDC-0611 sea-ice-age stage and failed because the legacy `daacdata.apps.nsidc.org` server redirected the bearer-token request to Earthdata Login. The previous downloader treated that redirect as an invalid token.

## Root cause

NSIDC-0611 Version 4 is served from the legacy NSIDC DAAC HTTPS archive rather than the Earthdata Cloud granule path used by CryoSat-2 and ICESat-2. NASA's documented access pattern for this legacy server uses Earthdata Login username/password authentication with session cookies. The annual NetCDF files are located in the archive's `data/` subdirectory.

## Fix

- Keep `EARTHDATA_TOKEN` for Earthdata Cloud products.
- Prompt separately for `EARTHDATA_USERNAME` and `EARTHDATA_PASSWORD` for NSIDC-0611.
- Keep all three credentials only in the current PowerShell/Python process; do not write them into the project.
- Use Python's in-memory `HTTPPasswordMgrWithDefaultRealm`, `HTTPBasicAuthHandler`, `HTTPCookieProcessor`, and `CookieJar` for the legacy NSIDC archive.
- Reuse the cookie-authenticated opener across the annual NSIDC-0611 downloads.
- Correct the NSIDC-0611 base path to `.../nsidc0611_seaice_age_v4/data/`.
- Continue validating every downloaded annual file as NetCDF before accepting it.
- Reuse already-downloaded valid raw files.

## Verification

- `tests/test_six_source_arctic_validation_stack.py`: 17 passed.
- `tests/test_2026_sea_ice_scientific_review_fixes.py` + `tests/test_sea_ice_actual_fix.py`: 12 passed.
- Python compilation of the acquisition script: passed.
- The older `test_v2299_scientific_review_fixes.py` was started but exceeded the execution window before completion; no failure was emitted before timeout.
