# Scientific constraints used by v2.29.28

The model supports three posterior-weighting modes:

- `none`: no diagnostic weighting; only the selected experiment is run.
- `ar6`: climate forcing, feedback, sensitivity and historical-climate diagnostics.
- `ar6_amoc`: all `ar6` diagnostics plus AMOC state and transient-response diagnostics.

Broad physically motivated priors are a separate opt-in. User-supplied min/max ranges are never silently replaced.

## Likelihood structure

Diagnostics within the same physical family are correlated. v2.16.0 therefore averages log likelihoods within groups before summing the group scores:

1. forcing;
2. feedback decomposition;
3. climate sensitivity;
4. historical climate;
5. AMOC state;
6. AMOC response.

Each member exports target-level `constraint_loglike_target_<diagnostic>`, unweighted group-level `constraint_loglike_<group>`, and weighted group-level `constraint_weighted_loglike_<group>` fields so posterior weighting can be audited.

## Climate targets

The code currently uses broad split-normal targets for:

- doubled-CO2 effective radiative forcing;
- Planck response;
- combined water-vapour plus lapse-rate feedback;
- surface-albedo feedback;
- cloud feedback;
- ECS;
- TCR;
- 2011-2020 historical warming;
- 2006-2018 Earth energy imbalance;
- historical ocean heat-uptake efficiency, diagnosed from explicit mixed-layer-to-deep-ocean heat uptake rather than total TOA imbalance.

These constrain diagnostics produced by the model. ECS and TCR are not direct input parameters.

Arctic amplification is evaluated on a like-for-like near-surface-air basis: the Arctic near-surface-air anomaly is divided by the global area-weighted near-surface-air anomaly over the same time window. Bulk land/ocean surface warming and the Arctic ocean-interface temperature are exported separately and are not used as the denominator.

With default v2.16.0 coefficients, the standard sensitivity diagnostic remains approximately in the package's intended central range: ECS around 3.3 degrees C, TCR around 2.3 degrees C, and net feedback around -1.17 W/m2/K. Exact values depend on diagnostic duration and numerical settings.

## AMOC state targets

The optional `ar6_amoc` mode includes broad targets for:

- present-day AMOC strength;
- total Atlantic heat transport at 26.5 N;
- South Atlantic overturning freshwater transport, FovS.

Total Atlantic heat transport is represented as:

`AMOC * amoc_heat_transport_pw_per_sv + atlantic_gyre_heat_transport_pw`

FovS is represented as:

`-AMOC * (S_upper_34S - S_deep_34S) / S0`

The initial South Atlantic upper-limb salinity is derived from the sampled FovS, deep salinity and reference AMOC. Present-day agreement is therefore partly calibration by construction and must not be described as independent validation.


## Current prognostic sea-ice area and constrained Arctic coupling

The prognostic area formulation was introduced in v2.29.20 and is retained, with the v2.29.28 forced-response and validation-integrity corrections described below.

Sea-ice volume remains an explicit latent-energy reservoir, but ice-covered area is now a separate prognostic concentration state in Atlantic and non-Atlantic Arctic sectors. New ice spreads at a configurable thin local thickness, while vertical growth changes volume without automatically filling open water. Lateral melt, ridging/rafting, and divergence modify area separately. The implementation enforces `0 <= concentration <= 1`, non-negative volume, and `equivalent thickness = concentration * local thickness` at every substep. Complete loss and subsequent thin-ice recovery are tested directly.

The corrected observational-development configuration uses `arctic_new_ice_local_thickness_m=0.22 m`, `arctic_full_cover_equivalent_thickness_m=3.70 m`, `arctic_ice_concentration_exponent=1.00`, `arctic_ice_nonsolar_heat_loss_wm2=51.0 W/m2`, `arctic_ice_area_thinning_melt_amplification=2.0`, `arctic_ice_area_thin_pack_divergence_fraction_per_year=0.30`, `arctic_ice_mechanical_max_local_thickness_m=12.0 m`, `arctic_ice_export_onset_equivalent_thickness_m=0.90 m`, `arctic_ice_export_timescale_years=0.24`, `arctic_winter_transport_enhancement=19.0 W/m2/K`, `arctic_forced_ocean_heat_convergence_wm2_per_k=8.0 W/m2/K`, `arctic_forced_ocean_heat_convergence_onset_warming_c=0.40 C`, and `arctic_forced_ocean_heat_convergence_saturation_scale_c=0.45 C`. G02202 calibration requires <=1.0 M km2 historical RMSE, 0.80–1.25 trend-magnitude ratios, matching decline direction, and overlapping model/observed OLS 95% trend intervals in March and September. The inspected 2021–2025 period has a stricter <=0.50 M km2 RMSE guard in each month. The 12 m deformation/spreading constraint conserves ice volume and acts before the 500 m emergency-only abort; if full concentration cannot accommodate the conserved volume within 12 m, the production state now fails fast instead of silently exceeding the physical limit. It is inactive in the observational record and prevents finite-volume, near-zero-area future remnants.

