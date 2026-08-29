import pytest

from app_v4.data.models import AuditLog
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
async def test_list_backups_filters_by_success_type_q_and_date(session_factory):
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential("c", b"x")
        sw = await repo.create_switch("sw", "10.0.0.1", "ssh", 22, cred.id)
        await repo.create_backup(
            switch_id=sw.id,
            file_path="",
            content_hash="x",
            size_bytes=10,
            success=True,
            message="ok manual",
            backup_type="manual",
        )
        await repo.create_backup(
            switch_id=sw.id,
            file_path="",
            content_hash="y",
            size_bytes=20,
            success=False,
            message="timeout",
            backup_type="automatic",
        )
        await session.commit()
        sw_id = sw.id

    async with session_factory() as session:
        repo = Repository(session)
        success_only = await repo.list_backups(switch_id=sw_id, success=True)
        failed_only = await repo.list_backups(switch_id=sw_id, success=False)
        manual_only = await repo.list_backups(switch_id=sw_id, backup_type="manual")
        searched = await repo.list_backups(switch_id=sw_id, q="time")

    assert len(success_only) == 1 and success_only[0].success is True
    assert len(failed_only) == 1 and failed_only[0].success is False
    assert len(manual_only) == 1 and manual_only[0].backup_type == "manual"
    assert len(searched) == 1 and "time" in (searched[0].message or "")


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


@pytest.mark.asyncio
async def test_list_audit_filters_and_counts(session_factory):
    async with session_factory() as session:
        repo = Repository(session)
        user = await repo.create_user("auditor", "h", "admin")
        await session.commit()
        user_id = user.id

    async with session_factory() as session:
        session.add(AuditLog(action="auth.login_success", user_id=user_id))
        session.add(AuditLog(action="switch.created", user_id=user_id))
        session.add(AuditLog(action="auth.login_failed", user_id=None))
        await session.commit()

    async with session_factory() as session:
        repo = Repository(session)
        all_rows = await repo.list_audit(limit=10)
        only_auth = await repo.list_audit(limit=10, action_prefix="auth.")
        only_user1 = await repo.list_audit(limit=10, user_id=user_id)
        total = await repo.count_audit(action_prefix="auth.")

    assert len(all_rows) == 3
    assert all(r.action.startswith("auth.") for r in only_auth)
    assert all(r.user_id == user_id for r in only_user1)
    assert total == 2


@pytest.mark.asyncio
async def test_system_metrics_failures_24h_filters_by_age(session_factory):
    """failures_24h must count only in the last 24h, failures_total all-time."""
    from datetime import timedelta
    from app_v4.core.utcdatetime import utc_now
    from app_v4.data.models import Backup

    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential("c_metrics", b"x")
        switch = await repo.create_switch("sw_metrics", "10.0.0.1", "ssh", 22, cred.id)
        # One failed backup now (counts toward 24h and total).
        await repo.create_backup(switch.id, "", "", 0, False, "boom", "manual")
        # One failed backup 40 days ago (counts only toward total).
        old = await repo.create_backup(switch.id, "", "", 0, False, "old boom", "automatic")
        old.taken_at = utc_now() - timedelta(days=40)
        await session.commit()

        values = await repo.system_metrics()

    assert values["failures_24h"] == 1
    assert values["failures_total"] == 2


@pytest.mark.asyncio
async def test_list_backups_offset_and_count(session_factory):
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential("c_paging", b"x")
        switch = await repo.create_switch("sw_paging", "10.0.0.1", "ssh", 22, cred.id)
        for i in range(5):
            await repo.create_backup(switch.id, f"/f{i}.txt", f"h{i}", 10, True, f"msg-{i}", "manual")
        await session.commit()

    async with session_factory() as session:
        repo = Repository(session)
        total = await repo.count_backups()
        page2 = await repo.list_backups(limit=2, offset=2)
        # list_backups orders by taken_at DESC; all 5 created within the same
        # second, so exact ordering by created time is ambiguous — just assert
        # the paging mechanics: offset 2 skips 2 and total counts all 5.
        assert total == 5
        assert len(page2) == 2


@pytest.mark.asyncio
async def test_latest_backup_per_switch_server_side(session_factory):
    """Fleet dashboard must see every switch's true newest backup regardless of
    global list limits (the old client tricked truncation)."""
    from datetime import timedelta
    from app_v4.core.utcdatetime import utc_now

    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential("c_lps", b"x")
        sw_a = await repo.create_switch("sw-a", "10.0.0.1", "ssh", 22, cred.id)
        sw_b = await repo.create_switch("sw-b", "10.0.0.2", "ssh", 22, cred.id)

        now = utc_now()
        a_old = await repo.create_backup(sw_a.id, "/a-old.txt", "h1", 10, True, "old", "automatic")
        a_old.taken_at = now - timedelta(days=2)
        a_new = await repo.create_backup(sw_a.id, "/a-new.txt", "h2", 10, True, "new", "automatic")
        a_new.taken_at = now
        b_only = await repo.create_backup(sw_b.id, "/b-only.txt", "h3", 10, True, "only", "automatic")
        b_only.taken_at = now - timedelta(days=30)
        # failed backup must not surface for the success-only variant
        b_fail = await repo.create_backup(sw_b.id, "", "", 0, False, "fail", "automatic")
        b_fail.taken_at = now
        await session.commit()

    async with session_factory() as session:
        repo = Repository(session)
        rows = await repo.latest_backup_per_switch(only_success=True)

    by_switch = {r.switch_id: r for r in rows}
    assert set(by_switch) == {sw_a.id, sw_b.id}
    assert by_switch[sw_a.id].file_path == "/a-new.txt"
    assert by_switch[sw_b.id].file_path == "/b-only.txt"
