"""Duration-based AMOC state classification utilities.

The functions in this module treat recorded AMOC trajectories as piecewise
linear between output times. This avoids classifying a trajectory from a final
window mean that can hide recoveries, reversals, or oscillations.
"""

from __future__ import annotations

import math
from typing import Any, Sequence

import numpy as np


def condition_intervals(
    years: np.ndarray,
    values: np.ndarray,
    lower: float,
    upper: float,
    start_year: float,
    end_year: float,
) -> list[tuple[float, float]]:
    """Return merged intervals where a linearly interpolated series is in bounds."""

    x = np.asarray(years, dtype=float)
    y = np.asarray(values, dtype=float)
    finite = np.isfinite(x) & np.isfinite(y)
    x = x[finite]
    y = y[finite]
    if x.size < 2 or end_year <= start_year:
        return []
    order = np.argsort(x)
    x = x[order]
    y = y[order]
    intervals: list[tuple[float, float]] = []
    for index in range(x.size - 1):
        left = max(float(x[index]), start_year)
        right = min(float(x[index + 1]), end_year)
        if right <= left or x[index + 1] <= x[index]:
            continue
        y_left = float(np.interp(left, x[index:index + 2], y[index:index + 2]))
        y_right = float(np.interp(right, x[index:index + 2], y[index:index + 2]))
        fractions = [0.0, 1.0]
        delta = y_right - y_left
        if abs(delta) > 1.0e-15:
            for boundary in (lower, upper):
                if math.isfinite(boundary):
                    fraction = (boundary - y_left) / delta
                    if 0.0 < fraction < 1.0:
                        fractions.append(float(fraction))
        fractions = sorted(set(fractions))
        for first, second in zip(fractions[:-1], fractions[1:]):
            midpoint = 0.5 * (first + second)
            value = y_left + midpoint * delta
            if lower <= value <= upper:
                interval = (
                    left + first * (right - left),
                    left + second * (right - left),
                )
                if interval[1] > interval[0]:
                    intervals.append(interval)
    merged: list[tuple[float, float]] = []
    for left, right in intervals:
        if merged and left <= merged[-1][1] + 1.0e-9:
            merged[-1] = (merged[-1][0], max(merged[-1][1], right))
        else:
            merged.append((left, right))
    return merged


def interval_duration(intervals: Sequence[tuple[float, float]]) -> float:
    return float(sum(max(right - left, 0.0) for left, right in intervals))


def longest_interval(intervals: Sequence[tuple[float, float]]) -> float:
    return float(max((right - left for left, right in intervals), default=0.0))


def collapse_duration_diagnostics(
    values: np.ndarray,
    years: np.ndarray,
    threshold_sv: float,
    window_years: float,
    persistence_fraction: float = 0.95,
    recovery_years: float = 5.0,
) -> dict[str, Any]:
    """Classify AMOC outcomes using duration and recovery diagnostics.

    Persistent collapse requires the final state to be weak/collapsed, at least
    ``persistence_fraction`` of the final window in the interval [0, threshold],
    and no active recovery spell lasting ``recovery_years`` or longer.
    """

    if threshold_sv < 0.0:
        raise ValueError("threshold_sv cannot be negative")
    if window_years <= 0.0:
        raise ValueError("window_years must be positive")
    if not 0.0 < persistence_fraction <= 1.0:
        raise ValueError("persistence_fraction must be in (0, 1]")
    if recovery_years < 0.0 or recovery_years > window_years:
        raise ValueError("recovery_years must be between zero and window_years")

    x = np.asarray(years, dtype=float)
    y = np.asarray(values, dtype=float)
    finite = np.isfinite(x) & np.isfinite(y)
    x = x[finite]
    y = y[finite]
    if x.size < 2:
        raise ValueError("At least two finite AMOC records are required")
    order = np.argsort(x)
    x = x[order]
    y = y[order]
    end_year = float(x[-1])
    start_year = end_year - float(window_years)
    if start_year < float(x[0]) - 1.0e-9:
        raise ValueError("Requested collapse window is longer than the trajectory")

    collapsed_all = condition_intervals(x, y, 0.0, threshold_sv, float(x[0]), end_year)
    collapsed_window = condition_intervals(x, y, 0.0, threshold_sv, start_year, end_year)
    active_window = condition_intervals(x, y, threshold_sv, math.inf, start_year, end_year)
    reversed_window = condition_intervals(x, y, -math.inf, 0.0, start_year, end_year)
    collapsed_duration = interval_duration(collapsed_window)
    active_duration = interval_duration(active_window)
    reversed_duration = interval_duration(reversed_window)
    final_value = float(y[-1])
    final_collapsed = bool(0.0 <= final_value <= threshold_sv)
    fraction_collapsed = collapsed_duration / window_years
    longest_active_recovery = longest_interval(active_window)
    recovery_disqualifies = (
        bool(active_window)
        if recovery_years == 0.0
        else longest_active_recovery >= recovery_years
    )
    persistent = bool(
        final_collapsed
        and fraction_collapsed >= persistence_fraction
        and not recovery_disqualifies
        and reversed_duration <= (1.0 - persistence_fraction) * window_years + 1.0e-9
    )

    window_sample_values = y[x >= start_year]
    start_value = float(np.interp(start_year, x, y))
    window_values = np.concatenate(([start_value], window_sample_values))
    return {
        "final_amoc_sv": final_value,
        "final_window_minimum_amoc_sv": float(np.nanmin(window_values)),
        "final_window_maximum_amoc_sv": float(np.nanmax(window_values)),
        "final_window_collapsed_duration_years": collapsed_duration,
        "final_window_collapsed_fraction": float(fraction_collapsed),
        "final_window_longest_continuous_collapse_years": longest_interval(collapsed_window),
        "longest_continuous_collapse_years": longest_interval(collapsed_all),
        "final_window_active_duration_years": active_duration,
        "final_window_longest_active_recovery_years": longest_active_recovery,
        "final_window_reversed_duration_years": reversed_duration,
        "final_window_reversed_fraction": float(reversed_duration / window_years),
        "ever_collapsed": bool(
            collapsed_all or np.any((y >= 0.0) & (y <= threshold_sv))
        ),
        "persistent_collapsed": persistent,
        "reversed": bool(final_value < 0.0),
        "active": bool(final_value > threshold_sv),
    }
