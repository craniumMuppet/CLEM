#!/usr/bin/env python3
"""Acquire and preprocess the six-source Arctic validation stack.

The processors construct explicit spatial observation operators.  EGCM is
later sampled onto those exact supports, preventing full-domain model fields
from being compared against differently masked satellite/reanalysis products.

NASA/NSIDC DAAC authentication uses earthaccess for cloud-hosted products.
NSIDC-0611 remains an optional structural diagnostic because its legacy archive
can require separate account authorization; failure or absence of that one
source must not block acquisition of the five core calibration/validation
products. If EARTHDATA_USERNAME and EARTHDATA_PASSWORD are already set, the
script will attempt NSIDC-0611 through the official legacy cookie flow.
Credentials are never written into the project. Existing raw files can be
processed with --process-existing.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from http.cookiejar import CookieJar
import gzip
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
from typing import Iterable
from urllib.parse import urljoin, urlparse
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
import requests

try:
    import xarray as xr
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Install requirements-validation-data.txt before running this script") from exc

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from arctic_observation_operator import (  # noqa: E402
    save_spatial_operator,
    save_temporal_thickness_operator,
)
from arctic_validation_stack import (  # noqa: E402
    CRYOSAT2_OPERATOR,
    ICE_AGE_DIR,
    ICESAT2_OPERATOR,
    OSI_SAF_DIR,
    OSI_SAF_OPERATOR,
    PHYSICAL_DIR,
    PIOMAS_OPERATOR,
    PRIMARY_AREA_DIR,
    PRIMARY_AREA_OPERATOR,
    sha256_file,
    write_stack_status,
)

RAW_ROOT = ROOT / "data" / "validation" / "raw_observations"
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "EGCM-Arctic-Validation/2026 scientific reproducibility"})

G02202_BASE_CANDIDATES = (
    "https://noaadata.apps.nsidc.org/NOAA/G02202_V6/north/monthly/",
    "https://noaadata.apps.nsidc.org/NOAA/G02202_V6/north/",
)
G02202_ANCILLARY_URL = (
    "https://noaadata.apps.nsidc.org/NOAA/G02202_V6/ancillary/"
    "G02202-ancillary-psn25-v06r00.nc"
)
PIOMAS_HEFF_BASE = "https://pscfiles.apl.uw.edu/zhang/PIOMAS/data/v2.1/heff/"
PIOMAS_GRID_URLS = {
    "grid.dat": "https://pscfiles.apl.washington.edu/zhang/PIOMAS/utilities/grid.dat",
    "grid.dat.pop": "https://pscfiles.apl.washington.edu/zhang/PIOMAS/utilities/grid.dat.pop",
    "io.dat_360_120.output": (
        "https://pscfiles.apl.washington.edu/zhang/PIOMAS/utilities/io.dat_360_120.output"
    ),
}
PIOMAS_COMMON_DOMAIN_MIN_LAT_DEG = 60.0
OSI_CATALOG = (
    "https://thredds.met.no/thredds/catalog/osisaf/met.no/reprocessed/ice/"
    "conc_450a1_files/catalog.xml"
)
OSI_FILESERVER_PREFIX = "https://thredds.met.no/thredds/fileServer/"
NSIDC_ICE_AGE_HTTPS_BASE = (
    "https://daacdata.apps.nsidc.org/pub/DATASETS/nsidc0611_seaice_age_v4/data/"
)
NSIDC_ICE_AGE_START_YEAR = 1984
NSIDC_ICE_AGE_END_YEAR = 2024


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _download(url: str, destination: Path, overwrite: bool = False) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 0 and not overwrite:
        return destination
    temporary = destination.with_suffix(destination.suffix + ".part")
    response = SESSION.get(url, timeout=180, stream=True)
    response.raise_for_status()
    with temporary.open("wb") as handle:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                handle.write(chunk)
    temporary.replace(destination)
    return destination


def _html_links(url: str) -> list[str]:
    response = SESSION.get(url, timeout=120)
    response.raise_for_status()
    return [
        urljoin(url, match)
        for match in re.findall(r'href=["\']([^"\']+)["\']', response.text, flags=re.I)
    ]


def _crawl_http_files(url: str, suffixes: tuple[str, ...], depth: int = 3) -> list[str]:
    visited: set[str] = set()
    found: list[str] = []

    def visit(current: str, remaining: int) -> None:
        if current in visited or remaining < 0:
            return
        visited.add(current)
        try:
            links = _html_links(current)
        except requests.RequestException:
            return
        for link in links:
            clean = link.split("#", 1)[0].split("?", 1)[0]
            if clean.lower().endswith(suffixes):
                found.append(clean)
            elif remaining > 0 and clean.endswith("/"):
                visit(clean, remaining - 1)

    visit(url, depth)
    return sorted(set(found))


def _file_signature(path: Path, size: int = 16) -> bytes:
    with Path(path).open("rb") as handle:
        return handle.read(size)


def _is_netcdf_file(path: Path) -> bool:
    """Return True for classic NetCDF or NetCDF-4/HDF5 data files."""
    try:
        signature = _file_signature(path, 8)
    except OSError:
        return False
    return signature.startswith(b"CDF") or signature == b"\x89HDF\r\n\x1a\n"


def _open_dataset(path: Path):
    """Open a verified NetCDF file with explicit backend fallbacks.

    Earthdata granules can expose ancillary/metadata links alongside the actual
    NetCDF payload.  Do not let xarray guess from a sidecar path: verify the
    file signature first, then try the installed NetCDF backends explicitly.
    """
    path = Path(path)
    if not path.exists() or path.stat().st_size <= 0:
        raise FileNotFoundError(f"Missing or empty observation file: {path}")
    if not _is_netcdf_file(path):
        signature = _file_signature(path, 16)
        raise ValueError(
            f"Observation file is not NetCDF/NetCDF-4: {path.name} "
            f"(signature={signature!r})"
        )

    errors: list[str] = []
    signature = _file_signature(path, 8)
    engines = ("netcdf4", "h5netcdf") if signature == b"\x89HDF\r\n\x1a\n" else ("netcdf4", "scipy")
    for engine in engines:
        try:
            return xr.open_dataset(
                path, engine=engine, decode_times=True, mask_and_scale=True
            )
        except Exception as exc:
            errors.append(f"{engine}: {type(exc).__name__}: {exc}")
    raise ValueError(
        f"Could not open NetCDF observation file {path.name}. " + " | ".join(errors)
    )


def _numeric_array(values) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    array[~np.isfinite(array)] = np.nan
    return array


def _find_variable(ds, exact_names: list[str], contains: tuple[str, ...]):
    for name in exact_names:
        if name in ds.variables:
            return ds[name]
    for name, variable in ds.data_vars.items():
        lower = name.lower()
        if all(part in lower for part in contains):
            return variable
    raise KeyError(f"Could not find variable matching {exact_names} / {contains}")


def _concentration_fraction(variable) -> np.ndarray:
    values = _numeric_array(variable.values)
    finite = values[np.isfinite(values)]
    if finite.size and np.nanpercentile(finite, 95) > 1.5:
        values = values / 100.0
    values[(values < 0.0) | (values > 1.0)] = np.nan
    return np.squeeze(values)


def _projected_axis_values_meters(variable) -> np.ndarray:
    """Return a 1-D projected coordinate axis in metres.

    CF/OSI-SAF products commonly store EASE-grid coordinates in kilometres,
    whereas pyproj and the area calculation expect metres.  The previous
    implementation ignored the coordinate ``units`` attribute, turning a
    25 km grid into 25 m cells.  Honour explicit units and use a conservative
    spacing inference only when the attribute is absent.
    """
    values = np.asarray(variable.values, dtype=float)
    units = str(variable.attrs.get("units", "")).strip().lower().replace(" ", "")
    if units in {"km", "kilometer", "kilometers", "kilometre", "kilometres"} or "kilomet" in units:
        return values * 1000.0
    if units in {"m", "meter", "meters", "metre", "metres"} or units.endswith("meter") or units.endswith("metre"):
        return values
    finite = values[np.isfinite(values)]
    if finite.size >= 2:
        spacing = float(np.nanmedian(np.abs(np.diff(finite))))
        # Polar climate grids with coordinate steps of order 1--100 and axis
        # magnitudes of order 10^3 are conventionally expressed in km.
        if 1.0 <= spacing <= 250.0 and float(np.nanmax(np.abs(finite))) <= 20000.0:
            return values * 1000.0
    return values


def _xy_from_dataset(ds, *, meters: bool = False) -> tuple[np.ndarray, np.ndarray] | None:
    x_names = ("x", "xc", "xgrid")
    y_names = ("y", "yc", "ygrid")
    x_var = next((ds[name] for name in x_names if name in ds.variables), None)
    y_var = next((ds[name] for name in y_names if name in ds.variables), None)
    if x_var is None or y_var is None:
        return None
    x = _projected_axis_values_meters(x_var) if meters else np.asarray(x_var.values, dtype=float)
    y = _projected_axis_values_meters(y_var) if meters else np.asarray(y_var.values, dtype=float)
    if x.ndim != 1 or y.ndim != 1:
        return None
    return x, y


def _lat_lon_from_dataset(ds, shape: tuple[int, int], epsg: int) -> tuple[np.ndarray, np.ndarray]:
    lat_var = next((ds[name] for name in ("latitude", "lat") if name in ds.variables), None)
    lon_var = next((ds[name] for name in ("longitude", "lon") if name in ds.variables), None)
    if lat_var is not None and lon_var is not None:
        lat = np.squeeze(_numeric_array(lat_var.values))
        lon = np.squeeze(_numeric_array(lon_var.values))
        if lat.ndim == 1 and lon.ndim == 1 and (lat.size, lon.size) == shape:
            lon, lat = np.meshgrid(lon, lat)
        if lat.shape == shape and lon.shape == shape:
            return lat, lon
    xy = _xy_from_dataset(ds, meters=True)
    if xy is None:
        raise ValueError("Dataset contains neither usable latitude/longitude nor projected x/y coordinates")
    try:
        from pyproj import CRS, Transformer
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("pyproj is required to geolocate projected observation grids") from exc
    x, y = xy
    if (len(y), len(x)) != shape:
        raise ValueError(f"Projected coordinate shape {(len(y), len(x))} != data shape {shape}")
    xx, yy = np.meshgrid(x, y)
    transformer = Transformer.from_crs(CRS.from_epsg(epsg), CRS.from_epsg(4326), always_xy=True)
    lon, lat = transformer.transform(xx, yy)
    return np.asarray(lat, dtype=float), np.asarray(lon, dtype=float)


def projected_grid_cell_area_km2(ds, epsg: int, equal_area: bool = False) -> np.ndarray | None:
    if "grid_cell_area" in ds.variables:
        values = np.squeeze(_numeric_array(ds["grid_cell_area"].values))
        units = str(ds["grid_cell_area"].attrs.get("units", "m2")).lower()
        return values if "km" in units else values / 1.0e6
    xy = _xy_from_dataset(ds, meters=True)
    if xy is None:
        return None
    x, y = xy
    if len(x) < 2 or len(y) < 2:
        return None
    dx = float(np.nanmedian(np.abs(np.diff(x))))
    dy = float(np.nanmedian(np.abs(np.diff(y))))
    projected = dx * dy / 1.0e6
    shape = (len(y), len(x))
    if equal_area:
        return np.full(shape, projected, dtype=float)
    try:
        from pyproj import CRS, Proj, Transformer

        xx, yy = np.meshgrid(x, y)
        transformer = Transformer.from_crs(CRS.from_epsg(epsg), CRS.from_epsg(4326), always_xy=True)
        lon, lat = transformer.transform(xx, yy)
        factors = Proj(CRS.from_epsg(epsg)).get_factors(lon, lat)
        areal_scale = np.asarray(factors.areal_scale, dtype=float)
        area = projected / areal_scale
        area[~np.isfinite(area)] = np.nan
        return area
    except Exception:
        return np.full(shape, projected, dtype=float)


def _date_from_filename(path: Path) -> tuple[int, int] | None:
    matches = re.findall(r"((?:19|20)\d{2})(0[1-9]|1[0-2])", path.name)
    if not matches:
        return None
    year, month = matches[-1]
    return int(year), int(month)


def _dataset_date(ds, path: Path) -> tuple[int, int] | None:
    date = _date_from_filename(path)
    if date is not None:
        return date
    if "time" in ds.variables:
        values = np.asarray(ds["time"].values).ravel()
        if values.size:
            stamp = pd.Timestamp(values[0])
            return int(stamp.year), int(stamp.month)
    return None


def acquire_g02202(overwrite: bool = False) -> list[Path]:
    raw_dir = RAW_ROOT / "nsidc_g02202_v6"
    _download(G02202_ANCILLARY_URL, raw_dir / Path(G02202_ANCILLARY_URL).name, overwrite=overwrite)
    urls: list[str] = []
    for base in G02202_BASE_CANDIDATES:
        candidates = _crawl_http_files(base, (".nc", ".nc4"), depth=3)
        for url in candidates:
            date = _date_from_filename(Path(url))
            if date is None or date[1] not in (3, 9):
                continue
            if "month" in url.lower():
                urls.append(url)
        if urls:
            break
    if not urls:
        raise RuntimeError(
            "Could not discover G02202 v6 monthly files. Place northern monthly NetCDF files "
            f"in {raw_dir.relative_to(ROOT)} and run --process-existing."
        )
    return [_download(url, raw_dir / Path(url).name, overwrite=overwrite) for url in sorted(set(urls))]


def _g02202_permanent_support(ancillary_path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if not ancillary_path.exists():
        raise FileNotFoundError(
            f"Missing G02202 v6 ancillary file {ancillary_path.name}; it is required for the permanent pole-hole mask"
        )
    with _open_dataset(ancillary_path) as ds:
        pole = np.squeeze(_numeric_array(_find_variable(ds, ["polehole_bitmask"], ("pole", "mask")).values))
        surface = np.squeeze(_numeric_array(_find_variable(ds, ["surface_type"], ("surface", "type")).values))
        shape = tuple(pole.shape)
        if len(shape) != 2 or surface.shape != pole.shape:
            raise ValueError("G02202 ancillary pole-hole/surface masks have incompatible shapes")
        lat, lon = _lat_lon_from_dataset(ds, shape, 3411)
    # surface_type=50 is ocean. Bit 1 denotes cells inside the largest Nimbus-7 SMMR pole hole.
    pole_code = np.where(np.isfinite(pole), np.rint(pole), 0).astype(np.int64)
    support = (
        np.isfinite(surface)
        & (np.rint(surface).astype(np.int64) == 50)
        & ((pole_code & 1) == 0)
        & np.isfinite(lat)
        & np.isfinite(lon)
    )
    if not np.any(support):
        raise RuntimeError("G02202 permanent ocean/pole-hole support is empty")
    return support, lat, lon


def _process_fixed_mask_concentration(
    files: Iterable[Path],
    output_dir: Path,
    *,
    operator_path: Path,
    source_id: str,
    product: str,
    version: str,
    epsg: int,
    equal_area: bool,
    base_support: np.ndarray | None = None,
    fixed_latitude: np.ndarray | None = None,
    fixed_longitude: np.ndarray | None = None,
    metadata_extra: dict | None = None,
    crosscheck: bool = False,
) -> None:
    arrays: list[np.ndarray] = []
    dates: list[tuple[int, int]] = []
    area_km2: np.ndarray | None = None
    latitude: np.ndarray | None = fixed_latitude
    longitude: np.ndarray | None = fixed_longitude
    source_hashes: dict[str, str] = {}
    variable_names: set[str] = set()
    for path in sorted(files):
        date = _date_from_filename(path)
        if date is None or date[1] not in (3, 9):
            continue
        with _open_dataset(path) as ds:
            variable = _find_variable(
                ds,
                ["cdr_seaice_conc_monthly", "ice_conc", "sea_ice_concentration"],
                ("ice", "conc"),
            )
            concentration = _concentration_fraction(variable)
            if concentration.ndim == 3:
                concentration = concentration[0]
            if concentration.ndim != 2:
                continue
            if area_km2 is None:
                area_km2 = projected_grid_cell_area_km2(ds, epsg, equal_area=equal_area)
                if area_km2 is None:
                    area_km2 = np.full(concentration.shape, 625.0, dtype=float)
            if np.shape(area_km2) != np.shape(concentration):
                raise ValueError(f"Grid shape changed in {path.name}")
            if latitude is None or longitude is None:
                latitude, longitude = _lat_lon_from_dataset(ds, concentration.shape, epsg)
            if latitude.shape != concentration.shape or longitude.shape != concentration.shape:
                raise ValueError(f"Latitude/longitude shape mismatch in {path.name}")
            arrays.append(concentration)
            dates.append(date)
            source_hashes[path.name] = sha256_file(path)
            variable_names.add(str(variable.name))
    if not arrays or area_km2 is None or latitude is None or longitude is None:
        raise RuntimeError(f"No March/September concentration fields found for {source_id}")

    fixed_support = np.ones(arrays[0].shape, dtype=bool)
    if base_support is not None:
        if base_support.shape != fixed_support.shape:
            raise ValueError("Explicit fixed support does not match concentration grid")
        fixed_support &= base_support
    for concentration in arrays:
        fixed_support &= np.isfinite(concentration)
    fixed_support &= (
        np.isfinite(area_km2)
        & (area_km2 > 0.0)
        & np.isfinite(latitude)
        & np.isfinite(longitude)
    )
    if not np.any(fixed_support):
        raise RuntimeError(f"Fixed spatial support is empty for {source_id}")

    output_dir.mkdir(parents=True, exist_ok=True)
    save_spatial_operator(
        operator_path,
        source_id=source_id,
        latitude_deg=latitude[fixed_support],
        longitude_deg=longitude[fixed_support],
        cell_area_km2=area_km2[fixed_support],
    )

    records: list[dict] = []
    for concentration, (year, month) in zip(arrays, dates):
        selected = fixed_support & (concentration >= 0.15)
        area = float(np.nansum(np.where(selected, concentration * area_km2, 0.0)) / 1.0e6)
        extent = float(np.nansum(np.where(selected, area_km2, 0.0)) / 1.0e6)
        records.append({"year": year, "month": month, "area": area, "extent": extent, "source": source_id})
    frame = pd.DataFrame(records).sort_values(["year", "month"]).drop_duplicates(["year", "month"], keep="last")
    output_hashes: dict[str, str] = {}
    for month in (3, 9):
        subset = frame[frame["month"] == month].drop(columns=["month"])
        name = f"N_{month:02d}_fixed_mask_crosscheck.csv" if crosscheck else f"N_{month:02d}_fixed_mask.csv"
        output = output_dir / name
        subset.to_csv(output, index=False)
        output_hashes[name] = sha256_file(output)
    output_hashes[operator_path.name] = sha256_file(operator_path)
    metadata = {
        "source_id": source_id,
        "product": product,
        "version": version,
        "fixed_mask": True,
        "concentration_threshold": 0.15,
        "model_domain_compatible": bool(operator_path.exists() and np.count_nonzero(fixed_support) > 0),
        "model_domain_compatibility_basis": (
            "runtime spatial observation operator: EGCM concentration is sampled at the exact retained observation cell centers"
        ),
        "spatial_support_rule": (
            "explicit fixed support saved in MODEL_OBSERVATION_OPERATOR.npz; all processed records use identical cells"
        ),
        "operator_cell_count": int(np.count_nonzero(fixed_support)),
        "operator_area_million_km2": float(np.sum(area_km2[fixed_support]) / 1.0e6),
        "area_definition": "sum(concentration * cell_area) where concentration >= 0.15 on fixed support",
        "extent_definition": "sum(cell_area) where concentration >= 0.15 on fixed support",
        "projection_epsg": epsg,
        "source_variable_names": sorted(variable_names),
        "source_files_sha256": source_hashes,
        "processed_files_sha256": output_hashes,
        "generated_utc": utc_now(),
    }
    if metadata_extra:
        metadata.update(metadata_extra)
    (output_dir / "METADATA.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def process_g02202(paths: Iterable[Path] | None = None) -> None:
    raw_dir = RAW_ROOT / "nsidc_g02202_v6"
    files = sorted(paths or raw_dir.glob("*.nc*"))
    ancillary = raw_dir / Path(G02202_ANCILLARY_URL).name
    files = [path for path in files if path.name != ancillary.name]
    support, lat, lon = _g02202_permanent_support(ancillary)
    _process_fixed_mask_concentration(
        files,
        PRIMARY_AREA_DIR,
        operator_path=PRIMARY_AREA_OPERATOR,
        source_id="nsidc_g02202_v6",
        product="NOAA/NSIDC Climate Data Record of Passive Microwave Sea Ice Concentration",
        version="6",
        epsg=3411,
        equal_area=False,
        base_support=support,
        fixed_latitude=lat,
        fixed_longitude=lon,
        metadata_extra={
            "doi": "10.7265/b18j-z797",
            "role": "primary_fixed_mask_area_calibration",
            "raw_sea_ice_index_area_used": False,
            "pole_hole_rule": (
                "permanent common mask excludes every cell flagged inside the Nimbus-7 SMMR pole hole (polehole_bitmask bit 1)"
            ),
        },
    )


def _read_fixed_width(path: Path, width: int, expected: int) -> np.ndarray:
    values: list[float] = []
    for line in path.read_text(encoding="ascii", errors="ignore").splitlines():
        for start in range(0, len(line), width):
            text = line[start:start + width].strip()
            if text:
                values.append(float(text))
    if len(values) < expected:
        raise ValueError(f"{path.name} contains {len(values)} values; expected at least {expected}")
    return np.asarray(values[:expected], dtype=float)


def _read_piomas_geometry(raw_dir: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Read PIOMAS scalar-grid geometry following PSC's heff_for_volume.f.

    PSC's reference volume code does not use ``HTN * HTE`` directly.  It
    constructs scalar-cell metric lengths by averaging the neighbouring POP
    staggered-grid metrics: DXT = 0.5*(HTN + HTN[j+1]) and
    DYT = 0.5*(HTE + HTE[i+1]).  DXT/DYT are kilometres, so their product is
    the cell area in km2.
    """
    nx, ny = 360, 120
    n = nx * ny
    grid = _read_fixed_width(raw_dir / "grid.dat", 8, 2 * n)
    lon = grid[:n].reshape(ny, nx)
    lat = grid[n:2 * n].reshape(ny, nx)
    pop = _read_fixed_width(raw_dir / "grid.dat.pop", 8, 7 * n)
    htn = pop[2 * n:3 * n].reshape(ny, nx)
    hte = pop[3 * n:4 * n].reshape(ny, nx)

    htn_next_j = np.zeros_like(htn)
    htn_next_j[:-1, :] = htn[1:, :]
    dxt = 0.5 * (htn + htn_next_j)
    hte_next_i = np.zeros_like(hte)
    hte_next_i[:, :-1] = hte[:, 1:]
    dyt = 0.5 * (hte + hte_next_i)
    dxt[dxt == 0.0] = 1.0
    dyt[dyt == 0.0] = 1.0
    area_km2 = np.abs(dxt * dyt)

    mask_values = _read_fixed_width(raw_dir / "io.dat_360_120.output", 2, n).reshape(ny, nx)
    ocean = mask_values > 0.0
    support = (
        ocean
        & np.isfinite(lat)
        & np.isfinite(lon)
        & np.isfinite(area_km2)
        & (area_km2 > 0.0)
        & (lat >= PIOMAS_COMMON_DOMAIN_MIN_LAT_DEG)
        & (lat <= 90.0)
    )
    # PSC's reference volume loop excludes the first/last j rows; keep the
    # common-domain operator on the same well-defined interior scalar grid.
    support[0, :] = False
    support[-1, :] = False
    if not np.any(support):
        raise RuntimeError("PIOMAS common-domain grid support is empty")
    return support, lat, lon, area_km2


