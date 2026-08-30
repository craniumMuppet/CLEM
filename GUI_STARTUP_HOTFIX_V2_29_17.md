# EGCM v2.29.17 desktop-GUI startup hotfix

## Failure

The desktop GUI exited during window construction because the new GUI key
`arctic_new_ice_local_thickness` did not have corresponding tooltip metadata.
The underlying metadata entry existed only under the ModelConfig field name
`arctic_new_ice_local_thickness_m`.

`run_gui.bat` preferred the windowed Python interpreter, so the uncaught
traceback had no console and the failure appeared as if the GUI simply did
nothing.

## Fix

- Added tooltip metadata for the exact desktop-GUI key.
- Replaced the windowed launcher with a guarded launcher that writes the full
  traceback to `gui_startup_error.log` and displays a native Windows error
  dialog when startup fails.
- Added `run_gui_debug.bat`, which keeps startup errors visible in a console.
- Added a pure regression test for the metadata and launcher behavior.
- Added a full Tk construction smoke test and verified it under a virtual
  graphical display.

The climate equations and v2.29.17 scientific changes are otherwise unchanged.
