"""System-tray integration: keep the backend alive when the window is closed.

Closing the main window hides it and leaves the uvicorn backend running in the
background. The tray icon is the only way to truly quit (menu → Keluar), which
also stops the backend thread via the normal main() teardown path.
"""

from __future__ import annotations

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from app_v4.desktop.theme import theme_asset

_TRAY_TOOLTIP = "NCM v4 — backend running (closed to tray)"


def _build_icon() -> QIcon:
    """App icon for the tray; falls back to an amber glyph if the asset is missing."""
    ico_path = theme_asset("ncm.ico")
    if ico_path.exists():
        return QIcon(str(ico_path))
    from PySide6.QtGui import QColor, QPainter, QPixmap

    pix = QPixmap(64, 64)
    pix.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pix)
    painter.setPen(QColor(255, 184, 0))
    painter.setBrush(QColor(255, 184, 0))
    painter.drawRect(8, 8, 48, 48)
    painter.end()
    return QIcon(pix)


class TrayController(QObject):
    """Owns the QSystemTrayIcon; close-to-tray + true exit menu."""

    def __init__(self, window, app, get_stop_backend):
        """``get_stop_backend``: callable that stops the backend thread (idempotent)."""
        super().__init__()
        self._window = window
        self._app = app
        self._stop_backend = get_stop_backend

        self.tray = QSystemTrayIcon(_build_icon())
        self.tray.setToolTip(_TRAY_TOOLTIP)

        menu = QMenu()
        self.action_show = QAction("Buka NCM v4", menu)
        self.action_quit = QAction("Keluar (hentikan server)", menu)
        menu.addAction(self.action_show)
        menu.addSeparator()
        menu.addAction(self.action_quit)
        self.tray.setContextMenu(menu)
        self._menu = menu

        self.action_show.triggered.connect(self._show_window)
        self.action_quit.triggered.connect(self._quit_app)
        self.tray.activated.connect(self._on_activated)

        self._window.installEventFilter(self)
        app.setQuitOnLastWindowClosed(False)

    def _show_window(self) -> None:
        self._window.showNormal()
        self._window.activateWindow()
        self._window.raise_()

    def _quit_app(self) -> None:
        self.tray.hide()
        self._stop_backend()
        self._app.quit()

    def _on_activated(self, reason) -> None:
        # Click on the icon re-opens the window (Windows: single left click).
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._show_window()

    def eventFilter(self, obj, event) -> bool:
        from PySide6.QtCore import QEvent

        if obj is self._window and event.type() == QEvent.Type.Close:
            # Intercept the close: hide to tray, keep the backend alive.
            event.ignore()
            self._window.hide()
            self.tray.show()
            if not getattr(self, "_notified_once", False):
                self.tray.showMessage(
                    "NCM v4",
                    "Aplikasi tetap berjalan di background. "
                    "Klik ikon tray untuk membuka, menu Keluar untuk menghentikan server.",
                    QSystemTrayIcon.MessageIcon.Information,
                    4000,
                )
                self._notified_once = True
            return True
        return False

    def show(self) -> None:
        self.tray.show()