def _decompress_gzip(path: Path) -> Path:
    if path.suffix.lower() != ".gz":
        return path
    output = path.with_suffix("")
    if not output.exists() or output.stat().st_mtime < path.stat().st_mtime:
        with gzip.open(path, "rb") as source, output.open("wb") as destination:
            shutil.copyfileobj(source, destination)
    return output


def acquire_piomas(overwrite: bool = False) -> list[Path]:
    """Acquire the official PSC flat-binary PIOMAS heff files.

    The PSC model-grid documentation identifies ``heff.H<yyyy>`` as flat
    binary single-precision output.  The earlier acquisition path selected the
    later ``.nc.gz`` conversion, which produced a large nonphysical background
    offset in the derived volume series.  Prefer the authoritative binary files
    and parse them directly.
    """
    raw_dir = RAW_ROOT / "piomas_v2_1"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for name, url in PIOMAS_GRID_URLS.items():
        _download(url, raw_dir / name, overwrite=overwrite)
    urls = _crawl_http_files(PIOMAS_HEFF_BASE, (".gz",), depth=0)
    selected: list[str] = []
    for url in urls:
        if url.lower().endswith(".nc.gz"):
            continue
        match = re.search(r"heff\.H((?:19|20)\d{2})\.gz$", url)
        if match and int(match.group(1)) >= 1979:
            selected.append(url)
    if not selected:
        raise RuntimeError(
            "Could not discover official PIOMAS flat-binary heff.H<year>.gz files; place those files and grid utilities in "
            f"{raw_dir.relative_to(ROOT)}."
        )
    return [_download(url, raw_dir / Path(url).name, overwrite=overwrite) for url in sorted(selected)]


