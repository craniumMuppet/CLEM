#!/usr/bin/env python3
"""Create and synchronize CLEM's project-local runtime environment."""

from __future__ import annotations

import argparse
from importlib import metadata
from pathlib import Path
import re
import subprocess
import sys
import venv


ROOT = Path(__file__).resolve().parent
LOCK_FILE = ROOT / "requirements.lock"
VENV_DIR = ROOT / ".venv"
PIN_PATTERN = re.compile(r"^([A-Za-z0-9_.-]+)==([^;\s]+)")


def locked_requirements(path: Path = LOCK_FILE) -> dict[str, str]:
    """Return normalized package names and exact versions from the runtime lock."""
    pins: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        match = PIN_PATTERN.match(raw_line.strip())
        if match is None:
            continue
        name, version = match.groups()
        pins[re.sub(r"[-_.]+", "-", name).lower()] = version
    if not pins:
        raise RuntimeError(f"No exact dependency pins were found in {path}")
    return pins


def dependency_mismatches(path: Path = LOCK_FILE) -> list[str]:
    """Describe missing or wrong-version packages in the active interpreter."""
    mismatches: list[str] = []
    for name, expected in locked_requirements(path).items():
        try:
            installed = metadata.version(name)
        except metadata.PackageNotFoundError:
            mismatches.append(f"{name} (missing; requires {expected})")
            continue
        if installed != expected:
            mismatches.append(f"{name} {installed} (requires {expected})")
    return mismatches


def environment_python(venv_dir: Path = VENV_DIR) -> Path:
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _check_environment(python: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(python), str(Path(__file__).resolve()), "--check-current"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def ensure_runtime() -> Path:
    """Create/update .venv from the exact runtime lock and return its Python."""
    if sys.version_info < (3, 12):
        raise RuntimeError(
            f"CLEM requires Python 3.12 or newer; found {sys.version.split()[0]}"
        )
    if not LOCK_FILE.is_file():
        raise RuntimeError(f"Missing runtime dependency lock: {LOCK_FILE}")

    python = environment_python()
    if not python.is_file():
        print(f"Creating CLEM runtime environment in {VENV_DIR} ...", flush=True)
        venv.EnvBuilder(with_pip=True).create(VENV_DIR)
    if not python.is_file():
        raise RuntimeError(f"Virtual environment did not create {python}")

    check = _check_environment(python)
    if check.returncode != 0:
        print("Installing or updating CLEM runtime dependencies ...", flush=True)
        subprocess.run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "-r",
                str(LOCK_FILE),
            ],
            cwd=ROOT,
            check=True,
        )
        check = _check_environment(python)
        if check.returncode != 0:
            details = check.stdout.strip() or check.stderr.strip()
            raise RuntimeError(
                "The CLEM runtime environment is still incomplete after installation."
                + (f"\n{details}" if details else "")
            )

    print("CLEM runtime dependencies are ready.", flush=True)
    return python


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-current",
        action="store_true",
        help="check the active interpreter against requirements.lock without installing",
    )
    args = parser.parse_args()
    if args.check_current:
        mismatches = dependency_mismatches()
        if mismatches:
            print("\n".join(mismatches))
            return 1
        return 0
    ensure_runtime()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"CLEM dependency setup failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
