"""Deterministic segmented execution for long release-validation trajectories."""
from __future__ import annotations

from dataclasses import fields, replace
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any

import numpy as np
import pandas as pd

from climate_model import ModelConfig, ModelState, SimulationResult
from trusted_validation_pickle import dump_trusted_pickle, load_trusted_pickle

ROOT = Path(__file__).resolve().parent
WORKER = ROOT / "validation_segment_worker.py"

_HISTORY_FIELDS = (
    "land_anomaly_history_c",
    "ocean_anomaly_history_c",
    "deep_anomaly_history_c",
    "atlantic_ocean_anomaly_history_c",
    "non_atlantic_ocean_anomaly_history_c",
    "atlantic_deep_anomaly_history_c",
    "non_atlantic_deep_anomaly_history_c",
    "arctic_atlantic_air_anomaly_history_c",
    "arctic_non_atlantic_air_anomaly_history_c",
    "arctic_atlantic_air_low_pass_history_c",
    "arctic_non_atlantic_air_low_pass_history_c",
    "arctic_reference_air_temperature_history_c",
    "arctic_reference_atlantic_air_temperature_history_c",
    "arctic_reference_non_atlantic_air_temperature_history_c",
    "arctic_atlantic_interface_temperature_history_c",
    "arctic_non_atlantic_interface_temperature_history_c",
    "arctic_reference_interface_temperature_history_c",
    "arctic_reference_atlantic_interface_temperature_history_c",
    "arctic_reference_non_atlantic_interface_temperature_history_c",
    "arctic_atlantic_open_water_temperature_history_c",
    "arctic_non_atlantic_open_water_temperature_history_c",
    "arctic_atlantic_local_ice_thickness_history_m",
    "arctic_non_atlantic_local_ice_thickness_history_m",
    "sea_ice_history",
    "atlantic_sea_ice_history",
    "non_atlantic_sea_ice_history",
    "snow_history",
    "cloud_history",
    "amoc_history_sv",
)
_MAXIMUM_FIELDS = (
    "maximum_arctic_open_water_temperature_c",
    "maximum_arctic_open_water_temperature_c_at_1pct_open",
    "maximum_arctic_open_water_temperature_c_at_5pct_open",
    "maximum_arctic_open_water_temperature_c_at_10pct_open",
    "maximum_dormant_arctic_open_water_heat_wyr_m2",
)


def _combine_results(
    results: list[tuple[float, SimulationResult]],
    base_config: ModelConfig,
) -> SimulationResult:
    if not results:
        raise ValueError("At least one segment result is required")
    first = results[0][1]
    frames: list[pd.DataFrame] = []
    histories: dict[str, list[np.ndarray]] = {name: [] for name in _HISTORY_FIELDS}
    for segment_index, (offset, result) in enumerate(results):
        frame = result.dataframe.copy()
        frame["elapsed_years"] = frame["elapsed_years"].to_numpy(dtype=float) + offset
        drop = 0 if segment_index == 0 else 1
        frames.append(frame.iloc[drop:].copy())
        for name in _HISTORY_FIELDS:
            histories[name].append(np.asarray(getattr(result, name))[drop:])
    updates: dict[str, Any] = {
        "config": base_config,
        "dataframe": pd.concat(frames, ignore_index=True),
        "diagnostics": None,
        "amoc_hysteresis": None,
    }
    for name, arrays in histories.items():
        updates[name] = np.concatenate(arrays, axis=0)
    for name in _MAXIMUM_FIELDS:
        updates[name] = max(float(getattr(result, name)) for _, result in results)
    return replace(first, **updates)


