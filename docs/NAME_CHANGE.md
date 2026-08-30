# Model name

The model's full public name is **Coupled Low-complexity Earth Model**. The abbreviation **CLEM** may be used in filenames, repository shorthand, and prose after the full name has been introduced.

## Previous name

Earlier releases and historical result files used **Emergent-Sensitivity Global Climate Model** (and a few older variants such as **Emergent Global Climate Model**). Those historical outputs are preserved byte-for-byte where possible because changing them would alter provenance. They do not define the current model name.

## Numerical effect

The rename changes model identity strings and therefore changes the byte-level SHA-256 of `climate_model.py`, but it does not change numerical equations, defaults, or prognostic dynamics. Repair R13 verifies this by hashing the model AST while excluding only the public CLI parser and the `MODEL_NAME` metadata constant.
