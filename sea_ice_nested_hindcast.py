"""Strict nested temporal hindcast harness for Arctic sea-ice validation.

A fixed historical trajectory is not a hindcast. This module enforces the
required sequence for every fold:

1. build training observations using data no later than the fold cutoff;
2. call a complete calibration function for that fold;
3. verify calibration provenance did not use future observations;
4. simulate the forecast interval from the fold-specific calibrated model;
5. score only the forecast interval against declared baselines.

The release package does not invent a calibration algorithm or missing
observations. Project-specific calibration code should provide the callbacks
specified by :func:`run_nested_hindcasts`.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence


@dataclass(frozen=True)
class HindcastFold:
    calibrate_through: int
    forecast_start: int
    forecast_end: int

    def validate(self) -> None:
        if self.forecast_start != self.calibrate_through + 1:
            raise ValueError(
                "forecast_start must be exactly one year after calibrate_through"
            )
        if self.forecast_end < self.forecast_start:
            raise ValueError("forecast_end must not precede forecast_start")


DEFAULT_FOLDS: tuple[HindcastFold, ...] = (
    HindcastFold(1979, 1980, 1990),
    HindcastFold(1989, 1990, 2000),
    HindcastFold(1999, 2000, 2010),
    HindcastFold(2009, 2010, 2020),
)


@dataclass(frozen=True)
class CalibrationProvenance:
    training_data_max_year: int
    full_model_recalibrated: bool
    calibration_method: str
    calibrated_parameter_count: int
    objective_description: str
    configuration_sha256: str
    used_future_observations: bool = False

    def validate_for(self, fold: HindcastFold) -> None:
        if self.training_data_max_year > fold.calibrate_through:
            raise ValueError(
                "Calibration provenance includes observations after the fold cutoff"
            )
        if self.used_future_observations:
            raise ValueError("Calibration provenance declares future-observation use")
        if not self.full_model_recalibrated:
            raise ValueError(
                "Each fold must rerun the complete declared calibration; a fixed "
                "trajectory or post-hoc bias correction is not a nested hindcast"
            )
        if self.calibrated_parameter_count <= 0:
            raise ValueError("calibrated_parameter_count must be positive")
        if len(self.configuration_sha256) != 64:
            raise ValueError("configuration_sha256 must be a SHA-256 hex digest")


@dataclass(frozen=True)
class CalibratedFold:
    configuration: Any
    provenance: CalibrationProvenance


CalibrateFn = Callable[[HindcastFold], CalibratedFold]
SimulateFn = Callable[[HindcastFold, Any], Any]
ScoreFn = Callable[[HindcastFold, Any], Mapping[str, Any]]


def configuration_sha256(payload: Any) -> str:
    """Return a stable SHA-256 for JSON-serializable calibration output."""
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_folds(folds: Iterable[HindcastFold]) -> tuple[HindcastFold, ...]:
    values = tuple(folds)
    if not values:
        raise ValueError("At least one hindcast fold is required")
    for fold in values:
        fold.validate()
    return values


def run_nested_hindcasts(
    *,
    calibrate: CalibrateFn,
    simulate: SimulateFn,
    score: ScoreFn,
    folds: Sequence[HindcastFold] = DEFAULT_FOLDS,
) -> dict[str, Any]:
    """Run fold-specific calibration, simulation, and scoring.

    The callback boundary is deliberate: the model package has several
    calibration workflows and no scientifically justified way to fabricate the
    missing fixed-mask area or thickness/volume observations. This harness
    guarantees that whichever calibration workflow is chosen is invoked anew
    for each temporal fold and that its provenance is checked before scoring.
    """
    checked = validate_folds(folds)
    results: list[dict[str, Any]] = []
    hashes: set[str] = set()

    for fold in checked:
        calibrated = calibrate(fold)
        calibrated.provenance.validate_for(fold)
        simulation = simulate(fold, calibrated.configuration)
        metrics = dict(score(fold, simulation))
        hashes.add(calibrated.provenance.configuration_sha256)
        results.append(
            {
                "fold": asdict(fold),
                "calibration_provenance": asdict(calibrated.provenance),
                "forecast_metrics": metrics,
            }
        )

    return {
        "protocol": "nested_fold_specific_full_recalibration",
        "fixed_trajectory_reuse_allowed": False,
        "folds": results,
        "all_folds_completed": len(results) == len(checked),
        "distinct_configuration_hashes": len(hashes),
        "predictive_skill_claim_requires_baseline_scores": True,
        "minimum_baselines": [
            "persistence",
            "expanding_linear_trend",
            "temperature_driven_regression",
            "autoregressive_model",
        ],
    }


def write_hindcast_manifest(payload: Mapping[str, Any], path: str | Path) -> Path:
    """Write a deterministic JSON manifest for audit/release artifacts."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    return target
