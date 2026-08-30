#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXPECTED_MODEL_VERSION = "2.29.28"
EXPECTED_REPAIR_REVISION = "R13"
EXPECTED_MODEL_NAME = "Coupled Low-complexity Earth Model"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


model_text = read("climate_model.py")
match = re.search(r'^MODEL_VERSION\s*=\s*["\']([^"\']+)["\']', model_text, re.MULTILINE)
if not match:
    raise SystemExit("MODEL_VERSION not found")
model_version = match.group(1)

with (ROOT / "pyproject.toml").open("rb") as handle:
    project = tomllib.load(handle)["project"]
project_version = str(project["version"])
project_name = str(project["name"])

metadata = json.loads(read("RELEASE_METADATA.json"))
readme = read("README.md")
app_head = "\n".join(read("app.py").splitlines()[:8])
app_text = read("app.py")
gui_text = read("climate_model_gui.py")
ci_text = read(".github/workflows/ci.yml")
release_cmd = read("RUN_RELEASE_CONSISTENCY.cmd")
validation_cmd = read("RUN_OUT_OF_SAMPLE_VALIDATION.cmd")

checks = {
    "MODEL_NAME_is_CLEM_long_name": f'MODEL_NAME = "{EXPECTED_MODEL_NAME}"' in model_text,
    "MODEL_VERSION_is_2.29.28": model_version == EXPECTED_MODEL_VERSION,
    "pyproject_version_is_2.29.28": project_version == EXPECTED_MODEL_VERSION,
    "pyproject_name_matches_CLEM_long_name": project_name == "coupled-low-complexity-earth-model",
    "MODEL_VERSION_matches_pyproject": model_version == project_version,
    "README_title_is_2.29.28": readme.startswith(f"# {EXPECTED_MODEL_NAME} v{EXPECTED_MODEL_VERSION}\n"),
    "README_does_not_claim_CLEM_v2.13": "CLEM v2.13" not in readme,
    "README_uses_long_model_name": EXPECTED_MODEL_NAME in readme,
    "metadata_model_version": metadata.get("model_version") == EXPECTED_MODEL_VERSION,
    "metadata_model_name": metadata.get("model_name") == EXPECTED_MODEL_NAME,
    "metadata_repair_revision": metadata.get("repair_revision") == EXPECTED_REPAIR_REVISION,
    "repair_revision_not_model_version": metadata.get("repair_label_is_model_version") is False,
    "app_header_not_stale_v2.29.23": "v2.29.23" not in app_head,
    "streamlit_title_uses_MODEL_NAME_AND_VERSION": 'st.title(f"{MODEL_NAME} v{MODEL_VERSION}")' in app_text,
    "desktop_title_uses_MODEL_NAME_AND_VERSION": 'APP_TITLE = f"{MODEL_NAME} {MODEL_VERSION}"' in gui_text,
    "old_brand_absent_from_active_runtime_surfaces": "Emergent-Sensitivity Global Climate Model" not in (model_text + app_text + gui_text + read("pyproject.toml")),
    "CI_uses_2.29.28_identity": "clem-v2.29.28-physics-r13-ci" in ci_text and "clem-v2.13" not in ci_text,
    "release_launcher_uses_long_name_and_2.29.28": f"{EXPECTED_MODEL_NAME} v2.29.28" in release_cmd and "CLEM v2.13" not in release_cmd,
    "validation_launcher_uses_long_name_and_2.29.28": f"{EXPECTED_MODEL_NAME} v2.29.28" in validation_cmd and "CLEM v2.12" not in validation_cmd,
}

for name, ok in checks.items():
    print(f"{name}: {'PASS' if ok else 'FAIL'}")

if not all(checks.values()):
    raise SystemExit(1)

print("RELEASE IDENTITY CHECK PASSED")
