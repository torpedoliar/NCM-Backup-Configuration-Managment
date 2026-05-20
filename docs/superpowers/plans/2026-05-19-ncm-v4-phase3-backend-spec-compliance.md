# NCM v4 Phase 3 Backend Spec Compliance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close remaining backend gaps from `docs/superpowers/specs/2026-05-18-ncm-v4-ops-terminal-design.md` before UI work depends on the API contract.

**Architecture:** Keep all changes inside `app_v4/`. Preserve existing routes where clients/tests already use them, but add spec-compatible aliases. Add service events, audit API, retention, problem details, static serving, and graceful shutdown as small backend units with direct tests.

**Tech Stack:** FastAPI, async SQLAlchemy, APScheduler AsyncIOScheduler, SQLite, pytest, pytest-asyncio, FastAPI TestClient.

---

## File Structure

- Modify: `app_v4/data/repository.py` — add query helpers for switch detail, backup `since`, backup diff pair lookup, audit filtering, retention deletion.
- Modify: `app_v4/service/api/switches.py` — add `GET /switches/{id}` and make delete admin-only.
- Modify: `app_v4/service/api/backups.py` — add spec route alias `POST /switches/{id}/backup`, add pair diff route, catch backup errors as problem-details.
- Modify: `app_v4/service/api/jobs.py` — add audit records for job mutations.
- Modify: `app_v4/service/api/auth.py` — add audit records for login/logout/refresh failures and successes.
- Modify: `app_v4/service/api/system.py` — include uptime, scheduler state, DB size.
- Modify: `app_v4/service/app.py` — register audit router, problem handlers, lifespan shutdown, static bundle mount/fallback.
- Modify: `app_v4/service/runtime.py` — wire `EventHub` into backup/scheduler/audit, expose startup time and shutdown.
- Modify: `app_v4/service/backup_service.py` — broadcast backup lifecycle events and return categorized failure codes.
- Modify: `app_v4/service/scheduler.py` — broadcast `job_triggered`, expose running state, call retention nightly.
- Modify: `app_v4/service/events.py` — keep current hub, add typed event helper functions.
- Modify: `app_v4/core/config.py` — add audit retention, static serving, and optional SSL settings.
- Modify: `app_v4/core/paths.py` — expose static index path and log path.
- Modify: `app_v4/core/dpapi.py` — use `CRYPTPROTECT_UI_FORBIDDEN` flag.
- Modify: `app_v4/core/key_envelope.py` — raise explicit `MasterKeyUnavailableError`.
- Create: `app_v4/service/api/audit.py` — admin-only audit log endpoint.
- Create: `app_v4/service/retention_service.py` — backup/audit retention cleanup.
- Create: `app_v4/service/problem_handlers.py` — RFC 7807-style exception handlers.
- Test: `app_v4/tests/test_backend_spec_contract.py`
- Test: `app_v4/tests/test_audit_api.py`
- Test: `app_v4/tests/test_events_integration.py`
- Test: `app_v4/tests/test_retention_service.py`
- Test: `app_v4/tests/test_problem_details.py`
- Test: `app_v4/tests/test_static_serving.py`

### Task 1: API Contract Compatibility

**Files:**
- Modify: `app_v4/data/repository.py`
- Modify: `app_v4/service/api/switches.py`
- Modify: `app_v4/service/api/backups.py`
- Test: `app_v4/tests/test_backend_spec_contract.py`

- [ ] **Step 1: Write failing API contract tests**

Create `app_v4/tests/test_backend_spec_contract.py`:

