# Convection review follow-up — 2026-09-14

> **Superseded default SSP response:** this report records the corrected
> convection-only model before the separately sourced forced-heat capacity was
> added later on September 14. Its 3.6–4.3% SSP2-4.5 result remains preserved as
> mechanism-isolation evidence. See `AMOC_FORCED_HEAT_CLOSURE_2026_09_14.md` for
> the current equations and results.

The default direct convection multiplier from `eec6bcd` is withdrawn. The
convection scale now uses the local north/deep control hydrography. This fixes
the reviewed implementation and evidence issues; it does not establish a
realistic SSP AMOC weakening magnitude.

## Review conclusions and changes

The former denominator was a north/Southern-Ocean hydraulic contrast, even
though the numerator represents a local north-surface/deep density anomaly.
It could therefore make local convection more or less sensitive when only
the remote Southern Ocean reference salinity changed. The denominator is now

`B_local = abs(-alpha * (T_n0 - T_d0) + beta * (S_n0 - S_d0))`.

The salinities come from the solved control state. Neither hydraulic geometry
nor hydraulic EOS selects this normalization. Zero/nonfinite local contrasts
are rejected instead of silently replacing them with an enormous sensitivity.
The transient salinity anomaly is referenced to that same solved control
hydrography, including when the freshwater-budget initializer replaces raw
user-supplied salinities to close the control circulation.
The signed contrast and its magnitude are available in diagnostics. At the
default 10-degree control, `B_local` is about `1.45e-3`, compared with the trial's
`5.08e-4`. This magnitude is a normalization scale from prescribed hydrography;
it is not a measured sinking margin or a derived convective-onset criterion.
The exponential anomaly response remains an explicit reduced model assumption.

The direct transport experiment remains `q_target = q_hydraulic * C**p`, but
`p` now defaults to zero. Convection still affects conservative north/deep salt
mixing and can thereby affect the hydraulic density and transport. Nonzero
`p` changes the model closure. The previous review's assertion that overlapping
responses *prove* double counting was too strong; the supported finding is
that their additional proportional coupling was not independently justified.

There is no general identity between open-ocean convection and net AMOC
sinking. For example, Wei and Zhang (2024) obtain increased Labrador Sea
convection alongside reduced AMOC in a coupled-model hosing experiment.
That study cautions against identifying the two processes; it does not validate
CLEM's remaining closure. [Wei and Zhang, Nature Communications](https://www.nature.com/articles/s41467-024-54756-3).

The CLI, desktop GUI, and Streamlit app expose `p` as an experimental control,
including the zero branch. The desktop GUI also permits an explicitly enabled
Monte Carlo range. The unsupported built-in `0.5–1.5` science prior has been
removed, so a default ensemble cannot silently enable the multiplier.

## Evidence handling

SSP2-4.5 was inspected when alternatives were selected for `eec6bcd`. Its
15–50% development criterion is retained, but agreement with that range cannot
be treated as independent validation. The verifier records numerical checks
and the response criterion separately, saves both resolutions even when the
criterion fails, then exits with failure. Incomplete annual windows and
nonfinite values are rejected. A new integration is marked incomplete before
it starts, so an integration failure cannot retain a stale successful SSP
result. The main verifier now labels this scenario
`ssp245_development`, replacing `ssp245_out_of_sample`.

Historical results under `physics_revision_20260912/` and
`outputs_ssp245_amoc_repaired/` describe the previous equations. They are not
rewritten as results of the current model. New evidence is under
`physics_review_followup_20260914/`, with source hashes and separate experiment
directories.

## Current results

Both 1850–2100 SSP2-4.5 runs completed with the revised defaults. The broad
response criterion **fails at both resolutions**; it was not relaxed.

| Resolution | Mean 1995–2014 AMOC | Mean 2081–2100 AMOC | Decline | AMOC in 2100 | FovS in 2100 |
|---|---:|---:|---:|---:|---:|
| 10° | 16.685 Sv | 15.973 Sv | 4.27% | 16.019 Sv | −0.1513 Sv |
| 5° | 16.721 Sv | 16.116 Sv | 3.62% | 16.162 Sv | −0.1523 Sv |

These are simulated values, not observations. The maximum pre-projection salt
error is below `5.17e-10 ppm`. The earlier trial's 17–18% decline is therefore
not preserved by the reviewed changes. CLEM's weak transient AMOC response
remains an unresolved model limitation; matching the desired decline requires
an independently supported physical development, not choosing a multiplier
from this SSP comparison.

The other development experiments completed:

- The five-year control remains at 17.000 Sv with negligible thermal drift.
- Abrupt doubled CO₂ gives 16.071 Sv at 10° and 16.183 Sv at 5° after 60 years.
- Coupled 0.2 Sv freshwater hosing gives 14.059 Sv after 100 years.
- Halving the time step and increasing Arctic substeps changes the 20-year
  doubled-CO₂ endpoint by −0.00384 Sv and −0.000056 K.
- In the isolated 100-year hosing plus 900-year recovery experiment, the open
  boundary leaves 13.92% of the hosing-end basin salt deficit, versus 95.97%
  with the legacy closed boundary. Final AMOC is 16.763 and 16.618 Sv,
  respectively. These runs disable seasonal Arctic and anomalous hydrology
  and Greenland freshwater processes to isolate boundary ventilation.

All **129 focused tests passed** in 283.84 seconds, and the desktop GUI startup
smoke test and Python compilation passed. The test selection covers the prior
physics-repair modules, the new convection/evidence regressions, and the
Streamlit canonical-default check. It is not the full release suite.
The machine-readable summary and exact test inventory are in
[`review_results.json`](../physics_review_followup_20260914/review_results.json);
the SSP configurations and metrics are in
[`ssp245_results.json`](../physics_review_followup_20260914/ssp245/ssp245_results.json).

All three experiment source snapshots match the current governing modules:

- `climate_model.py`: `6cf686b11f8b6210c3e311a3ac72587809a13d788a6b044fc051bc636513a832`
- `amoc_density_r16.py`: `ce2ba84068cdb908dd612c9629ca215f75391e0f6defef52ae25871d64dda122`

## Reproduction

From the repository root:

```powershell
python tools/verify_physics_revision.py --output physics_review_followup_20260914/coupled
python tools/verify_physics_revision.py --recovery-only --output physics_review_followup_20260914/recovery
python tools/verify_physics_revision.py --ssp245-only --output physics_review_followup_20260914/ssp245
```

The SSP command deliberately returns a nonzero exit code when the unchanged
response criterion fails, after writing the measured values. This is a
scientific-model shortfall, not a claim of a numerical integration failure.

## Validation scope

Behavioral checks cover independence of local convection from remote Southern
Ocean salinity, unchanged immediate hydraulic transport when only convection
efficiency changes at the default exponent, retained conservative salt mixing,
explicit experiment activation, GUI/CLI round trips, prior activity, and failed
or incomplete SSP evidence. Tests are numerical and software checks, not an
observational validation campaign.

The previous full-suite review was interrupted before completion. It found
failures, but did not establish that all were introduced by `eec6bcd`.
The representative hybrid test also failed on parent `4cf51b2`, and the Arctic
default assertion concerned an earlier change. Those failures are not used as
proof that direct multiplication alone was invalid. The full historical
release matrix has not passed for the current equations.
