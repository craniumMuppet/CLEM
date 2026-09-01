#!/usr/bin/env python3
"""Fail closed if the EGCM v2.29.29 tested tree differs from its fingerprint."""
from __future__ import annotations

from v22929_release_integrity import FINGERPRINT_JSON, ROOT, load_json, verify_fingerprint_payload


def main() -> None:
    path = ROOT / FINGERPRINT_JSON
    if not path.is_file():
        raise SystemExit(f"Missing {FINGERPRINT_JSON}")
    errors = verify_fingerprint_payload(load_json(path))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(f"Fingerprint verification failed with {len(errors)} error(s)")
    print("Fingerprint verification: PASS")


if __name__ == "__main__":
    main()
