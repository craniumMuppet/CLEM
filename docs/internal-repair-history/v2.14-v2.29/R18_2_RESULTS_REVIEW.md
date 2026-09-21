# CLEM v2.29.28 R18.2 sea-ice operator results review

## Execution integrity

The user-local R18.2 validation completed both requested 1850-2025 historical branches (10 degree and 5 degree). Each branch contains 3,501 records and all integration children remained within the mandatory five-model-year limit. The evaluated `climate_model.py` SHA-256 is `e1553c1baccd7a90974f7879dd664a8a4b447adec5bd93407bbc5dd0e2c9bd90`, identical to R18.1/R18.2 governing physics. No climate rerun is required.

Validated R18.2 source ZIP SHA-256: `bef91cd0ee1e3d439bca460f5df8a7c28adf949c336dd90fe7d1e57d7f08ee5a`.

R18.2 result ZIP SHA-256: `d6506dfbec839528ad3c4e633c1563cf18c1fc6caf6dd94fd44dfe5ec36e0f06`.

## NSIDC-compatible 15% cell-threshold area

| Resolution | Month | Bias (M km2) | RMSE (M km2) | Correlation | Model trend (M km2/dec) | Observed trend |
|---|---:|---:|---:|---:|---:|---:|
| 10 deg | March | +0.240 | 0.488 | 0.844 | -0.554 | -0.380 |
| 5 deg | March | +0.355 | 0.451 | 0.872 | -0.388 | -0.380 |
| 10 deg | September | -0.152 | 0.560 | 0.903 | -0.913 | -0.793 |
| 5 deg | September | -0.055 | 0.518 | 0.900 | -0.830 | -0.793 |

The large R18 apparent positive area bias was therefore primarily an observation-operator mismatch. The corrected area comparison does not justify another sea-ice physics retune.

## Extent interpretation

A literal >=15% threshold on CLEM's coarse reconstructed native-cell concentration is not a credible satellite-style extent prediction. It produces extent biases of roughly +6.8 to +10.4 M km2; the 5 degree March field saturates enough that its thresholded trend is zero and its correlation is undefined.

The separate prognostic fractional-support diagnostic remains the physically meaningful reduced-order footprint quantity. Its extent RMSE is about 0.62-0.72 M km2 with correlations around 0.89-0.90 across March/September and 5/10 degree configurations. Extent remains non-release-blocking and must not be represented as satellite-resolution validation.

## Disposition

- Keep the R18/R18.1/R18.2 governing physics unchanged.
- Keep the fractional-support extent state as a reduced-order structural diagnostic.
- Keep native >=15% cell-threshold extent explicitly resolution-limited and non-release-blocking.
- Do not rerun AMOC, TEOS, or sea-ice integrations for R18.3 release finalization.
- Independent predictive scientific validation remains `not_available` until the frozen 2027-2036 prospective evidence period is complete.
- NSIDC-0611 v4 remains an unavailable external structural diagnostic until authentic Earthdata-derived files and hashes are supplied.
