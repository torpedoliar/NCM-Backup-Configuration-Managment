from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

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


@pytest.mark.asyncio
async def test_switches_table_has_is_active_and_deactivated_at(tmp_path: Path):
    db_url = f"sqlite+aiosqlite:///{(tmp_path / 'app.db').as_posix()}"
    engine = create_async_engine(db_url)
    await init_db(engine)
    async with engine.begin() as conn:
        cols = await conn.run_sync(
            lambda sync_conn: {c["name"] for c in inspect(sync_conn).get_columns("switches")}
        )
    await engine.dispose()
    assert "is_active" in cols
    assert "deactivated_at" in cols


@pytest.mark.asyncio
async def test_init_db_adds_is_active_to_existing_switches(tmp_path: Path):
    settings = Settings(base_dir=tmp_path)
    engine, session_factory = create_session_factory(settings)

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "create table switches (id integer primary key, name text not null, "
                "ip text not null, protocol text not null, port integer not null, "
                "credential_id integer not null, notes text, "
                "created_at datetime not null default current_timestamp, "
                "updated_at datetime not null default current_timestamp)"
            )
        )

    await init_db(engine)

    async with session_factory() as session:
        rows = await session.execute(text("pragma table_info(switches)"))
        columns = {row[1] for row in rows}

    await engine.dispose()

    assert "is_active" in columns
    assert "deactivated_at" in columns


@pytest.mark.asyncio
async def test_jobs_table_has_day_of_week_and_day_of_month(tmp_path):
    db_url = f"sqlite+aiosqlite:///{(tmp_path / 'app.db').as_posix()}"
    engine = create_async_engine(db_url)
    await init_db(engine)
    async with engine.begin() as conn:
        cols = await conn.run_sync(lambda sync_conn: {c['name'] for c in inspect(sync_conn).get_columns('jobs')})
    await engine.dispose()
    assert 'day_of_week' in cols
    assert 'day_of_month' in cols
