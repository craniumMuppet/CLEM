#!/usr/bin/env python3
"""Manual one-segment-at-a-time QA helper for constrained execution hosts.

This does not alter equations. It exists only so release validation can be
advanced across independent tool invocations when a host throttles long-lived
process trees.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
from typing import Any

from climate_model import ModelConfig, ProcessClimateModel
from validation_segmentation import _combine_results
from trusted_validation_pickle import dump_trusted_pickle, load_trusted_pickle


def write_pickle(path: Path, value: Any, trusted_root: Path | None = None) -> None:
    root = Path(trusted_root) if trusted_root is not None else Path(path).parent
    dump_trusted_pickle(path, value, root)


def prepare(args: argparse.Namespace) -> None:
    base = replace(
        ModelConfig(),
        scenario=args.scenario,
        start_year=args.start_year,
        duration_years=args.duration,
        dt_years=args.dt,
        record_every_years=args.record_every,
        resolution_deg=args.resolution,
        auto_initialize_from_1850=False,
    )
    initial_state = None
    if args.perturbation_sign != 0.0:
        seed = ProcessClimateModel(replace(base, duration_years=1.0))
        mask = seed.arctic_module_blend
        sign = float(args.perturbation_sign)
        seed.state.arctic_atlantic_air_anomaly_c += sign * 0.5 * mask
        seed.state.arctic_non_atlantic_air_anomaly_c += sign * 0.5 * mask
        seed.state.arctic_atlantic_ice_energy_anomaly_wyr_m2 += sign * 0.25 * mask
        seed.state.arctic_non_atlantic_ice_energy_anomaly_wyr_m2 += sign * 0.25 * mask
        seed.state.arctic_atlantic_open_water_heat_anomaly_wyr_m2 += sign * 0.10 * mask
        seed.state.arctic_non_atlantic_open_water_heat_anomaly_wyr_m2 += sign * 0.10 * mask
        initial_state = seed.state.copy()
    taskdir = args.taskdir.resolve()
    taskdir.mkdir(parents=True, exist_ok=True)
    checkpoint = {
        "base_config": base,
        "total_years": float(args.duration),
        "segment_years": float(args.segment_years),
        "next_start": 0.0,
        "index": 0,
        "state": initial_state,
        "maximum_pre_projection_salt_error_ppm": 0.0,
        "cumulative_absolute_salt_projection_correction_psu_m3": 0.0,
        "output_dir": str(taskdir / "segments"),
    }
    write_pickle(taskdir / "checkpoint.pkl", checkpoint, taskdir)
    write_pickle(taskdir / "config.pkl", base, taskdir)
    print(taskdir / "checkpoint.pkl")


def combine(args: argparse.Namespace) -> None:
    taskdir = args.taskdir.resolve()
    config = load_trusted_pickle(taskdir / "config.pkl", taskdir)
    segment_results = []
    for path in sorted((taskdir / "segments").glob("segment_*.pkl")):
        segment_results.append(load_trusted_pickle(path, taskdir))
    if not segment_results:
        raise SystemExit("No persisted segment results found")
    result = _combine_results(segment_results, config)
    write_pickle(taskdir / "combined.pkl", {"config": config, "result": result}, taskdir)
    print(f"combined={len(segment_results)} records={len(result.dataframe)}")


def finalize(args: argparse.Namespace) -> None:
    import validate_v2294 as validator

    taskdir = args.taskdir.resolve()
    payload = load_trusted_pickle(taskdir / "combined.pkl", taskdir)
    config = payload["config"]
    result = payload["result"]
    kind = args.kind
    if kind == "summary_ssp245":
        validator.scenario_run = lambda *a, **k: (config, result)
        value = validator._summary_ssp245_task()
    elif kind == "summary_ssp585":
        validator.scenario_run = lambda *a, **k: (config, result)
        value = validator._summary_ssp585_task()
    elif kind == "summary_ssp126":
        validator.scenario_run = lambda *a, **k: (config, result)
        value = validator._pathway_summary_task("ssp126")
    elif kind == "summary_ssp460":
        validator.scenario_run = lambda *a, **k: (config, result)
        value = validator._pathway_summary_task("ssp460")
    elif kind.startswith("timestep_"):
        validator.scenario_run = lambda *a, **k: (config, result)
        dt = float(kind.split("_", 1)[1].replace("p", "."))
        value = validator.timestep_metrics(dt)
    elif kind == "control":
        validator.run_segmented = lambda *a, **k: result
        value = validator.control_check()
    elif kind in {"perturbation_cold", "perturbation_warm"}:
        validator.run_segmented = lambda *a, **k: result
        value = validator.perturbation_check(-1.0 if kind.endswith("cold") else 1.0)
    elif kind == "energy_audit":
        validator.run_segmented = lambda *a, **k: result
        value = validator._energy_audit_task()
    else:
        raise SystemExit(f"Unsupported finalize kind: {kind}")
    args.output.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    print(args.output)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--taskdir", type=Path, required=True)
    prep.add_argument("--scenario", default="constant")
    prep.add_argument("--start-year", type=float, default=1850.0)
    prep.add_argument("--duration", type=float, required=True)
    prep.add_argument("--dt", type=float, default=0.05)
    prep.add_argument("--record-every", type=float, default=1.0)
    prep.add_argument("--resolution", type=float, default=5.0)
    prep.add_argument("--segment-years", type=float, required=True)
    prep.add_argument("--perturbation-sign", type=float, default=0.0)
    prep.set_defaults(func=prepare)
    comb = sub.add_parser("combine")
    comb.add_argument("--taskdir", type=Path, required=True)
    comb.set_defaults(func=combine)
    fin = sub.add_parser("finalize")
    fin.add_argument("--taskdir", type=Path, required=True)
    fin.add_argument("--kind", required=True)
    fin.add_argument("--output", type=Path, required=True)
    fin.set_defaults(func=finalize)
    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
