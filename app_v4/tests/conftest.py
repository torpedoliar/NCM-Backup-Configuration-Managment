from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app_v4.core.config import Settings
from app_v4.data.db import create_session_factory, init_db


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    return Settings(base_dir=tmp_path)


@pytest_asyncio.fixture
async def session_factory(test_settings: Settings) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine, factory = create_session_factory(test_settings)
    await init_db(engine)
    yield factory
    await engine.dispose()