```python
from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app_v4.core.auth_service import AuthService
from app_v4.data.repository import Repository
from app_v4.service.app import create_app
from app_v4.service.runtime import Runtime


def _token(settings, user_id: int, role: str = "admin") -> str:
    return AuthService(settings).issue_access_token(user_id=user_id, username=f"u{user_id}", role=role)


async def _seed_user(session_factory, user_id: int, role: str):
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_user(f"u{user_id}", "hash", role)
        await session.commit()


def test_switch_detail_and_admin_only_delete(test_settings, session_factory, anyio_backend):
    async def seed():
        await _seed_user(session_factory, 1, "admin")
        await _seed_user(session_factory, 2, "operator")
        async with session_factory() as session:
            repo = Repository(session)
            cred = await repo.create_credential("c", b"blob")
            switch = await repo.create_switch("sw01", "10.0.0.1", "ssh", 22, cred.id)
            await session.commit()
            return switch.id

    import anyio
    switch_id = anyio.run(seed)
    app = create_app(Runtime.for_tests(test_settings, session_factory=session_factory))
    client = TestClient(app)

    admin_headers = {"Authorization": f"Bearer {_token(test_settings, 1, 'admin')}"}
    operator_headers = {"Authorization": f"Bearer {_token(test_settings, 2, 'operator')}"}

    detail = client.get(f"/api/v1/switches/{switch_id}", headers=admin_headers)
    assert detail.status_code == 200
    assert detail.json()["id"] == switch_id

    denied = client.delete(f"/api/v1/switches/{switch_id}", headers=operator_headers)
    assert denied.status_code == 403


def test_backup_spec_alias_and_pair_diff(test_settings, session_factory, crypto_service, anyio_backend, tmp_path):
    class FakeBackupService:
        async def execute_backup(self, switch_id, backup_type="manual", job_id=None, triggered_by_user_id=None):
            return {"success": True, "backup_id": 1, "message": "ok", "file_path": str(tmp_path / "new.txt")}

    async def seed():
        await _seed_user(session_factory, 1, "operator")
        async with session_factory() as session:
            repo = Repository(session)
            cred = await repo.create_credential("c", b"blob")
            switch = await repo.create_switch("sw01", "10.0.0.1", "ssh", 22, cred.id)
            old_path = tmp_path / "old.txt"
            new_path = tmp_path / "new.txt"
            old_path.write_text("hostname old\n", encoding="utf-8")
            new_path.write_text("hostname new\n", encoding="utf-8")
            old = await repo.create_backup(switch.id, "manual", True, str(old_path), "h1", 12, None, None, None)
            new = await repo.create_backup(switch.id, "manual", True, str(new_path), "h2", 12, old.id, None, None)
            await session.commit()
            return switch.id, old.id, new.id

    import anyio
    switch_id, old_id, new_id = anyio.run(seed)
    app = create_app(Runtime.for_tests(test_settings, session_factory=session_factory, backup_service=FakeBackupService()))
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {_token(test_settings, 1, 'operator')}"}

    trigger = client.post(f"/api/v1/switches/{switch_id}/backup", headers=headers)
    assert trigger.status_code == 200
    assert trigger.json()["backup_id"] == 1

    diff = client.get(f"/api/v1/backups/diff?a={old_id}&b={new_id}", headers=headers)
    assert diff.status_code == 200
    assert "-hostname old" in diff.text
    assert "+hostname new" in diff.text
```

- [ ] **Step 2: Run failing tests**

Run:

```powershell
rtk python -m pytest app_v4/tests/test_backend_spec_contract.py -v
```

Expected: fails because routes and RBAC changes are not implemented.

- [ ] **Step 3: Implement switch detail and delete RBAC**

In `app_v4/data/repository.py`, add:

```python
async def get_switch(self, switch_id: int) -> Switch | None:
    return await self.session.get(Switch, switch_id)
```

In `app_v4/service/api/switches.py`, add before patch/delete routes:

```python
@router.get("/switches/{switch_id}", response_model=SwitchOut)
async def get_switch(
    switch_id: int,
    session: AsyncSession = Depends(get_session),
    _user=Depends(require_role("admin", "operator", "viewer")),
):
    repo = Repository(session)
    switch = await repo.get_switch(switch_id)
    if switch is None:
        raise problem(404, "switch_not_found", f"Switch {switch_id} not found")
    return SwitchOut.model_validate(switch)
```

Change delete dependency to admin-only:

```python
_user=Depends(require_role("admin")),
```

- [ ] **Step 4: Implement backup alias and pair diff**

In `app_v4/service/api/backups.py`, factor trigger body into `_run_backup(...)` and expose both routes:

```python
@router.post("/switches/{switch_id}/backup")
async def trigger_backup_spec_alias(
    switch_id: int,
    runtime: Runtime = Depends(get_runtime),
    current_user=Depends(require_role("admin", "operator")),
):
    return await _run_backup(runtime, switch_id, current_user.id)

@router.post("/switches/{switch_id}/backups")
async def trigger_backup_existing_route(
    switch_id: int,
    runtime: Runtime = Depends(get_runtime),
    current_user=Depends(require_role("admin", "operator")),
):
    return await _run_backup(runtime, switch_id, current_user.id)
```

