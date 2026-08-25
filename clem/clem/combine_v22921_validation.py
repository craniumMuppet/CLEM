#!/usr/bin/env python3
"""Compatibility entry point delegating to the v2.29.22 combiner."""
from combine_v22922_validation import *  # noqa: F401,F403
from combine_v22922_validation import main

if __name__ == "__main__":
    main()
