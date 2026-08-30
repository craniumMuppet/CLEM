# AMOC completion counts (updated in v2.17.0)

At the end of every successful Monte Carlo ensemble, the model now reports:

1. The number of successful members with AMOC below 10 Sv at calendar year 2100.
2. The number classified as weak/collapsed from a time-weighted mean AMOC over the final 30 simulation years, using 0 <= AMOC <= 6 Sv.
3. The number classified as reversed from the same mean, using AMOC < 0 Sv.
4. The number classified as active, using AMOC > 6 Sv.

The calculation interpolates individual member trajectories to 2100 when needed. The final classification uses a time-weighted 30-year mean rather than only the last timestep.

The results are written to:

- the final console output;
- `monte_carlo_summary.json` under `amoc_completion_counts`;
- `monte_carlo_amoc_counts.json`;
- `monte_carlo_amoc_counts.txt`.

If 2100 lies outside the simulation or the simulation is shorter than 30 years, the corresponding statistic is marked unavailable rather than inferred from another date or a shorter period.
