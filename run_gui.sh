#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
python3 bootstrap_runtime.py
exec .venv/bin/python climate_model_gui.py