def _read_piomas_heff_binary(path: Path) -> np.ndarray:
    """Read one official PIOMAS heff.HYYYY[.gz] flat-binary file.

    Each complete year normally contains 12 consecutive 360x120 float32
    fields.  Byte order is detected because PSC notes it may need swapping on
    non-PC architectures.  The selected interpretation must be overwhelmingly
    finite, non-negative and within a generous physical thickness envelope.
    """
    nx, ny = 360, 120
    n = nx * ny
    opener = gzip.open if path.suffix.lower() == ".gz" else open
    with opener(path, "rb") as handle:
        payload = handle.read()
    if len(payload) % (4 * n) != 0:
        raise ValueError(
            f"{path.name} has {len(payload)} bytes; expected an integer number of {n}-cell float32 fields"
        )
    field_count = len(payload) // (4 * n)
    if field_count < 1 or field_count > 12:
        raise ValueError(f"{path.name} contains {field_count} monthly fields; expected 1..12")

    candidates: list[tuple[float, np.ndarray, str]] = []
    for dtype, endian_name in (("<f4", "little"), (">f4", "big")):
        values = np.frombuffer(payload, dtype=dtype).astype(float).reshape(field_count, ny, nx)
        finite = np.isfinite(values)
        plausible = finite & (values >= -1.0e-6) & (values <= 50.0)
        plausible_fraction = float(np.count_nonzero(plausible) / values.size)
        finite_values = values[finite]
        p99 = float(np.nanpercentile(finite_values, 99)) if finite_values.size else 0.0
        # Wrong-endian float32 often decodes ordinary metre-scale thicknesses
        # as denormal values around 1e-41.  Reward a physically resolvable
        # upper percentile without requiring every grid cell to contain ice.
        scale_bonus = 0.2 if 0.01 <= p99 <= 20.0 else 0.0
        score = plausible_fraction + scale_bonus
        candidates.append((score, values, endian_name))
    score, values, endian_name = max(candidates, key=lambda item: item[0])
    if score < 0.98:
        raise ValueError(
            f"{path.name} does not decode as plausible PIOMAS float32 heff data (best {endian_name}-endian score={score:.3f})"
        )
    return values


