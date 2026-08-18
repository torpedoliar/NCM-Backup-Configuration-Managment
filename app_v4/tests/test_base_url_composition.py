"""Regression: when wizard chooses bind_host=0.0.0.0 (LAN exposure), the
desktop client (httpx login + QWebEngineView SPA targets) must dial 127.0.0.1,
not 0.0.0.0. The latter is not routable on Windows and produces
"All connection attempts failed" at login.
"""

from __future__ import annotations

import re

from app_v4.desktop.launcher import probe_host


def test_compose_base_url_for_wildcard_bind_uses_loopback():
    bind_host = "0.0.0.0"
    bind_port = 8443

    base_url = f"http://{probe_host(bind_host)}:{bind_port}"

    assert base_url == "http://127.0.0.1:8443"
    assert "0.0.0.0" not in base_url


def test_compose_base_url_for_loopback_bind_unchanged():
    base_url = f"http://{probe_host('127.0.0.1')}:9000"
    assert base_url == "http://127.0.0.1:9000"


def test_compose_base_url_for_lan_bind_unchanged():
    """A user that bound to a specific LAN IP wants the client dial that IP."""
    base_url = f"http://{probe_host('192.168.10.5')}:9000"
    assert base_url == "http://192.168.10.5:9000"


def test_main_module_uses_probe_host_for_base_url():
    """Static guard: the URL composition in desktop/main.py must wrap
    bind.bind_host with probe_host(...). Without this, choosing 0.0.0.0 in the
    wizard yields http://0.0.0.0:port which httpx cannot reach.
    """
    from app_v4.desktop import main as desktop_main
    import inspect

    source = inspect.getsource(desktop_main)
    assert re.search(r'base_url\s*=\s*f"http://\{probe_host\(', source), (
        "desktop/main.py must compose base_url via probe_host(bind.bind_host); "
        "raw bind_host produces unroutable URLs for 0.0.0.0 / wildcard binds."
    )
