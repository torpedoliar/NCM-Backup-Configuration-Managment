"""End-to-end drift detection: golden baseline -> drifted backup -> review created."""

import hashlib
import json
from pathlib import Path

import pytest

from app_v4.data.repository import Repository
from app_v4.net.runner import BackupRunResult
from app_v4.service.backup_service import BackupService
from app_v4.service.diff_service import DiffService
from app_v4.service.events import EventHub, EventMessage
from app_v4.service.review_service import ReviewService
from app_v4.tests.test_backup_service import FakeRunner

_FIXTURE = Path(__file__).parent / "fixtures" / "network_doc" / "awplus.txt"


class RecordingHub(EventHub):
    """EventHub that records broadcasts instead of pushing to websockets."""

    def __init__(self) -> None:
        super().__init__()
        self.events: list[EventMessage] = []

    async def broadcast(self, event: EventMessage) -> None:
        self.events.append(event)


@pytest.mark.asyncio
async def test_e2e_drift_baseline_switch(test_settings, session_factory, crypto_service):
    """Switch-level baseline: create golden -> drift -> review created + event."""
    base = test_settings.base_dir

    async with session_factory() as session:
        repo = Repository(session)
        blob = crypto_service.encrypt_credential("admin", "p", "e")
        cred = await repo.create_credential("cred", blob)
        sw = await repo.create_switch("e2e-sw", "10.0.0.1", "ssh", 22, cred.id)
        await session.commit()
        sid = sw.id

    base_text = _FIXTURE.read_text(encoding="utf-8")

    # Write golden to disk, create backup record, create baseline
    golden_path = base / "golden_switch.txt"
    golden_path.write_text(base_text, encoding="utf-8")
    async with session_factory() as session:
        repo = Repository(session)
        golden = await repo.create_backup(
            switch_id=sid, file_path=str(golden_path),
            content_hash=hashlib.sha256(base_text.encode("utf-8")).hexdigest(),
            size_bytes=len(base_text.encode("utf-8")),
            success=True, message="golden",
        )
        bl = await repo.create_baseline(
            kind="switch", switch_id=sid, model=None,
            backup_id=golden.id, content_hash="", created_by=None,
        )
        await session.commit()
        bl_id = bl.id

    drifted = base_text.replace("vlan 4 name BOD", "vlan 4 name BOD_RENAMED\nvlan 99 name DRIFTED")

    hub = RecordingHub()
    rs = ReviewService(test_settings, session_factory)
    bsvc = BackupService(
        settings=test_settings, session_factory=session_factory,
        crypto_service=crypto_service,
        runner=FakeRunner(BackupRunResult(True, drifted, "ok")),
        diff_service=DiffService(test_settings), event_hub=hub, review_service=rs,
    )
    result = await bsvc.execute_backup(switch_id=sid, backup_type="manual", triggered_by_user_id=None)
    assert result["success"] is True

    async with session_factory() as session:
        repo = Repository(session)
        reviews = await repo.list_reviews(switch_id=sid, limit=10)
        assert len(reviews) >= 1, "No review created after drift"
        r = reviews[0]
        assert r.status == "pending"
        assert r.backup_id == result["backup_id"]
        assert r.baseline_id == bl_id
        summary = json.loads(r.diff_summary)
        assert summary["vlans_renamed"] == [4] or summary["vlans_added"] == [99]
        assert "Baseline" in r.raw_diff

    drift_events = [e for e in hub.events if e.type == "config_drift"]
    assert len(drift_events) == 1
    assert drift_events[0].payload["switch_id"] == sid
    assert drift_events[0].payload["backup_id"] == result["backup_id"]

    completed_events = [e for e in hub.events if e.type == "backup_completed"]
    assert len(completed_events) == 1


