# v2.29.5 Post-Fix Review

## Findings addressed

| Finding | v2.29.5 resolution | Remaining scope limit |
|---|---|---|
| Native Arctic sea ice was overestimated | Native March and September area are retuned and release-gated independently of the statistical operator | Two zonal sectors cannot resolve drift, ridging, export or basin geography |
| Zero native ice could diagnose nonzero area/extent | Exact-zero short circuit applies to totals and display fields | Near-zero nonzero states still pass through the historical operator |
| Future closure could conceal native-state changes | Post-2020 closure removed; native area and frozen-operator area are both reported | Observation-equivalent future area is still an emulator diagnostic, not an independent forecast |
| Holdout lacked a relative-skill baseline | All four holdout metrics must beat frozen-2020 persistence | Five holdout years remain a short evaluation period |
| OISST benchmark was not reproducible | Exact files, deterministic processor, weighting and SHA-256 output are included | Sector means do not validate local/coastal SST |
| Corrected control obscured raw residual tendency | Corrected and uncorrected 500-year drift are reported separately | Reference-tendency correction remains a calibrated reduced-model closure |

## Scientific classification

- Global and hemispheric scenario sensitivity: appropriate for a
  reduced-complexity emulator.
- Native sea-ice seasonality: quantitatively gated at hemispheric scale.
- Sea-ice longitude maps: visualization only, with no regional forecast skill.
- Arctic open-water temperatures: reduced-sector diagnostics, not local or
  coastal forecasts.
- AMOC and Greenland: controlled sensitivity experiments, not precise collapse
  timing or outlet-glacier forecasts.

## Release decision

The build is releasable only after the generated v2.29.5 validation JSON,
complete regression record, and extracted-package verification all pass. This
review does not substitute for those machine-generated checks.
