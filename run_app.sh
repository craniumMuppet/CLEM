#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
python3 -m streamlit run app.py
