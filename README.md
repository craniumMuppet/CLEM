# Coupled Low-complexity Earth Model v2.29.29

**Abbreviation: CLEM**  
**Current release: v2.29.29**  
**Validation/release maintenance lineage: R18.5.1 / R18.6 public-release consolidation**

**CLEM v2.29.29** is a process-based reduced-complexity climate model written in Python.

It couples global temperature, ocean heat uptake, radiative feedbacks, Arctic sea ice, Greenland meltwater, Atlantic salinity, and a dynamically evolving Atlantic Meridional Overturning Circulation (AMOC).

CLEM is intended for **climate-process experiments, sensitivity studies, teaching, and model development** rather than as a replacement for a comprehensive General Circulation Model (GCM) or Earth System Model (ESM).

Climate sensitivity is not prescribed directly. **ECS and TCR are diagnosed from forcing experiments.** The original feedback coefficients were calibrated against AR6 assessments. This is calibration evidence, not independent validation.

## Current scientific results

The current checkout adds a FAFMIP-informed AMOC sinking-capacity limit. The
lower of this limit and the hydraulic density capacity controls the default SSP
response. Its global-forcing mapping and 20-year lag are emulator assumptions,
so these results are conditional sensitivities. See the
[forced-heat review](docs/AMOC_FORCED_HEAT_CLOSURE_2026_09_14.md).

### Paired CO2 target sweep

The sweep uses **128 paired prior members per CO2 target** at 400, 600, 800,
1000, 1200 and 2200 ppm.

![Conditional AMOC outcomes across six CO2 targets](docs/assets/science_update_2026_09/co2_target_sweep_overview.png)

![Paired AMOC percentage-decline trajectories across six CO2 targets](docs/assets/science_update_2026_09/co2_target_sweep_amoc_percent_decline_trajectories.png)

### Four-pathway SSP comparison

All four panels use the same 5° integrations from 1850 to 2300.

![Temperature, AMOC, FovS and sea-ice response under four SSP pathways](docs/assets/science_update_2026_09/ssp_four_panel_comparison.png)

| Scenario | 2100 temperature | AMOC, 2081–2100 | AMOC decline | 2100 FovS | 2100 sea ice |
|---|---:|---:|---:|---:|---:|
| SSP1-2.6 | 1.46 °C | 12.70 Sv | 20.9% | −0.124 Sv | 16.61 million km² |
| SSP2-4.5 | 2.33 °C | 11.30 Sv | 29.7% | −0.107 Sv | 16.17 million km² |
| SSP4-6.0 | 2.77 °C | 10.63 Sv | 33.8% | −0.099 Sv | 15.95 million km² |
| SSP5-8.5 | 4.14 °C | 8.79 Sv | 45.3% | −0.075 Sv | 15.18 million km² |

Temperature is relative to 1850. AMOC decline compares 2081–2100 with
1995–2014. Under SSP5-8.5 the empirical branch approaches zero by 2300.

### SSP2-4.5 parameter uncertainty

![SSP2-4.5 Monte Carlo AMOC percentage decline](docs/assets/science_update_2026_09/ssp245_monte_carlo_amoc_decline_percent.png)

| Absolute AMOC transport | Global surface-temperature anomaly |
|:---:|:---:|
| ![SSP2-4.5 Monte Carlo AMOC transport](docs/assets/science_update_2026_09/ssp245_monte_carlo_amoc_sv.png) | ![SSP2-4.5 Monte Carlo global surface-temperature anomaly](docs/assets/science_update_2026_09/ssp245_monte_carlo_global_surface_warming.png) |

### Current biases and scope

| Check | Current result | Reference or declared range | Difference |
|---|---:|---:|---:|
| Historical warming, 2011–2020 | 0.8368 °C | 0.95–1.20 °C | 0.1132 °C below lower bound |
| Ocean heat-content change, 1971–2018 | 348.2 ZJ | 350–500 ZJ | 1.8 ZJ below lower bound |
| 100-year post-hosing recovery | 79.510% | at least 80% | 0.490 percentage points low |
| Historical AMOC, approximately 2004–2020 | 15.74–15.86 Sv | RAPID 16.9 ± 1.2 Sv | about 1.0–1.2 Sv low |
| Arctic sea-ice area bias | March +0.355 and September −0.055 million km² | NSIDC-compatible area | seasonal signed bias |