Add pair diff route:

```python
@router.get("/backups/diff")
async def diff_backups(
    a: int,
    b: int,
    session: AsyncSession = Depends(get_session),
    _user=Depends(require_role("admin", "operator", "viewer")),
):
    repo = Repository(session)
    left = await repo.get_backup(a)
    right = await repo.get_backup(b)
    if left is None or right is None:
        raise problem(404, "backup_not_found", "One or both backups were not found")
    left_path = Path(left.file_path or "")
    right_path = Path(right.file_path or "")
    if not left_path.exists() or not right_path.exists():
        raise problem(404, "backup_file_not_found", "One or both backup files were not found")
    diff = DiffService(runtime.settings).unified_diff(
        left_path.read_text(encoding="utf-8"),
        right_path.read_text(encoding="utf-8"),
        fromfile=f"backup-{a}",
        tofile=f"backup-{b}",
    )
    return Response(diff, media_type="text/plain")
```

- [ ] **Step 5: Run contract tests**

Run:

```powershell
rtk python -m pytest app_v4/tests/test_backend_spec_contract.py -v
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
rtk git add app_v4/data/repository.py app_v4/service/api/switches.py app_v4/service/api/backups.py app_v4/tests/test_backend_spec_contract.py
rtk git commit -m "feat: align v4 backend API contract with spec"
```

### Task 2: Audit API and Audit Coverage

**Files:**
- Create: `app_v4/service/api/audit.py`
- Modify: `app_v4/service/app.py`
- Modify: `app_v4/service/api/auth.py`
- Modify: `app_v4/service/api/jobs.py`
- Modify: `app_v4/service/api/backups.py`
- Test: `app_v4/tests/test_audit_api.py`

- [ ] **Step 1: Write failing audit API test**

Create `app_v4/tests/test_audit_api.py`:

```python
from fastapi.testclient import TestClient

from app_v4.core.auth_service import AuthService
from app_v4.data.repository import Repository
from app_v4.service.app import create_app
from app_v4.service.runtime import Runtime


def _token(settings, user_id: int, role: str) -> str:
    return AuthService(settings).issue_access_token(user_id=user_id, username=f"u{user_id}", role=role)


def test_audit_endpoint_is_admin_only(test_settings, session_factory, anyio_backend):
    async def seed():
        async with session_factory() as session:
            repo = Repository(session)
            admin = await repo.create_user("admin", "hash", "admin")
            viewer = await repo.create_user("viewer", "hash", "viewer")
            await repo.create_audit_log(admin.id, "switch.created", "switch", 7, "127.0.0.1", {"name": "sw01"})
            await session.commit()
            return admin.id, viewer.id

    import anyio
    admin_id, viewer_id = anyio.run(seed)
    client = TestClient(create_app(Runtime.for_tests(test_settings, session_factory=session_factory)))

    viewer = client.get("/api/v1/audit", headers={"Authorization": f"Bearer {_token(test_settings, viewer_id, 'viewer')}"})
    assert viewer.status_code == 403

    admin = client.get("/api/v1/audit", headers={"Authorization": f"Bearer {_token(test_settings, admin_id, 'admin')}"})
    assert admin.status_code == 200
    assert admin.json()[0]["action"] == "switch.created"
```

- [ ] **Step 2: Run failing test**

```powershell
rtk python -m pytest app_v4/tests/test_audit_api.py -v
```

Expected: fail because `/api/v1/audit` is missing.

- [ ] **Step 3: Add audit router**

Create `app_v4/service/api/audit.py`:

```python
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app_v4.data.repository import Repository
from app_v4.service.deps import get_session, require_role

router = APIRouter(tags=["audit"])


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None
    action: str
    target_type: str | None
    target_id: int | None
    ip: str | None
    ts: datetime
    detail_json: dict[str, Any] | None


@router.get("/audit", response_model=list[AuditOut])
async def list_audit(
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
    _user=Depends(require_role("admin")),
):
    repo = Repository(session)
    rows = await repo.list_audit(limit=limit)
    return [AuditOut.model_validate(row) for row in rows]
```

Register in `app_v4/service/app.py`:

```python
from app_v4.service.api import audit, auth, backups, credentials, jobs, switches, system, users, ws
...
app.include_router(audit.router, prefix="/api/v1")
```

- [ ] **Step 4: Add mutation audit coverage**

