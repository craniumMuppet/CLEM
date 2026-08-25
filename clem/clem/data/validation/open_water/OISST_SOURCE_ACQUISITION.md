# OISST source acquisition and hashing

Run the following command in a networked release environment:

```text
python tools/acquire_oisst_provenance.py --work-dir <temporary-download-directory>
```

The command downloads the two official NOAA PSL climatology files, verifies the
catalogue-reported byte sizes, records SHA-256 hashes, runs the deterministic
model-mask processor, and writes both the processed JSON and source manifest.
The original NetCDF files are not redistributed.

A release may claim source-level OISST reproducibility only when both generated
JSON files are included and their hashes are covered by the package manifest.
