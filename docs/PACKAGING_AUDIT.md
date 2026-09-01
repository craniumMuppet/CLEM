# Coupled Low-complexity Earth Model v2.29.29 packaging audit

## Scope

This audit covers the v2.29.29 public-release consolidation. Active model/runtime identity is v2.29.29. Historical numerical and provenance artifacts retain the version labels under which they were generated.

## Preservation rule

The release is built from the validated R18.5.1 public-release tree. No governing numerical result is renamed to imply a v2.29.29 rerun. The version bump is documented by `V2_29_29_DYNAMICS_EQUIVALENCE.json`.

## Public-release contents

- current CLEM v2.29.29 runtime and GUI
- v2.29.29 validators, CI, launchers, packaging, and identity checks
- R18.2 sea-ice observation-operator evidence
- R18.4 NSIDC-0611 processed observational data and provenance
- public README, scientific references, `THIRD_PARTY_DATA.md`, and MIT code license
- frozen 2027–2036 prospective-validation protocol

## Validation status

Engineering/physics/static verification and existing numerical/structural evidence are retained. Independent prospective predictive validation remains `not_available` because the preregistered future observations do not yet exist.
