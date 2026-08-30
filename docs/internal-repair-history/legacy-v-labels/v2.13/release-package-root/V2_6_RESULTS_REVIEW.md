# v2.6 returned-results review

The uploaded v2.6 verification bundle completed all planned experiments.

## Passed and frozen

- Salt conservation: exact to reported precision.
- Forced energy closure: relative residual 0.000536 (0.0536%).
- Seasonal-Arctic timestep convergence: 0.000869 C GMST and 0.00680 Sv AMOC
  difference between dt=0.05 and dt=0.025 over the test interval.
- Control AMOC thermohaline state: +6 K north-minus-south temperature contrast,
  negative thermal density contribution, positive net density driver, ratio 1.
- 0.5 Sv hosing: AMOC collapses to ~0 Sv and the North Atlantic cold anomaly is
  -3.80 C, within the intended -3 to -8 C target.
- Thermal-only abrupt-2xCO2: AMOC weakens 34.1% without externally prescribed
  warming/Greenland freshwater pathways.
- Salt-loop topology: FovS control value remains -0.15 Sv while the Southern
  surface box is no longer inserted into the 34.5 S overturning branch.
- Hysteretic memory: zero-hosing control remains at 17 Sv while a separately
  perturbed trajectory remains on a collapsed branch after hosing is removed.
- Pycnocline closure: final imbalance 1.04e-6 Sv and depth 1034.336 m, matching
  the free zero-volume-imbalance equilibrium rather than an imposed restoring.
- Sea-ice/brine freshwater coupling is active and salt conserving.
- Greenland cap is not active in the verification trajectory; maximum applied
  Greenland freshwater is ~0.0143 Sv versus the 0.10 Sv safety ceiling.

## Remaining issue found

The v2.6 water-vapour reduction was based on a category error: the ~+1.30 AR6
number is combined WV+LR, not standalone WV. v2.6 produces standalone WV
~+1.475 and combined WV+LR ~+1.049 W m-2 K-1, which is too weak. Its 150-year
Gregory effective ECS is ~2.26 C. v2.7 corrects only this sensitivity error and
adds explicit equilibrium ECS/TCR verification.
