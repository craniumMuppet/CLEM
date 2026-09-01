from __future__ import annotations

from dataclasses import replace
import pytest

import climate_model as cm
import amoc_density_r16 as eos
import verify_r16_local as vr


def test_teos10_positive_control_is_not_rejected_by_linear_absolute_ratio_gate(monkeypatch):
    cfg = cm.ModelConfig(
        resolution_deg=10.0,
        auto_initialize_from_1850=False,
        amoc_density_eos="teos10",
    )
    # Reproduce the R16 user-run setup condition without requiring GSW in the
    # packaging environment: the TEOS dimensional control contrast is ~2.693
    # times the linear reference, but hydraulics normalize by its own baseline.
    monkeypatch.setattr(
        eos,
        "teos10_density_driver",
        lambda **kwargs: 2.6930 * cfg.amoc_reference_density_driver,
    )
    d = cm.validate_initial_amoc_density_margin(cfg)
    assert d["density_driver"] > 0.0
    assert d["density_ratio"] == pytest.approx(2.6930, rel=0, abs=1e-12)
    assert d["density_ratio"] > cfg.amoc_maximum_initial_density_ratio


def test_linear_absolute_density_guard_still_applies():
    cfg = cm.ModelConfig(
        resolution_deg=10.0,
        auto_initialize_from_1850=False,
        # Force a large positive linear density contrast outside the calibrated band.
        initial_north_salinity_psu=36.0,
    )
    with pytest.raises(ValueError, match="linear-EOS range"):
        cm.validate_initial_amoc_density_margin(cfg)


def test_r16_1_validation_only_is_exactly_the_three_missing_teos_runs():
    assert vr.MAX_CHUNK_YEARS == 5.0
    assert vr.VALIDATION_ONLY_SEGMENTS == [
        "r16_control_teos10_20y",
        "r16_teos10_hosing_0p2_100y",
        "r16_teos10_ssp245_1850_2100_10deg",
    ]
    assert set(vr.VALIDATION_ONLY_SEGMENTS).issubset(vr.SEGMENTS)
    assert "R16_2_TEOS" in vr.BUNDLE.name
