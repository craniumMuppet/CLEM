"""Windows-friendly desktop GUI launcher with visible startup diagnostics."""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ERROR_LOG = BASE_DIR / "gui_startup_error.log"


def _show_error(message: str) -> None:
    """Show a native error dialog, falling back to stderr when available."""

    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(
            None,
            message,
            "EGCM GUI startup failed",
            0x00000010,
        )
        return
    except Exception:
        pass

    try:
        print(message, file=sys.stderr)
    except Exception:
        pass


def main() -> int:
    os.chdir(BASE_DIR)
    try:
        from climate_model_gui import main as gui_main

        gui_main()
        return 0
    except BaseException:
        details = traceback.format_exc()
        try:
            ERROR_LOG.write_text(details, encoding="utf-8")
        except OSError:
            pass
        _show_error(
            "The EGCM desktop GUI could not start.\n\n"
            f"The full traceback was written to:\n{ERROR_LOG}\n\n"
            f"Last error:\n{details.strip().splitlines()[-1] if details.strip() else 'Unknown error'}"
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
