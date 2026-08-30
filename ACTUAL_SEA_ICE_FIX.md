# Actual sea-ice fix — v2.29.24

v2.29.24 is the completed correction of the reviewed sea-ice-fix derivative. It changes the active Arctic model, preserves conservation, and carries current validation/test evidence under the v2.29.24 identity.

## Active model changes

1. The grid-equivalent latent-energy safeguard and local unresolved-pack thickness safeguard are separate controls: 8 m equivalent storage versus a 12 m emergency local geometry bound.
2. Thick-pack resistance suppresses fixed-volume area retreat as surviving floes become thicker than the periodic-control pack, preventing retreat from mechanically concentrating conserved volume into a cap-driven remnant.
3. Warming-driven Arctic ocean heat convergence remains conservative: imported Arctic heat is removed with equal and opposite sign from the lower-latitude ocean.
4. Depleted-pack phase restoring uses a configurable 0.14 saturation scale and an independent configurable 2.5 W/m² maximum reverse-flux bound.
5. The forced-ocean convergence onset, restoring controls, thickness safeguards, and thick-pack resistance have CLI, Streamlit, desktop GUI, metadata, and Monte Carlo parity.
6. The changed physical model is versioned as 2.29.24 rather than reusing the 2.29.23 identity.

## Historical September result

| Resolution | Skill vs persistence | Skill vs expanding trend | 2021–2025 RMSE |
|---|---:|---:|---:|
| 5° | +0.1148 | +0.0884 | 0.2232 million km² |
| 10° | +0.1623 | +0.1374 | 0.2657 million km² |

March skill remains positive against both baselines at both resolutions.

The rolling evaluation is retrospective and development-informed; it is not labelled as prospective independent validation.

## Future response

September 2100 Northern Hemisphere area declines monotonically across SSP1-2.6, SSP2-4.5, SSP4-6.0 and SSP5-8.5 at both resolutions. SSP2-4.5 ends at 1.5164 million km² at 5° and 1.4127 million km² at 10°.

The local-thickness safeguard is not controlling the bulk pack: SSP2-4.5 safeguard contact is 0% at 5° and about 0.0005% at 10°. Under SSP5-8.5, safeguard contact is about 1.20% at 5° and 0% at 10°, while mean September local thickness is only about 2.85–3.06 m.

## Stability and regression verification

- Canonical non-slow suite: 323/323 passed; 52 slow tests deselected; 0 failures; 0 errors.
- 200-year unforced 5° and 10° runs: stable at numerical-roundoff scale.
- Strong implementation-level receiver mutation: restored and passing.
- 6 m grid-equivalent latent-reservoir regression: passes without clipping by the local geometry safeguard.
- Python compilation, interface parity and GUI-startup focused tests: pass.

See `V2_29_24_REVIEW_FIXES.md`, `TEST_RESULTS_V2_29_24.json`, `VALIDATION_SUMMARY_V2_29_24.json`, and `validation/v22924/` for the exact evidence.
