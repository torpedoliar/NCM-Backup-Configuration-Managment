"""Close-to-tray: window close hides to tray, backend keeps running; menu Keluar quits."""

from unittest.mock import MagicMock

from app_v4.desktop.shell.main_window import MainWindow
from app_v4.desktop.shell.tray import TrayController


def _make(qtbot):
    window = MainWindow(service_url="http://127.0.0.1:8443")
    qtbot.addWidget(window)
    app = window.windowHandle() and window  # parent object only; app comes via instance()
    stop_backend = MagicMock()
    from PySide6.QtWidgets import QApplication

    controller = TrayController(window, QApplication.instance(), get_stop_backend=stop_backend)
    return window, controller, stop_backend


def test_close_event_hides_window_and_keeps_backend(qtbot):
    window, controller, stop_backend = _make(qtbot)
    window.show()

    window.close()  # goes through the event system -> hits the event filter
    qtbot.wait(10)

    assert not window.isVisible()  # hidden to tray, not destroyed
    stop_backend.assert_not_called()  # backend still running


def test_quit_action_stops_backend_and_quits(qtbot):
    window, controller, stop_backend = _make(qtbot)
    controller._app = MagicMock()
    controller._app.quit = MagicMock()

    controller.action_quit.trigger()
    qtbot.wait(10)

    stop_backend.assert_called_once()
    controller._app.quit.assert_called_once()


def test_tray_controller_disables_quit_on_last_window_closed(qtbot):
    from PySide6.QtWidgets import QApplication

    window = MainWindow(service_url="http://127.0.0.1:8443")
    qtbot.addWidget(window)
    controller = TrayController(window, QApplication.instance(), get_stop_backend=MagicMock())
    assert QApplication.instance().quitOnLastWindowClosed() is False
