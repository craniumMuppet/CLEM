#!/usr/bin/env python3
"""Run all v2.29.5 validation tasks in isolated parallel subprocesses."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TASK_NAMES = (
    "summary_ssp245",
    "summary_ssp585",
    "summary_ssp126",
    "summary_ssp460",
    "energy_audit",
    "arctic_reference",
    "arctic_reference_public_range_stress",
    "disabled_arctic_initialization",
    "monte_carlo_safety",
    "timestep_0p1",
    "timestep_0p05",
    "timestep_0p025",
    "control",
    "perturbation_cold",
    "perturbation_warm",
    "hosing_recovery",
    "resolution_2p5",
    "resolution_5p0",
    "resolution_10p0",
)


def run_task(name: str, output_dir: Path, timeout: float) -> tuple[str, dict]:
    output = output_dir / f"{name}.json"
    log = output_dir / f"{name}.log"
    command = [
        sys.executable,
        "-u",
        str(ROOT / "validate_v2295.py"),
        "--task",
        name,
        "--task-output",
        str(output),
    ]
    with log.open("w", encoding="utf-8") as handle:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            stdout=handle,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
        )
    if completed.returncode != 0:
        tail = "\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-50:])
        raise RuntimeError(f"Validation task {name} failed with exit code {completed.returncode}:\n{tail}")
    return name, json.loads(output.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=7200.0)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "validation_v2295_tasks_final",
    )
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    for path in output_dir.glob("*"):
        if path.is_file():
            path.unlink()

    tasks: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {
            executor.submit(run_task, name, output_dir, args.timeout): name
            for name in TASK_NAMES
        }
        for future in as_completed(futures):
            name, value = future.result()
            tasks[name] = value
            print(f"PASSED {name}", flush=True)

    if set(tasks) != set(TASK_NAMES):
        missing = sorted(set(TASK_NAMES) - set(tasks))
        raise RuntimeError(f"Missing validation tasks: {missing}")

    sys.path.insert(0, str(ROOT))
    from validate_v2295 import _assemble_records

    _assemble_records(tasks)
    print(f"Complete: {len(tasks)}/{len(TASK_NAMES)} validation tasks passed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
