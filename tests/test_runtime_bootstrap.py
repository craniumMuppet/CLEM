"""Runtime dependency bootstrap regressions."""

from __future__ import annotations

from importlib import metadata
from pathlib import Path

import bootstrap_runtime as bootstrap


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_lock_parser_includes_production_teos_dependency() -> None:
    pins = bootstrap.locked_requirements()
    assert pins["gsw"] == "3.6.23"
    assert pins["numpy"] == "2.3.5"
    assert len(pins) > 6


def test_dependency_check_reports_missing_and_wrong_versions(
    monkeypatch, tmp_path: Path
) -> None:
    lock = tmp_path / "requirements.lock"
    lock.write_text("Example_Package==1.2.3\nmissing-one==4.5.6\n", encoding="utf-8")

    def fake_version(name: str) -> str:
        if name == "example-package":
            return "1.0.0"
        raise metadata.PackageNotFoundError(name)

    monkeypatch.setattr(bootstrap.metadata, "version", fake_version)
    assert bootstrap.dependency_mismatches(lock) == [
        "example-package 1.0.0 (requires 1.2.3)",
        "missing-one (missing; requires 4.5.6)",
    ]


def test_launchers_bootstrap_and_use_the_project_environment() -> None:
    windows = (ROOT / "run_gui.bat").read_text(encoding="utf-8")
    unix = (ROOT / "run_gui.sh").read_text(encoding="utf-8")
    assert "bootstrap_runtime.py" in windows
    assert '.venv\\Scripts\\pythonw.exe' in windows
    assert "bootstrap_runtime.py" in unix
    assert ".venv/bin/python" in unix


def test_generated_runtime_environment_is_excluded_from_release_packages() -> None:
    fingerprint = (ROOT / "release_tree_fingerprint.py").read_text(encoding="utf-8")
    packager = (ROOT / "tools" / "package_v22923.py").read_text(encoding="utf-8")
    assert '".venv"' in fingerprint
    assert '".venv"' in packager
    assert '"bootstrap_runtime.py"' in packager