AMOC spread mainly reflects the forced-heat prior. FovS remains prognostic but
follows the AMOC closure while it controls. The sea-ice maps use reduced
geometry and have no local forecast skill.

### SSP diagnostics

The composites show surface temperature, sea ice, snow, AMOC, convection,
pycnocline depth and Atlantic salinity. The rectangular North Atlantic feature
comes from the reduced grid.

#### SSP2-4.5

![SSP2-4.5 process and final-state diagnostics](docs/assets/science_update_2026_09/ssp245_diagnostics.png)

#### SSP5-8.5

![SSP5-8.5 process and final-state diagnostics](docs/assets/science_update_2026_09/ssp585_diagnostics.png)

Figure provenance and source hashes are in the
[asset manifest](docs/assets/science_update_2026_09/manifest.json).

## Current release status

**Current checkout (Unreleased, September 16 science update):** the default
uses direct water-mass TEOS-10 density, an open Atlantic boundary, bilateral
ocean freezing floors and dry-column water-vapour weighting. It also updates
Greenland runoff, Arctic feedback accounting and AMOC sinking capacity. The
lower of the hydraulic and FAFMIP-informed capacities controls AMOC.

Current figures use the unreleased revision. Tagged-release evidence retains
its original model state. See the
[repair report](docs/PHYSICS_REVIEW_REPAIRS_2026_09_12.md).

**v2.29.29** consolidates the validated R15–R18.5.1 work without retuning the
v2.29.28 dynamics. A dynamics-equivalence record links the inherited evidence.

R18.4 completed the sixth-source Arctic observational stack by processing authentic **NSIDC-0611 v4/v4.1 EASE-Grid Sea Ice Age** files for 1984–2024. The Arctic observational stack is now **6/6 available**. Independent predictive scientific validation remains **`not_available`** until the preregistered 2027–2036 prospective holdout observations exist.

See `RELEASE_NOTES_V2_29_29.md`, `V2_29_29_DYNAMICS_EQUIVALENCE.json`, `R18_2_RESULTS_REVIEW.md`, `R18_4_NSIDC_0611_INTEGRATION.md`, `R18_5_PUBLIC_RELEASE_MERGE.md`, `docs/VALIDATION.md`, and `docs/MODEL_LIMITATIONS.md`.

---

## Features

### Global Climate

- Latitude-band energy-balance climate model
- Separate land, mixed-layer ocean, and deep-ocean heat reservoirs
- Meridional heat transport
- Land-ocean heat exchange
- Annual-mean insolation in the latitude-band energy-balance model
- Prognostic low-cloud feedback
- Snow and surface-albedo feedbacks
- Water-vapour feedback
- Lapse-rate feedback
- Deep-ocean heat uptake
- CO2 forcing using the Meinshausen et al. formulation
- SSP1-2.6
- SSP2-4.5
- SSP4-6.0
- SSP5-8.5
- Abrupt 2xCO2 experiments
- 1% CO2 experiments
- Ramp-and-hold forcing
- Overshoot experiments
- Constant-CO2 experiments
- Hybrid SSP experiments

### Arctic and Cryosphere

- Seasonal thermodynamic Arctic model
- Seasonal solar geometry, including polar night and midnight sun, within the Arctic module
- Prognostic sea-ice concentration
- Prognostic sea-ice volume
- Vertical ice growth
- Lateral melt
- New-ice formation
- Ridging
- Divergence
- Mechanical sea-ice export
- Separate Atlantic and non-Atlantic Arctic sectors
- Snow and ice albedo
- Melt-pond effects
- Ocean-atmosphere heat exchange
- Sea-ice freshwater storage
- Sea-ice freshwater export
- Greenland surface-mass-balance response
- Positive-degree-day Greenland melt
- Greenland precipitation and retention
- Greenland freshwater delivery to the North Atlantic

### AMOC and Atlantic Ocean

CLEM contains an explicitly coupled reduced-order AMOC. Its transport evolves
toward the lower of a prognostic hydraulic density capacity and an empirical,
slow forced-heat capacity benchmarked against FAFMIP experiments. FAFMIP does
not directly constrain CLEM's global-forcing-to-regional-heat mapping.

