"""Regression checks for the Greenland volume-to-mass conversion."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import climate_model_gui
from climate_model import (
    GREENLAND_ICE_DENSITY_KG_M3,
    GREENLAND_REFERENCE_ICE_MASS_GT,
    GREENLAND_REFERENCE_ICE_VOLUME_KM3,
    ModelConfig,
    build_parser,
)


CORRECTED_GREENLAND_MASS_GT = 2.61345e6
ROOT = Path(__file__).resolve().parents[1]


def test_greenland_reference_volume_is_converted_to_mass() -> None:
    expected_gt = 2.85e6 * 1.0e9 * 917.0 / 1.0e12

    assert GREENLAND_REFERENCE_ICE_VOLUME_KM3 == pytest.approx(2.85e6)
    assert GREENLAND_ICE_DENSITY_KG_M3 == pytest.approx(917.0)
    assert GREENLAND_REFERENCE_ICE_MASS_GT == pytest.approx(CORRECTED_GREENLAND_MASS_GT)
    assert ModelConfig().greenland_initial_ice_mass_gt == pytest.approx(expected_gt)


def test_cli_and_desktop_gui_inherit_canonical_greenland_mass() -> None:
    expected = ModelConfig().greenland_initial_ice_mass_gt
    cli_args = build_parser().parse_args([])

    assert cli_args.greenland_initial_ice_mass_gt == pytest.approx(expected)
    gui_default = float(climate_model_gui.DEFAULTS["greenland_initial_ice_mass_gt"])
    assert gui_default == pytest.approx(expected)


def test_active_saved_gui_profile_uses_corrected_mass() -> None:
    profile_path = ROOT / "climate_model_settings_increased_sv_from_melt.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))

    configured_mass = float(profile["settings"]["greenland_initial_ice_mass_gt"])
    assert configured_mass == pytest.approx(CORRECTED_GREENLAND_MASS_GT)
