#!/usr/bin/env python3
"""Regression tests for v2.20.0 AMOC duration-based completion counts."""

from __future__ import annotations

import numpy as np

from monte_carlo import build_amoc_completion_counts


def main() -> None:
    years = np.arange(2000.0, 2131.0)
    amoc = np.vstack(
        [
            np.full(years.size, 9.0),
            np.full(years.size, 11.0),
            np.where(years >= 2101.0, 5.0, 12.0),
            np.where(years >= 2101.0, -2.0, 12.0),
        ]
    )
    weights = np.array([0.2, 0.2, 0.3, 0.3])
    counts = build_amoc_completion_counts(
        years,
        amoc,
        weights,
        posterior_weighting_enabled=True,
    )

    assert counts["successful_members"] == 4
    assert counts["at_2100"]["available"] is True
    assert counts["at_2100"]["count_under_threshold"] == 1
    assert counts["at_2100"]["count_not_under_threshold"] == 3
    assert np.isclose(
        counts["at_2100"]["posterior_weight_sum_under_threshold"], 0.2
    )
    assert np.isclose(
        counts["at_2100"]["conditional_weighted_fraction_under_threshold"],
        0.2,
    )
    assert "weighted_probability_under_threshold" not in counts["at_2100"]

    duration = counts["final_30_year_duration"]
    assert duration["available"] is True
    assert duration["collapsed_count"] == 1
    assert duration["reversed_count"] == 1
    assert duration["active_count"] == 2
    assert duration["not_collapsed_count"] == 2
    assert np.isclose(duration["posterior_weight_sum_collapsed"], 0.3)
    assert np.isclose(duration["posterior_weight_sum_reversed"], 0.3)
    assert np.isclose(duration["posterior_weight_sum_not_collapsed"], 0.4)
    assert np.isclose(duration["conditional_weighted_collapse_fraction"], 0.3)
    assert np.isclose(duration["conditional_weighted_reversal_fraction"], 0.3)
    assert np.isclose(duration["conditional_weighted_active_fraction"], 0.4)
    assert duration["persistence_required_fraction"] == 0.95
    assert duration["recovery_disqualifying_years"] == 5.0
    assert "final_30_year_mean" not in counts

    short_years = np.arange(2000.0, 2011.0)
    short_amoc = np.full((2, short_years.size), 8.0)
    unavailable = build_amoc_completion_counts(
        short_years,
        short_amoc,
        np.array([0.5, 0.5]),
    )
    assert unavailable["at_2100"]["available"] is False
    assert unavailable["final_30_year_duration"]["available"] is False

    print("All v2.20.0 AMOC completion-count tests passed.")


if __name__ == "__main__":
    main()
