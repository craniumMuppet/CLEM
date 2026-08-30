# Versioning

The full public model name is **Coupled Low-complexity Earth Model (CLEM)**.

CLEM has one authoritative model version and a separate repair-workflow revision.

## Model version

**2.29.28**

Authoritative sources:

- `climate_model.py` — `MODEL_VERSION = "2.29.28"`
- `pyproject.toml` — `version = "2.29.28"`

The extensive `v2.29.x` validators, tests, comments, engineering notes, and historical results belong to the real CLEM model-development lineage.

## Physics-repair revision

**R13**

R13 is a provenance label for the repair/validation workflow that produced the current validated package. It is not a semantic model version and must not be displayed as `CLEM v2.13`.

Earlier repair artifacts originally used labels `v2.11`, `v2.12`, and `v2.13`. In current public documentation these are referred to as **Repair R11**, **Repair R12**, and **Repair R13**. Raw evidence retains original filenames/hashes where necessary for provenance.

## Recommended GitHub release name

`Coupled Low-complexity Earth Model v2.29.28 — Physics Repair R13`

Recommended tag if a distinct tag is needed without changing `MODEL_VERSION`:

`v2.29.28-physics-r13`
