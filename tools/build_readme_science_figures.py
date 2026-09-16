"""Build the compact science figures used near the top of the README.

The script reads completed local outputs without changing them. It copies the
selected ensemble plots into a stable documentation directory, builds the
four-panel SSP comparison from the saved comparison CSVs, and composes the
most useful process diagnostics for SSP2-4.5 and SSP5-8.5.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

import matplotlib

matplotlib.use("Agg")
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "docs" / "assets" / "science_update_2026_09"
SSP_DIR = ROOT / "outputs_ssps"
SWEEP_DIR = ROOT / "outputs_co2_target_sweep"
MONTE_CARLO_DIR = ROOT / "outputs_ssp245_monte_carlo"

SCENARIOS = {
    "ssp1_2_6": ("SSP1-2.6", "#2a9d8f"),
    "ssp2_4_5": ("SSP2-4.5", "#277da1"),
    "ssp4_6_0": ("SSP4-6.0", "#f8961e"),
    "ssp5_8_5": ("SSP5-8.5", "#d62828"),
}

COPIED_FIGURES = {
    SWEEP_DIR / "co2_target_sweep_amoc_percent_decline_trajectories.png": (
        "co2_target_sweep_amoc_percent_decline_trajectories.png"
    ),
    SWEEP_DIR / "co2_target_sweep_overview.png": "co2_target_sweep_overview.png",
    MONTE_CARLO_DIR / "monte_carlo_amoc_decline_percent_all.png": (
        "ssp245_monte_carlo_amoc_decline_percent.png"
    ),
    MONTE_CARLO_DIR / "monte_carlo_amoc_sv_all.png": (
        "ssp245_monte_carlo_amoc_sv.png"
    ),
    MONTE_CARLO_DIR / "monte_carlo_global_surface_warming_c_all.png": (
        "ssp245_monte_carlo_global_surface_warming.png"
    ),
}

DIAGNOSTIC_PANELS = (
    ("final_near_surface_air_temperature_anomaly_map.png", "Near-surface air anomaly"),
    ("final_sea_ice_map.png", "Sea ice"),
    ("final_snow_map.png", "Snow"),
    ("amoc_dynamical_targets.png", "AMOC targets"),
    ("amoc_convection_pycnocline_diagnostics.png", "Convection and pycnocline"),
    ("amoc_salinity_timeseries.png", "Atlantic salinity"),
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(paths: list[Path]) -> None:
    missing = [str(path.relative_to(ROOT)) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing required science output(s): " + ", ".join(missing))


def copy_selected_figures() -> list[Path]:
    require(list(COPIED_FIGURES))
    outputs: list[Path] = []
    for source, destination_name in COPIED_FIGURES.items():
        destination = ASSET_DIR / destination_name
        shutil.copyfile(source, destination)
        outputs.append(destination)
    return outputs


def build_ssp_comparison() -> Path:
    csv_paths = {
        "temperature": SSP_DIR / "ssp_temperature_comparison.csv",
        "amoc": SSP_DIR / "ssp_amoc_comparison.csv",
        "fovs": SSP_DIR / "ssp_fovs_comparison.csv",
        "sea_ice": SSP_DIR / "ssp_sea_ice_comparison.csv",
    }
    require(list(csv_paths.values()))
    frames = {name: pd.read_csv(path) for name, path in csv_paths.items()}

    fig, axes = plt.subplots(2, 2, figsize=(16, 10), sharex=True)
    panels = (
        (
            axes[0, 0],
            frames["temperature"],
            "temperature_anomaly_c",
            "A  Global surface-temperature anomaly",
            "Temperature anomaly (°C)",
        ),
        (
            axes[0, 1],
            frames["amoc"],
            "amoc_sv",
            "B  AMOC transport",
            "AMOC (Sv)",
        ),
        (
            axes[1, 0],
            frames["fovs"],
            "fovs_sv",
            "C  Southern-boundary overturning freshwater transport",
            "FovS (Sv)",
        ),
        (
            axes[1, 1],
            frames["sea_ice"],
            "sea_ice_area_million_km2",
            "D  Northern Hemisphere sea-ice area",
            "Area (million km²)",
        ),
    )

    legend_handles = []
    legend_labels = []
    for axis, frame, suffix, title, ylabel in panels:
        years = frame["year"]
        for key, (label, color) in SCENARIOS.items():
            line = axis.plot(
                years,
                frame[f"{key}_{suffix}"],
                color=color,
                linewidth=2.3,
                label=label,
            )[0]
            if axis is axes[0, 0]:
                legend_handles.append(line)
                legend_labels.append(label)
        axis.axvline(2100, color="#666666", linestyle="--", linewidth=1.0, alpha=0.7)
        axis.set_title(title, loc="left", fontsize=12, fontweight="bold")
        axis.set_ylabel(ylabel)
        axis.set_xlim(float(years.min()), float(years.max()))
        axis.grid(True, linewidth=0.6, alpha=0.25)
        axis.spines[["top", "right"]].set_visible(False)
    axes[1, 0].axhline(0.0, color="#444444", linewidth=0.9, alpha=0.7)
    axes[1, 0].set_xlabel("Year")
    axes[1, 1].set_xlabel("Year")

    fig.suptitle(
        "CLEM response across four SSP pathways",
        fontsize=19,
        fontweight="bold",
        y=0.985,
    )
    fig.legend(
        legend_handles,
        legend_labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.947),
        ncol=4,
        frameon=False,
        fontsize=11,
    )
    fig.text(
        0.5,
        0.018,
        "5° configuration, automatic 1850 initialization. The AMOC forced-heat closure is empirical; "
        "sea-ice geography is reduced-order. The dashed line marks 2100.",
        ha="center",
        fontsize=9.5,
        color="#444444",
    )
    fig.tight_layout(rect=(0.02, 0.05, 0.98, 0.91), h_pad=2.2, w_pad=2.0)
    output = ASSET_DIR / "ssp_four_panel_comparison.png"
    fig.savefig(output, dpi=180, facecolor="white")
    plt.close(fig)
    return output


def build_diagnostic_contact_sheet(scenario: str, label: str) -> Path:
    diagnostic_dir = SSP_DIR / scenario / "diagnostics"
    inputs = [diagnostic_dir / filename for filename, _ in DIAGNOSTIC_PANELS]
    require(inputs)

    fig, axes = plt.subplots(3, 2, figsize=(18, 15.5))
    for axis, path, (_, title) in zip(axes.flat, inputs, DIAGNOSTIC_PANELS):
        axis.imshow(mpimg.imread(path))
        axis.set_title(title, fontsize=12, fontweight="bold", pad=7)
        axis.axis("off")
    fig.suptitle(
        f"{label} process and final-state diagnostics",
        fontsize=21,
        fontweight="bold",
        y=0.99,
    )
    fig.text(
        0.5,
        0.012,
        "Maps and time series are reduced-model diagnostics and do not establish regional forecast skill.",
        ha="center",
        fontsize=10,
        color="#444444",
    )
    fig.tight_layout(rect=(0.01, 0.035, 0.99, 0.955), h_pad=1.4, w_pad=0.8)
    output = ASSET_DIR / f"{scenario}_diagnostics.png"
    fig.savefig(output, dpi=160, facecolor="white")
    plt.close(fig)
    return output


def write_manifest(outputs: list[Path]) -> Path:
    sweep_quality = json.loads(
        (SWEEP_DIR / "co2_target_sweep_ensemble_quality.json").read_text(encoding="utf-8")
    )
    monte_carlo_quality = json.loads(
        (MONTE_CARLO_DIR / "monte_carlo_ensemble_quality.json").read_text(encoding="utf-8")
    )
    source_paths = [
        SSP_DIR / "ssp_temperature_comparison.csv",
        SSP_DIR / "ssp_amoc_comparison.csv",
        SSP_DIR / "ssp_fovs_comparison.csv",
        SSP_DIR / "ssp_sea_ice_comparison.csv",
        *COPIED_FIGURES.keys(),
    ]
    manifest = {
        "generated_date": "2026-09-16",
        "co2_target_sweep": {
            "requested_members_per_target": sweep_quality["requested_members"],
            "complete_paired_members": sweep_quality["complete_paired_members"],
            "failed_members": sweep_quality["failed_members"],
        },
        "ssp245_monte_carlo": {
            "requested_members": monte_carlo_quality["requested_members"],
            "successful_members": monte_carlo_quality["successful_members"],
            "failed_members": monte_carlo_quality["failed_members"],
        },
        "sources": {
            str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path)
            for path in source_paths
        },
        "assets": {
            path.name: sha256(path)
            for path in sorted(outputs)
        },
    }
    output = ASSET_DIR / "manifest.json"
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return output


def main() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    outputs = copy_selected_figures()
    outputs.append(build_ssp_comparison())
    outputs.append(build_diagnostic_contact_sheet("ssp245", "SSP2-4.5"))
    outputs.append(build_diagnostic_contact_sheet("ssp585", "SSP5-8.5"))
    manifest = write_manifest(outputs)
    print(f"Wrote {len(outputs)} figures and {manifest.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