@pytest.mark.asyncio
async def test_e2e_drift_model_baseline(test_settings, session_factory, crypto_service):
    """Model-level baseline: switch inherits template, drift detected."""
    base = test_settings.base_dir

    async with session_factory() as session:
        repo = Repository(session)
        blob = crypto_service.encrypt_credential("admin", "p", "e")
        cred = await repo.create_credential("cred", blob)
        sw = await repo.create_switch("e2e-model-a", "10.0.0.2", "ssh", 22, cred.id)
        await repo.update_switch(sw.id, model="AT-8000")
        await session.commit()
        sid = sw.id

    base_text = _FIXTURE.read_text(encoding="utf-8")

    golden_path = base / "golden_model.txt"
    golden_path.write_text(base_text, encoding="utf-8")
    async with session_factory() as session:
        repo = Repository(session)
        golden = await repo.create_backup(
            switch_id=sid, file_path=str(golden_path),
            content_hash=hashlib.sha256(base_text.encode("utf-8")).hexdigest(),
            size_bytes=len(base_text.encode("utf-8")),
            success=True, message="golden",
        )
        await repo.create_baseline(
            kind="model", switch_id=None, model="AT-8000",
            backup_id=golden.id, content_hash="", created_by=None,
        )
        await session.commit()

    drifted = base_text.replace("vlan 4 name BOD", "vlan 4 name BOD\nvlan 100 name DRIFTED")

    rs = ReviewService(test_settings, session_factory)
    bsvc = BackupService(
        settings=test_settings, session_factory=session_factory,
        crypto_service=crypto_service,
        runner=FakeRunner(BackupRunResult(True, drifted, "ok")),
        diff_service=DiffService(test_settings), review_service=rs,
    )
    result = await bsvc.execute_backup(switch_id=sid, backup_type="manual", triggered_by_user_id=None)
    assert result["success"] is True

    async with session_factory() as session:
        repo = Repository(session)
        reviews = await repo.list_reviews(switch_id=sid, limit=10)
        assert len(reviews) >= 1, "Model baseline drift not detected"
        summary = json.loads(reviews[0].diff_summary)
        assert summary["vlans_added"] == [100]


@pytest.mark.asyncio
async def test_e2e_no_drift_skips_review(test_settings, session_factory, crypto_service):
    """Identical config produces no review."""
    base = test_settings.base_dir

    async with session_factory() as session:
        repo = Repository(session)
        blob = crypto_service.encrypt_credential("admin", "p", "e")
        cred = await repo.create_credential("cred", blob)
        sw = await repo.create_switch("e2e-no-drift", "10.0.0.3", "ssh", 22, cred.id)
        await session.commit()
        sid = sw.id

    same_text = _FIXTURE.read_text(encoding="utf-8")

    golden_path = base / "golden_nodrift.txt"
    golden_path.write_text(same_text, encoding="utf-8")
    async with session_factory() as session:
        repo = Repository(session)
        golden = await repo.create_backup(
            switch_id=sid, file_path=str(golden_path),
            content_hash=hashlib.sha256(same_text.encode("utf-8")).hexdigest(),
            size_bytes=len(same_text.encode("utf-8")),
            success=True, message="golden",
        )
        await repo.create_baseline(
            kind="switch", switch_id=sid, model=None,
            backup_id=golden.id, content_hash="", created_by=None,
        )
        await session.commit()

    rs = ReviewService(test_settings, session_factory)
    bsvc = BackupService(
        settings=test_settings, session_factory=session_factory,
        crypto_service=crypto_service,
        runner=FakeRunner(BackupRunResult(True, same_text, "ok")),
        diff_service=DiffService(test_settings), review_service=rs,
    )
    result = await bsvc.execute_backup(switch_id=sid, backup_type="manual", triggered_by_user_id=None)
    assert result["success"] is True

    async with session_factory() as session:
        repo = Repository(session)
        reviews = await repo.list_reviews(switch_id=sid, limit=10)
        assert len(reviews) == 0, "Identical config should not create a review"