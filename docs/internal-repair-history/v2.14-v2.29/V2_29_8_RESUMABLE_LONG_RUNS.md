# v2.29.8 Resumable Long Runs and Explicit CO2 Targets

## Scope

v2.29.8 is an operational/output maintenance release built on the unchanged v2.29.7 physical configuration. It adds durable long-run continuation, explicit CO2 target selection, and AMOC percentage-decline products. It does not alter the v2.29.7 scientific calibration or evidence classifications.

## Save and load behavior

Long Monte Carlo and paired CO2 target-sweep runs write an atomic `long_run_state.json` file in the output folder. The state records the exact configuration fingerprint, resolved seed, original command arguments, progress counters, checkpoint folder, and completion/error status.

A requested random seed of `0` is resolved once at the start of a new run. That resolved seed is saved and reused on resume. This prevents a resumed run from generating a different ensemble.

The desktop GUI now includes **Load saved run**. Select an existing output folder containing `long_run_state.json`; the GUI restores the original saved command, replaces only the output path, adds `--mc-resume`, and resumes compatible checkpoints. Editing a setting after loading intentionally clears the exact saved-command override.

Standard Monte Carlo runs checkpoint each member. Paired CO2 sweeps additionally checkpoint each completed member-target simulation under:

`co2_target_sweep_target_checkpoints/member_XXXXXXXX/target_XXXXXXXX.pkl`

If a sweep is stopped or an outer member times out, a later resume retries the member and loads each already completed target instead of rerunning it.

## CO2 target selection

The target sweep supports two modes:

- `increments`: start, fixed increment, and exact maximum target.
- `specific`: an exact comma-, space-, or semicolon-separated list such as `200,300,600,1200`.

Specific targets are validated, sorted, and deduplicated. Every target must be positive and at least the common starting CO2 concentration. The specific list is run exactly; the start concentration is only added automatically in increment mode.

CLI options:

- `--sweep-target-mode increments|specific`
- `--sweep-specific-targets "200,300,600,1200"`

## AMOC percentage-decline products

For every member and target, the initial AMOC baseline is the mean of the first ten annual records. Positive decline means weakening:

`100 * (1 - AMOC / initial_baseline)`

New or expanded products include:

- `co2_target_sweep_amoc_percent_decline_timeseries.csv`
- `co2_target_sweep_amoc_percent_decline_trajectories.png`
- `amoc_decline_percent` in `co2_target_sweep_timeseries.npz`
- `amoc_decline_percent` in the optional long CSV
- final-window and maximum decline statistics in `co2_target_sweep_summary.csv`
- weighted p01, p05, p17, p50, p83, p95, and p99 trajectory bands

## Compatibility and safety

Checkpoints are loaded only when their SHA-256 configuration fingerprint matches the current run. Incompatible target lists, parameter ranges, seeds, scenario controls, or model versions are rejected rather than mixed. Atomic temporary-file replacement prevents partially written state or checkpoint files from being accepted.
