#!/usr/bin/env python3
"""Run and combine current-source v2.29.28 validation at 5 and 10 degrees.

Canonical release artifacts are promoted out of a staging directory only after
both per-resolution validators and the cross-resolution combiner exit cleanly.
Failed diagnostics remain in staging and can never be mistaken for completion.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VALIDATOR = ROOT / "validate_v22928.py"
COMBINER = ROOT / "combine_v22928_validation.py"
ARTIFACT_NAMES = tuple(
    [f"SEA_ICE_VALIDATION_V2_29_28_{resolution}DEG.json" for resolution in (5, 10)]
    + [
        f"ARCTIC_GREENLAND_AMOC_VALIDATION_V2_29_28_{resolution}DEG.json"
        for resolution in (5, 10)
    ]
    + [f"COUPLED_TIMESERIES_V2_29_28_{resolution}DEG.csv" for resolution in (5, 10)]
    + ["VALIDATION_SUMMARY_V2_29_28.json"]
)


def _run(command: list[str]) -> None:
    print("RUN", subprocess.list2cmdline(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def _run_resolutions(commands: list[list[str]]) -> None:
    """Run resolution-isolated validators concurrently in one staging tree."""

    processes: list[tuple[list[str], subprocess.Popen[bytes]]] = []
    for command in commands:
        print("RUN", subprocess.list2cmdline(command), flush=True)
        processes.append((command, subprocess.Popen(command, cwd=ROOT)))
    failures: list[tuple[list[str], int]] = []
    try:
        for command, process in processes:
            return_code = process.wait()
            if return_code:
                failures.append((command, return_code))
    except BaseException:
        for _, process in processes:
            if process.poll() is None:
                process.terminate()
        raise
    if failures:
        command, return_code = failures[0]
        raise subprocess.CalledProcessError(return_code, command)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "release_validation")
    parser.add_argument("--segment-years", type=float, default=20.0)
    parser.add_argument("--test-results", type=Path, default=ROOT / "TEST_RESULTS_V2_29_28.json")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    missing = [str(path) for path in (VALIDATOR, COMBINER) if not path.is_file()]
    if missing:
        raise SystemExit("Missing coupled-validation dependency: " + ", ".join(missing))
    if not args.test_results.is_file():
        raise SystemExit(f"Missing engineering-test evidence: {args.test_results}")

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    existing = [output_dir / name for name in ARTIFACT_NAMES if (output_dir / name).exists()]
    if existing and not args.overwrite:
        detail = ", ".join(path.name for path in existing)
        raise SystemExit(f"Refusing to overwrite existing validation artifacts: {detail}")

    staging = Path(tempfile.mkdtemp(prefix="v22928-coupled-", dir=output_dir))
    try:
        _run_resolutions(
            [
                [
                    sys.executable,
                    str(VALIDATOR),
                    "--resolution",
                    str(resolution),
                    "--segment-years",
                    str(args.segment_years),
                    "--output-dir",
                    str(staging),
                ]
                for resolution in (5, 10)
            ]
        )
        _run(
            [
                sys.executable,
                str(COMBINER),
                "--output-dir",
                str(staging),
                "--test-results",
                str(args.test_results.resolve()),
            ]
        )

        missing_outputs = [name for name in ARTIFACT_NAMES if not (staging / name).is_file()]
        if missing_outputs:
            raise RuntimeError(
                "Successful coupled workflow did not produce: " + ", ".join(missing_outputs)
            )
        for name in ARTIFACT_NAMES:
            source = staging / name
            destination = output_dir / name
            if destination.exists():
                destination.unlink()
            source.replace(destination)
        shutil.rmtree(staging)
    except BaseException:
        print(f"Validation failed; noncanonical diagnostics retained in {staging}", flush=True)
        raise

    print(f"Coupled validation complete: {output_dir}", flush=True)


if __name__ == "__main__":
    main()
