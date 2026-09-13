# Physics review repairs — 2026-09-12

This is an Unreleased structural revision. It corrects reproducible defects and
removes unsupported default forcing closures. It does **not** establish that
the revised model reproduces observed climate or real AMOC tipping behavior.
The tagged-release and September 11 validation results describe older equations.

## Implemented corrections

### Ocean reference temperatures and polar radiation

The liquid-ocean reference floor now applies in both hemispheres, within the
existing global-mean offset solve. The blended reference remains 14 degrees C.
No ocean grid cell has a reference temperature below -1.8 degrees C.

The water-vapour emission-height shift is weighted by the baseline vapour path,
`q0 / (q0 + water_vapor_optical_path_scale)`, with scale 0.002 kg/kg. Thus a dry
column cannot produce the same height shift per fractional humidity increase
as a moist column. This is an explicit saturating optical-path approximation,
not a radiative-kernel fit; its scale is configurable. The existing 0.98 km
coefficient is retained, without recalibrating ECS to its old value.

At 10 degrees, the net longwave response to +1 K over 85N land changes from
approximately +0.866 to -0.891 W/m2. At 75N it is approximately -1.299 W/m2.
Tests cover both land/ocean columns at 5 and 10 degrees for warming of 0.01,
1, 4 and 10 K. All have a negative net longwave response under the revised
default. This is a model-specific regression safeguard, not a claim that every
column of every stable coupled climate model must have negative feedback.

### AMOC water masses and basin salt exchange

The default is `south_atlantic_upper` geometry with `teos10_matched`. The
northern sinking density uses prognostic northern temperature and salinity. The
source density uses prognostic South Atlantic upper salinity and the transformed
temperature implied by northern surface-to-deep stratification. The local 35 S
surface temperature is retained in `teos10_surface_watermass` as a structural
sensitivity. The control temperature contrast and noncanonical hydraulic
exponents remain reduced-model assumptions.

TEOS-10 evaluates liquid water at no less than its salinity-dependent freezing
temperature. This bounds the EOS input, not the prognostic reservoir's heat.
`amoc_north_eos_temperature_c`, `amoc_source_eos_temperature_c`, and the two
`amoc_*_freezing_bound_active` fields expose that intervention. Bound activation
requires scrutiny; it does not validate an otherwise unphysical thermal state.
The literal surface-water-mass option remains available for structural
comparisons.

Positive overturning now follows external -> SAU -> tropical -> north -> deep
-> external, with every connection reversed for negative transport. In the
default `freshwater_budget` mode, the steady salinity contrasts are solved from
explicit surface, northern-boundary and southern-gyre freshwater terms. The
initial salinity values provide only the conserved absolute salt-inventory seed;
neither FovS nor a boundary salinity contrast enters the solve. The deep box has
no artificial freshwater source. Global salt remains conserved before roundoff
projection. `prescribed_hydrography` and `amoc_open_boundary_enabled=False`
retain historical initialization/topology for attribution. The separate
Southern surface reservoir starts at 34.0 PSU and is not the hydraulic source.

The old SAU/deep calculation is retained as
`amoc_internal_section_freshwater_sv`. The legacy -0.15 Sv configuration field
is inactive as a contrast target in freshwater-budget mode. `fovs_sv` and
`amoc_boundary_overturning_freshwater_sv` record the actual external advective
boundary, while `amoc_basin_salt_inventory_anomaly_psu_m3` tracks the Atlantic
inventory. The default control result is -0.16 Sv, predicted by the reduced
steady freshwater budget rather than selected from an FovS observation.

### Arctic and Greenland

The GMST-triggered Arctic ocean heat convergence, reference-phase restoring
and extra winter GMST transport are disabled by default. The pre-existing
state-dependent atmosphere/ocean exchanges and seasonal thermodynamics remain.
Legacy heat-convergence and restoring sensitivities can be enabled explicitly;
CLI/API/desktop defaults agree. Monte Carlo sampling excludes parameters of
disabled closures and rejects explicit attempts to sample them as active.

Ice export's latent energy and freshwater equivalent now use a common physical
conversion: the former freshwater-only observational multiplier is removed.
The old configured export freshwater target is historical/diagnostic only.
This fixes their relative accounting, **not** the absolute export closure.
The thickness-relaxation export, concentration parameterizations and absolute
reference surface-energy budget still need observationally constrained
development. No claim of a validated Fram Strait export is made.

