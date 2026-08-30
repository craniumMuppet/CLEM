# CLEM physics repair v2.8 returned-results review

Returned verification bundle reviewed on 2026-08-28.

## Passed and frozen

- Control Atlantic north-minus-south temperature contrast: +6.0 K.
- Control density ratio: 1.0.
- Salt conservation: exact to reported precision.
- Energy closure: 0.0422% relative residual.
- Seasonal-Arctic timestep convergence: 0.00150 K GMST and 0.01096 Sv AMOC between dt=0.05 and 0.025 yr.
- Pure thermal abrupt-2x AMOC weakening: 37.87% (17.0 -> 10.56 Sv), with sea-ice salinity coupling disabled.
- TCR: 1.923 C.
- Gregory 1-150 yr effective ECS: 2.851 C.
- Water-vapour feedback: +1.809 W m-2 K-1.
- WV + resolved lapse-rate + polar-inversion closure: +1.376 W m-2 K-1.
- Planck: -3.268 W m-2 K-1.
- Cloud: +0.439 W m-2 K-1.
- Surface albedo: +0.294 W m-2 K-1.
- Net feedback: -1.159 W m-2 K-1.
- 0.5 Sv / 180 yr hosing: collapse to ~0 Sv with a -3.46 C North-Atlantic cold blob.
- Pycnocline closure on the long collapsed branch: final imbalance 7.7e-7 Sv.
- Reference-residual correction: negligible (~1e-16 W m-2).
- Sea-ice export salinity amplitude normalized from raw reference 0.20894 Sv to 0.075 Sv; transient scaled export anomaly <= 0.0485 Sv.

## Remaining failures

### 1. Constant-2xCO2 millennial AMOC collapse

The 1200-yr abrupt-2x run does not reach a clean radiative equilibrium because AMOC continues to weaken and collapses by year 1200:

- y150: 9.22 Sv
- y400: 7.83 Sv
- y800: 6.09 Sv
- y1000: 3.92 Sv
- y1200: ~0 Sv

The tail TOA imbalance is -0.505 W m-2 and the tail AMOC trend is -2.34 Sv/century.

The v2.8 sea-ice export *magnitude* correction worked, but the routing remained physically reversed. Positive mechanical Arctic export was coded as freshwater leaving the North-Atlantic box and entering the South-Atlantic upper limb. Fram Strait ice export instead delivers Arctic freshwater into the Nordic/subpolar North Atlantic. Consequently, declining export under warming had the wrong sign in v2.8 and artificially freshened the North Atlantic.

v2.9 corrects the route conservatively:

- positive export: +FW to North Atlantic, -FW to external Arctic/global reservoir;
- positive storage/freezing: -FW from North Atlantic, +FW to external reservoir;
- South-Atlantic upper limb is not touched by the sea-ice export term.

### 2. Persistent collapsed cold state remains slightly too cold

The 0.4 Sv / 250 yr hosing + 800 yr recovery experiment remains on a collapsed branch, but final North-Atlantic cooling is -8.79 C, just beyond the -8 C long-state gate.

The short 180-yr hosing cold blob is -3.46 C and should be preserved. Based on the measured v2.7 -> v2.8 response to the regional AMOC heat-response damping change, v2.9 increases that damping only from 1.75 to 2.10 W m-2 K-1. This is targeted to bound the equilibrium collapsed-state cooling while retaining the transient 3-8 C hosing fingerprint.

## Additional verifier improvement

v2.9 splits sea-ice salinity coupling into independent storage/brine and mechanical-export switches and adds separate 150-year runs for:

1. pure thermal response;
2. thermal + storage/brine only;
3. thermal + export only;
4. thermal + both sea-ice pathways.

This prevents future sign errors from being hidden inside a single combined cryosphere freshwater diagnostic.
