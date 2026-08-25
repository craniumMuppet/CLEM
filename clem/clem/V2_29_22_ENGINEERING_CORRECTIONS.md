# EGCM v2.29.22 engineering corrections

## Classification

v2.29.22 remains **engineering-only**. Retrospective calibration and evaluation do not constitute prospective untouched temporal validation. Multiplier-derived extent remains explicitly non-independent.

## Relocation-safe scientific evidence

All scientific fingerprint keys are canonical paths relative to the package root. Absolute paths and `..` traversal are rejected by status finalization and packaging. Validation resolves every fingerprinted file from `Path(__file__).resolve().parent`.

The final packager extracts its archive to a new temporary directory and requires both the status finalizer and packager to succeed from that relocated tree.

## Production process ledger

The ordinary Arctic production timestep emits raw arrays for:

- reference-cycle ice and open-water transitions;
- thermodynamic formation and melt energy changes;
- mechanical export and phase-restoring energy changes;
- open-water surface energy change;
- phase-normalization, area-remap, and cleanup ocean transfers;
- formation, melt, ridging, divergence, compaction, and support area changes;
- initial and final ice, open-water, and concentration reservoirs.

`arctic_process_budget.evaluate_arctic_process_ledger()` independently reconstructs final reservoirs from those terms. It does not consume a residual calculated by the model.

The structural validator runs perturbed cold-formation and mixed melt/export/mechanics production cases. Every required process must be nonzero. Separate mutation checks corrupt formation, melt, export, phase restoring, ocean transfer, ridging, and divergence terms; every corruption must fail closure.

## Self-contained test evidence

`run_v22922_engineering_tests.py` runs the complete repository-defined non-slow inventory in one pytest invocation against one frozen tree. It writes:

- `TEST_RESULTS_V2_29_22.json` with one outcome per collected test;
- `TEST_EVENTS_V2_29_22.ndjson` as raw per-test event evidence;
- `TEST_RESULTS_V2_29_22.junit.xml` as raw JUnit evidence;
- `TEST_RESULTS_V2_29_22.txt` as a human-readable summary.

The JSON records package-relative raw-evidence names and SHA-256 hashes. No temporary shard or build-machine paths are accepted.

## Retained runtime corrections

The v2.29.21 `SimulationResult.arctic_module_blend` output fix and bounded young-ice compactness mapping are retained. At 0.01 m grid-equivalent ice, the configured mapping remains near 0.29 m local thickness rather than the former multi-metre pathology.
