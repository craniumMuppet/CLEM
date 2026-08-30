# EGCM v2.29.17 — Arctic and CO2-Sweep Integrity

## Status

- **Engineering status:** focused regression suites pass.
- **Scientific status:** the model remains a reduced-complexity emulator. March sea-ice timing and future ice-free thresholds are not independently validated and must not be presented as precise forecasts.
- **Calibration status:** raw Northern Hemisphere March area trends are no longer used as a winter-response target because pole-hole mask changes create sensor-era discontinuities. The homogeneous March-extent diagnostic is tuning-informed, not independent prediction.

## CO2 target sweep repair

The v2.29.14–v2.29.16 worker treated one failed target as a failed paired member. It stopped that member immediately, left later targets pending, and then applied the 20% member-failure gate to the whole member. A run with a small number of target-specific failures could therefore be rejected as a 50% member failure.

v2.29.17:

- continues all independent targets after an individual target failure;
- returns `status="partial"` for a member with at least one successful target;
- stores a fixed target-success mask and NaN-padded failed cells;
- evaluates baseline failures at the member level and target failures at the target-simulation level;
- computes per-target statistics only from available members;
- preserves failure rows and exact target/member accounting in summaries and checkpoints;
- normalizes earlier compatible result records that lack the new target-level counters.

## Arctic structural repair

### Thin-ice compactness

The former mapping approached a two-metre local-thickness limit as equivalent volume approached zero. v2.29.17 directly parameterizes local thickness:

- new-ice local thickness default: **0.15 m**;
- science-prior support: **0.08–0.30 m**;
- full-pack equivalent thickness default: **4.0 m**;
- transition exponent default: **1.0**.

Concentration is diagnosed as equivalent thickness divided by the local-thickness target, so concentration times local thickness remains exactly equal to equivalent thickness.

### Winter lead closure

The lead-closure coefficient is now a structural option rather than a default calibration:

- default: **0.0**;
- prior support: **0.0–0.60**;
- explicit probability mass at zero: **0.35**.

This removes the previous default compensation tuned against the inhomogeneous raw March-area slope.

### Longwave response

`arctic_interface_longwave_damping_wm2_k` is active in both ice-surface equilibrium and open-water heat loss. It is sampled by the default science prior rather than silently ignored.

### Internal cadence

The Arctic module now uses a fixed maximum internal timestep of `1 / arctic_transient_substeps_per_year`, plus at most one remainder. Common outer timesteps no longer silently change the calibrated internal cadence. The default is **80 internal steps/year**.

## Checkpoint and validation safety

- Array members in safe checkpoints use stored ZIP members, preventing valid highly compressible arrays from triggering the reader's compression-ratio defense.
- The writer reads and validates the completed temporary checkpoint before atomically replacing the previous file.
- Validation task fingerprints include the runtime provenance digest.
- Remaining pickle-based validation transports are restricted to private, current-user-owned, non-symlink work directories and require an EGCM-specific transport header. They are not accepted as general checkpoints or user data.

## Observation and evidence semantics

- March temporal robustness uses post-1988 March extent periods.
- Raw March area is explicitly excluded as a temporal calibration target.
- The 2025 AMSR2/NSIDC-0803 transition is disclosed as a prospective-product discontinuity.
- Engineering pass/fail and scientific adequacy are reported separately.

## Focused verification

The v2.29.17 suite verifies:

- highly compressible checkpoint round trips;
- thin-ice small-volume behavior and volume identity;
- active open-water longwave damping;
- fixed Arctic substep cadence;
- partial CO2-target member behavior;
- private validation-pickle restrictions;
- extent-based March trend semantics;
- retained resumable-sweep, target-baseline, prior, recovery, and winter-state behavior.
