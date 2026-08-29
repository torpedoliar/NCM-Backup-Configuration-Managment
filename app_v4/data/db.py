from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app_v4.core.config import Settings
from app_v4.core.paths import resolve_paths
from app_v4.data.models import Base


def create_session_factory(settings: Settings) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    paths = resolve_paths(settings)
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    engine = create_async_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        echo=False,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    return engine, session_factory


async def init_db(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _run_sqlite_migrations(conn)
    # PRAGMAs must run outside the transaction block above: SQLite rejects
    # switching journal_mode=WAL from within an open transaction.
    async with engine.connect() as conn:
        await conn.execute(text("pragma journal_mode=WAL"))
        await conn.execute(text("pragma foreign_keys=ON"))


async def _run_sqlite_migrations(conn) -> None:
    await _add_column_if_missing(conn, "backups", "triggered_by_user_id", "INTEGER")
    await conn.execute(text("create index if not exists ix_backups_triggered_by_user_id on backups (triggered_by_user_id)"))
    await _add_column_if_missing(conn, "switches", "is_active", "INTEGER NOT NULL DEFAULT 1")
    await _add_column_if_missing(conn, "switches", "deactivated_at", "DATETIME")
    await _add_column_if_missing(conn, "switches", "model", "VARCHAR(100)")
    await _add_column_if_missing(conn, "jobs", "day_of_week", "VARCHAR(3)")
    await _add_column_if_missing(conn, "jobs", "day_of_month", "INTEGER")
    await _add_column_if_missing(conn, "jobs", "name", "VARCHAR(100)")
    await conn.execute(
        text(
            "update jobs set name = (select switches.name from switches "
            "where switches.id = jobs.switch_id) "
            "where name is null or name = ''"
        )
    )
    await _add_column_if_missing(conn, "users", "failed_login_count", "INTEGER NOT NULL DEFAULT 0")
    await _add_column_if_missing(conn, "users", "last_failed_login_at", "DATETIME")
    await _add_column_if_missing(conn, "users", "locked_until", "DATETIME")


async def _add_column_if_missing(conn, table_name: str, column_name: str, column_sql: str) -> None:
    rows = await conn.execute(text(f"pragma table_info({table_name})"))
    existing = {row[1] for row in rows}
    if column_name not in existing:
        await conn.execute(text(f"alter table {table_name} add column {column_name} {column_sql}"))


async def get_session(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session
