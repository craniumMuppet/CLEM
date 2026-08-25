#!/usr/bin/env python3
"""Re-run the uploaded central configurations with v2.16.0 continuous AMOC physics."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from climate_model import ModelConfig, ProcessClimateModel

CASES = {
    "ssp585": Path("/mnt/data/runs_inspect/ssp/ssp585/monte_carlo_base_config.json"),
    "carbon_pulse_0_5_2200ppm": Path(
        "/mnt/data/runs_inspect/pulse/carbon_pulse_test_0_5_2200ppm/monte_carlo_base_config.json"
    ),
}


def main() -> None:
    root = Path(__file__).resolve().parent / "validation_continuous_amoc_v2_16_0"
    root.mkdir(exist_ok=True)
    combined: dict[str, object] = {"model_version": "2.16.0", "cases": {}}
    for name, source in CASES.items():
        raw = json.loads(source.read_text())
        # Migrate the v2.15 AMOC closure to the v2.16 continuous defaults.
        raw.update(
            amoc_convection_critical_density_ratio=0.88,
            amoc_convection_transition_width=0.035,
            amoc_convective_mixing_reference_sv=5.0,
            amoc_convective_mixing_exponent=2.0,
            amoc_convection_entrainment_feedback=0.10,
        )
        config = ModelConfig(**raw)
        result = ProcessClimateModel(config).run()
        frame = result.dataframe
        case_dir = root / name
        case_dir.mkdir(exist_ok=True)
        frame.to_csv(case_dir / "timeseries.csv", index=False)
        active_config = asdict(config)
        ignored_legacy = {
            key: active_config.pop(key)
            for key in (
                "amoc_convection_collapse_density_ratio",
                "amoc_convection_restart_density_ratio",
                "amoc_collapsed_convection_fraction",
            )
        }
        active_config["ignored_legacy_v2_15_fields"] = ignored_legacy
        (case_dir / "config.json").write_text(json.dumps(active_config, indent=2))
        collapsed = frame[frame["amoc_sv"] <= config.amoc_collapse_threshold_sv]
        annual_target_change = (
            frame["amoc_convection_target"].diff().abs()
            / frame["year"].diff()
        )
        assessment = {
            **result.summary(),
            "first_amoc_below_2sv_year": (
                None if collapsed.empty else float(collapsed["year"].iloc[0])
            ),
            "maximum_annual_convection_target_change": float(
                annual_target_change.max()
            ),
            "maximum_annual_amoc_change_sv": float(
                (frame["amoc_sv"].diff().abs() / frame["year"].diff()).max()
            ),
            "minimum_convective_mixing_sv": float(
                frame["amoc_convective_mixing_sv"].min()
            ),
            "minimum_effective_convection_density_ratio": float(
                frame["amoc_convection_effective_density_ratio"].min()
            ),
        }
        (case_dir / "summary.json").write_text(json.dumps(assessment, indent=2))
        combined["cases"][name] = assessment
    (root / "summary.json").write_text(json.dumps(combined, indent=2))


if __name__ == "__main__":
    main()
