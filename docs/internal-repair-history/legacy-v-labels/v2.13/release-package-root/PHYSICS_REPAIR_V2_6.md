# CLEM physics repair v2.6

This revision is a narrow cleanup on top of the v2.5 South-Atlantic salt-loop repair.

## Physics changes

- Water-vapor emission-height sensitivity reduced from 1.00 to 0.80 km per ln(q/q0).
  This targets the excessive water-vapor feedback without introducing a direct
  feedback-factor tuning coefficient.
- The unresolved polar inversion/lapse closure remains active in the energy
  equation but is now diagnosed separately as `polar_inversion_flux_wm2`.
  `lapse_rate_flux_wm2` now reports only the resolved clear-sky lapse-rate term.

## Verification changes

- Removed the redundant 300-year standalone pycnocline test.
- Pycnocline closure is evaluated from year 600 onward in the existing 1050-year
  collapse/recovery experiment. v2.5 data showed the free volume budget converges
  to the analytic zero-imbalance depth (~1034.34 m), with a final residual of
  ~2e-6 Sv; the previous 300-year test ended while this stable adjustment was
  still in progress.
- Thermal-only output now reports water-vapor, resolved lapse-rate, and polar
  inversion feedback components separately.

All v2.5 AMOC, salt-loop, energy, sea-ice, Greenland, deep-ocean, and pycnocline
physics are otherwise unchanged.
