# Coupled Low-complexity Earth Model v2.29.29

**Abbreviation: CLEM**  
**Current release: v2.29.29**  
**Validation/release maintenance lineage: R18.5.1 / R18.6 public-release consolidation**

**CLEM v2.29.29** is a process-based reduced-complexity climate model written in Python.

It couples global temperature, ocean heat uptake, radiative feedbacks, Arctic sea ice, Greenland meltwater, Atlantic salinity, and a dynamically evolving Atlantic Meridional Overturning Circulation (AMOC).

CLEM is intended for **climate-process experiments, sensitivity studies, teaching, and model development** rather than as a replacement for a comprehensive General Circulation Model (GCM) or Earth System Model (ESM).

Climate sensitivity is not prescribed directly. **ECS and TCR emerge from the model's radiative feedbacks, ocean heat uptake, and coupled dynamics.**

## Current release status

**v2.29.29** is the public-release consolidation of the validated R15–R18.5.1 repair, structural-validation, observation-integration, packaging, and attribution work. The version bump itself changes release identity only; it does not retune the governing climate, AMOC, Greenland, or sea-ice dynamics. Existing v2.29.28 numerical evidence is retained as inherited evidence and is linked to v2.29.29 by an explicit dynamics-equivalence record.

R18.4 completed the sixth-source Arctic observational stack by processing authentic **NSIDC-0611 v4/v4.1 EASE-Grid Sea Ice Age** files for 1984–2024. The Arctic observational stack is now **6/6 available**. Independent predictive scientific validation remains **`not_available`** until the preregistered 2027–2036 prospective holdout observations exist.

See `RELEASE_NOTES_V2_29_29.md`, `V2_29_29_DYNAMICS_EQUIVALENCE.json`, `R18_2_RESULTS_REVIEW.md`, `R18_4_NSIDC_0611_INTEGRATION.md`, `R18_5_PUBLIC_RELEASE_MERGE.md`, `docs/VALIDATION.md`, and `docs/MODEL_LIMITATIONS.md`.

---

## Features

### Global Climate

- Latitude-band energy-balance climate model
- Separate land, mixed-layer ocean, and deep-ocean heat reservoirs
- Meridional heat transport
- Land-ocean heat exchange
- Seasonal solar geometry
- Polar night and midnight sun
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

CLEM contains an explicitly coupled reduced-order AMOC rather than prescribing AMOC strength directly from global temperature.

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

The equilibrium 2xCO2 experiment reaches approximately **3.27 °C warming** while retaining an AMOC strength of approximately **11.1 Sv**.

---

## AMOC and Salt-Advection Feedback

The default control configuration uses an AMOC reference strength of approximately:

**17 Sv**

### FovS

The reference overturning freshwater transport at approximately 34.5°S is:

**FovS = -0.150 Sv**

CLEM uses the conventional sign interpretation in which negative FovS represents an overturning circulation that imports salt into the Atlantic / exports freshwater.

This allows an active Atlantic **salt-advection feedback**.

When AMOC weakens:

1. Northward salt transport decreases.
2. The northern Atlantic freshens.
3. Surface density decreases.
4. Deep convection weakens.
5. AMOC weakens further.

Under SSP2-4.5, FovS remains negative through 2100.

| Resolution | Late/final FovS |
|---|---:|
| 5° | **-0.102 Sv** |
| 10° | **-0.097 Sv** |

Salt is explicitly conserved between the Atlantic and compensation reservoirs.

The validation integrations report a maximum salt-conservation error of:

**0.0 ppm to reported numerical precision**

---

## SSP2-4.5 Example

The SSP2-4.5 experiment produces similar global warming at 5° and 10° model resolution.

| Metric | 5° | 10° |
|---|---:|---:|
| Historical warming, 2011-2020 vs 1850-1900 | 1.020 °C | 1.027 °C |
| Warming, 2081-2100 vs 1850-1900 | **2.655 °C** | **2.671 °C** |
| AMOC, 1995-2014 | 14.98 Sv | 14.88 Sv |
| AMOC, 2081-2100 | **9.20 Sv** | **8.65 Sv** |
| AMOC decline | **38.60%** | **41.87%** |
| Minimum AMOC | 8.83 Sv | 8.25 Sv |
| Final FovS | -0.102 Sv | -0.097 Sv |

The cross-resolution difference in late-century global warming is approximately:

**0.016 °C**

The corresponding difference in AMOC decline is approximately:

**3.27 percentage points**

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
historical decline to the thermal-density pathway; removing anomalous
freshwater changes shifts the mean by only about 0.025 Sv. At the control
temperatures, the old constant thermal expansion coefficient is
2.0e-4 K^-1, compared with TEOS-10 values of about 1.22e-4 K^-1 for the
northern box and 0.43e-4 K^-1 for the cold Southern source. The old linear
thermal (-0.001200) and haline (+0.001634) terms therefore left a fragile
0.000434 residual, whereas the direct TEOS-10 density contrast is 0.001169.
The repair changes only the equation used to translate the established thermal
and salinity coordinates into density, retaining their geometry, initial
hydrography, hydraulic coefficients, and 17 Sv control. A literal
prognostic-water-mass TEOS alternative was also tested; although its historical
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

Run all four supported SSP pathways sequentially with identical settings:

```bash
python climate_model.py --run-all-ssp --start-year 1850 --years 250 --output outputs_all_ssp
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
`--resume-all-ssp`; complete compatible scenario subfolders are skipped.

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

The raw NSIDC-0611 NetCDF archive is **not** a CLEM release asset. CLEM ships the processed diagnostic and full source-file SHA-256 provenance instead. Historical numerical assets are inherited by the explicit dynamics-equivalence record; they are not relabelled as newly generated v2.29.29 runs.

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

CLEM source code and original CLEM material are released under the MIT License. See `LICENSE`. Third-party datasets and derived data may be subject to separate terms; see `THIRD_PARTY_DATA.md`.
