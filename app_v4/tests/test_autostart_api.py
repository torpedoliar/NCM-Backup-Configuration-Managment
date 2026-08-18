from __future__ import annotations

from typing import Iterable
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app_v4.data.repository import Repository
from app_v4.service.app import create_app
from app_v4.service.runtime import ServiceRuntime


def _admin_token(runtime: ServiceRuntime, user_id: int) -> str:
    return runtime.auth_service.issue_access_token(user_id, "admin", "admin")


def _viewer_token(runtime: ServiceRuntime) -> str:
    return runtime.auth_service.issue_access_token(2, "viewer", "viewer")


def _operator_token(runtime: ServiceRuntime) -> str:
    return runtime.auth_service.issue_access_token(3, "ops", "operator")


class _FakeProcess:
    def __init__(self, returncode: int, stdout: bytes = b"", stderr: bytes = b""):
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    async def communicate(self) -> tuple[bytes, bytes]:
        return self._stdout, self._stderr


def _patch_subprocess(monkeypatch, scripted: Iterable[_FakeProcess]) -> list[list[str]]:
    captured: list[list[str]] = []
    queue = list(scripted)

    async def fake_create(*args, **kwargs):
        captured.append(list(args))
        return queue.pop(0)

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_create)
    return captured


@pytest.mark.asyncio
async def test_get_autostart_returns_disabled_when_task_missing(test_settings, session_factory, monkeypatch):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"A" * 32)
    async with session_factory() as session:
        repo = Repository(session)
        admin = await repo.create_user("admin", "h", "admin")
        await session.commit()
        admin_id = admin.id

    _patch_subprocess(
        monkeypatch,
        [
            _FakeProcess(returncode=1, stderr=b"ERROR: The system cannot find the file specified."),
        ],
    )

    client = TestClient(create_app(runtime))
    r = client.get(
        "/api/v1/system/autostart",
        headers={"Authorization": f"Bearer {_admin_token(runtime, admin_id)}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["installed"] is False
    assert body["ready"] is False


@pytest.mark.asyncio
async def test_put_autostart_admin_only_and_invokes_create(test_settings, session_factory, monkeypatch, tmp_path):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"A" * 32)
    async with session_factory() as session:
        repo = Repository(session)
        admin = await repo.create_user("admin", "h", "admin")
        await session.commit()
        admin_id = admin.id

    fake_exe = tmp_path / "ncm-v4-desktop.exe"
    fake_exe.write_bytes(b"MZ")

    captured = _patch_subprocess(
        monkeypatch,
        [
            _FakeProcess(returncode=0),  # /Create
            _FakeProcess(returncode=0, stdout=b"NCM v4 Backend  N/A   Ready"),  # /Query
        ],
    )

    monkeypatch.setattr(
        "app_v4.service.api.autostart.resolve_executable_path",
        lambda: fake_exe,
    )

    client = TestClient(create_app(runtime))
    forbidden = client.put(
        "/api/v1/system/autostart",
        json={"enabled": True, "trigger": "startup"},
        headers={"Authorization": f"Bearer {_operator_token(runtime)}"},
    )
    assert forbidden.status_code == 403

    r = client.put(
        "/api/v1/system/autostart",
        json={"enabled": True, "trigger": "startup"},
        headers={"Authorization": f"Bearer {_admin_token(runtime, admin_id)}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["installed"] is True
    assert body["ready"] is True

    create_call = captured[0]
    assert "/Create" in create_call
    assert "/SC" in create_call
    sc_index = create_call.index("/SC")
    assert create_call[sc_index + 1].upper() == "ONSTART"


@pytest.mark.asyncio
async def test_put_autostart_disable_removes_task(test_settings, session_factory, monkeypatch):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"A" * 32)
    async with session_factory() as session:
        repo = Repository(session)
        admin = await repo.create_user("admin", "h", "admin")
        await session.commit()
        admin_id = admin.id

    captured = _patch_subprocess(
        monkeypatch,
        [
            _FakeProcess(returncode=0),  # /Delete
        ],
    )

    client = TestClient(create_app(runtime))
    r = client.put(
        "/api/v1/system/autostart",
        json={"enabled": False},
        headers={"Authorization": f"Bearer {_admin_token(runtime, admin_id)}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["installed"] is False
    assert "/Delete" in captured[0]


@pytest.mark.asyncio
async def test_put_autostart_returns_502_when_not_frozen(test_settings, session_factory, monkeypatch):
    """When running from source there is no bundled exe to schedule."""
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"A" * 32)
    async with session_factory() as session:
        repo = Repository(session)
        admin = await repo.create_user("admin", "h", "admin")
        await session.commit()
        admin_id = admin.id

    monkeypatch.setattr(
        "app_v4.service.api.autostart.resolve_executable_path",
        lambda: None,
    )

    client = TestClient(create_app(runtime))
    r = client.put(
        "/api/v1/system/autostart",
        json={"enabled": True, "trigger": "startup"},
        headers={"Authorization": f"Bearer {_admin_token(runtime, admin_id)}"},
    )
    assert r.status_code == 422
    assert "executable" in r.json()["detail"].lower() or "frozen" in r.json()["detail"].lower()
