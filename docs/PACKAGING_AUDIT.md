# Coupled Low-complexity Earth Model v2.29.28 packaging audit

## Scope

This audit covers the branding-only rename of the current model from **Emergent-Sensitivity Global Climate Model** to **Coupled Low-complexity Earth Model (CLEM)**. Model/runtime version **2.29.28** and Physics Repair **R13** are unchanged.

## Source-tree preservation

The renamed tree was compared file-for-file against the immediately preceding audited `CLEM-v2.29.28-source.zip`:

- predecessor files: **693**
- renamed-tree files: **694**
- missing predecessor files: **0**
- added files: **1** (`docs/NAME_CHANGE.md`)
- modified files: **31**, all attributable to branding, release identity, tests that assert branding, release-finalization tooling, or the name-only equivalence/fingerprint metadata

No model/data/test/tool path was deleted. Historical result artifacts were not rewritten merely to change their old display name.

## Numerical equivalence

The byte-level `climate_model.py` hash changes because `MODEL_NAME` and the CLI description changed. Numerical equivalence is checked with a normalized AST that excludes only:

- `MODEL_NAME` (release metadata only)
- `build_parser()` (public CLI surface already excluded by Repair R13)

The normalized dynamics/configuration AST is identical before and after the rename:

`ad7687f6833c102337ebdbe13369837d15d2c1b672042d30d5f86fbc1ac7e574`

The bundled Repair R11 numerical baseline is still accepted by the Repair R13 equivalence guard.

## Active identity surfaces

The authoritative full name is **Coupled Low-complexity Earth Model**. The following current surfaces use that identity:

- `climate_model.py` (`MODEL_NAME`)
- desktop GUI title
- Streamlit page/title
- CLI help description
- output metadata exported through `MODEL_NAME`
- `pyproject.toml` project name/description
- README and release metadata
- Windows/Linux release and validation launchers
- release-identity checker

Historical `TEST_RESULTS_V2_*` and archived provenance may retain the previous name because those files document what was actually emitted at the time.

## Regression checks

- release identity check: **PASS**
- zero-climate-year physics/release consistency: **PASS**
- name/GUI/release targeted tests: **7 passed**
- complete historical test collection: **427 tests collected**
- normalized dynamics/configuration AST before/after rename: **identical**
- known inherited Arctic observational-data availability failures remain external-data/provenance issues and are unrelated to this rename
