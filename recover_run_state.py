#!/usr/bin/env python3
"""Explicitly recover a long-run state file from its backup or checkpoints."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from run_state import recover_run_state


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Recover long_run_state.json from its durable backup or checkpoint metadata."
    )
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    state = recover_run_state(args.output_dir.resolve())
    print(json.dumps(state, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
