# Arctic validation acquisition hotfix — 2026-08-08

## Failure addressed

The Windows acquisition run reached NASA Earthdata successfully but failed while opening an ICESat-2 IS2SITMOGR4 v4 download with xarray backend auto-detection.

IS2SITMOGR4 v4 is distributed as NetCDF-4. The acquisition path previously trusted every path returned by `earthaccess.download()` and passed it directly to `xarray.open_dataset()` without verifying that the returned path was the scientific NetCDF payload.

## Fix

`tools/acquire_arctic_validation_stack.py` now:

1. obtains Earthdata granule data links explicitly;
2. selects only `.nc`, `.nc4`, or `.cdf` scientific payload links;
3. verifies the downloaded file signature before processing;
4. accepts both classic NetCDF (`CDF`) and NetCDF-4/HDF5 signatures;
5. opens NetCDF-4 explicitly with `netcdf4` and then `h5netcdf` fallback;
6. opens classic NetCDF explicitly with `netcdf4` and then `scipy` fallback;
7. rejects HTML, XML, browse imagery, or other sidecars with an actionable error;
8. allows `--process-existing` to discover already-downloaded valid NetCDF files by signature rather than filename alone.

No change was made to the six-source scientific roles or the Items 1–4 observation operators.

## Regression results

- `python -m compileall -q .`: PASS
- `tests/test_six_source_arctic_validation_stack.py`: 13 passed
- `tests/test_2026_sea_ice_scientific_review_fixes.py` + `tests/test_sea_ice_actual_fix.py`: 12 passed
- targeted `tests/test_v2299_scientific_review_fixes.py`: 2 passed
- total confirmed focused tests: 27 passed, 0 failed

## Windows continuation

From the project root, rerun:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\tools\acquire_arctic_validation_stack.ps1
```

Existing raw files are reused where the download client recognizes them, and the script continues acquisition/processing. When all six sources are operator-complete, it writes `ARCTIC_VALIDATION_DATA_BUNDLE.zip` in the project root.
