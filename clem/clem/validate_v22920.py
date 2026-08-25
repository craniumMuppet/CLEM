#!/usr/bin/env python3
"""Compatibility entry point delegating to the v2.29.22 validator."""
from validate_v22922 import *  # noqa: F401,F403
from validate_v22922 import main

if __name__ == "__main__":
    main()
