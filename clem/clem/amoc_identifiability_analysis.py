#!/usr/bin/env python3
"""Posterior sensitivity and identifiability diagnostics for AMOC ensembles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata

PARAMETER_END_COLUMN = "initial_north_salinity_psu"
DEFAULT_OUTCOMES = [
    "ssp585_amoc_decline_2100_percent",
    "hosing_0p1_amoc_decline_40yr_percent",
    "final_amoc_sv",
    "minimum_amoc_sv",
    "amoc_collapsed",
]


def normalize_weights(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    values[~np.isfinite(values)] = 0.0
    values[values < 0.0] = 0.0
    total = values.sum()
    if total <= 0.0:
        return np.full(len(values), 1.0 / len(values))
    return values / total


def weighted_mean(x: np.ndarray, w: np.ndarray) -> float:
    return float(np.sum(w * x))


def weighted_corr(x: np.ndarray, y: np.ndarray, w: np.ndarray) -> float:
    mx = weighted_mean(x, w)
    my = weighted_mean(y, w)
    dx = x - mx
    dy = y - my
    denominator = np.sqrt(np.sum(w * dx * dx) * np.sum(w * dy * dy))
    if denominator <= 0.0:
        return float("nan")
    return float(np.sum(w * dx * dy) / denominator)


def weighted_rank_corr(x: np.ndarray, y: np.ndarray, w: np.ndarray) -> float:
    return weighted_corr(rankdata(x), rankdata(y), w)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("members", type=Path, help="monte_carlo_members_weighted.csv")
    parser.add_argument("--output", type=Path, default=Path("amoc_identifiability"))
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args()

    frame = pd.read_csv(args.members)
    if "posterior_weight" not in frame:
        raise KeyError("posterior_weight column is required")
    if "status" in frame:
        frame = frame.loc[frame["status"] == "ok"].copy()
    weights = normalize_weights(frame["posterior_weight"].to_numpy(float))

    columns = list(frame.columns)
    start = columns.index("co2_doubling_erf_wm2")
    end = columns.index(PARAMETER_END_COLUMN) + 1
    parameters = [
        name for name in columns[start:end]
        if pd.api.types.is_numeric_dtype(frame[name])
    ]
    outcomes = [name for name in DEFAULT_OUTCOMES if name in frame]

    records = []
    for outcome in outcomes:
        y = frame[outcome].to_numpy(float)
        for parameter in parameters:
            x = frame[parameter].to_numpy(float)
            valid = np.isfinite(x) & np.isfinite(y) & np.isfinite(weights)
            if valid.sum() < 20:
                continue
            w = normalize_weights(weights[valid])
            records.append(
                {
                    "outcome": outcome,
                    "parameter": parameter,
                    "weighted_pearson": weighted_corr(x[valid], y[valid], w),
                    "weighted_spearman": weighted_rank_corr(x[valid], y[valid], w),
                    "posterior_mean": weighted_mean(x[valid], w),
                    "posterior_sd": float(np.sqrt(np.sum(w * (x[valid] - weighted_mean(x[valid], w)) ** 2))),
                }
            )

    correlations = pd.DataFrame(records)
    correlations["absolute_weighted_spearman"] = correlations["weighted_spearman"].abs()
    correlations = correlations.sort_values(
        ["outcome", "absolute_weighted_spearman"],
        ascending=[True, False],
    )

    # Weighted standardized design-matrix condition number is a compact warning
    # for equifinality/collinearity. It is not proof of physical identifiability.
    matrix = frame[parameters].to_numpy(float)
    finite_rows = np.all(np.isfinite(matrix), axis=1)
    x = matrix[finite_rows]
    w = normalize_weights(weights[finite_rows])
    mean = np.sum(w[:, None] * x, axis=0)
    sd = np.sqrt(np.sum(w[:, None] * (x - mean) ** 2, axis=0))
    keep = sd > 1.0e-12
    standardized = (x[:, keep] - mean[keep]) / sd[keep]
    weighted_design = standardized * np.sqrt(w[:, None])
    singular_values = np.linalg.svd(weighted_design, compute_uv=False)
    condition_number = float(singular_values[0] / max(singular_values[-1], 1.0e-15))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    correlations.to_csv(args.output.with_suffix(".csv"), index=False)
    summary = {
        "members": int(len(frame)),
        "effective_sample_size": float(1.0 / np.sum(weights**2)),
        "parameters": len(parameters),
        "outcomes": outcomes,
        "weighted_standardized_design_condition_number": condition_number,
        "interpretation": (
            "Large condition numbers and multiple similarly ranked parameters indicate "
            "equifinality. Correlation is sensitivity evidence, not causal identification."
        ),
    }
    with args.output.with_suffix(".json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)

    for outcome in outcomes:
        print(f"\n{outcome}")
        print(
            correlations.loc[correlations["outcome"] == outcome]
            .head(args.top)[
                ["parameter", "weighted_spearman", "weighted_pearson"]
            ]
            .to_string(index=False)
        )
    print("\n" + json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