PIOMAS and satellite mean-state checks require source-specific nRMSE and relative-bias limits. Temporal correlations are separate gates: CryoSat-2 currently fails, so full volume/thickness validation is **not complete**. CryoSat-2 and ICESat-2 were visible during recalibration and are development-informed constraints, not independent validation. OSI SAF is likewise a non-independent cross-dataset diagnostic. Scientific predictive validation remains incomplete: NSIDC-0611 is pending, retrospective fold-local prior-grid evaluation fails the all-baseline skill condition, and untouched prospective validation is reserved for 2027 onward.

The release configuration limits `arctic_winter_transport_enhancement` to at most 25 W/m2/K and uses 19 W/m2/K by default. The seasonal operator requires both darkness and a sufficiently cold atmospheric state, so warm shoulder-season darkness does not receive deep-winter transport. Values above the release ceiling require explicit unsafe debug mode and are not scientific-release configurations.

The Greenland temperature driver combines Greenland/high-latitude land and global surface warming, with only a 0.10 default contribution from low-pass maritime Arctic air. Raw instantaneous marine Arctic-air anomalies are not used as the dominant driver. Explicit seasonal surface mass balance is kept separate from slow dynamic discharge. The 0.025 Sv freshwater cap is a safety bound; routine activation fails validation.

The same physical defaults are required at 5-degree and 10-degree resolution. Historical/recent sea-ice, structural area-volume, Arctic-air, Greenland, AMOC, salt-conservation, and cross-resolution gates are evaluated separately. Observation-file hash verification is a fail-closed evidence-integrity requirement, but matching hashes alone cannot confer scientific-release status.


## v2.29 Arctic ocean/surface coupling

The fractional Arctic surface is coupled conservatively to the existing prognostic Atlantic and non-Atlantic mixed-layer ocean anomalies. Basal ice heat flux increases with shallow-ocean temperature, while open water exchanges sensible heat in either direction with the ocean. Every transient ocean-to-surface flux is applied with an equal-and-opposite mixed-layer tendency.

The control climatology uses separate periodic Atlantic and central-Arctic shallow-ocean states. Their seasonal temperature is generated from an effective heat capacity, surface exchange, and a restoring heat-convergence closure. The closure is an emulator representation of unresolved ocean heat transport, not an explicit circulation model. The former 4°C open-water ceiling remains only as a deprecated configuration field for old files and has no dynamical effect.

The new coefficients are structurally uncertain and should be sampled in ensembles:

- `arctic_basal_ocean_exchange_wm2_k`;
- `arctic_open_water_ocean_exchange_wm2_k`;
- `arctic_reference_ocean_heat_capacity_wyr_m2_k`;
- `arctic_reference_ocean_restoring_wm2_k`;
- `arctic_forced_ocean_heat_convergence_wm2_per_k`;
- `arctic_forced_ocean_heat_convergence_onset_warming_c`.

v2.29.25 and later releases make both thickness safeguards explicitly numerical and non-corrective. `arctic_max_equivalent_thickness_m=20` is a fail-fast threshold and never clips/transfers latent energy. `arctic_max_local_ice_thickness_m=500` is a fail-fast threshold and never increases concentration or projected area. Both are excluded from Monte Carlo science priors. A private 12 m regularizer is used only during periodic reference-cycle iteration for convergence.

Depleted-pack phase restoring uses two independent validated controls: `arctic_phase_restoring_deficit_saturation_fraction=0.14` sets the transition scale and `arctic_phase_restoring_max_deficit_flux_wm2=2.5` sets the maximum reverse cooling/regrowth flux before the Arctic blend factor. This prevents a change in saturation shape from silently raising the maximum restoring force.

## AMOC response targets

To reduce state-only circularity, `ar6_amoc` also evaluates:

- percentage AMOC decline under SSP5-8.5 by 2081-2100 relative to 1995-2014;
- percentage AMOC decline around year 40 of a standardized 0.1 Sv freshwater-hosing experiment.

The target intervals are intentionally broad. They are response filters for a reduced model, not claims that either experiment has one uniquely correct value.

