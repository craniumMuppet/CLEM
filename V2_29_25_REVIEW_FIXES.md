# v2.29.25 review fixes

> **Historical note:** This document records the earlier v2.29.25 engineering review stage. The later Arctic scientific-validation corrections are documented in `SCIENTIFIC_REVIEW_FIXES_2026.md` and supersede its sea-ice calibration interpretation.

This release addresses review findings 1, 2, 4, 5 and 6 from the v2.29.24 package. Review finding 3 (the complete 52-test slow inventory) is intentionally out of scope by request.

## 1. Emergency safeguards removed from science uncertainty

`arctic_max_equivalent_thickness_m` and `arctic_max_local_ice_thickness_m` are no longer members of `MONTE_CARLO_PHYSICAL_PARAMETERS` or `SCIENCE_PRIOR_SPECS`. Metadata classifies them as numerical/operational safety controls.

## 2. Local safeguard cannot control projected area

The v2.29.24 production code imposed `concentration >= equivalent_thickness / max_local_thickness`. v2.29.25 removes that production floor. The threshold is fail-fast only: a state below it is unchanged; a breach raises `FloatingPointError` instead of modifying area. A private 12 m regularizer is retained only inside periodic reference-cycle iteration to preserve solver convergence.

The grid-equivalent threshold is also fail-fast: it no longer clips latent energy or transfers excess energy to the ocean.

## 4. Reproducible tested-input fingerprint

`release_tree_fingerprint.py` provides a `tested-code` profile with the complete file inventory and SHA-256 aggregate. It includes release Markdown because regressions inspect those documents, and excludes generated evidence so evidence writing does not alter the tested identity.

## 5. Clean pytest provenance

Current pytest evidence is generated from the final `emergent_global_climate_model_v2_29_25` package directory. Historical v2.29.24 logs are retained only as historical artifacts.

## 6. Direct thick-pack-resistance behavior test

Focused regression coverage verifies resistance is one for control-or-thinner floes, decreases for thicker floes, strengthens with the exponent, suppresses only the volume-deficit area-retreat support term, and leaves supplied latent ice volume unchanged.
