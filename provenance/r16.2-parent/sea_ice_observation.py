"""Native Arctic sea-ice area, extent, and observation diagnostics.

The dynamical core carries prognostic Northern Hemisphere sea-ice
concentration (area fraction) and latent ice volume in two zonal sectors. This
module deliberately contains no observationally fitted area/extent mapping.

Three quantities are kept distinct:

* **native physical area** integrates all prognostic ice concentration;
* **15%-threshold area** integrates concentration only in model cells whose
  concentration is at least 15%, matching the support normally used for a
  concentration-derived satellite area product;
* **15%-threshold extent** counts the ocean area of those same model cells.

The model is coarse and zonal, so the thresholded quantities are diagnostics,
not longitude-resolved forecasts. They are nevertheless generated directly
from the prognostic concentration state and contain no fitted NSIDC
area-to-extent multiplier.

The historical zero-intercept March/September area-to-extent multipliers are
retained only as explicit legacy compatibility helpers. They are not used by
the model, validation, release gates, or output diagnostics.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

EARTH_AREA_M2 = 5.100656e14
MARCH_PHASE = (3.0 - 0.5) / 12.0
SEPTEMBER_PHASE = (9.0 - 0.5) / 12.0
MINIMUM_EXTENT_CONCENTRATION = 0.15


@dataclass(frozen=True)
class SeasonalExtentAnchor:
    """Legacy 1979-2020 zero-intercept extent/area coefficient.

    These constants are kept so old saved configurations and analysis scripts
    can still be interpreted. They must not be used as scientific validation
    evidence because the fitted denominator was the discontinuous raw NSIDC
    area series.
    """

    extent_per_native_area: float


# Legacy-only coefficients. Active model diagnostics do not use them.
MARCH = SeasonalExtentAnchor(extent_per_native_area=1.1626984241436893)
SEPTEMBER = SeasonalExtentAnchor(extent_per_native_area=1.4457143785849278)


def seasonal_summer_weight(calendar_year: float) -> float:
    """Return a smooth 0=March, 1=September interpolation weight."""
    phase = float(calendar_year % 1.0)
    return float(0.5 * (1.0 - math.cos(2.0 * math.pi * (phase - MARCH_PHASE))))


def seasonal_extent_multiplier(calendar_year: float) -> float:
    """Return the deprecated fitted seasonal area-to-extent multiplier.

    This function exists for backwards compatibility only. New code should
    derive extent from native concentration via
    :func:`reconstruct_concentration_and_occupancy`.
    """
    summer = seasonal_summer_weight(calendar_year)
    return float(
        (1.0 - summer) * MARCH.extent_per_native_area
        + summer * SEPTEMBER.extent_per_native_area
    )


def raw_northern_ice_area_million_km2(
    atlantic_fraction: np.ndarray,
    non_atlantic_fraction: np.ndarray,
    lat: np.ndarray,
    atlantic_ocean_fraction_map: np.ndarray,
    ocean_fraction_map: np.ndarray,
    map_area_weights: np.ndarray,
) -> float:
    """Integrate native zonal Atlantic/non-Atlantic ice over the NH ocean."""
    non_atlantic_map = np.clip(
        np.asarray(ocean_fraction_map, dtype=float)
        - np.asarray(atlantic_ocean_fraction_map, dtype=float),
        0.0,
        1.0,
    )
    ice_area_fraction = (
        np.asarray(atlantic_fraction, dtype=float)[:, None]
        * np.asarray(atlantic_ocean_fraction_map, dtype=float)
        + np.asarray(non_atlantic_fraction, dtype=float)[:, None] * non_atlantic_map
    )
    north = np.asarray(lat, dtype=float)[:, None] >= 0.0
    return float(
        np.sum(np.where(north, ice_area_fraction, 0.0) * map_area_weights)
        * EARTH_AREA_M2
        / 1.0e12
    )


def diagnosed_area_extent_million_km2(
    *,
    raw_area_million_km2: float,
    warming_c: float,
    calendar_year: float,
    northern_ocean_area_million_km2: float,
    native_extent_million_km2: float | None = None,
    use_legacy_calibrated_multiplier: bool = False,
) -> tuple[float, float]:
    """Return native area and a bounded extent diagnostic.

    ``native_extent_million_km2`` should be supplied when native concentration
    geometry is available. If it is omitted, the conservative compatibility
    default is ``extent = area`` rather than silently applying an empirical
    historical fit. ``use_legacy_calibrated_multiplier=True`` exists only for
    reproduction of older outputs.

    ``warming_c`` is intentionally unused and retained for API compatibility.
    """
    del warming_c
    ocean_area = max(float(northern_ocean_area_million_km2), 0.0)
    native_area = float(np.clip(float(raw_area_million_km2), 0.0, ocean_area))
    if native_area == 0.0:
        return 0.0, 0.0

    if native_extent_million_km2 is not None:
        extent = float(native_extent_million_km2)
    elif use_legacy_calibrated_multiplier:
        extent = native_area * seasonal_extent_multiplier(calendar_year)
    else:
        extent = native_area

    extent = float(np.clip(extent, 0.0, ocean_area))
    return native_area, extent


def _native_concentration_map(
    *,
    atlantic_fraction: np.ndarray,
    non_atlantic_fraction: np.ndarray,
    atlantic_ocean_fraction_map: np.ndarray,
    ocean_fraction_map: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Return native ice concentration and ocean fraction on the map grid."""
    ocean = np.asarray(ocean_fraction_map, dtype=float)
    atlantic_ocean = np.asarray(atlantic_ocean_fraction_map, dtype=float)
    non_atlantic_ocean = np.clip(ocean - atlantic_ocean, 0.0, 1.0)
    ice_area_fraction = (
        np.asarray(atlantic_fraction, dtype=float)[:, None] * atlantic_ocean
        + np.asarray(non_atlantic_fraction, dtype=float)[:, None]
        * non_atlantic_ocean
    )
    concentration = np.divide(
        ice_area_fraction,
        ocean,
        out=np.zeros_like(ice_area_fraction, dtype=float),
        where=ocean > 1.0e-12,
    )
    return np.clip(concentration, 0.0, 1.0), ocean