## AMOC heat coupling

The climate core carries separate Atlantic and non-Atlantic ocean states. The anomalous overturning heat transport is:

`surface_fraction * PW_per_Sv * (AMOC - reference_AMOC)`

It is applied as equal-and-opposite tropical and subpolar Atlantic heat convergence. The global integral is zero to floating-point precision.

A separate conservative Atlantic/non-Atlantic contrast damping represents unresolved compensation by atmospheric transport and ocean gyres. The damping redistributes heat between regional reservoirs; it does not create or remove global energy.

Important structural parameters are:

- `amoc_heat_transport_pw_per_sv`;
- `amoc_surface_heat_coupling_fraction`;
- `amoc_heat_response_damping_wm2_k`;
- `amoc_temperature_density_coupling`;
- `amoc_interhemispheric_temperature_coupling`.

These are emulator coefficients and should be sampled in uncertainty studies.

## Freshwater representation

Default warming freshwater is separated into:

- a reversible hydrological term proportional to the configured climate driver;
- an explicit seasonal Greenland surface-mass-balance anomaly;
- a separate slow Greenland dynamic-discharge state.

The Greenland surface branch calculates positive-degree-day melt, snowfall/rain partition, precipitation response, warming-dependent retention, runoff and accumulation relative to a zero-anomaly control seasonal cycle. The slow branch uses `greenland_dynamic_discharge_fraction` of the public `greenland_freshwater_sv_per_k` coefficient and approaches its target on `greenland_freshwater_adjustment_years`. The default public coefficients remain 0.006 Sv/K for hydrology and 0.005 Sv/K for Greenland.

The finite Greenland reservoir constrains cumulative net loss and permits negative surface flux during net accumulation. The default compensation mode places an equal virtual-salt anomaly in an external global-ocean reservoir. This exactly conserves total box-model salt but is not a literal simulation of sea-level rise or water-mass redistribution.

## Post-1850 initialization

An SSP or hybrid run beginning after 1850 is initialized by integrating the selected pathway continuously from 1850 to the requested start year. Explicit hosing is disabled during this initialization. The resulting climate, AMOC, salinity and lagged Greenland states become the initial state of the recorded experiment.

Use `--no-auto-initialize-from-1850` only for a deliberate zero-anomaly experiment or a workflow that supplies its own restart state.

## Hard numerical filters

Constrained members are rejected when they have:

- non-finite required diagnostics;
- numerically implausible ECS or TCR;
- a non-stabilizing net feedback;
- excessive residual TOA imbalance in the equilibrium diagnostic;
- salt-conservation error above the configured hard tolerance.

## Remaining scientific limitations

- The ocean is regionalized only into Atlantic and non-Atlantic components within latitude bands; it is not a resolved circulation model.
- AMOC convection and pycnocline dynamics are parameterized.
- Greenland surface mass balance is reduced to a regional temperature/PDD emulator; firn hydrology, outlet-glacier geometry and ice dynamics are not spatially resolved.
- Hydrological and Arctic-gateway freshwater inputs remain effective fluxes rather than a routed hydrological model.
- Present-day AMOC/FovS calibration remains partly structural.
- Transient response targets improve calibration independence but do not establish a tipping probability.
- The geography is adequate for reduced-model maps, not local impact assessment.


## v2.16.0 prior design

The built-in prior and likelihood no longer use the same narrow interval. Prior support is broader and based on parameter support: beta for bounded fractions, truncated log-normal for positive scales, truncated normal for signed measured quantities, and uniform for weakly known emulator coefficients. Present-day ERF, AMOC and FovS evidence is applied through the likelihood rather than duplicated in the prior. Net feedback remains exported as a diagnostic but is not a separate likelihood target because it is the deterministic sum of the component feedbacks.

Correlations are imposed simultaneously with a positive-semidefinite Gaussian-copula matrix. The included relationships are limited to water-vapour/lapse-rate coupling, ocean exchange/deep-ocean capacity, AMOC strength/pycnocline depth, Ekman/eddy compensation and convection adjustment/recovery times.


## AMOC bistability and hysteresis constraints

The current model distinguishes equilibrium bistability from transient memory.

The equilibrium AMOC diagnostic holds radiative forcing at the preindustrial state, disables warming-driven freshwater terms and compensates imposed freshwater within the connected Atlantic surface boxes. It solves the autonomous salinity-overturning-pycnocline equations directly. A candidate root is accepted only when its scaled tendency norm is below `2e-5`; local stability additionally requires the largest real Jacobian eigenvalue to be below `-1e-7 yr-1`.

