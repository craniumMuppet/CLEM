"""Continue the completed recovery experiment to year 3000 in five-year children.

The original validation bundle is immutable input. This separate continuation
records the parent checkpoint hash and the explicit duration/spec migration.
"""
from __future__ import annotations

import argparse
import copy
from dataclasses import replace
import json
from pathlib import Path
import pickle
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import verify_physics_local as verification
from run_state import output_directory_run_lock

PARENT_NAME = "recovery_0p4_1050y"
NAME = "recovery_0p4_extended_3000y"
END_YEAR = 3000.0
OUT = ROOT / "physics_recovery_extension_20260911"
PARENT_OUT = ROOT / "physics_verification_results"
PARENT_SPEC = copy.deepcopy(verification.SEGMENTS[PARENT_NAME])
SPEC = copy.deepcopy(PARENT_SPEC)
SPEC["duration"] = END_YEAR
SPEC["stages"][-1]["end"] = END_YEAR
LINEAGE = OUT / "lineage.json"


def configure() -> None:
    verification.OUT = OUT
    verification.CHECKPOINTS = OUT / "_checkpoints"
    verification.SEGMENTS[NAME] = SPEC


def validate_lineage() -> dict:
    lineage = json.loads(LINEAGE.read_text(encoding="utf-8"))
    for path, key in (
        (ROOT / "climate_model.py", "climate_model_sha256"),
        (ROOT / "verify_physics_local.py", "base_runner_sha256"),
        (Path(__file__), "extension_runner_sha256"),
    ):
        if verification.sha256(path) != lineage[key]:
            raise RuntimeError(f"Continuation source changed: {path.name}")
    if verification.stable_json_hash(SPEC) != lineage["extension_spec_sha256"]:
        raise RuntimeError("Continuation specification changed")
    return lineage


def seed() -> dict:
    configure()
    cp = verification.checkpoint_path(NAME)
    if LINEAGE.exists():
        lineage = validate_lineage()
        if cp.exists():
            return verification.setup_segment_worker(NAME)
    else:
        lineage = None
    parent_cp = PARENT_OUT / "_checkpoints" / PARENT_NAME / "checkpoint.pkl"
    parent_progress = json.loads(parent_cp.with_name("progress.json").read_text())
    parent_manifest = json.loads((PARENT_OUT / "manifest.json").read_text())
    source_hash = verification.sha256(ROOT / "climate_model.py")
    runner_hash = verification.sha256(ROOT / "verify_physics_local.py")
    checkpoint_hash = verification.sha256(parent_cp)
    if not parent_manifest.get("all_segments_completed"):
        raise RuntimeError("Parent validation is incomplete")
    if parent_manifest["climate_model_sha256"] != source_hash or parent_manifest["runner_sha256"] != runner_hash:
        raise RuntimeError("Parent source hashes do not match the current sources")
    if parent_progress["checkpoint_sha256"] != checkpoint_hash:
        raise RuntimeError("Parent checkpoint hash mismatch")
    if not parent_progress["completed"] or abs(parent_progress["elapsed_years"] - 1050.0) > 1e-6:
        raise RuntimeError("Parent checkpoint is not the completed year-1050 state")
    # Only load the locally generated checkpoint after checking its recorded hash.
    with parent_cp.open("rb") as handle:
        payload = pickle.load(handle)
    if payload["source_sha256"] != source_hash or payload["spec_sha256"] != verification.stable_json_hash(PARENT_SPEC):
        raise RuntimeError("Parent checkpoint source/spec mismatch")
    if payload["segment"] != PARENT_NAME or abs(payload["elapsed_years"] - 1050.0) > 1e-6:
        raise RuntimeError("Unexpected parent checkpoint state")
    model = payload["model"]
    if model.config.scenario != "constant" or model.config.freshwater_hosing_sv != 0.0:
        raise RuntimeError("Continuation requires the original constant-CO2, post-hosing state")
    state_bytes = pickle.dumps(model.state)
    model.config = replace(model.config, duration_years=END_YEAR)
    assert pickle.dumps(model.state) == state_bytes
    cp.parent.mkdir(parents=True, exist_ok=True)
    verification.chunk_dir(NAME).mkdir(parents=True, exist_ok=True)
    # The existing CSV preserves the complete historical tail for the unchanged
    # year-600-onward closure criterion. Do not restart its averaging clock.
    import pandas as pd
    parent_csv = PARENT_OUT / "segments" / PARENT_NAME / "timeseries.csv"
    history = pd.read_csv(parent_csv).to_dict("records")
    if abs(float(history[-1]["elapsed_years"]) - float(payload["elapsed_years"])) > 1e-6:
        raise RuntimeError("Parent time series does not reach its checkpoint")
    verification.write_records_json(verification.segment_dir(NAME) / "initial.json", history)
    new_lineage = {
        "created_unix": time.time(),
        "climate_model_sha256": source_hash,
        "base_runner_sha256": runner_hash,
        "extension_runner_sha256": verification.sha256(Path(__file__)),
        "parent_checkpoint_sha256": checkpoint_hash,
        "parent_timeseries_sha256": verification.sha256(parent_csv),
        "parent_spec_sha256": payload["spec_sha256"],
        "extension_spec_sha256": verification.stable_json_hash(SPEC),
        "parent_spec": PARENT_SPEC,
        "extension_spec": SPEC,
        "initial_elapsed_years": payload["elapsed_years"],
        "end_year": END_YEAR,
        "configuration_change": {"duration_years": [1050.0, END_YEAR]},
        "state_unchanged_at_handoff": True,
        "thresholds": {"evaluation_start_year": 600.0, "mean_abs_volume_imbalance_sv": 0.5, "final_abs_volume_imbalance_sv": 0.05},
    }
    if lineage and lineage["parent_checkpoint_sha256"] != checkpoint_hash:
        raise RuntimeError("Parent checkpoint changed during interrupted setup")
    verification.atomic_write_json(LINEAGE, lineage or new_lineage)
    verification.atomic_pickle(cp, {
        **payload, "segment": NAME, "spec_sha256": new_lineage["extension_spec_sha256"],
    })
    progress = {"elapsed_years": payload["elapsed_years"], "duration_years": END_YEAR,
                "completed": False, "checkpoint_sha256": verification.sha256(cp)}
    verification.atomic_write_json(verification.progress_path(NAME), progress)
    return progress