Greenland PDD now integrates a Gaussian daily temperature distribution:
`E[max(T,0)] = sigma*phi(mu/sigma) + mu*Phi(mu/sigma)`.
The configurable default sigma is 4.5 K; zero recovers deterministic PDD.
Runoff is calculated as current retained-adjusted melt minus reference
retained-adjusted melt, so retention changes act on the full melt reservoir,
including the reference melt. The scalar seasonal and vector annual paths agree
and the unforced anomaly is zero. Spatial snowfall/rain, refreezing and dynamic
discharge remain simplified; the reported historical mass-loss bias has not
been declared solved or tuned away.

### Accounting and validation semantics

The Arctic air heat-content diagnostic now uses the capacity of the integrated
air state; it no longer multiplies that capacity by the module blend a second
time. Complete time-weighted annual means are used for Gregory regression,
its plotted points, the equilibrium tail and feedback normalization. The
Arctic module's net TOA term is included explicitly in the component sum.
An equilibrating run should satisfy `(N-F)/T`, which equals `-F/T` only when
the residual imbalance N vanishes. These components are algebraic model
diagnostics, not a full radiative-kernel decomposition.

The static verifier tests the response to warming northern sinking water at
fixed source state, rather than prescribing a sign for every possible control
thermal contrast. The initial-FovS and water-vapour-coefficient pins are no
longer advertised as physical validation. The SSP2-4.5 development gate now
uses the previously declared 15–50% range instead of 5–50%; it is not relaxed
to accommodate the revised model.

## Development verification

109 distinct focused tests pass, covering new physical invariants, existing
temperature/convection behavior, Greenland units, prior activity, CLI/desktop
parity, Monte Carlo integrity, freshwater routing and conservation. This includes 18 coupled 15-year
salt-conservation integrations across compensation modes, hosing and time steps.
Compilation and `git diff --check` pass. The entire historical release test
inventory and the historical/SSP/equilibrium validation matrix were not rerun.

The reproducible experiment driver is `tools/verify_physics_revision.py`.
Results and time series are in `physics_revision_20260912/`.

| Coupled experiment | Final air warming (K) | Final AMOC (Sv) |
|---|---:|---:|
| Control, 5 years, 10 degrees | approximately 0 | 17.000 |
| Abrupt 2xCO2, 60 years, 10 degrees | 1.743 | 16.072 |
| Abrupt 2xCO2, 60 years, 5 degrees | 1.739 | 16.183 |
| 0.2 Sv hosing, 100 years, 10 degrees | -0.0022 | 14.083 |

Maximum pre-projection salt error is 3.45e-10 ppm. The recorded radiative
component budget closes within 2.7e-15 W/m2. Halving the main step to 0.025 years
and doubling Arctic substeps to 160/year changes the year-20 air warming by
-0.000056 K and AMOC by -0.00384 Sv. No EOS freezing-bound activations occur
in the recorded samples. These are consistency checks, not observational fits.

The initial South Atlantic implementation made AMOC strengthen to 19.214 Sv
under doubled CO2. Mechanism isolation reproduced 19.141 Sv after disabling all
anomalous freshwater and 19.073 Sv after disabling sea-ice salinity coupling,
locating the error in the thermal hydraulic observation operator. It applied
the local 35 S surface-temperature anomaly directly to the source water. Under
TEOS-10, nearly uniform warming then made the already warm source expand faster
than northern water and increased the diagnosed density head despite growing
northern stratification.

The corrected operator retains the prognostic South Atlantic upper salinity but
represents the thermally transformed source with the northern deep-temperature
anomaly. The hydraulic thermal contrast therefore follows the model's northern
surface-to-deep stratification. It introduces no fitted weakening target or new
coefficient. In doubled CO2, 10-degree AMOC reaches a minimum of 15.808 Sv and
ends at 16.072 Sv; the 5-degree result reaches 15.921 and ends at 16.183 Sv.
These establish the correct forced sign and numerical consistency, but do not
constitute observational validation of the response magnitude.

The experiment source snapshots are saved with the time series.
`source_equivalence.json` records exact equality between the current executable
sources and the experiment snapshots. The current source and experiment hashes
are both recorded.

