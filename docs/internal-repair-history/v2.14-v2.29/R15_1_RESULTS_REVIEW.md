# CLEM v2.29.28 — R15.1 local validation review

Status: **R15.1 rejected as the production physics candidate.**

The user-run R15.1 bundle completed all 28 requested experiments. The execution protocol itself worked correctly: 674 child chunks completed, no child advanced more than 5 model years, there were no timeouts, and no child returned a non-zero status. The numerical results therefore provide usable evidence about the proposed R15.1 physics rather than merely about the runner.

## Decisive AMOC result

R15.1 changed the default hydraulic density contrast from the validated interhemispheric North-Atlantic versus Southern-high-latitude closure to North Atlantic versus South-Atlantic upper-limb water. That replacement is rejected by the local numerical evidence.

| Experiment | R13 / validated branch | R15.1 South-Atlantic-upper default |
| --- | ---: | ---: |
| SSP2-4.5 AMOC response, 10° | 41.87% decline | 17.505 Sv at 2100 (about 3% stronger than 17 Sv control) |
| SSP2-4.5 AMOC response, 5° | 38.60% decline | 17.532 Sv at 2100 (about 3% stronger) |
| 0.1 Sv hosing, year 100 | 13.78 Sv | 16.026 Sv |
| 0.2 Sv hosing, year 100 | 9.51 Sv | 14.961 Sv |
| 0.3 Sv hosing, year 100 | 4.13 Sv | 13.794 Sv |

The R15.1 South-Atlantic-upper control density driver is about 0.001846, compared with 0.000434 in the validated interhemispheric geometry. Under SSP2-4.5, the South-Atlantic-upper temperature contrast evolves in a direction that slightly *increases* that already-large hydraulic driver. Freshwater perturbations therefore become far too weak relative to the control density scale. The 0.4 Sv / 200-year hosing stage in the R15.1 recovery experiment never produced a collapsed branch (minimum AMOC about 13.51 Sv).

Conclusion: **South-Atlantic-upper water is retained only as a structural sensitivity geometry in R16. It is not the default hydraulic source-water closure.** The 34.5°S FovS diagnostic and the reduced interhemispheric hydraulic density contrast represent different diagnostics and do not need to use the same southern water box.

## R15.1 fixes that survived numerical testing

- **Variable-volume Greenland freshwater routing:** behaves as intended. The default step-2x run accumulated about 4.03e13 m3 of added ocean freshwater over 150 years; the legacy-compensated branch accumulated zero. The salt inventory remained conserved to essentially machine precision.
- **Greenland elevation feedback:** active but modest over this test, increasing cumulative loss from about 39,738 Gt to 40,293 Gt (roughly 1.4%).
- **Timestep convergence:** strong. At 40 years of step-2x forcing, AMOC was 17.2587 / 17.2670 / 17.2823 Sv for dt=0.025 / 0.05 / 0.10 years, with global warming 2.0370 / 2.0352 / 2.0319 C.
- **Salt conservation:** maximum reported errors were at numerical-roundoff scale; no evidence of the old implicit salt-restoration problem appeared.
- **Arctic mechanism ablations:** the extra lapse-rate feedback has the largest isolated effect in the 100-year step-2x tests (about +0.87 C Arctic and +0.10 C global relative to its ablation). Forced ocean heat convergence and phase restoring have smaller, interacting effects. R15.1 does not provide evidence sufficient to remove any of these terms by default; they remain explicit sensitivity switches.

## Validation-design defects found by the R15.1 run

1. The TEOS-10 branch was tested only in a control run. Because the hydraulic target is normalized to its control density driver, a control-only TEOS comparison cannot reveal its forced response. R16 adds forced TEOS-10 hosing and SSP2-4.5 experiments.
2. The 24 Sv upper-saturation experiment used positive freshwater hosing, which only weakens AMOC and therefore never exercised the upper saturation branch. R16 tests saturation under a strengthening (negative freshwater) perturbation.
3. The reversal-enabled 0.3 Sv experiment never approached zero AMOC and was identical to the no-reversal case. R16 deliberately tests reversal under stronger freshening and pairs it with a no-reversal control.
4. The 0.4 Sv recovery forcing did not reach the collapsed branch with the rejected R15.1 geometry. R16 returns to the validated interhemispheric geometry and uses a stronger collapse/recovery challenge.

## R16 disposition

R16 keeps the successful Greenland mass-routing, conservation, diagnostic switches, dead-control cleanup, and prospective-validation work. It restores the validated interhemispheric AMOC hydraulic default, retains the South-Atlantic-upper geometry as a named structural sensitivity, expands the forced EOS/structural test matrix, and replaces the coarse binary sea-ice extent threshold with a conservative unfitted meridional subgrid threshold diagnostic.
