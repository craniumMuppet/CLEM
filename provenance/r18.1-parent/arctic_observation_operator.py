"""Spatial observation operators for Arctic sea-ice validation.

The validation products and EGCM live on different grids.  Scientific scores
therefore must be formed by projecting EGCM's native fields onto the exact
observation support used to construct each processed target.  This module owns
that projection contract; it contains no fitted sea-ice coefficients.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy.spatial import cKDTree


@dataclass(frozen=True)
class SpatialOperator:
    source_id: str
    latitude_deg: np.ndarray
    longitude_deg: np.ndarray
    cell_area_km2: np.ndarray

    @property
    def point_count(self) -> int:
        return int(self.latitude_deg.size)

    @property
    def area_million_km2(self) -> float:
        return float(np.sum(self.cell_area_km2) / 1.0e6)


@dataclass(frozen=True)
class TemporalThicknessOperator:
    source_id: str
    latitude_deg: np.ndarray
    longitude_deg: np.ndarray
    cell_area_km2: np.ndarray
    years: np.ndarray
    months: np.ndarray
    observation_weight_km2: np.ndarray

    def weight_for(self, year: int, month: int) -> np.ndarray | None:
        matches = np.where((self.years == int(year)) & (self.months == int(month)))[0]
        if matches.size != 1:
            return None
        return np.asarray(self.observation_weight_km2[int(matches[0])], dtype=float)


@dataclass(frozen=True)
class ModelGridSampler:
    flat_indices: np.ndarray
    angular_distance_deg: np.ndarray
    field_shape: tuple[int, ...]

    def sample(self, field: np.ndarray) -> np.ndarray:
        array = np.asarray(field, dtype=float)
        if tuple(array.shape) != self.field_shape:
            raise ValueError(
                f"Model field shape {array.shape} does not match sampler grid {self.field_shape}"
            )
        return array.ravel()[self.flat_indices]


def _clean_operator_arrays(
    latitude_deg: np.ndarray,
    longitude_deg: np.ndarray,
    cell_area_km2: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    lat = np.asarray(latitude_deg, dtype=float).ravel()
    lon = np.asarray(longitude_deg, dtype=float).ravel()
    area = np.asarray(cell_area_km2, dtype=float).ravel()
    if not (lat.size == lon.size == area.size):
        raise ValueError("Observation operator latitude/longitude/area arrays must have equal size")
    valid = (
        np.isfinite(lat)
        & np.isfinite(lon)
        & np.isfinite(area)
        & (lat >= -90.0)
        & (lat <= 90.0)
        & (area > 0.0)
    )
    lat = lat[valid]
    lon = ((lon[valid] + 180.0) % 360.0) - 180.0
    area = area[valid]
    if lat.size == 0:
        raise ValueError("Observation operator contains no valid cells")
    return lat, lon, area


def save_spatial_operator(
    path: Path,
    *,
    source_id: str,
    latitude_deg: np.ndarray,
    longitude_deg: np.ndarray,
    cell_area_km2: np.ndarray,
) -> Path:
    lat, lon, area = _clean_operator_arrays(latitude_deg, longitude_deg, cell_area_km2)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        schema_version=np.asarray([1], dtype=np.int16),
        source_id=np.asarray([str(source_id)]),
        latitude_deg=lat,
        longitude_deg=lon,
        cell_area_km2=area,
    )
    return path


def load_spatial_operator(path: Path) -> SpatialOperator:
    with np.load(path, allow_pickle=False) as payload:
        source = str(np.asarray(payload["source_id"]).ravel()[0])
        lat, lon, area = _clean_operator_arrays(
            payload["latitude_deg"], payload["longitude_deg"], payload["cell_area_km2"]
        )
    return SpatialOperator(source, lat, lon, area)


def save_temporal_thickness_operator(
    path: Path,
    *,
    source_id: str,
    latitude_deg: np.ndarray,
    longitude_deg: np.ndarray,
    cell_area_km2: np.ndarray,
    years: np.ndarray,
    months: np.ndarray,
    observation_weight_km2: np.ndarray,
) -> Path:
    lat, lon, area = _clean_operator_arrays(latitude_deg, longitude_deg, cell_area_km2)
    years_array = np.asarray(years, dtype=np.int32).ravel()
    months_array = np.asarray(months, dtype=np.int8).ravel()
    weights = np.asarray(observation_weight_km2, dtype=float)
    if weights.ndim != 2:
        raise ValueError("Temporal thickness weights must be [record, cell]")
    if weights.shape != (years_array.size, lat.size):
        raise ValueError(
            f"Thickness weight shape {weights.shape} does not match records/cells "
            f"({years_array.size}, {lat.size})"
        )
    if months_array.size != years_array.size:
        raise ValueError("Temporal thickness years/months lengths differ")
    weights = np.where(np.isfinite(weights) & (weights > 0.0), weights, 0.0)
    if np.any(np.sum(weights, axis=1) <= 0.0):
        raise ValueError("Every temporal thickness record must have positive observation weight")
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        schema_version=np.asarray([1], dtype=np.int16),
        source_id=np.asarray([str(source_id)]),
        latitude_deg=lat,
        longitude_deg=lon,
        cell_area_km2=area,
        years=years_array,
        months=months_array,
        observation_weight_km2=weights,
    )
    return path


def load_temporal_thickness_operator(path: Path) -> TemporalThicknessOperator:
    with np.load(path, allow_pickle=False) as payload:
        source = str(np.asarray(payload["source_id"]).ravel()[0])
        lat, lon, area = _clean_operator_arrays(
            payload["latitude_deg"], payload["longitude_deg"], payload["cell_area_km2"]
        )
        years = np.asarray(payload["years"], dtype=np.int32).ravel()
        months = np.asarray(payload["months"], dtype=np.int8).ravel()
        weights = np.asarray(payload["observation_weight_km2"], dtype=float)
    if weights.shape != (years.size, lat.size):
        raise ValueError(f"Invalid temporal thickness operator shape in {path}")
    return TemporalThicknessOperator(source, lat, lon, area, years, months, weights)


def _unit_vectors(latitude_deg: np.ndarray, longitude_deg: np.ndarray) -> np.ndarray:
    lat = np.deg2rad(np.asarray(latitude_deg, dtype=float).ravel())
    lon = np.deg2rad(np.asarray(longitude_deg, dtype=float).ravel())
    cos_lat = np.cos(lat)
    return np.column_stack((cos_lat * np.cos(lon), cos_lat * np.sin(lon), np.sin(lat)))


def prepare_model_grid_sampler(
    result: Any,
    latitude_deg: np.ndarray,
    longitude_deg: np.ndarray,
) -> ModelGridSampler:
    """Map observation cell centers to the nearest EGCM ocean grid cell."""
    if not hasattr(result, "grid"):
        raise AttributeError("Result has no grid; spatial observation operators cannot be applied")
    grid = result.grid
    lat2d = np.asarray(grid.lat2d, dtype=float)
    lon2d = np.asarray(grid.lon2d, dtype=float)
    ocean = np.asarray(grid.ocean_fraction_map, dtype=float)
    if lat2d.shape != lon2d.shape or lat2d.shape != ocean.shape:
        raise ValueError("EGCM grid latitude/longitude/ocean arrays have incompatible shapes")
    candidate = np.isfinite(lat2d) & np.isfinite(lon2d) & (ocean > 1.0e-12)
    if not np.any(candidate):
        raise ValueError("EGCM grid contains no ocean cells")
    flat_candidate = np.flatnonzero(candidate.ravel())
    tree = cKDTree(_unit_vectors(lat2d.ravel()[flat_candidate], lon2d.ravel()[flat_candidate]))
    chord, nearest = tree.query(_unit_vectors(latitude_deg, longitude_deg), k=1)
    flat_indices = flat_candidate[np.asarray(nearest, dtype=int)]
    chord = np.clip(np.asarray(chord, dtype=float), 0.0, 2.0)
    angle_deg = np.rad2deg(2.0 * np.arcsin(0.5 * chord))
    return ModelGridSampler(flat_indices, angle_deg, tuple(lat2d.shape))


def model_fixed_mask_area_extent(
    result: Any,
    index: int,
    operator: SpatialOperator,
    sampler: ModelGridSampler,
    *,
    concentration_threshold: float = 0.15,
) -> dict[str, float | int | str]:
    """Project model ice area/extent onto an observation fixed mask.

    R18 uses the prognostic/fractional 15% occupancy map when the result
    provides one. This is essential for a coarse model: applying a hard 15%
    threshold to the native cell-mean concentration discards the independent
    support geometry and recreates the old whole-cell extent artifact.

    Older results without an occupancy map retain the legacy thresholded
    concentration path for backwards compatibility.
    """
    concentration = sampler.sample(result.sea_ice_concentration_map_at_index(index))
    concentration = np.clip(np.nan_to_num(concentration, nan=0.0), 0.0, 1.0)
    occupancy_method = "legacy_native_concentration_threshold"
    if hasattr(result, "sea_ice_extent_occupancy_map_at_index"):
        occupancy = sampler.sample(result.sea_ice_extent_occupancy_map_at_index(index))
        occupancy = np.clip(np.nan_to_num(occupancy, nan=0.0), 0.0, 1.0)
        # Native concentration is the cell-mean ice area fraction. Fractional
        # occupancy is the subgrid fraction at >=15% SIC. The support-state
        # consistency constraint guarantees concentration <= occupancy and an
        # implied concentration >=15% wherever occupancy is nonzero.
        area = float(np.sum(concentration * operator.cell_area_km2) / 1.0e6)
        extent = float(np.sum(occupancy * operator.cell_area_km2) / 1.0e6)
        occupancy_method = "fractional_15pct_support_occupancy"
    else:
        selected = concentration >= float(concentration_threshold)
        area = float(
            np.sum(np.where(selected, concentration * operator.cell_area_km2, 0.0))
            / 1.0e6
        )
        extent = float(
            np.sum(np.where(selected, operator.cell_area_km2, 0.0)) / 1.0e6
        )
    return {
        "area_million_km2": area,
        "extent_million_km2": extent,
        "operator_cell_count": operator.point_count,
        "operator_area_million_km2": operator.area_million_km2,
        "maximum_mapping_distance_deg": float(np.max(sampler.angular_distance_deg)),
        "extent_operator_method": occupancy_method,
    }


def model_equivalent_ice_thickness_map(result: Any, index: int) -> np.ndarray:
    """Return concentration times local ice thickness, i.e. volume per ocean area."""
    concentration = np.asarray(result.sea_ice_concentration_map_at_index(index), dtype=float)
    local = np.asarray(result.arctic_local_ice_thickness_map_at_index(index), dtype=float)
    if concentration.shape != local.shape:
        raise ValueError("Concentration and local-thickness maps have different shapes")
    local = np.nan_to_num(local, nan=0.0, posinf=0.0, neginf=0.0)
    return np.clip(concentration, 0.0, 1.0) * np.maximum(local, 0.0)


def model_volume_on_operator(
    result: Any,
    index: int,
    operator: SpatialOperator,
    sampler: ModelGridSampler,
) -> float:
    equivalent_thickness = sampler.sample(model_equivalent_ice_thickness_map(result, index))
    equivalent_thickness = np.nan_to_num(equivalent_thickness, nan=0.0, posinf=0.0, neginf=0.0)
    # m * km2 -> 1e6 m3; one million km3 = 1e15 m3, hence 1e-9.
    return float(np.sum(equivalent_thickness * operator.cell_area_km2) * 1.0e-9)


def model_mean_thickness_on_temporal_operator(
    result: Any,
    index: int,
    operator: TemporalThicknessOperator,
    sampler: ModelGridSampler,
    *,
    year: int,
    month: int,
) -> float:
    weight = operator.weight_for(year, month)
    if weight is None:
        return float("nan")
    local = sampler.sample(result.arctic_local_ice_thickness_map_at_index(index))
    local = np.nan_to_num(local, nan=0.0, posinf=0.0, neginf=0.0)
    total = float(np.sum(weight))
    if total <= 0.0:
        return float("nan")
    return float(np.sum(np.maximum(local, 0.0) * weight) / total)
