# CLEM v2.13 GitHub packaging audit - second full pass

Date: 2026-08-30

## Scope

This audit was redone from scratch after the first GitHub-source cleanup was found to be over-pruned. The final source package is checked against four independent sources of truth:

1. the original `CLEM-main.zip` repository;
2. the validated `CLEM-physics-repair-v2.13-release-consistency.zip` package;
3. the original v2.11 full numerical verification bundle;
4. the original v2.12 held-out validation bundle.

## File preservation

- Original inner repository tree: 619 files.
- Validated v2.13 inner tree: 631 non-cache files (656 including generated cache artifacts in the repair ZIP).
- Original inner files missing from validated v2.13: **0**.
- Validated v2.13 non-cache files missing from final GitHub source: **0**.
- All 22 outer files from the v2.13 release package are preserved: root repository control files stay at root; the remaining release-package files are archived verbatim under `docs/v2.13/release-package-root/`.

Three validated inner paths intentionally differ in the GitHub source:

- `README.md`: GitHub usage/versioning documentation;
- `.github/workflows/ci.yml`: current self-contained release CI instead of the inherited external-data-dependent full historical suite;
- `.gitignore`: replaced at repository root by the original full repository-level `.gitignore`; the exact validated inner `.gitignore` is preserved as `docs/v2.13/inner-tree.gitignore`.

The validated climate-model source itself is unchanged.

## Repository-root files restored

The first cleanup missed outer repository files. The final package restores the originals byte-for-byte:

- `LICENSE` (MIT)
- `.gitattributes`
- full repository `.gitignore`

The original repository root README is preserved under `docs/original-repository-root/README.md`.

## GUI and launcher audit

The final package includes:

- `run_gui.bat`
- `launch_gui.pyw`
- `climate_model_gui.py`
- `run_gui_debug.bat`
- `run_gui.sh`
- `run_app.bat`
- `run_app.sh`
- all current verification `.cmd` launchers
- all referenced PowerShell acquisition scripts

`run_gui.bat` resolves to both `launch_gui.pyw` and the console fallback `climate_model_gui.py`. `climate_model_gui.main` imports successfully. The dedicated GUI launcher regression suite passes 3/3.

Linux/macOS documentation uses `bash run_gui.sh` / `bash run_app.sh`, so execution does not depend on ZIP executable-bit preservation. Shell scripts are also stored executable in the rebuilt archive where supported.

## Python/import audit

- 210 Python/PYW files parsed in the reconstructed source tree before release-root archival additions.
- Missing project-local imports: **0**.
- `climate_model` imports successfully.
- `climate_model_gui` imports successfully.
- Streamlit is pinned as `streamlit==1.60.0` in `requirements.lock`. The audit container itself does not have Streamlit installed, so `app.py` is not imported there without installing the declared dependencies.

## Static and test audit

From a clean tree:

- full `compileall`: PASS;
- `python climate_model.py --help`: PASS;
- v2.13 zero-year release consistency: PASS;
- GUI startup regression: 3/3 PASS;
- complete historical pytest discovery: 427 tests collected.

The inherited full historical test suite is **not** claimed to be all-green without its external Arctic observational data state. Four early Arctic observational-stack tests fail identically in both the untouched validated v2.13 package and the reconstructed GitHub tree. These are inherited data-state/metadata expectations, not missing-package regressions. Current GitHub CI therefore runs self-contained release checks and verifies that the complete historical suite still collects.

## Git audit

After cache removal, `git check-ignore` reports **0 delivered files** that would be silently excluded by the repository `.gitignore` when committing the unpacked source tree.

## ZIP/path audit

The final archive is checked for:

- ZIP CRC/integrity errors: none;
- path traversal (`..`) or absolute paths: none;
- case-insensitive filename collisions: none;
- Windows reserved-name collisions: none;
- paths over 220 characters: none;
- `__pycache__`, `.pyc`, and `.pytest_cache` artifacts: none.

## Numerical validation asset audit

The two raw bundles inside `CLEM-v2.13-validation-results.zip` are byte-identical to the user's original uploads:

- v2.11 full physics bundle SHA-256: `8e3f9e692f7d87d6f60b2312bbbe1f14aec7eaef029d465c4011fe6af3faa63b`
- v2.12 held-out validation bundle SHA-256: `6f2adc2b1203d54d85d8e4ce0c082f00d66e813eb0e92389d3232818f10cfced`

The validation asset's internal `SHA256SUMS.txt` verifies successfully.

## Versioning clarification

The model/runtime version remains `2.29.28` in `MODEL_VERSION` and `pyproject.toml`. `v2.13` is the physics-repair/release-consistency package revision used by this workflow. The final README states this explicitly; no model-version code was changed to relabel the validated dynamics.

Two dependency-lock header comments still mention the historical lock-generation label `EGCM v2.29.23`; the dependency pins themselves are retained unchanged from the validated source. This is documented rather than silently editing a validated dependency lock.
