"""NCM v4 desktop theme."""

from __future__ import annotations

from pathlib import Path


def load_theme_qss() -> str:
    """Return the bundled ops_terminal.qss stylesheet content.

    Resolves from the package directory so it works in dev and inside the
    PyInstaller _internal/ bundle (the spec ships ops_terminal.qss as a data
    file under app_v4/desktop/theme/).
    """
    qss_path = Path(__file__).resolve().parent / "ops_terminal.qss"
    return qss_path.read_text(encoding="utf-8")
