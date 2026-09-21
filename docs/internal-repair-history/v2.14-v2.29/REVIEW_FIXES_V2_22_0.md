# Scientific and continuation hardening in v2.22.0

## Equilibrium continuation

The equilibrium diagnostic now follows only roots that pass both multiscale linear and nonlinear reduced-AMOC stability tests. A forcing level with no accepted stable root is emitted as an unresolved row rather than being replaced by an unstable solution. Adaptive midpoint refinement is triggered by missing stable roots, changes in stable-root count, large branch jumps and near-neutral eigenvalues. Each root receives a persistent branch ID, and the output records branch continuity, jumps, search completeness, bound contact and local forcing resolution. Pure branch matching and refinement logic lives in `amoc_continuation.py`, separate from the physical tendency equations.

The diagnostic name is `preindustrial_fixed_climate_amoc_equilibrium_continuation`. It holds the radiative state fixed at preindustrial conditions and must not be interpreted as a fully coupled CO2-temperature-freshwater equilibrium.

## Stability

Central-difference Jacobians are evaluated at three relative step sizes. Linear stability is accepted only when the classification is consistent across all three. Nonlinear validation covers signed coordinate axes, the dominant eigenvector and deterministic combined perturbations, with 1.0, 0.5 and 0.25-year integration steps. Because a stable non-normal system can exhibit transient growth, acceptance requires either direct return inside the initial radius or a bounded, contracting peak-distance envelope over successive windows. The reported scope is explicitly `reduced_amoc_subsystem`.

## Greenland

The default melt driver now uses a geographic Greenland land mask instead of all Arctic land. The reservoir separately tracks gross cumulative melt, gross cumulative accumulation and net ice loss; sea-level contribution is calculated from net ice loss.

## Validation and tests

`held_out_amoc_validation.py` loads versioned external benchmark definitions from `held_out_amoc_benchmarks.json`, verifies that they are excluded from tuning, and reports pass/fail results separately from structural stress tests. Legacy standalone regression scripts are now collected through pytest markers. `run_tests.py` delegates to pytest rather than maintaining a second test list. `held_out_amoc_validation.py --fail-on-benchmark` can be used as a strict external-validation gate without tuning the model to the benchmark.
