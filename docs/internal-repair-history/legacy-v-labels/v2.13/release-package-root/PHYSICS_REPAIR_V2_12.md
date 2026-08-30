# Physics repair v2.12 - out-of-sample validation only

## Physics status

`climate_model.py` is unchanged from verified v2.11. No process coefficient, forcing amplitude, AMOC equation, sea-ice equation, pycnocline equation, salinity tendency, or radiative feedback parameter is changed in v2.12.

## New validation experiments

The new validation-only launcher runs only five independent experiments, each with the same mandatory <=5-model-year child-process boundary and atomic checkpointing used by the main verifier:

- `ssp245_1850_2100_10deg`: SSP2-4.5 from 1850 through 2100 at 10 degrees, 0.25-y records.
- `ssp245_1850_2100_5deg`: the same at 5 degrees.
- `hosing_0p1_100y`: 0.1 Sv for 100 years.
- `hosing_0p2_100y`: 0.2 Sv for 100 years.
- `hosing_0p3_100y`: 0.3 Sv for 100 years.

## Independent gates

SSP2-4.5:
- 2011-2020 warming relative to 1850-1900: broad 0.8-1.3 C historical check.
- 2081-2100 warming relative to 1850-1900: IPCC AR6 very-likely 2.1-3.5 C.
- AMOC must decline 5-50% from 1995-2014 to 2081-2100 and remain above 5 Sv; minimum trajectory AMOC must remain above 3 Sv.
- Salt conservation must remain exact to the existing tolerance.

Cross resolution:
- historical warming difference <=0.20 C;
- late-century warming difference <=0.30 C;
- late-century AMOC difference <=2.0 Sv;
- AMOC-decline difference <=10 percentage points.

Untuned hosing dose response:
- minimum AMOC weakens monotonically from 0.1 to 0.2 to 0.3 Sv;
- North Atlantic cooling increases monotonically;
- the 0.1-Sv/100-y experiment must not jump directly to the collapsed branch;
- salt conservation must pass in all three runs.

## Fast path

Run `RUN_V2_12_OUT_OF_SAMPLE_VALIDATION.cmd`. It does not rerun the already-verified v2.11 ECS, TCR, 0.5-Sv hosing, 1050-y hysteresis, or other development tests. Their exact uploaded v2.11 results and manifest are bundled and fingerprint-checked against the unchanged climate-model source.
