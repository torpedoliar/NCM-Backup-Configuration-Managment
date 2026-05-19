import pytest

from app_v4.data.repository import Repository, hash_refresh_token  # noqa: F401


@pytest.mark.asyncio
async def test_bootstrap_admin_creates_first_user(session_factory):
    async with session_factory() as session:
        repo = Repository(session)
        user = await repo.create_user(username="admin", password_hash="hashed", role="admin")
        await session.commit()

    async with session_factory() as session:
        repo = Repository(session)
        loaded = await repo.get_user_by_username("admin")

    assert user.id is not None
    assert loaded is not None
    assert loaded.username == "admin"
    assert loaded.role == "admin"


@pytest.mark.asyncio
async def test_session_lifecycle(session_factory):
    async with session_factory() as session:
        repo = Repository(session)
        user = await repo.create_user("operator", "hash", "operator")
        session_row = await repo.create_session(
            user_id=user.id,
            refresh_token_hash="refresh-hash",
            ip="10.0.0.5",
            user_agent="pytest",
            days_valid=7,
        )
        await session.commit()

    async with session_factory() as session:
        repo = Repository(session)
        loaded = await repo.get_session_by_refresh_hash("refresh-hash")
        await repo.revoke_session(session_row.id)
        await session.commit()

    assert loaded is not None
    assert loaded.user_id == user.id