def run_segmented(
    config: ModelConfig,
    *,
    segment_years: float = 40.0,
    initial_state: ModelState | None = None,
    timeout_seconds: float = 600.0,
) -> SimulationResult:
    """Run one trajectory in short isolated processes and concatenate records.

    Segment boundaries are integral years so the periodic Arctic control phase
    and all calendar-year scenario forcing remain exactly aligned. The model
    state and cumulative salt diagnostics are passed without approximation.
    On POSIX, a shell-level chain avoids nested-interpreter throttling in the
    release-QA container. Windows and other platforms use the direct worker.
    """
    import math
    import os

    total = float(config.duration_years)
    if total <= 0.0:
        raise ValueError("duration_years must be positive")
    segment_years = max(1.0, float(segment_years))
    with tempfile.TemporaryDirectory(prefix="v2294_segments_") as directory_text:
        directory = Path(directory_text)
        segment_results: list[tuple[float, SimulationResult]] = []
        use_shell_chain = os.name == "posix" and (ROOT / "validation_segment_chain.py").exists()
        if use_shell_chain:
            checkpoint_path = directory / "checkpoint.pkl"
            output_dir = directory / "results"
            dump_trusted_pickle(
                checkpoint_path,
                {
                    "base_config": config,
                    "total_years": total,
                    "segment_years": segment_years,
                    "next_start": 0.0,
                    "index": 0,
                    "state": initial_state.copy() if initial_state is not None else None,
                    "maximum_pre_projection_salt_error_ppm": 0.0,
                    "cumulative_absolute_salt_projection_correction_psu_m3": 0.0,
                    "output_dir": str(output_dir),
                },
                directory,
            )
            count = int(math.ceil(total / segment_years))
            command = "set -e; " + " ".join(
                [
                    "for i in $(seq 1 %d); do" % count,
                    "\"%s\" -u \"%s\" --checkpoint \"%s\";" % (
                        sys.executable,
                        ROOT / "validation_segment_chain.py",
                        checkpoint_path,
                    ),
                    "done",
                ]
            )
            completed = subprocess.run(
                ["bash", "-lc", command],
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=max(timeout_seconds, timeout_seconds * count),
                check=False,
            )
            if completed.returncode != 0:
                raise RuntimeError(
                    "Segmented validation shell chain failed with exit code "
                    f"{completed.returncode}:\n{completed.stdout[-8000:]}"
                )
            print(completed.stdout, end="", flush=True)
            for path in sorted(output_dir.glob("segment_*.pkl")):
                segment_results.append(load_trusted_pickle(path, directory))
            if len(segment_results) != count:
                raise RuntimeError(
                    f"Segmented validation produced {len(segment_results)} of {count} results"
                )
        else:
            state = initial_state.copy() if initial_state is not None else None
            maximum_salt = 0.0
            cumulative_salt = 0.0
            start_year = 0.0
            index = 0
            while start_year < total - 1.0e-12:
                duration = min(segment_years, total - start_year)
                segment_config = replace(
                    config,
                    start_year=float(config.start_year + start_year),
                    duration_years=float(duration),
                    auto_initialize_from_1850=False,
                )
                input_path = directory / f"segment_{index:04d}_input.pkl"
                output_path = directory / f"segment_{index:04d}_output.pkl"
                dump_trusted_pickle(
                    input_path,
                    {
                        "config": segment_config,
                        "state": state,
                        "maximum_pre_projection_salt_error_ppm": maximum_salt,
                        "cumulative_absolute_salt_projection_correction_psu_m3": cumulative_salt,
                    },
                    directory,
                )
                completed = subprocess.run(
                    [sys.executable, "-u", str(WORKER), "--input", str(input_path), "--output", str(output_path)],
                    cwd=ROOT,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=timeout_seconds,
                    check=False,
                )
                if completed.returncode != 0 or not output_path.exists():
                    raise RuntimeError(
                        f"Validation segment {index} ({start_year:g}-{start_year + duration:g} y) failed "
                        f"with exit code {completed.returncode}:\n{completed.stdout[-4000:]}"
                    )
                output = load_trusted_pickle(output_path, directory)
                result = output["result"]
                segment_results.append((start_year, result))
                print(f"SEGMENT PASSED {start_year:g}-{start_year + duration:g} years", flush=True)
                state = output["state"].copy()
                maximum_salt = float(output["maximum_pre_projection_salt_error_ppm"])
                cumulative_salt = float(output["cumulative_absolute_salt_projection_correction_psu_m3"])
                start_year += duration
                index += 1
    return _combine_results(segment_results, config)
