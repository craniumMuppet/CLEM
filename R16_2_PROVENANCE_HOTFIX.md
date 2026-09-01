# CLEM v2.29.28 - R16.2 TEOS delta provenance hotfix

R16.2 changes verifier/provenance tooling only. `climate_model.py` is byte-identical
to R16.1 (`08662fef5d83154d8bc43420705a937c6acbc4b52b4677a6e20536d73193506e`).

The R16.1 TEOS delta launcher incorrectly inherited a Repair-R11/R13 baseline gate
that only accepted changes proven to be CLI/name-only. That gate was valid for the
historical R13 release-consistency case but invalid for R16.1, because R16.1
intentionally changed `validate_initial_amoc_density_margin()` to stop applying a
linear-EOS calibration envelope to TEOS-10.

R16.2 replaces that unrelated gate with `R16_TEOS_DELTA_PROVENANCE.json` plus an
exact bundled R16 parent snapshot. Validation requires:

- R16 source ZIP SHA-256 `e4a890150dc95f8bbb8a4340676b5d1e795c064503299ac258ec154dce5c8ab7`;
- R16 `climate_model.py` SHA-256 `ddcd2272bf2d10ed9d9eacb9fabdc5e65db7fdfc3e3e23a09e85d5bfffc2ba40`;
- current/R16.1 `climate_model.py` SHA-256 `08662fef5d83154d8bc43420705a937c6acbc4b52b4677a6e20536d73193506e`;
- identical top-level AST after excluding only `validate_initial_amoc_density_margin`.

This is deliberately **not** called full dynamics equivalence: the TEOS preflight
behavior changed intentionally. The proof instead demonstrates that all other
`climate_model.py` top-level code is unchanged from R16.
