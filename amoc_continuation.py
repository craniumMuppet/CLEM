#!/usr/bin/env python3
"""Branch tracking and pseudo-arclength helpers for AMOC continuation.

The climate and salt-tendency equations remain in ``climate_model.py``. This
module contains dimensionless distance, global branch assignment, predictor
construction, and adaptive-refinement topology so those operations can be
tested independently from the physical model.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.optimize import linear_sum_assignment


EQUILIBRIUM_DISTANCE_NORMALIZERS = np.array(
    [0.05, 0.05, 0.05, 0.05, 0.05, 0.25, 0.02, 5.0], dtype=float
)


def _validated_normalizers(normalizers: np.ndarray | None = None) -> np.ndarray:
    values = (
        EQUILIBRIUM_DISTANCE_NORMALIZERS
        if normalizers is None
        else np.asarray(normalizers, dtype=float)
    )
    if values.shape != EQUILIBRIUM_DISTANCE_NORMALIZERS.shape:
        raise ValueError("equilibrium normalizers must contain eight values")
    if not np.all(np.isfinite(values)) or np.any(values <= 0.0):
        raise ValueError("equilibrium normalizers must be finite and positive")
    return values


def normalized_equilibrium_distance(
    first: np.ndarray,
    second: np.ndarray,
    normalizers: np.ndarray | None = None,
) -> float:
    """Return a dimensionless distance between two equilibrium states."""
    scale = _validated_normalizers(normalizers)
    first_array = np.asarray(first, dtype=float)
    second_array = np.asarray(second, dtype=float)
    if first_array.shape != scale.shape or second_array.shape != scale.shape:
        raise ValueError("equilibrium vectors must contain eight values")
    return float(np.linalg.norm((first_array - second_array) / scale))


def secant_predictor(
    previous_level: float,
    previous_vector: np.ndarray,
    current_level: float,
    current_vector: np.ndarray,
    target_level: float,
) -> np.ndarray:
    """Predict a state at ``target_level`` from the previous branch secant."""
    previous = np.asarray(previous_vector, dtype=float)
    current = np.asarray(current_vector, dtype=float)
    denominator = float(current_level - previous_level)
    if abs(denominator) <= 1.0e-14:
        return current.copy()
    slope = (current - previous) / denominator
    return current + slope * float(target_level - current_level)


def pseudo_arclength_tangent(
    previous_vector: np.ndarray,
    previous_parameter: float,
    current_vector: np.ndarray,
    current_parameter: float,
    parameter_scale: float,
    normalizers: np.ndarray | None = None,
) -> np.ndarray:
    """Return a normalized tangent in scaled state-parameter coordinates."""
    if not np.isfinite(parameter_scale) or parameter_scale <= 0.0:
        raise ValueError("parameter_scale must be finite and positive")
    scale = np.concatenate(
        [_validated_normalizers(normalizers), np.array([parameter_scale], dtype=float)]
    )
    previous = np.concatenate(
        [np.asarray(previous_vector, dtype=float), [float(previous_parameter)]]
    )
    current = np.concatenate(
        [np.asarray(current_vector, dtype=float), [float(current_parameter)]]
    )
    tangent = (current - previous) / scale
    norm = float(np.linalg.norm(tangent))
    if norm <= 1.0e-14:
        raise ValueError("pseudo-arclength seed points are indistinguishable")
    return tangent / norm


def pseudo_arclength_predictor(
    previous_vector: np.ndarray,
    previous_parameter: float,
    current_vector: np.ndarray,
    current_parameter: float,
    step_size: float,
    parameter_scale: float,
    normalizers: np.ndarray | None = None,
) -> tuple[np.ndarray, float, np.ndarray]:
    """Predict the next point along a scaled pseudo-arclength tangent."""
    if not np.isfinite(step_size) or step_size <= 0.0:
        raise ValueError("step_size must be finite and positive")
    state_scale = _validated_normalizers(normalizers)
    full_scale = np.concatenate([state_scale, [float(parameter_scale)]])
    tangent = pseudo_arclength_tangent(
        previous_vector,
        previous_parameter,
        current_vector,
        current_parameter,
        parameter_scale,
        state_scale,
    )
    current = np.concatenate(
        [np.asarray(current_vector, dtype=float), [float(current_parameter)]]
    )
    predicted = current + float(step_size) * full_scale * tangent
    return predicted[:-1], float(predicted[-1]), tangent


def assign_branch_ids(
    roots_by_level: dict[float, list[dict[str, Any]]],
    maximum_match_distance: float = 25.0,
    normalizers: np.ndarray | None = None,
) -> None:
    """Assign persistent IDs using global matching and secant prediction.

    The Hungarian assignment makes the result independent of root-list order.
    For branches present at two previous forcing levels, matching is performed
    against a secant prediction rather than the last state alone.
    """
    if maximum_match_distance <= 0.0:
        raise ValueError("maximum_match_distance must be positive")
    scale = _validated_normalizers(normalizers)
    next_branch_id = 0
    active_previous: list[dict[str, Any]] = []
    histories: dict[str, list[tuple[float, np.ndarray]]] = {}

    for level in sorted(roots_by_level):
        current = sorted(
            roots_by_level[level], key=lambda root: float(np.asarray(root["vector"])[5])
        )
        roots_by_level[level][:] = current
        if not active_previous:
            for root in current:
                branch_id = f"B{next_branch_id:03d}"
                next_branch_id += 1
                root["branch_id"] = branch_id
                root["branch_match_distance"] = float("nan")
                root["branch_prediction_used"] = False
                histories[branch_id] = [(float(level), np.asarray(root["vector"], dtype=float).copy())]
            active_previous = current
            continue

        predicted_vectors: list[np.ndarray] = []
        prediction_flags: list[bool] = []
        for previous_root in active_previous:
            branch_id = str(previous_root["branch_id"])
            history = histories[branch_id]
            if len(history) >= 2:
                (level_0, vector_0), (level_1, vector_1) = history[-2:]
                predicted = secant_predictor(
                    level_0, vector_0, level_1, vector_1, float(level)
                )
                prediction_flags.append(True)
            else:
                predicted = np.asarray(previous_root["vector"], dtype=float)
                prediction_flags.append(False)
            predicted_vectors.append(predicted)

        if current:
            cost = np.empty((len(active_previous), len(current)), dtype=float)
            for row, predicted in enumerate(predicted_vectors):
                for column, root in enumerate(current):
                    cost[row, column] = normalized_equilibrium_distance(
                        predicted, root["vector"], scale
                    )
            row_indices, column_indices = linear_sum_assignment(cost)
        else:
            cost = np.empty((len(active_previous), 0), dtype=float)
            row_indices = np.array([], dtype=int)
            column_indices = np.array([], dtype=int)

        matched_current: set[int] = set()
        for row, column in zip(row_indices, column_indices):
            distance = float(cost[row, column])
            if distance > maximum_match_distance:
                continue
            branch_id = str(active_previous[int(row)]["branch_id"])
            root = current[int(column)]
            root["branch_id"] = branch_id
            root["branch_match_distance"] = distance
            root["branch_prediction_used"] = bool(prediction_flags[int(row)])
            histories.setdefault(branch_id, []).append(
                (float(level), np.asarray(root["vector"], dtype=float).copy())
            )
            matched_current.add(int(column))

        for column, root in enumerate(current):
            if column in matched_current:
                continue
            branch_id = f"B{next_branch_id:03d}"
            next_branch_id += 1
            root["branch_id"] = branch_id
            root["branch_match_distance"] = float("nan")
            root["branch_prediction_used"] = False
            histories[branch_id] = [
                (float(level), np.asarray(root["vector"], dtype=float).copy())
            ]
        active_previous = current


def continuation_refinement_midpoints(
    levels: list[float],
    roots_by_level: dict[float, list[dict[str, Any]]],
    minimum_step: float,
    branch_jump_sv: float,
    near_neutral_rate_per_year: float = 5.0e-4,
) -> list[float]:
    """Return interval midpoints needing finer continuation resolution."""
    midpoints: list[float] = []
    for left, right in zip(levels[:-1], levels[1:]):
        width = right - left
        if width <= minimum_step * 1.01:
            continue
        left_stable = [item for item in roots_by_level[left] if item["stable"]]
        right_stable = [item for item in roots_by_level[right] if item["stable"]]
        refine = len(left_stable) != len(right_stable) or not left_stable or not right_stable
        if left_stable and right_stable:
            minimum_jump = min(
                abs(float(a["vector"][5]) - float(b["vector"][5]))
                for a in left_stable
                for b in right_stable
            )
            refine = refine or minimum_jump >= branch_jump_sv
            near_fold = min(
                abs(float(item["maximum_real_eigenvalue_per_year"]))
                for item in left_stable + right_stable
            ) < near_neutral_rate_per_year
            refine = refine or near_fold
        if refine:
            midpoints.append(0.5 * (left + right))
    return midpoints
