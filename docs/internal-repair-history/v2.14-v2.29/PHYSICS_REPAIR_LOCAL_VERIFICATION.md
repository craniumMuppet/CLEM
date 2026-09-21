# CLEM physics repair — local verification candidate v2.4

This candidate is intended to be integrated and verified on the user's computer. Long climate integrations were not run while preparing the package.

## What the returned v2.3 run established

The v2.3 local suite completed all planned integrations in restartable <=5-model-year chunks. Salt conservation, seasonal-Arctic timestep convergence, and the repaired pycnocline volume closure passed. The returned numerical failures were:

- thermal-only 2xCO2 AMOC weakening: 0.56% (17.0 -> 16.90 Sv), far too weak;
- 0.5 Sv hosing minimum AMOC: 10.25 Sv, so no collapse;
- minimum North Atlantic anomaly under hosing: -1.54 C, too weak because the AMOC did not collapse;
- 0.4 Sv / 250-year hosing plus 800-year recovery never collapsed;
- reported 100-year energy closure residual: 19.0%.

The same run also showed that the numerical harness itself was functioning: the long experiments reached their planned durations, checkpoints were committed every <=5 model years, salt conservation was exact to the configured numerical tolerance, and the pycnocline tail volume imbalance was about 0.13 Sv.

## v2.4 targeted changes

### 1. AMOC forced thermal density response

The v2.3 hydraulic density driver blended two perturbation terms that both contained the North Atlantic surface-temperature anomaly: an interhemispheric north-south surface anomaly and a local northern surface-to-deep stratification anomaly. In the returned 2xCO2 run those terms partly cancelled because the Southern Ocean warmed faster; during hosing they also duplicated the stabilising North Atlantic cooling signal.

v2.4 therefore keeps the realistic +6 K Atlantic north-minus-south control temperature contrast unchanged, but uses the full anomaly in northern sinking-region surface temperature relative to the Atlantic deep reservoir for forced thermal density changes. The duplicate interhemispheric perturbation pathway is disabled by default. The perturbation term is exactly zero in the control state, so the control density driver and its normalization are unchanged.

Post-hoc application of this equation to the already-returned v2.3 states (without integrating them) changes the final thermal-only density ratio from about 0.977 to about 0.564. This is only a diagnostic of equation strength; the coupled v2.4 trajectory must be rerun locally.

### 2. Arctic external-energy diagnostic

The v2.3 `arctic_external_surface_flux_anomaly_global_wm2` diagnostic omitted the temperature-dependent longwave damping term that is present in the prognostic Arctic ice/open-water surface energy equations. The omission grows with warming and made the reported TOA integral inconsistent with the resolved heat reservoirs.

v2.4 includes the exact anomalous longwave loss in the external Arctic surface flux while continuing to exclude air/surface and ocean/surface exchanges, which are internal resolved-system transfers. A separate `arctic_external_longwave_loss_anomaly_global_wm2` diagnostic is included so the next returned bundle exposes the correction directly.

The verifier also reports separately integrated bulk radiative TOA energy, Arctic external energy, and Arctic longwave-loss anomaly in addition to the total energy-closure residual.

### 3. What was deliberately not retuned

No hosing magnitude, salinity-box volume, South Atlantic restoring coefficient, AMOC surface-heat coupling, hydraulic exponent, pycnocline closure coefficient, Greenland cap, or convection transport multiplier was changed in v2.4. This keeps the next run diagnostic: it tests whether fixing the duplicated thermal pathway is sufficient before any additional salt-feedback calibration is considered.

## Run

From `clem\clem`, run either:

`RUN_PHYSICS_VERIFICATION.cmd`

or:

`python verify_physics_local.py`

Every integration child advances at most 5 model years, checkpoints atomically, and exits. Rerunning the same command resumes source/spec-compatible checkpoints. Because v2.4 changes `climate_model.py`, use a clean extraction directory or run once with `--fresh` if overwriting an older candidate.

Upload the generated `physics_verification_bundle.zip` for evaluation.
