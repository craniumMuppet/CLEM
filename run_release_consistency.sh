#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
echo "Coupled Low-complexity Earth Model v2.29.28 - Physics Repair R13 release consistency check"
python check_release_identity.py
python verify_physics_local.py --worker-mode static
