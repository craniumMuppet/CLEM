#!/usr/bin/env python3
"""Create the tested-code-and-scientific-input fingerprint for EGCM v2.29.28."""
from __future__ import annotations

import json

from v22928_release_integrity import FINGERPRINT_JSON, ROOT, create_fingerprint_payload


def main() -> None:
    payload = create_fingerprint_payload()
    target = ROOT / FINGERPRINT_JSON
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {target.name}: {payload['file_count']} files")
    print(f"Aggregate SHA-256: {payload['aggregate_sha256']}")


if __name__ == "__main__":
    main()
