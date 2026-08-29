import json

import pytest

from app_v4.data.repository import Repository
from app_v4.service.review_service import ReviewService

BASE = (
    "hostname sw1\n"
    "!\n"
    "vlan 10 name MGMT\n"
    "!\n"
    "interface port1.0.1\n"
    " switchport mode access\n"
    "!\n"
)

DRIFTED = (
    "hostname sw1\n"
    "!\n"
    "vlan 10 name MGMT\n"
    "vlan 20 name NEW\n"
    "!\n"
    "interface port1.0.1\n"
    " switchport mode access\n"
    "!\n"
)


@pytest.mark.asyncio
async def test_drift_creates_pending_review(test_settings, session_factory):
    service = ReviewService(test_settings, session_factory)

    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential("cred", b"enc")
        sw = await repo.create_switch("sw1", "10.0.0.1", "ssh", 22, cred.id)
        baseline = await repo.create_baseline(
            kind="switch", switch_id=sw.id, model=None,
            backup_id=None, content_hash="h", created_by=None,
        )
        backup = await repo.create_backup(
            switch_id=sw.id, file_path="/tmp/f", content_hash="h",
            size_bytes=1, success=True, message="m",
        )
        await session.commit()
        switch_id = sw.id
        baseline_id = baseline.id
        backup_id = backup.id

    outcome = await service.on_backup_complete(
        switch=sw,
        backup_id=backup_id,
        content_text=DRIFTED,
        baseline_text=BASE,
        baseline_id=baseline_id,
    )

    assert outcome.drifted is True
    assert outcome.review_id is not None

    async with session_factory() as session:
        repo = Repository(session)
        reviews = await repo.list_reviews(status="pending")
        assert len(reviews) == 1
        review = reviews[0]
        assert review.backup_id == backup_id
        assert review.baseline_id == baseline_id
        summary = json.loads(review.diff_summary)
        assert summary["vlans_added"] == [20]
        assert "Baseline" in review.raw_diff


@pytest.mark.asyncio
async def test_no_diff_skips_review(test_settings, session_factory):
    service = ReviewService(test_settings, session_factory)
    outcome = await service.on_backup_complete(
        switch=None,
        backup_id=1,
        content_text=BASE,
        baseline_text=BASE,
        baseline_id=1,
    )
    assert outcome.drifted is False


@pytest.mark.asyncio
async def test_review_status_transitions(test_settings, session_factory):
    service = ReviewService(test_settings, session_factory)

    async with session_factory() as session:
        repo = Repository(session)
        user = await repo.create_user("reviewer", "hash", "admin")
        cred = await repo.create_credential("cred2", b"enc")
        sw = await repo.create_switch("sw2", "10.0.0.", "ssh", 22, cred.id)
        backup = await repo.create_backup(
            switch_id=sw.id, file_path="/tmp/f", content_hash="h",
            size_bytes=1, success=True, message="m",
        )
        review = await repo.create_review(
            switch_id=sw.id, backup_id=backup.id, baseline_id=None,
            raw_diff="a", diff_summary="{}",
        )
        await session.commit()
        review_id = review.id
        reviewer_id = user.id

    assert await service.set_review_status(review_id, "approved", reviewed_by=reviewer_id, comment="ok") is True

    async with session_factory() as session:
        repo = Repository(session)
        review = await repo.get_review(review_id)
        assert review.status == "approved"
        assert review.reviewed_by == reviewer_id
        assert review.reviewed_at is not None
        assert review.comment == "ok"

    with pytest.raises(ValueError):
        await service.set_review_status(review_id, "bogus", reviewed_by=reviewer_id)


@pytest.mark.asyncio
async def test_compliance_summary(test_settings, session_factory):
    service = ReviewService(test_settings, session_factory)

    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential("cred3", b"enc")
        await repo.create_switch("sw-a", "10.0.0.3", "ssh", 22, cred.id)
        await session.commit()

    summary = await service.compliance_summary(attestation_days=30)
    assert summary["switches_total"] >= 1
    assert summary["switches_missing_baseline"] != []
    assert "reviews_pending" in summary


@pytest.mark.asyncio
async def test_reminder_empty_when_nothing_pending(test_settings, session_factory):
    service = ReviewService(test_settings, session_factory)
    content = await service.send_reminder()
    assert content["subject"] == "" or "pending" in content["subject"].lower()
