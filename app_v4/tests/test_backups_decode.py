from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app_v4.data.repository import Repository
from app_v4.service.app import create_app
from app_v4.service.runtime import ServiceRuntime

FX = Path(__file__).parent / "fixtures" / "network_doc"


def _headers(runtime: ServiceRuntime) -> dict[str, str]:
    return {"Authorization": f"Bearer {runtime.auth_service.issue_access_token(1, 'ops', 'operator')}"}


async def _seed(session_factory, tmp_path, fixture: str, *, protocol: str = "websmart-snmp") -> int:
    backup_path = tmp_path / f"{fixture}.txt"
    backup_path.write_text((FX / f"{fixture}.txt").read_text(encoding="utf-8"), encoding="utf-8")
    async with session_factory() as session:
        repo = Repository(session)
        if await repo.get_user_by_username("ops") is None:
            await repo.create_user("ops", "hash", "operator")
        cred = await repo.get_credential_by_name("lab")
        if cred is None:
            cred = await repo.create_credential("lab", b"x")
        switch = await repo.create_switch(f"WS Lab {fixture}", "10.10.0.9", protocol, 161, cred.id)
        await repo.create_backup(
            switch_id=switch.id,
            file_path=str(backup_path),
            content_hash=f"hash-{fixture}",
            size_bytes=100,
            success=True,
            message="ok",
            backup_type="manual",
        )
        await session.commit()
        return switch.id


@pytest.mark.asyncio
async def test_decode_requires_authentication(test_settings, session_factory, tmp_path):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s" * 32)
    switch_id = await _seed(session_factory, tmp_path, "websmart")
    client = TestClient(create_app(runtime))

    assert client.get(f"/api/v1/backups/1/decode").status_code == 401


@pytest.mark.asyncio
async def test_decode_websmart_and_websmart_v2(test_settings, session_factory, tmp_path):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s" * 32)
    await _seed(session_factory, tmp_path, "websmart")
    await _seed(session_factory, tmp_path, "websmart_v2")
    client = TestClient(create_app(runtime))

    for backup_id, expected in (
        (1, ("ICT Network SW", 30, 56)),
        (2, ("Nutanix Switch", 4, 60)),
    ):
        response = client.get(f"/api/v1/backups/{backup_id}/decode", headers=_headers(runtime))
        assert response.status_code == 200
        doc = response.json()
        assert doc["backup_id"] == backup_id
        assert doc["switch_name"] == f"WS Lab {'websmart' if backup_id == 1 else 'websmart_v2'}"
        assert doc["protocol"] == "websmart-snmp"
        assert doc["dialect"] == "websmart"
        assert doc["hostname"] == expected[0]
        assert len(doc["vlans"]) == expected[1]
        assert len(doc["ports"]) == expected[2]
        assert doc["parse_warnings"] == []
        assert all({"id", "name"} <= set(v) for v in doc["vlans"])
        assert all(
            {"name", "mode", "native_vlan", "access_vlan", "trunk_allowed_vlans"} <= set(p)
            for p in doc["ports"]
        )


@pytest.mark.asyncio
async def test_decode_awplus_detects_dialect(test_settings, session_factory, tmp_path):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s" * 32)
    await _seed(session_factory, tmp_path, "awplus", protocol="ssh")
    client = TestClient(create_app(runtime))

    response = client.get("/api/v1/backups/1/decode", headers=_headers(runtime))

    assert response.status_code == 200
    doc = response.json()
    assert doc["dialect"] == "awplus"
    port = next(p for p in doc["ports"] if p["name"] == "port1.0.1")
    assert port["mode"] == "trunk" and port["native_vlan"] == 11


@pytest.mark.asyncio
async def test_decode_unknown_dialect_warns_but_returns_200(test_settings, session_factory, tmp_path):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s" * 32)
    path = tmp_path / "weird.txt"
    path.write_text("no recognizable markers here\n", encoding="utf-8")
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_user("ops", "hash", "operator")
        cred = await repo.create_credential("lab", b"x")
        switch = await repo.create_switch("Odd", "10.10.0.10", "ssh", 22, cred.id)
        await repo.create_backup(switch.id, str(path), "hash-weird", 30, True)
        await session.commit()
    client = TestClient(create_app(runtime))

    response = client.get("/api/v1/backups/1/decode", headers=_headers(runtime))

    assert response.status_code == 200
    assert response.json()["dialect"] == "unknown"
    assert response.json()["parse_warnings"] == ["unknown switch config dialect; nothing parsed"]


@pytest.mark.asyncio
async def test_decode_404_for_missing_backup_and_missing_file(test_settings, session_factory, tmp_path):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s" * 32)
    await _seed(session_factory, tmp_path, "websmart", )
    async with session_factory() as session:
        repo = Repository(session)
        backup = await repo.get_backup(1)
        assert backup is not None
        backup.file_path = str(tmp_path / "gone.txt")
        await session.commit()
    client = TestClient(create_app(runtime))

    assert client.get("/api/v1/backups/999/decode", headers=_headers(runtime)).status_code == 404
    assert client.get("/api/v1/backups/1/decode", headers=_headers(runtime)).status_code == 404
