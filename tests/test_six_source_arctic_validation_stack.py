"""Focused regression coverage for the six-source Arctic observation stack."""
from __future__ import annotations

from pathlib import Path
import zipfile

import numpy as np
import pandas as pd

from arctic_observation_operator import (
    load_spatial_operator,
    load_temporal_thickness_operator,
    model_fixed_mask_area_extent,
    model_mean_thickness_on_temporal_operator,
    model_volume_on_operator,
    prepare_model_grid_sampler,
    save_spatial_operator,
    save_temporal_thickness_operator,
)
import arctic_validation_stack as validation_stack
from arctic_validation_stack import SOURCES, source_status, validation_stack_status
from sea_ice_validation import evaluate_physical_constraints, evaluate_result, model_monthly_records
from tools.acquire_arctic_validation_stack import (
    _is_netcdf_file,
    _netcdf_links_from_granule,
    _open_dataset,
    ice_age_masks,
)
from tools.export_arctic_validation_bundle import export_bundle

ROOT = Path(__file__).resolve().parents[1]


def test_registry_has_exact_six_products_and_explicit_spatial_operators() -> None:
    assert set(SOURCES) == {
        "nsidc_g02202_v6",
        "piomas_v2_1",
        "cryosat2_rdeft4_v1",
        "icesat2_is2sitmogr4_v4",
        "osi_saf_osi450a1_v3_1",
        "nsidc_0611_v4",
    }
    assert SOURCES["nsidc_g02202_v6"].calibrated_to is True
    assert SOURCES["osi_saf_osi450a1_v3_1"].calibrated_to is False
    for source_id in (
        "nsidc_g02202_v6",
        "piomas_v2_1",
        "cryosat2_rdeft4_v1",
        "icesat2_is2sitmogr4_v4",
        "osi_saf_osi450a1_v3_1",
    ):
        assert any(path.endswith(".npz") for path in SOURCES[source_id].required_paths)