def summarize() -> dict:
    import numpy as np
    rows = verification.collect_segment_records(NAME)
    verification.write_segment_csv(NAME, rows)
    final = rows[-1]
    def window(start):
        part = [r for r in rows if r["elapsed_years"] >= start - verification.EPS]
        t = np.array([r["elapsed_years"] for r in part])
        return {
            "start_year": start,
            "mean_abs_volume_imbalance_sv": float(np.mean([abs(r["pycnocline_volume_imbalance_sv"]) for r in part])),
            "amoc_trend_sv_per_century": float(100 * np.polyfit(t, [r["amoc_sv"] for r in part], 1)[0]),
            "depth_trend_m_per_century": float(100 * np.polyfit(t, [r["pycnocline_depth_m"] for r in part], 1)[0]),
        }
    original_tail = window(600.0)
    result = {
        "lineage": validate_lineage(), "completed": final["elapsed_years"] >= END_YEAR - 1e-6,
        "elapsed_years": final["elapsed_years"], "final_amoc_sv": final["amoc_sv"],
        "final_depth_m": final["pycnocline_depth_m"],
        "final_volume_imbalance_sv": final["pycnocline_volume_imbalance_sv"],
        "original_evaluation_window": original_tail,
        "last_450_years": window(final["elapsed_years"] - 450),
        "last_100_years": window(final["elapsed_years"] - 100),
        "pass_original_pycnocline_thresholds": bool(original_tail["mean_abs_volume_imbalance_sv"] < 0.5 and abs(final["pycnocline_volume_imbalance_sv"]) < 0.05),
        "maximum_salt_error_ppm": max(abs(r["salt_conservation_error_ppm"]) for r in rows),
        "maximum_pre_projection_salt_error_ppm": max(abs(r["pre_projection_salt_conservation_error_ppm"]) for r in rows),
        "finished_unix": time.time(),
    }
    verification.atomic_write_json(OUT / "results.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", choices=["seed", "advance"])
    args = parser.parse_args()
    configure()
    if args.worker:
        if args.worker == "seed":
            result = seed()
        else:
            validate_lineage()
            result = verification.advance_segment_worker(NAME, 5.0)
        print("__RESULT__" + json.dumps(result), flush=True)
        return
    OUT.mkdir(parents=True, exist_ok=True)
    with output_directory_run_lock(OUT, run_kind="recovery_extension"):
        status_path = OUT / "status.json"
        try:
            elapsed = 1050.0
            mode = "seed"
            while elapsed < END_YEAR - 1e-6:
                log = OUT / "logs" / (f"{mode}_{elapsed:010.4f}.txt")
                log.parent.mkdir(parents=True, exist_ok=True)
                with log.open("w", encoding="utf-8") as handle:
                    child = subprocess.run([sys.executable, "-u", str(Path(__file__).resolve()), "--worker", mode],
                                           cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT, timeout=300)
                if child.returncode:
                    raise RuntimeError(f"Worker failed; see {log}")
                lines = log.read_text(encoding="utf-8").splitlines()
                result = json.loads(next(line[len("__RESULT__"):] for line in reversed(lines) if line.startswith("__RESULT__")))
                next_elapsed = float(result["elapsed_years"])
                if mode == "advance" and next_elapsed <= elapsed:
                    raise RuntimeError("Continuation worker made no progress")
                elapsed, mode = next_elapsed, "advance"
                verification.atomic_write_json(status_path, {"status": "running", "elapsed_years": elapsed, "end_year": END_YEAR, "updated_unix": time.time()})
                print(f"Checkpoint committed: {elapsed:.1f}/{END_YEAR:g} years", flush=True)
            result = summarize()
            shutil.copy2(Path(__file__), OUT / Path(__file__).name)
            verification.atomic_write_json(status_path, {"status": "completed", "elapsed_years": elapsed, "end_year": END_YEAR, "updated_unix": time.time(), "pass_original_pycnocline_thresholds": result["pass_original_pycnocline_thresholds"]})
            print("DONE: " + str(OUT / "results.json"), flush=True)
        except Exception as exc:
            verification.atomic_write_json(status_path, {"status": "failed", "error": repr(exc), "updated_unix": time.time()})
            raise


if __name__ == "__main__":
    main()