Add `AuditWriter` calls in:
- `app_v4/service/api/auth.py`: `auth.login_success`, `auth.login_failed`, `auth.refresh`, `auth.logout`.
- `app_v4/service/api/jobs.py`: `job.created`, `job.updated`, `job.deleted`.
- `app_v4/service/api/backups.py`: `backup.manual_triggered`.

Use existing pattern from `app_v4/service/api/switches.py` and `app_v4/service/audit.py`.

- [ ] **Step 5: Run audit tests**

```powershell
rtk python -m pytest app_v4/tests/test_audit_api.py app_v4/tests/test_auth_api.py app_v4/tests/test_jobs_api.py app_v4/tests/test_backups_api.py -v
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
rtk git add app_v4/service/api/audit.py app_v4/service/api/auth.py app_v4/service/api/jobs.py app_v4/service/api/backups.py app_v4/service/app.py app_v4/tests/test_audit_api.py
rtk git commit -m "feat: add v4 audit API and coverage"
```

### Task 3: WebSocket Lifecycle Events

**Files:**
- Modify: `app_v4/service/events.py`
- Modify: `app_v4/service/runtime.py`
- Modify: `app_v4/service/backup_service.py`
- Modify: `app_v4/service/scheduler.py`
- Modify: `app_v4/service/api/backups.py`
- Test: `app_v4/tests/test_events_integration.py`

- [ ] **Step 1: Write failing event tests**

Create `app_v4/tests/test_events_integration.py`:

```python
from dataclasses import dataclass

import pytest

from app_v4.data.repository import Repository
from app_v4.net.runner import BackupRunResult
from app_v4.service.backup_service import BackupService
from app_v4.service.diff_service import DiffService
from app_v4.service.events import EventHub


@dataclass
class FakeRunner:
    result: BackupRunResult

    async def execute_backup(self, protocol, host, port, username, password, enable_password=""):
        return self.result


class RecordingHub(EventHub):
    def __init__(self):
        super().__init__()
        self.events = []

    async def broadcast(self, event):
        self.events.append(event)


@pytest.mark.asyncio
async def test_backup_service_broadcasts_lifecycle_events(test_settings, session_factory, crypto_service):
    hub = RecordingHub()
    service = BackupService(
        settings=test_settings,
        session_factory=session_factory,
        crypto_service=crypto_service,
        runner=FakeRunner(BackupRunResult(True, "hostname sw01", "Backup completed successfully")),
        diff_service=DiffService(test_settings),
        event_hub=hub,
    )
    async with session_factory() as session:
        repo = Repository(session)
        blob = crypto_service.encrypt_credential("admin", "secret", "")
        cred = await repo.create_credential("cred", blob)
        switch = await repo.create_switch("sw01", "10.0.0.1", "ssh", 22, cred.id)
        await session.commit()
        switch_id = switch.id

    await service.execute_backup(switch_id=switch_id, backup_type="manual", triggered_by_user_id=None)

    assert [event.type for event in hub.events] == ["backup_started", "backup_completed"]
    assert hub.events[0].payload["switch_id"] == switch_id
```

- [ ] **Step 2: Run failing test**

```powershell
rtk python -m pytest app_v4/tests/test_events_integration.py -v
```

Expected: fail because `BackupService` does not accept/broadcast `event_hub`.

- [ ] **Step 3: Add event helper functions**

In `app_v4/service/events.py`, add:

```python
async def publish(hub: EventHub | None, event_type: str, payload: dict) -> None:
    if hub is None:
        return
    await hub.broadcast(EventMessage.create(event_type, payload))
```

- [ ] **Step 4: Wire backup events**

In `BackupService.__init__`, add:

```python
event_hub: EventHub | None = None,
...
self.event_hub = event_hub
```

In `execute_backup`, publish before runner call:

```python
await publish(self.event_hub, "backup_started", {"switch_id": switch.id, "switch_name": switch.name, "backup_type": backup_type})
```

On success:

```python
await publish(self.event_hub, "backup_completed", {"switch_id": switch.id, "switch_name": switch.name, "backup_id": backup.id})
```

On failure:

```python
await publish(self.event_hub, "backup_failed", {"switch_id": switch.id, "switch_name": switch.name, "message": run.message})
```

- [ ] **Step 5: Wire scheduler event**

In `SchedulerService.execute_scheduled_backup`, publish before backup:

```python
await publish(self.event_hub, "job_triggered", {"job_id": job_id, "switch_id": switch_id})
```

