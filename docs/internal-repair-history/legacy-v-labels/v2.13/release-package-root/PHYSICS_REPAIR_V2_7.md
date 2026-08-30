# CLEM physics repair v2.7

v2.7 is a sensitivity-correction and release-level verification revision on top
of the v2.6/v2.5 structural AMOC, salt-loop, energy and pycnocline repairs.

## Why v2.6 was not accepted

The v2.6 local verification suite passed every existing target, but its 150-year
abrupt-2xCO2 Gregory regression implied an effective ECS of about 2.26 C. The
cause was the v2.6 reduction of the water-vapour emission-height sensitivity
from 1.00 to 0.80 km per ln(q/q0).

That reduction was based on an incorrect comparison in the original review:
~+1.30 W m-2 K-1 is the AR6 assessed combined water-vapour + lapse-rate
feedback, not standalone water-vapour feedback. Standalone water-vapour
feedback in CMIP5/6 is about +1.77 W m-2 K-1, while AR6 assesses combined
WV+LR at +1.30 W m-2 K-1 (very likely 1.1 to 1.5; likely 1.2 to 1.4).

## Physics change

- `water_vapor_emission_height_km_per_lnq`: 0.80 -> 0.98.
- No AMOC, salt, pycnocline, deep-ocean, cloud, albedo, Greenland, sea-ice,
  transport, or energy-budget coefficients are changed.

The 0.98 value is intended to restore standalone WV to roughly +1.8 W m-2 K-1
while the model's negative lapse-rate feedback brings the combined WV+LR term
close to the assessed ~+1.3 W m-2 K-1.

## New verification

The one-command verifier now adds:

- 1200-year abrupt-2xCO2 equilibrium ECS, with final 100-year TOA convergence.
- Gregory 1-150 year forcing, feedback and effective ECS from the same run.
- Full equilibrium feedback decomposition: Planck, WV, resolved lapse rate,
  polar inversion closure, surface albedo, cloud and net feedback.
- 1% per year CO2 TCR through the exact doubling time.
- Correct AR6 checks for standalone WV versus combined WV+LR.
- Quantitative reference-residual audit. The additive finite-step correction is
  reported as W m-2, K yr-1, psu yr-1 and Sv yr-1. Zero control drift remains a
  regression property only, not independent validation.

All integrations remain split into restartable child processes advancing no
more than 5 model years. Checkpoints are saved atomically after every chunk.
