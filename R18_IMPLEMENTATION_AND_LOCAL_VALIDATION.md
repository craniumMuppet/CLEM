# R18 implementation and local validation

R18 changes only the sea-ice support reference/validation operator and the local recovery experiment design. It does not retune the default AMOC.

## Sea ice

The support reference is now thermodynamic: the existing 80% pack/MIZ boundary remains the warm limit, while representative pack concentration approaches 100% under cold conditions using the model's existing freezing temperature and ice-formation temperature scale. This changes only unresolved spatial support; native concentration and latent ice volume remain the conserved prognostic states. The exact fixed-mask validator now integrates fractional support occupancy for extent and native concentration for area.

## AMOC recovery

A single +0.8 Sv collapse seed is reused for -0.25, -0.30, -0.35, and -0.40 Sv de-hosing branches to year 700. The -0.40 branch is then continued with zero hosing to year 900 to test persistence. No restart threshold is added.

## Local execution

Run `run_r18_local_validation.bat`. Every integration child is capped at five model years and checkpointed. Sea-ice output is monthly and includes exact packaged NSIDC fixed-mask area/extent and 1979-2024 March/September metrics. TEOS is not rerun because R17 already completed that sensitivity.
