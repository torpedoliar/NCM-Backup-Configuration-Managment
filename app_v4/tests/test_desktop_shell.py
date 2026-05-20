from app_v4.desktop.shell.main_window import MainWindow


def test_main_window_renders_ops_terminal_chrome(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.windowTitle() == "NCM v4 Ops Terminal"
    assert window.sidebar.brand.text() == "NCM OPS_"
    assert "monitoring / Dashboard" in window.topbar.breadcrumb.text()


def test_main_window_switches_to_inventory(qtbot):
    window = MainWindow(service_url="http://127.0.0.1:8443")
    qtbot.addWidget(window)
    window.sidebar.buttons["Switches"].click()
    assert window.stack.currentWidget().__class__.__name__ == "InventoryView"


def test_desktop_shell_has_ops_terminal_status(qtbot):
    window = MainWindow(service_url="http://127.0.0.1:8443")
    qtbot.addWidget(window)

    assert window.topbar.service_pulse.text() == "SERVICE / RUNNING"
    assert window.sidebar.version_tag.text() == "V3.5.7 / PROD"