- [ ] **Step 6: Wire runtime**

In `build_runtime(...)`, pass `event_hub` to `BackupService` and `SchedulerService`.

- [ ] **Step 7: Run event tests**

```powershell
rtk python -m pytest app_v4/tests/test_events_integration.py app_v4/tests/test_backup_service.py app_v4/tests/test_scheduler.py app_v4/tests/test_websocket.py -v
```

Expected: pass.

- [ ] **Step 8: Commit**

```powershell
rtk git add app_v4/service/events.py app_v4/service/runtime.py app_v4/service/backup_service.py app_v4/service/scheduler.py app_v4/tests/test_events_integration.py
rtk git commit -m "feat: broadcast v4 backup and scheduler events"
```

### Task 4: Retention Service

**Files:**
- Create: `app_v4/service/retention_service.py`
- Modify: `app_v4/core/config.py`
- Modify: `app_v4/data/repository.py`
- Modify: `app_v4/service/runtime.py`
- Modify: `app_v4/service/scheduler.py`
- Test: `app_v4/tests/test_retention_service.py`

- [ ] **Step 1: Write failing retention tests**

Create `app_v4/tests/test_retention_service.py`:

```python
from datetime import datetime, timedelta

import pytest

from app_v4.data.models import AuditLog, Backup
from app_v4.data.repository import Repository
from app_v4.service.retention_service import RetentionService


@pytest.mark.asyncio
async def test_retention_removes_old_audit_rows(test_settings, session_factory):
    async with session_factory() as session:
        session.add(AuditLog(user_id=None, action="old", ts=datetime.utcnow() - timedelta(days=100)))
        session.add(AuditLog(user_id=None, action="new", ts=datetime.utcnow()))
        await session.commit()

    service = RetentionService(test_settings, session_factory)
    deleted = await service.trim_audit()

    assert deleted == 1
    async with session_factory() as session:
        rows = await Repository(session).list_audit(limit=10)
    assert [row.action for row in rows] == ["new"]
```

- [ ] **Step 2: Run failing test**

```powershell
rtk python -m pytest app_v4/tests/test_retention_service.py -v
```

Expected: fail because service missing.

- [ ] **Step 3: Add config**

In `app_v4/core/config.py`:

```python
audit_retention_days: int = 90
retention_hour: int = 3
retention_minute: int = 0
```

- [ ] **Step 4: Add repository delete helpers**

In `app_v4/data/repository.py`:

```python
async def delete_audit_older_than(self, cutoff: datetime) -> int:
    result = await self.session.execute(delete(AuditLog).where(AuditLog.ts < cutoff))
    return int(result.rowcount or 0)
```

Add the needed import:

```python
from sqlalchemy import delete
```

- [ ] **Step 5: Create retention service**

Create `app_v4/service/retention_service.py`:

```python
from __future__ import annotations

from datetime import datetime, timedelta

from app_v4.core.config import Settings
from app_v4.data.repository import Repository


class RetentionService:
    def __init__(self, settings: Settings, session_factory):
        self.settings = settings
        self.session_factory = session_factory

    async def trim_audit(self) -> int:
        cutoff = datetime.utcnow() - timedelta(days=self.settings.audit_retention_days)
        async with self.session_factory() as session:
            repo = Repository(session)
            deleted = await repo.delete_audit_older_than(cutoff)
            await session.commit()
            return deleted

    async def run_once(self) -> dict[str, int]:
        return {"audit_deleted": await self.trim_audit()}
```

- [ ] **Step 6: Schedule retention nightly**

In `SchedulerService.start`, add cron job after scheduler start:

```python
self.scheduler.add_job(
    self.retention_service.run_once,
    CronTrigger(hour=self.settings.retention_hour, minute=self.settings.retention_minute),
    id="retention-nightly",
    replace_existing=True,
)
```

- [ ] **Step 7: Run retention tests**

```powershell
rtk python -m pytest app_v4/tests/test_retention_service.py app_v4/tests/test_scheduler.py -v
```

Expected: pass.

- [ ] **Step 8: Commit**

```powershell
rtk git add app_v4/core/config.py app_v4/data/repository.py app_v4/service/retention_service.py app_v4/service/runtime.py app_v4/service/scheduler.py app_v4/tests/test_retention_service.py
rtk git commit -m "feat: add v4 retention service"
```

### Task 5: Problem Details, Static Serving, and Graceful Shutdown

