import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app_v4.data.repository import Repository
from app_v4.service.app import create_app
from app_v4.service.runtime import ServiceRuntime

FX = Path(__file__).parent / "fixtures" / "network_doc"


def _key_headers() -> dict[str, str]:
    return {"X-API-Key": "netdoc-secret"}


async def _seed(session_factory, tmp_path, *, backup_path: Path | None = None, content_hash: str = "hash-office2") -> int:
    path = backup_path or tmp_path / "awplus.txt"
    if backup_path is None:
        path.write_text((FX / "awplus.txt").read_text(encoding="utf-8"), encoding="utf-8")
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_api_key(
            name="netdoc",
            key_hash=hashlib.sha256(b"netdoc-secret").hexdigest(),
            prefix="netd",
        )
        cred = await repo.create_credential(name="lab", enc_blob=b"x")
        switch = await repo.create_switch(
            name="Office2", ip="10.10.0.6", protocol="ssh", port=22, credential_id=cred.id
        )
        await repo.create_backup(
            switch_id=switch.id,
            file_path=str(path),
            content_hash=content_hash,
            size_bytes=100,
            success=True,
            message="ok",
            backup_type="manual",
        )
        await session.commit()
        return switch.id


@pytest.mark.asyncio
async def test_network_doc_requires_api_key(test_settings, session_factory, tmp_path):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s" * 32)
    await _seed(session_factory, tmp_path)
    client = TestClient(create_app(runtime))

    assert client.get("/api/v1/network-doc").status_code == 401


@pytest.mark.asyncio
async def test_network_doc_returns_parsed_switch(test_settings, session_factory, tmp_path):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s" * 32)
    await _seed(session_factory, tmp_path)
    client = TestClient(create_app(runtime))

    response = client.get("/api/v1/network-doc", headers=_key_headers())

    assert response.status_code == 200
    doc = response.json()[0]
    assert doc["ip"] == "10.10.0.6"
    assert doc["name"] == "Office2"
    assert any(v["id"] == 88 and v["name"] == "IPH-DEVICE" for v in doc["vlans"])
    port = next(p for p in doc["ports"] if p["name"] == "port1.0.1")
    assert port["mode"] == "trunk" and port["native_vlan"] == 11


@pytest.mark.asyncio
async def test_network_doc_warns_for_no_backup_and_missing_file(test_settings, session_factory, tmp_path):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s" * 32)
    switch_id = await _seed(session_factory, tmp_path, backup_path=tmp_path / "missing.txt")
    client = TestClient(create_app(runtime))

    missing = client.get(f"/api/v1/network-doc/{switch_id}", headers=_key_headers())
    assert missing.status_code == 200
    assert missing.json()["parse_warnings"] == ["backup file missing on disk"]

    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential(name="empty", enc_blob=b"x")
        empty = await repo.create_switch("Empty", "10.10.0.7", "ssh", 22, cred.id)
        await session.commit()

    no_backup = client.get(f"/api/v1/network-doc/{empty.id}", headers=_key_headers())
    assert no_backup.status_code == 200
    assert no_backup.json()["parse_warnings"] == ["no successful backup"]


@pytest.mark.asyncio
async def test_network_doc_malformed_config_does_not_break_bulk(test_settings, session_factory, tmp_path, monkeypatch):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s" * 32)
    await _seed(session_factory, tmp_path, content_hash="malformed-config")
    client = TestClient(create_app(runtime))
    sentinel = "C:/backups/secret/API_KEY=top-secret"

    monkeypatch.setattr(
        "app_v4.service.api.network_doc.parse_config",
        lambda text: (_ for _ in ()).throw(ValueError(f"bad config: {sentinel}")),
    )
    response = client.get("/api/v1/network-doc", headers=_key_headers())

    assert response.status_code == 200
    warnings = response.json()[0]["parse_warnings"]
    assert warnings == ["unable to parse backup"]
    assert sentinel not in response.text


@pytest.mark.asyncio
async def test_network_doc_cache_overlays_identity_per_switch(test_settings, session_factory, tmp_path):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s" * 32)
    await _seed(session_factory, tmp_path, content_hash="shared-config")
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.get_credential_by_name("lab")
        second = await repo.create_switch("Branch", "10.10.0.8", "telnet", 23, cred.id)
        await repo.create_backup(second.id, str(tmp_path / "awplus.txt"), "shared-config", 100, True)
        await session.commit()

    response = TestClient(create_app(runtime)).get("/api/v1/network-doc", headers=_key_headers())

    assert response.status_code == 200
    docs = {doc["name"]: doc for doc in response.json()}
    assert docs["Office2"]["ip"] == "10.10.0.6"
    assert docs["Branch"]["ip"] == "10.10.0.8"
    assert docs["Branch"]["protocol"] == "telnet"


@pytest.mark.asyncio
async def test_network_doc_returns_404_for_missing_switch(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s" * 32)
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_api_key("netdoc", hashlib.sha256(b"netdoc-secret").hexdigest(), "netd")
        await session.commit()

    response = TestClient(create_app(runtime)).get("/api/v1/network-doc/999", headers=_key_headers())
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_network_doc_backup_taken_at_is_utc_aware(test_settings, session_factory, tmp_path):
    """backup_taken_at serializes with a UTC offset even when the DB value is naive."""
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s" * 32)
    switch_id = await _seed(session_factory, tmp_path)
    # Overwrite the backup's taken_at with a naive datetime to simulate legacy DB
    async with session_factory() as session:
        repo = Repository(session)
        backup = await repo.get_latest_backup(switch_id)
        assert backup is not None
        backup.taken_at = datetime(2026, 8, 17, 10, 30, 0)  # naive, no tzinfo
        await session.commit()

    response = TestClient(create_app(runtime)).get(
        f"/api/v1/network-doc/{switch_id}", headers=_key_headers()
    )
    assert response.status_code == 200
    raw = response.json()["backup_taken_at"]
    assert isinstance(raw, str), f"expected string, got {type(raw)}"
    assert raw.endswith("+00:00") or raw.endswith("Z"), f"no UTC offset in {raw!r}"
