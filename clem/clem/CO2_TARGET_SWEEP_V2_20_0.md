# Paired Monte Carlo CO₂ target sweep (v2.20.0)

The CO₂ target sweep measures how AMOC outcomes change as a prescribed CO₂ target is raised in fixed concentration increments. All weighted outcomes are reported as **conditional ensemble fractions**: fractions of the selected parameter design after applying the configured weights, not unconditional real-world probabilities.

## Experiment design

For every target concentration, CO₂:

1. begins at `sweep_start_ppm` (default 278.3 ppm);
2. increases linearly to the target over `sweep_ramp_years`;
3. remains fixed for `sweep_hold_years`;
4. is classified over the final `sweep_collapse_window_years`.

Targets include the starting concentration as a control, every regular increment, and the exact maximum even when the increment does not land on it. The same sampled parameter member is reused at every target, reducing sampling noise between adjacent target experiments.

## Duration-based outcomes

The classifier integrates the time spent in each AMOC state using linearly interpolated threshold crossings.

- **Ever collapsed:** AMOC reaches the interval from 0 Sv through the configured collapse threshold at any point.
- **Persistent collapsed:** the final AMOC remains in the weak/collapsed interval, at least `sweep_persistence_fraction` of the final window is collapsed, no recovery spell above the threshold lasts `sweep_recovery_years` or longer, and reversal does not dominate the final window.
- **Reversed:** AMOC is negative at the end of the run.
- **Active:** AMOC finishes above the collapse threshold.

Per-member output also includes collapsed duration, collapsed fraction, longest continuous collapse, active/recovery duration, longest recovery spell, reversal duration, and final-window minimum/maximum AMOC.

## Uncertainty and threshold estimation

The sweep reports pointwise weighted-member bootstrap intervals for conditional ensemble fractions. CO₂ targets corresponding to 10%, 50%, and 90% conditional fractions include:

- an isotonic non-decreasing point estimate;
- the raw first crossing of the sampled curve;
- a central bootstrap confidence interval;
- the fraction of bootstrap curves that cross the requested level.

Raw curves are checked for monotonicity. Any downward step is recorded in `monotonicity_checks`, and a warning explains that threshold estimates use an isotonic projection. The raw results remain available and are never overwritten.

## Main settings

- Members per target: `--monte-carlo-runs`
- Starting CO₂: `--sweep-start-ppm` (278.3)
- Target increment: `--sweep-step-ppm` (50)
- Maximum target: `--sweep-max-ppm` (1200)
- Ramp duration: `--sweep-ramp-years` (100)
- Hold duration: `--sweep-hold-years` (200)
- Classification window: `--sweep-collapse-window-years` (30)
- Required collapsed fraction: `--sweep-persistence-fraction` (0.95)
- Disqualifying recovery duration: `--sweep-recovery-years` (5)
- Bootstrap replicates: `--sweep-bootstrap-samples` (1000)
- Confidence level: `--sweep-confidence-level` (0.90)
- Trajectory plot: `--sweep-plot-mode mean|all`

## Outputs

- `co2_target_sweep_overview.png`
- `co2_target_sweep_amoc_trajectories.png`
- `co2_target_sweep_summary.csv`
- `co2_target_sweep_members.csv`
- `co2_target_sweep_mean_timeseries.csv`
- `co2_target_sweep_timeseries.npz`
- `co2_target_sweep_summary.json`
- `co2_target_sweep_base_config.json`
- optional long-form CSV when `--mc-save-long-csv` is selected

## Example

```bash
python co2_target_sweep.py \
  --monte-carlo-runs 256 \
  --mc-use-science-priors \
  --mc-seed 19930929 \
  --sweep-start-ppm 278.3 \
  --sweep-step-ppm 50 \
  --sweep-max-ppm 1200 \
  --sweep-ramp-years 100 \
  --sweep-hold-years 200 \
  --sweep-persistence-fraction 0.95 \
  --sweep-recovery-years 5 \
  --sweep-bootstrap-samples 1000 \
  --sweep-confidence-level 0.90 \
  --sweep-plot-mode mean \
  --output outputs_co2_target_sweep
```

Posterior modes are supported. Their required calibration experiments are calculated once per paired parameter member, not once per CO₂ target.