**Files:**
- Create: `app_v4/service/problem_handlers.py`
- Modify: `app_v4/service/problem.py`
- Modify: `app_v4/service/app.py`
- Modify: `app_v4/service/runtime.py`
- Modify: `app_v4/service/api/system.py`
- Modify: `app_v4/core/paths.py`
- Test: `app_v4/tests/test_problem_details.py`
- Test: `app_v4/tests/test_static_serving.py`

- [ ] **Step 1: Write failing tests**

Create `app_v4/tests/test_problem_details.py`:

```python
from fastapi.testclient import TestClient

from app_v4.service.app import create_app
from app_v4.service.runtime import Runtime


def test_problem_details_media_type_for_http_errors(test_settings, session_factory):
    client = TestClient(create_app(Runtime.for_tests(test_settings, session_factory=session_factory)))
    response = client.get("/api/v1/system/status")
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["status"] == 401
```

Create `app_v4/tests/test_static_serving.py`:

```python
from pathlib import Path

from fastapi.testclient import TestClient

from app_v4.service.app import create_app
from app_v4.service.runtime import Runtime


def test_static_index_fallback(test_settings, session_factory):
    static_dir = Path(test_settings.base_dir) / "service" / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    (static_dir / "index.html").write_text("<div id='root'></div>", encoding="utf-8")

    client = TestClient(create_app(Runtime.for_tests(test_settings, session_factory=session_factory)))
    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "root" in response.text
```

- [ ] **Step 2: Run failing tests**

```powershell
rtk python -m pytest app_v4/tests/test_problem_details.py app_v4/tests/test_static_serving.py -v
```

Expected: fail because handlers/static fallback are missing.

- [ ] **Step 3: Add problem handler**

Create `app_v4/service/problem_handlers.py`:

```python
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def _body(status: int, title: str, detail: str, type_: str = "about:blank") -> dict:
    return {"type": type_, "title": title, "status": status, "detail": detail}


def register_problem_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        detail = exc.detail
        if isinstance(detail, dict) and {"type", "title", "status", "detail"}.issubset(detail):
            body = detail
        else:
            body = _body(exc.status_code, exc.__class__.__name__, str(detail))
        return JSONResponse(body, status_code=exc.status_code, media_type="application/problem+json")

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            _body(422, "Validation Error", str(exc), "validation_error"),
            status_code=422,
            media_type="application/problem+json",
        )
```

- [ ] **Step 4: Add static mount and fallback**

In `app_v4/service/app.py`:

```python
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app_v4.core.paths import resolve_paths
from app_v4.service.problem_handlers import register_problem_handlers
...
register_problem_handlers(app)
paths = resolve_paths(runtime.settings)
if paths.static_dir.exists():
    app.mount("/assets", StaticFiles(directory=paths.static_dir / "assets"), name="assets")

@app.get("/{full_path:path}", include_in_schema=False)
async def web_fallback(full_path: str):
    index = paths.static_dir / "index.html"
    if index.exists() and not full_path.startswith("api/") and full_path != "ws":
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="Not Found")
```

- [ ] **Step 5: Add runtime shutdown and status fields**

In `Runtime`, add:

```python
started_at: datetime = field(default_factory=datetime.utcnow)

async def shutdown(self) -> None:
    if self.scheduler_service is not None:
        await self.scheduler_service.stop()
```

