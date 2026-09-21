# Percent-ramp-to-cap scenario (v2.18.1)

## Definition

For annual growth rate `r` expressed as a percentage, the prescribed concentration is

`CO2(t) = min(CO2_start * (1 + r/100)^t, CO2_cap)`.

The exact continuous time to the cap is

`t_cap = log(CO2_cap / CO2_start) / log(1 + r/100)`.

The model automatically sets the run length to `t_cap + hold_years`.

## User controls

- `--co2-growth-rate-percent`
- `--co2-growth-cap`
- `--co2-hold-years`
- `--percent-ramp-compare-rates`

The desktop GUI exposes the same values under **CO2 pathway**. The preset
**Percent CO2 ramp comparison** uses 278.3 ppm, a 1200 ppm cap, a 200-year hold,
and comparison rates of 0.5%, 1%, 2%, 3% and 5% per year.

## Comparison outputs

The combined PNG has three aligned panels: prescribed CO2, global surface
temperature anomaly and AMOC transport. Vertical markers show when each pathway
reaches the common cap. The CSV files preserve annual trajectories and endpoint
metrics for further analysis.


## Rate input behavior in v2.18.1

The comma-separated growth-rate list is now the only user-facing rate input.
Supply one value for a single pathway or multiple values for a comparison. The
first sorted value is used for the standard single-run output files; all listed
values are used for the comparison plot and tables. The old scalar CLI option
remains accepted only for backward compatibility and is ignored whenever the
percent-ramp scenario uses the rate list.
