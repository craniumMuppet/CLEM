# Posterior-weighted AMOC completion reporting (updated in v2.17.0)

When `mc_constraint_mode` is `ar6` or `ar6_amoc`, the completion report now prints both raw member counts and posterior weight sums.

Reported weighted diagnostics include:

- posterior weight and normalized probability of AMOC below 10 Sv in 2100;
- posterior weight and normalized probability of a final-30-year weak/collapsed state (`0–6 Sv`);
- posterior weight and probability of a reversed state (`<0 Sv`);
- posterior weight and probability of an active state (`>6 Sv`).

The same values are written to `monte_carlo_summary.json`, `monte_carlo_amoc_counts.json`, and `monte_carlo_amoc_counts.txt`. With constraint mode `none`, weighted lines are omitted because equal weights add no information beyond raw fractions.

## Prior controls

`Use built-in broad physical priors` replaces the custom range table with the complete built-in climate and AMOC prior set. Parameters use distributions chosen for their support: bounded fractions use beta distributions, positive scales commonly use log-normal or log-uniform distributions, measured signed quantities use truncated normal distributions, and weakly constrained coefficients use uniform distributions.

`Correlate physically related sampled parameters` applies the documented Gaussian-copula correlations to related parameter pairs. It preserves each parameter's marginal distribution while changing which values occur together.
