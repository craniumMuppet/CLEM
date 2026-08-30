# v2.29.2 Release Integrity Maintenance

v2.29.2 addresses the remaining configuration-safety and release-verification defects found in the fresh v2.29.1 review. It does not restore temperature clipping or change the calibrated freshwater defaults.

## Arctic reference-cycle convergence

The reference solver now integrates for at least `arctic_reference_spinup_years` and continues adaptively until both periodic closure and year-to-year convergence satisfy `arctic_reference_convergence_tolerance_wyr_m2`. It stops at `arctic_reference_max_spinup_years` and initialization fails rather than accepting a non-converged cycle. When `seasonal_arctic_enabled` is false, no reference cycle is generated.

## Salt integrity

The six-box system records the maximum salt residual before projection, the largest individual projection correction, cumulative signed correction and cumulative absolute correction. Projection is permitted only below `salt_projection_max_residual_ppm`, which is intended for floating-point roundoff. Larger residuals raise `FloatingPointError` and cannot be hidden by the exact projection.

## Monte Carlo safety

Temperature, dormant-heat, salt, density-margin and reference-cycle checks are applied in every Monte Carlo constraint mode. Mode `none` means no observational likelihood weighting; it no longer means no physical safety screening. Invalid members receive zero weight and an explicit rejection reason.

## Signed phase-restoring closure

The reduced lateral ocean heat-convergence closure is signed about the periodic reference ice fraction. Positive ice anomalies receive heat from the non-Arctic ocean and negative anomalies export heat to it. Equal-and-opposite tendencies preserve whole-domain energy. This remains a calibrated reduced-complexity closure rather than resolved ocean circulation and is retained as structural uncertainty.

## Verification policy

`run_tests.py` collects the complete retained inventory by default and executes every node in a clean subprocess while allowing normal pytest setup, teardown, finalizers and terminal reporting. `--fast` is explicitly a reduced development subset. Conservation property tests use deterministic grids and seeded random samples so they cannot be skipped because an optional plugin is unavailable.

The v2.29.2 validator adds public-range reference-cycle stress, disabled-Arctic initialization, unconditional Monte Carlo rejection, pre-projection salt integrity and the existing scenario, energy, timestep, control, perturbation, hosing and resolution checks. A failed required gate returns a nonzero process status.

## Final validation snapshot

- Historical GMST, 2011–2020: **1.108°C**
- Ocean heat-content gain, 1971–2018: **383.71 ZJ**
- Annual Arctic amplification, 1979–2021: **3.408×**
- SSP2-4.5 AMOC weakening by 2100: **20.85%**
- SSP5-8.5 AMOC weakening by 2100: **39.60%**
- SSP2-4.5 / SSP5-8.5 peak Arctic open-water temperature: **12.79°C / 17.46°C**
- Abrupt-2×CO₂ resolved-energy residual: **−0.0397%**
- 500-year GMST / AMOC drift: **1.01×10⁻⁵°C / −3.15×10⁻⁶ Sv**
- Maximum pre-projection salt residual: **3.47×10⁻¹⁰ ppm**
- Public-range reference stress: **155 years**, closure **8.22×10⁻⁹ W·yr/m²**
- Required validation gates: **15/15 passed**

