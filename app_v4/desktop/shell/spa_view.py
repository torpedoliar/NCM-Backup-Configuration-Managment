from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineScript
from PySide6.QtWebEngineWidgets import QWebEngineView

from app_v4.desktop.bridge.web_bridge import WebBridge


class SpaView(QWebEngineView):
    """Single embedded SPA view shared across all desktop tabs.

    Why single instance: each QWebEngineView has its own JS context and
    localStorage. Multiple instances would each show the SPA's login page
    because the bearer token only lives in the instance that received it.
    Reusing one instance lets the SPA's wouter Router swap pages via
    pushState — no reload, no re-login, full app state preserved.
    """

    def __init__(self, service_url: str, access_token: str, refresh_token: str = "") -> None:
        super().__init__()
        self.service_url = service_url.rstrip("/")
        self._access_token = access_token
        self._refresh_token = refresh_token

        self.bridge = WebBridge(self.service_url, access_token)
        self.channel = QWebChannel(self)
        self.channel.registerObject("ncm", self.bridge)
        self.page().setWebChannel(self.channel)

        self._install_token_injection()
        self.setUrl(QUrl(self.service_url + "/"))

    def _install_token_injection(self) -> None:
        """Pre-seed localStorage with the bearer token before any SPA script runs.

        The injection script is registered with QWebEngineScript so it executes
        at DocumentCreation, before React mounts and reads localStorage in
        AuthProvider's useState initializer. Without this the SPA boots with
        a null token and renders LoginPage even though we already authenticated
        in the Qt login dialog.
        """
        access = (self._access_token or "").replace("\\", "\\\\").replace('"', '\\"')
        refresh = (self._refresh_token or "").replace("\\", "\\\\").replace('"', '\\"')
        source = (
            f'localStorage.setItem("access_token", "{access}");\n'
            f'localStorage.setItem("refresh_token", "{refresh}");\n'
        )
        script = QWebEngineScript()
        script.setName("ncm-v4-token-injector")
        script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        script.setRunsOnSubFrames(False)
        script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        script.setSourceCode(source)
        self.page().scripts().insert(script)

    def navigate(self, route: str) -> None:
        """Push a SPA-internal route via History API; no full reload, no re-login."""
        if not route.startswith("/"):
            route = "/" + route
        target = self.service_url + route
        js = (
            f'window.history.pushState({{}}, "", "{target}");\n'
            'window.dispatchEvent(new PopStateEvent("popstate"));\n'
        )
        self.page().runJavaScript(js)
