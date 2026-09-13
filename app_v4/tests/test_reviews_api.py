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
async def test_backup_switch_seq_per_switch(test_settings, session_factory):
    """Each switch gets its own 1,2,3... sequence independent of global ids."""
    from app_v4.data.repository import Repository

    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential("c-seq", b"enc")
        sw1 = await repo.create_switch("sw-seq-1", "10.0.0.21", "ssh", 22, cred.id)
        sw2 = await repo.create_switch("sw-seq-2", "10.0.0.22", "ssh", 22, cred.id)
        b1 = await repo.create_backup(sw1.id, "/tmp/a1", "h1", 10, True)
        b2 = await repo.create_backup(sw1.id, "/tmp/a2", "h2", 10, True)
        other = await repo.create_backup(sw2.id, "/tmp/b1", "h3", 10, True)
        await session.commit()
        assert (b1.switch_seq, b2.switch_seq) == (1, 2)
        assert other.switch_seq == 1


@pytest.mark.asyncio
async def test_review_workflow_in_review_and_notes(test_settings, session_factory):
    """Full flow: pending -> start (in_review) -> notes thread -> approved."""
    async with session_factory() as session:
        repo = Repository(session)
        admin = await repo.create_user("admin-flow", "hash", "admin")
        cred = await repo.create_credential("cred-flow", b"enc")
        sw = await repo.create_switch("sw-flow", "10.0.0.6", "ssh", 22, cred.id)
        await repo.create_backup(
            switch_id=sw.id, file_path="/tmp/flow.txt", content_hash="f1",
            size_bytes=10, success=True, message="seed",
        )
        await session.commit()
        admin_id, switch_id = admin.id, sw.id

    rs = ReviewService(test_settings, session_factory)
    client = _make_client(test_settings, session_factory, review_service=rs)
    headers = {"Authorization": f"Bearer {_token(test_settings, admin_id, 'admin')}"}

    # Seed a pending review directly.
    async with session_factory() as session:
        repo = Repository(session)
        review = await repo.create_review(
            switch_id=switch_id, backup_id=1, baseline_id=None,
            raw_diff="-a\n+b", diff_summary="{}",
        )
        await session.commit()
        review_id = review.id

    # Start -> in_review with reviewer captured.
    resp = client.post(f"/api/v1/reviews/{review_id}/start", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "in_review"
    assert body["started_by"] == admin_id
    assert body["started_at"] is not None

    # Double-start -> 409.
    resp = client.post(f"/api/v1/reviews/{review_id}/start", headers=headers)
    assert resp.status_code == 409

    # Add notes to the thread.
    resp = client.post(
        f"/api/v1/reviews/{review_id}/notes",
        headers=headers,
        json={"body": "Port 1/0/12 down — menunggu konfirmasi NOC"},
    )
    assert resp.status_code == 200
    assert resp.json()[0]["body"].startswith("Port 1/0/12")
    resp = client.post(
        f"/api/v1/reviews/{review_id}/notes",
        headers=headers,
        json={"body": "Dikonfirmasi NOC: aman"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    # Decision after notes; notes survive and are returned with the review.
    resp = client.post(
        f"/api/v1/reviews/{review_id}/status",
        headers=headers,
        json={"status": "approved", "comment": "ok"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "approved"
    assert body["reviewed_by"] == admin_id
    assert body["reviewed_by_name"] == "admin-flow"
    assert body["started_by_name"] == "admin-flow"
    assert len(body["notes"]) == 2  # thread intact after decision

    # list with include_notes returns the same thread.
    resp = client.get(f"/api/v1/reviews?include_notes=true", headers=headers)
    row = next(r for r in resp.json() if r["id"] == review_id)
    assert len(row["notes"]) == 2
    assert row["notes"][0]["author_name"] == "admin-flow"


@pytest.mark.asyncio
async def test_delete_review(test_settings, session_factory):
    """DELETE /reviews/{id} deletes review and associated notes."""
    async with session_factory() as session:
        repo = Repository(session)
        admin = await repo.create_user("admin-del", "hash", "admin")
        cred = await repo.create_credential("cred-del", b"enc")
        sw = await repo.create_switch("sw-del", "10.0.0.88", "ssh", 22, cred.id)
        b = await repo.create_backup(sw.id, "/tmp/del.txt", "h-del", 10, True)
        rev = await repo.create_review(sw.id, b.id, None, "diff", "{}")
        await repo.create_review_note(rev.id, admin.id, "some note")
        await session.commit()
        admin_id, review_id = admin.id, rev.id

    client = _make_client(test_settings, session_factory)
    headers = {"Authorization": f"Bearer {_token(test_settings, admin_id, 'admin')}"}

    resp = client.delete(f"/api/v1/reviews/{review_id}", headers=headers)
    assert resp.status_code == 204

    # Now review is gone -> 404
    resp2 = client.get(f"/api/v1/reviews/{review_id}/diff", headers=headers)
    assert resp2.status_code == 404

    # Deleting again -> 404
    resp3 = client.delete(f"/api/v1/reviews/{review_id}", headers=headers)
    assert resp3.status_code == 404


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


@pytest.mark.asyncio
async def test_review_promote_to_baseline_and_rollback(test_settings, session_factory):
    """POST /reviews/{id}/promote-baseline and GET /reviews/{id}/rollback."""
    async with session_factory() as session:
        repo = Repository(session)
        admin = await repo.create_user("admin-promote", "hash", "admin")
        cred = await repo.create_credential("c-prom", b"enc")
        sw = await repo.create_switch("SW-PROMOTE", "10.0.0.99", "ssh", 22, cred.id)
        b1 = await repo.create_backup(sw.id, "/tmp/p1", "hash-prom1", 100, True)
        b2 = await repo.create_backup(sw.id, "/tmp/p2", "hash-prom2", 120, True)
        bl = await repo.create_baseline(
            "switch",
            switch_id=sw.id,
            model=None,
            backup_id=b1.id,
            content_hash=b1.content_hash,
            created_by=admin.id,
        )
        diff_text = "--- Baseline\n+++ Current\n@@ -1,2 +1,3 @@\n hostname SW-OLD\n+ vlan 50\n- vlan 40\n"
        review = await repo.create_review(
            switch_id=sw.id,
            backup_id=b2.id,
            baseline_id=bl.id,
            raw_diff=diff_text,
            diff_summary="{}",
        )
        await session.commit()
        review_id = review.id
        admin_id = admin.id

    client = _make_client(test_settings, session_factory)
    headers = {"Authorization": f"Bearer {_token(test_settings, admin_id, 'admin')}"}

    # 1. Rollback script generation
    rb_resp = client.get(f"/api/v1/reviews/{review_id}/rollback", headers=headers)
    assert rb_resp.status_code == 200
    rb_text = rb_resp.text
    assert "REMEDIATION ROLLBACK SCRIPT FOR SW-PROMOTE" in rb_text
    assert "no vlan 50" in rb_text
    assert "vlan 40" in rb_text

    # 2. Promote to Baseline
    promote_resp = client.post(
        f"/api/v1/reviews/{review_id}/promote-baseline",
        headers=headers,
        json={"reason": "CR-2026-999: Approved VLAN change", "comment": "Verified by Audit"},
    )
    assert promote_resp.status_code == 200
    body = promote_resp.json()
    assert body["status"] == "approved"
    assert "[Promoted to Baseline] CR-2026-999" in body["comment"]
    assert any("CR-2026-999" in n["body"] for n in body["notes"])

    # 3. Verify baseline was updated to b2
    async with session_factory() as session:
        repo = Repository(session)
        updated_bl = await repo.get_baseline_for_switch(sw)
        assert updated_bl is not None
        assert updated_bl.backup_id == b2.id
        assert updated_bl.content_hash == b2.content_hash


@pytest.mark.asyncio
async def test_run_fleet_cycle_review(test_settings, session_factory):
    """POST /reviews/run-cycle."""
    async with session_factory() as session:
        repo = Repository(session)
        admin = await repo.create_user("admin-cycle", "hash", "admin")
        cred = await repo.create_credential("c-cyc", b"enc")
        sw = await repo.create_switch("SW-CYCLE-1", "10.0.0.101", "ssh", 22, cred.id)
        b = await repo.create_backup(sw.id, "/tmp/c1", "hash-c1", 100, True)
        bl = await repo.create_baseline("switch", switch_id=sw.id, model=None, backup_id=b.id, content_hash=b.content_hash, created_by=admin.id)
        await session.commit()
        admin_id = admin.id

    client = _make_client(test_settings, session_factory)
    headers = {"Authorization": f"Bearer {_token(test_settings, admin_id, 'admin')}"}

    resp = client.post("/api/v1/reviews/run-cycle", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_checked"] == 1
    assert data["clean_count"] == 1
    assert data["drift_count"] == 0
    assert "lolos attestasi clean" in data["message"]


@pytest.mark.asyncio
async def test_review_reminder_endpoint(test_settings, session_factory):
    """POST /reviews/reminder."""
    async with session_factory() as session:
        repo = Repository(session)
        admin = await repo.create_user("admin-rem", "hash", "admin")
        await session.commit()
        admin_id = admin.id

    rs = ReviewService(test_settings, session_factory)
    client = _make_client(test_settings, session_factory, review_service=rs)
    headers = {"Authorization": f"Bearer {_token(test_settings, admin_id, 'admin')}"}

    # When email is disabled, returns 422
    resp = client.post("/api/v1/reviews/reminder", headers=headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_prepare_baseline_review(test_settings, session_factory):
    """POST /baselines/{id}/prepare-review prepares comparison review without modifying baseline."""
    async with session_factory() as session:
        repo = Repository(session)
        admin = await repo.create_user("admin-prep", "hash", "admin")
        cred = await repo.create_credential("c-prep", b"enc")
        sw = await repo.create_switch("SW-PREP", "10.0.0.105", "ssh", 22, cred.id)
        b1 = await repo.create_backup(sw.id, "/tmp/p1", "hash-p1", 100, True)
        b2 = await repo.create_backup(sw.id, "/tmp/p2", "hash-p2", 100, True)
        bl = await repo.create_baseline("switch", switch_id=sw.id, model=None, backup_id=b1.id, content_hash=b1.content_hash, created_by=admin.id)
        await session.commit()
        admin_id, baseline_id, b1_id = admin.id, bl.id, b1.id

    rs = ReviewService(test_settings, session_factory)
    client = _make_client(test_settings, session_factory, review_service=rs)
    headers = {"Authorization": f"Bearer {_token(test_settings, admin_id, 'admin')}"}

    # 1. Prepare review -> returns review_id, baseline is NOT overwritten
    resp = client.post(f"/api/v1/baselines/{baseline_id}/prepare-review", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_new"] is True
    review_id = data["review_id"]

    # Verify baseline backup_id is still b1_id (NOT overwritten!)
    async with session_factory() as session:
        repo = Repository(session)
        check_bl = await repo.get_baseline(baseline_id)
        assert check_bl.backup_id == b1_id

    # 2. Calling prepare-review again returns the SAME active review
    resp2 = client.post(f"/api/v1/baselines/{baseline_id}/prepare-review", headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["review_id"] == review_id
    assert resp2.json()["is_new"] is False

    # 3. Check list_baselines returns review info
    resp_bl = client.get("/api/v1/baselines", headers=headers)
    assert resp_bl.status_code == 200
    bl_row = next(r for r in resp_bl.json() if r["id"] == baseline_id)
    assert bl_row["last_review_id"] == review_id
    assert bl_row["last_review_status"] == "in_review"
    assert bl_row["last_reviewed_by_name"] == "admin-prep"

    # 4. Approve review with explicit reviewer_name (e.g. from DataGuard session)
    resp_appr = client.post(
        f"/api/v1/reviews/{review_id}/status",
        headers=headers,
        json={"status": "approved", "comment": "Approved from DataGuard", "reviewer_name": "dg-operator-john"},
    )
    assert resp_appr.status_code == 200
    appr_body = resp_appr.json()
    assert appr_body["status"] == "approved"
    assert appr_body["reviewed_by_name"] == "dg-operator-john"
    assert appr_body["reviewed_at"] is not None

    # 5. Check list_baselines reflects approved status and reviewer name
    resp_bl2 = client.get("/api/v1/baselines", headers=headers)
    assert resp_bl2.status_code == 200
    bl_row2 = next(r for r in resp_bl2.json() if r["id"] == baseline_id)
    assert bl_row2["last_review_status"] == "approved"
    assert bl_row2["last_reviewed_by_name"] == "dg-operator-john"
    assert bl_row2["last_reviewed_at"] is not None

