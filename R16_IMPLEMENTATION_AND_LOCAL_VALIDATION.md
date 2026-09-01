# CLEM v2.29.28 — Physics Repair Candidate R16

Status: **source candidate complete enough for local numerical validation; numerical acceptance pending.**

R16 is a repair-workflow revision, not a model-version bump. The runtime remains CLEM v2.29.28. The R13 numerical results remain the validated baseline until R16 passes the user-run local suite.

## Why R16 exists

The completed R15.1 local suite successfully exercised all 28 requested experiments in 674 restartable child chunks with no child advancing more than five model years. That run rejected one major R15.1 physics proposal: using South-Atlantic-upper-limb water as the default hydraulic source box made SSP2-4.5 AMOC strengthen and made freshwater hosing far too weak. See `R15_1_RESULTS_REVIEW.md`.

R16 therefore restores the validated interhemispheric high-latitude hydraulic density contrast as the default and retains the South-Atlantic-upper-limb construction only as a named structural-sensitivity geometry.

## R16 source changes

### AMOC

- Default hydraulic density geometry: `interhemispheric_high_latitude`.
- `legacy_southern_surface` is an exact compatibility alias for that historical closure.
- `south_atlantic_upper` remains available only as a structural-sensitivity geometry.
- Linear alpha/beta EOS remains the default.
- TEOS-10 remains an explicit structural branch and uses the standard `gsw` library. R16 fixes the R15.1 TEOS coordinate bug by using geometry-specific representative southern coordinates rather than always evaluating the source at 34.5 S.
- TEOS-10 is now tested under forcing, not only in a normalized control state.
- Density exponent, pycnocline feedback, strong-state saturation and reversal branches are exercised in regimes that can actually distinguish them.

### Greenland freshwater and salt

R15/R15.1's successful repair is retained:

- Greenland land-ice melt is an uncompensated ocean freshwater/mass addition by default rather than a zero-net-volume hydrological redistribution.
- Ocean water-volume state is propagated through checkpoints.
- Physical salt mass is conserved while salinity is allowed to dilute as freshwater mass is added.
- Legacy-compensated Greenland routing remains only as an attribution branch.
- Greenland elevation/melt feedback remains explicitly switchable.

### Sea-ice extent

R16 replaces the native whole-cell 0/1 threshold jump with an **unfitted, conservative meridional subgrid diagnostic**:

- prognostic sea-ice area/volume/thickness states are unchanged;
- each native latitude/sector concentration cell is reconstructed as a monotone piecewise-linear profile in equal-area `sin(latitude)` coordinates;
- slopes use minmod limiting and physical [0,1] bounds;
- the 15% concentration crossing is solved analytically;
- the reconstructed cell mean is constrained to the native prognostic mean, so the diagnostic does not create or remove ice area;
- Atlantic and non-Atlantic sectors are reconstructed independently and combined with the native ocean fractions;
- no observed extent series, fitted area-to-extent coefficient or post-hoc multiplier enters the operator.

Extent remains a derived coarse spatial diagnostic, **not** an independently prognostic longitude-resolved sea-ice field and **not** a scientific-release gate.

### Parameter activity and interfaces

- Compatibility-only AMOC/Arctic fields remain loadable for old configurations but are hidden from active user controls/priors where they have no dynamical effect.
- `atlantic_gyre_heat_transport_pw` is explicitly diagnostic-only: it participates in RAPID total-MHT scoring but not climate tendencies, and is removed from active climate-control interfaces.
- Stale AMOC metadata defaults were corrected to match the actual CLEM v2.29.28 configuration.

### Prospective validation

- `prospective_validation_r16.py` evaluates evidence rather than accepting a manual pass Boolean.
- The reserved prospective period remains 2027-2036 with evaluation no earlier than 2037.
- Until qualifying independent observations exist, the result remains `not_available` and scientific release remains incomplete.
- The R16 conservative extent diagnostic remains excluded from the prospective predictive gate because longitude is unresolved and extent is not a separate prognostic spatial state.

## Local validation

Run on Windows from the extracted R16 source directory:

```text
run_r16_local_validation.bat
```

The full R16 suite includes forced TEOS-10 experiments, so the launcher checks for `gsw` before it starts. If needed:

```text
python -m pip install -r requirements-r16-teos10.txt
```

This is a validation-suite dependency. Ordinary/default CLEM runs using `amoc_density_eos=linear` do not require `gsw`.

The runner:

- uses an active-PID lock;
- fingerprints source and experiment specifications;
- runs only one expensive child stage at a time;
- advances a maximum of five model years per child process;
- commits atomic restart checkpoints and cumulative record counts after each child;
- resumes from the latest matching checkpoint;
- emits a self-contained `CLEM_v2.29.28_R16_validation_results.zip` even if a later experiment fails.

R16 contains 34 experiments covering control identity, timestep convergence, hosing dose-response, compensated/uncompensated hosing, forced TEOS-10 and South-Atlantic-upper attribution, SSP2-4.5 10/5-degree response, AMOC structural families, collapse/recovery, Greenland routing/elevation and Arctic ablations.

No expensive climate integration is required or performed during source packaging. Numerical acceptance must be based on the returned user-run R16 result bundle.
