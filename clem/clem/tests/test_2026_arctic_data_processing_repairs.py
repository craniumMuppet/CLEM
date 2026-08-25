from __future__ import annotations

import gzip
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from arctic_validation_stack import source_status
from tools.acquire_arctic_validation_stack import (
    _is_osi_monthly_file,
    _projected_axis_values_meters,
    _read_piomas_heff_binary,
    _validate_piomas_common_domain,
    projected_grid_cell_area_km2,
)


def test_osi_projected_kilometre_axes_become_625_km2_cells() -> None:
    ds = xr.Dataset(coords={
        "x": xr.DataArray(np.array([-25.0, 0.0, 25.0]), dims=("x",), attrs={"units": "km"}),
        "y": xr.DataArray(np.array([-25.0, 0.0, 25.0]), dims=("y",), attrs={"units": "km"}),
    })
    area = projected_grid_cell_area_km2(ds, epsg=6931, equal_area=True)
    assert area is not None
    assert np.allclose(area, 625.0)
    assert np.allclose(_projected_axis_values_meters(ds["x"]), [-25000.0, 0.0, 25000.0])


def test_piomas_flat_binary_reader_detects_little_and_big_endian(tmp_path: Path) -> None:
    values = np.zeros((2, 120, 360), dtype=np.float32)
    values[0, :, :] = 1.25
    values[1, :, :] = 2.50
    for endian in ("<", ">"):
        path = tmp_path / f"heff.H2000.{endian == '>'}.gz"
        payload = values.astype(endian + "f4").tobytes(order="C")
        with gzip.open(path, "wb") as handle:
            handle.write(payload)
        decoded = _read_piomas_heff_binary(path)
        assert decoded.shape == values.shape
        assert np.allclose(decoded, values)


def test_piomas_sanity_check_rejects_spurious_background() -> None:
    bad = pd.DataFrame({
        "year": [1979, 1979],
        "month": [1, 2],
        "volume_million_km3": [0.87, 0.88],
    })
    try:
        _validate_piomas_common_domain(bad)
    except RuntimeError as exc:
        assert "exceeds 0.1" in str(exc)
    else:
        raise AssertionError("spurious-background PIOMAS evidence must fail closed")


def test_piomas_source_is_either_corrected_or_fail_closed() -> None:
    status = source_status("piomas_v2_1")
    if status["available"]:
        metadata = status["metadata"] or {}
        assert metadata.get("source_format") == "official_PSC_flat_binary_float32"
        assert metadata.get("published_scalar_total_volume_used") is False
        assert float(metadata["sanity_check"]["max_common_domain_volume_million_km3"]) <= 0.1
    else:
        assert status["missing_paths"] or status["sanity_errors"]


def test_osi_monthly_selector_rejects_daily_files() -> None:
    assert _is_osi_monthly_file(Path("ice_conc_nh_ease2-250_cdr-v3p1_197903.nc"))
    assert not _is_osi_monthly_file(Path("ice_conc_nh_ease2-250_cdr-v3p1_197903311200.nc"))


def test_osi_source_is_either_corrected_monthly_or_fail_closed() -> None:
    status = source_status("osi_saf_osi450a1_v3_1")
    if status["available"]:
        metadata = status["metadata"] or {}
        assert metadata.get("temporal_sampling") == "official_monthly_mean_files_only"
        assert metadata.get("daily_files_accepted_as_monthly") is False
        assert status["sanity_errors"] == []
    else:
        assert status["missing_paths"] or status["sanity_errors"]
