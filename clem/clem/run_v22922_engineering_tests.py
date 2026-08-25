#!/usr/bin/env python3
"""Run one frozen-tree non-slow pytest invocation and retain raw v2.29.22 evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from climate_model import MODEL_VERSION

EXPECTED_VERSION = "2.29.22"
JSON_NAME = "TEST_RESULTS_V2_29_22.json"
TXT_NAME = "TEST_RESULTS_V2_29_22.txt"
EVENTS_NAME = "TEST_EVENTS_V2_29_22.ndjson"
JUNIT_NAME = "TEST_RESULTS_V2_29_22.junit.xml"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ProgressPlugin:
    def __init__(self, events_path: Path) -> None:
        self.events_path = events_path
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        self.events_path.write_text("", encoding="utf-8")
        self.collected = 0
        self.completed = 0
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.xfailed = 0
        self.xpassed = 0
        self.seen: set[str] = set()
        self.failures: list[dict[str, str]] = []
        self.outcomes: list[dict[str, Any]] = []

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        self.collected = len(session.items)
        print(
            f"PROGRESS 0/{self.collected} tests completed pytest_pid={os.getpid()}",
            flush=True,
        )

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        terminal = report.when == "call" or (
            report.when in {"setup", "teardown"} and report.failed
        )
        if not terminal or report.nodeid in self.seen:
            return
        self.seen.add(report.nodeid)
        self.completed += 1
        if report.passed:
            if hasattr(report, "wasxfail"):
                self.xpassed += 1
                outcome = "XPASS"
            else:
                self.passed += 1
                outcome = "PASSED"
        elif report.skipped:
            if hasattr(report, "wasxfail"):
                self.xfailed += 1
                outcome = "XFAIL"
            else:
                self.skipped += 1
                outcome = "SKIPPED"
        else:
            self.failed += 1
            outcome = "FAILED"
            self.failures.append(
                {"nodeid": report.nodeid, "longrepr": str(report.longrepr)}
            )
        event = {
            "sequence": self.completed,
            "nodeid": report.nodeid,
            "outcome": outcome,
            "duration_seconds": float(report.duration),
            "when": report.when,
        }
        self.outcomes.append(event)
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
        print(
            f"PROGRESS {self.completed}/{self.collected} tests completed "
            f"pytest_pid={os.getpid()} outcome={outcome} nodeid={report.nodeid}",
            flush=True,
        )


def write_outputs(
    output_dir: Path,
    plugin: ProgressPlugin,
    exit_code: int,
    pytest_args: list[str],
) -> None:
    complete = plugin.completed == plugin.collected and plugin.collected > 0
    passed = bool(exit_code == 0 and complete and plugin.failed == 0)
    junit_path = output_dir / JUNIT_NAME
    raw_evidence = {
        EVENTS_NAME: {
            "sha256": sha256(plugin.events_path),
            "size_bytes": plugin.events_path.stat().st_size,
        },
        JUNIT_NAME: {
            "sha256": sha256(junit_path),
            "size_bytes": junit_path.stat().st_size,
        },
    }
    reported_pytest_args = [
        f"--junitxml={JUNIT_NAME}" if item.startswith("--junitxml=") else item
        for item in pytest_args
    ]
    payload: dict[str, Any] = {
        "schema_version": "2.0",
        "model_version": MODEL_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "test_selection": "single frozen-tree complete repository-defined non-slow suite",
        "pytest_args": reported_pytest_args,
        "pytest_pid": os.getpid(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "collected": plugin.collected,
        "completed": plugin.completed,
        "passed": plugin.passed,
        "failed": plugin.failed,
        "skipped": plugin.skipped,
        "xfailed": plugin.xfailed,
        "xpassed": plugin.xpassed,
        "pytest_exit_code": int(exit_code),
        "complete": complete,
        "engineering_integrity_passed": passed,
        "raw_evidence": raw_evidence,
        "outcomes": plugin.outcomes,
        "failures": plugin.failures,
    }
    (output_dir / JSON_NAME).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / TXT_NAME).write_text(
        "\n".join(
            [
                "EGCM v2.29.22 single-invocation non-slow test results",
                f"collected={plugin.collected}",
                f"completed={plugin.completed}",
                f"passed={plugin.passed}",
                f"failed={plugin.failed}",
                f"skipped={plugin.skipped}",
                f"engineering_integrity_passed={str(passed).lower()}",
                f"pytest_exit_code={exit_code}",
                f"raw_events={EVENTS_NAME}",
                f"junit_xml={JUNIT_NAME}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("."))
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if MODEL_VERSION != EXPECTED_VERSION:
        raise SystemExit(f"Expected {EXPECTED_VERSION}, found {MODEL_VERSION}")
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    pytest_args = list(args.pytest_args)
    if pytest_args and pytest_args[0] == "--":
        pytest_args = pytest_args[1:]
    if not pytest_args:
        pytest_args = ["-m", "not slow", "-ra"]
    pytest_args = [*pytest_args, f"--junitxml={output_dir / JUNIT_NAME}"]
    plugin = ProgressPlugin(output_dir / EVENTS_NAME)
    exit_code = int(pytest.main(pytest_args, plugins=[plugin]))
    write_outputs(output_dir, plugin, exit_code, pytest_args)
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
