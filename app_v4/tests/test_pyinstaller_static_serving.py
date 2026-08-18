"""Smoke test: simulate PyInstaller-frozen environment and confirm that the
static bundle (SPA) is mountable from sys._MEIPASS, not from base_dir.

This is a regression guard for the fix that moved static_dir resolution to
detect sys.frozen + sys._MEIPASS. Without that fix, `assets_dir.exists()` in
service.app:38 returns False under PyInstaller windowed builds, so the SPA
never loads and `web_fallback` always 404s.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app_v4.core.config import Settings
from app_v4.core.paths import resolve_paths
from app_v4.service.app import create_app
from app_v4.service.runtime import ServiceRuntime


@pytest.mark.asyncio
async def test_spa_served_when_static_lives_in_pyinstaller_meipass(
    tmp_path: Path,
    monkeypatch,
    test_settings,
    session_factory,
):
    bundle_dir = tmp_path / "_internal"
    static_dir = bundle_dir / "app_v4" / "service" / "static"
    static_dir.mkdir(parents=True)
    (static_dir / "index.html").write_text("<div id='root'>spa</div>", encoding="utf-8")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle_dir), raising=False)

    paths = resolve_paths(test_settings)
    assert paths.static_dir == static_dir

    runtime = ServiceRuntime.for_tests(test_settings, session_factory=session_factory, jwt_secret=b"s" * 32)
    client = TestClient(create_app(runtime))

    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "spa" in response.text
