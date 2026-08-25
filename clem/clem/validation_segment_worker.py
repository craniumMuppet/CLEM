#!/usr/bin/env python3
"""Isolated short-segment runner used by the v2.29.7 release validator.

The execution environment used for release QA throttles very long single Python
processes.  This worker advances one ordinary model segment, preserving the
actual prognostic state and cumulative conservation diagnostics between
segments.  It does not change model equations or timestep semantics.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from climate_model import ProcessClimateModel
from trusted_validation_pickle import dump_trusted_pickle, load_trusted_pickle


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    trusted_root = Path(args.input).resolve().parent
    payload = load_trusted_pickle(args.input, trusted_root)
    config = payload["config"]
    model = ProcessClimateModel(config)
    if payload.get("state") is not None:
        model.state = payload["state"].copy()
    model._maximum_pre_projection_salt_error_ppm = float(
        payload.get("maximum_pre_projection_salt_error_ppm", 0.0)
    )
    model._cumulative_absolute_salt_projection_correction_psu_m3 = float(
        payload.get("cumulative_absolute_salt_projection_correction_psu_m3", 0.0)
    )
    result = model.run()
    output = {
        "result": result,
        "state": model.state.copy(),
        "maximum_pre_projection_salt_error_ppm": float(
            model._maximum_pre_projection_salt_error_ppm
        ),
        "cumulative_absolute_salt_projection_correction_psu_m3": float(
            model._cumulative_absolute_salt_projection_correction_psu_m3
        ),
    }
    dump_trusted_pickle(args.output, output, trusted_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
