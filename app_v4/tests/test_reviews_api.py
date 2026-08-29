import json

import pytest
from fastapi.testclient import TestClient

from app_v4.core.auth_service import AuthService
from app_v4.core.runtime_settings import AuthSettings
from app_v4.data.repository import Repository
from app_v4.service.app import create_app
from app_v4.service.review_service import ReviewService
from app_v4.service.runtime import ServiceRuntime

JWT_SECRET = b"test-secret-for-reviews-api-tests-32"


def _token(settings, user_id: int, role: str = "admin") -> str:
    return AuthService(
        jwt_secret=JWT_SECRET,
        settings_provider=lambda: AuthSettings(),
    ).issue_access_token(user_id=user_id, username=f"u{user_id}", role=role)


def _make_client(test_settings, session_factory, review_service=None) -> TestClient:
    return TestClient(
        create_app(
            ServiceRuntime.for_tests(
                test_settings,
                session_factory=session_factory,
                jwt_secret=JWT_SECRET,
                review_service=review_service,
            )
        )
    )


@pytest.mark.asyncio
async def test_baseline_crud(test_settings, session_factory):
    """Create, list, and delete per-switch and model baselines via API."""
    async with session_factory() as session:
        repo = Repository(session)
        admin = await repo.create_user("admin", "hash", "admin")
        cred = await repo.create_credential("test-cred", b"enc_blob")
        sw = await repo.create_switch("sw-test", "10.0.0.1", "ssh", 22, cred.id)
        await session.commit()
        admin_id, switch_id = admin.id, sw.id

    client = _make_client(test_settings, session_factory)
    headers = {"Authorization": f"Bearer {_token(test_settings, admin_id, 'admin')}"}

    resp = client.get("/api/v1/baselines", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []

    resp = client.post("/api/v1/baselines", headers=headers, json={"kind": "switch", "switch_id": switch_id})
    assert resp.status_code == 201
    data = resp.json()
    assert data["kind"] == "switch"
    assert data["switch_id"] == switch_id
    assert data["backup_id"] is None

    resp = client.post("/api/v1/baselines", headers=headers, json={"kind": "switch", "switch_id": switch_id})
    assert resp.status_code == 409

    resp = client.post("/api/v1/baselines", headers=headers, json={"kind": "model", "model": "AT-8000"})
    assert resp.status_code == 201
    assert resp.json()["kind"] == "model"

    resp = client.post("/api/v1/baselines", headers=headers, json={"kind": "model", "model": "AT-8000"})
    assert resp.status_code == 409

    resp = client.get("/api/v1/baselines", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    baseline_id = data["id"]
    resp = client.delete(f"/api/v1/baselines/{baseline_id}", headers=headers)
    assert resp.status_code == 204

    resp = client.delete(f"/api/v1/baselines/{baseline_id}", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_review_workflow(test_settings, session_factory):
    """Create a baseline, run a drifted backup, review the resulting drift."""
    async with session_factory() as session:
        repo = Repository(session)
        admin = await repo.create_user("admin2", "hash", "admin")
        cred = await repo.create_credential("cred-review", b"enc")
        sw = await repo.create_switch("sw-review", "10.0.0.2", "ssh", 22, cred.id)
        await session.commit()
        admin_id, switch_id = admin.id, sw.id

    rs = ReviewService(test_settings, session_factory)
    client = _make_client(test_settings, session_factory, review_service=rs)
    headers = {"Authorization": f"Bearer {_token(test_settings, admin_id, 'admin')}"}

    resp = client.post("/api/v1/baselines", headers=headers, json={"kind": "switch", "switch_id": switch_id})
    assert resp.status_code == 201
    baseline_id = resp.json()["id"]

    async with session_factory() as session:
        repo = Repository(session)
        backup = await repo.create_backup(
            switch_id=switch_id, file_path="/tmp/fake", content_hash="abc",
            size_bytes=100, success=True, message="manual backup",
        )
        review = await repo.create_review(
            switch_id=switch_id, backup_id=backup.id, baseline_id=baseline_id,
            raw_diff="--- a\n+++ b\n@@ -1 +1 @@\n-old\n+new",
            diff_summary=json.dumps({"vlans_added": [100], "vlans_removed": []}),
        )
        await session.commit()
        review_id = review.id

    resp = client.get("/api/v1/reviews", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["status"] == "pending"
    assert data[0]["switch_name"] == "sw-review"
    assert data[0]["diff_summary"]["vlans_added"] == [100]

    resp = client.get("/api/v1/reviews?status=approved", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []

    resp = client.get(f"/api/v1/reviews/{review_id}/diff", headers=headers)
    assert resp.status_code == 200
    assert "old" in resp.text

    resp = client.post(
        f"/api/v1/reviews/{review_id}/status",
        headers=headers,
        json={"status": "approved", "comment": "Looks good"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
    assert resp.json()["comment"] == "Looks good"

    resp = client.get("/api/v1/reviews/compliance", headers=headers)
    assert resp.status_code == 200
    comp = resp.json()
    assert comp["switches_with_baseline"] >= 1
    assert comp["reviews_approved"] >= 1


@pytest.mark.asyncio
async def test_notify_settings(test_settings, session_factory):
    """GET/PATCH /system/notify-settings."""
    async with session_factory() as session:
        repo = Repository(session)
        admin = await repo.create_user("admin3", "hash", "admin")
        await session.commit()
        admin_id = admin.id

    client = _make_client(test_settings, session_factory)
    headers = {"Authorization": f"Bearer {_token(test_settings, admin_id, 'admin')}"}

    resp = client.get("/api/v1/system/notify-settings", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["enabled"] is False
    assert data["app_public_url"] == "http://127.0.0.1:8443"

    resp = client.patch(
        "/api/v1/system/notify-settings",
        headers=headers,
        json={"enabled": True, "smtp_host": "smtp.example.com", "review_reminder_hour": 10},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["enabled"] is True
    assert data["smtp_host"] == "smtp.example.com"
    assert data["review_reminder_hour"] == 10

    resp = client.get("/api/v1/system/notify-settings", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["enabled"] is True
    assert resp.json()["review_reminder_hour"] == 10