Signed salt advection can produce Stommel-type multiple equilibria for some parameter combinations because transport reverses consistently and weakened salt import freshens the northern box. Version 2.16.0 adds continuous convective salt entrainment to this loop. The equilibrium solver searches the continuous equations from multiple initial guesses and reports bistability only when two converged, locally stable roots coexist; it does not insert active or collapsed branches.

The default convection transport exponent is 1.0, so loss of deep-water formation directly suppresses overturning transport. Hydraulic transport remains controlled by the basin-scale north-south density gradient, while convection is controlled by a local northern surface-to-deep density anomaly. Convection efficiency follows a smooth response centred at a default normalized density ratio of 0.91 with width 0.035. Active convection also exchanges salt vertically with the deep box and supplies continuous entrainment support to the local density response. There is no collapse threshold, restart threshold or forced collapsed-convection target in the dynamics. All of these coefficients are reduced-model parameters rather than observational tipping thresholds.

The calculated collapse and recovery thresholds are properties of the reduced model and its virtual-salt compensation convention. They must not be interpreted as observationally constrained real-world thresholds or tipping dates.
## Fast freshwater uncertainty in `none` mode

The fast selected-scenario mode can sample the freshwater mechanisms without running posterior calibration experiments. The desktop custom range table exposes:

- `hydrological_freshwater_sv_per_k`: 0.003–0.010 Sv/K;
- `hydrological_freshwater_north_fraction`: 0.50–0.90;
- `greenland_freshwater_sv_per_k`: 0.002–0.010 Sv/K;
- `greenland_freshwater_adjustment_years`: 30–150 years.

These are uncertainty ranges, not posterior probabilities. The resulting freshwater and AMOC trajectories remain prognostic outputs.

In v2.27, `greenland_freshwater_sv_per_k` controls only the slow dynamic-discharge branch. Seasonal surface mass balance is calculated separately from positive-degree-day melt, snowfall/rain partition, precipitation response, and firn retention. The combined instantaneous Greenland freshwater flux is capped at 0.025 Sv by default and by the finite ice reservoir.



## v2.17.0 structural AMOC constraints

Greenland freshwater discharge is limited by a prognostic finite reservoir. The default initial reservoir is 2.85 million Gt; discharge scales with the remaining fraction and is capped by a configurable maximum flux. This is still a reduced ice-sheet emulator, not a dynamic ice-sheet model.

The transient model checks the absolute initial basin density driver against a fixed reference. Members outside the configured 0.68–1.25 ratio are rejected by default. This prevents member-specific normalization from making arbitrarily weak absolute density margins appear equally robust.

Negative overturning is disabled in the default projection configuration. The signed hydraulic solution is retained as a diagnostic and may be enabled for explicit sensitivity experiments, but a scalar sign reversal is not treated as a validated reversed-circulation projection.

The v2.17.0 central parameter set is calibrated jointly, using the same period definitions as the posterior likelihood, to fall inside both the configured SSP5-8.5 AMOC-weakening range and the 0.1 Sv hosing-response range. This calibration does not convert the emulator into a comprehensive circulation model, and posterior probabilities remain conditional on the priors and structural assumptions.

### v2.29.1 Arctic phase-consistency bounds

The model rejects zero open-water/ocean coupling and monitors local Arctic open-water temperature at every internal timestep. Positive sensible heat may not remain beneath effective ice cover. Reference-ocean temperature targets are independent of transient exchange rates, preventing the exchange coefficient from implicitly selecting an unphysical control climatology.

### v2.29.1 Arctic phase-consistency bounds

The model rejects zero open-water/ocean coupling and monitors local Arctic open-water temperature at every internal timestep. Positive sensible heat may not remain beneath effective ice cover. Reference-ocean temperature targets are independent of transient exchange rates, preventing the exchange coefficient from implicitly selecting an unphysical control climatology.

## v2.29.2 integrity constraints

- Arctic reference cycles are accepted only after adaptive closure and convergence satisfy the configured tolerance before the hard spin-up maximum.
- Whole-domain salt projection corrects floating-point roundoff only. The pre-projection residual is retained as a diagnostic and structural residuals terminate the run.
- Monte Carlo numerical and physical safety checks always apply, including when observational constraint weighting is disabled.
- Lateral Arctic phase-restoring ocean heat convergence is signed about the periodic reference ice fraction and is applied with an equal-and-opposite non-Arctic ocean tendency.
- Arctic summary diagnostics use `arctic_module_full_latitude_deg`; disabling the seasonal Arctic module bypasses reference-cycle generation.
