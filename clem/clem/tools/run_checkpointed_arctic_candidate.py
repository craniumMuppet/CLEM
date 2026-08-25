#!/usr/bin/env python3
"""Checkpointed exact Arctic candidate runner for long validation trajectories.

The runner advances one ordinary ``ProcessClimateModel`` instance in short,
restartable chunks.  The complete model object is serialized, so continuation
uses the same configuration, reference cycle, state, forcing clock, and
cumulative diagnostics as an uninterrupted integration.

Only March- and September-like records (calendar phases 0.2 and 0.7, matching
the canonical 0.1-year release sampling nearest the observational months) are
retained for Arctic observation-operator scoring.  This keeps checkpoints
small without changing the model integration itself.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import json
import os
from pathlib import Path
import pickle
import sys
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from climate_model import ModelConfig, ProcessClimateModel, SimulationResult
from sea_ice_validation import evaluate_result


RECORD_PHASES = (0.2, 0.7)
FIRST_RECORD_YEAR = 1979
LAST_RECORD_YEAR = 2026


class SparseArcticResult:
    """Minimal result interface required by ``sea_ice_validation``."""

    _resolved_index = SimulationResult._resolved_index
    _sea_ice_observation_at_index = SimulationResult._sea_ice_observation_at_index
    sea_ice_concentration_map_at_index = SimulationResult.sea_ice_concentration_map_at_index
    arctic_local_ice_thickness_map_at_index = SimulationResult.arctic_local_ice_thickness_map_at_index
    northern_sea_ice_area_extent_at_index = SimulationResult.northern_sea_ice_area_extent_at_index
    northern_sea_ice_volume_thickness_at_index = SimulationResult.northern_sea_ice_volume_thickness_at_index

    def __init__(self, payload: dict[str, Any]):
        model: ProcessClimateModel = payload["model"]
        self.config = model.config
        self.grid = model.grid
        self.dataframe = pd.DataFrame.from_records(payload["records"])
        self.atlantic_sea_ice_history = np.asarray(payload["atlantic_ice_history"])
        self.non_atlantic_sea_ice_history = np.asarray(payload["non_atlantic_ice_history"])
        self.arctic_atlantic_local_ice_thickness_history_m = np.asarray(
            payload["atlantic_local_thickness_history"]
        )
        self.arctic_non_atlantic_local_ice_thickness_history_m = np.asarray(
            payload["non_atlantic_local_thickness_history"]
        )


def _atomic_pickle(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("wb") as handle:
        pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(path)


def _load_checkpoint(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        payload = pickle.load(handle)
    if payload.get("format") != "egcm_checkpointed_arctic_candidate_v1":
        raise ValueError(f"Unsupported checkpoint format in {path}")
    return payload


def _candidate_config(
    overrides: dict[str, Any],
    *,
    resolution_deg: float = 10.0,
    duration_years: float = 177.0,
) -> ModelConfig:
    unknown = sorted(set(overrides) - set(ModelConfig.__dataclass_fields__))
    if unknown:
        raise ValueError(f"Unknown ModelConfig override(s): {unknown}")
    return replace(
        ModelConfig(),
        start_year=1850.0,
        duration_years=float(duration_years),
        scenario="ssp245",
        resolution_deg=float(resolution_deg),
        dt_years=0.05,
        record_every_years=0.1,
        auto_initialize_from_1850=False,
        **overrides,
    )


def _local_thickness(model: ProcessClimateModel, elapsed: float) -> tuple[np.ndarray, np.ndarray]:
    reference = model._arctic_reference_state(elapsed)
    atlantic_ice_energy = (
        reference["atlantic_ice_energy_wyr_m2"]
        + model.state.arctic_atlantic_ice_energy_anomaly_wyr_m2
    )
    non_atlantic_ice_energy = (
        reference["non_atlantic_ice_energy_wyr_m2"]
        + model.state.arctic_non_atlantic_ice_energy_anomaly_wyr_m2
    )
    _, _, atlantic_local = model._arctic_state_from_energy_and_concentration(
        atlantic_ice_energy,
        reference["atlantic_ice_fraction"]
        + model.state.arctic_atlantic_ice_concentration_anomaly,
    )
    _, _, non_atlantic_local = model._arctic_state_from_energy_and_concentration(
        non_atlantic_ice_energy,
        reference["non_atlantic_ice_fraction"]
        + model.state.arctic_non_atlantic_ice_concentration_anomaly,
    )
    return atlantic_local, non_atlantic_local


def _record_target_elapsed() -> list[float]:
    targets: list[float] = []
    for year in range(FIRST_RECORD_YEAR, LAST_RECORD_YEAR + 1):
        for phase in RECORD_PHASES:
            elapsed = float(year) + phase - 1850.0
            if 0.0 <= elapsed <= 177.0 + 1.0e-12:
                targets.append(elapsed)
    return sorted(targets)


TARGETS = _record_target_elapsed()


def _capture(payload: dict[str, Any], elapsed: float) -> None:
    model: ProcessClimateModel = payload["model"]
    record = model.record(elapsed)
    atlantic_local, non_atlantic_local = _local_thickness(model, elapsed)
    payload["records"].append(record)
    payload["atlantic_ice_history"].append(model.state.atlantic_sea_ice_fraction.copy())
    payload["non_atlantic_ice_history"].append(model.state.non_atlantic_sea_ice_fraction.copy())
    payload["atlantic_local_thickness_history"].append(atlantic_local.copy())
    payload["non_atlantic_local_thickness_history"].append(non_atlantic_local.copy())


def _next_target_after(elapsed: float) -> float | None:
    for target in TARGETS:
        if target > elapsed + 1.0e-10:
            return target
    return None


def cmd_init(args: argparse.Namespace) -> int:
    overrides = json.loads(args.overrides)
    if not isinstance(overrides, dict):
        raise ValueError("--overrides must decode to a JSON object")
    config = _candidate_config(
        overrides,
        resolution_deg=args.resolution,
        duration_years=args.duration_years,
    )
    model = ProcessClimateModel(config)
    payload: dict[str, Any] = {
        "format": "egcm_checkpointed_arctic_candidate_v1",
        "candidate_id": args.candidate_id,
        "overrides": overrides,
        "elapsed_years": 0.0,
        "model": model,
        "records": [],
        "atlantic_ice_history": [],
        "non_atlantic_ice_history": [],
        "atlantic_local_thickness_history": [],
        "non_atlantic_local_thickness_history": [],
    }
    _atomic_pickle(args.checkpoint, payload)
    print(
        json.dumps(
            {
                "status": "initialized",
                "candidate_id": args.candidate_id,
                "calendar_year": 1850.0,
                "checkpoint": str(args.checkpoint),
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


def cmd_advance(args: argparse.Namespace) -> int:
    payload = _load_checkpoint(args.checkpoint)
    model: ProcessClimateModel = payload["model"]
    elapsed = float(payload["elapsed_years"])
    target_elapsed = min(float(args.to_year) - 1850.0, float(model.config.duration_years))
    if target_elapsed < elapsed - 1.0e-10:
        raise ValueError("--to-year precedes the existing checkpoint")
    tolerance = 1.0e-10
    next_capture = _next_target_after(elapsed)
    while elapsed < target_elapsed - tolerance:
        dt = min(float(model.config.dt_years), target_elapsed - elapsed)
        if next_capture is not None and next_capture > elapsed + tolerance:
            dt = min(dt, next_capture - elapsed)
        model.step(elapsed, dt_years=dt)
        elapsed = min(target_elapsed, elapsed + dt)
        if next_capture is not None and abs(elapsed - next_capture) <= 5.0e-9:
            _capture(payload, elapsed)
            next_capture = _next_target_after(elapsed)
    payload["elapsed_years"] = elapsed
    payload["model"] = model
    _atomic_pickle(args.checkpoint, payload)
    print(
        json.dumps(
            {
                "status": "advanced",
                "candidate_id": payload["candidate_id"],
                "calendar_year": 1850.0 + elapsed,
                "records": len(payload["records"]),
                "checkpoint": str(args.checkpoint),
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


def cmd_evaluate(args: argparse.Namespace) -> int:
    payload = _load_checkpoint(args.checkpoint)
    calendar_year = 1850.0 + float(payload["elapsed_years"])
    if calendar_year < float(args.require_through_year) - 1.0e-9:
        raise ValueError(
            f"Checkpoint only reaches {calendar_year:.2f}; "
            f"evaluation requires {args.require_through_year:.2f}"
        )
    result = SparseArcticResult(payload)
    evaluation = evaluate_result(result)
    output = evaluation if args.evaluation_only else {
        "candidate_id": payload["candidate_id"],
        "overrides": payload["overrides"],
        "trajectory_through_calendar_year": calendar_year,
        "record_count": len(payload["records"]),
        "evaluation": evaluation,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    compact = {
        "candidate_id": payload["candidate_id"],
        "calibration_passed": evaluation.get("calibration_passed"),
        "development_passed": evaluation.get("validation_informed_development_evaluation_passed"),
        "physical_passed": evaluation.get("physical_volume_thickness_validation", {}).get("passed"),
        "osi_march_rmse": evaluation.get("osi_saf_development_crosscheck", {}).get("months", {}).get("3", {}).get("rmse_million_km2"),
        "osi_september_rmse": evaluation.get("osi_saf_development_crosscheck", {}).get("months", {}).get("9", {}).get("rmse_million_km2"),
        "piomas_nrmse": evaluation.get("physical_volume_thickness_validation", {}).get("metrics", {}).get("piomas_v2_1", {}).get("normalized_rmse"),
    }
    print(json.dumps(compact, sort_keys=True), flush=True)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.add_argument("--checkpoint", required=True, type=Path)
    init.add_argument("--candidate-id", required=True)
    init.add_argument("--overrides", default="{}")
    init.add_argument("--resolution", type=float, default=10.0)
    init.add_argument("--duration-years", type=float, default=177.0)
    init.set_defaults(func=cmd_init)

    advance = sub.add_parser("advance")
    advance.add_argument("--checkpoint", required=True, type=Path)
    advance.add_argument("--to-year", required=True, type=float)
    advance.set_defaults(func=cmd_advance)

    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--checkpoint", required=True, type=Path)
    evaluate.add_argument("--output", required=True, type=Path)
    evaluate.add_argument("--require-through-year", type=float, default=2026.0)
    evaluate.add_argument(
        "--evaluation-only",
        action="store_true",
        help="Write the canonical sea_ice_validation evaluation payload without candidate-runner wrapping.",
    )
    evaluate.set_defaults(func=cmd_evaluate)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
