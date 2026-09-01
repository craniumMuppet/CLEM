#!/usr/bin/env python3
"""Run the current-source v2.29.29 per-resolution coupled validation."""

from validate_v22923 import run_validation


def main() -> None:
    run_validation(
        expected_version="2.29.29",
        artifact_tag="V2_29_29",
        validator_filename="validate_v22929.py",
        combiner_filename="combine_v22929_validation.py",
    )


if __name__ == "__main__":
    main()
