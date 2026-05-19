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
        await conn.execute(text("pragma journal_mode=WAL"))
        await conn.execute(text("pragma foreign_keys=ON"))


async def _run_sqlite_migrations(conn) -> None:
    await _add_column_if_missing(conn, "backups", "triggered_by_user_id", "INTEGER")
    await conn.execute(text("create index if not exists ix_backups_triggered_by_user_id on backups (triggered_by_user_id)"))


async def _add_column_if_missing(conn, table_name: str, column_name: str, column_sql: str) -> None:
    rows = await conn.execute(text(f"pragma table_info({table_name})"))
    existing = {row[1] for row in rows}
    if column_name not in existing:
        await conn.execute(text(f"alter table {table_name} add column {column_name} {column_sql}"))


async def get_session(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session
