# Forced-heat AMOC closure — 2026-09-14

## Why this change was necessary

After the local-convection normalization was corrected, CLEM's default
SSP2-4.5 response weakened by only 3.6–4.3% between 1995–2014 and 2081–2100.
Mechanism-isolation runs showed that plausible changes to hydrological
freshwater, the pycnocline feedback, and the existing thermal-density coupling
could not produce a material response. The missing response was structural:
CLEM's internally resolved North Atlantic surface heat perturbation was too
small to stand in for the greenhouse-forced heat-flux mechanism seen in
coupled ocean models.

The replacement is not numerically fitted to CLEM's SSP2-4.5 endpoint. It uses
the independent FAFMIP experiments analysed by Couldrey et al. (2022) as an
external benchmark. Their
50% North Atlantic heat-flux experiment may provide a total North Atlantic heat
input closer to 1pctCO2 near doubling after the redistribution feedback.
It produced 5.1 Sv ensemble-mean weakening in the final decade of a 70-year
experiment. Most models stabilised after the first decades. The reported
intermodel heat sensitivity was 0.25–0.66 Sv m²/W around a 0.39 Sv m²/W
ensemble mean. [Couldrey et al., Climate Dynamics](https://link.springer.com/article/10.1007/s00382-022-06386-y).
FAFMIP applies a constant regional ocean heat-flux perturbation derived from
years 61–80 of 1pctCO2 experiments. It does not define the instantaneous global
effective-forcing transfer function used below. That mapping and the scaled
uncertainty range are emulator assumptions, so the resulting SSP trajectory is
not a process-derived forecast.

## Equations

The instantaneous forced-heat sinking capacity is

```text
H*(t) = max(0, q_ref - R_heat F_A(t) / F_2x),
```

where `F_A` is total anthropogenic effective forcing plus any explicit constant
additional forcing for an SSP run using total forcing, `F_2x` is the configured
doubled-CO2 forcing, and the default `R_heat = 5.10 Sv`. Idealised and CO2-only
experiments use their selected prescribed forcing. The prognostic capacity follows

```text
dH/dt = (H* - H) / tau_heat,
```

with an exact exponential timestep and default `tau_heat = 20 years`. This
heuristic timescale makes the response nearly complete by the FAFMIP final
decade and is consistent with the reported qualitative first-decades
stabilization. The paper does not estimate a 20-year e-folding time. It is
exposed in both user interfaces and the command line.

The existing hydraulic target `q_hydraulic` still contains the TEOS-10 density,
salinity, limited pycnocline-depth, and optional convection experiment. The
active target is

```text
q_target = min(q_hydraulic, H).
```

This represents heat and hydraulic density as competing limits on northern
sinking. It avoids adding a second thermal anomaly to the hydraulic anomaly.
If freshening or salt-advection feedback makes the hydraulic branch weaker,
that branch becomes controlling. The transport still adjusts prognostically:

```text
dq/dt = (q_target - q) / tau_AMOC.
```

The output reports `amoc_hydraulic_target_sv`,
`amoc_forced_heat_capacity_sv`, and `amoc_transport_target_sv` separately.
Setting `amoc_forced_heat_response_sv_per_doubling` to zero disables the new
constraint and recovers the previous transport target, including hydraulic
strengthening above the reference transport. A zero or negative forced-heat
reduction does not impose an upper bound on that hydraulic branch.

## FovS and salt conservation

No FovS value or salinity contrast is prescribed by this change. Salinities
remain prognostic in the same six-reservoir conservative budget. FovS remains
diagnosed at the external southern boundary as

```text
FovS = -q (S_external - S_deep) / S0.
```

The new response changes FovS only through the simulated overturning and the
resulting salt transports. The control freshwater-budget initialization and
its −0.160 Sv conditional control prediction are unchanged.

## Default SSP2-4.5 result

The implementation is evaluated with continuous 1850–2100 integrations at
10° and 5° resolution.

| Resolution | AMOC 1995–2014 | AMOC 2081–2100 | Decline | AMOC in 2100 | Late FovS | FovS in 2100 |
|---|---:|---:|---:|---:|---:|---:|
| 10° | 16.083 Sv | 11.297 Sv | 29.761% | 10.952 Sv | −0.1100 Sv | −0.10732 Sv |
| 5° | 16.083 Sv | 11.297 Sv | 29.761% | 10.952 Sv | −0.1099 Sv | −0.10725 Sv |

At 2100 the forced-heat capacity is 10.710 Sv at both resolutions. The
hydraulic targets remain distinct: 16.844 Sv at 10° and 16.957 Sv at 5°.
The heat capacity is therefore the active constraint throughout 2081–2100.
The identical AMOC values across resolution are a direct consequence of a
forcing-index capacity controlling over the grid-dependent hydraulic branch;
they are not independent agreement between two spatial AMOC predictions. FovS
still differs because each grid carries its own prognostic salinities.

Both development gates pass and maximum pre-projection salt error is
`3.45e-10 ppm` at 10° and `5.17e-10 ppm` at 5°. Machine-readable results and
complete annual series are in
`physics_review_forced_heat_20260914/ssp245_results.json` and the adjacent CSVs.

The refreshed default 5° output under `outputs_ssp245/` extends the same run to
2200. Mean AMOC in 2181–2200 is 9.962 Sv, a 38.060% reduction from the
1995–2014 mean. The single 2200 endpoint is 9.934 Sv, or 41.563% below the
17 Sv control. Those percentages use different reference definitions and must
not be interchanged. FovS in 2200 is -0.10559 Sv. Exact period means, endpoint
states, salt errors, and a direct recalculation of FovS from the saved salinity
contrast are in `outputs_ssp245/amoc_fovs_review.json`.

These runs are development consistency evidence. The 15–50% range was already
inspected during earlier development and is not an independent validation
target. Passing it does not establish forecast skill. The untouched
prospective validation period remains unavailable.

## Second review corrections

A second source review found two nondefault-state defects and one evidence
wording problem. The convection salinity anomaly was measured from the raw
configured north/deep salinities even when freshwater-budget initialization
had replaced them with a solved control hydrography. It is now measured from
that solved hydrography, matching the normalization and restoring unit
convection efficiency at the initialized control state. The total-effective
SSP forcing branch also omitted the public constant `additional_forcing_wm2`
from the forced-heat index; it is now included there while natural and volcanic
forcing remain excluded.

The earlier wording treated the 5.10 Sv response, its scaled prior, and the
20-year lag as if FAFMIP directly constrained this global-forcing transfer.
FAFMIP instead applies regional surface heat-flux perturbations. The global
effective-forcing map, prior range, and lag are documented as empirical
emulator choices. These corrections do not change the default SSP2-4.5 run:
the current-source 1850–2200 annual time series remains byte-identical across
all 262 columns to the saved `outputs_ssp245/timeseries.csv`.

## Idealized response check

A 70-year abrupt doubled-CO2 run at 10° with the seasonal Arctic disabled to
isolate the annual-mean forced response gives a final-decade AMOC weakening of
4.786 Sv. The prognostic heat capacity reaches 12.054 Sv, a 4.946 Sv reduction
from the 17 Sv control, while the separately calculated hydraulic target remains 16.526
Sv. The small difference from the 5.10 Sv source mean is the expected lag of
the 20-year heat-capacity state plus the 8-year transport adjustment. No
response-amplitude correction is applied to remove that lag. Maximum
pre-projection salt error is `3.45e-10 ppm`. Because this run exercises the
same empirical response parameter, it checks implementation behavior and does
not provide independent validation.

## Verification status

The focused closure, interface, EOS, Monte Carlo, and short hosing suite passes
54 tests. The 300-year unforced 5° control and the multiscale unforced
equilibrium-Jacobian check also pass. Python compilation and the source-diff
check pass.

One older hosing-recovery regression requires at least 80% recovery of the
initial loss after 100 years and measures 79.5099%. The preserved source from
before this forced-heat closure gives the identical result, so this is not a
regression introduced here. Neither the physical parameter nor the test
threshold was changed after seeing the result. The full release suite therefore
is not claimed to pass. `physics_review_forced_heat_20260914/review_results.json`
records this distinction.

The older historical-development regression also remains outside its declared
ranges: 2011–2020 warming is 0.8368 °C against 0.95–1.20 °C, and the 1971–2018
ocean-heat-content change is 348.2 ZJ against 350–500 ZJ. The preserved
pre-closure calculation is essentially the same, so these are existing model
baseline limitations rather than effects of the new AMOC heat capacity. Those
thresholds were not relaxed.
