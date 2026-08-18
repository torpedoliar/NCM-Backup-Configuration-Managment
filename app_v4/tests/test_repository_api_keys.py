import pytest

from app_v4.data.repository import Repository


@pytest.mark.asyncio
async def test_create_and_lookup_api_key(session_factory):
    async with session_factory() as session:
        repo = Repository(session)
        created = await repo.create_api_key(name="netdoc", key_hash="abc123", prefix="ncr_1234")
        await session.commit()
        assert created.id is not None

    async with session_factory() as session:
        repo = Repository(session)
        found = await repo.get_api_key_by_hash("abc123")
        assert found is not None and found.name == "netdoc"
        assert await repo.get_api_key_by_hash("nope") is None


@pytest.mark.asyncio
async def test_revoke_hides_from_lookup(session_factory):
    async with session_factory() as session:
        repo = Repository(session)
        key = await repo.create_api_key(name="x", key_hash="h", prefix="p")
        await session.commit()
        key_id = key.id

    async with session_factory() as session:
        repo = Repository(session)
        assert await repo.revoke_api_key(key_id) is True
        await session.commit()

    async with session_factory() as session:
        repo = Repository(session)
        assert await repo.get_api_key_by_hash("h") is None  # revoked excluded
        assert [k.revoked for k in await repo.list_api_keys()] == [True]


@pytest.mark.asyncio
async def test_get_api_key_by_name_and_touch_last_used(session_factory):
    async with session_factory() as session:
        repo = Repository(session)
        key = await repo.create_api_key(name="netdoc", key_hash="hh", prefix="ncr_ab")
        await session.commit()
        key_id = key.id
        assert key.last_used_at is None
        assert key.revoked is False

    async with session_factory() as session:
        repo = Repository(session)
        found = await repo.get_api_key_by_name("netdoc")
        assert found is not None and found.id == key_id
        assert await repo.get_api_key_by_name("missing") is None

        await repo.touch_api_key_last_used(key_id)
        await session.commit()

    async with session_factory() as session:
        repo = Repository(session)
        found = await repo.get_api_key_by_hash("hh")
        assert found is not None and found.last_used_at is not None

    async with session_factory() as session:
        repo = Repository(session)
        # touching a missing key is a no-op, not an error
        await repo.touch_api_key_last_used(999999)
        assert await repo.revoke_api_key(999999) is False


@pytest.mark.asyncio
async def test_plaintext_key_is_never_stored(session_factory):
    import hashlib

    plaintext = "ncr_supersecrettoken"
    key_hash = hashlib.sha256(plaintext.encode()).hexdigest()

    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_api_key(name="netdoc", key_hash=key_hash, prefix=plaintext[:8])
        await session.commit()

    async with session_factory() as session:
        repo = Repository(session)
        keys = await repo.list_api_keys()
        assert len(keys) == 1
        stored = keys[0]
        assert stored.key_hash == key_hash
        assert plaintext not in stored.key_hash
        # prefix is a display fragment only, never the whole secret
        assert stored.prefix != plaintext
        assert plaintext.startswith(stored.prefix)
        # lookup only succeeds with the digest, never the plaintext
        assert await repo.get_api_key_by_hash(plaintext) is None
        assert await repo.get_api_key_by_hash(key_hash) is not None
