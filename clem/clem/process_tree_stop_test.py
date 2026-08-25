#!/usr/bin/env python3
"""Verify that GUI termination stops a parent and all worker descendants."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from climate_model_gui import terminate_process_tree


def process_is_computing(pid: int) -> bool:
    """Return True while a process exists and is not a terminated zombie."""
    if os.name == "nt":
        completed = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return str(pid) in completed.stdout

    stat_path = Path(f"/proc/{pid}/stat")
    if not stat_path.exists():
        return False
    try:
        return stat_path.read_text(encoding="utf-8").split()[2] != "Z"
    except (OSError, IndexError):
        return False


def main() -> None:
    parent_code = """
import subprocess
import sys
import time
children = [
    subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])
    for _ in range(3)
]
print(' '.join(str(child.pid) for child in children), flush=True)
time.sleep(120)
"""

    creationflags = 0
    kwargs: dict[str, object] = {}
    if os.name == "nt":
        creationflags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True

    parent = subprocess.Popen(
        [sys.executable, "-c", parent_code],
        stdout=subprocess.PIPE,
        text=True,
        creationflags=creationflags,
        **kwargs,
    )
    assert parent.stdout is not None
    child_pids = [int(value) for value in parent.stdout.readline().split()]

    success, details = terminate_process_tree(parent, graceful_timeout_seconds=1.0)
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if parent.poll() is not None and not any(
            process_is_computing(pid) for pid in child_pids
        ):
            break
        time.sleep(0.1)

    live_children = [pid for pid in child_pids if process_is_computing(pid)]
    if not success or parent.poll() is None or live_children:
        raise RuntimeError(
            f"Process-tree stop failed: success={success}, "
            f"parent_returncode={parent.poll()}, live_children={live_children}, "
            f"details={details}"
        )
    print("PASS: parent and all worker descendants terminated")


if __name__ == "__main__":
    main()
