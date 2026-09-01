# Versioning

The full public model name is **Coupled Low-complexity Earth Model (CLEM)**.

## Current model version

**2.29.29**

Authoritative sources:

- `climate_model.py` — `MODEL_VERSION = "2.29.29"`
- `pyproject.toml` — `version = "2.29.29"`
- public release tag — `v2.29.29`

All active runtime, GUI, CI, launcher, validator, packaging, and release-integrity surfaces use v2.29.29.

## Historical numerical evidence

Some packaged result, validation, and provenance filenames intentionally retain **v2.29.28** or earlier version labels. Those files are historical evidence generated under those exact version identities and are not renamed because doing so would falsify numerical provenance.

The v2.29.29 release is linked to the immediately preceding validated v2.29.28/R18.5.1 tree by `V2_29_29_DYNAMICS_EQUIVALENCE.json`. The v2.29.29 version bump does not retune governing physics, so the validated v2.29.28 numerical evidence is inherited explicitly rather than relabelled.

## Repair-workflow revisions

Repair labels such as **R13** and maintenance labels R15–R18.x are provenance/workflow labels, not semantic model versions. They must not be displayed as `CLEM v2.13`, `CLEM v18`, or similar.

## Recommended GitHub release

Release name: `Coupled Low-complexity Earth Model v2.29.29`

Tag: `v2.29.29`

## Current versus historical fingerprints

`V2_29_29_RELEASE_TREE_FINGERPRINT.json` is the active v2.29.29 release-tree fingerprint. The generic historical `SOURCE_FINGERPRINT.json` is retained for repair-line/prospective-protocol provenance and must not be interpreted as the current package identity.
