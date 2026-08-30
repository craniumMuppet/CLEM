# v2.29.7 Accuracy and Validation

## Evidence partition

v2.29.7 distinguishes four evidence roles:

1. **Tuning-informed development regression:** global warming, ocean heat, Arctic amplification, AMOC ranges, and NSIDC records inspected during development.
2. **Validation-informed development period:** 2021–2025 NSIDC records, repeatedly inspected during v2.29.5–v2.29.7 work.
3. **Tuning-informed external sanity check:** broad NOAA OISST sector-temperature ranges inspected during v2.29.7 retuning.
4. **Prospective temporal evaluation:** 2027 onward. March 2026 is reported separately because it was already inspected and is not independent.

No record through 2026 is presented as untouched independent validation.

## Sea-ice development performance

For the selected default candidate over 1979–2020:

| Metric | Model result |
|---|---:|
| March native area mean | 13.125 million km² |
| March native-area RMSE | 0.404 million km² |
| March native-area trend | −0.187 million km² decade⁻¹ |
| September native area mean | 4.006 million km² |
| September native-area RMSE | 0.538 million km² |
| September native-area trend | −0.334 million km² decade⁻¹ |
| Fraction of observed September trend | approximately 68% |
| 2021–2025 September native-area RMSE | 0.238 million km² |

Raw rolling-origin skill relative to persistence is positive for March area, March extent, September area, and September extent. Skill relative to a rolling linear-trend baseline is positive for both area metrics but remains slightly negative for both extent metrics. The release therefore does not claim general independent forecasting skill.

## Open-water temperature evidence

The selected candidate passes all four broad development bounds:

| Reduced sector/season | Model mean |
|---|---:|
| Atlantic-influenced JJA | 3.763°C |
| Atlantic-influenced September | 1.286°C |
| Non-Atlantic JJA | 3.051°C |
| Non-Atlantic September | 0.124°C |

These ranges were inspected during tuning and are not independent validation. The processor uses the model's smooth Atlantic fraction mask. The official source files were not available in this runtime, so source-file hashes and a reproduced processed artifact are not fabricated. The package includes `tools/acquire_oisst_provenance.py` and `data/validation/open_water/OISST_SOURCE_ACQUISITION.md` for deterministic acquisition and hash generation in a networked environment.

## Release validation

`validate_v2297.py` and `tools/run_v2297_validation_parallel.py` generate the authoritative records:

- `VALIDATION_SUMMARY_V2_29_7.json`
- `DEEP_VALIDATION_V2_29_7.json`
- `IMPLEMENTATION_AUDIT_V2_29_7.json`

Release gates include native sea-ice RMSE and trends, a minimum 60% representation of the observed September trend, positive persistence skill for all four historical sea-ice metrics, OISST development-bound acceptance, cap occupancy, energy and salt accounting, control drift, timestep and resolution convergence, scenario ordering, AMOC recovery, evidence labels, interface parity, and package provenance. The reference-cycle gate compares the unforced control against the warmed historical model state rather than incorrectly forcing the preindustrial cycle into modern observational bounds.

The standard idealized hosing check retains its 80% minimum-recovery requirement. The selected 150-year convection-recovery timescale produces approximately 80.15% recovery after 100 unforced recovery years.

## Interpretation

- Global temperature and energy-balance output: reduced-complexity emulator use within the documented development ranges.
- AMOC and Greenland output: sensitivity experiments, not precise timing or regional forecasts.
- Native Arctic sea ice: materially improved climatology and temporal response, but still tuning-informed.
- Arctic open-water temperature: reduced-sector qualitative/development diagnostic only.
