# EGCM v2.29.23 engineering corrections

## Classification

v2.29.23 remains **engineering-only**. Scientific release remains false because the available sea-ice and coupled evidence is retrospective and development-inspected rather than prospective untouched temporal validation.

## Canonical tested-tree provenance

`release_tree_fingerprint.py` defines one deterministic package-relative inventory covering executable source, desktop and Streamlit GUI code, all tests, validation and packaging tools, launch scripts, dependency/configuration files, release-facing Markdown documentation, and packaged runtime data. Generated evidence and transient caches are excluded.

`run_v22923_engineering_tests.py` computes the full inventory and aggregate SHA-256 before pytest, runs the complete repository-defined non-slow suite once, recomputes the inventory afterward, and fails the runner if the tree changed. The complete file inventory and per-file hashes are embedded in `TEST_RESULTS_V2_29_23.json`.

The status finalizer and packager import the same fingerprint implementation and require the current tree to reproduce the test-evidence inventory exactly. A post-test syntax error, source edit, test edit, tool edit, or documentation edit therefore invalidates finalization and packaging.

Both tools bootstrap the relocated release root onto `sys.path` before importing the shared fingerprint module. Their documented direct commands are exercised in subprocess regression tests, so execution does not depend on an external `PYTHONPATH`.

## Packaging runtime gates

Before packaging, and again after relocation, the packager requires:

- full Python `compileall` success;
- import success for the model, desktop GUI, validation entrypoints, process-budget evaluator, and tree-fingerprint module;
- exact matching Streamlit dependency pins in `pyproject.toml` and `requirements.lock`, while `compileall` covers the Streamlit app itself;
- GUI command-builder smoke success;
- real Tk desktop-GUI construction and destruction under a graphical display or `xvfb-run`.

## Actual receiving-reservoir conservation

Each production Arctic ledger entry records:

- initial and final sea-ice latent energy and open-water sensible heat;
- initial, post-internal-transfer, and final Arctic mixed-layer ocean heat;
- the actual ocean-surface exchange transition;
- initial and final Atlantic lower-latitude mixed-layer heat;
- initial and final non-Atlantic lower-latitude mixed-layer heat;
- the lower-latitude routing shape and receiving-ocean fractions;
- all existing area-process terms and final concentration.

The independent evaluator derives the energy that must leave the surface reservoirs from their actual initial/final states. It compares that requirement with the actual Arctic mixed-layer receiver change, verifies the final ocean state after surface exchange, and verifies both the global amount and spatial routing of lower-latitude phase-restoring/export compensation.

Declared transfer arrays remain diagnostics; they are no longer accepted as proof that the receiving reservoir was updated.

## Implementation mutation gates

The structural validator executes three production subclasses:

1. suppress the Arctic mixed-layer receiver update;
2. reverse the Arctic mixed-layer receiver update;
3. misroute lower-latitude compensation into the Arctic region.

All three must fail the independent receiving-reservoir closure. No mutation gate edits a completed ledger record.

## Evidence

The version-matched package contains complete 5° and 10° runs from 1850 through 2100, matched no-Greenland-freshwater sensitivities, combined validation status, tree-bound non-slow pytest JSON/NDJSON/JUnit evidence, canonical package status, complete file manifest, ZIP checksum, and relocation verification.
