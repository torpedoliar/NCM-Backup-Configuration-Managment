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
        golden = await repo.create_backup(
            switch_id=sw.id, file_path="/tmp/golden.txt", content_hash="h1",
            size_bytes=10, success=True, message="golden",
        )
        await session.commit()
        admin_id, switch_id, golden_id = admin.id, sw.id, golden.id

    client = _make_client(test_settings, session_factory)
    headers = {"Authorization": f"Bearer {_token(test_settings, admin_id, 'admin')}"}

    resp = client.get("/api/v1/baselines", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []

    # No successful backup -> baseline creation is refused (zombie guard).
    resp = client.post("/api/v1/baselines", headers=headers, json={"kind": "model", "model": "NOBACKUP-9000"})
    assert resp.status_code == 422

    resp = client.post("/api/v1/baselines", headers=headers, json={"kind": "switch", "switch_id": switch_id})
    assert resp.status_code == 201
    data = resp.json()
    assert data["kind"] == "switch"
    assert data["switch_id"] == switch_id
    # Falls back to the switch's latest successful backup.
    assert data["backup_id"] == golden_id

    resp = client.post("/api/v1/baselines", headers=headers, json={"kind": "switch", "switch_id": switch_id})
    assert resp.status_code == 409

    resp = client.post("/api/v1/baselines", headers=headers, json={"kind": "model", "model": "AT-8000"})
    assert resp.status_code == 422  # no backup of any AT-8000 switch yet

    # Explicit golden backup works for model templates.
    resp = client.post(
        "/api/v1/baselines",
        headers=headers,
        json={"kind": "model", "model": "AT-8000", "backup_id": golden_id},
    )
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
        await repo.create_backup(
            switch_id=sw.id, file_path="/tmp/seed.txt", content_hash="seed",
            size_bytes=10, success=True, message="seed backup",
        )
        await session.commit()
        admin_id, switch_id = admin.id, sw.id

    rs = ReviewService(test_settings, session_factory)
    client = _make_client(test_settings, session_factory, review_service=rs)
    headers = {"Authorization": f"Bearer {_token(test_settings, admin_id, 'admin')}"}

    # The baseline now snapshots the switch's latest successful backup.
    resp = client.post("/api/v1/baselines", json={"kind": "switch", "switch_id": switch_id}, headers=headers)
    assert resp.status_code == 201
    baseline_id = resp.json()["id"]
    assert resp.json()["backup_id"] is not None

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
async def test_on_demand_review_drift_and_clean(test_settings, session_factory, tmp_path):
    """POST /baselines/{id}/refresh compares golden vs latest: drift opens a pending
    review; a second run (no change) reports no drift; both are audit-logged."""
    async with session_factory() as session:
        repo = Repository(session)
        admin = await repo.create_user("admin4", "hash", "admin")
        cred = await repo.create_credential("cred-ond", b"enc")
        sw = await repo.create_switch("sw-ondemand", "10.0.0.4", "ssh", 22, cred.id)
        await session.commit()
        admin_id, switch_id = admin.id, sw.id

    rs = ReviewService(test_settings, session_factory)
    client = _make_client(test_settings, session_factory, review_service=rs)
    headers = {"Authorization": f"Bearer {_token(test_settings, admin_id, 'admin')}"}

    golden_text = "hostname sw-ondemand\nvlan 10 name MGMT\n"
    golden_file = tmp_path / "golden_ondemand.txt"
    golden_file.write_text(golden_text, encoding="utf-8")

    async with session_factory() as session:
        repo = Repository(session)
        golden = await repo.create_backup(
            switch_id=switch_id, file_path=str(golden_file),
            content_hash="goldenhash", size_bytes=100, success=True, message="golden",
        )
        baseline = await repo.create_baseline(
            kind="switch", switch_id=switch_id, model=None,
            backup_id=golden.id, content_hash="goldenhash", created_by=None,
        )
        await session.commit()
        baseline_id, golden_id = baseline.id, golden.id

    # Latest backup drifts from the golden.
    drifted_file = tmp_path / "latest_ondemand.txt"
    drifted_file.write_text(golden_text + "vlan 99 name NEW\n", encoding="utf-8")
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_backup(
            switch_id=switch_id, file_path=str(drifted_file),
            content_hash="drifthash", size_bytes=120, success=True, message="drift",
        )
        await session.commit()

    resp = client.post(f"/api/v1/baselines/{baseline_id}/refresh", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["drifted"] is True
    assert body["review_id"] is not None
    assert body["baseline"]["backup_id"] != golden_id  # re-pointed to the latest

    async with session_factory() as session:
        repo = Repository(session)
        review = await repo.get_review(body["review_id"])
        assert review is not None and review.status == "pending"
        audits = await repo.list_audit(limit=10)
        refreshed = [a for a in audits if a.action == "baseline.refreshed"]
        assert refreshed and json.loads(refreshed[0].detail_json)["drifted"] is True

    # Run again: golden is now the drifted config -> no drift.
    resp2 = client.post(f"/api/v1/baselines/{baseline_id}/refresh", headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["drifted"] is False
    assert resp2.json()["review_id"] is None


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