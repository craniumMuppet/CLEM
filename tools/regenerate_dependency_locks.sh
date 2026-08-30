#!/usr/bin/env sh
set -eu

uv pip compile requirements.in --generate-hashes --output-file requirements.lock
uv pip compile requirements-dev.in --generate-hashes --output-file requirements-dev.lock