The AMOC subsystem includes:

- Five active Atlantic boxes
- External ocean salt reservoir
- Northern Atlantic box
- Tropical Atlantic box
- South Atlantic upper box
- Southern Ocean box
- Deep Atlantic reservoir
- Prognostic temperature-driven density changes
- Prognostic salinity-driven density changes
- Dynamic pycnocline depth
- Ekman inflow
- Eddy outflow
- Low-latitude upwelling
- Continuous deep-convection response
- Gyre salt exchange
- Hydrological freshwater forcing
- Greenland freshwater forcing
- Arctic sea-ice freshwater forcing
- AMOC heat transport feedback
- FAFMIP-informed empirical forced-heat sinking capacity
- Salt-advection feedback
- Freshwater hosing experiments
- Weak and collapsed AMOC states
- AMOC recovery experiments
- Equilibrium continuation
- Hysteresis diagnostics

Negative/reversed AMOC is disabled in the validated default configuration because a reverse-circulation closure has not been independently validated.

---

## Climate Sensitivity

CLEM calculates its climate sensitivity from explicit forcing experiments rather than specifying ECS as a fixed input.

| Diagnostic | CLEM v2.29.29 |
|---|---:|
| Equilibrium Climate Sensitivity (ECS) | **3.273 °C** |
| Gregory effective ECS, years 1-150 | **3.461 °C** |
| Transient Climate Response (TCR) | **1.923 °C** |
| 2xCO2 effective radiative forcing | **3.93 W m^-2** |
| Net climate feedback | **-1.144 W m^-2 K^-1** |
| Planck feedback | **-3.255 W m^-2 K^-1** |
| Water-vapour feedback | **+1.814 W m^-2 K^-1** |
| Resolved lapse-rate feedback | **-0.465 W m^-2 K^-1** |
| Water-vapour + lapse-rate | **+1.384 W m^-2 K^-1** |
| Surface-albedo feedback | **+0.302 W m^-2 K^-1** |
| Cloud feedback | **+0.425 W m^-2 K^-1** |

These inherited sensitivity values used the bulk-surface temperature field.
Current ECS, TCR, Gregory regression, and feedback normalization use
`global_near_surface_air_warming_c`. Outputs identify that field explicitly and
retain separate `bulk_surface_equilibrium_response_c` and
`bulk_surface_transient_response_c` diagnostics. The two temperature definitions
must not be treated as interchangeable in comparisons or calibration.

The equilibrium 2xCO2 experiment reaches approximately **3.27 °C warming** while retaining an AMOC strength of approximately **11.1 Sv**.

---

## AMOC and Salt-Advection Feedback

The default control configuration uses an AMOC reference strength of approximately:

**17 Sv**

### FovS

CLEM uses the conventional sign interpretation in which negative FovS represents an overturning circulation that exports freshwater from the Atlantic.

In the revised model, `fovs_sv` and `amoc_boundary_overturning_freshwater_sv`
both report the actual external boundary transport. The historical SAU/deep
quantity is retained as `amoc_internal_section_freshwater_sv`.

The default control salinity contrast is solved without an FovS target. The
specified control budget contains -0.28 Sv of Atlantic surface freshwater
exchange, +0.06 Sv of northern-boundary import, and +0.38 Sv of azonal southern
gyre import. Steady conservation then predicts:

**FovS = -0.16 Sv**

This is an equilibrium budget prediction conditional on independently estimated
control fluxes. CLEM does not yet predict absolute evaporation, precipitation,
runoff, or the azonal boundary transport, so it is not a free coupled-climate
prediction. `amoc_basin_salt_inventory_anomaly_psu_m3` tracks subsequent basin
storage changes.

In the current 5° SSP2-4.5 batch, external-boundary FovS remains negative
through 2100.

| Period | FovS |
|---|---:|
| 2081–2100 mean | **−0.10991 Sv** |
| 2100 | **−0.10725 Sv** |

Salt is explicitly conserved between the Atlantic and compensation reservoirs.

The validation integrations report a maximum salt-conservation error of:

**0.0 ppm to reported numerical precision**

---

## SSP2-4.5 Example

The SSP2-4.5 experiment produces similar global warming at 5° and 10° model resolution.

