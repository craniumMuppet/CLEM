# CLEM physics repair candidate

This is a candidate physics repair, not a validated release. Validation is deliberately delegated to the user's local machine through `verify_physics_local.py`.

Changed defaults/structure:
- AMOC control reference temperatures now use Atlantic-only 2-D climatology rather than zonal all-ocean means.
- AMOC surface heat coupling: 0.075 -> 0.25; local damping: 1.35 -> 1.00 W m-2 K-1.
- Thermal AMOC throttles relaxed: stratification saturation 0.60 -> 4.0 K; interhemispheric coupling 0.02 -> 0.50; convection thermal coupling 0.30 -> 0.80.
- Deep-ocean effective heat capacity: 110 -> 260 W yr m-2 K-1.
- Pycnocline artificial restoring-to-700-m term removed; depth now responds to the diagnosed volume imbalance.
- Pycnocline feedback strength: 0.10 -> 0.35.
- Convection strengthening cap raised from 1.05 to 1.50.
- Greenland applied freshwater ceiling: 0.025 -> 0.10 Sv (finite reservoir bound remains active).
- Saturation humidity uses an ice Magnus branch below freezing.

Not declared solved by parameter choice alone:
- Salt-advection bistability/FovS interpretation must be judged from the returned hysteresis diagnostics.
- Sea-ice/brine/export salinity coupling still requires a defensible freshwater-routing formulation rather than an arbitrary tune. The verifier is intended to establish the new baseline before that addition.
- Feedback-component calibration (WV/LR) is intentionally not retuned before the AMOC/control-state changes are verified.