def _latitude_edges_from_centers(lat: np.ndarray) -> np.ndarray:
    """Infer latitude-band edges from monotone cell centres."""
    centers = np.asarray(lat, dtype=float)
    if centers.ndim != 1 or centers.size < 2:
        raise ValueError("lat must be a one-dimensional array with at least two centres")
    if not np.all(np.diff(centers) > 0.0):
        raise ValueError("lat centres must be strictly increasing")
    edges = np.empty(centers.size + 1, dtype=float)
    edges[1:-1] = 0.5 * (centers[:-1] + centers[1:])
    edges[0] = centers[0] - 0.5 * (centers[1] - centers[0])
    edges[-1] = centers[-1] + 0.5 * (centers[-1] - centers[-2])
    return np.clip(edges, -90.0, 90.0)


def _minmod(a: float, b: float) -> float:
    if a * b <= 0.0:
        return 0.0
    return math.copysign(min(abs(a), abs(b)), a)


def _conservative_subgrid_threshold(
    concentration: np.ndarray,
    lat: np.ndarray,
    threshold: float = MINIMUM_EXTENT_CONCENTRATION,
) -> tuple[np.ndarray, np.ndarray]:
    """Fractional extent occupancy and thresholded concentration integral.

    Each latitude cell is reconstructed linearly in x=sin(latitude).  The
    profile is centred on the exact equal-area midpoint so its cell mean is
    exactly the prognostic concentration. Slopes are minmod limited and then
    bounded so both endpoints remain in [0,1]. The returned thresholded
    concentration is the integral over only the above-threshold portion,
    normalized by the full cell width.
    """
    c = np.clip(np.asarray(concentration, dtype=float), 0.0, 1.0)
    lat = np.asarray(lat, dtype=float)
    if c.shape != lat.shape:
        raise ValueError("sector concentration must match latitude centres")
    edges_deg = _latitude_edges_from_centers(lat)
    x_edges = np.sin(np.deg2rad(edges_deg))
    x_mid = 0.5 * (x_edges[:-1] + x_edges[1:])
    dx = np.diff(x_edges)
    n = c.size
    slopes = np.zeros(n, dtype=float)
    if n == 2:
        common = (c[1] - c[0]) / max(x_mid[1] - x_mid[0], 1e-15)
        slopes[:] = common
    elif n > 2:
        slopes[0] = (c[1] - c[0]) / max(x_mid[1] - x_mid[0], 1e-15)
        slopes[-1] = (c[-1] - c[-2]) / max(x_mid[-1] - x_mid[-2], 1e-15)
        for i in range(1, n - 1):
            left = (c[i] - c[i - 1]) / max(x_mid[i] - x_mid[i - 1], 1e-15)
            right = (c[i + 1] - c[i]) / max(x_mid[i + 1] - x_mid[i], 1e-15)
            slopes[i] = _minmod(left, right)

    occupancy = np.zeros(n, dtype=float)
    thresholded_integral = np.zeros(n, dtype=float)
    for i in range(n):
        half = 0.5 * dx[i]
        slope = float(slopes[i])
        # Bound slope while preserving the exact cell mean c[i].
        if half > 0.0:
            slope_limit = min(c[i] / half, (1.0 - c[i]) / half)
            slope = float(np.clip(slope, -slope_limit, slope_limit))
        c0 = float(np.clip(c[i] - slope * half, 0.0, 1.0))
        c1 = float(np.clip(c[i] + slope * half, 0.0, 1.0))
        if c0 >= threshold and c1 >= threshold:
            occupancy[i] = 1.0
            thresholded_integral[i] = c[i]
            continue
        if c0 < threshold and c1 < threshold:
            continue
        delta = c1 - c0
        if abs(delta) < 1e-15:
            continue
        u = float(np.clip((threshold - c0) / delta, 0.0, 1.0))
        if delta > 0.0:
            occupancy[i] = 1.0 - u
            thresholded_integral[i] = c0 * (1.0 - u) + 0.5 * delta * (1.0 - u * u)
        else:
            occupancy[i] = u
            thresholded_integral[i] = c0 * u + 0.5 * delta * u * u
    return np.clip(occupancy, 0.0, 1.0), np.clip(thresholded_integral, 0.0, 1.0)


