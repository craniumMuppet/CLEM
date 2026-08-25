# v2.29.13 — Lock recovery and Monte Carlo AMOC baseline integrity

v2.29.13 fixes the three defects found by the independent v2.29.12 review and corrects the unexpectedly low default Monte Carlo AMOC starting distribution. The deterministic physical model calibration is unchanged: `ModelConfig.amoc_reference_sv` remains 17.0 Sv.

## Stale-lock reclamation

v2.29.12 used an exclusive owner file, but two processes could both decide that the same owner was stale. One process could delete a newly created lock after the other process had reclaimed the stale path.

v2.29.13 serializes the complete owner-file create/check/reclaim transaction with a short-lived operating-system advisory gate:

- POSIX systems use `fcntl.flock`.
- Windows uses `msvcrt.locking`.
- The gate is released automatically if a process exits.
- The durable JSON owner record remains the long-lived run lock and retains PID, host, process-start marker, token, purpose, and output-directory metadata.
- Lock release also passes through the gate and deletes the owner file only when its token matches.

This preserves stale-owner recovery while preventing simultaneous reclaimers from entering the same output folder.

## Recovery-source compatibility

A syntactically valid backup is no longer accepted merely because it parses. When checkpoint metadata is also available, immutable run identity fields are compared:

- format and state version;
- run kind and model version;
- run fingerprint and resolved seed;
- checkpoint directory and total work units;
- work-unit name and complete settings snapshot.

A backup that describes a different run is recorded as a failed recovery source, and recovery falls through to the compatible checkpoint template.

## Failed-checkpoint reconstruction

Recovery now classifies every readable compatible terminal checkpoint as either successful or failed. Reconstructed progress therefore distinguishes:

- attempted work;
- successful work;
- failed work;
- validated successful checkpoints;
- pending work.

A failed checkpoint is no longer silently converted back into pending work.

## Monte Carlo AMOC starting-strength investigation

The supplied v2.29.11 run configured `amoc_reference_sv = 17.0`, but its built-in science-prior profile sampled that same control-state anchor from a uniform 5.0–19.5 Sv distribution. The saved 1850 AMOC results were therefore:

- unweighted mean: 13.515 Sv;
- weighted mean: 13.574 Sv;
- unweighted median: 13.967 Sv;
- reported unweighted percentile median: 14.050 Sv;
- reported weighted percentile median: 14.024 Sv;
- unweighted 5–95% interval: approximately 6.73–18.96 Sv.

That legacy run also retained only 483 of 1,024 requested members (47.2% survival; 52.8% failed), with 368 members retaining positive safety-filter weight. It would be rejected by the v2.29.12+ ensemble-quality gates and should not be treated as a valid quantitative uncertainty ensemble.

The low start was not caused by the AMOC integration equations or plotting. The model initializes each member at its sampled `amoc_reference_sv`; the prior was moving the initial-condition anchor away from the configured 17 Sv default.

### v2.29.13 behavior

Built-in science-prior ensembles now keep `amoc_reference_sv` fixed at the configured base value. With the default configuration, all accepted members therefore start at 17.0 Sv before scenario evolution. The setting remains an explicit Monte Carlo parameter: users can still sample it deliberately with `--mc-range amoc_reference_sv MIN MAX` when built-in science priors are disabled.

This is a prior-definition correction, not a physical retuning. All other AMOC process parameters remain uncertainty-sampled as before.

## Retained limitations

The March native sea-ice temporal response remains scientifically inadequate and non-predictive. v2.29.13 does not alter or conceal that limitation.
