"""UTF-8 console setup for Windows project commands."""
from __future__ import annotations

import os
import sys


def _set_windows_console_utf8() -> None:
    if os.name != "nt":
        return

    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleOutputCP(65001)
        kernel32.SetConsoleCP(65001)
    except Exception:
        return


def _reconfigure_text_stream(name: str) -> None:
    stream = getattr(sys, name, None)
    if stream is None:
        return

    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is None:
        return

    try:
        reconfigure(encoding="utf-8", errors="replace")
    except (TypeError, ValueError, OSError):
        return


def configure_utf8_stdio() -> None:
    """Make project command output UTF-8 even on GBK Windows consoles."""
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")

    _set_windows_console_utf8()
    _reconfigure_text_stream("stdout")
    _reconfigure_text_stream("stderr")
