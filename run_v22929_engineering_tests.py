#!/usr/bin/env python3
"""Run the canonical tree-bound v2.29.29 engineering regression suite."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from climate_model import MODEL_VERSION
from tools.v22929_release_integrity import (
    ROOT,
    TEST_EVENTS,
    TEST_JSON,
    TEST_JUNIT,
    TEST_TXT,
    create_fingerprint_payload,
)

EXPECTED_VERSION = "2.29.29"
DECLARED_PYTEST_REQUIREMENT = "pytest==9.1.1"

DEFAULT_TEST_ARGS = [
    "tests/test_2026_arctic_observational_recalibration.py",
    "tests/test_v22929_release_finalization.py",
    "tests/test_v22929_coupled_fail_closed.py",
    "tests/test_six_source_arctic_validation_stack.py",
    "tests/test_sea_ice_actual_fix.py",
    "tests/test_v2297_review_fixes.py",
    "tests/test_2026_arctic_data_processing_repairs.py",
    "tests/test_2026_sea_ice_scientific_review_fixes.py",
    "tests/test_v22917_arctic_sweep_integrity.py",
    "tests/test_v22918_release_corrections.py",
    "tests/test_v22920_prognostic_sea_ice.py",
    "tests/test_v22920_review_corrections.py",
    "tests/test_v22922_engineering_corrections.py",
    "tests/test_v22923_engineering_corrections.py",
    "tests/test_v22925_review_cleanup.py",
    "tests/test_v2295_physical_integrity.py::test_version_native_cycle_and_amoc_physics_defaults",
    "tests/test_v2299_scientific_review_fixes.py",
    "tests/test_v229_coupled_arctic_ocean.py::test_reference_cycle_contains_periodic_sector_ocean_states",
    "tests/test_v229_coupled_arctic_ocean.py::test_basal_heat_flux_increases_with_ocean_temperature",
    "tests/test_v229_coupled_arctic_ocean.py::test_open_water_exchange_is_two_way",
    "tests/test_v229_coupled_arctic_ocean.py::test_transient_ocean_surface_exchange_is_equal_and_opposite",
    "-k",
    (
        "not reference_cache_identity_includes_longwave_damping and "
        "not zero_lateral_restoring_is_valid_and_negative_is_rejected and "
        "not native_amoc_reference_converges_without_canonical_substitution and "
        "not reference_area_mean_resolution_spread_is_reduced"
    ),
    "--tb=short",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class EvidencePlugin:
    def __init__(self, events_path: Path) -> None:
        self.events_path = events_path
        self.events_path.write_text("", encoding="utf-8")
        self.collected = 0
        self.completed = 0
        self.passed = 0
        self.failed = 0
        self.errors = 0
        self.skipped = 0
        self.xfailed = 0
        self.xpassed = 0
        self.seen: set[str] = set()
        self.outcomes: list[dict[str, Any]] = []
        self.failures: list[dict[str, str]] = []

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        self.collected = len(session.items)
        print(f"PROGRESS 0/{self.collected} pytest_pid={os.getpid()}", flush=True)

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
        elif report.when == "call":
            self.failed += 1
            outcome = "FAILED"
        else:
            self.errors += 1
            outcome = "ERROR"
        if report.failed:
            self.failures.append({"nodeid": report.nodeid, "longrepr": str(report.longrepr)})
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
            f"PROGRESS {self.completed}/{self.collected} outcome={outcome} nodeid={report.nodeid}",
            flush=True,
        )


def write_outputs(
    output_dir: Path,
    plugin: EvidencePlugin,
    pytest_exit_code: int,
    runner_exit_code: int,
    pytest_args: list[str],
    tree_before: dict[str, Any],
    tree_after: dict[str, Any],
) -> None:
    tree_unchanged = tree_before == tree_after
    complete = plugin.collected > 0 and plugin.completed == plugin.collected
    engineering_passed = bool(
        pytest_exit_code == runner_exit_code == 0
        and complete
        and plugin.failed == plugin.errors == 0
        and tree_unchanged
    )
    junit_path = output_dir / TEST_JUNIT
    raw_evidence = {
        TEST_EVENTS: {
            "sha256": sha256_file(plugin.events_path),
            "size_bytes": plugin.events_path.stat().st_size,
        },
        TEST_JUNIT: {
            "sha256": sha256_file(junit_path),
            "size_bytes": junit_path.stat().st_size,
        },
    }
    reported_args = [
        f"--junitxml={TEST_JUNIT}" if item.startswith("--junitxml=") else item
        for item in pytest_args
    ]
    nodeids = [str(item["nodeid"]) for item in plugin.outcomes]
    payload: dict[str, Any] = {
        "schema_version": 4,
        "model_version": MODEL_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "test_selection": "single canonical unchanged-tree bounded release regression suite",
        "runner_command": subprocess.list2cmdline([sys.executable, Path(__file__).name]),
        "pytest_args": reported_args,
        "pytest_pid": os.getpid(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "pytest_version": pytest.__version__,
        "declared_pytest_requirement": DECLARED_PYTEST_REQUIREMENT,
        "release_tree_fingerprint": tree_before,
        "post_pytest_release_tree": {
            "file_count": tree_after["file_count"],
            "aggregate_sha256": tree_after["aggregate_sha256"],
        },
        "tree_unchanged_during_pytest": tree_unchanged,
        "collected": plugin.collected,
        "completed": plugin.completed,
        "passed": plugin.passed,
        "failed": plugin.failed,
        "errors": plugin.errors,
        "skipped": plugin.skipped,
        "xfailed": plugin.xfailed,
        "xpassed": plugin.xpassed,
        "pytest_exit_code": int(pytest_exit_code),
        "runner_exit_code": int(runner_exit_code),
        "complete": complete,
        "engineering_integrity_passed": engineering_passed,
        "raw_evidence": raw_evidence,
        "nodeids": nodeids,
        "outcomes": plugin.outcomes,
        "failures": plugin.failures,
        "scope": "bounded release/recalibration and Arctic physical/coupled regression suite",
    }
    (output_dir / TEST_JSON).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / TEST_TXT).write_text(
        "\n".join(
            [
                "CLEM v2.29.29 unchanged-tree machine-verifiable test evidence",
                f"release_tree_sha256={tree_before['aggregate_sha256']}",
                f"release_tree_file_count={tree_before['file_count']}",
                f"tree_unchanged_during_pytest={str(tree_unchanged).lower()}",
                f"collected={plugin.collected}",
                f"completed={plugin.completed}",
                f"passed={plugin.passed}",
                f"failed={plugin.failed}",
                f"errors={plugin.errors}",
                f"engineering_integrity_passed={str(engineering_passed).lower()}",
                f"pytest_exit_code={pytest_exit_code}",
                f"runner_exit_code={runner_exit_code}",
                f"raw_events={TEST_EVENTS}",
                f"junit_xml={TEST_JUNIT}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT)
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if MODEL_VERSION != EXPECTED_VERSION:
        raise SystemExit(f"Expected {EXPECTED_VERSION}, found {MODEL_VERSION}")
    if pytest.__version__ != DECLARED_PYTEST_REQUIREMENT.split("==", 1)[1]:
        raise SystemExit(
            f"Expected {DECLARED_PYTEST_REQUIREMENT}, found pytest=={pytest.__version__}"
        )
    output_dir = args.output_dir.resolve()
    if output_dir != ROOT:
        raise SystemExit("Canonical evidence must be written in the release root")
    pytest_args = list(args.pytest_args)
    if pytest_args and pytest_args[0] == "--":
        pytest_args = pytest_args[1:]
    if not pytest_args:
        pytest_args = list(DEFAULT_TEST_ARGS)
    pytest_args.append(f"--junitxml={output_dir / TEST_JUNIT}")
    tree_before = create_fingerprint_payload()
    plugin = EvidencePlugin(output_dir / TEST_EVENTS)
    pytest_exit_code = int(pytest.main(pytest_args, plugins=[plugin]))
    tree_after = create_fingerprint_payload()
    tree_changed = tree_before != tree_after
    runner_exit_code = pytest_exit_code if pytest_exit_code else (3 if tree_changed else 0)
    write_outputs(
        output_dir,
        plugin,
        pytest_exit_code,
        runner_exit_code,
        pytest_args,
        tree_before,
        tree_after,
    )
    raise SystemExit(runner_exit_code)


if __name__ == "__main__":
    main()
