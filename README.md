# Coupled Low-complexity Earth Model v2.29.28

**Abbreviation: CLEM**  
**Validated Physics Repair: R13**

The Coupled Low-complexity Earth Model (CLEM) is a physically based reduced-complexity Earth-system model coupling global climate, ocean heat uptake, Arctic sea ice, Greenland freshwater forcing, and the AMOC.

## Version identity

The model/runtime version is **2.29.28**. This is authoritative in both:

- `climate_model.py`: `MODEL_VERSION = "2.29.28"`
- `pyproject.toml`: `version = "2.29.28"`

**R13 is not a CLEM model version.** It is the thirteenth repair/validation iteration used to produce this validated package. Files carrying `V2_11`, `V2_12`, or `V2_13` in the repair-validation provenance refer to those internal repair iterations; historical files carrying `V2_29_x` refer to the actual CLEM 2.29.x model lineage.

See `docs/VERSIONING.md`, `docs/NAME_CHANGE.md`, and `RELEASE_METADATA.json`.

## Install

Python 3.12+ is recommended.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Run

### Desktop GUI

Windows: double-click:

```text
run_gui.bat
```

Debug launcher:

```text
run_gui_debug.bat
```

Linux/macOS:

```bash
bash run_gui.sh
```

Direct Python fallback:

```bash
python climate_model_gui.py
```

### Streamlit UI

```bash
streamlit run app.py
```

Windows convenience launcher: `run_app.bat`  
Linux/macOS: `bash run_app.sh`

### Command line

```bash
python climate_model.py --help
```

## Current verification commands

- `RUN_RELEASE_CONSISTENCY.cmd` — static/setup release check; advances zero climate years.
- `RUN_OUT_OF_SAMPLE_VALIDATION.cmd` — SSP2-4.5 5°/10° and untuned hosing-dose validation.
- `RUN_PHYSICS_VERIFICATION.cmd` — complete checkpointed physics suite.

Expensive verification integrations are split into restartable chunks of at most five model years.

## Validated headline results

- Equilibrium ECS: **3.273 °C**
- TCR: **1.923 °C**
- SSP2-4.5 warming, 2081–2100 vs 1850–1900: **2.671 °C (10°)** / **2.655 °C (5°)**
- SSP2-4.5 AMOC decline: **41.87% (10°)** / **38.60% (5°)**
- Forced energy-closure residual: **0.0435%**
- Salt conservation: passes to reported precision

Full numerical evidence is distributed separately as the GitHub Release asset:

`CLEM-v2.29.28-physics-repair-r13-validation-results.zip`

See `docs/VALIDATION.md`.

## Known limitation

The model's 2004–2020 AMOC mean is approximately **14.2 Sv**, below the RAPID-era comparison used during validation. This held-out discrepancy is documented rather than post-hoc tuned. See `docs/MODEL_LIMITATIONS.md`.

## Historical model records

The repository intentionally retains v2.29.x engineering notes, validators, tests, and evidence. These are the actual model-development lineage and are not stale references to the R13 repair workflow.
Historical result/provenance files may still contain the previous public name, **Emergent-Sensitivity Global Climate Model**. They are preserved as historical evidence; the current public name is defined in `docs/NAME_CHANGE.md`.

Some inherited observational-data tests require external Arctic observational stack state and are not standalone GitHub CI gates. The complete test suite is retained for provenance and targeted reproduction.

## License

MIT License. See `LICENSE`.
