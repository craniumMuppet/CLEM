# NOAA OISST Arctic open-water sanity-check provenance

`NOAA_OISST_ARCTIC_BENCHMARKS.json` defines only broad temperature plausibility
bounds for the model's reduced Atlantic and non-Atlantic Arctic open-water
states. The ranges were inspected during v2.29.7 retuning. Passing them is therefore a **tuning-informed development check**, not independent or quantitative regional validation.

The processor now imports the same smooth fractional Atlantic-basin mask used
by `climate_model.py`; the former 60°W–90°E wedge has been removed. It records
SHA-256 hashes for both source files and for the model/processor source, sector
area weights, monthly means, and JJA/September summaries.

Download, hash, and process the two official NOAA climatology files with:

```text
python tools/acquire_oisst_provenance.py --work-dir ./oisst-source-files
```

The lower-level processor remains available for already downloaded files:

```text
python tools/process_noaa_oisst_arctic_benchmarks.py --sst sst.ltm.1991-2020.nc --ice icec.ltm.1991-2020.nc --output oisst_arctic_processed.json
```

The NOAA NetCDF files are not redistributed in this archive. Consequently,
the packaged record explicitly says that source hashes and a processed output
are not present and does not call the 4-bound comparison reproducible
observational validation. A future release may bundle the small processed JSON
and the two source hashes after the official files are acquired in a networked
release environment.
