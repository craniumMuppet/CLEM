# v2.29.7 Post-Fix Review

## Review outcome

The v2.29.7 changes directly address every actionable finding from the independent v2.29.6 review without restoring a statistical sea-ice area correction or weakening the predeclared scientific bounds.

## Findings addressed

- Historical September native-area trend representation increases from approximately 41% to approximately 68% of observed.
- Raw annual rolling-origin persistence skill is positive for all four March/September area/extent metrics.
- All four OISST development-temperature bounds pass in the selected candidate.
- The prescribed Arctic geometry, seasonal control amplitude, lapse closure, ocean exchanges, shortwave response and AMOC hydraulic ceiling are explicit and uncertainty-sampled.
- March 2026 is reported as previously inspected evaluation evidence and is not called independent.
- Development dependency input and lock records are synchronized.
- Packaging creates a complete SHA-256 manifest covering every packaged file except the self-referential manifest itself.
- The OISST acquisition workflow is included and missing source hashes remain explicitly null rather than invented.
- The preindustrial Arctic reference-cycle gate now tests physically ordered control-to-historical ice loss and seasonal-amplitude consistency instead of comparing the control directly with modern observed means.
- The AMOC convection-recovery default is 150 years, which preserves the unchanged 80% hosing-recovery release requirement after the Arctic retuning.
- Retained compatibility tests now distinguish the preindustrial reference cycle from modern climatology and the single-year 2100 AMOC state from the release headline’s 2081–2100 mean.
- Desktop metadata aliases now cover every tuned Arctic control used by the GUI layout.

## Findings retained as limitations

- The Arctic reference atmosphere remains prescribed rather than fully coupled.
- OISST evidence is tuning-informed and not quantitative regional validation.
- Extent skill against a rolling trend baseline remains weaker than persistence skill.
- The next untouched temporal evaluation begins in 2027.
- AMOC and Greenland magnitudes remain reduced-complexity sensitivity results.

## Acceptance rule

This document does not replace automated certification. The release is acceptable only when all scientific tasks and release gates in the v2.29.7 validation records pass, the complete regression inventory passes on frozen source, and the packaged ZIP passes clean-extraction startup, focused tests, multiprocessing Monte Carlo, checksum, and full-file-manifest verification.
