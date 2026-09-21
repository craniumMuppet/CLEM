# v2.29.14 — Recovery determinism and winter sea-ice compactness

## Scope

v2.29.14 addresses the two P2 and one P3 findings from the independent v2.29.13 review and reduces the excessive historical March native sea-ice area response. The v2.29.13 output-directory lock, semantic backup fallback, checkpoint accounting, and fixed 17 Sv built-in Monte Carlo AMOC control anchor are retained.

## CO2-target checkpoint recovery

The target-sweep worker previously wrote nested checkpoints only after successful targets. A real target exception was present in the outer member checkpoint but absent from the nested target directory inspected during checkpoint-only state reconstruction. Recovery could therefore change one failed target into pending work.

v2.29.14 writes one canonical nested checkpoint for every attempted target. A failed checkpoint contains the run fingerprint, member and target indices, target concentration, common start concentration, common AMOC baseline, terminal `failed` status, error text, traceback, and exact attempted/successful/failed counters. Checkpoint-only recovery now reconstructs the same terminal accounting as the live run.

## Deterministic validation records

Parallel validation tasks complete in nondeterministic order. v2.29.13 serialized dictionaries with insertion order, so semantically identical deep-validation records could have different hashes. v2.29.14 writes validation records with canonical sorted-key JSON serialization. Reversing task insertion order therefore produces byte-identical records.

Transient `validation_v*_runner.pid` and `validation_v*_runner.log` files are explicitly excluded from the package file inventory and ZIP archive.

## Winter mechanical lead closure

### Structural problem

The native thermodynamic state conserves equivalent ice thickness, but the reduced two-sector geometry converted thinning too directly into concentration loss. Real winter pack ice can redistribute and close leads through convergence, ridging, rafting, and rapid freezing while losing thickness and volume. The emulator lacked that compactness-preserving pathway, causing March area to decline much faster than the observed fitted trend even though the March climatological mean was close.

### Implemented process

The new cold-season lead-closure operator:

1. Computes the ordinary concentration from conserved equivalent thickness.
2. Diagnoses a cold-season weight from the prescribed reference-air climatology using a squared ramp below seawater freezing.
3. Allows a one-percentage-point concentration deficit before closure begins.
4. Closes a configurable fraction of the remaining deficit relative to the periodic control pack.
5. Recomputes local ice thickness as equivalent thickness divided by concentration.

The identity

`concentration × local thickness = equivalent thickness`

is preserved exactly. The operator cannot create ice when equivalent thickness is zero, cannot increase a positive concentration anomaly, and does not alter the periodic unforced control trajectory. It changes unresolved compactness and surface partitioning, not latent heat or ice mass.

### Selected defaults

- `arctic_winter_lead_closure_fraction = 0.65`
- `arctic_winter_lead_closure_onset_fraction = 0.01`
- `arctic_winter_lead_closure_temperature_scale_c = 15.0`

The closure fraction is represented in the built-in science prior with support 0.35–0.90 and a mode at 0.65. The onset and seasonal temperature scale remain explicit fixed controls unless a custom Monte Carlo range is supplied.

## Development comparison

The selected tuning-informed historical comparison changed approximately as follows:

| Metric | v2.29.13 | v2.29.14 selected configuration |
|---|---:|---:|
| March native-area trend, million km2/decade | -0.1210 | -0.0560 |
| March trend magnitude / observed | 3.17 | 1.46 |
| March native-area mean, million km2 | 13.124 | 13.214 |
| March native-area RMSE, million km2 | 0.378 | 0.382 |
| September native-area trend, million km2/decade | about -0.364 | -0.361 |
| September native-area RMSE, million km2 | about 0.642 | 0.647 |

The March mean and RMSE change modestly, while the excessive trend response is reduced by more than half. September trend changes by less than one percent, demonstrating that the correction is season-selective rather than a general suppression of ice loss.

These historical values were used during development. They are not independent validation.

## Remaining scientific limitation

The model still lacks observed weather sequences, realistic ice dynamics, basin geometry, and internally generated interannual variability. The historical March correlation therefore remains low and the robust March temporal-skill criterion remains failed. v2.29.14 does not claim quantitative prediction of individual March years, short-term winter variability, regional winter ice, or exact future March threshold timing.

The improvement applies to the forced winter trend response. Future sea ice, AMOC, and Greenland outputs remain reduced-complexity sensitivity results rather than precise forecasts.

The selected configuration also raises the unresolved Arctic lapse-rate/inversion closure from 1.00 to 1.10 W/m2/K. This restores the predeclared annual Arctic-amplification development envelope after winter lead closure slightly reduced ice-albedo amplification.
