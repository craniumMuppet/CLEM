#!/usr/bin/env python3
"""Compare distinct AMOC structural model families without pooling posteriors."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from climate_model import ModelConfig, ProcessClimateModel


def first_crossing(years: np.ndarray, values: np.ndarray, threshold: float) -> float:
    indices = np.flatnonzero(values <= threshold)
    return float(years[indices[0]]) if indices.size else float("nan")


def parse_choices(raw: str, allowed: Iterable[str], label: str) -> tuple[str, ...]:
    requested = tuple(item.strip() for item in raw.split(",") if item.strip())
    allowed_set = set(allowed)
    invalid = sorted(set(requested) - allowed_set)
    if invalid:
        raise ValueError(f"Invalid {label}: {', '.join(invalid)}")
    if not requested:
        raise ValueError(f"At least one {label} must be selected")
    return requested


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run AMOC structural families separately. The resulting rows are "
            "alternative model structures and must not be pooled as ordinary "
            "parameter samples."
        )
    )
    parser.add_argument(
        "--scenario",
        default="ssp245",
        choices=["ssp126", "ssp245", "ssp460", "ssp585"],
    )
    parser.add_argument("--years", type=float, default=650.0)
    parser.add_argument("--dt", type=float, default=0.1)
    parser.add_argument(
        "--compensation-modes",
        default="external,atlantic",
        help="Comma-separated freshwater compensation modes.",
    )
    parser.add_argument(
        "--coupling-schemes",
        default="euler,heun",
        help="Comma-separated AMOC coupling schemes.",
    )
    parser.add_argument(
        "--southern-ocean-structures",
        default="fixed,warming_sensitive",
        help="Comma-separated Southern Ocean structural families.",
    )
    parser.add_argument(
        "--indo-pacific-modes",
        default="none,diagnostic,interactive",
        help="Comma-separated Indo-Pacific compensation structures.",
    )
    parser.add_argument(
        "--reversal-options",
        default="false,true",
        help="Comma-separated Boolean reversal options.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("amoc_structural_families.csv"),
    )
    args = parser.parse_args()

    compensation_modes = parse_choices(
        args.compensation_modes,
        ("external", "atlantic"),
        "freshwater compensation mode",
    )
    coupling_schemes = parse_choices(
        args.coupling_schemes,
        ("euler", "heun"),
        "coupling scheme",
    )
    southern_structures = parse_choices(
        args.southern_ocean_structures,
        ("fixed", "warming_sensitive"),
        "Southern Ocean structure",
    )
    indo_pacific_modes = parse_choices(
        args.indo_pacific_modes,
        ("none", "diagnostic", "interactive"),
        "Indo-Pacific compensation mode",
    )
    reversal_tokens = parse_choices(
        args.reversal_options,
        ("false", "true"),
        "reversal option",
    )
    reversal_options = tuple(token == "true" for token in reversal_tokens)

    base = ModelConfig(
        scenario=args.scenario,
        duration_years=args.years,
        dt_years=args.dt,
        record_every_years=1.0,
    )
    records: list[dict[str, object]] = []
    for compensation in compensation_modes:
        for reversal in reversal_options:
            for coupling in coupling_schemes:
                for southern_structure in southern_structures:
                    for indo_pacific_mode in indo_pacific_modes:
                        config = replace(
                            base,
                            freshwater_compensation_mode=compensation,
                            amoc_allow_reversal=reversal,
                            amoc_coupling_scheme=coupling,
                            amoc_southern_ocean_structure=southern_structure,
                            amoc_indo_pacific_compensation_mode=indo_pacific_mode,
                        )
                        family = (
                            f"freshwater={compensation}|reversal={reversal}|"
                            f"coupling={coupling}|southern={southern_structure}|"
                            f"indo_pacific={indo_pacific_mode}"
                        )
                        try:
                            frame = ProcessClimateModel(config).run().dataframe
                            years = frame["year"].to_numpy(float)
                            amoc = frame["amoc_sv"].to_numpy(float)
                            records.append(
                                {
                                    "family": family,
                                    "freshwater_compensation_mode": compensation,
                                    "reversal_enabled": reversal,
                                    "coupling_scheme": coupling,
                                    "southern_ocean_structure": southern_structure,
                                    "indo_pacific_compensation_mode": indo_pacific_mode,
                                    "status": "ok",
                                    "final_gmst_c": float(
                                        frame.iloc[-1]["global_surface_warming_c"]
                                    ),
                                    "final_amoc_sv": float(amoc[-1]),
                                    "minimum_amoc_sv": float(np.nanmin(amoc)),
                                    "first_year_amoc_le_6_sv": first_crossing(
                                        years,
                                        amoc,
                                        6.0,
                                    ),
                                    "first_year_amoc_lt_0_sv": first_crossing(
                                        years,
                                        amoc,
                                        -1.0e-12,
                                    ),
                                    "maximum_diagnostic_indo_pacific_compensation_sv": float(
                                        frame[
                                            "amoc_indo_pacific_compensation_diagnostic_sv"
                                        ].max()
                                    ),
                                    "maximum_active_indo_pacific_compensation_sv": float(
                                        frame[
                                            "amoc_indo_pacific_compensation_active_sv"
                                        ].max()
                                    ),
                                    "maximum_absolute_salt_error_ppm": float(
                                        frame["salt_conservation_error_ppm"].abs().max()
                                    ),
                                }
                            )
                        except Exception as error:
                            records.append(
                                {
                                    "family": family,
                                    "freshwater_compensation_mode": compensation,
                                    "reversal_enabled": reversal,
                                    "coupling_scheme": coupling,
                                    "southern_ocean_structure": southern_structure,
                                    "indo_pacific_compensation_mode": indo_pacific_mode,
                                    "status": "failed",
                                    "error": f"{type(error).__name__}: {error}",
                                }
                            )

    result = pd.DataFrame(records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output, index=False)
    metadata = {
        "scenario": args.scenario,
        "years": args.years,
        "dt": args.dt,
        "families_requested": int(len(records)),
        "freshwater_compensation_modes": list(compensation_modes),
        "reversal_options": list(reversal_options),
        "coupling_schemes": list(coupling_schemes),
        "southern_ocean_structures": list(southern_structures),
        "indo_pacific_compensation_modes": list(indo_pacific_modes),
        "note": (
            "Each row is a separate structural model family; do not pool rows "
            "as ordinary parameter samples or interpret row frequencies as probabilities."
        ),
    }
    with args.output.with_suffix(".json").open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)
    print(result.to_string(index=False))
    print(f"\nWritten to {args.output.resolve()}")


if __name__ == "__main__":
    main()
