from __future__ import annotations

from pathlib import Path
import zipfile

import pytest

import tools.acquire_arctic_validation_stack as acquire
from tools.export_arctic_validation_bundle import export_bundle


def test_acquire_earthdata_does_not_attempt_ice_age_without_legacy_credentials(monkeypatch):
    calls = []
    monkeypatch.delenv("EARTHDATA_USERNAME", raising=False)
    monkeypatch.delenv("EARTHDATA_PASSWORD", raising=False)
    monkeypatch.setattr(acquire, "acquire_cryosat2", lambda: [Path("cryo.nc")])
    monkeypatch.setattr(acquire, "process_cryosat2", lambda paths: calls.append(("cryo", list(paths))))
    monkeypatch.setattr(acquire, "acquire_icesat2", lambda: [Path("ice2.nc")])
    monkeypatch.setattr(acquire, "process_icesat2", lambda paths: calls.append(("ice2", list(paths))))
    monkeypatch.setattr(acquire, "acquire_ice_age", lambda: (_ for _ in ()).throw(AssertionError("must not run")))
    monkeypatch.setattr(acquire, "_write_physical_manifest", lambda: None)
    monkeypatch.setattr(acquire, "write_stack_status", lambda: Path("status.json"))

    result = acquire.acquire_earthdata()

    assert calls == [("cryo", [Path("cryo.nc")]), ("ice2", [Path("ice2.nc")])]
    assert result["nsidc_0611_v4"].startswith("not_attempted")


def test_acquire_earthdata_catches_legacy_ice_age_authorization_failure(monkeypatch):
    monkeypatch.setenv("EARTHDATA_USERNAME", "user")
    monkeypatch.setenv("EARTHDATA_PASSWORD", "password")
    monkeypatch.setattr(acquire, "acquire_cryosat2", lambda: [])
    monkeypatch.setattr(acquire, "process_cryosat2", lambda paths: None)
    monkeypatch.setattr(acquire, "acquire_icesat2", lambda: [])
    monkeypatch.setattr(acquire, "process_icesat2", lambda paths: None)
    monkeypatch.setattr(acquire, "acquire_ice_age", lambda: (_ for _ in ()).throw(RuntimeError("legacy authorization denied")))
    monkeypatch.setattr(acquire, "_write_physical_manifest", lambda: None)
    monkeypatch.setattr(acquire, "write_stack_status", lambda: Path("status.json"))

    result = acquire.acquire_earthdata()

    assert "not_processed" in result["nsidc_0611_v4"]
    assert "legacy authorization denied" in result["nsidc_0611_v4"]


def test_export_allows_exactly_missing_ice_age(monkeypatch, tmp_path):
    import tools.export_arctic_validation_bundle as exporter

    monkeypatch.setattr(exporter, "validation_stack_status", lambda: {
        "all_six_observational_products_available": False,
        "missing_sources": ["nsidc_0611_v4"],
    })
    monkeypatch.setattr(exporter, "SOURCES", {})
    output = export_bundle(tmp_path / "bundle.zip", allow_missing_ice_age=True)
    with zipfile.ZipFile(output) as archive:
        assert "ARCTIC_VALIDATION_STACK_STATUS.json" in archive.namelist()


def test_export_rejects_missing_core_source_even_when_ice_age_is_optional(monkeypatch, tmp_path):
    import tools.export_arctic_validation_bundle as exporter

    monkeypatch.setattr(exporter, "validation_stack_status", lambda: {
        "all_six_observational_products_available": False,
        "missing_sources": ["piomas_v2_1", "nsidc_0611_v4"],
    })
    monkeypatch.setattr(exporter, "SOURCES", {})
    with pytest.raises(SystemExit, match="piomas_v2_1"):
        export_bundle(tmp_path / "bundle.zip", allow_missing_ice_age=True)


def test_xarray_is_only_required_when_observational_netcdf_is_opened(monkeypatch, tmp_path):
    path = tmp_path / "observation.nc"
    path.write_bytes(b"CDF\x01" + b"\x00" * 32)
    monkeypatch.setattr(acquire, "xr", None)

    with pytest.raises(RuntimeError, match="requirements-validation-data.txt"):
        acquire._open_dataset(path)
