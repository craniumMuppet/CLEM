# v2.29.16 Release Integrity and Output Organization

v2.29.16 fixes the independent v2.29.15 review findings and applies the requested AMOC-output organization changes without retuning climate, AMOC, Greenland, or sea-ice parameters.

## Resumable validation provenance

Every isolated validation task now freezes a provenance snapshot before execution and stores the task name, model version, validator SHA-256, task-relevant source-tree SHA-256, and task-configuration SHA-256 in its output envelope. `--resume` validates every field before reuse. Raw, stale, renamed, source-mismatched, or validator-mismatched task JSON files are rejected and rerun.

## Exact subannual Arctic diagnostics

After the periodic-control residual correction, seasonal and public Arctic sea-ice concentration are reconstructed from the corrected ice-energy and transient-air state at the exact end phase. Quarterly and other subannual records therefore use the same concentration state as local thickness and open-water temperature, eliminating the residual-scale inconsistency found in v2.29.15.

The invariant unforced reference manifold now uses that same closure-adjusted concentration mapping. This preserves the ordinary-equation control solution while avoiding a mismatch between the pre-closure reference concentration and the post-closure live state.

## AMOC percentage output

`monte_carlo_amoc_decline_percent_all.png` is now a primary output beside the AMOC-Sv figure rather than being placed in `diagnostics`. Its curve is signed like the AMOC transport response: a 50% weakening is plotted as `-50%`, while strengthening is positive.

The stored `amoc_decline_percent` Monte Carlo time series follows this signed convention for consistency with the displayed curve.

## Diagnostic map layout

The main `diagnostics` folder now contains weighted mean and weighted median final maps. The 1st-percentile, 99th-percentile, and 1-99% width maps are stored in `diagnostics/1_99_percentiles`. The 5th/95th-percentile and 5-95% width products remain in the main diagnostics folder.

## Audit coverage

The implementation audit now includes the active packager, validation-provenance module, v2.29.16 regression file, `tests/test_v22912_monte_carlo_integrity.py`, and all retained high-value integrity tests.
