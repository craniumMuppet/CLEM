"""Scientifically conservative Arctic sea-ice validation.

This module deliberately separates three evidence classes:

1. NOAA/NSIDC Sea Ice Index v4 *extent*, which is retained as a historical
   diagnostic.
2. Raw Sea Ice Index v4 *area*, which is packaged for provenance but is never
   used for calibration, trend skill, release gating, or headline scores
   because its pole-hole mask changes across satellite eras.
3. Optional homogeneous fixed-mask area and source-separated volume/thickness
   observations.  Scientific area/volume validation is enabled only when those
   datasets are explicitly supplied with metadata.

The model's 15 %-extent diagnostic is generated from native prognostic
concentration and contains no fitted area-to-extent multiplier.

Historical rolling-origin and fold-local scores remain method-development evidence.
They are not untouched predictive validation. The predictive skill gate remains
closed until the reserved prospective period can be evaluated.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import linregress, theilslopes

from prospective_validation_r16 import evaluate as evaluate_r16_prospective

from arctic_observation_operator import (
    load_spatial_operator,
    load_temporal_thickness_operator,
    model_fixed_mask_area_extent,
    model_mean_thickness_on_temporal_operator,
    model_volume_on_operator,
    prepare_model_grid_sampler,
)
from arctic_validation_stack import (
    CRYOSAT2_OPERATOR,
    ICESAT2_OPERATOR,
    OSI_SAF_OPERATOR,
    PHYSICAL_METRIC_THRESHOLDS,
    PIOMAS_OPERATOR,
    PRIMARY_AREA_OPERATOR,
    load_ice_age_annual,
    load_osi_saf_month,
    load_physical_source,
    source_status,
    validation_stack_status,
)

ROOT = Path(__file__).resolve().parent
NSIDC_DIR = ROOT / "data" / "validation" / "nsidc"
FIXED_MASK_DIR = ROOT / "data" / "validation" / "sea_ice_fixed_mask"
PHYSICAL_DIR = ROOT / "data" / "validation" / "sea_ice_physical"
PROSPECTIVE_UNTOUCHED_START_YEAR = 2027
MIN_FIXED_MASK_TREND_MAGNITUDE_RATIO = 0.80
MAX_FIXED_MASK_TREND_MAGNITUDE_RATIO = 1.25
RECENT_PERIOD_AREA_RMSE_LIMIT_MILLION_KM2 = 0.50


@dataclass(frozen=True)
class Period:
    """Evidence partition used by the release validator."""

    name: str
    start_year: int
    end_year: int
    evidence_role: str
    used_for_tuning: bool


CALIBRATION = Period(
    "development_1979_2020",
    1979,
    2020,
    "tuning_informed_historical_development_not_independent_validation",
    True,
)
DEVELOPMENT_EVALUATION = Period(
    "validation_informed_development_evaluation_2021_2025",
    2021,
    2025,
    "validation_informed_development_evaluation_not_independent",
    True,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_nsidc_month(month: int) -> pd.DataFrame:
    """Load the packaged Sea Ice Index v4 monthly table.

    The returned ``area`` column is raw source material only.  Callers must not
    interpret it as a homogeneous long-term calibration target.
    """
    path = NSIDC_DIR / f"N_{month:02d}_extent_v4.0.csv"
    frame = pd.read_csv(path, skipinitialspace=True)
    frame.columns = [str(column).strip() for column in frame.columns]
    return frame


def _fixed_mask_path(month: int) -> Path:
    return FIXED_MASK_DIR / f"N_{month:02d}_fixed_mask.csv"


def homogeneous_area_metadata() -> dict[str, Any]:
    """Return metadata for the primary fixed-mask sea-ice area product.

    Availability requires the explicit model observation operator in addition
    to the two monthly tables.  The model is compared by sampling its native
    concentration on this exact retained observation support.
    """
    path = FIXED_MASK_DIR / "METADATA.json"
    if not path.exists():
        return {
            "available": False,
            "status": "missing",
            "required_directory": str(FIXED_MASK_DIR.relative_to(ROOT)),
            "required_files": [
                "N_03_fixed_mask.csv",
                "N_09_fixed_mask.csv",
                "MODEL_OBSERVATION_OPERATOR.npz",
                "METADATA.json",
            ],
            "reason": (
                "No complete homogeneous fixed-mask area dataset/operator is bundled. "
                "Raw NSIDC Sea Ice Index area is excluded from calibration."
            ),
        }
    try:
        metadata = dict(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError) as exc:
        return {"available": False, "status": "invalid_metadata", "reason": str(exc)}
    fixed_mask = bool(metadata.get("fixed_mask", False))
    threshold = metadata.get("concentration_threshold")
    try:
        threshold_ok = abs(float(threshold) - 0.15) <= 1.0e-12
    except (TypeError, ValueError):
        threshold_ok = False
    required_tables_exist = all(_fixed_mask_path(month).exists() for month in (3, 9))
    operator_exists = PRIMARY_AREA_OPERATOR.exists()
    runtime_operator_declared = (
        "runtime spatial observation operator"
        in str(metadata.get("model_domain_compatibility_basis", "")).lower()
    )
    metadata["available"] = bool(
        fixed_mask
        and threshold_ok
        and required_tables_exist
        and operator_exists
        and runtime_operator_declared
    )
    metadata["operator_file_exists"] = operator_exists
    if not metadata["available"]:
        metadata["status"] = "invalid_or_incomplete_metadata"
        metadata["reason"] = (
            "Scientific fixed-mask area requires fixed_mask=true, concentration_threshold=0.15, "
            "both March/September CSV tables, and MODEL_OBSERVATION_OPERATOR.npz with the "
            "runtime exact-support comparison contract."
        )
    else:
        metadata["status"] = "available"
    return metadata

def load_homogeneous_area_month(month: int) -> pd.DataFrame | None:
    """Load an optional homogeneous fixed-mask monthly area table.

    Required columns are ``year`` and ``area`` in million km2.  An optional
    ``extent`` column may be present but NSIDC extent remains the primary
    packaged extent diagnostic unless an explicitly documented replacement is
    chosen outside this module.
    """
    metadata = homogeneous_area_metadata()
    path = _fixed_mask_path(month)
    if not metadata.get("available", False) or not path.exists():
        return None
    frame = pd.read_csv(path, skipinitialspace=True)
    frame.columns = [str(column).strip() for column in frame.columns]
    required = {"year", "area"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{path.name} missing required columns: {missing}")
    if frame["year"].duplicated().any():
        raise ValueError(f"{path.name} contains duplicate years")
    area = pd.to_numeric(frame["area"], errors="coerce").to_numpy(dtype=float)
    if not np.all(np.isfinite(area)) or np.any(area < 0.0):
        raise ValueError(f"{path.name} contains invalid fixed-mask area values")
    return frame


def physical_observation_metadata() -> dict[str, Any]:
    """Return source-separated metadata for PIOMAS, CryoSat-2, and ICESat-2."""
    source_ids = (
        "piomas_v2_1",
        "cryosat2_rdeft4_v1",
        "icesat2_is2sitmogr4_v4",
    )
    statuses = {source_id: source_status(source_id) for source_id in source_ids}
    available_count = sum(bool(item.get("available", False)) for item in statuses.values())
    complete = available_count == len(source_ids)
    return {
        "available": available_count > 0,
        "complete": complete,
        "status": "complete" if complete else "incomplete",
        "available_source_count": available_count,
        "required_source_count": len(source_ids),
        "sources": statuses,
        "reason": (
            "PIOMAS supplies the long volume constraint; CryoSat-2 and ICESat-2 "
            "supply source-separated, development-informed satellite thickness "
            "constraints. These products were visible during recalibration and "
            "are never merged before scoring."
        ),
    }

def load_physical_observations() -> pd.DataFrame | None:
    """Backward-compatible loader for the PIOMAS long-volume constraint only.

    Satellite thickness products are intentionally not merged into this frame;
    source-separated scoring is performed by :func:`evaluate_physical_constraints`.
    """
    return load_physical_source("piomas_v2_1")

def nearest_record_index(years: np.ndarray, year: int, month: int) -> int:
    target = float(year) + (float(month) - 0.5) / 12.0
    return int(np.argmin(np.abs(np.asarray(years, dtype=float) - target)))


def model_monthly_records(
    result: Any,
    years: range,
    months: tuple[int, ...] = (3, 9),
) -> pd.DataFrame:
    """Pair model records with observations through source-specific operators."""
    rows: list[dict[str, float | int | str | bool]] = []
    model_years = result.dataframe["year"].to_numpy(dtype=float)

    physical_frames = {
        source_id: load_physical_source(source_id)
        for source_id in (
            "piomas_v2_1",
            "cryosat2_rdeft4_v1",
            "icesat2_is2sitmogr4_v4",
        )
    }
    physical_indices = {
        source_id: frame.set_index(["year", "month"])
        for source_id, frame in physical_frames.items()
        if frame is not None
    }

    def prepare_spatial(path: Path):
        if not path.exists():
            return None
        try:
            operator = load_spatial_operator(path)
            sampler = prepare_model_grid_sampler(
                result, operator.latitude_deg, operator.longitude_deg
            )
            return operator, sampler
        except (AttributeError, KeyError, ValueError):
            return None

    def prepare_temporal(path: Path):
        if not path.exists():
            return None
        try:
            operator = load_temporal_thickness_operator(path)
            sampler = prepare_model_grid_sampler(
                result, operator.latitude_deg, operator.longitude_deg
            )
            return operator, sampler
        except (AttributeError, KeyError, ValueError):
            return None

    primary_runtime = (
        prepare_spatial(PRIMARY_AREA_OPERATOR)
        if source_status("nsidc_g02202_v6").get("available", False)
        else None
    )
    piomas_runtime = (
        prepare_spatial(PIOMAS_OPERATOR)
        if source_status("piomas_v2_1").get("available", False)
        else None
    )
    cryosat_runtime = (
        prepare_temporal(CRYOSAT2_OPERATOR)
        if source_status("cryosat2_rdeft4_v1").get("available", False)
        else None
    )
    icesat_runtime = (
        prepare_temporal(ICESAT2_OPERATOR)
        if source_status("icesat2_is2sitmogr4_v4").get("available", False)
        else None
    )
    osi_runtime = (
        prepare_spatial(OSI_SAF_OPERATOR)
        if source_status("osi_saf_osi450a1_v3_1").get("available", False)
        else None
    )

    for month in months:
        raw = load_nsidc_month(month).set_index("year")
        homogeneous = load_homogeneous_area_month(month)
        homogeneous_index = homogeneous.set_index("year") if homogeneous is not None else None
        for year in years:
            if year not in raw.index:
                continue
            index = nearest_record_index(model_years, year, month)
            target = float(year) + (float(month) - 0.5) / 12.0
            if abs(float(model_years[index]) - target) > 0.10:
                raise ValueError(
                    "Sea-ice validation requires subannual records at 0.1-year cadence or finer"
                )
            metrics = result.northern_sea_ice_area_extent_at_index(index)
            physical_metrics = (
                result.northern_sea_ice_volume_thickness_at_index(index)
                if hasattr(result, "northern_sea_ice_volume_thickness_at_index")
                else {}
            )
            native_area = float(metrics["native_northern_ice_area_million_km2"])

            homogeneous_row = None
            if homogeneous_index is not None and year in homogeneous_index.index:
                homogeneous_row = homogeneous_index.loc[year]
            observed_fixed_area = (
                float(homogeneous_row["area"]) if homogeneous_row is not None else float("nan")
            )
            area_source = (
                str(homogeneous_row.get("source", "NOAA_NSIDC_G02202_v6_fixed_mask"))
                if homogeneous_row is not None
                else "unavailable_raw_nsidc_area_excluded"
            )

            primary_area = float("nan")
            primary_extent = float("nan")
            primary_operator_applied = False
            primary_mapping_distance = float("nan")
            if primary_runtime is not None and homogeneous_row is not None:
                operator, sampler = primary_runtime
                fixed = model_fixed_mask_area_extent(result, index, operator, sampler)
                primary_area = float(fixed["area_million_km2"])
                primary_extent = float(fixed["extent_million_km2"])
                primary_mapping_distance = float(fixed["maximum_mapping_distance_deg"])
                primary_operator_applied = True

            osi_model_area = float("nan")
            if osi_runtime is not None:
                operator, sampler = osi_runtime
                osi_fixed = model_fixed_mask_area_extent(result, index, operator, sampler)
                osi_model_area = float(osi_fixed["area_million_km2"])

            model_piomas_volume = float("nan")
            if piomas_runtime is not None and hasattr(result, "arctic_local_ice_thickness_map_at_index"):
                operator, sampler = piomas_runtime
                model_piomas_volume = model_volume_on_operator(result, index, operator, sampler)

            model_cryosat_thickness = float("nan")
            if cryosat_runtime is not None and hasattr(result, "arctic_local_ice_thickness_map_at_index"):
                operator, sampler = cryosat_runtime
                model_cryosat_thickness = model_mean_thickness_on_temporal_operator(
                    result, index, operator, sampler, year=year, month=month
                )

            model_icesat_thickness = float("nan")
            if icesat_runtime is not None and hasattr(result, "arctic_local_ice_thickness_map_at_index"):
                operator, sampler = icesat_runtime
                model_icesat_thickness = model_mean_thickness_on_temporal_operator(
                    result, index, operator, sampler, year=year, month=month
                )

            source_column = "source_dataset" if "source_dataset" in raw.columns else "source-data"
            row: dict[str, float | int | str | bool] = {
                "year": year,
                "month": month,
                "model_year": float(model_years[index]),
                # Scientific area target: exact G02202 fixed-support operator only.
                "model_area": primary_area,
                "model_fixed_mask_area_million_km2": primary_area,
                "model_fixed_mask_extent_diagnostic_million_km2": primary_extent,
                "model_fixed_mask_operator_applied": primary_operator_applied,
                "model_fixed_mask_maximum_mapping_distance_deg": primary_mapping_distance,
                # Native/full-domain diagnostics remain separate and are not substituted for the fixed-mask score.
                "model_thresholded_area_full_nh_million_km2": float(
                    metrics["northern_hemisphere_sea_ice_thresholded_area_million_km2"]
                ),
                "model_physical_area": float(metrics["northern_hemisphere_sea_ice_area_million_km2"]),
                "model_extent": float(metrics["northern_hemisphere_sea_ice_extent_million_km2"]),
                "model_native_area": native_area,
                "model_raw_area": native_area,
                "model_osi_saf_fixed_mask_area_million_km2": osi_model_area,
                "model_warming_c": float(result.dataframe.iloc[index]["global_surface_warming_c"]),
                "observed_area": observed_fixed_area,
                "observed_raw_area_excluded": float(raw.loc[year, "area"]),
                "observed_area_is_homogeneous_fixed_mask": bool(homogeneous_row is not None),
                "observed_area_source": area_source,
                "observed_extent": float(raw.loc[year, "extent"]),
                "observation_source": str(raw.loc[year, source_column]),
                # Full-domain native physical diagnostics, retained for process inspection only.
                "model_volume_million_km3": float(physical_metrics.get(
                    "northern_hemisphere_sea_ice_volume_million_km3", float("nan")
                )),
                "model_mean_thickness_m": float(physical_metrics.get(
                    "northern_hemisphere_mean_ice_thickness_m", float("nan")
                )),
                "model_thick_ice_area_million_km2": float(physical_metrics.get(
                    "northern_hemisphere_thick_ice_area_million_km2", float("nan")
                )),
                "model_thick_ice_area_fraction": float(physical_metrics.get(
                    "northern_hemisphere_thick_ice_area_fraction", float("nan")
                )),
                # Source-specific like-for-like physical observation operators.
                "model_piomas_volume_million_km3": model_piomas_volume,
                "model_cryosat2_mean_thickness_m": model_cryosat_thickness,
                "model_icesat2_mean_thickness_m": model_icesat_thickness,
                "observed_volume_million_km3": float("nan"),
                "observed_mean_thickness_m": float("nan"),
                "observed_thick_ice_area_million_km2": float("nan"),
                "observed_piomas_volume_million_km3": float("nan"),
                "observed_cryosat2_mean_thickness_m": float("nan"),
                "observed_icesat2_mean_thickness_m": float("nan"),
                "physical_observation_source": "unavailable",
            }
            key = (year, month)
            piomas_index = physical_indices.get("piomas_v2_1")
            if piomas_index is not None and key in piomas_index.index:
                value = float(piomas_index.loc[key]["volume_million_km3"])
                row["observed_piomas_volume_million_km3"] = value
                row["observed_volume_million_km3"] = value
            cryo_index = physical_indices.get("cryosat2_rdeft4_v1")
            if cryo_index is not None and key in cryo_index.index:
                row["observed_cryosat2_mean_thickness_m"] = float(
                    cryo_index.loc[key]["mean_thickness_m"]
                )
            icesat_index = physical_indices.get("icesat2_is2sitmogr4_v4")
            if icesat_index is not None and key in icesat_index.index:
                row["observed_icesat2_mean_thickness_m"] = float(
                    icesat_index.loc[key]["mean_thickness_m"]
                )
            supplied = []
            if np.isfinite(float(row["observed_piomas_volume_million_km3"])):
                supplied.append("PIOMAS_v2.1_common_domain")
            if np.isfinite(float(row["observed_cryosat2_mean_thickness_m"])):
                supplied.append("CryoSat2_RDEFT4_v1")
            if np.isfinite(float(row["observed_icesat2_mean_thickness_m"])):
                supplied.append("ICESat2_IS2SITMOGR4_v4")
            if supplied:
                row["physical_observation_source"] = "+".join(supplied)
            rows.append(row)
    return pd.DataFrame(rows)

def _safe_correlation(model: np.ndarray, observed: np.ndarray) -> float:
    if (
        len(model) < 3
        or float(np.std(model)) <= 1.0e-14
        or float(np.std(observed)) <= 1.0e-14
    ):
        return float("nan")
    return float(np.corrcoef(model, observed)[0, 1])


def _trend_summary(years: np.ndarray, values: np.ndarray) -> dict[str, float]:
    """Return OLS and robust trend diagnostics in million km2 per decade."""
    years = np.asarray(years, dtype=float)
    values = np.asarray(values, dtype=float)
    finite = np.isfinite(years) & np.isfinite(values)
    years = years[finite]
    values = values[finite]
    if len(values) < 2:
        nan = float("nan")
        return {
            "ols_trend_million_km2_per_decade": nan,
            "ols_standard_error_million_km2_per_decade": nan,
            "ols_95pct_ci_low_million_km2_per_decade": nan,
            "ols_95pct_ci_high_million_km2_per_decade": nan,
            "theil_sen_trend_million_km2_per_decade": nan,
            "theil_sen_95pct_ci_low_million_km2_per_decade": nan,
            "theil_sen_95pct_ci_high_million_km2_per_decade": nan,
        }
    regression = linregress(years, values)
    theil = theilslopes(values, years, 0.95)
    slope = float(regression.slope * 10.0)
    standard_error = float(regression.stderr * 10.0)
    return {
        "ols_trend_million_km2_per_decade": slope,
        "ols_standard_error_million_km2_per_decade": standard_error,
        "ols_95pct_ci_low_million_km2_per_decade": float(
            slope - 1.96 * standard_error
        ),
        "ols_95pct_ci_high_million_km2_per_decade": float(
            slope + 1.96 * standard_error
        ),
        "theil_sen_trend_million_km2_per_decade": float(theil.slope * 10.0),
        "theil_sen_95pct_ci_low_million_km2_per_decade": float(
            theil.low_slope * 10.0
        ),
        "theil_sen_95pct_ci_high_million_km2_per_decade": float(
            theil.high_slope * 10.0
        ),
    }


def _empty_metric_summary(reason: str) -> dict[str, Any]:
    nan = float("nan")
    return {
        "available": False,
        "reason": reason,
        "records": 0,
        "model_mean_million_km2": nan,
        "observed_mean_million_km2": nan,
        "rmse_million_km2": nan,
        "mae_million_km2": nan,
        "bias_million_km2": nan,
        "correlation": nan,
        "model_trend_million_km2_per_decade": nan,
        "observed_trend_million_km2_per_decade": nan,
        "model_trend_diagnostics": _trend_summary(np.array([]), np.array([])),
        "observed_trend_diagnostics": _trend_summary(np.array([]), np.array([])),
    }


def _metric_summary(frame: pd.DataFrame, quantity: str) -> dict[str, Any]:
    model_name = f"model_{quantity}"
    observed_name = f"observed_{quantity}"
    if model_name not in frame.columns or observed_name not in frame.columns:
        return _empty_metric_summary(f"missing columns for {quantity}")
    model_all = frame[model_name].to_numpy(dtype=float)
    observed_all = frame[observed_name].to_numpy(dtype=float)
    finite = np.isfinite(model_all) & np.isfinite(observed_all)
    if int(np.count_nonzero(finite)) < 2:
        reason = (
            "homogeneous fixed-mask observations unavailable"
            if quantity == "area"
            else f"insufficient observations for {quantity}"
        )
        return _empty_metric_summary(reason)
    model = model_all[finite]
    observed = observed_all[finite]
    years = frame["year"].to_numpy(dtype=float)[finite]
    error = model - observed
    model_trend = _trend_summary(years, model)
    observed_trend = _trend_summary(years, observed)
    return {
        "available": True,
        "records": int(len(model)),
        "model_mean_million_km2": float(np.mean(model)),
        "observed_mean_million_km2": float(np.mean(observed)),
        "rmse_million_km2": float(np.sqrt(np.mean(error * error))),
        "mae_million_km2": float(np.mean(np.abs(error))),
        "bias_million_km2": float(np.mean(error)),
        "correlation": _safe_correlation(model, observed),
        "model_trend_million_km2_per_decade": model_trend[
            "ols_trend_million_km2_per_decade"
        ],
        "observed_trend_million_km2_per_decade": observed_trend[
            "ols_trend_million_km2_per_decade"
        ],
        "model_trend_diagnostics": model_trend,
        "observed_trend_diagnostics": observed_trend,
    }


def _raw_area_diagnostic(frame: pd.DataFrame) -> dict[str, Any]:
    if "observed_raw_area_excluded" not in frame.columns:
        return {"available": False, "used_for_calibration": False}
    model = frame["model_area"].to_numpy(dtype=float)
    observed = frame["observed_raw_area_excluded"].to_numpy(dtype=float)
    years = frame["year"].to_numpy(dtype=float)
    finite = np.isfinite(model) & np.isfinite(observed)
    if np.count_nonzero(finite) < 2:
        return {"available": False, "used_for_calibration": False}
    return {
        "available": True,
        "used_for_calibration": False,
        "used_for_skill_claim": False,
        "warning": (
            "Raw NSIDC area is reported for provenance only. Pole-hole mask "
            "changes make its long-term level/trend unsuitable for calibration."
        ),
        "model_trend": _trend_summary(years[finite], model[finite]),
        "raw_observed_trend_not_scientific_target": _trend_summary(
            years[finite], observed[finite]
        ),
    }


def evaluate_period(records: pd.DataFrame, period: Period) -> dict[str, Any]:
    selected = records[records["year"].between(period.start_year, period.end_year)]
    by_month: dict[str, Any] = {}
    for month in (3, 9):
        month_frame = selected[selected["month"] == month]
        area = _metric_summary(month_frame, "area")
        extent = _metric_summary(month_frame, "extent")
        by_month[str(month)] = {
            "area": area,
            "extent": extent,
            "raw_nsidc_area_diagnostic_excluded": _raw_area_diagnostic(month_frame),
            "fixed_mask_model_operator_applied_for_all_scored_records": bool(
                "model_fixed_mask_operator_applied" in month_frame.columns
                and np.any(np.isfinite(month_frame["observed_area"].to_numpy(dtype=float)))
                and np.all(
                    month_frame.loc[
                        np.isfinite(month_frame["observed_area"].to_numpy(dtype=float)),
                        "model_fixed_mask_operator_applied",
                    ].fillna(False).to_numpy(dtype=bool)
                )
            ),
            "fixed_mask_model_operator_applied_record_count": int(
                np.count_nonzero(
                    month_frame.get(
                        "model_fixed_mask_operator_applied",
                        pd.Series(False, index=month_frame.index),
                    ).fillna(False).to_numpy(dtype=bool)
                )
            ),
            "source_products": sorted(
                set(str(value) for value in month_frame["observation_source"])
            ),
        }
    march_area = by_month["3"]["area"]
    september_area = by_month["9"]["area"]
    area_amplitude_available = bool(
        march_area.get("available") and september_area.get("available")
    )
    if area_amplitude_available:
        model_amplitude = float(
            march_area["model_mean_million_km2"]
            - september_area["model_mean_million_km2"]
        )
        observed_amplitude = float(
            march_area["observed_mean_million_km2"]
            - september_area["observed_mean_million_km2"]
        )
    else:
        model_amplitude = float("nan")
        observed_amplitude = float("nan")
    return {
        "name": period.name,
        "period": [period.start_year, period.end_year],
        "evidence_role": period.evidence_role,
        "used_for_tuning": period.used_for_tuning,
        "records": int(len(selected)),
        "months": by_month,
        "homogeneous_area_available": area_amplitude_available,
        "model_march_minus_september_area_million_km2": model_amplitude,
        "observed_march_minus_september_area_million_km2": observed_amplitude,
    }


def _rolling_origin_metric(
    records: pd.DataFrame,
    *,
    month: int,
    quantity: str,
    minimum_training_years: int = 10,
) -> dict[str, Any]:
    """Descriptive fixed-trajectory rolling comparison with prior-only baselines."""
    frame = (
        records[records["month"] == month]
        .sort_values("year")
        .reset_index(drop=True)
    )
    model_name = f"model_{quantity}"
    observed_name = f"observed_{quantity}"
    if model_name not in frame or observed_name not in frame:
        return {"available": False, "records": [], "folds": 0}
    finite = np.isfinite(frame[model_name].to_numpy(dtype=float)) & np.isfinite(
        frame[observed_name].to_numpy(dtype=float)
    )
    frame = frame.loc[finite].reset_index(drop=True)
    if len(frame) <= minimum_training_years:
        return {
            "available": False,
            "folds": 0,
            "minimum_training_years": minimum_training_years,
            "records": [],
            "reason": "insufficient admissible observations",
        }
    rows: list[dict[str, float | int]] = []
    for index in range(minimum_training_years, len(frame)):
        training = frame.iloc[:index]
        target = frame.iloc[index]
        years = training["year"].to_numpy(dtype=float)
        observed = training[observed_name].to_numpy(dtype=float)
        target_year = float(target["year"])
        trend_prediction = float(np.polyval(np.polyfit(years, observed, 1), target_year))
        rows.append(
            {
                "year": int(target["year"]),
                "observed": float(target[observed_name]),
                "model": float(target[model_name]),
                "persistence": float(observed[-1]),
                "expanding_linear_trend": trend_prediction,
            }
        )
    fold = pd.DataFrame(rows)
    observed = fold["observed"].to_numpy(dtype=float)

    def rmse(column: str) -> float:
        error = fold[column].to_numpy(dtype=float) - observed
        return float(np.sqrt(np.mean(error * error)))

    model_rmse = rmse("model")
    persistence_rmse = rmse("persistence")
    trend_rmse = rmse("expanding_linear_trend")
    return {
        "available": True,
        "first_target_year": int(fold.iloc[0]["year"]),
        "last_target_year": int(fold.iloc[-1]["year"]),
        "folds": int(len(fold)),
        "minimum_training_years": minimum_training_years,
        "model_rmse_million_km2": model_rmse,
        "one_year_persistence_rmse_million_km2": persistence_rmse,
        "expanding_linear_trend_rmse_million_km2": trend_rmse,
        "model_skill_score_vs_persistence": float(
            1.0 - model_rmse / max(persistence_rmse, 1.0e-12)
        ),
        "model_skill_score_vs_expanding_linear_trend": float(
            1.0 - model_rmse / max(trend_rmse, 1.0e-12)
        ),
        "interpretation": (
            "descriptive historical forced-signal comparison; not predictive validation "
            "because the complete model is not recalibrated inside each fold"
        ),
        "records": rows,
    }


def rolling_origin_evaluation(records: pd.DataFrame) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for month, season in ((3, "march"), (9, "september")):
        metrics[f"{season}_extent"] = _rolling_origin_metric(
            records, month=month, quantity="extent"
        )
        metrics[f"{season}_area"] = _rolling_origin_metric(
            records, month=month, quantity="area"
        )
    return {
        "evidence_role": "fixed_trajectory_historical_diagnostic_only",
        "used_for_tuning": True,
        "independent_predictive_validation": False,
        "model_recalibrated_inside_each_fold": False,
        "method": (
            "Baselines use only observations available before each target, but "
            "the emulator trajectory is fixed and was not recalibrated inside folds."
        ),
        "metrics": metrics,
    }


def _prior_only_bias_corrected_metric(
    records: pd.DataFrame,
    *,
    month: int,
    quantity: str,
    minimum_training_years: int = 10,
) -> dict[str, Any]:
    frame = (
        records[records["month"] == month]
        .sort_values("year")
        .reset_index(drop=True)
    )
    model_name = f"model_{quantity}"
    observed_name = f"observed_{quantity}"
    if model_name not in frame or observed_name not in frame:
        return {"available": False, "folds": 0, "records": []}
    finite = np.isfinite(frame[model_name].to_numpy(dtype=float)) & np.isfinite(
        frame[observed_name].to_numpy(dtype=float)
    )
    frame = frame.loc[finite].reset_index(drop=True)
    if len(frame) <= minimum_training_years:
        return {"available": False, "folds": 0, "records": []}
    rows: list[dict[str, float | int]] = []
    for index in range(minimum_training_years, len(frame)):
        training = frame.iloc[:index]
        target = frame.iloc[index]
        training_bias = float(
            np.mean(
                training[model_name].to_numpy(dtype=float)
                - training[observed_name].to_numpy(dtype=float)
            )
        )
        rows.append(
            {
                "year": int(target["year"]),
                "observed": float(target[observed_name]),
                "raw_model": float(target[model_name]),
                "prior_only_bias_correction": training_bias,
                "bias_corrected_model": float(target[model_name]) - training_bias,
            }
        )
    fold = pd.DataFrame(rows)
    error = (
        fold["bias_corrected_model"].to_numpy(dtype=float)
        - fold["observed"].to_numpy(dtype=float)
    )
    return {
        "available": True,
        "first_target_year": int(fold.iloc[0]["year"]),
        "last_target_year": int(fold.iloc[-1]["year"]),
        "folds": int(len(fold)),
        "minimum_training_years": minimum_training_years,
        "rmse_million_km2": float(np.sqrt(np.mean(error * error))),
        "records": rows,
    }


def _five_year_forced_signal_metric(
    records: pd.DataFrame,
    *,
    month: int,
    quantity: str,
    minimum_training_years: int = 15,
    window_years: int = 5,
) -> dict[str, Any]:
    frame = (
        records[records["month"] == month]
        .sort_values("year")
        .reset_index(drop=True)
    )
    model_name = f"model_{quantity}"
    observed_name = f"observed_{quantity}"
    if model_name not in frame or observed_name not in frame:
        return {"available": False, "folds": 0, "records": []}
    finite = np.isfinite(frame[model_name].to_numpy(dtype=float)) & np.isfinite(
        frame[observed_name].to_numpy(dtype=float)
    )
    frame = frame.loc[finite].reset_index(drop=True)
    rows: list[dict[str, float | int]] = []
    first_start = max(minimum_training_years, window_years)
    for start in range(first_start, len(frame) - window_years + 1, window_years):
        target_window = frame.iloc[start : start + window_years]
        prior = frame.iloc[:start]
        prior_window = prior.iloc[-window_years:]
        prior_block_means: list[float] = []
        prior_block_years: list[float] = []
        for block_start in range(0, len(prior) - window_years + 1, window_years):
            block = prior.iloc[block_start : block_start + window_years]
            prior_block_means.append(float(block[observed_name].mean()))
            prior_block_years.append(float(block["year"].mean()))
        target_midyear = float(target_window["year"].mean())
        if len(prior_block_means) >= 2:
            trend_prediction = float(
                np.polyval(
                    np.polyfit(prior_block_years, prior_block_means, 1),
                    target_midyear,
                )
            )
        else:
            trend_prediction = float(prior_window[observed_name].mean())
        rows.append(
            {
                "start_year": int(target_window["year"].iloc[0]),
                "end_year": int(target_window["year"].iloc[-1]),
                "observed_five_year_mean": float(target_window[observed_name].mean()),
                "model_five_year_mean": float(target_window[model_name].mean()),
                "prior_nonoverlapping_five_year_persistence": float(
                    prior_window[observed_name].mean()
                ),
                "prior_expanding_nonoverlapping_block_trend": trend_prediction,
            }
        )
    fold = pd.DataFrame(rows)
    if fold.empty:
        return {
            "available": False,
            "folds": 0,
            "window_years": window_years,
            "records": [],
        }
    observed = fold["observed_five_year_mean"].to_numpy(dtype=float)

    def rmse(column: str) -> float:
        error = fold[column].to_numpy(dtype=float) - observed
        return float(np.sqrt(np.mean(error * error)))

    model_rmse = rmse("model_five_year_mean")
    persistence_rmse = rmse("prior_nonoverlapping_five_year_persistence")
    trend_rmse = rmse("prior_expanding_nonoverlapping_block_trend")
    return {
        "available": True,
        "first_target_year": int(fold.iloc[0]["start_year"]),
        "last_target_year": int(fold.iloc[-1]["end_year"]),
        "folds": int(len(fold)),
        "window_years": window_years,
        "blocks_are_nonoverlapping": True,
        "model_rmse_million_km2": model_rmse,
        "prior_five_year_persistence_rmse_million_km2": persistence_rmse,
        "prior_expanding_five_year_trend_rmse_million_km2": trend_rmse,
        "model_skill_score_vs_persistence": float(
            1.0 - model_rmse / max(persistence_rmse, 1.0e-12)
        ),
        "model_skill_score_vs_expanding_linear_trend": float(
            1.0 - model_rmse / max(trend_rmse, 1.0e-12)
        ),
        "interpretation": (
            "descriptive historical forced-signal comparison; not predictive validation "
            "because the complete model is not recalibrated inside each fold"
        ),
        "records": rows,
    }


def enhanced_historical_evaluation(records: pd.DataFrame) -> dict[str, Any]:
    bias_corrected: dict[str, Any] = {}
    forced_signal: dict[str, Any] = {}
    for month, season in ((3, "march"), (9, "september")):
        for quantity in ("extent", "area"):
            key = f"{season}_{quantity}"
            bias_corrected[key] = _prior_only_bias_corrected_metric(
                records, month=month, quantity=quantity
            )
            forced_signal[key] = _five_year_forced_signal_metric(
                records, month=month, quantity=quantity
            )
    return {
        "prior_only_bias_corrected_annual": bias_corrected,
        "five_year_forced_signal": forced_signal,
        "extent_scores_are_diagnostic_only": True,
        "area_scores_require_homogeneous_fixed_mask": True,
        "used_for_quantitative_skill_claim": False,
        "evidence_role": "validation_informed_historical_diagnostics",
        "used_for_tuning": True,
        "independent_predictive_validation": False,
        "model_recalibrated_inside_each_fold": False,
    }


def inspected_march_2026_evaluation(records: pd.DataFrame) -> dict[str, Any]:
    selected = records[(records["year"] == 2026) & (records["month"] == 3)]
    if selected.empty:
        return {
            "status": "observation_not_available_in_packaged_table",
            "used_for_tuning": True,
            "independent_predictive_validation": False,
        }
    row = selected.iloc[0]
    output: dict[str, Any] = {
        "status": "reported_after_prior_inspection_not_independent",
        "year": 2026,
        "month": 3,
        "model_extent_million_km2": float(row["model_extent"]),
        "observed_extent_million_km2": float(row["observed_extent"]),
        "extent_error_million_km2": float(
            row["model_extent"] - row["observed_extent"]
        ),
        "raw_nsidc_area_million_km2_excluded": float(
            row.get("observed_raw_area_excluded", float("nan"))
        ),
        "observation_source": str(row["observation_source"]),
        "used_for_tuning": True,
        "independent_predictive_validation": False,
    }
    if np.isfinite(float(row["observed_area"])):
        output.update(
            {
                "model_fixed_mask_area_million_km2": float(row["model_area"]),
                "observed_fixed_mask_area_million_km2": float(row["observed_area"]),
                "fixed_mask_area_error_million_km2": float(
                    row["model_area"] - row["observed_area"]
                ),
                # Backward-compatible generic area-error name for callers that
                # provide only a synthetic/native area column.
                "area_error_million_km2": float(
                    row["model_area"] - row["observed_area"]
                ),
            }
        )
    return output


MARCH_TREND_PERIODS: tuple[tuple[int, int], ...] = (
    (1988, 2020),
    (1990, 2020),
    (1988, 2015),
    (1990, 2015),
)


def march_extent_trend_robustness(records: pd.DataFrame) -> dict[str, Any]:
    """Evaluate March extent trends over predeclared same-product periods."""
    march = records[records["month"] == 3].copy()
    rows: list[dict[str, Any]] = []
    for start_year, end_year in MARCH_TREND_PERIODS:
        frame = march[march["year"].between(start_year, end_year)]
        years = frame["year"].to_numpy(dtype=float)
        model = frame["model_extent"].to_numpy(dtype=float)
        observed = frame["observed_extent"].to_numpy(dtype=float)
        finite = np.isfinite(model) & np.isfinite(observed)
        years = years[finite]
        model = model[finite]
        observed = observed[finite]
        model_trend = _trend_summary(years, model)
        observed_trend = _trend_summary(years, observed)
        model_slope = model_trend["ols_trend_million_km2_per_decade"]
        observed_slope = observed_trend["ols_trend_million_km2_per_decade"]
        ratio = float(abs(model_slope) / max(abs(observed_slope), 1.0e-12))
        rows.append(
            {
                "period": [start_year, end_year],
                "records": int(len(model)),
                "model": model_trend,
                "observed": observed_trend,
                "absolute_ols_error_million_km2_per_decade": float(
                    abs(model_slope - observed_slope)
                ),
                "trend_magnitude_ratio": ratio,
                "interannual_correlation": _safe_correlation(model, observed),
                "matching_decline_direction": bool(
                    model_slope < 0.0 and observed_slope < 0.0
                ),
            }
        )
    errors = np.asarray(
        [row["absolute_ols_error_million_km2_per_decade"] for row in rows],
        dtype=float,
    )
    direction_fraction = float(
        np.mean([row["matching_decline_direction"] for row in rows])
    )
    primary = rows[0]
    gates = {
        "primary_absolute_ols_error_le_0p20": (
            primary["absolute_ols_error_million_km2_per_decade"] <= 0.20
        ),
        "primary_trend_magnitude_ratio_between_0p40_and_1p60": (
            0.40 <= primary["trend_magnitude_ratio"] <= 1.60
        ),
        "median_period_absolute_ols_error_le_0p25": (
            float(np.median(errors)) <= 0.25
        ),
        "decline_direction_match_fraction_ge_0p75": direction_fraction >= 0.75,
    }
    return {
        "metric": "march_extent",
        "raw_march_area_trend_used_for_calibration": False,
        "raw_area_exclusion_reason": (
            "The packaged raw area series changes pole-hole masks across sensor "
            "eras and is excluded from all calibration and skill gates."
        ),
        "extent_observation_operator_calibrated": False,
        "extent_is_separate_prognostic_state": False,
        "extent_derived_from_native_concentration": True,
        "predeclared_periods": [list(period) for period in MARCH_TREND_PERIODS],
        "period_results": rows,
        "median_absolute_ols_error_million_km2_per_decade": float(
            np.median(errors)
        ),
        "maximum_absolute_ols_error_million_km2_per_decade": float(np.max(errors)),
        "decline_direction_match_fraction": direction_fraction,
        "gates": gates,
        "passed": bool(all(gates.values())),
        "scientifically_adequate_for_quantitative_temporal_use": False,
        "used_for_scientific_release_gate": False,
        "mandatory_limitation": (
            "Historical records were inspected during development and the model "
            "does not resolve satellite-scale spatial concentration. This coarse "
            "zonal 15% extent is diagnostic only, not independently validated "
            "prediction skill."
        ),
        "evidence_role": "tuning_informed_extent_diagnostic",
        "independent_predictive_validation": False,
    }


def march_area_trend_robustness(records: pd.DataFrame) -> dict[str, Any]:
    """Backward-compatible alias; raw March area is no longer trend-calibrated."""
    return march_extent_trend_robustness(records)


def _finite_le(value: Any, threshold: float) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return bool(np.isfinite(number) and number <= threshold)


def _finite_ge(value: Any, threshold: float) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return bool(np.isfinite(number) and number >= threshold)


def _fixed_mask_trend_magnitude_ratio(metric: dict[str, Any]) -> float:
    try:
        model = float(metric.get("model_trend_million_km2_per_decade"))
        observed = float(metric.get("observed_trend_million_km2_per_decade"))
    except (TypeError, ValueError):
        return float("nan")
    if not np.isfinite(model) or not np.isfinite(observed) or abs(observed) < 1.0e-12:
        return float("nan")
    return abs(model / observed)

def _trend_direction_matches(metric: dict[str, Any]) -> bool:
    try:
        model = float(metric.get("model_trend_million_km2_per_decade"))
        observed = float(metric.get("observed_trend_million_km2_per_decade"))
    except (TypeError, ValueError):
        return False
    return bool(np.isfinite(model) and np.isfinite(observed) and model * observed > 0.0)

def _trend_ratio_in_declared_range(metric: dict[str, Any]) -> bool:
    ratio = _fixed_mask_trend_magnitude_ratio(metric)
    return bool(np.isfinite(ratio) and MIN_FIXED_MASK_TREND_MAGNITUDE_RATIO <= ratio <= MAX_FIXED_MASK_TREND_MAGNITUDE_RATIO)


def _ols_trend_intervals_overlap(metric: dict[str, Any]) -> bool:
    """Require overlap of model and observed OLS 95% trend intervals."""

    model = metric.get("model_trend_diagnostics", {})
    observed = metric.get("observed_trend_diagnostics", {})
    try:
        model_low = float(model["ols_95pct_ci_low_million_km2_per_decade"])
        model_high = float(model["ols_95pct_ci_high_million_km2_per_decade"])
        observed_low = float(observed["ols_95pct_ci_low_million_km2_per_decade"])
        observed_high = float(observed["ols_95pct_ci_high_million_km2_per_decade"])
    except (KeyError, TypeError, ValueError):
        return False
    values = (model_low, model_high, observed_low, observed_high)
    return bool(
        all(np.isfinite(value) for value in values)
        and max(model_low, observed_low) <= min(model_high, observed_high)
    )


def calibration_passes(
    summary: dict[str, Any],
    march_trend_robustness: dict[str, Any],
    physical_validation: dict[str, Any] | None = None,
) -> tuple[bool, dict[str, bool]]:
    """Return scientific-development gates without using raw NSIDC area."""
    march = summary["months"]["3"]
    september = summary["months"]["9"]
    physical_validation = physical_validation or {}
    homogeneous_area = bool(march["area"].get("available") and september["area"].get("available"))
    physical_complete = bool(physical_validation.get("complete", False))
    physical_passed = bool(physical_validation.get("passed", False))
    gates = {
        "raw_nsidc_area_excluded_from_calibration": True,
        "extent_operator_contains_no_observational_fit": bool(
            not march_trend_robustness.get("extent_observation_operator_calibrated", True)
        ),
        "march_fixed_mask_area_rmse_le_1p00": _finite_le(march["area"].get("rmse_million_km2"), 1.00),
        "september_fixed_mask_area_rmse_le_1p00": _finite_le(september["area"].get("rmse_million_km2"), 1.00),
        "march_fixed_mask_area_trend_direction_matches": _trend_direction_matches(march["area"]),
        "september_fixed_mask_area_trend_direction_matches": _trend_direction_matches(september["area"]),
        "march_fixed_mask_area_trend_magnitude_ratio_in_range": _trend_ratio_in_declared_range(march["area"]),
        "september_fixed_mask_area_trend_magnitude_ratio_in_range": _trend_ratio_in_declared_range(september["area"]),
        "march_fixed_mask_area_ols_95pct_trend_intervals_overlap": _ols_trend_intervals_overlap(march["area"]),
        "september_fixed_mask_area_ols_95pct_trend_intervals_overlap": _ols_trend_intervals_overlap(september["area"]),
        "coarse_zonal_extent_excluded_from_scientific_release_gate": True,
        "homogeneous_fixed_mask_area_dataset_available": homogeneous_area,
        "piomas_and_both_satellite_thickness_sources_available": physical_complete,
        "source_separated_physical_constraints_pass": physical_passed,
        "march_exact_fixed_mask_operator_applied": bool(
            march.get("fixed_mask_model_operator_applied_for_all_scored_records", False)
        ),
        "september_exact_fixed_mask_operator_applied": bool(
            september.get("fixed_mask_model_operator_applied_for_all_scored_records", False)
        ),
    }
    return bool(all(gates.values())), gates

def development_evaluation_passes(
    summary: dict[str, Any],
) -> tuple[bool, dict[str, bool]]:
    march = summary["months"]["3"]
    september = summary["months"]["9"]
    gates = {
        "raw_nsidc_area_excluded_from_development_score": True,
        "coarse_zonal_extent_excluded_from_development_score": True,
        "march_homogeneous_fixed_mask_area_available": bool(
            march["area"].get("available")
        ),
        "september_homogeneous_fixed_mask_area_available": bool(
            september["area"].get("available")
        ),
        "march_fixed_mask_area_rmse_le_0p50": _finite_le(
            march["area"].get("rmse_million_km2"),
            RECENT_PERIOD_AREA_RMSE_LIMIT_MILLION_KM2,
        ),
        "september_fixed_mask_area_rmse_le_0p50": _finite_le(
            september["area"].get("rmse_million_km2"),
            RECENT_PERIOD_AREA_RMSE_LIMIT_MILLION_KM2,
        ),
        "march_exact_fixed_mask_operator_applied": bool(
            march.get("fixed_mask_model_operator_applied_for_all_scored_records", False)
        ),
        "september_exact_fixed_mask_operator_applied": bool(
            september.get("fixed_mask_model_operator_applied_for_all_scored_records", False)
        ),
    }
    return bool(all(gates.values())), gates


def _physical_metric_summary(
    records: pd.DataFrame, quantity: str, unit_label: str
) -> dict[str, Any]:
    model_name = f"model_{quantity}"
    observed_name = f"observed_{quantity}"
    if model_name not in records or observed_name not in records:
        return {"available": False, "records": 0, "unit": unit_label}
    model = records[model_name].to_numpy(dtype=float)
    observed = records[observed_name].to_numpy(dtype=float)
    finite = np.isfinite(model) & np.isfinite(observed)
    if np.count_nonzero(finite) < 2:
        return {"available": False, "records": 0, "unit": unit_label}
    model = model[finite]
    observed = observed[finite]
    error = model - observed
    rmse = float(np.sqrt(np.mean(error * error)))
    observed_mean_abs = float(np.mean(np.abs(observed)))
    return {
        "available": True,
        "records": int(np.count_nonzero(finite)),
        "unit": unit_label,
        "model_mean": float(np.mean(model)),
        "observed_mean": float(np.mean(observed)),
        "rmse": rmse,
        "normalized_rmse_fraction": (
            rmse / observed_mean_abs if observed_mean_abs > 1.0e-12 else float("nan")
        ),
        "mae": float(np.mean(np.abs(error))),
        "bias": float(np.mean(error)),
        "correlation": _safe_correlation(model, observed),
    }


def evaluate_physical_constraints(records: pd.DataFrame) -> dict[str, Any]:
    """Score PIOMAS, CryoSat-2 and ICESat-2 separately.

    PIOMAS is never treated as a satellite observation and the two satellite
    thickness products are never averaged into a synthetic target.
    """
    metadata = physical_observation_metadata()

    def pair_summary(model_column: str, observed_column: str, unit: str) -> dict[str, Any]:
        if model_column not in records.columns or observed_column not in records.columns:
            return {"available": False, "records": 0, "unit": unit}
        model = pd.to_numeric(records[model_column], errors="coerce").to_numpy(dtype=float)
        observed = pd.to_numeric(records[observed_column], errors="coerce").to_numpy(dtype=float)
        finite = np.isfinite(model) & np.isfinite(observed)
        if int(np.count_nonzero(finite)) < 2:
            return {"available": False, "records": int(np.count_nonzero(finite)), "unit": unit}
        model = model[finite]
        observed = observed[finite]
        error = model - observed
        rmse = float(np.sqrt(np.mean(error * error)))
        scale = float(np.mean(np.abs(observed)))
        return {
            "available": True,
            "records": int(len(model)),
            "unit": unit,
            "model_mean": float(np.mean(model)),
            "observed_mean": float(np.mean(observed)),
            "rmse": rmse,
            "normalized_rmse_fraction": rmse / scale if scale > 1.0e-12 else float("nan"),
            "mae": float(np.mean(np.abs(error))),
            "bias": float(np.mean(error)),
            "correlation": _safe_correlation(model, observed),
        }

    metrics = {
        "piomas_volume": pair_summary(
            "model_piomas_volume_million_km3",
            "observed_piomas_volume_million_km3",
            "million_km3",
        ),
        "cryosat2_mean_thickness": pair_summary(
            "model_cryosat2_mean_thickness_m",
            "observed_cryosat2_mean_thickness_m",
            "m",
        ),
        "icesat2_mean_thickness": pair_summary(
            "model_icesat2_mean_thickness_m",
            "observed_icesat2_mean_thickness_m",
            "m",
        ),
    }
    thresholds = {
        "piomas_volume": PHYSICAL_METRIC_THRESHOLDS["piomas_volume_normalized_rmse"],
        "cryosat2_mean_thickness": PHYSICAL_METRIC_THRESHOLDS["cryosat2_mean_thickness_normalized_rmse"],
        "icesat2_mean_thickness": PHYSICAL_METRIC_THRESHOLDS["icesat2_mean_thickness_normalized_rmse"],
    }
    normalized_rmse_gates = {
        f"{name}_normalized_rmse_le_{threshold:.2f}": bool(
            metric.get("available", False)
            and _finite_le(metric.get("normalized_rmse_fraction"), threshold)
        )
        for name, metric in metrics.items()
        for threshold in (thresholds[name],)
    }
    relative_bias_limits = {
        "piomas_volume": 0.10,
        "cryosat2_mean_thickness": 0.10,
        "icesat2_mean_thickness": 0.20,
    }
    bias_gates = {
        f"{name}_absolute_relative_mean_bias_le_{limit:.2f}": bool(
            metric.get("available", False)
            and np.isfinite(float(metric.get("bias", float("nan"))))
            and np.isfinite(float(metric.get("observed_mean", float("nan"))))
            and abs(float(metric["observed_mean"])) > 1.0e-12
            and abs(float(metric["bias"]) / float(metric["observed_mean"])) <= limit
        )
        for name, metric in metrics.items()
        for limit in (relative_bias_limits[name],)
    }
    gates = {**normalized_rmse_gates, **bias_gates}
    temporal_correlation_gates = {
        "piomas_volume_correlation_ge_0.80": _finite_ge(
            metrics["piomas_volume"].get("correlation"), 0.80
        ),
        "cryosat2_mean_thickness_correlation_ge_0.30": _finite_ge(
            metrics["cryosat2_mean_thickness"].get("correlation"), 0.30
        ),
        "icesat2_mean_thickness_correlation_ge_0.30": _finite_ge(
            metrics["icesat2_mean_thickness"].get("correlation"), 0.30
        ),
    }
    complete = bool(metadata.get("complete", False)) and all(
        metric.get("available", False) for metric in metrics.values()
    )
    passed = bool(complete and all(gates.values()))
    temporal_response_passed = bool(
        complete and all(temporal_correlation_gates.values())
    )
    return {
        "available": bool(metadata.get("available", False)),
        "complete": complete,
        "metadata": metadata,
        "metrics": metrics,
        "quality_gates": gates,
        "temporal_correlation_gates": temporal_correlation_gates,
        "mean_state_constraints_passed": passed,
        "temporal_response_validation_passed": temporal_response_passed,
        "temporal_correlation_is_release_blocking": False,
        "temporal_correlation_role": "retrospective_development_diagnostic",
        "passed": passed,
        "scientific_volume_thickness_validation_complete": bool(
            passed and temporal_response_passed
        ),
        "gate_note": (
            "PIOMAS volume and both satellite thickness products must pass "
            "predeclared normalized-RMSE and relative-mean-bias gates. Temporal "
            "correlations are retained as retrospective development diagnostics "
            "of exact annual phasing; they are not a release gate for the "
            "deterministic forced reduced model and do not establish independent "
            "prospective predictive skill."
        ),
    }


def evaluate_osi_saf_crosscheck(records: pd.DataFrame) -> dict[str, Any]:
    """Development-only fixed-mask area comparison against OSI SAF OSI-450-a1."""
    status = source_status("osi_saf_osi450a1_v3_1")
    if not status.get("available", False):
        return {"available": False, "passed": False, "source": status, "months": {}}
    months: dict[str, Any] = {}
    month_passes = []
    for month in (3, 9):
        observed = load_osi_saf_month(month)
        if observed is None:
            months[str(month)] = {"available": False}
            month_passes.append(False)
            continue
        model = records[records["month"] == month][
            ["year", "model_osi_saf_fixed_mask_area_million_km2"]
        ].rename(columns={"model_osi_saf_fixed_mask_area_million_km2": "model_area"})
        merged = model.merge(observed[["year", "area"]], on="year", how="inner")
        if len(merged) < 2:
            months[str(month)] = {"available": False, "records": int(len(merged))}
            month_passes.append(False)
            continue
        error = merged["model_area"].to_numpy(float) - merged["area"].to_numpy(float)
        rmse = float(np.sqrt(np.mean(error * error)))
        months[str(month)] = {
            "available": True,
            "records": int(len(merged)),
            "rmse_million_km2": rmse,
            "bias_million_km2": float(np.mean(error)),
            "correlation": _safe_correlation(
                merged["model_area"].to_numpy(float), merged["area"].to_numpy(float)
            ),
            "rmse_le_1p00_million_km2": rmse <= 1.0,
        }
        month_passes.append(rmse <= 1.0)
    return {
        "available": True,
        "source": status,
        "used_for_calibration": False,
        "independent_crosscheck": False,
        "used_during_method_development": True,
        "evidence_role": "cross_dataset_development_diagnostic_not_independent_validation",
        "months": months,
        "passed": bool(month_passes and all(month_passes)),
    }


def evaluate_ice_age_structure(records: pd.DataFrame) -> dict[str, Any]:
    """Compare model >2 m ice fraction with observed multiyear-ice fraction.

    These are not identical physical quantities, so this is deliberately a
    structural diagnostic and not a numerical release gate.
    """
    status = source_status("nsidc_0611_v4")
    observed = load_ice_age_annual()
    if observed is None:
        return {"available": False, "source": status, "used_for_calibration": False}
    model = records[["year", "month", "model_thick_ice_area_fraction"]].copy()
    merged = model.merge(observed, on=["year", "month"], how="inner")
    if len(merged) < 2:
        return {
            "available": False,
            "source": status,
            "records": int(len(merged)),
            "used_for_calibration": False,
        }
    m = merged["model_thick_ice_area_fraction"].to_numpy(float)
    o = merged["multiyear_ice_fraction_of_ice"].to_numpy(float)
    finite = np.isfinite(m) & np.isfinite(o)
    m, o = m[finite], o[finite]
    return {
        "available": len(m) >= 2,
        "source": status,
        "records": int(len(m)),
        "used_for_calibration": False,
        "direct_metric_equivalence_claimed": False,
        "model_metric": "fraction of prognostic ice area with local thickness >=2 m",
        "observed_metric": "fraction of observed ice classified as multiyear by NSIDC-0611 v4",
        "correlation": _safe_correlation(m, o) if len(m) >= 2 else float("nan"),
        "mean_difference_fraction": float(np.mean(m - o)) if len(m) else float("nan"),
        "interpretation": (
            "Structural consistency diagnostic only; sea-ice age and >2 m thickness are related but not identical."
        ),
    }

def _dataset_metadata_with_integrity() -> dict[str, Any]:
    metadata = json.loads((NSIDC_DIR / "METADATA.json").read_text(encoding="utf-8"))
    actual_hashes = {
        f"N_{month:02d}_extent_v4.0.csv": sha256_file(
            NSIDC_DIR / f"N_{month:02d}_extent_v4.0.csv"
        )
        for month in (3, 9)
    }
    expected_hashes = metadata.get("packaged_file_sha256", {})
    metadata["actual_packaged_file_sha256"] = actual_hashes
    metadata["packaged_file_hashes_match"] = bool(
        expected_hashes
        and all(
            expected_hashes.get(name) == value
            for name, value in actual_hashes.items()
        )
    )
    metadata["raw_area_used_for_calibration"] = False
    metadata["raw_area_used_for_skill_claim"] = False
    metadata["raw_area_status"] = "provenance_only_excluded_due_to_pole_hole_discontinuity"
    return metadata


def retrospective_fold_local_hindcast_requirements() -> dict[str, Any]:
    """Return packaged retrospective fold-local development evidence, fail-closed."""
    manifest_path = ROOT / "RETROSPECTIVE_FOLD_LOCAL_ARCTIC_HINDCAST_V2_29_28.json"
    minimum_baselines = [
        "persistence",
        "expanding_linear_trend",
        "temperature_driven_regression",
        "autoregressive_model",
    ]
    fallback = {
        "required": True,
        "status": "missing_retrospective_fold_local_manifest",
        "manifest": manifest_path.name,
        "minimum_baselines": minimum_baselines,
        "all_folds_scored": False,
        "all_folds_have_minimum_baselines": False,
        "fold_local_candidate_selection_required": True,
        "fold_local_candidate_selection_used": False,
        "model_recalibration_required_inside_each_fold": True,
        "full_continuous_recalibration_required_for_nested_validation_claim": True,
        "full_continuous_recalibration_used": False,
        "retrospective_development_validation": True,
        "scientific_predictive_skill_claim_allowed": False,
    }
    if not manifest_path.is_file():
        return fallback
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback
    return {
        "required": True,
        "status": str(manifest.get("status", "invalid_retrospective_fold_local_manifest")),
        "manifest": manifest_path.name,
        "minimum_baselines": list(manifest.get("minimum_baselines", minimum_baselines)),
        "all_folds_scored": bool(manifest.get("all_folds_scored", False)),
        "all_folds_have_minimum_baselines": bool(manifest.get("all_folds_have_minimum_baselines", False)),
        "fold_local_candidate_selection_required": True,
        "fold_local_candidate_selection_used": bool(manifest.get("fold_local_candidate_selection_from_predeclared_prior_grid", False)),
        "model_recalibration_required_inside_each_fold": True,
        "full_continuous_recalibration_required_for_nested_validation_claim": True,
        "full_continuous_recalibration_used": bool(manifest.get("full_continuous_recalibration_inside_each_fold", False)),
        "retrospective_development_validation": True,
        "scientific_predictive_skill_claim_allowed": bool(manifest.get("scientific_predictive_skill_claim_allowed", False)),
    }


def nested_hindcast_requirements() -> dict[str, Any]:
    """Compatibility alias; the release no longer calls this independent nested validation."""
    return retrospective_fold_local_hindcast_requirements()


def evaluate_result(result: Any) -> dict[str, Any]:
    """Return conservative native-state and six-source scientific diagnostics."""
    records = model_monthly_records(result, range(1979, 2027))
    development_1979_2020 = evaluate_period(records, CALIBRATION)
    development_2021_2025 = evaluate_period(records, DEVELOPMENT_EVALUATION)
    march_trend = march_extent_trend_robustness(records)
    physical_validation = evaluate_physical_constraints(records)
    calibration_passed, calibration_gates = calibration_passes(
        development_1979_2020, march_trend, physical_validation
    )
    development_passed, development_gates = development_evaluation_passes(
        development_2021_2025
    )
    rolling = rolling_origin_evaluation(records[records["year"] <= 2025])
    enhanced = enhanced_historical_evaluation(records[records["year"] <= 2025])
    march_2026 = inspected_march_2026_evaluation(records)
    metadata = _dataset_metadata_with_integrity()
    fixed_mask_metadata = homogeneous_area_metadata()
    retrospective = retrospective_fold_local_hindcast_requirements()
    stack = validation_stack_status()
    osi_development = evaluate_osi_saf_crosscheck(records)
    ice_age = evaluate_ice_age_structure(records)

    engineering_gates = {
        "packaged_nsidc_files_match_hashes": bool(metadata.get("packaged_file_hashes_match", False)),
        "raw_nsidc_area_excluded_from_scientific_targets": True,
        "extent_operator_unfitted": True,
        "fixed_mask_area_operator_enforced_when_target_available": True,
        "source_specific_physical_observation_operators_enforced": True,
    }
    engineering_passed = bool(all(engineering_gates.values()))
    observational_stack_complete = bool(
        stack.get("all_six_observational_products_available", False)
        and calibration_passed
        and ice_age.get("available", False)
    )
    prospective_evidence_path = ROOT / "validation" / "prospective" / "R16_PROSPECTIVE_EVIDENCE.json"
    prospective = evaluate_r16_prospective(
        prospective_evidence_path if prospective_evidence_path.exists() else None
    )
    prospective_untouched_validation_complete = bool(
        prospective.get("independent_predictive_scientific_validation_complete", False)
    )
    independent_predictive_scientific_validation_status = str(
        prospective.get("independent_predictive_scientific_validation_status", "not_available")
    )
    scientific_validation_complete = bool(
        observational_stack_complete
        and retrospective.get("scientific_predictive_skill_claim_allowed", False)
        and prospective_untouched_validation_complete
    )

    return {
        "dataset_metadata": metadata,
        "arctic_validation_stack": stack,
        "all_six_observational_products_available": bool(
            stack.get("all_six_observational_products_available", False)
        ),
        "homogeneous_fixed_mask_area_metadata": fixed_mask_metadata,
        "physical_volume_thickness_validation": physical_validation,
        "osi_saf_development_crosscheck": osi_development,
        "ice_age_structural_diagnostic": ice_age,
        "observational_stack_complete": observational_stack_complete,
        "prospective_untouched_validation_complete": prospective_untouched_validation_complete,
        "independent_predictive_scientific_validation_status": independent_predictive_scientific_validation_status,
        "prospective_validation_evidence": prospective,
        "area_operator": {
            "mapping": "native EGCM concentration sampled on exact observation cell centers",
            "spatial_support_file": "data/validation/sea_ice_fixed_mask/MODEL_OBSERVATION_OPERATOR.npz",
            "concentration_threshold": 0.15,
            "zero_preserving": True,
            "continuous_below_threshold": True,
            "monotone": True,
            "warming_dependent": False,
            "statistical_area_correction": False,
            "extent_method": "conservative_unfitted_meridional_subgrid_15pct_threshold",
            "extent_observation_operator_calibrated": False,
            "extent_is_separate_prognostic_state": False,
            "extent_derived_from_native_concentration": True,
            "extent_uses_raw_nsidc_area": False,
            "extent_from_native_prognostic_concentration": True,
            "extent_independently_prognostic_spatial_field": False,
            "extent_interpretation": (
                "Extent is a deterministic conservative subgrid threshold diagnostic derived from the native two-sector prognostic concentration. "
                "It preserves native area, permits fractional within-band occupancy, and contains no fitted historical area-to-extent multiplier."
            ),
        },
        "calibration": development_1979_2020,
        "calibration_gates": calibration_gates,
        "calibration_passed": calibration_passed,
        "calibration_interpretation": (
            "Scientific calibration requires homogeneous G02202 fixed-mask area, PIOMAS volume, "
            "and separate CryoSat-2/ICESat-2 thickness checks. Missing observations fail closed."
        ),
        "march_extent_trend_robustness": march_trend,
        "march_native_area_trend_robustness": {
            "status": "raw_nsidc_area_excluded",
            "reason": march_trend["raw_area_exclusion_reason"],
        },
        "validation_informed_development_evaluation": development_2021_2025,
        "validation_informed_development_evaluation_gates": development_gates,
        "validation_informed_development_evaluation_passed": development_passed,
        "rolling_origin_historical_evaluation": rolling,
        "enhanced_historical_evaluation": enhanced,
        "retrospective_fold_local_hindcast_evaluation": retrospective,
        "inspected_march_2026_evaluation": march_2026,
        "quantitative_temporal_skill_claim": {
            "claimed": False,
            "reason": (
                "Retrospective fold-local method-development checks do not establish independent predictive skill, and the prospective untouched period has not yet been evaluated."
            ),
        },
        "prospective_untouched_temporal_evaluation": {
            "start_year": PROSPECTIVE_UNTOUCHED_START_YEAR,
            "status": "reserved_not_yet_available",
            "used_for_tuning": False,
            "independent_predictive_validation": True,
            "reason": (
                "Records through 2025 and March 2026 were already inspected. Prospective skill must remain a separate product-era evaluation."
            ),
        },
        "engineering_gates": engineering_gates,
        "all_current_sea_ice_engineering_gates_passed": engineering_passed,
        "all_current_sea_ice_development_checks_passed": development_passed,
        "scientific_validation_complete": scientific_validation_complete,
        # Backwards-compatible diagnostic field. Historical temporal scores are
        # explicitly non-release-blocking and do not establish prospective skill.
        "scientific_temporal_skill_gate_passed": False,
        "all_current_sea_ice_release_gates_passed": scientific_validation_complete,
        "historical_scores_are_release_blocking": False,
        "extent_metrics_are_release_blocking": False,
        "records": records.to_dict(orient="records"),
    }
