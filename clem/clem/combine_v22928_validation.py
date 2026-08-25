#!/usr/bin/env python3
"""Combine fail-closed v2.29.28 5-degree and 10-degree validation outputs."""

from combine_v22923_validation import combine_validation


def main() -> None:
    combine_validation(model_version="2.29.28", artifact_tag="V2_29_28")


if __name__ == "__main__":
    main()