An additional isolated pulse-recovery comparison is run with
`python tools/verify_physics_revision.py --recovery-only`. It compares open and
legacy closed boundaries under identical 0.2 Sv, 100-year hosing followed by
900 years without hosing, with seasonal Arctic, anomalous hydrology and
Greenland freshwater disabled. Its separate results file reports basin salt
deficit and transport; it is not a proof of branch identity or hysteresis.

| Isolated pulse recovery at year 1000 | Open boundary | Legacy closed boundary |
|---|---:|---:|
| Fraction of year-100 basin salt deficit remaining | 0.1386 | 0.9596 |
| AMOC (Sv) | 16.7644 | 16.6207 |

Both use the revised density/radiation physics; only topology differs. The
large difference in inventory decay directly tests ventilation, while the
partially recovered transports show why transport alone cannot identify trapped
inventory or prove hysteresis. Maximum pre-projection salt errors are 3.45e-10
ppm (open) and 1.73e-10 ppm (closed). Results are in
`physics_revision_20260912/recovery_results.json`.

## Scientific basis and outstanding scope

- [TEOS-10 freezing temperature](https://www.teos-10.org/pubs/gsw/html/gsw_t_freezing.html)
  defines the liquid-water EOS boundary.
- [IPCC AR6 Chapter 7](https://www.ipcc.ch/report/ar6/wg1/chapter/chapter-7/)
  distinguishes calibrated emulators, climate feedbacks and sensitivity diagnostics.
- [Assessment of PDD methods using observations](https://www.cambridge.org/core/journals/journal-of-glaciology/article/assessment-of-current-methods-of-positive-degreeday-calculation-using-in-situ-observations-from-glaciated-regions/920859A8D1B91C2C2AFA3C6DE1710E31)
  discusses Gaussian temperature variability and limitations of a fixed spread.

Outstanding scientific work includes a realistic AMOC thermal/ventilation
response, the absolute Arctic mass/energy budget, Greenland spatial SMB and
discharge, regional baseline/feedback constraints and refreshed historical
validation. Previously inspected observations remain development evidence;
2013–2024 cannot be relabelled an untouched holdout. The broad review's exact
attribution percentages and tipping thresholds remain claims to reproduce.

## FovS-focused investigation — 2026-09-13

The reproducible diagnostics are `tools/investigate_fovs.py` and
`tools/investigate_fovs_sign.py`; their complete outputs are
`physics_revision_20260912/fovs_investigation.json` and
`physics_revision_20260912/fovs_sign_investigation.json`.

The investigation found that the initial open-boundary revision still exposed
the old internal SAU/deep transport as `fovs_sv`. At control it was -0.150 Sv,
while transport through the actual model boundary was +0.2186 Sv. Their signs
were opposite. Changing the legacy target from -0.15 to +0.15 Sv left the
boundary value exactly +0.2186 Sv, proving that the configured quantity was
not the standard basin-boundary indicator. The output contract was corrected:
`fovs_sv` now equals `amoc_boundary_overturning_freshwater_sv` when the open
boundary is active, and the former value is explicitly
`amoc_internal_section_freshwater_sv`. `fovs_is_external_boundary` states which
topology produced the compatibility field. Closed legacy runs retain their
internal-section `fovs_sv` and set that flag to zero.

The positive sign had a hydrographic cause. The first open-boundary patch used
a 34.70 PSU global-mean-like compensation reservoir as upper water entering at
34.5 S, while the returning deep box was 35.15 PSU. Therefore
`-17 * (34.70 - 35.15) / 35 = +0.2186 Sv` by construction. This is the same
fresh-upper/salty-deep bias associated with positive FovS in coupled models.

The replacement does not choose a boundary salinity or FovS. It solves the
steady salinity system from three independently estimated control-budget sums:

- Atlantic surface freshwater exchange: -0.28 Sv (net evaporation);
- non-overturning northern-boundary import: +0.06 Sv;
- azonal southern-boundary/gyre import: +0.38 Sv.

With zero storage, conservation requires
`FovS = -(-0.28 + 0.06 + 0.38) = -0.16 Sv`. Solving the full box equations gives
the same result and predicts external/deep salinities of 35.2401/34.9107 PSU.
Changing the external salinity seed changes only the absolute salt inventory,
while the legacy internal-section FovS field is completely inactive; neither
can change the solved contrast or boundary FovS.
The legacy `prescribed_hydrography` mode reproduces +0.2186 Sv for the old
34.70 PSU external seed and -0.1001 Sv for a deliberately saltier 35.356 PSU
seed, making the distinction explicit.

This is an equilibrium freshwater-budget prediction conditional on the stated
flux observations. It is more independent than selecting an observed FovS or
the salinity contrast that produces it. It is not a free atmosphere-ocean
prediction: CLEM does not calculate absolute evaporation, precipitation,
runoff, Bering Strait transport or the azonal southern-boundary circulation.
The lower-Atlantic surface term (-0.65 Sv) is the basin total after treating the
observed northern +0.37 Sv freshwater divergence as a steady-equivalent surface
input. That observation can include storage over its finite measurement period;
the source estimates a much smaller 0.008 Sv contribution for the cited salinity
trend, but the approximation remains explicit.

The model contains a transient salinity feedback. Reducing AMOC from 17 to
16 Sv at control changes the northern salt tendency by -0.0864 PSU per century.
In an AMOC-only perturbation from 17 to 15 Sv, active salinity makes AMOC 0.0248
Sv weaker than a frozen-salinity ablation at year 10, 0.00835 Sv weaker at year
50, and 0.00143 Sv weaker at year 100 while both return to about 16.984 Sv. An
isolated 0.2 Sv, 100-year hosing run ends at 14.403 Sv and FovS -0.1664 Sv.
These experiments show a modest transient response, not a stable
weak branch.

Changing the legacy `initial_fovs_sv` field from -0.15 through 0 to +0.15 leaves
the salinity state, initial FovS and hosing response unchanged.
The field is excluded from built-in physical Monte Carlo priors and is an active
contrast target only in explicit `prescribed_hydrography` runs.

A second code audit removed three residual interface inconsistencies. Validation
now also ignores `initial_fovs_sv` when freshwater-budget mode is active. The
standalone AMOC density safety check calls the same control-salinity solver as the
model, so its canonical default ratio is 1.0 instead of depending on the legacy
hydrography. The optional linear EOS now also evaluates its South Atlantic
reference on the active grid, giving the default control a ratio of 1.0 at 10,
5 and 2.5 degree resolution. Output columns now distinguish physical/steady-equivalent surface
fluxes from non-overturning boundary terms and from their combined virtual box
forcing; the boundary terms are no longer reported as surface fluxes.

The boundary reservoir remains a reduced single box and its gyre term is a
fixed virtual freshwater exchange, not an evolving resolved velocity/salinity
field. Formal stability still requires equilibrium analysis and the complete
Atlantic freshwater budget.

The refined indicator is `DeltaFov = FovS - FovN`. This model does not resolve
a liquid northern Arctic boundary transport, so it now publishes `FovN` and
`DeltaFov` as unavailable (`NaN`) with an explicit incomplete flag. Surface
runoff and sea-ice export are kept separate rather than being mislabeled as
the missing overturning transport.

Literature context: Weijer et al. (2019) define FovS at the Atlantic southern
boundary and review its interpretation and limits
(https://doi.org/10.1029/2019JC015083). The refined two-boundary definition is
used by Liu et al. (2025), `DeltaFov = FovS - FovN`
(https://doi.org/10.1038/s41467-025-66494-1). Arumí-Planas et al. (2024)
estimate -0.15 +/- 0.09 Sv at 34.5 S and identify fresher upper/saltier deep
water as characteristic of models with positive FovS
(https://doi.org/10.1029/2023JC020558). Caínzos et al. (2022) estimate
-0.13 +/- 0.03 Sv for 2010-2019 at 30 S
(https://doi.org/10.1029/2021GL096527). The independent control-budget terms
use Talley's (2008) -0.28 Sv Atlantic/Arctic surface balance and +0.06 Sv Bering
Strait transport (https://doi.org/10.1016/j.pocean.2008.05.001), McDonagh et
al.'s (2015) +0.37 Sv surface input north of 26.5 N
(https://doi.org/10.1175/JCLI-D-14-00519.1), and the +0.38 Sv azonal estimate
summarized by de Vries and Weber (2005)
(https://doi.org/10.1029/2004GL021450).
