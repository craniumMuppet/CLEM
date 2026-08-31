# CLEM — Coupled Low-complexity Earth Model

**CLEM v2.29.28** is a process-based reduced-complexity climate model written in Python.

It couples global temperature, ocean heat uptake, radiative feedbacks, Arctic sea ice, Greenland meltwater, Atlantic salinity, and a dynamically evolving Atlantic Meridional Overturning Circulation (AMOC).

CLEM is intended for **climate-process experiments, sensitivity studies, teaching, and model development** rather than as a replacement for a comprehensive General Circulation Model (GCM) or Earth System Model (ESM).

Climate sensitivity is not prescribed directly. **ECS and TCR emerge from the model's radiative feedbacks, ocean heat uptake, and coupled dynamics.**

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

| Diagnostic | CLEM v2.29.28 |
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

| Resolution | Late/FInal FovS |
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

Historical/development evaluation of the 5° configuration gives approximately:

| Metric | Result |
|---|---:|
| March sea-ice area RMSE | **0.51 million km²** |
| September sea-ice area RMSE | **0.52 million km²** |
| September sea-ice area trend | **-0.791 million km² decade^-1** |
| Observational comparison trend | **-0.846 million km² decade^-1** |

Sea-ice extent is less accurately represented than sea-ice area because extent is reconstructed from the model's coarse Arctic concentration field rather than being simulated on a high-resolution geographical ice grid.

---

## Known Biases and Limitations

### Low Historical AMOC Mean State

The largest documented mean-state bias is the historical AMOC strength.

For approximately 2004-2020:

| Dataset / Configuration | AMOC |
|---|---:|
| CLEM 10° | **~14.17 Sv** |
| CLEM 5° | **~14.32 Sv** |
| RAPID-era observational comparison | **16.9 ± 1.2 Sv** |

The modeled historical AMOC is therefore approximately:

**2.6-2.7 Sv lower than the observational comparison**

or roughly:

**15-16% too weak**

This bias is documented rather than removed using post-hoc tuning against the validation period.

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

Historical and recent Arctic sea-ice observations were inspected during development.

They should therefore be considered **development/calibration evaluation**, rather than completely untouched prospective validation.

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

Python 3.12+ is recommended.

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

CLEM v2.29.28 has been tested with a physics-validation suite covering:

- ECS
- Gregory regression
- TCR
- Radiative-feedback decomposition
- Energy conservation
- Salt conservation
- Timestep convergence
- SSP2-4.5 response
- Cross-resolution consistency
- AMOC thermal weakening
- FovS
- Salt-advection feedback
- Greenland freshwater forcing
- Arctic sea-ice freshwater storage
- Arctic freshwater export
- Pycnocline closure
- Freshwater hosing
- AMOC collapse
- AMOC recovery

The numerical validation results are distributed separately as:

```text
CLEM-v2.29.28-physics-repair-r13-validation-results.zip
```

---

## Status

CLEM is a **reduced-complexity research and experimentation model**.

Results should be interpreted in the context of the model's simplified atmosphere, ocean, and spatial resolution.

The model is particularly useful for exploring coupled feedbacks that are difficult to represent in simpler zero-dimensional climate emulators while remaining substantially more transparent and computationally inexpensive than comprehensive Earth System Models.

---

## License

MIT License.