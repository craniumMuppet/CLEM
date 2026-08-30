#!/usr/bin/env python3
"""Construct and destroy the complete Tk desktop GUI.

This test requires a graphical display. On Linux CI, run it through xvfb-run.
"""

from __future__ import annotations

import tkinter as tk

from climate_model_gui import ClimateModelGUI


def main() -> None:
    root = tk.Tk()
    root.withdraw()
    gui = ClimateModelGUI(root)
    root.update_idletasks()
    root.update()
    assert gui.root.title().startswith("Coupled Low-complexity Earth Model")
    print(f"PASS: desktop GUI constructed successfully: {gui.root.title()}")
    root.destroy()


if __name__ == "__main__":
    main()
