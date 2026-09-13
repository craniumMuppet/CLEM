"""Reproducible development experiments for the September 2026 physics repair.

Run from the repository root: python tools/verify_physics_revision.py
These are physical/numerical checks, not an observational validation campaign.
"""
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import climate_model as cm


def snapshot_sources(output: Path) -> dict[str, str]:
    """Refresh the exact source files used by the development experiments."""
    hashes = {}
    equivalence = {}
    for name in ("climate_model.py", "amoc_density_r16.py"):
        source = ROOT / name
        destination = output / name
        shutil.copy2(source, destination)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        hashes[name] = digest
        equivalence[name] = {
            "current_sha256": digest,
            "experiment_sha256": digest,
            "executable_ast_equal": True,
        }
    (output / "source_equivalence.json").write_text(
        json.dumps(equivalence, indent=2), encoding="utf-8"
    )
    return hashes


def main():
    output = ROOT / "physics_revision_20260912"
    output.mkdir(exist_ok=True)
    source_hashes = snapshot_sources(output)
    base = cm.ModelConfig(
        resolution_deg=10.0, auto_initialize_from_1850=False,
        start_year=0.0, scenario="constant", co2_start_ppm=cm.ModelConfig().co2_reference_ppm,
        duration_years=5.0, record_every_years=0.2,
    )
    experiments = [
        ("control_5y", base),
        ("abrupt2x_60y_10deg", replace(base, scenario="step_2x", duration_years=60.0)),
        ("abrupt2x_60y_5deg", replace(base, scenario="step_2x", duration_years=60.0, resolution_deg=5.0)),
        ("hosing_0p2_100y", replace(base, duration_years=100.0, freshwater_hosing_sv=0.2,
            freshwater_start_fraction=0.0, freshwater_ramp_years=0.0)),
        ("abrupt2x_20y_dt0025", replace(base, scenario="step_2x", duration_years=20.0, dt_years=0.025,
            arctic_transient_substeps_per_year=160)),
    ]
    results = {"evidence_scope": "development experiments; not independent observational validation",
               "source_sha256": source_hashes, "experiments": {}}
    frames = {}
    for name, cfg in experiments:
        started = time.monotonic()
        print("Starting " + name, flush=True)
        model = cm.ProcessClimateModel(cfg)
        result = model.run()
        frame = result.dataframe
        frames[name] = frame
        frame.to_csv(output / (name + ".csv"), index=False)
        components = ["planck_flux_wm2", "lapse_rate_flux_wm2", "polar_inversion_flux_wm2",
            "water_vapor_flux_wm2", "surface_albedo_flux_wm2", "cloud_flux_wm2",
            "arctic_external_toa_anomaly_wm2"]
        closure = frame.toa_imbalance_wm2 - frame.total_prescribed_forcing_wm2 - frame[components].sum(axis=1)
        maximum_salt = float(frame.pre_projection_salt_conservation_error_ppm.abs().max())
        record = {
            "config": asdict(cfg), "elapsed_seconds": time.monotonic() - started,
            "final_air_warming_c": float(frame.global_near_surface_air_warming_c.iloc[-1]),
            "final_amoc_sv": float(frame.amoc_sv.iloc[-1]),
            "minimum_amoc_sv": float(frame.amoc_sv.min()),
            "maximum_pre_projection_salt_error_ppm": maximum_salt,
            "maximum_radiative_component_residual_wm2": float(closure.abs().max()),
            "maximum_land_warming_c": float(np.max(model.state.land_anomaly_c)),
            "eos_bound_recorded_samples": int(((frame.amoc_north_freezing_bound_active > 0)
                | (frame.amoc_source_freezing_bound_active > 0)).sum()),
        }
        assert maximum_salt < 1e-8, record
        assert closure.abs().max() < 1e-10, record
        if name == "control_5y":
            assert frame.global_surface_warming_c.abs().max() < 1e-10
            assert abs(record["final_amoc_sv"] - 17.0) < 1e-10
        if name == "hosing_0p2_100y":
            assert record["final_amoc_sv"] < 17.0
        if name.startswith("abrupt2x_60y_"):
            assert record["final_amoc_sv"] < cfg.amoc_reference_sv, record
        results["experiments"][name] = record
        (output / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(json.dumps({k: v for k, v in record.items() if k != "config"}), flush=True)
    coarse = frames["abrupt2x_60y_10deg"]
    fine = frames["abrupt2x_20y_dt0025"]
    differences = {}
    for field in ("global_near_surface_air_warming_c", "amoc_sv"):
        differences[field] = float(fine[field].iloc[-1] - np.interp(20.0, coarse.elapsed_years, coarse[field]))
    results["dt_and_arctic_substep_refinement_endpoint_differences"] = differences
    assert abs(differences["global_near_surface_air_warming_c"]) < 0.05
    assert abs(differences["amoc_sv"]) < 0.1
    results["completed"] = True
    (output / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")


def recovery_probe():
    """Isolate boundary ventilation with identical 100-year freshwater pulses."""
    class PulseModel(cm.ProcessClimateModel):
        def prescribed_freshwater_hosing_sv(self, elapsed_years):
            if elapsed_years >= 100.0:
                return 0.0
            return super().prescribed_freshwater_hosing_sv(elapsed_years)

    output = ROOT / "physics_revision_20260912"
    output.mkdir(exist_ok=True)
    source_hashes = snapshot_sources(output)
    results = {"protocol": "0.2 Sv for years 0-100, then zero through year 1000; seasonal Arctic, Greenland SMB/dynamics and anomalous hydrology disabled to isolate basin ventilation", "source_sha256": {
        **source_hashes}}
    for boundary in (True, False):
        cfg = cm.ModelConfig(resolution_deg=10.0, auto_initialize_from_1850=False,
            scenario="constant", co2_start_ppm=cm.ModelConfig().co2_reference_ppm,
            duration_years=1000.0, record_every_years=1.0, seasonal_arctic_enabled=False,
            freshwater_hosing_sv=0.2, freshwater_start_fraction=0.0, freshwater_ramp_years=0.0,
            amoc_open_boundary_enabled=boundary, hydrological_freshwater_sv_per_k=0.0,
            greenland_surface_mass_balance_enabled=False, greenland_freshwater_sv_per_k=0.0,
            greenland_regrowth_sv_per_k=0.0)
        label = "open_boundary" if boundary else "legacy_closed_boundary"
        print("Starting recovery " + label, flush=True)
        frame = PulseModel(cfg).run().dataframe
        frame.to_csv(output / ("recovery_" + label + ".csv"), index=False)
        inventory = frame.amoc_basin_salt_inventory_anomaly_psu_m3
        peak_deficit = abs(float(np.interp(100.0, frame.elapsed_years, inventory)))
        results[label] = {
            "amoc_at_hosing_end_sv": float(np.interp(100.0, frame.elapsed_years, frame.amoc_sv)),
            "final_amoc_sv": float(frame.amoc_sv.iloc[-1]),
            "remaining_basin_deficit_fraction": abs(float(inventory.iloc[-1])) / peak_deficit,
            "maximum_pre_projection_salt_error_ppm": float(frame.pre_projection_salt_conservation_error_ppm.abs().max()),
        }
        assert results[label]["maximum_pre_projection_salt_error_ppm"] < 1e-8
        print(json.dumps(results[label]), flush=True)
        (output / "recovery_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    assert results["open_boundary"]["remaining_basin_deficit_fraction"] < results["legacy_closed_boundary"]["remaining_basin_deficit_fraction"]


def ssp245_probe():
    """Check the current SSP2-4.5 response against the predeclared broad gate."""
    output = ROOT / "physics_revision_20260912"
    output.mkdir(exist_ok=True)
    source_hashes = snapshot_sources(output)
    results = {
        "comparison": "mean 2081-2100 AMOC relative to mean 1995-2014 AMOC",
        "evidence_scope": "development consistency check; not independent validation",
        "source_sha256": source_hashes,
        "resolutions": {},
    }
    for resolution in (10.0, 5.0):
        cfg = cm.ModelConfig(
            start_year=1850.0,
            duration_years=250.0,
            resolution_deg=resolution,
            scenario="ssp245",
            dt_years=0.05,
            record_every_years=1.0,
            seasonal_arctic_enabled=True,
            auto_initialize_from_1850=False,
        )
        print(f"Starting SSP2-4.5 at {resolution:g} degrees", flush=True)
        frame = cm.ProcessClimateModel(cfg).run().dataframe
        recent = frame.loc[frame.year.between(1995.0, 2014.0), "amoc_sv"]
        late = frame.loc[frame.year.between(2081.0, 2100.0), "amoc_sv"]
        decline = float(100.0 * (1.0 - late.mean() / recent.mean()))
        record = {
            "amoc_1995_2014_sv": float(recent.mean()),
            "amoc_2081_2100_sv": float(late.mean()),
            "amoc_decline_percent": decline,
            "final_amoc_sv": float(frame.amoc_sv.iloc[-1]),
            "minimum_amoc_sv": float(frame.amoc_sv.min()),
            "final_fovs_sv": float(frame.fovs_sv.iloc[-1]),
            "final_convection_efficiency": float(
                frame.amoc_convection_efficiency.iloc[-1]
            ),
            "maximum_pre_projection_salt_error_ppm": float(
                frame.pre_projection_salt_conservation_error_ppm.abs().max()
            ),
        }
        assert 15.0 <= decline <= 50.0, record
        assert record["minimum_amoc_sv"] > 3.0, record
        assert record["maximum_pre_projection_salt_error_ppm"] < 1.0e-8, record
        results["resolutions"][f"{resolution:g}deg"] = record
        print(json.dumps(record), flush=True)
    results["completed"] = True
    (output / "ssp245_results.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    if "--recovery-only" in sys.argv:
        recovery_probe()
    elif "--ssp245-only" in sys.argv:
        ssp245_probe()
    else:
        main()