In `create_app`, use lifespan:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await runtime.shutdown()
```

In `system.py`, include:

```python
"uptime_seconds": int((datetime.utcnow() - runtime.started_at).total_seconds()),
"scheduler_running": runtime.scheduler_service.is_running if runtime.scheduler_service else False,
"db_size_bytes": paths.database_file.stat().st_size if paths.database_file.exists() else 0,
```

- [ ] **Step 6: Run tests**

```powershell
rtk python -m pytest app_v4/tests/test_problem_details.py app_v4/tests/test_static_serving.py app_v4/tests/test_system_api.py app_v4/tests/test_app_factory.py -v
```

Expected: pass.

- [ ] **Step 7: Commit**

```powershell
rtk git add app_v4/service/problem_handlers.py app_v4/service/problem.py app_v4/service/app.py app_v4/service/runtime.py app_v4/service/api/system.py app_v4/core/paths.py app_v4/tests/test_problem_details.py app_v4/tests/test_static_serving.py
rtk git commit -m "feat: add v4 problem details and static serving"
```

### Task 6: DPAPI Fatal Handling and Backup Failure Categories

**Files:**
- Modify: `app_v4/core/dpapi.py`
- Modify: `app_v4/core/key_envelope.py`
- Modify: `app_v4/net/runner.py`
- Modify: `app_v4/service/backup_service.py`
- Test: `app_v4/tests/test_key_envelope.py`
- Test: `app_v4/tests/test_backup_runner.py`

- [ ] **Step 1: Write failing tests**

Add to `app_v4/tests/test_key_envelope.py`:

```python
def test_key_envelope_raises_master_key_unavailable_on_dpapi_failure(tmp_path):
    class BrokenProvider:
        name = "dpapi-current-user"
        def protect(self, plaintext: bytes) -> bytes:
            return b"bad"
        def unprotect(self, ciphertext: bytes) -> bytes:
            raise RuntimeError("dpapi failed")

    store = KeyEnvelopeStore(tmp_path / "master.dpapi", BrokenProvider())
    (tmp_path / "master.dpapi").write_bytes(b"bad")

    with pytest.raises(MasterKeyUnavailableError) as exc:
        store.load()
    assert "MASTER_KEY_UNAVAILABLE" in str(exc.value)
```

Add to `app_v4/tests/test_backup_runner.py`:

```python
@pytest.mark.asyncio
async def test_backup_runner_categorizes_authentication_error():
    class AuthFailClient(FakeClient):
        async def connect(self):
            raise PermissionError("authentication failed")

    runner = BackupRunner(settings=Settings(network_max_retries=1), client_factory=lambda **kwargs: AuthFailClient(""))
    result = await runner.execute_backup("ssh", "host", 22, "u", "p")

    assert result.success is False
    assert result.error_code == "AUTHENTICATION_ERROR"
```

- [ ] **Step 2: Run failing tests**

```powershell
rtk python -m pytest app_v4/tests/test_key_envelope.py app_v4/tests/test_backup_runner.py -v
```

Expected: fail because exception type and `error_code` do not exist.

- [ ] **Step 3: Add master key exception and DPAPI flag**

In `app_v4/core/key_envelope.py`:

```python
class MasterKeyUnavailableError(RuntimeError):
    pass
```

Wrap load failures:

```python
except Exception as exc:
    raise MasterKeyUnavailableError("MASTER_KEY_UNAVAILABLE: unable to decrypt master key envelope") from exc
```

In `app_v4/core/dpapi.py`, use:

```python
CRYPTPROTECT_UI_FORBIDDEN = 0x1
```

Pass that flag to both DPAPI calls.

- [ ] **Step 4: Add failure categories**

Change `BackupRunResult` in `app_v4/net/runner.py`:

```python
@dataclass(frozen=True)
class BackupRunResult:
    success: bool
    config_text: str
    message: str
    error_code: str | None = None
```

Add categorizer:

```python
def _categorize_error(self, exc: Exception) -> str:
    text = str(exc).lower()
    if isinstance(exc, TimeoutError) or "timeout" in text:
        return "CONNECTION_TIMEOUT"
    if isinstance(exc, PermissionError) or "auth" in text or "password" in text:
        return "AUTHENTICATION_ERROR"
    if "prompt" in text:
        return "PROMPT_NOT_DETECTED"
    return "UNKNOWN"
```

Return failures with category:

```python
last_code = self._categorize_error(exc)
...
return BackupRunResult(False, "", f"Backup failed after {self.config.max_retries} attempts: {last_error}", last_code)
```

Update unsupported protocol return:

```python
return BackupRunResult(False, "", f"Unsupported protocol: {protocol}", "UNKNOWN")
```

- [ ] **Step 5: Run tests**

```powershell
rtk python -m pytest app_v4/tests/test_key_envelope.py app_v4/tests/test_backup_runner.py app_v4/tests/test_backup_service.py -v
```

Expected: pass.

- [ ] **Step 6: Full backend verification**

```powershell
rtk python -m pytest app_v4/tests -v
```

Expected: pass.

- [ ] **Step 7: Commit**

```powershell
rtk git add app_v4/core/dpapi.py app_v4/core/key_envelope.py app_v4/net/runner.py app_v4/service/backup_service.py app_v4/tests/test_key_envelope.py app_v4/tests/test_backup_runner.py
rtk git commit -m "feat: add v4 fatal key and backup error codes"
```
