# CLEM v2.29.28 - Physics Candidate R15.1

R15 is a source-side physics/validation candidate built from the verified R14 cleanup baseline. Numerical acceptance is intentionally deferred to the bounded local verifier run by the user.

## Physics repairs

- AMOC hydraulic density geometry now defaults to one coherent source/sink pair: North Atlantic sinking water versus South Atlantic upper-limb source water. Temperature and salinity use the same water masses. The legacy Southern-surface geometry remains selectable only for structural attribution.
- A reduced TEOS-10/GSW density branch is available for the two representative AMOC water masses. The inexpensive linear alpha/beta closure remains available so the local run can quantify EOS sensitivity rather than silently assume it is negligible.
- Greenland land-ice loss is separated from compensated redistribution. Realized ice loss changes represented ocean volume and globally dilutes salinity while the zero-net virtual-flux anomaly localizes the North Atlantic plume. Physical salt mass is conserved. Artificial hosing can independently be compensated or uncompensated.
- Greenland surface-elevation feedback is included as thinning -> lowering -> local warming via a configurable lapse rate -> increased PDD melt. It can be disabled for attribution.
- Arctic forced ocean heat convergence, seasonal/phase restoring, and extra unresolved lapse-rate feedback each have independent mechanism switches for ablation tests.

## Structural uncertainty

The R15 local suite compares density exponent, pycnocline coupling, hydraulic upper saturation, reversal permission, legacy versus coherent source geometry, linear versus TEOS-10 EOS, and a collapse/recovery experiment. These are structural families, not a parameter search for a desired threshold.

## Validation architecture

The scientific-release and sea-ice evaluators now use `prospective_validation_r15.py` and the frozen protocol in `validation/prospective/CLEM_R15_PROSPECTIVE_PROTOCOL.json`. Before the complete reserved 2027-2036 evidence set exists, status is `not_available`; no Boolean can be manually flipped to manufacture a pass.

Satellite-style 15% sea-ice extent remains diagnostic/non-release-blocking because the present low-complexity spatial representation cannot claim satellite-resolution extent skill. No empirical area-to-extent multiplier was introduced.

NSIDC-0611 v4 remains an external Earthdata-authenticated acquisition. R15 does not invent the missing product or mark the six-source stack complete without its real files and hashes.

CryoSat-2 temporal correlation remains a retrospective development diagnostic. R15 does not tune thickness physics to the short record after the observation-operator audit found no obvious month/footprint/threshold error.

## Local numerical verification

Run `run_r15_local_validation.bat`. Every expensive child process advances at most 5 model years and commits an atomic checkpoint containing source/spec fingerprints and elapsed year. Re-running resumes completed work. Upload `CLEM_v2.29.28_R15_1_validation_results.zip` for numerical review.


## R15.1 validation-setup hotfix

- Fixed `ProcessClimateModel.record()` to read `freshwater_hosing_compensated` and `greenland_uncompensated_freshwater_enabled` from `self.config`.
- The previous R15 package raised `NameError: name 'cfg' is not defined` during every local-validation setup before any numerical segment ran.
- This is a diagnostic/setup-scope repair only; no governing physics equation or default parameter was changed.
- `run_r15_local_validation.bat` still requires `gsw` at startup because the full requested R15 suite includes the TEOS-10 structural experiment. The ordinary linear-EOS model does not import `gsw`.
