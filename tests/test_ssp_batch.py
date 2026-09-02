"""All-SSP batch execution, comparison, and resume regressions."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import climate_model as cm
from climate_model_gui import DEFAULTS, build_cli_command, validate_values


def _temperature_frame(offset: float = 0.0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "year": [2000.0, 2001.0, 2002.0],
            "global_near_surface_air_warming_c": np.asarray([0.0, 0.2, 0.4])
            + offset,
            "amoc_sv": np.asarray([17.0, 16.5, 16.0]) - offset,
            "fovs_sv": np.asarray([-0.15, -0.14, -0.13]) + 0.01 * offset,
            "northern_hemisphere_sea_ice_area_million_km2": (
                np.asarray([10.0, 9.8, 9.6]) - offset
            ),
            "northern_hemisphere_sea_ice_extent_million_km2": (
                np.asarray([12.0, 11.7, 11.4]) - offset
            ),
        }
    )


def test_cli_and_desktop_expose_all_ssp_batch_flags() -> None:
    args = cm.build_parser().parse_args(
        ["--run-all-ssp", "--resume-all-ssp", "--ssp-workers", "2"]
    )
    assert args.run_all_ssp is True
    assert args.resume_all_ssp is True
    assert args.ssp_workers == 2

    values = dict(DEFAULTS)
    values.update(
        {"run_all_ssp": True, "resume_all_ssp": True, "ssp_workers": "2"}
    )
    validate_values(values)
    command = build_cli_command(values)
    assert command.count("--run-all-ssp") == 1
    assert command.count("--resume-all-ssp") == 1
    assert command[command.index("--ssp-workers") + 1] == "2"


def test_all_ssp_batch_rejects_monte_carlo() -> None:
    values = dict(DEFAULTS)
    values.update({"run_all_ssp": True, "monte_carlo_enabled": True})
    with pytest.raises(ValueError, match="deterministic"):
        validate_values(values)


@pytest.mark.parametrize("workers", ["0", "1.5", "5"])
def test_all_ssp_batch_rejects_invalid_worker_counts(workers: str) -> None:
    values = dict(DEFAULTS)
    values.update({"run_all_ssp": True, "ssp_workers": workers})
    with pytest.raises(ValueError, match="integer from 1 to 4"):
        validate_values(values)


def test_temperature_comparison_uses_global_near_surface_air(tmp_path: Path) -> None:
    for index, scenario in enumerate(cm.SSP_BATCH_SCENARIOS):
        scenario_output = tmp_path / scenario
        scenario_output.mkdir()
        frame = _temperature_frame(float(index))
        frame["global_bulk_surface_warming_c"] = 100.0 + index
        frame.to_csv(scenario_output / "timeseries.csv", index=False)

    comparison = cm.save_ssp_temperature_comparison(tmp_path)
    assert list(comparison.columns) == [
        "year",
        *(cm.SSP_COMPARISON_COLUMNS[item] for item in cm.SSP_BATCH_SCENARIOS),
    ]
    np.testing.assert_allclose(
        comparison[cm.SSP_COMPARISON_COLUMNS["ssp585"]],
        [3.0, 3.2, 3.4],
    )
    assert (tmp_path / "ssp_temperature_comparison.csv").is_file()
    assert (tmp_path / "ssp_temperature_comparison.png").is_file()


def test_all_ssp_comparisons_cover_amoc_fovs_sea_ice_and_every_field(
    tmp_path: Path,
) -> None:
    for index, scenario in enumerate(cm.SSP_BATCH_SCENARIOS):
        scenario_output = tmp_path / scenario
        scenario_output.mkdir()
        frame = _temperature_frame(float(index))
        frame["additional_diagnostic"] = index + frame["year"]
        frame.to_csv(scenario_output / "timeseries.csv", index=False)

    products = cm.save_ssp_comparisons(tmp_path)

    assert set(products) == {
        "temperature",
        "amoc",
        "fovs",
        "sea_ice",
        "combined_timeseries",
    }
    for stem in (
        "ssp_temperature_comparison",
        "ssp_amoc_comparison",
        "ssp_fovs_comparison",
        "ssp_sea_ice_comparison",
    ):
        assert (tmp_path / f"{stem}.csv").is_file()
        assert (tmp_path / f"{stem}.png").is_file()

    combined = pd.read_csv(tmp_path / "ssp_combined_timeseries.csv")
    assert len(combined) == 3 * len(cm.SSP_BATCH_SCENARIOS)
    assert set(combined["ssp_scenario"]) == set(cm.SSP_BATCH_SCENARIOS)
    assert "additional_diagnostic" in combined.columns
    sea_ice = products["sea_ice"]
    assert "ssp5_8_5_sea_ice_area_million_km2" in sea_ice.columns
    assert "ssp5_8_5_sea_ice_extent_million_km2" in sea_ice.columns


def test_all_ssp_batch_resumes_completed_scenarios(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    def fake_run_model(config: cm.ModelConfig, **_kwargs: object) -> SimpleNamespace:
        calls.append(config.scenario)
        offset = float(cm.SSP_BATCH_SCENARIOS.index(config.scenario))
        return SimpleNamespace(config=config, dataframe=_temperature_frame(offset))

    def fake_save_outputs(result: SimpleNamespace, output_dir: str | Path) -> None:
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        result.dataframe.to_csv(output / "timeseries.csv", index=False)
        (output / "config.json").write_text(
            json.dumps(asdict(result.config), indent=2), encoding="utf-8"
        )
        (output / "summary.json").write_text("{}\n", encoding="utf-8")
        for filename in (
            "temperature_timeseries.png",
            "amoc_timeseries.png",
            "fovs_timeseries.png",
            "sea_ice_timeseries.png",
        ):
            (output / filename).write_bytes(b"complete")

    monkeypatch.setattr(cm, "run_model", fake_run_model)
    monkeypatch.setattr(cm, "save_outputs", fake_save_outputs)
    config = cm.ModelConfig(
        scenario="ssp245",
        start_year=2000.0,
        duration_years=2.0,
        dt_years=0.1,
        auto_initialize_from_1850=False,
    )

    first = cm.run_all_ssp_scenarios(
        config, tmp_path, diagnose=False, workers=1
    )
    assert calls == list(cm.SSP_BATCH_SCENARIOS)
    assert first["status"] == "completed"

    calls.clear()
    second = cm.run_all_ssp_scenarios(
        config, tmp_path, resume=True, diagnose=False, workers=1
    )
    assert calls == []
    assert second["completed_scenarios"] == list(cm.SSP_BATCH_SCENARIOS)


def test_all_ssp_batch_submits_scenarios_before_collecting_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[tuple[str, object]] = []

    def fake_run_model(config: cm.ModelConfig, **_kwargs: object) -> SimpleNamespace:
        events.append(("run", config.scenario))
        offset = float(cm.SSP_BATCH_SCENARIOS.index(config.scenario))
        return SimpleNamespace(config=config, dataframe=_temperature_frame(offset))

    def fake_save_outputs(result: SimpleNamespace, output_dir: str | Path) -> None:
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        result.dataframe.to_csv(output / "timeseries.csv", index=False)
        (output / "config.json").write_text(
            json.dumps(asdict(result.config), indent=2), encoding="utf-8"
        )
        (output / "summary.json").write_text("{}\n", encoding="utf-8")
        for filename in (
            "temperature_timeseries.png",
            "amoc_timeseries.png",
            "fovs_timeseries.png",
            "sea_ice_timeseries.png",
        ):
            (output / filename).write_bytes(b"complete")

    class ImmediateResult:
        def __init__(self, function: object, args: tuple[object, ...]) -> None:
            self.function = function
            self.args = args
            self.value: object | None = None

        def ready(self) -> bool:
            return True

        def get(self) -> object:
            if self.value is None:
                self.value = self.function(*self.args)  # type: ignore[operator]
            return self.value

    class FakePool:
        def __init__(self, processes: int) -> None:
            events.append(("pool", processes))

        def apply_async(
            self, function: object, args: tuple[object, ...]
        ) -> ImmediateResult:
            scenario = args[0][0]
            events.append(("submit", scenario))
            return ImmediateResult(function, args)

        def close(self) -> None:
            events.append(("close", None))

        def join(self) -> None:
            events.append(("join", None))

        def terminate(self) -> None:
            events.append(("terminate", None))

    class FakeContext:
        @staticmethod
        def Pool(processes: int) -> FakePool:
            return FakePool(processes)

    monkeypatch.setattr(cm, "run_model", fake_run_model)
    monkeypatch.setattr(cm, "save_outputs", fake_save_outputs)
    monkeypatch.setattr(cm.multiprocessing, "get_context", lambda _mode: FakeContext())
    config = cm.ModelConfig(
        scenario="ssp245",
        start_year=2000.0,
        duration_years=2.0,
        dt_years=0.1,
        auto_initialize_from_1850=False,
    )

    state = cm.run_all_ssp_scenarios(
        config, tmp_path, diagnose=False, workers=4
    )

    assert events[0] == ("pool", 4)
    assert events[1:5] == [
        ("submit", scenario) for scenario in cm.SSP_BATCH_SCENARIOS
    ]
    assert state["parallel_workers"] == 4
    assert state["completed_scenarios"] == list(cm.SSP_BATCH_SCENARIOS)
    assert state["active_scenarios"] == []
