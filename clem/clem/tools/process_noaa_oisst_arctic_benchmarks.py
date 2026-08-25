#!/usr/bin/env python3
"""Reproduce NOAA OISST Arctic open-water benchmark statistics.

The processor reads NOAA OISST v2 monthly 1991-2020 climatological sea-surface
temperature and ice concentration, applies the *same smooth fractional
Atlantic basin mask used by the model*, and computes open-water-weighted means
north of 66 N. Every source file and the model mask implementation are hashed.

The output is an observational summary. It does not alter release bounds.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SST_URL = (
    "https://downloads.psl.noaa.gov/Datasets/noaa.oisst.v2/"
    "sst.ltm.1991-2020.nc"
)
DEFAULT_ICE_URL = (
    "https://downloads.psl.noaa.gov/Datasets/noaa.oisst.v2/"
    "icec.ltm.1991-2020.nc"
)


def source_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _coord_name(dataset: Any, names: tuple[str, ...]) -> str:
    for name in names:
        if name in dataset.coords or name in dataset.variables:
            return name
    raise KeyError(f"None of the coordinate names are present: {names}")


def _variable_name(dataset: Any, names: tuple[str, ...]) -> str:
    for name in names:
        if name in dataset.data_vars:
            return name
    raise KeyError(f"None of the variable names are present: {names}")


def _month_numbers(data_array: Any, time_name: str) -> np.ndarray:
    try:
        return np.asarray(data_array[time_name].dt.month, dtype=int)
    except Exception:
        count = int(data_array.sizes[time_name])
        if count != 12:
            raise ValueError("Climatology must contain 12 monthly records")
        return np.arange(1, 13, dtype=int)


def _model_sector_fractions(
    longitude_2d_deg_east: np.ndarray,
    latitude_2d: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Return the model's smooth Atlantic/non-Atlantic Arctic fractions."""
    from climate_model import _atlantic_basin_fraction

    longitude_signed = (
        (np.asarray(longitude_2d_deg_east, dtype=float) + 180.0) % 360.0
    ) - 180.0
    arctic = np.asarray(latitude_2d, dtype=float) >= 66.0
    atlantic_fraction = _atlantic_basin_fraction(
        longitude_signed,
        latitude_2d,
        np.ones_like(latitude_2d, dtype=float),
    )
    atlantic_fraction = np.where(
        arctic, np.clip(atlantic_fraction, 0.0, 1.0), 0.0
    )
    non_atlantic_fraction = np.where(
        arctic, np.clip(1.0 - atlantic_fraction, 0.0, 1.0), 0.0
    )
    return atlantic_fraction, non_atlantic_fraction


def _weighted_open_water_mean(
    temperature: np.ndarray,
    ice_concentration: np.ndarray,
    latitude_2d: np.ndarray,
    sector_fraction: np.ndarray,
) -> tuple[float, float, float]:
    ice = np.asarray(ice_concentration, dtype=float)
    if np.nanmax(ice) > 1.5:
        ice = ice / 100.0
    open_water_fraction = np.clip(1.0 - ice, 0.0, 1.0)
    area_weight = np.cos(np.deg2rad(latitude_2d))
    sector = np.clip(np.asarray(sector_fraction, dtype=float), 0.0, 1.0)
    base_weights = area_weight * sector
    weights = base_weights * open_water_fraction
    valid = np.isfinite(temperature) & np.isfinite(weights) & (weights > 0.0)
    if not np.any(valid):
        raise ValueError("No valid open-water cells remain after masking")
    mean = float(np.sum(temperature[valid] * weights[valid]) / np.sum(weights[valid]))
    sector_valid = np.isfinite(open_water_fraction) & (base_weights > 0.0)
    open_fraction = float(
        np.sum(open_water_fraction[sector_valid] * base_weights[sector_valid])
        / np.sum(base_weights[sector_valid])
    )
    sector_weight = float(np.sum(base_weights[sector_valid]))
    return mean, open_fraction, sector_weight


