# EGCM v2.29.20 implementation record — superseded

v2.29.20 introduced prognostic Arctic sea-ice concentration states, but the packaged implementation and its original evidence are not current release evidence.

The implementation was superseded because normal output generation could fail and the low-volume compactness transition produced physically invalid multi-metre local thickness. Its structural checks also did not provide independent process-by-process conservation evidence.

v2.29.21 retains the prognostic concentration architecture while correcting those defects, adding independent process budgets, completing the non-slow suite, and regenerating version-matched 5° and 10° 1850–2100 evidence.

Use `V2_29_21_ENGINEERING_CORRECTIONS.md` and the files carrying the `V2_29_21` suffix for the current implementation and evidence. Old v2.29.20 result filenames are intentionally absent.
