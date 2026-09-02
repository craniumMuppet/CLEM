"""Reduced AMOC equation-of-state helpers.

TEOS-10 is evaluated only for the representative North Atlantic sinking box
and the active reduced source-water box selected by ``amoc_density_geometry``;
it does not add grid-scale cost. The fixed-alpha/beta equation remains
available as an explicit structural sensitivity in :mod:`climate_model`.
"""

from __future__ import annotations


class TEOS10Unavailable(RuntimeError):
    """Raised when the required GSW dependency is unavailable."""


def teos10_density_driver(
    *,
    north_temperature_c: float,
    north_salinity_psu: float,
    source_temperature_c: float,
    source_salinity_psu: float,
    source_longitude_deg: float = -20.0,
    source_latitude_deg: float = -34.5,
    reference_density_kg_m3: float,
) -> float:
    """Return (rho_north-rho_source)/rho_ref using TEOS-10/GSW.

    Practical Salinity is converted to Absolute Salinity at representative
    Atlantic coordinates before in-situ density is evaluated at the surface.
    These coordinates are fixed parts of the reduced observation operator, not
    tuning parameters.
    """
    try:
        import gsw  # type: ignore
    except ImportError as exc:
        raise TEOS10Unavailable(
            "The production TEOS-10 AMOC density equation requires the 'gsw' "
            "package. Install the declared CLEM runtime dependencies or use "
            "amoc_density_eos='linear' as an explicit structural sensitivity."
        ) from exc

    p_dbar = 0.0
    north_lon, north_lat = -35.0, 55.0
    source_lon, source_lat = float(source_longitude_deg), float(source_latitude_deg)
    sa_north = float(gsw.SA_from_SP(float(north_salinity_psu), p_dbar, north_lon, north_lat))
    sa_source = float(gsw.SA_from_SP(float(source_salinity_psu), p_dbar, source_lon, source_lat))
    rho_north = float(gsw.rho_t_exact(sa_north, float(north_temperature_c), p_dbar))
    rho_source = float(gsw.rho_t_exact(sa_source, float(source_temperature_c), p_dbar))
    return (rho_north - rho_source) / float(reference_density_kg_m3)
