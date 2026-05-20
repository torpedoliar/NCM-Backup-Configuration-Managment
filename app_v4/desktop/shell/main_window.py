from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QStackedWidget, QVBoxLayout, QWidget

from app_v4.desktop.bridge.web_bridge import WebBridge
from app_v4.desktop.shell.sidebar import Sidebar
from app_v4.desktop.shell.topbar import Topbar
from app_v4.desktop.views.credentials_view import CredentialsView
from app_v4.desktop.views.dashboard_view import DashboardView
from app_v4.desktop.views.diff_view import DiffView
from app_v4.desktop.views.history_view import HistoryView
from app_v4.desktop.views.inventory_view import InventoryView
from app_v4.desktop.views.schedules_view import SchedulesView
from app_v4.desktop.views.settings_view import SettingsView
from app_v4.desktop.views.users_view import UsersView


class MainWindow(QMainWindow):
    def __init__(self, service_url: str = "http://127.0.0.1:8443", access_token: str | None = None):
        super().__init__()
        self.setWindowTitle("NCM v4 Ops Terminal")
        self.resize(1280, 800)
        theme = Path(__file__).resolve().parents[1] / "theme" / "ops_terminal.qss"
        self.setStyleSheet(theme.read_text(encoding="utf-8"))
        self.bridge = WebBridge(service_url, access_token)

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        self.sidebar = Sidebar()
        root_layout.addWidget(self.sidebar, 0)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        self.topbar = Topbar()
        content_layout.addWidget(self.topbar)

        self.stack = QStackedWidget()
        self.views = {
            "Dashboard": DashboardView(service_url, bridge=self.bridge),
            "Switches": InventoryView(),
            "Credentials": CredentialsView(),
            "History": HistoryView(service_url, bridge=self.bridge),
            "Diff": DiffView(service_url, bridge=self.bridge),
            "Schedules": SchedulesView(),
            "Users": UsersView(),
            "Settings": SettingsView(),
        }
        for name, view in self.views.items():
            self.stack.addWidget(view)
            self.sidebar.buttons[name].clicked.connect(
                lambda checked=False, n=name: self.stack.setCurrentWidget(self.views[n])
            )
        content_layout.addWidget(self.stack, 1)

        root_layout.addWidget(content, 1)
        self.setCentralWidget(root)
