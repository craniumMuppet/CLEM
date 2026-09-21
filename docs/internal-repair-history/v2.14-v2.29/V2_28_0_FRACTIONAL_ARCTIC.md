# v2.28.0 Fractional Arctic Rebuild

## Purpose

v2.28 replaces the remaining equivalent-thickness and empirical transient Arctic closure with a fractional two-area thermodynamic system. It is still a reduced-complexity emulator, not a dynamic sea-ice or regional circulation model.

## Structural implementation

Each Atlantic-influenced and central-Arctic latitude band carries two conserved surface reservoirs:

1. negative latent energy stored in sea ice per unit ocean-grid area;
2. positive sensible heat stored in the simultaneously open-water fraction.

Sea-ice concentration is diagnosed from grid-equivalent thickness. Conductive heat flow uses local thickness on the ice-covered fraction. The surface balance includes orbital shortwave, snow/bare-ice/melt-pond albedo, nonsolar surface loss, ice conduction, basal ocean heat, and separate ice/air and open-water/air exchange.

The same equations generate the periodic control cycles and transient anomalies. v2.28 no longer uses the old ice-anomaly relaxation or prescribed open-water heat-release coefficient in the active solver.

## Regional structure

The model solves separate Atlantic-influenced and non-Atlantic/central-Arctic cycles. The Atlantic sector has a warmer reference atmosphere and larger basal ocean heat flux. These remain zonal reduced-complexity sectors rather than a resolved Arctic Ocean geometry.

## Stability-dependent exchange

Open-water exchange transitions smoothly between:

- **0.5 W m-2 K-1** under stable conditions, when air is warmer than water;
- **5.0 W m-2 K-1** under unstable conditions, when water is warmer than air.

The transition width is **0.5°C**. This prevents a constant large exchange coefficient from artificially transferring too much summer atmospheric heat into cold open water while retaining autumn/winter ocean heat release.

## Energy handling

Ice melt and water freezing transfer energy between the latent and sensible reservoirs. Energy outside the finite explicit surface-reservoir range is transferred to the bulk mixed-layer ocean; it is not discarded. Total resolved heat diagnostics include the open-water surface reservoir.

## Outputs

v2.28 adds explicit histories and maps for:

- Atlantic and central-Arctic open-water temperature;
- local ice thickness on the ice-covered fraction;
- sector-specific reference and actual interface temperatures;
- area-weighted Arctic interface temperature;
- stability-dependent exchange coefficient;
- effective Arctic external surface flux.

## Preserved freshwater assumptions

The public freshwater coefficients remain:

- hydrological: **0.006 Sv/K**;
- Greenland dynamic-discharge coefficient: **0.005 Sv/K**.

The Greenland surface-mass-balance branch remains separate.

## Scope limits

The model does not include sea-ice dynamics, ridging, lead geometry, mechanical export, resolved ocean gateways, or a spatial atmospheric circulation. Cloud masking, sector contrast, and unresolved atmospheric heat transport remain calibrated effective closures. Validation ranges used during development are tuning-informed and are not independent evidence of predictive accuracy.

## Frozen development-regression results

| Diagnostic | v2.28.0 |
|---|---:|
| Historical GMST, 2011–2020 vs 1850–1900 | 1.104°C |
| Ocean heat gain, 1971–2018 | 380.30 ZJ |
| Annual Arctic amplification, 1979–2021 | 3.536× |
| DJF Arctic amplification | 4.806× |
| JJA Arctic amplification | 1.718× |
| SON Arctic amplification | 3.785× |
| SSP2-4.5 AMOC weakening by 2100 | 19.02% |
| SSP5-8.5 AMOC weakening by 2100 | 39.72% |
| Greenland sea-level contribution by 2100, SSP2-4.5 | 85.77 mm |
| 500-year GMST drift | 9.0 × 10^-6°C |
| Hosing recovery after 100 years | 89.53% |

All active literature ranges pass, but they were used during development and are not independent validation.