The current default uses the FAFMIP-informed forced-heat sinking-capacity proxy
described in the [September 14 forced-heat report](docs/AMOC_FORCED_HEAT_CLOSURE_2026_09_14.md).

| Current unreleased metric | 5° | 10° |
|---|---:|---:|
| AMOC, 1995–2014 | 16.083 Sv | 16.083 Sv |
| AMOC, 2081–2100 | **11.297 Sv** | **11.297 Sv** |
| AMOC decline | **29.761%** | **29.761%** |
| AMOC in 2100 | 10.952 Sv | 10.952 Sv |
| Late-century FovS | −0.1099 Sv | −0.1100 Sv |
| FovS in 2100 | −0.10725 Sv | −0.10732 Sv |
| Hydraulic target in 2100 | 16.957 Sv | 16.844 Sv |
| Forced-heat capacity in 2100 | 10.710 Sv | 10.710 Sv |

The forcing-index heat capacity is the tighter limit in this SSP run, which is
why the AMOC trajectory is common across resolutions. The grid-dependent
hydraulic targets and prognostic FovS values remain distinct. This is reduced
emulator behavior, not evidence that both grids independently predict the same
ocean circulation.

The all-SSP batch shown near the top uses automatic 1850 initialization and
gives a 29.680% SSP2-4.5 decline at 5°. The fixed-control review configuration
in this table gives 29.761%. That small difference is an initialization choice,
not independent cross-resolution agreement. Earlier trial responses are
preserved in the [convection follow-up](docs/CONVECTION_REVIEW_FOLLOWUP_2026_09_14.md)
as development history rather than current results.

---

## Freshwater Hosing Experiments

CLEM supports direct North Atlantic freshwater-forcing experiments for examining AMOC sensitivity, nonlinear weakening, collapse, and recovery.

Example 100-year experiments:

| Freshwater forcing | Final AMOC | North Atlantic temperature response |
|---|---:|---:|
| **0.1 Sv** | **13.78 Sv** | **-0.56 °C** |
| **0.2 Sv** | **9.51 Sv** | **-1.27 °C** |
| **0.3 Sv** | **4.13 Sv** | **-2.17 °C** |

A stronger **0.5 Sv** freshwater experiment reaches the collapsed branch and produces approximately:

**-3.12 °C North Atlantic cooling**

Long hosing and recovery experiments can produce persistent weak or collapsed circulation states rather than forcing the AMOC to automatically return to its initial strength.

---

## Conservation and Numerical Behaviour

CLEM contains explicit diagnostic checks for energy, salt, and ocean-volume consistency.

| Test | Result |
|---|---:|
| Forced energy-budget closure residual | **0.0435%** |
| Maximum reported salt error | **0.0 ppm** |
| Final pycnocline volume imbalance | **5.7 x 10^-7 Sv** |
| 0.05 -> 0.025 yr timestep AMOC difference | **0.0108 Sv** |
| 0.05 -> 0.025 yr timestep GMST difference | **0.00147 °C** |

The validation suite additionally tests:

- Thermal-only AMOC weakening
- Greenland freshwater forcing
- Sea-ice freshwater forcing
- Salt-advection response
- FovS behaviour
- Freshwater hosing
- AMOC collapse
- AMOC recovery
- Pycnocline closure
- Timestep convergence
- Cross-resolution consistency

---

## Arctic Sea Ice

The Arctic subsystem represents sea-ice **area and volume separately**, allowing changes in thickness and concentration to evolve independently.

The corrected R18.2 NSIDC-compatible 15% native-cell **area** comparison for the 5° configuration gives:

| Metric | March | September |
|---|---:|---:|
| Area bias | **+0.355 million km²** | **-0.055 million km²** |
| Area RMSE | **0.451 million km²** | **0.518 million km²** |
| Temporal correlation | **0.872** | **0.900** |
| Model trend | **-0.388 million km² decade^-1** | **-0.830 million km² decade^-1** |
| Observed trend | **-0.380 million km² decade^-1** | **-0.793 million km² decade^-1** |

A literal >=15% threshold applied to CLEM's coarse reconstructed concentration field is **not** treated as a satellite-resolution extent prediction. The separate fractional-support extent diagnostic is retained as a reduced-order structural footprint diagnostic and is non-release-blocking.

