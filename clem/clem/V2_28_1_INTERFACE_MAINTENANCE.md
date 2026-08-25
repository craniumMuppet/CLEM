# v2.28.1 maintenance release

v2.28.1 is the maintenance release of the v2.28 fractional-Arctic model. It fixes the reported Monte Carlo startup failure and synchronizes the public interfaces, diagnostics, and validation methodology without recalibrating the climate equations.

## Fixed

- Desktop, Streamlit, command-line metadata, and Monte Carlo defaults use the validated `ModelConfig` AMOC values.
- The desktop-generated Monte Carlo command no longer constructs the invalid control density ratio `0.5794`.
- Validated public AMOC defaults are density exponent `1.50`, convection density scale `4.00`, convection recovery `160 years`, reference density driver `7.5e-4`, and minimum accepted initial density ratio `0.68`.
- Desktop uncertainty ranges and Monte Carlo science priors contain the validated defaults.
- The explicit fractional-Arctic external surface-flux anomaly is included in the reported resolved-system TOA imbalance. Separate bulk-radiative and Arctic contributions remain available.
- Timestep validation and headline historical metrics use the same 0.1-year subannual sampling grid before time-weighted annual averaging.
- Dynamically inactive pre-v2.28 Arctic controls are removed from the desktop and Monte Carlo active parameter surfaces. Hidden CLI/configuration compatibility inputs remain accepted but are explicitly documented as ignored.
- The reported Arctic SAT product is named as a filtered near-surface-air diagnostic; the historical `one_year` column remains only as a compatibility alias. The actual default memory is `0.15 years`.
- Open-water temperature maps are masked in cells with no open-water area.

## Regression coverage

The release includes direct tests for the original GUI/Monte Carlo crash, an end-to-end two-member Monte Carlo run, public-default parity, corrected TOA heat-budget closure, common timestep sampling, inactive-control removal, SAT-memory wording, and open-water map masking.

## Fresh validation

- Historical GMST: `1.104460 C`
- 1971–2018 ocean heat gain: `380.303480 ZJ`
- Annual Arctic amplification: `3.534182x`
- DJF/JJA amplification: `4.806145x / 1.718482x`
- SSP2-4.5 / SSP5-8.5 AMOC weakening: `19.021439% / 39.718622%`
- Greenland contribution by 2100: `85.770110 mm`

The 20-year abrupt-2xCO2 energy audit closes the corrected resolved-system TOA integral to approximately `0.114%`; the former bulk-radiative-only diagnostic misses approximately `0.478%`.
