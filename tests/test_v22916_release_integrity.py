from __future__ import annotations

from dataclasses import replace
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

import monte_carlo as mc
from climate_model import MODEL_VERSION, ModelConfig, ProcessClimateModel
from validation_provenance import (
    expected_task_metadata,
    make_task_record,
    make_task_record_from_metadata,
    validate_task_record,
)


def test_v22916_version() -> None:
    assert MODEL_VERSION == "2.29.29"


def test_signed_amoc_percent_weakening_decreases() -> None:
    source = np.array([
        [20.0] * 10 + [15.0, 10.0],
        [18.0] * 10 + [13.5, 9.0],
    ])
    change = mc._derive_stack(source, "signed_percent_change_from_baseline")
    np.testing.assert_allclose(change[:, :10], 0.0)
    np.testing.assert_allclose(change[:, 10], -25.0)
    np.testing.assert_allclose(change[:, 11], -50.0)
    assert "amoc_decline_percent" in mc.MAIN_DERIVED_FIGURE_METRICS


def test_validation_task_provenance_rejects_stale_records(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    root.mkdir()
    validator = root / "validator.py"
    validator.write_text("VALUE = 1\n", encoding="utf-8")
    (root / "model.py").write_text("MODEL = 1\n", encoding="utf-8")

    record = make_task_record(
        root=root,
        validator_path=validator,
        task_name="summary",
        model_version="2.29.18",
        result={"passed": True},
    )
    assert validate_task_record(
        record,
        root=root,
        validator_path=validator,
        task_name="summary",
        model_version="2.29.18",
    ) == {"passed": True}

    stale_version = dict(record)
    stale_version["model_version"] = "2.29.15"
    with pytest.raises(ValueError, match="model_version"):
        validate_task_record(
            stale_version,
            root=root,
            validator_path=validator,
            task_name="summary",
            model_version="2.29.18",
        )

    (root / "model.py").write_text("MODEL = 2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="source_tree_sha256"):
        validate_task_record(
            record,
            root=root,
            validator_path=validator,
            task_name="summary",
            model_version="2.29.18",
        )



def test_validation_provenance_snapshot_is_frozen_before_execution(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    root.mkdir()
    validator = root / "validator.py"
    validator.write_text("VALUE = 1\n", encoding="utf-8")
    model = root / "model.py"
    model.write_text("MODEL = 1\n", encoding="utf-8")

    metadata = expected_task_metadata(
        root=root,
        validator_path=validator,
        task_name="long_task",
        model_version="2.29.18",
    )
    model.write_text("MODEL = 2\n", encoding="utf-8")
    record = make_task_record_from_metadata(metadata, {"passed": True})

    with pytest.raises(ValueError, match="source_tree_sha256"):
        validate_task_record(
            record,
            root=root,
            validator_path=validator,
            task_name="long_task",
            model_version="2.29.18",
        )

def test_subannual_arctic_state_and_saved_fields_are_exact() -> None:
    cfg = replace(
        ModelConfig(),
        start_year=1850.0,
        duration_years=1.0,
        dt_years=0.05,
        record_every_years=0.25,
        resolution_deg=10.0,
        scenario="ssp245",
        auto_initialize_from_1850=False,
    )
    recorded_model = ProcessClimateModel(cfg)
    result = recorded_model.run()
    replay = ProcessClimateModel(cfg)
    active = replay.grid.lat >= cfg.arctic_module_full_latitude_deg

    record_index = 0
    elapsed = 0.0
    next_record = min(cfg.record_every_years, cfg.duration_years)

    def verify(index: int, year: float) -> None:
        reference = replay._arctic_reference_state(year)
        for prefix, energy_field, open_field, air_field, seasonal_field, saved_ice, saved_local, saved_open in (
            (
                "atlantic",
                "arctic_atlantic_ice_energy_anomaly_wyr_m2",
                "arctic_atlantic_open_water_heat_anomaly_wyr_m2",
                "arctic_atlantic_air_anomaly_c",
                "arctic_atlantic_seasonal_ice_fraction",
                result.atlantic_sea_ice_history[index],
                result.arctic_atlantic_local_ice_thickness_history_m[index],
                result.arctic_atlantic_open_water_temperature_history_c[index],
            ),
            (
                "non_atlantic",
                "arctic_non_atlantic_ice_energy_anomaly_wyr_m2",
                "arctic_non_atlantic_open_water_heat_anomaly_wyr_m2",
                "arctic_non_atlantic_air_anomaly_c",
                "arctic_non_atlantic_seasonal_ice_fraction",
                result.non_atlantic_sea_ice_history[index],
                result.arctic_non_atlantic_local_ice_thickness_history_m[index],
                result.arctic_non_atlantic_open_water_temperature_history_c[index],
            ),
        ):
            total_ice = reference[f"{prefix}_ice_energy_wyr_m2"] + getattr(replay.state, energy_field)
            total_open = reference[f"{prefix}_open_water_heat_wyr_m2"] + getattr(replay.state, open_field)
            reference_air = reference[f"{prefix}_air_temperature_c"]
            concentration = getattr(replay.state, seasonal_field)
            concentration, equivalent, local = replay._arctic_state_from_energy_and_concentration(
                total_ice,
                concentration,
            )
            open_temperature = replay._arctic_open_water_temperature(total_open, 1.0 - concentration)
            np.testing.assert_allclose(getattr(replay.state, seasonal_field), concentration, rtol=0.0, atol=2e-13)
            np.testing.assert_allclose(saved_local, local, rtol=0.0, atol=2e-13)
            np.testing.assert_allclose(saved_open, open_temperature, rtol=0.0, atol=2e-13)
            np.testing.assert_allclose(saved_ice[active] * saved_local[active], equivalent[active], rtol=0.0, atol=2e-13)

    verify(record_index, elapsed)
    tolerance = 1e-10
    while elapsed < cfg.duration_years - tolerance:
        remaining = cfg.duration_years - elapsed
        to_record = next_record - elapsed
        dt = min(cfg.dt_years, remaining)
        if to_record > tolerance:
            dt = min(dt, to_record)
        replay.step(elapsed, dt_years=dt)
        elapsed = min(cfg.duration_years, elapsed + dt)
        if elapsed >= next_record - tolerance or elapsed >= cfg.duration_years - tolerance:
            record_index += 1
            verify(record_index, elapsed)
            while next_record <= elapsed + tolerance:
                next_record += cfg.record_every_years
            next_record = min(next_record, cfg.duration_years)

    assert record_index + 1 == len(result.dataframe)


def test_monte_carlo_output_layout_source_contract() -> None:
    source = Path(mc.__file__).read_text(encoding="utf-8")
    assert 'extreme_percentiles_dir = diagnostics_dir / "1_99_percentiles"' in source
    assert 'if metric in MAIN_DERIVED_FIGURE_METRICS' in source
    assert '"monte_carlo_final_map_mean.png"' in source
    assert '"monte_carlo_final_map_median.png"' in source
    assert 'extreme_percentiles_dir)' in source


def test_v22916_audit_and_packager_cover_reviewed_files() -> None:
    root = Path(__file__).resolve().parents[1]
    validator_source = (root / "validate_v22916.py").read_text(encoding="utf-8")
    assert '"tests/test_v22912_monte_carlo_integrity.py"' in validator_source
    assert '"tools/package_v22916.py"' in validator_source
    assert '"validation_provenance.py"' in validator_source