def _published_piomas_monthly_lookup() -> dict[tuple[int, int], float]:
    """Load PSC's published total-volume series for a sanity check only.

    Values in PIOMAS.monthly.Current.v2.1.csv are 10^3 km3; divide by 1000
    to express them in the model validation unit of million km3.  This series
    is never used as the calibrated common-domain target.
    """
    path = PHYSICAL_DIR / "PIOMAS.monthly.Current.v2.1.csv"
    if not path.exists():
        return {}
    frame = pd.read_csv(path, skipinitialspace=True)
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    lookup: dict[tuple[int, int], float] = {}
    for _, row in frame.iterrows():
        try:
            year = int(round(float(row["year"])))
        except (KeyError, TypeError, ValueError):
            continue
        for month, name in enumerate(month_names, start=1):
            try:
                value = float(row[name])
            except (KeyError, TypeError, ValueError):
                continue
            if np.isfinite(value) and value >= 0.0:
                lookup[(year, month)] = value * 1.0e-3
    return lookup


def _validate_piomas_common_domain(frame: pd.DataFrame) -> dict[str, float | int | None]:
    volumes = pd.to_numeric(frame["volume_million_km3"], errors="coerce").to_numpy(dtype=float)
    if volumes.size == 0 or not np.all(np.isfinite(volumes)) or np.any(volumes < 0.0):
        raise RuntimeError("PIOMAS common-domain volume contains missing, non-finite, or negative values")
    # Arctic sea-ice volume is O(10^-2) million km3.  A value above 0.1 is a
    # decisive unit/background failure, not a plausible climate state.
    if float(np.max(volumes)) > 0.1:
        raise RuntimeError(
            f"PIOMAS common-domain volume sanity check failed: maximum {float(np.max(volumes)):.6f} million km3 exceeds 0.1"
        )

    published = _published_piomas_monthly_lookup()
    ratios: list[float] = []
    for row in frame.itertuples(index=False):
        total = published.get((int(row.year), int(row.month)))
        value = float(row.volume_million_km3)
        if total is not None and total > 0.0:
            ratios.append(value / total)
    result: dict[str, float | int | None] = {
        "records": int(len(frame)),
        "max_common_domain_volume_million_km3": float(np.max(volumes)),
        "published_scalar_overlap_records": int(len(ratios)),
        "median_common_domain_to_published_total_ratio": None,
    }
    if ratios:
        median_ratio = float(np.median(ratios))
        result["median_common_domain_to_published_total_ratio"] = median_ratio
        # A >=60N common-domain integral should be of the same order as and no
        # larger than the published all-Arctic total by a large factor.  Keep
        # the bound broad so the scalar series is only a unit/background guard.
        if not (0.20 <= median_ratio <= 1.20):
            raise RuntimeError(
                "PIOMAS common-domain sanity check failed against the published total-volume series: "
                f"median ratio={median_ratio:.3f}"
            )
    return result


