#!/usr/bin/env python3
"""Run the current-source v2.29.28 per-resolution coupled validation."""

from validate_v22923 import run_validation


def main() -> None:
    run_validation(
        expected_version="2.29.28",
        artifact_tag="V2_29_28",
        validator_filename="validate_v22928.py",
        combiner_filename="combine_v22928_validation.py",
    )


if __name__ == "__main__":
    main()
