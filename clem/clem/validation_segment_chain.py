#!/usr/bin/env python3
"""Advance exactly one persisted v2.29.7 validation segment."""
from __future__ import annotations

import argparse
import math
from dataclasses import replace
from pathlib import Path

from climate_model import ProcessClimateModel
from trusted_validation_pickle import dump_trusted_pickle, load_trusted_pickle


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    args = parser.parse_args()
    trusted_root = Path(args.checkpoint).resolve().parent
    checkpoint = load_trusted_pickle(args.checkpoint, trusted_root)
    start = float(checkpoint["next_start"])
    total = float(checkpoint["total_years"])
    if start >= total - 1.0e-12:
        return 0
    duration = min(float(checkpoint["segment_years"]), total - start)
    base = checkpoint["base_config"]
    config = replace(
        base,
        start_year=float(base.start_year + start),
        duration_years=float(duration),
        auto_initialize_from_1850=False,
    )
    model = ProcessClimateModel(config)
    state = checkpoint.get("state")
    if state is not None:
        model.state = state.copy()
    model._maximum_pre_projection_salt_error_ppm = float(
        checkpoint.get("maximum_pre_projection_salt_error_ppm", 0.0)
    )
    model._cumulative_absolute_salt_projection_correction_psu_m3 = float(
        checkpoint.get("cumulative_absolute_salt_projection_correction_psu_m3", 0.0)
    )
    result = model.run()
    output_dir = Path(checkpoint["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    index = int(checkpoint["index"])
    result_path = output_dir / f"segment_{index:04d}.pkl"
    dump_trusted_pickle(result_path, (start, result), trusted_root)

    checkpoint.update(
        {
            "next_start": start + duration,
            "index": index + 1,
            "state": model.state.copy(),
            "maximum_pre_projection_salt_error_ppm": float(
                model._maximum_pre_projection_salt_error_ppm
            ),
            "cumulative_absolute_salt_projection_correction_psu_m3": float(
                model._cumulative_absolute_salt_projection_correction_psu_m3
            ),
        }
    )
    dump_trusted_pickle(args.checkpoint, checkpoint, trusted_root)
    print(f"SEGMENT PASSED {start:g}-{start + duration:g} years", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
