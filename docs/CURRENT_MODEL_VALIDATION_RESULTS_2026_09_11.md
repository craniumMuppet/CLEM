# Current-model numerical validation — 2026-09-11

**September 12 follow-up:** the recovery continuation reached year 3,000 and
passes both unchanged pycnocline limits, with small residual drift. See
`RECOVERY_EXTENSION_RESULTS_2026_09_12.md`. The original run and its year-1,050
failure below remain part of the record.

All 19 planned experiments completed, covering 4,770 model years in about
72.4 minutes. There were no finalization errors. The results contain 99 explicit
`pass`/`pass_*` flags: 98 true and one false. These include overlapping checks
and development benchmarks, not 99 independent scientific validation tests.

## Execution integrity

- Model SHA-256: `bc83e8906ec37b07a47d25649456eee90a1b8e4d877f186233241c1b670db098`
- Runner SHA-256: `27457db94dc7500091c76744b6e244992bfc0a064623e0068337cbc24e95b3e5`
- Both hashes match the current source files at review time.
- Every segment reached its planned final time; manifest reports
  `all_segments_completed: true`.
- ZIP integrity check passed for `physics_verification_bundle.zip`.
- Raw results: `physics_verification_results/results.json`.
- Raw manifest: `physics_verification_results/manifest.json`.

## Principal results

| Diagnostic | Result |
|---|---:|
| ECS, global near-surface air proxy | 3.482 °C |
| Gregory effective ECS, years 1–150 | 3.641 °C |
| TCR, global near-surface air proxy | 2.088 °C |
| Bulk-surface equilibrium response, separately labelled | 3.271 °C |
| Bulk-surface transient response, separately labelled | 1.925 °C |
| Equilibrium tail TOA imbalance | 0.0401 W/m² |
| Forced energy-closure relative residual | 0.0462% |
| SSP2-4.5 AMOC decline, 10° / 5° | 18.85% / 17.13% |
| Historical 2004–2020 AMOC mean, 10° / 5° | 15.727 / 15.848 Sv |
| SSP2-4.5 bulk warming, 10° / 5° | 2.669 / 2.652 °C |
| 100-year final AMOC under 0.1 / 0.2 / 0.3 Sv hosing | 15.121 / 12.849 / 10.144 Sv |

SSP warming compares 2081–2100 with 1850–1900. AMOC decline compares 2081–2100
with 1995–2014. The runner's SSP warming comparisons retain their bulk-temperature
definition; they must not be confused with the air-temperature sensitivity
diagnostics. The hosing dose response is monotonic. Control salt conservation,
forced energy conservation, time-step comparison, cross-resolution comparison,
and the recorded climate-sensitivity range checks pass.

## Unresolved pycnocline equilibrium check

The `recovery_0p4_1050y` experiment fails `pycnocline_closure.pass_closure`:

| Quantity | Measured | Required |
|---|---:|---:|
| Mean absolute volume imbalance, years 600–1050 | 1.6325 Sv | <0.50 Sv |
| Absolute final volume imbalance | 0.2205 Sv | <0.05 Sv |

This is a test for an equilibrated pycnocline, not a direct salt-conservation
test. The trajectory is still evolving: between years 950 and 1050, AMOC
decreases from about 14.54 to 14.25 Sv while pycnocline depth increases from
about 746.5 to 755.8 m. In the last recorded year, depth increases by about
0.070 m, consistent in scale with the nonzero prognostic volume tendency.

AMOC collapses under hosing, then recovers substantially after hosing removal
at year 250. Its post-release maximum is 16.385 Sv; its final value is 14.254 Sv.
The final value lies outside the runner's 10%-of-control recovery criterion,
but that endpoint does not establish irreversible collapse, a settled weak
attractor, or an equilibrium tipping threshold. The descriptive
`persistent_weakened_or_collapsed_branch` label should be interpreted with this
unresolved equilibration explicitly attached.

The next numerical diagnosis is to extend this recovery trajectory and examine
its late-time tendencies and equilibrium branches. The existing failure should
remain recorded; neither its threshold nor the governing physics should be
changed merely to make the flag pass. This suite is complete, but an all-pass
validation claim for the corrected model is not supported.
