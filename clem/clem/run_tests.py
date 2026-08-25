#!/usr/bin/env python3
"""Run the complete EGCM pytest inventory in isolated subprocesses.

Each collected node executes in a fresh process with an external timeout. Pytest
is allowed to complete setup, call, teardown, fixture finalizers, and terminal
reporting normally; no in-process forced exit is used. The default is the full
inventory. Use ``--fast`` only for a deliberately reduced development pass.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def marker_expression(fast: bool) -> str:
    if not fast:
        return ""
    return "not slow"


def pytest_command(
    target: str | None,
    expression: str,
    extra: list[str],
) -> list[str]:
    command = [
        sys.executable,
        "-u",
        "-m",
        "pytest",
        "-o",
        "addopts=",
        "-ra",
    ]
    if target is not None:
        command.append(target)
    if expression:
        command.extend(["-m", expression])
    command.extend(extra)
    return command


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Run the canonical normal suite by excluding only tests marked slow.",
    )
    # Backward-compatible switches. The complete suite is already the default.
    parser.add_argument("--include-slow", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--include-calibration", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--include-gui", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--all", action="store_true", help="Run the complete inventory (default).")
    parser.add_argument(
        "--combined",
        action="store_true",
        help="Run one normal pytest process instead of isolated test cases.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=1800.0,
        help="Maximum runtime for each isolated test case.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=0,
        help="Retries after an isolated timeout or abnormal pytest exit.",
    )
    parser.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="Additional arguments passed to pytest after '--'.",
    )
    args = parser.parse_args()

    if args.all or args.include_slow or args.include_calibration or args.include_gui:
        args.fast = False
    if args.timeout_seconds <= 0.0:
        raise SystemExit("--timeout-seconds must be positive")
    if args.retries < 0:
        raise SystemExit("--retries cannot be negative")

    root = Path(__file__).resolve().parent
    expression = marker_expression(args.fast)
    extra = list(args.pytest_args)
    if extra and extra[0] == "--":
        extra = extra[1:]

    env = os.environ.copy()
    env.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("OPENBLAS_NUM_THREADS", "1")
    env.setdefault("OMP_NUM_THREADS", "1")
    env.setdefault("MKL_NUM_THREADS", "1")
    env.setdefault("NUMEXPR_NUM_THREADS", "1")

    if args.combined:
        completed = subprocess.run(
            pytest_command(None, expression, extra),
            cwd=root,
            env=env,
            check=False,
        )
        raise SystemExit(completed.returncode)

    test_files = sorted((root / "tests").glob("test_*.py"))
    if not test_files:
        raise SystemExit("No tests/test_*.py modules were found.")

    failures: list[str] = []
    selected_nodes: list[str] = []
    for path in test_files:
        relative = path.relative_to(root).as_posix()
        try:
            collect = subprocess.run(
                pytest_command(relative, expression, ["--collect-only", "-q", *extra]),
                cwd=root,
                env=env,
                check=False,
                capture_output=True,
                text=True,
                timeout=args.timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            failures.append(f"{relative}: collection timeout")
            continue
        if collect.returncode not in (0, 5):
            failures.append(f"{relative}: collection exit {collect.returncode}")
            print(collect.stdout, end="")
            print(collect.stderr, end="", file=sys.stderr)
            continue
        nodes = [
            line.strip()
            for line in collect.stdout.splitlines()
            if line.strip().startswith("tests/") and "::" in line
        ]
        selected_nodes.extend(nodes)

    if failures:
        raise SystemExit("Test collection failures:\n- " + "\n- ".join(failures))
    if not selected_nodes:
        print("No tests selected for the chosen markers.")
        return

    print(
        f"Collected {len(selected_nodes)} test cases "
        f"({'fast subset' if args.fast else 'complete inventory'}).",
        flush=True,
    )
    for index, node in enumerate(selected_nodes, start=1):
        print(f"[{index}/{len(selected_nodes)}] {node}", flush=True)
        final_error: str | None = None
        for attempt in range(args.retries + 1):
            if attempt:
                print(
                    f"Retry {attempt}/{args.retries}: {node}",
                    file=sys.stderr,
                    flush=True,
                )
            try:
                completed = subprocess.run(
                    pytest_command(node, expression, ["-q", *extra]),
                    cwd=root,
                    env=env,
                    check=False,
                    timeout=args.timeout_seconds,
                )
            except subprocess.TimeoutExpired:
                final_error = f"{node}: timeout after {args.timeout_seconds:g}s"
                print(f"TIMEOUT: {node}", file=sys.stderr, flush=True)
                continue
            if completed.returncode in (0, 5):
                final_error = None
                break
            final_error = f"{node}: pytest exit {completed.returncode}"
        if final_error is not None:
            failures.append(final_error)

    if failures:
        raise SystemExit("Isolated test failures:\n- " + "\n- ".join(failures))
    print(f"\nAll {len(selected_nodes)} isolated test cases passed with normal teardown.")


if __name__ == "__main__":
    main()
