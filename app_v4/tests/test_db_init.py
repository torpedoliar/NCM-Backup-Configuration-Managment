from pathlib import Path

import pytest
from sqlalchemy import text

from app_v4.core.config import Settings
from app_v4.data.db import create_session_factory, init_db


@pytest.mark.asyncio
async def test_init_db_creates_v3_and_v4_tables(tmp_path: Path):
    settings = Settings(base_dir=tmp_path)
    engine, session_factory = create_session_factory(settings)

    await init_db(engine)

    async with session_factory() as session:
        rows = await session.execute(
            text("select name from sqlite_master where type='table' order by name")
        )
        table_names = {row[0] for row in rows}

    await engine.dispose()

    assert "credentials" in table_names
    assert "switches" in table_names
    assert "backups" in table_names
    assert "jobs" in table_names
    assert "users" in table_names
    assert "sessions" in table_names
    assert "audit_log" in table_names


@pytest.mark.asyncio
async def test_init_db_adds_triggered_by_user_id_to_existing_backups(tmp_path: Path):
    settings = Settings(base_dir=tmp_path)
    engine, session_factory = create_session_factory(settings)

    async with engine.begin() as conn:
        await conn.execute(text("create table backups (id integer primary key, switch_id integer not null)"))

    await init_db(engine)

    async with session_factory() as session:
        rows = await session.execute(text("pragma table_info(backups)"))
        columns = {row[1] for row in rows}

    await engine.dispose()

    assert "triggered_by_user_id" in columns
