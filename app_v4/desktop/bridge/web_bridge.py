from __future__ import annotations

from PySide6.QtCore import QObject, Slot


class WebBridge(QObject):
    def __init__(self, service_url: str, access_token: str | None = None):
        super().__init__()
        self._service_url = service_url
        self._access_token = access_token or ""

    @Slot(result=str)
    def serviceUrl(self) -> str:
        return self._service_url

    @Slot(result=str)
    def accessToken(self) -> str:
        return self._access_token
