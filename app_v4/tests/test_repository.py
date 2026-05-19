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


@pytest.mark.asyncio
async def test_credential_crud(session_factory):
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential(name="lab-ssh", enc_blob=b"ciphertext")
        await session.commit()
        cred_id = cred.id

    async with session_factory() as session:
        repo = Repository(session)
        loaded = await repo.get_credential_by_name("lab-ssh")
        listed = await repo.list_credentials()
        assert loaded is not None
        assert loaded.id == cred_id
        assert len(listed) == 1

        await repo.update_credential(cred_id, name="lab-ssh-renamed", enc_blob=b"new")
        await session.commit()

    async with session_factory() as session:
        repo = Repository(session)
        loaded = await repo.get_credential(cred_id)
        assert loaded is not None
        assert loaded.name == "lab-ssh-renamed"
        assert loaded.enc_blob == b"new"
        await repo.delete_credential(cred_id)
        await session.commit()

    async with session_factory() as session:
        repo = Repository(session)
        assert await repo.get_credential(cred_id) is None


@pytest.mark.asyncio
async def test_switch_crud(session_factory):
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential(name="c1", enc_blob=b"x")
        switch = await repo.create_switch(
            name="sw01",
            ip="10.0.0.1",
            protocol="ssh",
            port=22,
            credential_id=cred.id,
            notes="rack 1",
        )
        await session.commit()
        switch_id = switch.id

    async with session_factory() as session:
        repo = Repository(session)
        loaded = await repo.get_switch(switch_id)
        listed = await repo.list_switches()
        assert loaded is not None
        assert loaded.name == "sw01"
        assert loaded.credential.name == "c1"
        assert len(listed) == 1

        await repo.update_switch(switch_id, ip="10.0.0.2", port=2222)
        await session.commit()

    async with session_factory() as session:
        repo = Repository(session)
        loaded = await repo.get_switch(switch_id)
        assert loaded is not None
        assert loaded.ip == "10.0.0.2"
        assert loaded.port == 2222
        await repo.delete_switch(switch_id)
        await session.commit()


@pytest.mark.asyncio
async def test_delete_credential_in_use_raises(session_factory):
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential(name="busy", enc_blob=b"x")
        await repo.create_switch(
            name="sw", ip="10.0.0.5", protocol="ssh", port=22, credential_id=cred.id
        )
        await session.commit()
        cred_id = cred.id

    async with session_factory() as session:
        repo = Repository(session)
        with pytest.raises(ValueError, match="in use"):
            await repo.delete_credential(cred_id)


@pytest.mark.asyncio
async def test_list_users_and_update_user(session_factory):
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_user("admin", "h1", "admin")
        await repo.create_user("ops", "h2", "operator")
        await session.commit()

    async with session_factory() as session:
        repo = Repository(session)
        users = await repo.list_users()
        assert {u.username for u in users} == {"admin", "ops"}

        ops = await repo.get_user_by_username("ops")
        await repo.update_user(ops.id, role="viewer", is_active=False)
        await session.commit()

    async with session_factory() as session:
        repo = Repository(session)
        ops = await repo.get_user_by_username("ops")
        assert ops.role == "viewer"
        assert ops.is_active is False


@pytest.mark.asyncio
async def test_audit_write(session_factory):
    async with session_factory() as session:
        repo = Repository(session)
        user = await repo.create_user("admin", "h", "admin")
        await repo.write_audit(
            user_id=user.id,
            action="user.create",
            target_type="user",
            target_id=str(user.id),
            ip="127.0.0.1",
            detail_json='{"username":"admin"}',
        )
        await session.commit()
        user_id_for_assert = user.id

    async with session_factory() as session:
        repo = Repository(session)
        rows = await repo.list_audit(limit=10)
        assert len(rows) == 1
        assert rows[0].action == "user.create"
        assert rows[0].target_id == str(user_id_for_assert)


@pytest.mark.asyncio
async def test_backup_repository_methods(session_factory):
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential("cred", b"x")
        switch = await repo.create_switch("sw", "10.0.0.1", "ssh", 22, cred.id)
        backup = await repo.create_backup(
            switch_id=switch.id,
            file_path="backups/sw/2026-05-19/config.txt",
            content_hash="abc",
            size_bytes=3,
            success=True,
            message="ok",
            backup_type="manual",
            triggered_by_user_id=None,
        )
        await session.commit()
        backup_id = backup.id

    async with session_factory() as session:
        repo = Repository(session)
        loaded = await repo.get_backup(backup_id)
        backups = await repo.list_backups(switch_id=loaded.switch_id, limit=10)
        latest = await repo.get_latest_backup(loaded.switch_id)

    assert loaded is not None
    assert loaded.content_hash == "abc"
    assert [b.id for b in backups] == [backup_id]
    assert latest.id == backup_id


@pytest.mark.asyncio
async def test_job_repository_methods(session_factory):
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential("cred", b"x")
        switch = await repo.create_switch("sw", "10.0.0.1", "ssh", 22, cred.id)
        job = await repo.create_job(
            switch_id=switch.id,
            interval_minutes=60,
            enabled=True,
            schedule_hour=8,
            schedule_minute=30,
        )
        await session.commit()
        job_id = job.id

    async with session_factory() as session:
        repo = Repository(session)
        loaded = await repo.get_job(job_id)
        jobs = await repo.list_jobs(enabled_only=True)
        await repo.update_job(job_id, interval_minutes=120, enabled=False)
        await session.commit()

    assert loaded is not None
    assert loaded.switch.name == "sw"
    assert [j.id for j in jobs] == [job_id]

    async with session_factory() as session:
        repo = Repository(session)
        updated = await repo.get_job(job_id)
        assert updated.interval_minutes == 120
        assert updated.enabled is False
        assert await repo.delete_job(job_id) is True
        await session.commit()
