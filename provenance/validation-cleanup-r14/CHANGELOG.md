# CLEM v2.29.28 - validation-cleanup R14 candidate

This candidate is a **non-physics cleanup** built on the verified R13 source. It does not change the validated climate evolution equations.

## Fixed

- Removed the contradictory requirement that coarse two-sector satellite-style spatial extent must independently validate before current engineering/physics prerequisites can pass. Extent remains a diagnostic and is not manually set true.
- Removed retrospective September temporal-skill scores from the current release prerequisite conjunction. They remain development diagnostics and do not establish prospective skill.
- Added explicit `not_available` semantics for independent prospective predictive validation while retaining backwards-compatible aliases.
- Repaired desktop GUI drift so physical defaults resolve from the canonical `ModelConfig`.
- Removed the dead `amoc_pycnocline_relaxation_years` control from active GUI, Streamlit and Monte Carlo surfaces while preserving hidden backwards-compatible parsing.
- Classified CryoSat-2/ICESat-2 exact annual temporal correlation as a retrospective development diagnostic, not a release gate.
- Restored seven frozen processed observational CSVs to the CRLF byte representation already recorded by their historical SHA-256 provenance and protected those exact paths from Git line-ending normalization.
- Added regression tests for validation semantics and interface parity.

## Not changed

- EBM/radiative/ocean-heat dynamics.
- Sea-ice evolution physics.
- AMOC evolution equations.
- Greenland evolution/freshwater routing physics.
- Historical R13 result/provenance JSONs.

## Verification

- `climate_model.py` is AST-identical to R13 when the deliberately modified CLI parser is excluded.
- 56 bounded lightweight targeted tests passed; 1 known slow packaging-runtime smoke was deliberately deselected.
- No expensive climate integration was run by the assistant.

## Still requiring scientific work

See `CURRENT_R13_SOURCE_AUDIT.md` and `CRYOSAT2_DIAGNOSTIC.md`. The highest-priority physics items remain coherent AMOC water-mass density geometry/TEOS-10 sensitivity and physically correct Greenland land-ice freshwater routing.