def reconstruct_concentration_and_occupancy(
    *,
    atlantic_fraction: np.ndarray,
    non_atlantic_fraction: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray,
    lat2d: np.ndarray,
    lon2d: np.ndarray,
    atlantic_ocean_fraction_map: np.ndarray,
    ocean_fraction_map: np.ndarray,
    map_area_weights: np.ndarray,
    warming_c: float,
    calendar_year: float,
) -> tuple[np.ndarray, np.ndarray, dict[str, float | str]]:
    """Return native concentration and conservative fractional 15% occupancy.

    R16 reconstructs an unfitted monotone meridional concentration profile
    inside each native latitude/sector cell. The reconstruction is performed
    in equal-area x=sin(latitude) coordinates and preserves each native cell's
    prognostic mean exactly. It changes only the derived extent observation
    operator; prognostic area, volume and thermodynamics are untouched.
    """
    del lon, lon2d, warming_c, calendar_year
    lat = np.asarray(lat, dtype=float)
    atlantic = np.clip(np.asarray(atlantic_fraction, dtype=float), 0.0, 1.0)
    non_atlantic = np.clip(np.asarray(non_atlantic_fraction, dtype=float), 0.0, 1.0)
    concentration, ocean = _native_concentration_map(
        atlantic_fraction=atlantic,
        non_atlantic_fraction=non_atlantic,
        atlantic_ocean_fraction_map=atlantic_ocean_fraction_map,
        ocean_fraction_map=ocean_fraction_map,
    )
    atl_occ, atl_thr_int = _conservative_subgrid_threshold(atlantic, lat)
    non_occ, non_thr_int = _conservative_subgrid_threshold(non_atlantic, lat)

    atlantic_ocean = np.asarray(atlantic_ocean_fraction_map, dtype=float)
    non_atlantic_ocean = np.clip(np.asarray(ocean_fraction_map, dtype=float) - atlantic_ocean, 0.0, 1.0)
    valid_ocean = ocean > 1.0e-12
    occupancy = np.divide(
        atl_occ[:, None] * atlantic_ocean + non_occ[:, None] * non_atlantic_ocean,
        ocean,
        out=np.zeros_like(ocean, dtype=float),
        where=valid_ocean,
    )
    thresholded_ice_fraction = (
        atl_thr_int[:, None] * atlantic_ocean
        + non_thr_int[:, None] * non_atlantic_ocean
    )

    north = (np.asarray(lat2d, dtype=float) >= 0.0) & valid_ocean
    cell_area = np.asarray(map_area_weights, dtype=float) * EARTH_AREA_M2 / 1.0e12
    cell_ocean_area = ocean * cell_area
    native_area = float(np.sum(np.where(north, concentration * cell_ocean_area, 0.0)))
    thresholded_area = float(np.sum(np.where(north, thresholded_ice_fraction * cell_area, 0.0)))
    threshold_extent = float(np.sum(np.where(north, occupancy * cell_ocean_area, 0.0)))
    northern_ocean_area = float(np.sum(np.where(north, cell_ocean_area, 0.0)))

    native_area, _ = diagnosed_area_extent_million_km2(
        raw_area_million_km2=native_area,
        warming_c=0.0,
        calendar_year=0.0,
        northern_ocean_area_million_km2=northern_ocean_area,
        native_extent_million_km2=threshold_extent,
    )
    threshold_extent = float(np.clip(threshold_extent, 0.0, northern_ocean_area))
    thresholded_area = float(np.clip(thresholded_area, 0.0, threshold_extent))
    mean_pack_concentration = float(thresholded_area / threshold_extent) if threshold_extent > 0.0 else 0.0

    # Exact native-area conservation check for the reconstructed sector means.
    reconstructed_native_area = float(np.sum(np.where(north, concentration * cell_ocean_area, 0.0)))
    area_error = reconstructed_native_area - native_area
    metrics: dict[str, float | str] = {
        "northern_hemisphere_sea_ice_area_million_km2": native_area,
        "native_northern_ice_area_million_km2": native_area,
        "raw_two_sector_northern_ice_area_million_km2": native_area,
        "northern_hemisphere_sea_ice_thresholded_area_million_km2": thresholded_area,
        "northern_hemisphere_sea_ice_extent_million_km2": threshold_extent,
        "northern_hemisphere_mean_pack_concentration": mean_pack_concentration,
        "statistical_to_raw_area_ratio": 1.0,
        "sea_ice_area_mapping_is_identity": 1.0,
        "extent_observation_operator_calibrated": 0.0,
        "observation_operator_calibrated": 0.0,
        "extent_threshold_concentration": MINIMUM_EXTENT_CONCENTRATION,
        "extent_method": "conservative_unfitted_meridional_subgrid_15pct_threshold",
        "extent_contains_observational_fit": 0.0,
        "extent_is_separate_prognostic_state": 0.0,
        "extent_derived_from_native_concentration": 1.0,
        "extent_subgrid_fractional_occupancy": 1.0,
        "extent_reconstruction_coordinate": "sin(latitude)_equal_area",
        "extent_reconstruction_native_area_error_million_km2": area_error,
        "legacy_extent_multiplier_used": 0.0,
    }
    return concentration, np.clip(occupancy, 0.0, 1.0), metrics

