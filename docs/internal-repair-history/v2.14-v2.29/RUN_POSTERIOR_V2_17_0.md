# Running a new v2.17.0 posterior ensemble

Do not reuse v2.16.x member weights. The Greenland reservoir, density screening, reversal handling, AMOC defaults and priors changed.

## Recommended SSP5-8.5 run

```bash
python monte_carlo.py \
  --scenario ssp585 \
  --years 650 \
  --dt 0.05 \
  --monte-carlo-runs 8192 \
  --mc-workers 0 \
  --mc-constraint-mode ar6_amoc \
  --mc-use-science-priors \
  --output outputs_ssp585_v2170
```

## Recommended SSP2-4.5 run

Use the same seed and sampling settings when comparing scenarios:

```bash
python monte_carlo.py \
  --scenario ssp245 \
  --years 650 \
  --dt 0.05 \
  --monte-carlo-runs 8192 \
  --mc-workers 0 \
  --mc-constraint-mode ar6_amoc \
  --mc-use-science-priors \
  --output outputs_ssp245_v2170
```

The default seed uses the system clock. Set `--mc-seed` to the same nonzero value in both commands for matched deterministic sampling.

## What to check

After completion, inspect:

- `monte_carlo_constraint_summary.json`: effective sample size, maximum weight and weight quality;
- `monte_carlo_amoc_counts.txt`: raw and posterior-weighted active, weak/collapsed and reversed states;
- `monte_carlo_summary.json`: posterior probabilities and endpoint summaries;
- `monte_carlo_members_weighted.csv`: member-level diagnostics and weights.

Reversal is disabled by default, so ordinary projection runs should report zero reversed members. The `--amoc-allow-reversal` flag is intended only for explicit sensitivity experiments.
