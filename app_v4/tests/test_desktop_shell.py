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
    assert window.sidebar.version_tag.text() == "V4.6.0 / PROD"
