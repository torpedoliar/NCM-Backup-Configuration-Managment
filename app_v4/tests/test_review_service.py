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


def test_add_months_calendar_precision():
    """Calendar-month arithmetic clamps to month end (Jan 31 + 1mo -> Feb 28/29)."""
    from datetime import datetime

    from app_v4.service.review_service import _add_months

    assert _add_months(datetime(2026, 1, 31, 10, 0), 1) == datetime(2026, 2, 28, 10, 0)
    assert _add_months(datetime(2024, 1, 31), 1) == datetime(2024, 2, 29, 0, 0)  # leap year
    assert _add_months(datetime(2026, 3, 15), 6) == datetime(2026, 9, 15)
    assert _add_months(datetime(2026, 11, 30), 3) == datetime(2027, 2, 28)  # year rollover


@pytest.mark.asyncio
async def test_compliance_due_uses_calendar_months(test_settings, session_factory):
    """compliance_rows marks stale exactly at created_at + N calendar months."""
    from datetime import timedelta

    from app_v4.core.utcdatetime import utc_now
    from app_v4.data.repository import Repository

    service = ReviewService(test_settings, session_factory)
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential("cred-cal", b"enc")
        sw = await repo.create_switch("sw-cal", "10.0.0.12", "ssh", 22, cred.id)
        await session.commit()
        sid = sw.id

    async with session_factory() as session:
        repo = Repository(session)
        baseline = await repo.create_baseline(
            kind="switch", switch_id=sid, model=None,
            backup_id=None, content_hash="h", created_by=None,
        )
        await session.commit()

    # 29 days before due date (6-month cycle => ~5 months old): not due.
    not_due = utc_now() - timedelta(days=6 * 30 - 29)
    async with session_factory() as session:
        repo = Repository(session)
        (await repo.get_baseline(baseline.id)).created_at = not_due
        await session.commit()
    rows = await service.compliance_rows()
    row = next(r for r in rows if r["switch"] == "sw-cal")
    assert row["baseline"] == "yes"
    assert row["reminder_due"] is False

    # 200 days old => due date (created + 6 calendar months) is ~2.5 weeks past: due.
    overdue = utc_now() - timedelta(days=200)
    async with session_factory() as session:
        repo = Repository(session)
        (await repo.get_baseline(baseline.id)).created_at = overdue
        await session.commit()
    rows = await service.compliance_rows()
    row = next(r for r in rows if r["switch"] == "sw-cal")
    assert row["baseline"] == "stale"
    assert row["reminder_due"] is True
    assert row["next_review"]  # YYYY-MM-DD present for the export


@pytest.mark.asyncio
async def test_review_interval_monthly_cycle(test_settings, session_factory):
    """Reminder-review fires at the configured N-month interval; fresh baseline is not due."""
    from app_v4.data.repository import Repository

    service = ReviewService(test_settings, session_factory)
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential("cred-int", b"enc")
        sw = await repo.create_switch("sw-interval", "10.0.0.11", "ssh", 22, cred.id)
        await session.commit()
        sid = sw.id

    ctx = await service.reminder_context()
    assert ctx["review_interval_months"] == 6  # default
    assert ctx["reminder_review_count"] == 0  # no baseline at all

    async with session_factory() as session:
        repo = Repository(session)
        baseline = await repo.create_baseline(
            kind="switch", switch_id=sid, model=None,
            backup_id=None, content_hash="h", created_by=None,
        )
        await session.commit()

    ctx = await service.reminder_context()
    assert ctx["reminder_review_count"] == 0  # fresh baseline: next review in 6 months

    # Simulate a 7-month-old baseline by back-dating created_at.
    from datetime import timedelta

    from app_v4.core.utcdatetime import utc_now

    async with session_factory() as session:
        repo = Repository(session)
        baseline = await repo.get_baseline(baseline.id)
        baseline.created_at = utc_now() - timedelta(days=215)  # ~7 months
        await session.commit()

    ctx = await service.reminder_context()
    assert ctx["reminder_review_count"] == 1
    row = ctx["reminder_reviews"][0]
    assert row["switch"] == "sw-interval"
    assert row["days_overdue"] > 0
    assert row["interval_months"] == 6

    # Reminder email includes the Reminder review section.
    content = await service.send_reminder(review_url="http://x/config-review")
    assert "Reminder review" in content["body_text"]
    assert "sw-interval" in content["body_text"]


@pytest.mark.asyncio
async def test_reminder_with_custom_html_template(test_settings, session_factory):
    """Custom template renders variables; escaped output; multipart bodies returned."""
    from app_v4.data.repository import Repository
    from app_v4.data.models import Switch  # noqa: F401

    service = ReviewService(
        test_settings, session_factory,
        email_template="<p>Pending: {{pending_count}} — {{pending_reviews_html}}</p>"
                       "<p>Note <b>{{missing_baselines}}</b> & {{generated_at}}</p>"
                       "<p>Unknown var: {{nope}}</p>",
    )
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential("cred-rem", b"enc")
        sw = await repo.create_switch('sw<script>alert("x")</script>', "10.0.0.9", "ssh", 22, cred.id)
        await repo.create_backup(
            switch_id=sw.id, file_path="/tmp/f2", content_hash="h2",
            size_bytes=1, success=True, message="m",
        )
        await repo.create_review(
            switch_id=sw.id, backup_id=1, baseline_id=None,
            raw_diff="-a\n+b", diff_summary="{}",
        )
        await session.commit()

    content = await service.send_reminder(review_url="http://x/config-review")
    assert content["subject"] == "[NCM] Config review: 1 pending"
    html = content["body_html"]
    assert "Pending: 1" in html
    assert "<script>" not in html  # switch name is HTML-escaped
    assert "&lt;script&gt;" in html
    assert "Unknown var: <" in html  # unknown variable renders as empty string
    assert "{{nope}}" not in html
    assert "Pending config reviews: 1" in content["body_text"]  # text part still present

    # No custom template -> default HTML body includes the built-in table
    service2 = ReviewService(test_settings, session_factory)
    content2 = await service2.send_reminder(review_url="http://x/config-review")
    assert "config management review reminder" in content2["body_html"].lower()
