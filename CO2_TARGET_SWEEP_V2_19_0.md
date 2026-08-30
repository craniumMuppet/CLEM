# Paired Monte Carlo CO₂ target sweep (v2.19.0)

The CO₂ target sweep estimates how AMOC outcomes change as a prescribed CO₂ target is raised in fixed concentration increments.

## Experiment design

For every target concentration, CO₂:

1. begins at `sweep_start_ppm` (default 278.3 ppm);
2. increases linearly to the target over `sweep_ramp_years`;
3. remains fixed for `sweep_hold_years`;
4. is evaluated over the final `sweep_collapse_window_years`.

Targets include the starting concentration as a control, each regular increment, and the exact maximum even when the increment does not land on it.

The same sampled parameter member is reused at every target. This paired design prevents random differences between independently drawn ensembles from being mistaken for a CO₂-target response.

## Collapse definitions

Two outcomes are reported:

- **Ever collapsed:** AMOC reaches or falls below the configured collapse threshold at any recorded time.
- **Persistent collapse:** the final-window mean AMOC lies between 0 and the collapse threshold. Negative final-window AMOC is reported separately as reversal.

The default threshold remains 6 Sv and the default final window is 30 years.

## Main settings

- Members per target: `--monte-carlo-runs`
- Starting CO₂: `--sweep-start-ppm` (278.3)
- Target increment: `--sweep-step-ppm` (50)
- Maximum target: `--sweep-max-ppm` (1200)
- Ramp duration: `--sweep-ramp-years` (100)
- Hold duration: `--sweep-hold-years` (200)
- Collapse window: `--sweep-collapse-window-years` (30)
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

The JSON summary also estimates the CO₂ targets at which the interpolated ever-collapse and persistent-collapse probabilities first reach 10%, 50%, and 90%, when those probability levels occur inside the tested range.

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
  --sweep-plot-mode mean \
  --output outputs_co2_target_sweep
```

Posterior modes are supported. Their required calibration experiments are calculated once per paired parameter member, not once per CO₂ target.
