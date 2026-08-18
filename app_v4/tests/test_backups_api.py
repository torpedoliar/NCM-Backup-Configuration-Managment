from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app_v4.data.repository import Repository
from app_v4.service.app import create_app
from app_v4.service.runtime import ServiceRuntime


@dataclass
class FakeBackupService:
    result: dict

    async def execute_backup(self, switch_id, backup_type="manual", job_id=None, triggered_by_user_id=None):
        return self.result | {"switch_id": switch_id, "triggered_by_user_id": triggered_by_user_id}


def _operator_token(runtime: ServiceRuntime) -> str:
    return runtime.auth_service.issue_access_token(1, "ops", "operator")


def _viewer_token(runtime: ServiceRuntime) -> str:
    return runtime.auth_service.issue_access_token(2, "viewer", "viewer")


def _admin_token(runtime: ServiceRuntime) -> str:
    return runtime.auth_service.issue_access_token(3, "admin", "admin")


@pytest.mark.asyncio
async def test_trigger_backup_requires_operator(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(
        test_settings,
        session_factory,
        jwt_secret=b"b" * 32,
        backup_service=FakeBackupService({"success": True, "message": "ok", "backup_id": 9, "file_path": "", "size_kb": 1}),
    )
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_user("ops", "hash", "operator")
        await repo.create_user("viewer", "hash", "viewer")
        await session.commit()

    client = TestClient(create_app(runtime))

    viewer = client.post("/api/v1/switches/1/backups", headers={"Authorization": f"Bearer {_viewer_token(runtime)}"})
    operator = client.post("/api/v1/switches/1/backups", headers={"Authorization": f"Bearer {_operator_token(runtime)}"})

    assert viewer.status_code == 403
    assert operator.status_code == 202
    assert operator.json()["backup_id"] == 9


@pytest.mark.asyncio
async def test_list_and_read_backup_content(test_settings, session_factory, tmp_path: Path):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"b" * 32)
    file_path = tmp_path / "config.txt"
    file_path.write_text("config", encoding="utf-8")
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential("cred", b"x")
        switch = await repo.create_switch("sw", "10.0.0.1", "ssh", 22, cred.id)
        backup = await repo.create_backup(switch.id, str(file_path), "h", 6, True, "ok")
        await session.commit()
        backup_id = backup.id

    client = TestClient(create_app(runtime))
    list_response = client.get("/api/v1/backups", headers={"Authorization": f"Bearer {_viewer_token(runtime)}"})
    content_response = client.get(f"/api/v1/backups/{backup_id}/content", headers={"Authorization": f"Bearer {_viewer_token(runtime)}"})

    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == backup_id
    assert content_response.status_code == 200
    assert content_response.text == "config"