R18.4 additionally integrates NSIDC-0611 sea-ice age as a structural diagnostic. Authentic annual source files for **1984–2024** were processed into March/September multiyear-ice fractions with per-file SHA-256 provenance.

---

## Known Biases and Limitations

### Empirical SSP AMOC response

The current SSP AMOC magnitude is set mainly by the FAFMIP-informed empirical
forced-heat capacity. The underlying study applies regional ocean-surface heat
flux perturbations. It does not estimate CLEM's transfer from global effective
forcing, the scaled prior range, or the 20-year response time. Consequently,
the SSP5-8.5 approach toward a near-zero AMOC by 2300 and the Monte Carlo
collapse fraction are emulator sensitivity results. They are not process-only
predictions or calibrated real-world probabilities. FovS remains prognostic,
but its scenario path is conditional on the empirical AMOC transport whenever
that capacity is the active limit.

### Historical AMOC Mean State

The former fixed-alpha/beta configuration had a documented low historical AMOC
mean. The current v2.29.29 production configuration repairs that physical
density pathway with
[TEOS-10](https://www.teos-10.org/pubs/TEOS-10_Manual.pdf) on the same
reduced-order North Atlantic stratification pathway. It does not raise the
17 Sv preindustrial control anchor, retune a hydraulic coefficient, or add an
output correction.

For approximately 2004–2020:

| Dataset / Configuration | 2004–2020 AMOC |
|---|---:|
| Pre-repair fixed-alpha/beta, 10° | **~14.17 Sv** |
| Pre-repair fixed-alpha/beta, 5° | **~14.32 Sv** |
| CLEM v2.29.29 production matched-pathway TEOS-10, 10° | **~15.74 Sv** |
| CLEM v2.29.29 production matched-pathway TEOS-10, 5° | **~15.86 Sv** |
| RAPID 26.5° N | **16.9 ± 1.2 Sv** |

The nonlinear density closure reduces the pre-repair discrepancy from 2.6–2.7
Sv to about 1.0–1.2 Sv, inside the published RAPID uncertainty interval.
These are 10°/5° historical runs using the production 0.05-year integration
step, not a claim of independent calibration. The RAPID comparison is from
[Johns et al. (2023)](https://doi.org/10.1098/rsta.2022.0188).

Mechanism isolation attributes almost all of the pre-repair model's excessive
historical decline to the thermal-density pathway. Removing anomalous
freshwater changes shifts the mean by only about 0.025 Sv. At the control
temperatures, the old constant thermal expansion coefficient is
2.0e-4 K^-1, compared with TEOS-10 values of about 1.22e-4 K^-1 for the
northern box and 0.43e-4 K^-1 for the cold Southern source. The old linear
thermal (-0.001200) and haline (+0.001634) terms therefore left a fragile
0.000434 residual, whereas the direct TEOS-10 density contrast is 0.001169.
The repair changes only the equation used to translate the established thermal
and salinity coordinates into density, retaining their geometry, initial
hydrography, hydraulic coefficients, and 17 Sv control. A literal
prognostic-water-mass TEOS alternative was also tested. Although its historical
mean reached ~16.34 Sv, its SSP2-4.5 weakening was only ~6.5%, below the model's
independently declared 15–50% development range, so it was not promoted.

### Simplified Sea-Ice Geography

CLEM does not contain a high-resolution Arctic ocean grid.

Sea-ice area is therefore more directly represented than geographical sea-ice extent.

Detailed coastlines, regional ice-edge geometry, and small-scale ice transport cannot be reproduced.

### Reduced Atmospheric Dynamics

CLEM does not explicitly simulate:

- Synoptic weather systems
- Atmospheric jets
- Storm tracks
- Clouds as resolved 3-D systems
- Regional precipitation systems
- Atmospheric internal variability comparable to a GCM

These processes are represented through reduced-order parameterizations where relevant.

### Reduced Ocean Dynamics

CLEM does not explicitly resolve:

- Mesoscale ocean eddies
- Complete 3-D ocean circulation
- Detailed western boundary currents
- Regional ocean bathymetry
- Full ocean gyre dynamics
- Eddy-resolving convection

Its AMOC system should therefore be interpreted as a reduced dynamical representation rather than a substitute for an ocean GCM.

### Arctic Validation Status

Historical and recent Arctic observations were inspected during development and therefore remain **development/calibration/structural evaluation**, not untouched prospective validation.

The present observational stack contains all six intended products: NOAA/NSIDC fixed-mask concentration/area, PIOMAS volume, CryoSat-2 thickness, ICESat-2 thickness, OSI SAF area cross-check, and NSIDC-0611 multiyear sea-ice age. CryoSat-2 temporal correlation remains a documented development limitation and is not used to justify post-hoc physics tuning.

The frozen 2027–2036 prospective protocol has not yet accumulated the required future observations, so independent predictive validation is correctly reported as **`not_available`**, not as a model failure.

### AMOC Tipping Interpretation

CLEM can be used to investigate AMOC stability, collapse, recovery, and hysteresis mechanisms.

It should **not** be used to assign a precise real-world calendar year to a future AMOC tipping event.

---

## Model Purpose

CLEM is primarily intended to investigate questions such as:

- How do radiative feedbacks determine ECS?
- How does deep-ocean heat uptake affect transient warming?
- How does Arctic sea-ice loss affect climate feedbacks?
- How does Greenland meltwater influence North Atlantic salinity?
- How does Arctic freshwater export influence the AMOC?
- How does FovS affect Atlantic salt-advection feedback?
- How strongly does AMOC weaken under SSP forcing?
- How does freshwater forcing alter AMOC stability?
- Can weak or collapsed AMOC states persist after forcing is removed?
- How sensitive are these responses to model resolution and parameter choices?

The goal is not to reproduce every component of a comprehensive Earth System Model.

Instead, CLEM provides a relatively transparent coupled framework in which important climate feedbacks and ocean-circulation mechanisms can be directly inspected, modified, and experimentally tested.

---

## Running CLEM

### Requirements

Python 3.12+ is required.

```bash
python -m venv .venv
```

### Windows

```bash
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

### Linux / macOS

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
```

---

## Desktop GUI

On Windows:

```bash
run_gui.bat
```

The launcher creates a project-local `.venv` when necessary and synchronizes
all pinned runtime dependencies from `requirements.lock` before opening the
GUI. This includes the production `gsw`/TEOS-10 dependency. Subsequent launches
perform a fast version check and install only when the locked environment is
missing or out of date. An internet connection is therefore required for the
first launch or after a dependency-lock update.

Or run directly:

```bash
python climate_model_gui.py
```

---

## Streamlit Interface

```bash
streamlit run app.py
```

---

## Command Line

Display available options:

```bash
python climate_model.py --help
```

Example SSP2-4.5 experiment:

```bash
python climate_model.py --scenario ssp245 --start-year 1850 --years 250
```

Run all four supported SSP pathways in separate worker processes with identical
settings:

```bash
python climate_model.py --run-all-ssp --ssp-workers 4 --start-year 1850 --years 250 --output outputs_all_ssp
```

This writes the complete normal output set under `ssp126/`, `ssp245/`,
`ssp460/`, and `ssp585/`. At the batch root it also writes four-scenario CSVs
and plots for global near-surface air temperature, AMOC, FovS, and Northern
Hemisphere sea-ice area/extent:

- `ssp_temperature_comparison.csv` and `.png`
- `ssp_amoc_comparison.csv` and `.png`
- `ssp_fovs_comparison.csv` and `.png`
- `ssp_sea_ice_comparison.csv` and `.png`
- `ssp_combined_timeseries.csv`, containing every normal time-series field for
  every scenario in analysis-ready long form

Resume an interrupted batch with the same settings by adding
`--resume-all-ssp`. Complete compatible scenario subfolders are skipped.
Use `--ssp-workers 1` for the former sequential behavior or choose 2–4 workers
to trade additional memory use for faster completion. The default is the
smaller of four workers or the detected logical CPU count.

Available experiment types include:

- Constant CO2
- Linear forcing
- 1% CO2
- Ramp-and-hold
- Overshoot
- Abrupt 2xCO2
- SSP1-2.6
- SSP2-4.5
- SSP4-6.0
- SSP5-8.5
- Hybrid SSP pathways

---

## Validation

CLEM v2.29.29 has been tested with a physics/structural validation suite covering:

- ECS and Gregory regression
- TCR and radiative-feedback decomposition
- Energy and salt conservation
- Timestep convergence
- SSP2-4.5 response and cross-resolution consistency
- AMOC thermal weakening, FovS, and salt-advection feedback
- Greenland and Arctic freshwater routing
- Pycnocline closure
- Freshwater hosing, AMOC collapse, recovery, and structural sensitivity
- Reduced TEOS-10 AMOC EOS sensitivity
- Arctic mechanism ablations
- Sea-ice area/extent observation-operator tests
- PIOMAS, CryoSat-2, ICESat-2, OSI SAF, and NSIDC-0611 structural/development diagnostics

The release keeps the large historical numerical evidence separate from the clean source archive.

## Public release assets

CLEM v2.29.29 is distributed as a **multi-asset release** rather than one oversized source archive:

- `CLEM-v2.29.29-source.zip` — clean current source tree. Its SHA-256 is published in the accompanying `.sha256`/release asset manifest.
- `CLEM-v2.29.28-physics-repair-r13-validation-results.zip` — **80,553,730 bytes**, SHA-256 `3ebb04a5c6d609184f9576a77592c422e26d9956774ab0537111c2324708befb`. This is the large inherited Repair R11-R13 numerical evidence bundle. Its v2.29.28 name is preserved because that is the version that generated the evidence.
- `CLEM_v2.29.28_R17_validation_results.zip` — **44,545,789 bytes**, SHA-256 `c386edc134992a6e0ae45d8b7d0ecae1d726645729aa7ff2d03c86a09f1fd950`. This is the accepted R17 structural AMOC/TEOS-matched/recovery and paired 5°/10° sea-ice evidence bundle.
- `CLEM_v2.29.28_R18_validation_results_finalized.zip` — **29,314,682 bytes**, SHA-256 `69f0d2d8095e084e6464c291ca978417d9891d759ca0649106c6cee434dce4c8`. This is the finalized R18 structural/observation-operator validation bundle.
- `CLEM_v2.29.28_R18_2_seaice_operator_results.zip` — **25,318,048 bytes**, SHA-256 `d6506dfbec839528ad3c4e633c1563cf18c1fc6caf6dd94fd44dfe5ec36e0f06`. This contains the completed R18.2 5°/10° sea-ice observation-operator numerical comparison. Its historical version label is likewise preserved.

The raw NSIDC-0611 NetCDF archive is **not** a CLEM release asset. CLEM ships the processed diagnostic and full source-file SHA-256 provenance instead. Historical numerical assets are inherited by the explicit dynamics-equivalence record. They are not relabelled as newly generated v2.29.29 runs.

R15–R18.5.1 supplied the structural, observation-operator, provenance, and public-release work consolidated into v2.29.29. R18.2 supplies the completed sea-ice operator numerical evidence and R18.4 adds authentic NSIDC-0611 processed observational data. Historical evidence filenames retain `v2.29.28` where that is the version under which the numerical run was actually executed.

The preregistered 2027–2036 holdout is intentionally unavailable until future observations exist. It must not be replaced by retrospective data or manually marked as passed.

---

## Status

CLEM is a **reduced-complexity research and experimentation model**.

Current engineering integrity, numerical verification, physics verification, structural evaluation, and the six-source Arctic observational stack are complete for the frozen v2.29.29 release state. **Independent prospective predictive validation is not yet available** because the preregistered 2027–2036 observation period is in the future.

Results should be interpreted in the context of the model's simplified atmosphere, ocean, and spatial resolution. The model is particularly useful for exploring coupled feedbacks that are difficult to represent in simpler zero-dimensional climate emulators while remaining substantially more transparent and computationally inexpensive than comprehensive Earth System Models.

---

## Third-party data and scientific attribution

Dataset citations, provider acknowledgements, licence notes, and the boundary between CLEM's MIT-licensed code and externally sourced scientific data are documented in [`THIRD_PARTY_DATA.md`](THIRD_PARTY_DATA.md).

Processed third-party scientific data distributed with CLEM retain the attribution and provenance requirements of their source datasets and are not automatically relicensed under CLEM's MIT License.

---

## License

CLEM source code and original CLEM material are released under the MIT License. See `LICENSE`. Third-party datasets and derived data may be subject to separate terms. See `THIRD_PARTY_DATA.md`.
