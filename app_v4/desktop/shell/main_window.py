from __future__ import annotations

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QVBoxLayout, QWidget

from app_v4.desktop.shell.sidebar import Sidebar
from app_v4.desktop.shell.spa_view import SpaView
from app_v4.desktop.shell.topbar import Topbar
from app_v4.desktop.theme import load_theme_qss, theme_asset


# Maps the sidebar label to the SPA route. Order mirrors Sidebar's button order.
_SIDEBAR_ROUTES: dict[str, str] = {
    "Dashboard": "/",
    "Switches": "/switches",
    "Credentials": "/credentials",
    "History": "/history",
    "Diff": "/diff",
    "Schedules": "/schedules",
    "Users": "/users",
    "Settings": "/settings",
}


class MainWindow(QMainWindow):
    def __init__(
        self,
        service_url: str = "http://127.0.0.1:8443",
        access_token: str | None = None,
        refresh_token: str | None = None,
    ):
        super().__init__()
        self.setWindowTitle("NCM v4 Ops Terminal")
        self.resize(1280, 800)
        self.setStyleSheet(load_theme_qss())
        app_icon = theme_asset("ncm.ico")
        if app_icon.exists():
            self.setWindowIcon(QIcon(str(app_icon)))

        self.spa_view = SpaView(
            service_url=service_url,
            access_token=access_token or "",
            refresh_token=refresh_token or "",
        )

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
        content_layout.addWidget(self.spa_view, 1)

        root_layout.addWidget(content, 1)
        self.setCentralWidget(root)

        for label, route in _SIDEBAR_ROUTES.items():
            button = self.sidebar.buttons.get(label)
            if button is None:
                continue
            button.clicked.connect(lambda _checked=False, r=route: self.spa_view.navigate(r))