@pytest.mark.asyncio
async def test_list_backups_filters_by_success(test_settings, session_factory, tmp_path: Path):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"b" * 32)
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential("cred", b"x")
        switch = await repo.create_switch("sw", "10.0.0.1", "ssh", 22, cred.id)
        await repo.create_backup(
            switch.id, "", "h1", 1, success=True, message="ok manual", backup_type="manual"
        )
        await repo.create_backup(
            switch.id, "", "h2", 1, success=False, message="timeout", backup_type="automatic"
        )
        await session.commit()

    client = TestClient(create_app(runtime))
    response = client.get(
        "/api/v1/backups?success=true",
        headers={"Authorization": f"Bearer {_viewer_token(runtime)}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert all(b["success"] for b in body)


@pytest.mark.asyncio
async def test_get_backup_content_download_sets_attachment_header(test_settings, session_factory, tmp_path: Path):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"b" * 32)
    file_path = tmp_path / "cfg.txt"
    file_path.write_text("running-config", encoding="utf-8")
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential("cred", b"x")
        switch = await repo.create_switch("core-sw", "10.0.0.1", "ssh", 22, cred.id)
        backup = await repo.create_backup(switch.id, str(file_path), "h", 14, True, "ok")
        await session.commit()
        backup_id = backup.id

    client = TestClient(create_app(runtime))
    response = client.get(
        f"/api/v1/backups/{backup_id}/content?download=true",
        headers={"Authorization": f"Bearer {_viewer_token(runtime)}"},
    )

    assert response.status_code == 200
    cd = response.headers.get("content-disposition", "")
    assert "attachment" in cd
    assert ".txt" in cd
    assert response.text == "running-config"


@pytest.mark.asyncio
async def test_delete_backup_admin_only_and_unlinks_file(test_settings, session_factory, tmp_path: Path):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"b" * 32)
    file_path = tmp_path / "cfg.txt"
    file_path.write_text("config", encoding="utf-8")
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_user("ops", "hash", "operator")
        await repo.create_user("viewer", "hash", "viewer")
        await repo.create_user("admin", "hash", "admin")
        cred = await repo.create_credential("cred", b"x")
        switch = await repo.create_switch("sw", "10.0.0.1", "ssh", 22, cred.id)
        backup = await repo.create_backup(switch.id, str(file_path), "h", 6, True, "ok")
        await session.commit()
        backup_id = backup.id

    client = TestClient(create_app(runtime))

    forbidden = client.delete(
        f"/api/v1/backups/{backup_id}",
        headers={"Authorization": f"Bearer {_operator_token(runtime)}"},
    )
    assert forbidden.status_code == 403

    deleted = client.delete(
        f"/api/v1/backups/{backup_id}",
        headers={"Authorization": f"Bearer {_admin_token(runtime)}"},
    )
    assert deleted.status_code == 204
    assert not file_path.exists()

    missing = client.get(
        f"/api/v1/backups/{backup_id}",
        headers={"Authorization": f"Bearer {_admin_token(runtime)}"},
    )
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_diff_backups_returns_no_changes_for_identical_files(test_settings, session_factory, tmp_path: Path):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"b" * 32)
    left_path = tmp_path / "left.txt"
    right_path = tmp_path / "right.txt"
    left_path.write_text("hostname sw\ninterface 1\n", encoding="utf-8")
    right_path.write_text("hostname sw\ninterface 1\n", encoding="utf-8")
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential("cred", b"x")
        switch = await repo.create_switch("sw", "10.0.0.1", "ssh", 22, cred.id)
        left = await repo.create_backup(switch.id, str(left_path), "h1", left_path.stat().st_size, True, "ok")
        right = await repo.create_backup(switch.id, str(right_path), "h2", right_path.stat().st_size, True, "ok")
        await session.commit()
        left_id = left.id
        right_id = right.id

    client = TestClient(create_app(runtime))
    response = client.get(
        f"/api/v1/backups/diff?a={left_id}&b={right_id}",
        headers={"Authorization": f"Bearer {_viewer_token(runtime)}"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    assert response.text == "No changes.\n"


@pytest.mark.asyncio
async def test_diff_backups_returns_problem_for_non_text_backup(test_settings, session_factory, tmp_path: Path):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"b" * 32)
    left_path = tmp_path / "left.txt"
    right_path = tmp_path / "right.txt"
    left_path.write_bytes(b"\xff\xfe\x00")
    right_path.write_text("hostname sw\n", encoding="utf-8")
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential("cred", b"x")
        switch = await repo.create_switch("sw", "10.0.0.1", "ssh", 22, cred.id)
        left = await repo.create_backup(switch.id, str(left_path), "h1", left_path.stat().st_size, True, "ok")
        right = await repo.create_backup(switch.id, str(right_path), "h2", right_path.stat().st_size, True, "ok")
        await session.commit()
        left_id = left.id
        right_id = right.id

    client = TestClient(create_app(runtime))
    response = client.get(
        f"/api/v1/backups/diff?a={left_id}&b={right_id}",
        headers={"Authorization": f"Bearer {_viewer_token(runtime)}"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "One or both backup files are not UTF-8 text"


@pytest.mark.asyncio
async def test_diff_backups_side_by_side_returns_paired_rows(test_settings, session_factory, tmp_path: Path):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"b" * 32)
    left_path = tmp_path / "left.txt"
    right_path = tmp_path / "right.txt"
    left_path.write_text("hostname sw\nvlan 10\nvlan 20\n", encoding="utf-8")
    right_path.write_text("hostname sw\nvlan 10\nvlan 30\nvlan 40\n", encoding="utf-8")
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential("cred", b"x")
        switch = await repo.create_switch("sw", "10.0.0.1", "ssh", 22, cred.id)
        left = await repo.create_backup(switch.id, str(left_path), "h1", left_path.stat().st_size, True, "ok")
        right = await repo.create_backup(switch.id, str(right_path), "h2", right_path.stat().st_size, True, "ok")
        await session.commit()
        left_id = left.id
        right_id = right.id

    client = TestClient(create_app(runtime))
    response = client.get(
        f"/api/v1/backups/diff/side-by-side?a={left_id}&b={right_id}",
        headers={"Authorization": f"Bearer {_viewer_token(runtime)}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "rows" in body
    assert "stats" in body
    ops = [row["op"] for row in body["rows"]]
    assert "equal" in ops
    assert "replace" in ops or "insert" in ops
    assert body["stats"]["added_lines"] >= 1


@pytest.mark.asyncio
async def test_backup_report_csv_xlsx_pdf(test_settings, session_factory, tmp_path: Path):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"b" * 32)
    file_path = tmp_path / "cfg.txt"
    file_path.write_text("config", encoding="utf-8")
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential("cred", b"x")
        switch = await repo.create_switch("core-sw", "10.0.0.1", "ssh", 22, cred.id)
        await repo.create_backup(switch.id, str(file_path), "h", 6, True, "ok")
        await session.commit()

    client = TestClient(create_app(runtime))
    headers = {"Authorization": f"Bearer {_viewer_token(runtime)}"}

    csv_resp = client.get("/api/v1/backups/report?format=csv", headers=headers)
    assert csv_resp.status_code == 200
    assert csv_resp.headers["content-type"].startswith("text/csv")
    assert "core-sw" in csv_resp.text
    assert "ID,Switch" in csv_resp.text

    xlsx_resp = client.get("/api/v1/backups/report?format=xlsx", headers=headers)
    assert xlsx_resp.status_code == 200
    assert "spreadsheetml" in xlsx_resp.headers["content-type"]
    assert xlsx_resp.content[:2] == b"PK"

    pdf_resp = client.get("/api/v1/backups/report?format=pdf", headers=headers)
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert pdf_resp.content[:4] == b"%PDF"
