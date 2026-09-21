# v2.29.5 Accuracy and Validation

## Release purpose

v2.29.5 corrects the remaining sea-ice accuracy and evidence-integrity issues
identified after v2.29.4. The native thermodynamic state, not merely its
statistical observation operator, is now release-gated. Future sea ice no
longer uses a post-2020 target closure.

## Evidence partitions

1. **Development regressions:** broad GMST, ocean-heat, Arctic amplification,
   AMOC and Greenland ranges previously used while tuning the reduced model.
2. **Independent temporal holdout:** NOAA/NSIDC March and September area and
   extent for 2021-2025, excluded from the 1979-2020 observation-operator fit.
3. **External plausibility:** broad NOAA OISST sector-mean open-water
   temperature envelopes, with reproducible source locators and processing.
4. **Structural tests:** conservation, timestep/resolution convergence,
   perturbation recovery, exact-zero behavior, interface parity, software
   safety and package integrity.

Development regressions are not independent predictive validation.

## Sea-ice integrity changes

- The 1979-2020 observation operator is frozen and linear in native
  thermodynamic area, with seasonal pack-spread terms for extent.
- No calendar-time trend, scenario-specific closure, or future target appears
  after 2020.
- A prognostic state with exactly zero ice produces exactly zero diagnosed area
  and extent and zero Northern Hemisphere display fields.
- Validation reports both observation-equivalent and raw native future area.
- The native control must remain within 12-17 million km2 in March and 3-9
  million km2 in September, with September below March.
- SSP5-8.5 must produce no more late-century and year-2100 ice than SSP2-4.5 in
  both native and observation-equivalent diagnostics.

## Holdout skill

The 2021-2025 holdout uses four independent metrics: March area, March extent,
September area, and September extent. Each must satisfy its absolute RMSE gate
and outperform a frozen-2020 persistence forecast. This prevents a broad gate
from being passed without incremental predictive skill.

## Open-water provenance

`data/validation/open_water/NOAA_OISST_ARCTIC_BENCHMARKS.json` records the exact
NOAA OISST v2 1991-2020 SST and ice-concentration climatology locations.
`tools/process_noaa_oisst_arctic_benchmarks.py` records source SHA-256 hashes and
computes cosine-latitude and open-water-fraction weighted sector means north of
66 N. These remain broad sector plausibility checks, not local SST validation.

## Control reporting

The release reports two distinct integrations:

- **Corrected control:** the ordinary model step with its continuous
  phase-dependent reference-tendency correction. This is the release stability
  trajectory.
- **Uncorrected diagnostic:** the same initial state integrated through the
  uncorrected ordinary equations. Its drift exposes the residual tendency being
  corrected and is not presented as the stable release control.

The former zero-forcing reference-manifold bypass remains absent.

## Required release process

A final release requires all v2.29.5 validation tasks and release checks, the
complete isolated regression inventory, archive construction, and an
independent test/validation smoke run from the extracted archive. Numerical
results are written only by the completed release process to the synchronized
JSON and text records.
