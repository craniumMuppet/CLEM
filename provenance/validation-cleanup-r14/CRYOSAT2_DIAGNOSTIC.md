# CLEM v2.29.28 R13 - CryoSat-2 diagnostic audit

## Verdict

The poor CryoSat-2 temporal correlation is **still present**, but the current source audit does **not** support treating it as a demonstrated thickness-physics failure. The current observation operator uses the exact per-record satellite footprint, the product's 70% concentration retrieval threshold, concentration-and-cell-area weighting, and March-only comparisons. The historical R13 mean-state gates pass. The main mismatch is that CLEM's deterministic thickness trajectory has far less interannual variability than the short satellite record.

Do **not** tune sea-ice physics against the raw CryoSat correlation. Retain the correlation as a retrospective development diagnostic and require a separately preregistered prospective protocol for predictive-skill claims.

## Dataset/operator audit

- Product: `RDEFT4` version `1`; DOI `10.5067/96JO0KIFDAS8`.
- Months used: [3].
- Minimum concentration threshold: 0.70.
- Mean: concentration-and-cell-area weighted thickness over the exact valid satellite retrieval footprint.
- Model comparison: EGCM local ice thickness is sampled at identical cell centers and averaged with the identical per-record observation weights.
- Operator: `cryosat2_rdeft4_operator.npz`; SHA-256 `d14aa0ec444ecf60c33ca7be8d2fc38a6703535f7d7d6dbd9fa3db7c0a70cd11`.
- Source records: 14; 2016 is absent from the processed series.
- Source filenames are overwhelmingly March 29-31 endpoints, consistent with a 30-day March-centered product window.

No static evidence was found for a wrong month, wrong concentration threshold, wrong footprint, or separate model/observation weighting.

## Temporal statistics reproduced from frozen R13 outputs

| Metric | 5 degree | 10 degree |
|---|---:|---:|
| Records | 14 | 14 |
| Observed mean thickness (m) | 2.1294 | 2.1294 |
| Model mean thickness (m) | 1.9715 | 1.9789 |
| Bias (m) | -0.1579 | -0.1505 |
| RMSE (m) | 0.1985 | 0.1923 |
| Raw correlation | -0.143 | -0.123 |
| Observed SD (m) | 0.1205 | 0.1205 |
| Model SD (m) | 0.0197 | 0.0188 |
| Model/observed SD | 0.164 | 0.156 |
| Observed trend (m/decade) | +0.0399 | +0.0399 |
| Observed trend p-value | 0.603 | 0.603 |
| Model trend (m/decade) | -0.0426 | -0.0406 |
| Detrended correlation | +0.089 | +0.254 |
| First-difference correlation | +0.233 | +0.530 |
| Leave-one-out raw-correlation range | -0.282 to +0.031 | -0.266 to +0.046 |

The observed trend is not statistically distinguishable from zero over this short record, while CLEM produces a smooth declining thickness trajectory. The raw negative correlation is therefore not robust evidence for the sign of a forced thickness trend.

## ICESat-2 cross-check

| Metric | 5 degree | 10 degree |
|---|---:|---:|
| Records | 7 | 7 |
| Raw correlation | +0.678 | +0.692 |
| Model/observed SD | 0.192 | 0.181 |
| Detrended correlation | -0.854 | -0.423 |

ICESat-2 also has much larger interannual variance than CLEM. Its attractive raw correlation is therefore largely not evidence that CLEM reproduces observed year-to-year variability.

## Remaining observation-operator issue worth tightening

The acquisition code should make CryoSat granule selection deterministic by scientific date/window rather than relying on the middle item returned by a search result list. The frozen historical data themselves should **not** be replaced merely to change this selection rule; their exact source filenames and hashes are already provenance-bound. A future acquisition should explicitly select the preregistered 30-day window (for example, the product window centered on mid-March / ending near March 30-31).

## Candidate semantic repair

`sea_ice_validation.py` now reports:

- `temporal_correlation_is_release_blocking = false`
- `temporal_correlation_role = retrospective_development_diagnostic`

The legacy `scientific_volume_thickness_validation_complete` field remains for compatibility and is not manually flipped true.
