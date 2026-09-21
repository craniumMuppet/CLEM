# Continuation, stability and validation hardening in v2.23.0

## Root-search evidence

A finite seed set can never prove that every nonlinear equilibrium has been found. The equilibrium search therefore reports empirical evidence rather than claiming mathematical completeness. Deterministic seeds are followed by reproducible randomized batches until the number of distinct roots remains unchanged for a configurable number of batches. Outputs separate:

- `all_seed_solves_completed`;
- `root_count_saturated`;
- `additional_seed_search_performed`;
- `root_search_confidence`;
- root-count history;
- structured solver-failure details.

Only expected numerical exceptions are converted into seed failures. Unexpected exceptions propagate immediately.

## Branch tracking and folds

Root deduplication uses a dimensionless distance with variable-specific normalizers. Branch IDs are assigned with a Hungarian global assignment against secant-predicted states, removing dependence on root ordering and reducing identity swaps near close branches.

The bifurcation diagnostic now includes an augmented pseudo-arclength predictor-corrector. It solves the eight equilibrium residuals together with an arclength constraint, allowing the continuation parameter to reverse direction at a fold. Stable and unstable branch points are retained as `phase=branch` rows. Sign reversals in the continuation-parameter tangent are flagged as saddle-node candidates. Stable up/down paths still require the full multiscale linear and nonlinear acceptance tests.

## Nonlinear stability

A single slightly smaller excursion window no longer counts as decay. A perturbation must either return within its initial radius or show at least three consecutive contracting peak windows with a negative fitted log-envelope slope. Complex dominant eigenvectors are tested through both real and imaginary components, in both signs, with the critical directions repeated at 1.0, 0.5 and 0.25-year timesteps.

## Frozen external validation

The held-out set now contains four independently reported metrics:

- 2011-2020 global surface warming relative to 1850-1900;
- 1971-2018 ocean heat-content change;
- 1979-2021 Arctic amplification;
- late-century SSP2-4.5 AMOC weakening.

A separate calibration registry prevents calibration quantities from entering the held-out set. Every result records hashes for the benchmark file, calibration registry, processing script and complete model configuration. Each benchmark includes source, exact location, retrieval date, dataset version and processing-script metadata.

The default model currently fails all four frozen external ranges. These failures are intentionally reported without retuning against the held-out data.

## Reproducibility

`requirements.lock` now contains the fully resolved 42-package runtime graph for the tested Linux/Python 3.13 environment. `dependency_integrity.lock.json` records the graph hash and installed-distribution content hashes where the package was available locally, while `tools/regenerate_dependency_locks.sh` produces standard artifact-hash locks when the package index is available. The runtime output now includes surface, deep and total ocean heat-content anomalies in ZJ.
