# v2.20.0 implementation summary

## Correctness fixes

- Hybrid SSP switch years are validated against the actual recorded simulation interval.
- SSP4-6.0 runs correctly report automatic initialization from 1850.

## AMOC outcome classification

`amoc_outcomes.py` provides a shared, piecewise-linear duration classifier. It reports state durations and continuity rather than reducing an entire final window to one mean value. Monte Carlo completion counts and CO₂ target sweeps use this classifier.

## Conditional ensemble fractions

Weighted member outcomes are named `conditional_*_fraction` or `*_conditional_ensemble_fraction`. This terminology makes the result conditional on the sampled parameter design, weighting scheme, model equations, forcing pathway, and diagnostic threshold.

## CO₂ target thresholds

Target sweeps now include pointwise weighted-member bootstrap intervals, monotonicity checks, an isotonic non-decreasing projection for threshold estimation, raw first-crossing estimates, and warnings when the sampled curve is non-monotonic.

## Monte Carlo parameter safety

`MONTE_CARLO_PHYSICAL_PARAMETERS` is the explicit custom-range whitelist. `MONTE_CARLO_EXPERIMENT_CONTROLS` identifies rejected numerical and experiment controls. Custom ranges cannot silently sample timestep, duration, resolution, scenario, or forcing-pathway controls.

## CO₂ forcing

`ModelConfig.co2_forcing_formula` accepts:

- `logarithmic`: backward-compatible legacy formulation;
- `meinshausen2020`: concentration-dependent CO₂ forcing with a reference N₂O overlap term.

The Meinshausen curve is normalized so `co2_doubling_erf_wm2` remains the exact configured forcing at doubled CO₂.

## AMOC structural families

The default structure remains unchanged. Opt-in alternatives are:

- `amoc_southern_ocean_structure="warming_sensitive"`, which changes effective Ekman inflow and upwelling with Southern Ocean warming inside configurable bounds;
- `amoc_indo_pacific_compensation_mode="diagnostic"`, which reports potential compensation without altering dynamics;
- `amoc_indo_pacific_compensation_mode="interactive"`, which adds bounded compensation to the pycnocline volume budget.

`amoc_structural_family_analysis.py` runs cross-products of these structures with the existing freshwater-compensation, reversal, and coupling choices.

## Reproducibility and tests

- `requirements.lock` and `requirements-dev.lock` pin runtime and test dependencies.
- `.github/workflows/ci.yml` tests Python 3.12 and 3.13, including the graphical layout test under Xvfb.
- `tests/test_property_conservation.py` uses Hypothesis to test salt-advection, freshwater, heat-redistribution, and short-integration conservation properties.
- `tests/test_review_fixes.py` directly exercises the v2.20.0 fixes and new structural options.
- `run_tests.py` runs the maintained legacy regression scripts.
