#!/usr/bin/env python3
"""Graphical regression test for visible, editable Monte Carlo controls."""

from __future__ import annotations

import tkinter as tk

from climate_model_gui import ClimateModelGUI


def main() -> None:
    root = tk.Tk()
    root.geometry("1180x820")
    gui = ClimateModelGUI(root)
    gui.notebook.select(2)  # Monte Carlo tab
    gui.variables["monte_carlo_enabled"].set(True)
    gui.variables["mc_use_science_defaults"].set(True)
    gui.update_scenario_state()
    root.update_idletasks()
    root.update()

    editable = ("mc_runs", "mc_workers", "mc_seed", "mc_max_plotted")
    readonly = ("mc_constraint_mode", "mc_design", "mc_sampling")

    for key in editable:
        widget = gui.widgets[key]
        width = widget.winfo_width()
        state = str(widget.cget("state"))
        assert width >= 120, f"{key} is visually collapsed: width={width}"
        assert state == "normal", f"{key} should be editable, state={state}"

    for key in readonly:
        widget = gui.widgets[key]
        width = widget.winfo_width()
        state = str(widget.cget("state"))
        assert width >= 120, f"{key} is visually collapsed: width={width}"
        assert state == "readonly", f"{key} should be selectable, state={state}"

    print("PASS: Monte Carlo controls are visible and editable")
    root.destroy()


if __name__ == "__main__":
    main()
