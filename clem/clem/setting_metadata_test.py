#!/usr/bin/env python3
"""Coverage tests for v2.17.0 setting tooltips."""

from __future__ import annotations

import ast
from pathlib import Path

from climate_model_gui import MC_RANGE_SPECS
from setting_metadata import CONFIDENCE_SCALE, SETTING_INFO, setting_info, setting_tooltip


ROOT = Path(__file__).resolve().parent
STREAMLIT_SETTING_CALLS = {
    "slider",
    "number_input",
    "selectbox",
    "checkbox",
    "select_slider",
    "radio",
}


def desktop_keys() -> set[str]:
    tree = ast.parse((ROOT / "climate_model_gui.py").read_text(encoding="utf-8"))
    keys: set[str] = {"output", "preset"}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in {"_field", "_checkbox"} or len(node.args) < 3:
            continue
        try:
            keys.add(ast.literal_eval(node.args[2]))
        except (ValueError, TypeError):
            pass
    return keys


def streamlit_keys_and_missing_help() -> tuple[set[str], list[str]]:
    tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
    keys: set[str] = set()
    missing_help: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        call = node.value
        if not isinstance(target, ast.Name) or not isinstance(call, ast.Call):
            continue
        if not (
            isinstance(call.func, ast.Attribute)
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == "st"
            and call.func.attr in STREAMLIT_SETTING_CALLS
        ):
            continue
        keys.add(target.id)
        if not any(keyword.arg == "help" for keyword in call.keywords):
            missing_help.append(target.id)
    return keys, missing_help


def run() -> None:
    assert set(CONFIDENCE_SCALE) == {"Low", "Medium", "High", "Very high"}
    for key, info in SETTING_INFO.items():
        assert info.confidence in CONFIDENCE_SCALE, (key, info.confidence)
        text = info.tooltip()
        assert "Uncertainty / interval:" in text
        assert "Basis:" in text
        assert "Confidence:" in text

    for key in desktop_keys():
        setting_tooltip(key)

    for _range_id, config_field, _label, _minimum, _maximum, _units in MC_RANGE_SPECS:
        setting_tooltip(config_field)

    streamlit_keys, missing_help = streamlit_keys_and_missing_help()
    assert not missing_help, missing_help
    for key in streamlit_keys:
        setting_info(key)

    print(
        "Tooltip coverage passed:",
        len(desktop_keys()),
        "desktop settings,",
        len(MC_RANGE_SPECS),
        "Monte Carlo parameters,",
        len(streamlit_keys),
        "Streamlit controls.",
    )


if __name__ == "__main__":
    run()
