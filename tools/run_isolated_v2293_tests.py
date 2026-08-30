#!/usr/bin/env python3
"""Run each pytest node in an isolated subprocess with resumable results."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nodes", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--logs", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--rerun-failures", action="store_true")
    parser.add_argument("--max-tests", type=int, default=0)
    return parser.parse_args()


def load_nodes(path: Path) -> list[str]:
    nodes = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    return [node for node in nodes if "::" in node and not node.startswith("=")]


def load_results(path: Path) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return results
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        results[str(record["node"])] = record
    return results


def safe_name(node: str) -> str:
    digest = hashlib.sha256(node.encode("utf-8")).hexdigest()[:16]
    return f"{digest}.log"


def run_node(root: Path, node: str, log_dir: Path, timeout: float) -> dict[str, Any]:
    started = time.monotonic()
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        node,
    ]
    environment = os.environ.copy()
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    popen_kwargs: dict[str, Any] = {
        "cwd": root,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "env": environment,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["start_new_session"] = True
    process = subprocess.Popen(command, **popen_kwargs)
    timed_out = False
    try:
        output, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        if os.name == "nt":
            process.kill()
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        output, _ = process.communicate()
    seconds = time.monotonic() - started
    log_path = log_dir / safe_name(node)
    log_path.write_text(output, encoding="utf-8")
    if timed_out:
        status = "timeout"
    elif process.returncode == 0:
        status = "passed"
    else:
        status = "failed"
    return {
        "node": node,
        "status": status,
        "returncode": process.returncode,
        "seconds": round(seconds, 3),
        "log": str(log_path),
        "tail": "\n".join(output.splitlines()[-40:]),
    }


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    nodes = load_nodes(args.nodes)
    args.logs.mkdir(parents=True, exist_ok=True)
    if args.reset:
        args.results.unlink(missing_ok=True)
        for path in args.logs.glob("*.log"):
            path.unlink()
    previous = load_results(args.results)
    pending = []
    for node in nodes:
        prior = previous.get(node)
        if prior is None:
            pending.append(node)
        elif args.rerun_failures and prior.get("status") != "passed":
            pending.append(node)
    total = len(nodes)
    if args.max_tests > 0:
        pending = pending[: args.max_tests]
    completed_before = len(previous)
    print(
        f"Isolated suite: {total} nodes; {completed_before} retained; "
        f"{len(pending)} pending; workers={args.workers}",
        flush=True,
    )
    if not pending:
        failures = [r for r in previous.values() if r.get("status") != "passed"]
        print(f"Complete: {total - len(failures)} passed, {len(failures)} failed", flush=True)
        return 1 if failures else 0

    write_lock = threading.Lock()
    completed = completed_before
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {
            executor.submit(run_node, root, node, args.logs, args.timeout): node
            for node in pending
        }
        for future in as_completed(futures):
            record = future.result()
            with write_lock:
                with args.results.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(record, sort_keys=True) + "\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                completed += 1
                print(
                    f"[{completed}/{total}] {record['status'].upper():7s} "
                    f"{record['seconds']:7.2f}s {record['node']}",
                    flush=True,
                )

    final = load_results(args.results)
    unresolved = [node for node in nodes if node not in final]
    failures = [final[node] for node in nodes if node in final and final[node].get("status") != "passed"]
    passed = sum(1 for node in nodes if final.get(node, {}).get("status") == "passed")
    print(f"Checkpoint: {passed} passed, {len(failures)} failed, {len(unresolved)} pending", flush=True)
    if unresolved:
        return 2
    if failures:
        for record in failures:
            print(f"FAIL: {record['node']} ({record.get('status')})", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
