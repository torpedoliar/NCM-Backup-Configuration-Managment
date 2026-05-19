from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app_v4.cli import init_command
from app_v4.core.config import Settings
from app_v4.core.dpapi import MemoryProtectionProvider
from app_v4.core.key_envelope import KeyEnvelopeStore
from app_v4.core.paths import resolve_paths


@pytest.mark.asyncio
async def test_init_creates_envelope_admin_and_db(tmp_path: Path):
    settings = Settings(base_dir=tmp_path)
    provider = MemoryProtectionProvider(secret=b"unit-test")

    result = await init_command(
        settings=settings,
        master_passphrase="master-pass-1",
        admin_username="admin",
        admin_password="StrongAdmin1!",
        protection_provider=provider,
    )

    paths = resolve_paths(settings)
    envelope = KeyEnvelopeStore(paths.master_envelope_file, provider).load()

    assert envelope.master_passphrase == "master-pass-1"
    assert len(envelope.jwt_secret) == 32
    assert paths.master_key_file.exists()

    engine = create_async_engine(settings.database_url)
    async with engine.connect() as conn:
        rows = await conn.execute(text("select username, role, is_active from users"))
        users = list(rows)
    await engine.dispose()

    assert users == [("admin", "admin", 1)]
    assert result["created_admin"] is True
    assert result["created_envelope"] is True


@pytest.mark.asyncio
async def test_init_is_idempotent_when_envelope_and_admin_exist(tmp_path: Path):
    settings = Settings(base_dir=tmp_path)
    provider = MemoryProtectionProvider(secret=b"unit-test")

    await init_command(
        settings=settings,
        master_passphrase="master-pass-1",
        admin_username="admin",
        admin_password="StrongAdmin1!",
        protection_provider=provider,
    )

    second = await init_command(
        settings=settings,
        master_passphrase="master-pass-1",
        admin_username="admin",
        admin_password="StrongAdmin1!",
        protection_provider=provider,
    )

    assert second["created_envelope"] is False
    assert second["created_admin"] is False


@pytest.mark.asyncio
async def test_init_rejects_passphrase_mismatch_on_existing_envelope(tmp_path: Path):
    settings = Settings(base_dir=tmp_path)
    provider = MemoryProtectionProvider(secret=b"unit-test")

    await init_command(
        settings=settings,
        master_passphrase="master-pass-1",
        admin_username="admin",
        admin_password="StrongAdmin1!",
        protection_provider=provider,
    )

    with pytest.raises(ValueError, match="passphrase does not match"):
        await init_command(
            settings=settings,
            master_passphrase="different-pass",
            admin_username="admin",
            admin_password="StrongAdmin1!",
            protection_provider=provider,
        )