def test_malformed_piomas_common_domain_evidence_is_rejected_fail_closed(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path
    physical = root / "data" / "validation" / "sea_ice_physical"
    physical.mkdir(parents=True)
    pd.DataFrame({"year": [2000], "month": [3], "volume_million_km3": [0.88]}).to_csv(
        physical / "piomas_volume_monthly.csv", index=False
    )
    np.savez_compressed(
        physical / "piomas_common_domain_operator.npz",
        source_id=np.asarray("piomas_v2_1"),
        lat=np.asarray([70.0]), lon=np.asarray([0.0]), cell_area_km2=np.asarray([1.0]),
    )
    (physical / "piomas_v2_1_metadata.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(validation_stack, "ROOT", root)
    monkeypatch.setattr(validation_stack, "PHYSICAL_DIR", physical)
    status = validation_stack.source_status("piomas_v2_1")
    assert status["available"] is False
    assert status["missing_paths"] == []
    assert any("unit/background error" in item for item in status["sanity_errors"])


def test_physical_gate_stays_closed_without_source_specific_operators() -> None:
    class Result:
        dataframe = pd.DataFrame({
            "year": [1979 + (3 - 0.5) / 12.0, 1979 + (9 - 0.5) / 12.0],
            "global_surface_warming_c": [0.0, 0.0],
        })

        def northern_sea_ice_area_extent_at_index(self, index):
            return {
                "native_northern_ice_area_million_km2": 10.0,
                "northern_hemisphere_sea_ice_area_million_km2": 10.0,
                "northern_hemisphere_sea_ice_thresholded_area_million_km2": 9.0,
                "northern_hemisphere_sea_ice_extent_million_km2": 11.0,
            }

        def northern_sea_ice_volume_thickness_at_index(self, index):
            return {
                "northern_hemisphere_sea_ice_volume_million_km3": 0.02,
                "northern_hemisphere_mean_ice_thickness_m": 2.0,
                "northern_hemisphere_thick_ice_area_million_km2": 4.0,
                "northern_hemisphere_thick_ice_area_fraction": 0.4,
            }

    records = model_monthly_records(Result(), range(1979, 1980))
    physical = evaluate_physical_constraints(records)
    assert physical["available"] is True  # satellite evidence exists, but the required PIOMAS stream is invalid
    assert physical["complete"] is False
    assert physical["passed"] is False


def test_stack_status_is_truthful_with_repaired_core_five_evidence() -> None:
    status = validation_stack_status()
    assert status["required_source_count"] == 6
    assert set(status["available_sources"]) == {
        "nsidc_g02202_v6",
        "piomas_v2_1",
        "cryosat2_rdeft4_v1",
        "icesat2_is2sitmogr4_v4",
        "osi_saf_osi450a1_v3_1",
        "nsidc_0611_v4",
    }
    assert status["sources"]["piomas_v2_1"]["available"] is True
    assert status["sources"]["osi_saf_osi450a1_v3_1"]["available"] is True
    assert status["sources"]["nsidc_0611_v4"]["available"] is True
    assert status["all_six_observational_products_available"] is True
    assert status["core_five_calibration_validation_stack_complete"] is True


def test_ice_age_codes_exclude_land_and_unclassified_cells() -> None:
    values = np.array([[0, 1, 2, 16, 20, 21, np.nan]], dtype=float)
    ice, multiyear = ice_age_masks(values)
    assert ice.tolist() == [[False, True, True, True, False, False, False]]
    assert multiyear.tolist() == [[False, False, True, True, False, False, False]]


class _OperatorResult:
    class Grid:
        lat2d = np.array([[60.0, 60.0], [70.0, 70.0]])
        lon2d = np.array([[0.0, 90.0], [0.0, 90.0]])
        ocean_fraction_map = np.ones((2, 2), dtype=float)

    grid = Grid()

    def sea_ice_concentration_map_at_index(self, index):
        return np.array([[0.10, 0.50], [0.80, 1.00]], dtype=float)

    def arctic_local_ice_thickness_map_at_index(self, index):
        return np.array([[1.0, 2.0], [3.0, 4.0]], dtype=float)


def test_exact_spatial_operator_controls_area_and_volume(tmp_path: Path) -> None:
    path = tmp_path / "operator.npz"
    save_spatial_operator(
        path,
        source_id="synthetic",
        latitude_deg=np.array([60.0, 70.0, 70.0]),
        longitude_deg=np.array([90.0, 0.0, 90.0]),
        cell_area_km2=np.array([100.0, 200.0, 300.0]),
    )
    operator = load_spatial_operator(path)
    result = _OperatorResult()
    sampler = prepare_model_grid_sampler(result, operator.latitude_deg, operator.longitude_deg)
    area = model_fixed_mask_area_extent(result, 0, operator, sampler)
    # 0.5*100 + 0.8*200 + 1.0*300 = 510 km2.
    assert np.isclose(area["area_million_km2"], 510.0 / 1.0e6)
    assert np.isclose(area["extent_million_km2"], 600.0 / 1.0e6)
    # Equivalent thickness = concentration * local thickness on identical cells.
    expected_volume = (0.5 * 2.0 * 100.0 + 0.8 * 3.0 * 200.0 + 1.0 * 4.0 * 300.0) * 1.0e-9
    assert np.isclose(model_volume_on_operator(result, 0, operator, sampler), expected_volume)


def test_satellite_temporal_operator_uses_record_specific_concentration_weights(tmp_path: Path) -> None:
    path = tmp_path / "thickness_operator.npz"
    save_temporal_thickness_operator(
        path,
        source_id="satellite",
        latitude_deg=np.array([60.0, 70.0, 70.0]),
        longitude_deg=np.array([90.0, 0.0, 90.0]),
        cell_area_km2=np.array([100.0, 200.0, 300.0]),
        years=np.array([2020]),
        months=np.array([3]),
        observation_weight_km2=np.array([[10.0, 20.0, 70.0]]),
    )
    operator = load_temporal_thickness_operator(path)
    result = _OperatorResult()
    sampler = prepare_model_grid_sampler(result, operator.latitude_deg, operator.longitude_deg)
    value = model_mean_thickness_on_temporal_operator(
        result, 0, operator, sampler, year=2020, month=3
    )
    expected = (2.0 * 10.0 + 3.0 * 20.0 + 4.0 * 70.0) / 100.0
    assert np.isclose(value, expected)


def test_acquisition_script_uses_primary_icesat2_field_and_piomas_gridded_heff() -> None:
    source = (ROOT / "tools/acquire_arctic_validation_stack.py").read_text(encoding="utf-8")
    assert 'thickness_names=["ice_thickness", "sea_ice_thickness", "ice_thickness_int"]' in source
    assert "PIOMAS_HEFF_BASE" in source
    assert "published_scalar_total_volume_used\": False" in source
    assert "polehole_bitmask" in source
    assert "persist=False" in source
    assert 'os.environ.get("EARTHDATA_PASSWORD"' in source
    assert "HTTPPasswordMgrWithDefaultRealm" in source
    assert "HTTPCookieProcessor" in source
    assert "write_text(password" not in source.lower()


class _SyntheticResult:
    def __init__(self) -> None:
        years = []
        for year in range(1979, 2027):
            for month in (3, 9):
                years.append(year + (month - 0.5) / 12.0)
        self.dataframe = pd.DataFrame({
            "year": years,
            "global_surface_warming_c": np.linspace(0.0, 1.4, len(years)),
        })

    def northern_sea_ice_area_extent_at_index(self, index):
        year = float(self.dataframe.iloc[index]["year"])
        month = 3 if (year % 1.0) < 0.5 else 9
        decline = 0.05 * (int(year) - 1979)
        area = (12.0 if month == 3 else 6.0) - decline
        extent = (15.5 if month == 3 else 8.0) - decline
        return {
            "native_northern_ice_area_million_km2": area,
            "northern_hemisphere_sea_ice_area_million_km2": area,
            "northern_hemisphere_sea_ice_thresholded_area_million_km2": area,
            "northern_hemisphere_sea_ice_extent_million_km2": extent,
        }

    def northern_sea_ice_volume_thickness_at_index(self, index):
        return {
            "northern_hemisphere_sea_ice_volume_million_km3": 0.020,
            "northern_hemisphere_mean_ice_thickness_m": 2.0,
            "northern_hemisphere_thick_ice_area_million_km2": 4.0,
            "northern_hemisphere_thick_ice_area_fraction": 0.4,
        }


def test_evaluate_result_surfaces_six_channels_and_remains_incomplete() -> None:
    payload = evaluate_result(_SyntheticResult())
    assert payload["arctic_validation_stack"]["required_source_count"] == 6
    assert payload["all_six_observational_products_available"] is True
    assert payload["physical_volume_thickness_validation"]["complete"] is False
    assert payload["osi_saf_development_crosscheck"]["available"] is True
    assert payload["ice_age_structural_diagnostic"]["available"] is True
    assert payload["observational_stack_complete"] is False
    assert payload["scientific_validation_complete"] is False
    assert "exact observation cell centers" in payload["area_operator"]["mapping"]


def test_processed_transfer_bundle_excludes_raw_observation_files(tmp_path: Path) -> None:
    output = export_bundle(tmp_path / "bundle.zip", allow_partial=True)
    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
    assert "ARCTIC_VALIDATION_STACK_STATUS.json" in names
    assert not any("raw_observations" in name for name in names)
    assert not any(name.lower().endswith((".nc", ".nc4", ".h5", ".hdf5")) for name in names)


class _FakeEarthdataGranule:
    def data_links(self, access=None):
        return [
            "https://example.test/IS2SITMOGR4_01_202003_004_01.nc",
            "https://example.test/IS2SITMOGR4_01_202003_004_01.nc.xml",
            "https://example.test/IS2SITMOGR4_01_202003_004_01.png",
        ]


def test_earthdata_link_filter_keeps_only_scientific_netcdf_payload() -> None:
    assert _netcdf_links_from_granule(_FakeEarthdataGranule()) == [
        "https://example.test/IS2SITMOGR4_01_202003_004_01.nc"
    ]


def test_open_dataset_uses_verified_netcdf_signature_without_suffix(tmp_path: Path) -> None:
    import xarray as xr

    path = tmp_path / "earthdata_download_without_suffix"
    dataset = xr.Dataset({"ice_thickness": (("y", "x"), np.ones((2, 2), dtype=float))})
    dataset.to_netcdf(path, engine="scipy")
    assert _is_netcdf_file(path) is True
    with _open_dataset(path) as opened:
        assert "ice_thickness" in opened.variables


def test_open_dataset_rejects_earthdata_html_or_metadata_sidecar(tmp_path: Path) -> None:
    path = tmp_path / "unexpected_sidecar.nc"
    path.write_text("<html><body>not scientific NetCDF data</body></html>", encoding="utf-8")
    assert _is_netcdf_file(path) is False
    try:
        _open_dataset(path)
    except ValueError as exc:
        assert "not NetCDF/NetCDF-4" in str(exc)
    else:
        raise AssertionError("Sidecar/HTML file was incorrectly accepted as NetCDF")


def test_nsidc_ice_age_uses_official_annual_v41_filename() -> None:
    from tools.acquire_arctic_validation_stack import _nsidc_ice_age_filename

    assert _nsidc_ice_age_filename(1984) == "iceage_nh_12.5km_19840101_19841231_v4.1.nc"
    assert _nsidc_ice_age_filename(2024) == "iceage_nh_12.5km_20240101_20241231_v4.1.nc"


def test_direct_nsidc_daac_download_uses_legacy_cookie_auth(monkeypatch, tmp_path: Path) -> None:
    import tools.acquire_arctic_validation_stack as acquire

    class FakeResponse:
        def __init__(self):
            self._chunks = [b"CDF\x01" + b"\x00" * 32, b""]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def geturl(self):
            return (
                "https://daacdata.apps.nsidc.org/pub/DATASETS/"
                "nsidc0611_seaice_age_v4/data/test.nc"
            )

        def read(self, size):
            del size
            return self._chunks.pop(0)

    class FakeOpener:
        def __init__(self):
            self.urls = []

        def open(self, url, timeout):
            self.urls.append((url, timeout))
            return FakeResponse()

    fake_opener = FakeOpener()
    monkeypatch.setenv("EARTHDATA_USERNAME", "example-user")
    monkeypatch.setenv("EARTHDATA_PASSWORD", "example-password")
    monkeypatch.setattr(acquire, "_legacy_earthdata_opener", lambda: fake_opener)

    url = (
        "https://daacdata.apps.nsidc.org/pub/DATASETS/"
        "nsidc0611_seaice_age_v4/data/test.nc"
    )
    destination = tmp_path / "test.nc"
    returned = acquire._download_legacy_earthdata_https(url, destination)

    assert returned == destination
    assert destination.exists()
    assert fake_opener.urls == [(url, 180)]
    assert acquire._is_netcdf_file(destination)


def test_direct_nsidc_daac_download_requires_legacy_credentials(monkeypatch, tmp_path: Path) -> None:
    import pytest
    import tools.acquire_arctic_validation_stack as acquire

    monkeypatch.delenv("EARTHDATA_USERNAME", raising=False)
    monkeypatch.delenv("EARTHDATA_PASSWORD", raising=False)
    acquire._LEGACY_EARTHDATA_OPENER = None
    acquire._LEGACY_EARTHDATA_OPENER_IDENTITY = None
    with pytest.raises(RuntimeError, match="EARTHDATA_USERNAME"):
        acquire._download_legacy_earthdata_https(
            "https://daacdata.apps.nsidc.org/pub/DATASETS/nsidc0611_seaice_age_v4/data/test.nc",
            tmp_path / "test.nc",
        )


def test_nsidc_ice_age_archive_uses_data_subdirectory() -> None:
    import tools.acquire_arctic_validation_stack as acquire

    assert acquire.NSIDC_ICE_AGE_HTTPS_BASE.endswith("nsidc0611_seaice_age_v4/data/")
