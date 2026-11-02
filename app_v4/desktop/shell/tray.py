"""System-tray integration: keep the backend alive when the window is closed.

Closing the main window hides it and leaves the uvicorn backend running in the
background. The tray icon is the only way to truly quit (menu -> Keluar), which
also stops the backend thread via the normal main() teardown path.
"""

from __future__ import annotations

import sys
import threading

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from app_v4.desktop.theme import theme_asset

_TRAY_TOOLTIP = "NCM v4 - backend running (closed to tray)"


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


def _force_foreground(window) -> None:
    """Bring the window to the front despite the Windows foreground lock.

    activateWindow() alone is frequently ignored when another application owns
    the foreground, which made a tray click look like a frozen app. Pairing it
    with SetForegroundWindow on the native handle restores the window.
    """
    window.showNormal()
    window.raise_()
    window.activateWindow()
    if sys.platform != "win32":
        return
    try:
        import ctypes

        hwnd = int(window.winId())
        user32 = ctypes.windll.user32
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
    except Exception:  # noqa: BLE001 - focus is best effort, never fatal
        pass


class TrayController(QObject):
    """Owns the QSystemTrayIcon; close-to-tray + true exit menu."""

    # Emitted from the shutdown worker thread; Qt queues it onto the GUI thread
    # so QApplication.quit() is always called where Qt expects it.
    _backendStopped = Signal()

    def __init__(self, window, app, get_stop_backend):
        """get_stop_backend: callable that stops the backend thread (idempotent)."""
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

        self.action_show.triggered.connect(self.show_window)
        self.action_quit.triggered.connect(self._quit_app)
        self.tray.activated.connect(self._on_activated)
        self._backendStopped.connect(self._on_backend_stopped)

        self._window.installEventFilter(self)
        app.setQuitOnLastWindowClosed(False)

    def show_window(self) -> None:
        _force_foreground(self._window)

    def _quit_app(self) -> None:
        # Stopping uvicorn can block for seconds (in-flight backup, open
        # websocket). Doing it on the GUI thread froze the whole window, so the
        # teardown runs on a worker and only the final quit() returns to Qt.
        self.tray.hide()
        self.action_quit.setEnabled(False)
        self.action_show.setEnabled(False)
        threading.Thread(
            target=self._stop_backend_then_quit,
            daemon=True,
            name="ncm-v4-shutdown",
        ).start()

    def _stop_backend_then_quit(self) -> None:
        try:
            self._stop_backend()
        except Exception:  # noqa: BLE001 - shutdown must always finish
            pass
        finally:
            self._backendStopped.emit()

    def _on_backend_stopped(self) -> None:
        # Runs on the GUI thread (queued signal); app is looked up at emit
        # time so the quit target stays injectable in tests.
        self._app.quit()

    def _on_activated(self, reason) -> None:
        # Click on the icon re-opens the window (Windows: single left click).
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_window()

    def eventFilter(self, obj, event) -> bool:
        from PySide6.QtCore import QEvent

        if obj is self._window and event.type() == QEvent.Type.Close:
            # Intercept the close: hide to tray, keep the backend alive.
            # Deliberately no working-set trimming here: EmptyWorkingSet forced
            # every page out of RAM, so the next restore spent seconds paging
            # QtWebEngine back in and looked like a freeze.
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