def process_piomas(paths: Iterable[Path] | None = None) -> None:
    raw_dir = RAW_ROOT / "piomas_v2_1"
    if paths is None:
        files = sorted(
            path for path in list(raw_dir.glob("heff.H*.gz")) + list(raw_dir.glob("heff.H[0-9][0-9][0-9][0-9]"))
            if not path.name.lower().endswith(".nc.gz")
        )
    else:
        files = sorted(path for path in paths if not Path(path).name.lower().endswith(".nc.gz"))
    if not files:
        raise FileNotFoundError("No official flat-binary PIOMAS heff.H<year>[.gz] files are available")

    support, lat, lon, area_km2 = _read_piomas_geometry(raw_dir)
    save_spatial_operator(
        PIOMAS_OPERATOR,
        source_id="piomas_v2_1",
        latitude_deg=lat[support],
        longitude_deg=lon[support],
        cell_area_km2=area_km2[support],
    )
    rows: list[dict] = []
    source_hashes: dict[str, str] = {}
    used_years: set[int] = set()
    for source in files:
        source = Path(source)
        match = re.search(r"heff\.H((?:19|20)\d{2})(?:\.gz)?$", source.name)
        if not match:
            continue
        year = int(match.group(1))
        if year in used_years:
            continue
        values = _read_piomas_heff_binary(source)
        if values.shape[1:] != support.shape:
            raise ValueError(f"PIOMAS {source.name} grid {values.shape[1:]} != expected {support.shape}")
        for month in range(1, min(values.shape[0], 12) + 1):
            heff = np.asarray(values[month - 1], dtype=float)
            equivalent = np.where(support & np.isfinite(heff) & (heff >= 0.0), heff, 0.0)
            volume = float(np.sum(equivalent * area_km2) * 1.0e-9)
            rows.append({
                "year": year,
                "month": month,
                "volume_million_km3": volume,
                "source": "PIOMAS_v2.1_common_domain",
            })
        source_hashes[source.name] = sha256_file(source)
        used_years.add(year)
    if not rows:
        raise RuntimeError("No PIOMAS common-domain volume records were produced")

    output = PHYSICAL_DIR / "piomas_volume_monthly.csv"
    frame = pd.DataFrame(rows).sort_values(["year", "month"]).reset_index(drop=True)
    sanity = _validate_piomas_common_domain(frame)
    frame.to_csv(output, index=False)
    metadata = {
        "source_id": "piomas_v2_1",
        "product": "PIOMAS gridded monthly sea-ice thickness (heff: volume per unit area)",
        "version": "2.1",
        "role": "common_domain_long_record_volume_constraint",
        "common_domain_min_latitude_deg": PIOMAS_COMMON_DOMAIN_MIN_LAT_DEG,
        "common_domain_rule": (
            "PIOMAS ocean cells at >=60N on the PSC scalar grid; EGCM equivalent thickness is sampled at the same PIOMAS cell centers and integrated with the same cell areas"
        ),
        "source_format": "official_PSC_flat_binary_float32",
        "published_scalar_total_volume_used": False,
        "published_scalar_total_volume_used_for_sanity_check_only": True,
        "piomas_variable": "heff",
        "operator_file": PIOMAS_OPERATOR.name,
        "operator_file_sha256": sha256_file(PIOMAS_OPERATOR),
        "operator_cell_count": int(np.count_nonzero(support)),
        "operator_area_million_km2": float(np.sum(area_km2[support]) / 1.0e6),
        "cell_area_method": "PSC heff_for_volume.f scalar-cell metrics: DXT=0.5*(HTN+next-j HTN), DYT=0.5*(HTE+next-i HTE), area=DXT*DYT km2",
        "source_files_sha256": source_hashes,
        "processed_file_sha256": sha256_file(output),
        "output_units": "million_km3",
        "sanity_check": sanity,
        "is_direct_satellite_observation": False,
        "generated_utc": utc_now(),
    }
    (PHYSICAL_DIR / "piomas_v2_1_metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

def _earthdata_login():
    try:
        import earthaccess
    except ImportError as exc:
        raise RuntimeError("earthaccess is required. Install requirements-validation-data.txt") from exc
    return earthaccess, earthaccess.login(strategy="all", persist=False)


def _netcdf_links_from_granule(granule) -> list[str]:
    """Return only downloadable NetCDF payload links for an Earthdata granule."""
    links: list[str] = []
    for access in ("external", None):
        try:
            values = granule.data_links(access=access) if access is not None else granule.data_links()
        except Exception:
            continue
        for value in values or []:
            path = urlparse(str(value)).path.lower()
            if path.endswith((".nc", ".nc4", ".cdf")):
                links.append(str(value))
        if links:
            break
    return list(dict.fromkeys(links))


def _earthdata_download_selected(short_name: str, version: str, raw_dir: Path, years: range, month: int = 3) -> list[Path]:
    """Download one representative monthly NetCDF payload per requested year.

    Earthdata granules may advertise metadata/browse sidecars as well as the
    scientific file.  We explicitly select NetCDF data links and verify the
    downloaded file signature before returning it to a processor.
    """
    earthaccess, _ = _earthdata_login()
    raw_dir.mkdir(parents=True, exist_ok=True)
    selected: list[Path] = []
    for year in years:
        start = f"{year:04d}-{month:02d}-01"
        end = f"{year:04d}-{month:02d}-31"
        granules = earthaccess.search_data(
            short_name=short_name, version=version, temporal=(start, end)
        )
        if not granules:
            continue
        granule = granules[len(granules) // 2]
        links = _netcdf_links_from_granule(granule)
        downloaded: list[Path] = []
        if links:
            # A monthly granule should have one scientific NetCDF payload.  If
            # multiple are advertised, process every verified NetCDF file.
            for link in links:
                downloaded.extend(
                    Path(path)
                    for path in earthaccess.download([link], local_path=str(raw_dir))
                )
        else:
            downloaded.extend(
                Path(path)
                for path in earthaccess.download([granule], local_path=str(raw_dir))
            )

        verified = [path for path in downloaded if path.exists() and _is_netcdf_file(path)]
        if not verified:
            details = ", ".join(path.name for path in downloaded) or "no files returned"
            raise RuntimeError(
                f"Earthdata returned no valid NetCDF payload for {short_name} "
                f"{year:04d}-{month:02d}; downloaded: {details}"
            )
        selected.extend(verified)
    return list(dict.fromkeys(selected))


def _satellite_weighted_thickness(
    paths: Iterable[Path],
    *,
    source_id: str,
    source_label: str,
    output_name: str,
    metadata_name: str,
    operator_path: Path,
    thickness_names: list[str],
    concentration_names: list[str],
    epsg: int,
    min_concentration: float,
    max_latitude_deg: float | None,
    dataset_id: str,
    version: str,
    doi: str,
) -> None:
    rows: list[dict] = []
    used: list[Path] = []
    years: list[int] = []
    months: list[int] = []
    weights: list[np.ndarray] = []
    geometry_mask: np.ndarray | None = None
    operator_lat: np.ndarray | None = None
    operator_lon: np.ndarray | None = None
    operator_area: np.ndarray | None = None
    thickness_variable_names: set[str] = set()
    concentration_variable_names: set[str] = set()

    for path in sorted(paths):
        with _open_dataset(path) as ds:
            date = _dataset_date(ds, path)
            if date is None or date[1] != 3:
                continue
            thickness_var = _find_variable(ds, thickness_names, ("ice", "thickness"))
            concentration_var = _find_variable(ds, concentration_names, ("ice", "conc"))
            thickness = np.squeeze(_numeric_array(thickness_var.values))
            concentration = _concentration_fraction(concentration_var)
            if thickness.ndim == 3:
                thickness = thickness[0]
            if concentration.ndim == 3:
                concentration = concentration[0]
            if thickness.ndim != 2 or concentration.shape != thickness.shape:
                continue
            area = projected_grid_cell_area_km2(ds, epsg, equal_area=False)
            if area is None:
                area = np.full(thickness.shape, 625.0, dtype=float)
            lat, lon = _lat_lon_from_dataset(ds, thickness.shape, epsg)
            if geometry_mask is None:
                geometry_mask = (
                    np.isfinite(lat)
                    & np.isfinite(lon)
                    & np.isfinite(area)
                    & (area > 0.0)
                )
                if max_latitude_deg is not None:
                    geometry_mask &= lat <= float(max_latitude_deg)
                operator_lat = lat[geometry_mask]
                operator_lon = lon[geometry_mask]
                operator_area = area[geometry_mask]
            else:
                if thickness.shape != geometry_mask.shape:
                    raise ValueError(f"Satellite grid shape changed in {path.name}")
                if not np.allclose(lat[geometry_mask], operator_lat, atol=1.0e-5, equal_nan=False):
                    raise ValueError(f"Satellite latitude grid changed in {path.name}")
                wrapped = ((lon[geometry_mask] - operator_lon + 180.0) % 360.0) - 180.0
                if not np.allclose(wrapped, 0.0, atol=1.0e-5, equal_nan=False):
                    raise ValueError(f"Satellite longitude grid changed in {path.name}")

            valid = (
                geometry_mask
                & np.isfinite(thickness)
                & (thickness >= 0.0)
                & np.isfinite(concentration)
                & (concentration >= float(min_concentration))
            )
            weight_full = np.where(valid, concentration * area, 0.0)
            total = float(np.sum(weight_full))
            if total <= 0.0:
                continue
            mean = float(np.sum(np.where(valid, thickness * weight_full, 0.0)) / total)
            rows.append({
                "year": date[0],
                "month": date[1],
                "mean_thickness_m": mean,
                "source": source_label,
                "source_file": path.name,
            })
            years.append(date[0])
            months.append(date[1])
            weights.append(weight_full[geometry_mask])
            used.append(path)
            thickness_variable_names.add(str(thickness_var.name))
            concentration_variable_names.add(str(concentration_var.name))

    if not rows or geometry_mask is None or operator_lat is None or operator_lon is None or operator_area is None:
        raise RuntimeError(f"No {source_label} March thickness records were produced")
    frame = pd.DataFrame(rows).sort_values(["year", "month"]).drop_duplicates(["year", "month"], keep="last")
    # Keep the exact same record ordering in CSV and temporal operator.
    order = np.lexsort((np.asarray(months), np.asarray(years)))
    years_arr = np.asarray(years, dtype=int)[order]
    months_arr = np.asarray(months, dtype=int)[order]
    weights_arr = np.asarray(weights, dtype=float)[order]
    unique = np.ones(len(years_arr), dtype=bool)
    if len(years_arr) > 1:
        unique[:-1] = (years_arr[:-1] != years_arr[1:]) | (months_arr[:-1] != months_arr[1:])
    years_arr = years_arr[unique]
    months_arr = months_arr[unique]
    weights_arr = weights_arr[unique]
    save_temporal_thickness_operator(
        operator_path,
        source_id=source_id,
        latitude_deg=operator_lat,
        longitude_deg=operator_lon,
        cell_area_km2=operator_area,
        years=years_arr,
        months=months_arr,
        observation_weight_km2=weights_arr,
    )
    output = PHYSICAL_DIR / output_name
    frame.to_csv(output, index=False)
    metadata = {
        "source_id": source_id,
        "dataset_id": dataset_id,
        "version": version,
        "doi": doi,
        "role": "development_informed_satellite_thickness_constraint",
        "months_used": [3],
        "thickness_variables_used": sorted(thickness_variable_names),
        "concentration_variables_used": sorted(concentration_variable_names),
        "minimum_concentration_fraction": min_concentration,
        "maximum_latitude_deg": max_latitude_deg,
        "mean_definition": (
            "concentration-and-cell-area weighted thickness over the exact valid satellite retrieval footprint"
        ),
        "model_comparison_rule": (
            "EGCM local ice thickness is sampled at identical cell centers and averaged with the identical per-record observation weights"
        ),
        "operator_file": operator_path.name,
        "operator_file_sha256": sha256_file(operator_path),
        "processed_file_sha256": sha256_file(output),
        "source_files_sha256": {path.name: sha256_file(path) for path in used},
        "generated_utc": utc_now(),
    }
    (PHYSICAL_DIR / metadata_name).write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def acquire_cryosat2() -> list[Path]:
    return _earthdata_download_selected(
        "RDEFT4", "1", RAW_ROOT / "cryosat2_rdeft4_v1", range(2011, datetime.now().year + 1), 3
    )


def process_cryosat2(paths: Iterable[Path] | None = None) -> None:
    files = sorted(paths or [
        path for path in (RAW_ROOT / "cryosat2_rdeft4_v1").iterdir()
        if path.is_file() and _is_netcdf_file(path)
    ]) if (paths is not None or (RAW_ROOT / "cryosat2_rdeft4_v1").exists()) else []
    _satellite_weighted_thickness(
        files,
        source_id="cryosat2_rdeft4_v1",
        source_label="CryoSat2_RDEFT4_v1",
        output_name="cryosat2_rdeft4_monthly.csv",
        metadata_name="cryosat2_rdeft4_v1_metadata.json",
        operator_path=CRYOSAT2_OPERATOR,
        thickness_names=["sea_ice_thickness", "ice_thickness", "thickness"],
        concentration_names=["ice_con", "sea_ice_conc", "sea_ice_concentration", "ice_concentration"],
        epsg=3413,
        min_concentration=0.70,
        max_latitude_deg=None,
        dataset_id="RDEFT4",
        version="1",
        doi="10.5067/96JO0KIFDAS8",
    )


def acquire_icesat2() -> list[Path]:
    return _earthdata_download_selected(
        "IS2SITMOGR4", "4", RAW_ROOT / "icesat2_is2sitmogr4_v4", range(2019, datetime.now().year + 1), 3
    )


def process_icesat2(paths: Iterable[Path] | None = None) -> None:
    files = sorted(paths or [
        path for path in (RAW_ROOT / "icesat2_is2sitmogr4_v4").iterdir()
        if path.is_file() and _is_netcdf_file(path)
    ]) if (paths is not None or (RAW_ROOT / "icesat2_is2sitmogr4_v4").exists()) else []
    _satellite_weighted_thickness(
        files,
        source_id="icesat2_is2sitmogr4_v4",
        source_label="ICESat2_IS2SITMOGR4_v4",
        output_name="icesat2_is2sitmogr4_monthly.csv",
        metadata_name="icesat2_is2sitmogr4_v4_metadata.json",
        operator_path=ICESAT2_OPERATOR,
        # Primary field first; interpolated/smoothed thickness is not the default target.
        thickness_names=["ice_thickness", "sea_ice_thickness", "ice_thickness_int"],
        concentration_names=["sea_ice_conc", "sea_ice_concentration", "ice_concentration", "ice_con"],
        epsg=3411,
        min_concentration=0.15,
        max_latitude_deg=88.0,
        dataset_id="IS2SITMOGR4",
        version="4",
        doi="10.5067/TXDHDJ1JT0CG",
    )


def _thredds_catalog_files(catalog_url: str, visited: set[str] | None = None) -> list[str]:
    visited = visited or set()
    if catalog_url in visited:
        return []
    visited.add(catalog_url)
    response = SESSION.get(catalog_url, timeout=120)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    namespace = {"t": "http://www.unidata.ucar.edu/namespaces/thredds/InvCatalog/v1.0"}
    xlink = "{http://www.w3.org/1999/xlink}href"
    paths: list[str] = []
    for dataset in root.findall(".//t:dataset", namespace):
        url_path = dataset.attrib.get("urlPath")
        if url_path and url_path.lower().endswith((".nc", ".nc4")):
            paths.append(url_path)
    for reference in root.findall(".//t:catalogRef", namespace):
        href = reference.attrib.get(xlink)
        if href:
            paths.extend(_thredds_catalog_files(urljoin(catalog_url, href), visited))
    return paths


def acquire_osi_saf(overwrite: bool = False) -> list[Path]:
    raw_dir = RAW_ROOT / "osi_saf_osi450a1_v3_1"
    paths: list[Path] = []
    for url_path in sorted(set(_thredds_catalog_files(OSI_CATALOG))):
        name = Path(url_path).name
        lower = name.lower()
        date = _date_from_filename(Path(name))
        if date is None or date[1] not in (3, 9):
            continue
        if "nh" not in lower and "north" not in lower:
            continue
        if "monthly" not in lower and "month" not in lower and not re.search(r"\d{6}\.nc", lower):
            continue
        paths.append(_download(OSI_FILESERVER_PREFIX + url_path.lstrip("/"), raw_dir / name, overwrite=overwrite))
    if not paths:
        raise RuntimeError(
            "No OSI-450-a1 March/September files were found. Place monthly northern NetCDF files in "
            f"{raw_dir.relative_to(ROOT)} and run --process-existing."
        )
    return paths


def _is_osi_monthly_file(path: Path) -> bool:
    lower = path.name.lower()
    return bool(
        "monthly" in lower
        or "month" in lower
        or re.search(r"(?:19|20)\d{4}\.nc(?:4)?$", lower)
    )


def process_osi_saf(paths: Iterable[Path] | None = None) -> None:
    candidates = sorted(paths or (RAW_ROOT / "osi_saf_osi450a1_v3_1").glob("*.nc*"))
    files = [Path(path) for path in candidates if _is_osi_monthly_file(Path(path))]
    if not files:
        raise FileNotFoundError(
            "No OSI-450-a1 official monthly-mean NetCDF files are available; daily files are intentionally not substituted"
        )
    _process_fixed_mask_concentration(
        files,
        OSI_SAF_DIR,
        operator_path=OSI_SAF_OPERATOR,
        source_id="osi_saf_osi450a1_v3_1",
        product="EUMETSAT OSI SAF Global Sea Ice Concentration CDR OSI-450-a1",
        version="3.1",
        epsg=6931,
        equal_area=True,
        metadata_extra={
            "doi": "10.15770/EUM_SAF_OSI_0023",
            "role": "development_fixed_mask_area_cross_dataset_diagnostic",
            "used_for_calibration": False,
            "temporal_sampling": "official_monthly_mean_files_only",
            "daily_files_accepted_as_monthly": False,
        },
        crosscheck=True,
    )


def _legacy_earthdata_credentials() -> tuple[str, str]:
    """Return in-memory Earthdata credentials for the legacy NSIDC DAAC.

    NSIDC-0611 is served from the legacy ``daacdata.apps.nsidc.org`` archive.
    NASA documents this path with Earthdata username/password authentication
    plus session cookies; bearer-token authentication is not used here.
    Credentials are supplied only through the current process environment and
    are never written into the project.
    """
    username = os.environ.get("EARTHDATA_USERNAME", "").strip()
    password = os.environ.get("EARTHDATA_PASSWORD", "")
    if not username or not password:
        raise RuntimeError(
            "NSIDC-0611 v4 uses the legacy NSIDC DAAC HTTPS archive and requires "
            "EARTHDATA_USERNAME and EARTHDATA_PASSWORD in the current process. "
            "Run the supplied PowerShell acquisition script so they are prompted "
            "securely and kept in memory only."
        )
    return username, password


_LEGACY_EARTHDATA_OPENER = None
_LEGACY_EARTHDATA_OPENER_IDENTITY: tuple[str, str] | None = None


def _legacy_earthdata_opener():
    """Create an in-memory cookie-authenticated opener for legacy DAAC files."""
    global _LEGACY_EARTHDATA_OPENER, _LEGACY_EARTHDATA_OPENER_IDENTITY
    username, password = _legacy_earthdata_credentials()
    identity = (username, password)
    if _LEGACY_EARTHDATA_OPENER is not None and _LEGACY_EARTHDATA_OPENER_IDENTITY == identity:
        return _LEGACY_EARTHDATA_OPENER

    password_manager = urllib_request.HTTPPasswordMgrWithDefaultRealm()
    password_manager.add_password(
        None, "https://urs.earthdata.nasa.gov", username, password
    )
    cookie_jar = CookieJar()
    opener = urllib_request.build_opener(
        urllib_request.HTTPBasicAuthHandler(password_manager),
        urllib_request.HTTPCookieProcessor(cookie_jar),
    )
    opener.addheaders = [(
        "User-Agent", "EGCM-Arctic-Validation/2026 scientific reproducibility"
    )]
    _LEGACY_EARTHDATA_OPENER = opener
    _LEGACY_EARTHDATA_OPENER_IDENTITY = identity
    return opener


def _download_legacy_earthdata_https(
    url: str, destination: Path, *, overwrite: bool = False
) -> Path:
    """Download one NSIDC legacy-archive NetCDF using EDL cookies/basic auth."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if (
        destination.exists()
        and destination.stat().st_size > 0
        and _is_netcdf_file(destination)
        and not overwrite
    ):
        return destination

    temporary = destination.with_suffix(destination.suffix + ".part")
    temporary.unlink(missing_ok=True)
    opener = _legacy_earthdata_opener()
    try:
        with opener.open(url, timeout=180) as response:
            final_url = response.geturl()
            final_host = urlparse(final_url).hostname or ""
            if final_host.endswith("urs.earthdata.nasa.gov"):
                raise RuntimeError(
                    "Earthdata Login did not authorize the NSIDC legacy archive request. "
                    "Check the Earthdata username/password and ensure the NSIDC DAAC "
                    "application is authorized for the account."
                )
            with temporary.open("wb") as handle:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
    except HTTPError as exc:
        temporary.unlink(missing_ok=True)
        if exc.code in (401, 403):
            raise RuntimeError(
                "Earthdata Login rejected access to the NSIDC legacy archive. "
                "Verify EARTHDATA_USERNAME/EARTHDATA_PASSWORD and authorize the "
                "NSIDC DAAC application in Earthdata Login."
            ) from exc
        raise
    except URLError as exc:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"NSIDC legacy archive download failed for {url}: {exc}") from exc

    if not _is_netcdf_file(temporary):
        signature = _file_signature(temporary, 32) if temporary.exists() else b""
        temporary.unlink(missing_ok=True)
        raise RuntimeError(
            f"NSIDC DAAC returned a non-NetCDF payload for {destination.name} "
            f"(signature={signature!r})."
        )
    temporary.replace(destination)
    return destination


def _nsidc_ice_age_filename(year: int) -> str:
    return f"iceage_nh_12.5km_{year:04d}0101_{year:04d}1231_v4.1.nc"


def acquire_ice_age() -> list[Path]:
    """Acquire NSIDC-0611 v4 from the NSIDC DAAC HTTPS file system.

    CMR currently lists the collection but not its granules, so earthaccess
    search_data() cannot discover these files. The official v4/v4.1 archive
    serves the annual NetCDF files from its ``data/`` directory and uses the
    legacy Earthdata Login username/password + cookie authentication flow.
    """
    raw_dir = RAW_ROOT / "nsidc_0611_v4"
    raw_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for year in range(NSIDC_ICE_AGE_START_YEAR, NSIDC_ICE_AGE_END_YEAR + 1):
        filename = _nsidc_ice_age_filename(year)
        destination = raw_dir / filename
        url = urljoin(NSIDC_ICE_AGE_HTTPS_BASE, filename)
        paths.append(_download_legacy_earthdata_https(url, destination))
    if not paths:
        raise RuntimeError(
            "No NSIDC-0611 v4 annual NetCDF files were acquired. Place files in "
            f"{raw_dir.relative_to(ROOT)} and run --process-existing."
        )
    return paths


def _move_time_first(array: np.ndarray, dims: list[str]) -> np.ndarray:
    if array.ndim < 3:
        return array
    time_axis = next((i for i, name in enumerate(dims) if "time" in name.lower() or "week" in name.lower()), 0)
    return np.moveaxis(array, time_axis, 0) if time_axis != 0 else array


def ice_age_masks(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return valid sea-ice and multiyear masks for NSIDC-0611 v4 categories."""
    array = np.asarray(values, dtype=float)
    rounded = np.rint(np.where(np.isfinite(array), array, 0.0)).astype(np.int16)
    integer_like = np.isfinite(array) & np.isclose(array, rounded, atol=1.0e-6)
    # Valid sea-ice age classes are 1..16. Codes 20 (land) and 21 (age not calculated) are excluded.
    ice = integer_like & (rounded >= 1) & (rounded <= 16)
    multiyear = ice & (rounded >= 2)
    return ice, multiyear


def process_ice_age(paths: Iterable[Path] | None = None) -> None:
    files = sorted(paths or (RAW_ROOT / "nsidc_0611_v4").glob("*.nc*"))
    rows: list[dict] = []
    source_hashes: dict[str, str] = {}
    for path in files:
        with _open_dataset(path) as ds:
            variable = _find_variable(ds, ["age_of_sea_ice", "sea_ice_age", "ice_age"], ("age",))
            array = _move_time_first(_numeric_array(variable.values), list(variable.dims))
            if array.ndim == 2:
                array = array[None, ...]
            if array.ndim != 3:
                continue
            if "time" in ds.variables and len(np.asarray(ds["time"].values).ravel()) == array.shape[0]:
                stamps = [pd.Timestamp(value) for value in np.asarray(ds["time"].values).ravel()]
            else:
                year_match = re.search(r"((?:19|20)\d{2})", path.name)
                if not year_match:
                    continue
                year = int(year_match.group(1))
                stamps = [pd.Timestamp(year=year, month=1, day=1) + pd.Timedelta(days=7 * i) for i in range(array.shape[0])]
            source_hashes[path.name] = sha256_file(path)
            for month in (3, 9):
                indices = [i for i, stamp in enumerate(stamps) if stamp.month == month]
                fractions: list[float] = []
                for i in indices:
                    ice, multiyear = ice_age_masks(array[i])
                    if np.any(ice):
                        fractions.append(float(np.count_nonzero(multiyear) / np.count_nonzero(ice)))
                if fractions:
                    rows.append({
                        "year": int(stamps[indices[0]].year),
                        "month": month,
                        "multiyear_ice_fraction_of_ice": float(np.mean(fractions)),
                        "source": "NSIDC-0611_v4",
                        "source_file": path.name,
                    })
    if not rows:
        raise RuntimeError("No NSIDC-0611 March/September sea-ice-age records were produced")
    ICE_AGE_DIR.mkdir(parents=True, exist_ok=True)
    output = ICE_AGE_DIR / "multiyear_ice_annual.csv"
    frame = pd.DataFrame(rows).groupby(["year", "month"], as_index=False).agg({
        "multiyear_ice_fraction_of_ice": "mean",
        "source": "first",
        "source_file": "first",
    })
    frame.to_csv(output, index=False)
    metadata = {
        "source_id": "nsidc_0611_v4",
        "dataset_id": "NSIDC-0611",
        "version": "4",
        "doi": "10.5067/UTAV7490FEPB",
        "role": "multiyear_ice_structural_diagnostic",
        "months_used": [3, 9],
        "valid_ice_age_codes": "1..16",
        "excluded_codes": {"20": "land", "21": "age_not_calculated"},
        "multiyear_definition": "integer sea-ice-age categories 2..16 divided by categories 1..16",
        "direct_equivalence_to_model_2m_thickness_claimed": False,
        "processed_file_sha256": sha256_file(output),
        "source_files_sha256": source_hashes,
        "generated_utc": utc_now(),
    }
    (ICE_AGE_DIR / "METADATA.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_physical_manifest() -> None:
    manifest = {
        "generated_utc": utc_now(),
        "rule": "source-separated physical evidence; each comparison uses its explicit observation operator",
        "sources": {},
    }
    for source_id, csv_name, operator_name, metadata_name in (
        ("piomas_v2_1", "piomas_volume_monthly.csv", PIOMAS_OPERATOR.name, "piomas_v2_1_metadata.json"),
        ("cryosat2_rdeft4_v1", "cryosat2_rdeft4_monthly.csv", CRYOSAT2_OPERATOR.name, "cryosat2_rdeft4_v1_metadata.json"),
        ("icesat2_is2sitmogr4_v4", "icesat2_is2sitmogr4_monthly.csv", ICESAT2_OPERATOR.name, "icesat2_is2sitmogr4_v4_metadata.json"),
    ):
        manifest["sources"][source_id] = {
            "data_file": csv_name,
            "operator_file": operator_name,
            "metadata_file": metadata_name,
            "data_sha256": sha256_file(PHYSICAL_DIR / csv_name) if (PHYSICAL_DIR / csv_name).exists() else None,
            "operator_sha256": sha256_file(PHYSICAL_DIR / operator_name) if (PHYSICAL_DIR / operator_name).exists() else None,
            "metadata_sha256": sha256_file(PHYSICAL_DIR / metadata_name) if (PHYSICAL_DIR / metadata_name).exists() else None,
        }
    PHYSICAL_DIR.mkdir(parents=True, exist_ok=True)
    (PHYSICAL_DIR / "SOURCES.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def process_existing() -> dict[str, str]:
    results: dict[str, str] = {}
    processors = (
        ("nsidc_g02202_v6", process_g02202),
        ("piomas_v2_1", process_piomas),
        ("cryosat2_rdeft4_v1", process_cryosat2),
        ("icesat2_is2sitmogr4_v4", process_icesat2),
        ("osi_saf_osi450a1_v3_1", process_osi_saf),
        ("nsidc_0611_v4", process_ice_age),
    )
    for source_id, processor in processors:
        try:
            processor()
            results[source_id] = "processed"
        except (FileNotFoundError, RuntimeError, ValueError, KeyError) as exc:
            results[source_id] = f"not_processed: {exc}"
    _write_physical_manifest()
    write_stack_status()
    return results


def acquire_open(overwrite: bool = False) -> None:
    process_g02202(acquire_g02202(overwrite=overwrite))
    process_piomas(acquire_piomas(overwrite=overwrite))
    process_osi_saf(acquire_osi_saf(overwrite=overwrite))
    _write_physical_manifest()
    write_stack_status()


def refresh_piomas_osi(overwrite: bool = False) -> None:
    """Refresh only the two public products affected by the 2026-08-09 data fixes."""
    process_piomas(acquire_piomas(overwrite=overwrite))
    osi_raw_dir = RAW_ROOT / "osi_saf_osi450a1_v3_1"
    existing_osi = sorted(osi_raw_dir.glob("*.nc"))
    if existing_osi:
        process_osi_saf(existing_osi)
    else:
        process_osi_saf(acquire_osi_saf(overwrite=overwrite))
    _write_physical_manifest()
    write_stack_status()


def acquire_earthdata() -> dict[str, str]:
    """Acquire Earthdata-backed products without making NSIDC-0611 a hard blocker.

    CryoSat-2 and ICESat-2 are required source-separated thickness constraints.
    They are development-informed and are not labelled independent validation.
    NSIDC-0611 is a structural multiyear-ice diagnostic hosted on a legacy
    archive that may require separate EDL application authorization.  The
    scientific calibration can proceed without that diagnostic, so a missing or
    unauthorized NSIDC-0611 download is recorded and reported rather than
    aborting the entire five-source core stack.
    """
    results: dict[str, str] = {}

    process_cryosat2(acquire_cryosat2())
    results["cryosat2_rdeft4_v1"] = "processed"

    process_icesat2(acquire_icesat2())
    results["icesat2_is2sitmogr4_v4"] = "processed"

    username = os.environ.get("EARTHDATA_USERNAME", "").strip()
    password = os.environ.get("EARTHDATA_PASSWORD", "")
    if username and password:
        try:
            process_ice_age(acquire_ice_age())
            results["nsidc_0611_v4"] = "processed"
        except (FileNotFoundError, RuntimeError, ValueError, KeyError, HTTPError, URLError) as exc:
            results["nsidc_0611_v4"] = f"not_processed: {exc}"
            print(
                "WARNING: NSIDC-0611 sea-ice age could not be acquired from the legacy archive. "
                "This source is a structural diagnostic and will remain explicitly missing; "
                "the five-source core bundle will still be produced.\n"
                f"Reason: {exc}",
                file=sys.stderr,
            )
    else:
        results["nsidc_0611_v4"] = "not_attempted: legacy Earthdata username/password not supplied"
        print(
            "NOTE: NSIDC-0611 sea-ice age was not attempted because legacy Earthdata "
            "credentials were not supplied. The five-source core bundle can still be used "
            "for recalibration; the structural ice-age diagnostic remains pending.",
            file=sys.stderr,
        )

    _write_physical_manifest()
    write_stack_status()
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Acquire/process all six products")
    group.add_argument("--open-only", action="store_true", help="Acquire G02202, PIOMAS, OSI SAF")
    group.add_argument("--earthdata-only", action="store_true", help="Acquire CryoSat-2, ICESat-2, NSIDC ice age")
    group.add_argument("--process-existing", action="store_true", help="Process files already present in raw directories")
    group.add_argument("--refresh-piomas-osi", action="store_true", help="Refresh only corrected PIOMAS and OSI SAF public evidence")
    parser.add_argument("--overwrite", action="store_true", help="Redownload public source files")
    args = parser.parse_args()

    if args.process_existing:
        print(json.dumps(process_existing(), indent=2, sort_keys=True))
    elif args.refresh_piomas_osi:
        refresh_piomas_osi(overwrite=args.overwrite)
        print(write_stack_status().read_text(encoding="utf-8"), end="")
    else:
        if args.all or args.open_only:
            acquire_open(overwrite=args.overwrite)
        if args.all or args.earthdata_only:
            acquire_earthdata()
        print(write_stack_status().read_text(encoding="utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
