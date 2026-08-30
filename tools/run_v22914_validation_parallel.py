#!/usr/bin/env python3
"""Run all v2.29.14 validation tasks in isolated parallel subprocesses.

The runner records every task independently, reports all failures instead of
aborting on the first one, and supports ``--resume`` so completed task records
can be reused after a validator-only fix. Final records are assembled only when
the complete task inventory is present and valid.
"""

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
    "hybrid_amoc",
    "long_ssp245",
    "resolution_2p5",
    "resolution_5p0",
    "resolution_10p0",
)


def load_task_output(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Validation task record is not an object: {path}")
    return value


def run_task(name: str, output_dir: Path, timeout: float) -> tuple[str, dict]:
    output = output_dir / f"{name}.json"
    log = output_dir / f"{name}.log"
    command = [
        sys.executable,
        "-u",
        str(ROOT / "validate_v22914.py"),
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
        tail = "\n".join(
            log.read_text(encoding="utf-8", errors="replace").splitlines()[-50:]
        )
        raise RuntimeError(
            f"Validation task {name} failed with exit code "
            f"{completed.returncode}:\n{tail}"
        )
    return name, load_task_output(output)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=7200.0)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "validation_v22914_tasks_final",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse valid task JSON records and run only missing tasks.",
    )
    args = parser.parse_args()
    if args.workers < 1:
        raise SystemExit("--workers must be at least 1")
    if args.timeout <= 0.0:
        raise SystemExit("--timeout must be positive")

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    if not args.resume:
        for path in output_dir.glob("*"):
            if path.is_file():
                path.unlink()

    tasks: dict[str, dict] = {}
    pending: list[str] = []
    for name in TASK_NAMES:
        output = output_dir / f"{name}.json"
        if args.resume and output.is_file():
            try:
                tasks[name] = load_task_output(output)
            except Exception as exc:
                print(f"INVALID {name}: {exc}", file=sys.stderr, flush=True)
                output.unlink(missing_ok=True)
                pending.append(name)
            else:
                print(f"REUSED {name}", flush=True)
        else:
            pending.append(name)

    failures: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(run_task, name, output_dir, args.timeout): name
            for name in pending
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                completed_name, value = future.result()
            except Exception as exc:
                failures[name] = str(exc)
                print(f"FAILED {name}: {exc}", file=sys.stderr, flush=True)
            else:
                tasks[completed_name] = value
                print(f"PASSED {completed_name}", flush=True)

    if failures:
        details = "\n\n".join(
            f"{name}:\n{message}" for name, message in sorted(failures.items())
        )
        raise RuntimeError(
            f"{len(failures)} validation task(s) failed; completed records were retained for --resume.\n\n{details}"
        )

    missing = sorted(set(TASK_NAMES) - set(tasks))
    if missing:
        raise RuntimeError(f"Missing validation tasks: {missing}")

    sys.path.insert(0, str(ROOT))
    from validate_v22914 import _assemble_records

    _assemble_records(tasks)
    print(
        f"Complete: {len(tasks)}/{len(TASK_NAMES)} validation tasks passed",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
