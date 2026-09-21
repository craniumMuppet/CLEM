# Assessment of uploaded v2.15 climate-model experiments

## v2.16 status

The explicit collapse/restart switch identified below has been removed in v2.16.0. This document remains an assessment of the uploaded v2.15 outputs. Re-running the central configurations with the continuous v2.16 closure produces a gradual SSP5-8.5 collapse around 2264, while the central carbon-pulse case weakens and recovers without collapse. See `CONTINUOUS_AMOC_V2_16_0.md` and `validation_continuous_amoc_v2_16_0/`.

## Executive assessment

The uploaded runs are numerically stable, but the SSP5-8.5 ensemble is not yet suitable for interpreting the reported 93.8% collapse fraction as a real-world probability. The main scientific issue is a response shape that is too weak and gradual through 2100, followed by a very sharp, nearly universal transition during the 22nd century. This reflects fixed AMOC tipping parameters combined with broad, unweighted climate and freshwater parameter ranges.

The hybrid experiment is internally plausible, but it switches from SSP5-8.5 to SSP2-4.5 in 2020 over ten years. It is therefore essentially an early SSP2-4.5 mitigation experiment rather than a prolonged SSP5-8.5 overshoot experiment.

## Numerical integrity

Both ensembles completed all 2,048 requested members with zero failures. Salt conservation errors are approximately 10^-9 ppm, and no numerical instability is evident in the exported summaries or time series.

## SSP5-8.5 experiment

### Temperature

- 2011-2020 ensemble median warming: 1.24 degrees C relative to 1850-1900.
- Deterministic 2011-2020 mean: 1.31 degrees C.
- 2100 ensemble median: 5.57 degrees C.
- 2100 5th-95th percentile range: 4.61-6.96 degrees C.
- 42.3% of members exceed 5.7 degrees C in 2100.

The ensemble is therefore warm-biased relative to the assessed SSP5-8.5 2081-2100 range, especially because constraint mode `none` assigns equal weight to every parameter combination.

### AMOC

- Initial AMOC: 17 Sv.
- 2100 median AMOC: 15.12 Sv, an approximately 11% decline.
- 2100 5th-95th percentile AMOC: 13.00-16.02 Sv, corresponding to approximately 24%-6% decline.
- No member collapses before 2100.
- Fraction below 2 Sv: 11.7% in 2150, 83.4% in 2200, and 93.7% in 2250.
- Median first-collapse year among collapsing members: 2170.
- Final distribution is strongly bimodal: most members are near 0.2-0.3 Sv, while a small active branch remains near 16 Sv.

The 21st-century weakening is smaller than the assessed central SSP5-8.5 AMOC decline, but the post-2100 transition is much sharper and more certain than can be justified from the sampled uncertainty. The fixed collapse threshold, restart threshold, residual convection fraction, and recovery time are the principal cause of this overconfident branch split.

### Freshwater

At 2100, total anomalous freshwater has a median of 0.0587 Sv and a 5th-95th percentile range of 0.0317-0.0965 Sv. In the deterministic member:

- Hydrological freshwater at 2100: 0.0353 Sv.
- Greenland freshwater at 2100: 0.0142 Sv, approximately 448 Gt/yr.
- Integrated Greenland discharge through 2100: approximately 0.061 m global sea-level equivalent.
- Integrated Greenland discharge through 2300: approximately 0.56 m global sea-level equivalent.
- Integrated Greenland discharge through 2400: approximately 0.87 m global sea-level equivalent.

The multi-century Greenland discharge is physically plausible for a high-emissions pathway, but the 21st-century default Greenland response is relatively low. Sampling Greenland response time is therefore important. A finite Greenland ice reservoir is still needed for multi-millennial runs because the current temperature-proportional target can continue indefinitely.

## Hybrid SSP5-8.5 to SSP2-4.5 experiment

### Scenario definition

The pathway switches in 2020 and completes its transition by 2030. The output name can be misleading because the model experiences very little future SSP5-8.5 forcing. A late-mitigation or overshoot experiment should use a switch year such as 2050, 2070, or 2100.

### Results

- 2100 median warming: 3.17 degrees C.
- 2500 median warming: 3.59 degrees C.
- 2500 median TOA imbalance: 0.051 W/m2, indicating near equilibrium.
- Median minimum AMOC: 15.93 Sv.
- Median final AMOC: 16.50 Sv.
- Four of 2,048 members collapse, or 0.20%.

These results are plausible for an early transition to SSP2-4.5. The four collapsing outliers occupy a joint high-warming/high-freshwater corner and should not be interpreted as a calibrated probability.

## Required changes

1. Sample all four freshwater controls in fast `none` mode:
   - hydrological sensitivity;
   - hydrological north-routing fraction;
   - Greenland sensitivity;
   - Greenland response time.

2. For AMOC-collapse experiments in v2.16, sample the continuous closure parameters:
   - convection critical density ratio;
   - convection transition width;
   - convective salt-exchange strength;
   - convective mixing exponent;
   - entrainment feedback;
   - convection adjustment and recovery times.

3. Do not call the equal-weight member fraction a real-world probability. Label it as the fraction of the selected parameter design that collapses.

4. Add a conditional collapse-fraction time series and branch-conditioned summaries. Standard percentile bands are misleading for a bimodal active/collapsed distribution.

5. Recalibrate the transient AMOC response so the model gives stronger gradual weakening by 2100 without forcing an almost deterministic collapse by 2250.

6. Rename hybrid outputs to include the switch year, or move the switch later when testing overshoot and delayed mitigation.

7. Add a finite Greenland ice-mass reservoir before using multi-millennial experiments.
