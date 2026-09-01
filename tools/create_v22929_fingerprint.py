#!/usr/bin/env python3
"""Publish the unchanged-tree fingerprint already captured by the test runner."""
from __future__ import annotations

import json

from v22929_release_integrity import (
    FINGERPRINT_JSON,
    ROOT,
    TEST_JSON,
    load_json,
    verify_fingerprint_payload,
)


def main() -> None:
    tests = load_json(ROOT / TEST_JSON)
    payload = tests.get("release_tree_fingerprint")
    if not isinstance(payload, dict):
        raise SystemExit("Test evidence lacks an unchanged-tree fingerprint")
    errors = verify_fingerprint_payload(payload)
    if errors:
        raise SystemExit("Test-bound fingerprint is stale:\n- " + "\n- ".join(errors[:20]))
    target = ROOT / FINGERPRINT_JSON
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {target.name}: {payload['file_count']} files")
    print(f"Aggregate SHA-256: {payload['aggregate_sha256']}")


if __name__ == "__main__":
    main()
