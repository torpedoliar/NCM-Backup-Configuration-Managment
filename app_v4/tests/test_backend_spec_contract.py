from fastapi.testclient import TestClient

from app_v4.core.auth_service import AuthService
from app_v4.data.repository import Repository
from app_v4.service.app import create_app
from app_v4.service.runtime import ServiceRuntime


JWT_SECRET = b"test-secret"


def _token(settings, user_id: int, role: str = "admin") -> str:
    return AuthService(settings, JWT_SECRET).issue_access_token(user_id=user_id, username=f"u{user_id}", role=role)


async def _seed_user(session_factory, role: str):
    async with session_factory() as session:
        repo = Repository(session)
        user = await repo.create_user(f"u{role}", "hash", role)
        await session.commit()
        return user.id


def test_switch_detail_and_admin_only_delete(test_settings, session_factory):
    async def seed():
        admin_id = await _seed_user(session_factory, "admin")
        operator_id = await _seed_user(session_factory, "operator")
        async with session_factory() as session:
            repo = Repository(session)
            cred = await repo.create_credential("c", b"blob")
            switch = await repo.create_switch("sw01", "10.0.0.1", "ssh", 22, cred.id)
            await session.commit()
            return admin_id, operator_id, switch.id

    import anyio

    admin_id, operator_id, switch_id = anyio.run(seed)
    app = create_app(ServiceRuntime.for_tests(test_settings, session_factory=session_factory, jwt_secret=JWT_SECRET))
    client = TestClient(app)

    admin_headers = {"Authorization": f"Bearer {_token(test_settings, admin_id, 'admin')}"}
    operator_headers = {"Authorization": f"Bearer {_token(test_settings, operator_id, 'operator')}"}

    detail = client.get(f"/api/v1/switches/{switch_id}", headers=admin_headers)
    assert detail.status_code == 200
    assert detail.json()["id"] == switch_id

    denied = client.delete(f"/api/v1/switches/{switch_id}", headers=operator_headers)
    assert denied.status_code == 403


def test_backup_spec_alias_and_pair_diff(test_settings, session_factory, tmp_path):
    class FakeBackupService:
        async def execute_backup(self, switch_id, backup_type="manual", job_id=None, triggered_by_user_id=None):
            return {"success": True, "backup_id": 1, "message": "ok", "file_path": str(tmp_path / "new.txt"), "size_kb": 0.1}

    async def seed():
        operator_id = await _seed_user(session_factory, "operator")
        async with session_factory() as session:
            repo = Repository(session)
            cred = await repo.create_credential("c", b"blob")
            switch = await repo.create_switch("sw01", "10.0.0.1", "ssh", 22, cred.id)
            old_path = tmp_path / "old.txt"
            new_path = tmp_path / "new.txt"
            old_path.write_text("hostname old\n", encoding="utf-8")
            new_path.write_text("hostname new\n", encoding="utf-8")
            old = await repo.create_backup(switch.id, str(old_path), "h1", 12, True, "ok", "manual")
            new = await repo.create_backup(switch.id, str(new_path), "h2", 12, True, "ok", "manual")
            await session.commit()
            return operator_id, switch.id, old.id, new.id

    import anyio

    operator_id, switch_id, old_id, new_id = anyio.run(seed)
    app = create_app(
        ServiceRuntime.for_tests(
            test_settings,
            session_factory=session_factory,
            jwt_secret=JWT_SECRET,
            backup_service=FakeBackupService(),
        )
    )
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {_token(test_settings, operator_id, 'operator')}"}

    trigger = client.post(f"/api/v1/switches/{switch_id}/backup", headers=headers)
    assert trigger.status_code == 202
    assert trigger.json()["backup_id"] == 1

    diff = client.get(f"/api/v1/backups/diff?a={old_id}&b={new_id}", headers=headers)
    assert diff.status_code == 200
    assert "-hostname old" in diff.text
    assert "+hostname new" in diff.text
