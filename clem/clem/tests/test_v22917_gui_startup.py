"""Regression checks for the v2.29.18 desktop-GUI startup hotfix."""

from __future__ import annotations

from pathlib import Path

from setting_metadata import setting_info, setting_tooltip


ROOT = Path(__file__).resolve().parents[1]


def test_new_ice_gui_setting_has_tooltip_metadata() -> None:
    info = setting_info("arctic_new_ice_local_thickness")
    assert info.confidence == "Medium"
    tooltip = setting_tooltip("arctic_new_ice_local_thickness")
    assert "0.25 m" in tooltip
    assert "newly forming sea ice" in tooltip


def test_windowed_launcher_preserves_startup_traceback() -> None:
    launcher = (ROOT / "launch_gui.pyw").read_text(encoding="utf-8")
    assert "traceback.format_exc()" in launcher
    assert "gui_startup_error.log" in launcher
    assert "MessageBoxW" in launcher


def test_run_gui_has_console_fallback() -> None:
    launcher = (ROOT / "run_gui.bat").read_text(encoding="utf-8")
    assert "climate_model_gui.py" in launcher
    assert "python.exe" in launcher
