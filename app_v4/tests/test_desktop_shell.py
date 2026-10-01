from unittest.mock import MagicMock

from app_v4.desktop.shell.main_window import MainWindow


def test_main_window_renders_ops_terminal_chrome(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.windowTitle() == "NCM v4 Ops Terminal"
    assert window.sidebar.brand.text() == "NCM OPS_"
    assert "monitoring / Dashboard" in window.topbar.breadcrumb.text()


def test_main_window_switches_navigate_via_spa(qtbot):
    window = MainWindow(service_url="http://127.0.0.1:8443")
    qtbot.addWidget(window)

    captured = []
    window.spa_view.navigate = lambda route: captured.append(route)
    window.sidebar.buttons["Switches"].click()
    window.sidebar.buttons["Credentials"].click()
    window.sidebar.buttons["Settings"].click()

    assert captured == ["/switches", "/credentials", "/settings"]


def test_desktop_shell_has_ops_terminal_status(qtbot):
    window = MainWindow(service_url="http://127.0.0.1:8443")
    qtbot.addWidget(window)

    assert window.topbar.service_pulse.text() == "SERVICE / RUNNING"
    assert window.sidebar.version_tag.text() == "V4.7.0 / PROD"


def test_tray_controller_hides_window_on_close_and_restores_on_show(qtbot):
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import QApplication
    from app_v4.desktop.shell.tray import TrayController

    window = MainWindow(service_url="http://127.0.0.1:8443")
    qtbot.addWidget(window)

    app = QApplication.instance()
    stop_called = []
    tray = TrayController(window, app, get_stop_backend=lambda: stop_called.append(True))

    close_event = QCloseEvent()
    handled = tray.eventFilter(window, close_event)
    assert handled is True
    assert close_event.isAccepted() is False
    assert window.isVisible() is False

    tray._show_window()
    assert window.isVisible() is True

