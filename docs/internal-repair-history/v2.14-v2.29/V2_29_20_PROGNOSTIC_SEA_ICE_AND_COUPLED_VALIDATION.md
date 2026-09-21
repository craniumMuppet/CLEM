# EGCM v2.29.20 historical note — superseded

The v2.29.20 implementation and its original validation claims are superseded by v2.29.21.

The v2.29.20 package contained two release-blocking defects:

- normal output generation could fail because `SimulationResult` did not carry the Arctic module blend required by map reconstruction;
- the microscopic thin-ice transition returned physically relevant low-volume ice to a multi-metre compactness branch.

Old v2.29.20 validation and test-result files are intentionally not packaged as current evidence. They were generated from superseded source and must not be used to assess v2.29.21.

The current implementation, corrected mapping, process-budget tests, evidence workflow, and remaining limitations are documented in `V2_29_21_ENGINEERING_CORRECTIONS.md`. Current version-matched evidence uses the `V2_29_21` filename suffix.

Compatibility entry points named `validate_v22920.py` and `combine_v22920_validation.py` delegate to the v2.29.21 implementation. They do not recreate or certify v2.29.20 evidence.
