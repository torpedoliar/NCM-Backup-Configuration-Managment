from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView

from app_v4.desktop.bridge.web_bridge import WebBridge


class HistoryView(QWebEngineView):
    def __init__(self, service_url: str, bridge: WebBridge | None = None):
        super().__init__()
        self.target_url = service_url.rstrip("/") + "/history"
        self.channel = QWebChannel(self)
        self.bridge = bridge or WebBridge(service_url)
        self.channel.registerObject("ncm", self.bridge)
        self.page().setWebChannel(self.channel)
        self.setUrl(QUrl(self.target_url))

