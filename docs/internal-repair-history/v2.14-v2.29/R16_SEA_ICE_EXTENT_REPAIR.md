# R16 sea-ice extent diagnostic repair

## Problem

CLEM's native Arctic state is intentionally low dimensional: latitude bands and two longitudinal sectors carry prognostic thermodynamic ice quantities. The prior extent diagnostic treated a whole native cell as either inside or outside the satellite-style 15% concentration threshold. At coarse resolution this makes extent jump by an entire native band and can produce very large extent errors even when integrated area is much closer to observations.

That is a spatial-representation problem. It must not be repaired with an empirical area-to-extent multiplier because such a multiplier would fit the answer without adding the missing spatial degree of freedom.

## R16 operator

R16 retains the native prognostic state and changes only the derived observation operator.

For each sector independently:

1. Convert latitude to `x = sin(latitude)`, so equal increments in x are proportional to spherical surface area.
2. Reconstruct a monotone piecewise-linear concentration profile inside each native cell.
3. Limit slopes with a minmod operator and physical [0,1] concentration bounds.
4. Offset the profile so its exact equal-area mean equals the native prognostic cell-mean concentration.
5. Solve the 0.15 concentration crossing analytically inside the cell.
6. Convert the above-threshold fraction to threshold occupancy and integrate it over the cell's native ocean area.

The Atlantic and non-Atlantic sectors are reconstructed independently and combined with their native ocean-fraction weights.

## Invariants

- No observed extent data enter the reconstruction.
- No fitted area-to-extent scale or multiplier is used.
- Native prognostic ice area is conserved by the subgrid reconstruction to numerical precision.
- Concentration remains within [0,1].
- Fully ice-free and fully ice-covered cells remain exactly 0 and 1 occupancy where appropriate.
- The operator may return fractional threshold occupancy, removing the artificial whole-band binary jump.

## Scientific interpretation

The repaired value is still a **diagnostic derived from the native two-sector state**. It does not create longitude-resolved sea-ice dynamics and is not claimed to be a satellite-equivalent independently prognostic extent field. Consequently, R16 keeps extent non-release-blocking and excludes it from the independent prospective predictive-release gate.