def process(
    sst_path: Path,
    ice_path: Path,
    *,
    model_source_path: Path = ROOT / "climate_model.py",
) -> dict[str, Any]:
    try:
        import xarray as xr
    except ImportError as exc:
        raise SystemExit("xarray is required to process NOAA OISST files") from exc

    with xr.open_dataset(sst_path, decode_times=True) as sst_ds, xr.open_dataset(
        ice_path, decode_times=True
    ) as ice_ds:
        lat_name = _coord_name(sst_ds, ("lat", "latitude"))
        lon_name = _coord_name(sst_ds, ("lon", "longitude"))
        time_name = _coord_name(sst_ds, ("time",))
        sst_name = _variable_name(sst_ds, ("sst", "sea_surface_temperature"))
        ice_name = _variable_name(
            ice_ds, ("icec", "ice", "sea_ice_concentration")
        )

        sst = sst_ds[sst_name].squeeze(drop=True)
        ice = ice_ds[ice_name].squeeze(drop=True)
        ice_lat_name = _coord_name(ice_ds, ("lat", "latitude"))
        ice_lon_name = _coord_name(ice_ds, ("lon", "longitude"))
        if ice_lat_name != lat_name or ice_lon_name != lon_name:
            ice = ice.rename({ice_lat_name: lat_name, ice_lon_name: lon_name})
        ice = ice.interp(
            {lat_name: sst[lat_name], lon_name: sst[lon_name]}, method="nearest"
        )

        latitude = np.asarray(sst[lat_name], dtype=float)
        longitude = np.mod(np.asarray(sst[lon_name], dtype=float), 360.0)
        lon2d, lat2d = np.meshgrid(longitude, latitude)
        atlantic, non_atlantic = _model_sector_fractions(lon2d, lat2d)
        months = _month_numbers(sst, time_name)

        monthly: dict[str, dict[str, dict[str, float]]] = {}
        for month in (6, 7, 8, 9):
            indices = np.flatnonzero(months == month)
            if indices.size != 1:
                raise ValueError(
                    f"Expected one climatological record for month {month}"
                )
            idx = int(indices[0])
            temperature = np.asarray(sst.isel({time_name: idx}), dtype=float)
            ice_concentration = np.asarray(
                ice.isel({time_name: idx}), dtype=float
            )
            monthly[str(month)] = {}
            for name, sector in (
                ("atlantic", atlantic),
                ("non_atlantic", non_atlantic),
            ):
                mean, open_fraction, sector_weight = _weighted_open_water_mean(
                    temperature, ice_concentration, lat2d, sector
                )
                monthly[str(month)][name] = {
                    "open_water_temperature_c": mean,
                    "open_water_fraction": open_fraction,
                    "cosine_latitude_sector_weight": sector_weight,
                }

    def mean_months(sector: str, selected: tuple[int, ...]) -> float:
        return float(
            np.mean(
                [
                    monthly[str(month)][sector]["open_water_temperature_c"]
                    for month in selected
                ]
            )
        )

    arctic_area_weight = np.where(
        lat2d >= 66.0, np.cos(np.deg2rad(lat2d)), 0.0
    )
    total_arctic_weight = float(np.sum(arctic_area_weight))
    atlantic_weight = float(np.sum(arctic_area_weight * atlantic))
    non_atlantic_weight = float(np.sum(arctic_area_weight * non_atlantic))
    return {
        "schema_version": "2.0",
        "method": {
            "latitude_min_deg_n": 66.0,
            "sector_mask": (
                "smooth fractional _atlantic_basin_fraction from climate_model.py; "
                "non-Atlantic is the complementary Arctic ocean fraction"
            ),
            "weights": (
                "cos(latitude) multiplied by model sector fraction and OISST "
                "open_water_fraction"
            ),
            "jja_months": [6, 7, 8],
            "september_month": 9,
            "atlantic_fraction_of_arctic_weight": (
                atlantic_weight / max(total_arctic_weight, 1.0e-12)
            ),
            "non_atlantic_fraction_of_arctic_weight": (
                non_atlantic_weight / max(total_arctic_weight, 1.0e-12)
            ),
        },
        "source_files": {
            "sst": {
                "path": str(sst_path),
                "source_url": DEFAULT_SST_URL,
                "source_sha256": source_sha256(sst_path),
            },
            "ice_concentration": {
                "path": str(ice_path),
                "source_url": DEFAULT_ICE_URL,
                "source_sha256": source_sha256(ice_path),
            },
            "model_sector_mask_source": {
                "path": str(model_source_path),
                "source_sha256": source_sha256(model_source_path),
            },
        },
        "monthly": monthly,
        "summary": {
            "atlantic_jja_mean_c": mean_months("atlantic", (6, 7, 8)),
            "non_atlantic_jja_mean_c": mean_months(
                "non_atlantic", (6, 7, 8)
            ),
            "atlantic_september_mean_c": mean_months("atlantic", (9,)),
            "non_atlantic_september_mean_c": mean_months(
                "non_atlantic", (9,)
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sst", type=Path, required=True, help=f"Local copy of {DEFAULT_SST_URL}"
    )
    parser.add_argument(
        "--ice", type=Path, required=True, help=f"Local copy of {DEFAULT_ICE_URL}"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--model-source", type=Path, default=ROOT / "climate_model.py"
    )
    args = parser.parse_args()
    result = process(
        args.sst,
        args.ice,
        model_source_path=args.model_source,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(args.output)


if __name__ == "__main__":
    main()
