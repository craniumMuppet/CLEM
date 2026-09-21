# CLEM v2.29.28 Physics Candidate R17

R17 addresses the three issues left after the completed R16/R16.2 evidence without retuning already-passing default AMOC behavior.

## 1. Prognostic conservative sea-ice support state

R16 showed that a concentration-only diagnostic reconstruction remained too spatially diffuse. R17 therefore adds a separate unresolved **ice-support fraction** to each native Arctic latitude band and ocean sector. It is a geometric state, not additional ice mass.

- Existing prognostic sea-ice concentration and latent-energy equations remain the ice-area/volume authority.
- Support is constrained to be at least the native concentration (SIC cannot exceed 100%) and at most concentration / 0.15 (occupied support cannot imply SIC below the 15% extent threshold).
- Support evolves from the model's existing formation, melt, divergence, compaction, and mechanical spreading process ledger.
- Ridging changes overlap/thickness inside the support and does not directly move the outer footprint.
- The unperturbed reference support uses the fixed 80% pack/MIZ boundary; the marginal thermodynamic support conversion uses the midpoint of the fixed 15-80% MIZ definition. Neither quantity is fitted to observed CLEM area/extent error.
- The observation operator integrates prognostic support for 15% extent while native ice area is unchanged exactly.
- If support is absent, the R16 conservative reconstruction remains a backwards-compatible fallback.

This is a candidate physical spatial degree of freedom. It is **not accepted merely because it is conservative**; the local 1850-2025 hybrid-forcing and future Arctic runs must show whether the resulting extent is credible.

## 2. Matched-pathway TEOS-10 branch

R16.2 established that the earlier TEOS branch mixed two structural changes: nonlinear EOS plus a direct North-surface versus Southern-surface thermal pathway. That branch remains available as `teos10_surface_watermass` (and legacy alias `teos10`) for attribution.

R17 adds `amoc_density_eos=teos10_matched`. It preserves the exact effective thermal contrast used by the validated linear hydraulic branch, but evaluates density nonlinearly with GSW/TEOS-10. This isolates the EOS change much more cleanly. The default remains `linear`.

## 3. Collapse/recovery is mapped, not forced

The R16 +0.8 Sv collapse followed by zero added hosing remained collapsed to year 700. Inspection showed that this can be a genuine reduced-order alternative equilibrium: after collapse the North stays very fresh while the model retains its climatological northern freshwater forcing and salt-advection feedback.

R17 therefore does **not** add a restart threshold, artificial background recovery flux, or retune `amoc_reference_sv`. Instead it runs one 250-year collapse seed, then clones that exact checkpoint into three de-hosing branches: -0.05, -0.10, and -0.20 Sv through year 700. This maps the recovery side of the hysteresis structure without prescribing the answer.

## Local validation

All integrations are child processes advancing at most 5 model years and writing atomic restart checkpoints. Re-running the same launcher resumes from the latest committed checkpoint.

- `run_r17_local_validation.bat` — all 11 changed/new experiments. Requires GSW because the TEOS stage is included.
- `run_r17_sea_ice_validation.bat` — four sea-ice experiments only with monthly output for March/September evaluation; no GSW dependency.
- `run_r17_teos_validation.bat` — three matched-TEOS experiments only; requires GSW.
- `run_r17_recovery_validation.bat` — one collapse seed plus three de-hosing branches; no GSW dependency.

The output is `CLEM_v2.29.28_R17_validation_results.zip`. Upload that ZIP for numerical review.

R16/R16.2 accepted evidence is not rerun unnecessarily. R17 numerical acceptance remains pending until the local result bundle is reviewed.
