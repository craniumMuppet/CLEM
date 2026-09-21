# Percent-ramp rate input simplification (v2.18.1)

The `percent_ramp_hold` scenario now has one rate control: a comma-separated
list such as `0.5,1,2,3,5`.

- One value runs one pathway and still creates the comparison products.
- Multiple values run all pathways and place them in the shared plot and CSVs.
- The first sorted value is used for the ordinary single-run output files and
  diagnostics, avoiding a second independent rate setting.
- `--co2-growth-rate-percent` remains accepted only so old commands do not
  break; the rate list controls the percent-ramp scenario.

Monte Carlo runs accept exactly one rate in the list because combining several
rates would represent several distinct ensembles. Run one ensemble per rate.
