from fastapi.testclient import TestClient

from app_v4.core.auth_service import AuthService
from app_v4.data.repository import Repository
from app_v4.service.app import create_app
from app_v4.service.runtime import ServiceRuntime

JWT_SECRET = b"test-secret-for-audit-api-tests-32"


def _token(settings, user_id: int, role: str) -> str:
    return AuthService(settings, JWT_SECRET).issue_access_token(user_id=user_id, username=f"u{user_id}", role=role)


def test_audit_endpoint_is_admin_only(test_settings, session_factory):
    async def seed():
        async with session_factory() as session:
            repo = Repository(session)
            admin = await repo.create_user("admin", "hash", "admin")
            viewer = await repo.create_user("viewer", "hash", "viewer")
            await repo.write_audit(admin.id, "switch.created", "switch", "7", "127.0.0.1", '{"name":"sw01"}')
            await session.commit()
            return admin.id, viewer.id

    import anyio

    admin_id, viewer_id = anyio.run(seed)
    client = TestClient(
        create_app(
            ServiceRuntime.for_tests(
                test_settings,
                session_factory=session_factory,
                jwt_secret=JWT_SECRET,
            )
        )
    )

    viewer = client.get("/api/v1/audit", headers={"Authorization": f"Bearer {_token(test_settings, viewer_id, 'viewer')}"})
    assert viewer.status_code == 403

    admin = client.get("/api/v1/audit", headers={"Authorization": f"Bearer {_token(test_settings, admin_id, 'admin')}"})
    assert admin.status_code == 200
    assert admin.json()[0]["action"] == "switch.created"
    assert admin.json()[0]["detail_json"] == {"name": "sw01"}
