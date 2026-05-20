# NCM v4 Backend Execution Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add working v4 backup execution for SSH/Telnet switches, backup/history APIs, jobs CRUD, and APScheduler-backed runtime scheduling.

**Architecture:** Keep `app/` untouched. Add v4-native service modules for network settings, SSH/Telnet clients, backup runner, backup persistence, diff generation, and scheduler lifecycle. API endpoints call services through `ServiceRuntime`; tests avoid real network by injecting fake runners and using temp file storage.

**Tech Stack:** FastAPI, async SQLAlchemy 2, asyncssh, telnetlib3, APScheduler AsyncIOScheduler, pytest-asyncio, httpx/TestClient. All terminal commands must use `rtk`.

---

## File Structure

Create:

```text
app_v4/core/network_config.py
app_v4/net/__init__.py
app_v4/net/ssh_client.py
app_v4/net/telnet_client.py
app_v4/net/runner.py
app_v4/service/diff_service.py
app_v4/service/backup_service.py
app_v4/service/scheduler.py
app_v4/service/api/backups.py
app_v4/service/api/jobs.py
app_v4/tests/test_network_config.py
app_v4/tests/test_diff_service.py
app_v4/tests/test_backup_service.py
app_v4/tests/test_backups_api.py
app_v4/tests/test_jobs_api.py
app_v4/tests/test_scheduler.py
```

Modify:

```text
app_v4/requirements-v4.txt
app_v4/core/config.py
app_v4/core/paths.py
app_v4/data/repository.py
app_v4/service/runtime.py
app_v4/service/app.py
app_v4/tests/conftest.py
```

Do not modify `app/`.

---

## Task 1: Add Phase 1 dependencies

**Files:**
- Modify: `app_v4/requirements-v4.txt`

- [ ] **Step 1: Update requirements**

Append these lines to `app_v4/requirements-v4.txt` if missing:

```text
asyncssh>=2.14.2
telnetlib3>=2.0.4
apscheduler>=3.10.4
```

- [ ] **Step 2: Install requirements**

```bash
rtk python -m pip install -r app_v4/requirements-v4.txt
```

Expected: install succeeds.

- [ ] **Step 3: Verify imports**

```bash
rtk python -c "import asyncssh, telnetlib3, apscheduler; print('ok')"
```

Expected:

```text
ok
```

- [ ] **Step 4: Commit**

```bash
rtk git add app_v4/requirements-v4.txt
rtk git commit -m "chore: add v4 execution dependencies"
```

---

## Task 2: Add network and backup settings

**Files:**
- Modify: `app_v4/core/config.py`
- Modify: `app_v4/core/paths.py`
- Create: `app_v4/core/network_config.py`
- Test: `app_v4/tests/test_network_config.py`

- [ ] **Step 1: Write failing tests**

Create `app_v4/tests/test_network_config.py`:

```python
from pathlib import Path

from app_v4.core.config import Settings
from app_v4.core.network_config import NetworkConfig, load_network_config
from app_v4.core.paths import resolve_paths


def test_settings_include_backup_and_network_defaults(tmp_path: Path):
    settings = Settings(base_dir=tmp_path)

    assert settings.backup_min_keep == 1
    assert settings.backup_retention_days == 365
    assert settings.network_max_retries == 3
    assert settings.network_connect_timeout == 15
    assert settings.network_retry_delay == 2
    assert settings.network_backoff_multiplier == 2


def test_resolve_paths_includes_scheduler_lock(tmp_path: Path):
    settings = Settings(base_dir=tmp_path)
    paths = resolve_paths(settings)

    assert paths.scheduler_lock_file == tmp_path / "data" / "scheduler.lock"


def test_load_network_config_from_settings(tmp_path: Path):
    settings = Settings(base_dir=tmp_path, network_max_retries=5)
    config = load_network_config(settings)

    assert isinstance(config, NetworkConfig)
    assert config.max_retries == 5
    assert "terminal length 0" in config.paging_disable_commands
    assert "--More--" in config.paging_indicators
    assert "#" in config.prompts
```

- [ ] **Step 2: Run tests to verify failure**

```bash
rtk python -m pytest app_v4/tests/test_network_config.py -v
```

Expected: FAIL with missing `app_v4.core.network_config` or missing settings fields.

- [ ] **Step 3: Replace `app_v4/core/config.py`**

```python
from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NCM_V4_", extra="ignore")

    base_dir: Path = Field(default_factory=lambda: Path.cwd())
    service_host: str = "127.0.0.1"
    service_port: int = 8443
    jwt_access_minutes: int = 15
    jwt_refresh_days: int = 7
    scheduler_lock_seconds: int = 180

    backup_min_keep: int = 1
    backup_retention_days: int = 365
    backup_root_folder: str = "backups"
    diff_context_lines: int = 3

    network_max_retries: int = 3
    network_retry_delay: int = 2
    network_backoff_multiplier: int = 2
    network_connect_timeout: int = 15
    network_command_timeout: int = 60
    network_read_timeout: int = 30

    @property
    def database_url(self) -> str:
        db_path = self.base_dir / "data" / "app.db"
        return f"sqlite+aiosqlite:///{db_path.as_posix()}"

    @property
    def service_url(self) -> str:
        return f"https://{self.service_host}:{self.service_port}"
```

- [ ] **Step 4: Replace `app_v4/core/paths.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app_v4.core.config import Settings


@dataclass(frozen=True)
class AppPaths:
    base_dir: Path
    data_dir: Path
    logs_dir: Path
    backups_dir: Path
    static_dir: Path
    master_envelope_file: Path
    master_key_file: Path
    scheduler_lock_file: Path


def resolve_paths(settings: Settings) -> AppPaths:
    base_dir = settings.base_dir
    backup_root = Path(settings.backup_root_folder)
    backups_dir = backup_root if backup_root.is_absolute() else base_dir / backup_root
    return AppPaths(
        base_dir=base_dir,
        data_dir=base_dir / "data",
        logs_dir=base_dir / "logs",
        backups_dir=backups_dir,
        static_dir=base_dir / "app_v4" / "service" / "static",
        master_envelope_file=base_dir / "data" / "master.dpapi",
        master_key_file=base_dir / "data" / "master.key",
        scheduler_lock_file=base_dir / "data" / "scheduler.lock",
    )
```

- [ ] **Step 5: Create `app_v4/core/network_config.py`**

```python
from __future__ import annotations

from dataclasses import dataclass, field

from app_v4.core.config import Settings


@dataclass(frozen=True)
class NetworkConfig:
    max_retries: int
    retry_delay: int
    backoff_multiplier: int
    connect_timeout: int
    command_timeout: int
    read_timeout: int
    prompts: list[str] = field(default_factory=list)
    paging_disable_commands: list[str] = field(default_factory=list)
    paging_indicators: list[str] = field(default_factory=list)


def load_network_config(settings: Settings) -> NetworkConfig:
    return NetworkConfig(
        max_retries=settings.network_max_retries,
        retry_delay=settings.network_retry_delay,
        backoff_multiplier=settings.network_backoff_multiplier,
        connect_timeout=settings.network_connect_timeout,
        command_timeout=settings.network_command_timeout,
        read_timeout=settings.network_read_timeout,
        prompts=["#", ">", "(config)#", "(config-if)#"],
        paging_disable_commands=[
            "terminal length 0",
            "set length 0",
            "terminal pager 0",
        ],
        paging_indicators=[
            "--More--",
            "-- More --",
            "<--- More --->",
            "More: <space>",
            "More:",
            "Quit: q",
        ],
    )
```

- [ ] **Step 6: Run tests**

```bash
rtk python -m pytest app_v4/tests/test_network_config.py app_v4/tests/test_config_paths.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
rtk git add app_v4/core/config.py app_v4/core/paths.py app_v4/core/network_config.py app_v4/tests/test_network_config.py
rtk git commit -m "feat: add v4 network and backup settings"
```

---

## Task 3: Extend repository for backups and jobs

**Files:**
- Modify: `app_v4/data/repository.py`
- Test: `app_v4/tests/test_repository.py`

- [ ] **Step 1: Append failing tests**

Append to `app_v4/tests/test_repository.py`:

```python

@pytest.mark.asyncio
async def test_backup_repository_methods(session_factory):
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential("cred", b"x")
        switch = await repo.create_switch("sw", "10.0.0.1", "ssh", 22, cred.id)
        backup = await repo.create_backup(
            switch_id=switch.id,
            file_path="backups/sw/2026-05-19/config.txt",
            content_hash="abc",
            size_bytes=3,
            success=True,
            message="ok",
            backup_type="manual",
            triggered_by_user_id=None,
        )
        await session.commit()
        backup_id = backup.id

    async with session_factory() as session:
        repo = Repository(session)
        loaded = await repo.get_backup(backup_id)
        backups = await repo.list_backups(switch_id=loaded.switch_id, limit=10)
        latest = await repo.get_latest_backup(loaded.switch_id)

    assert loaded is not None
    assert loaded.content_hash == "abc"
    assert [b.id for b in backups] == [backup_id]
    assert latest.id == backup_id


@pytest.mark.asyncio
async def test_job_repository_methods(session_factory):
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential("cred", b"x")
        switch = await repo.create_switch("sw", "10.0.0.1", "ssh", 22, cred.id)
        job = await repo.create_job(
            switch_id=switch.id,
            interval_minutes=60,
            enabled=True,
            schedule_hour=8,
            schedule_minute=30,
        )
        await session.commit()
        job_id = job.id

    async with session_factory() as session:
        repo = Repository(session)
        loaded = await repo.get_job(job_id)
        jobs = await repo.list_jobs(enabled_only=True)
        await repo.update_job(job_id, interval_minutes=120, enabled=False)
        await session.commit()

    assert loaded is not None
    assert loaded.switch.name == "sw"
    assert [j.id for j in jobs] == [job_id]

    async with session_factory() as session:
        repo = Repository(session)
        updated = await repo.get_job(job_id)
        assert updated.interval_minutes == 120
        assert updated.enabled is False
        assert await repo.delete_job(job_id) is True
        await session.commit()
```

- [ ] **Step 2: Run tests to verify failure**

```bash
rtk python -m pytest app_v4/tests/test_repository.py -v
```

Expected: FAIL with missing backup/job repository methods.

- [ ] **Step 3: Add backup/job methods to `Repository` before `system_metrics`**

Edit `app_v4/data/repository.py`, adding this block above `# ----- system -----`:

```python
    # ----- backups -----

    async def create_backup(
        self,
        switch_id: int,
        file_path: str,
        content_hash: str,
        size_bytes: int,
        success: bool,
        message: str | None = None,
        backup_type: str = "manual",
        job_id: int | None = None,
        triggered_by_user_id: int | None = None,
    ) -> Backup:
        backup = Backup(
            switch_id=switch_id,
            file_path=file_path,
            content_hash=content_hash,
            size_bytes=size_bytes,
            success=success,
            message=message,
            backup_type=backup_type,
            job_id=job_id,
            triggered_by_user_id=triggered_by_user_id,
        )
        self.session.add(backup)
        await self.session.flush()
        return backup

    async def get_backup(self, backup_id: int) -> Backup | None:
        return await self.session.get(Backup, backup_id)

    async def list_backups(
        self,
        switch_id: int | None = None,
        limit: int | None = None,
    ) -> list[Backup]:
        stmt = select(Backup).order_by(Backup.taken_at.desc())
        if switch_id is not None:
            stmt = stmt.where(Backup.switch_id == switch_id)
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_backup(self, switch_id: int) -> Backup | None:
        result = await self.session.execute(
            select(Backup)
            .where(Backup.switch_id == switch_id, Backup.success.is_(True))
            .order_by(Backup.taken_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def delete_backup(self, backup_id: int) -> bool:
        backup = await self.get_backup(backup_id)
        if backup is None:
            return False
        await self.session.delete(backup)
        return True

    # ----- jobs -----

    async def create_job(
        self,
        switch_id: int,
        interval_minutes: int,
        enabled: bool = True,
        schedule_hour: int = 8,
        schedule_minute: int = 0,
    ) -> Job:
        job = Job(
            switch_id=switch_id,
            interval_minutes=interval_minutes,
            enabled=enabled,
            schedule_hour=schedule_hour,
            schedule_minute=schedule_minute,
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def get_job(self, job_id: int) -> Job | None:
        result = await self.session.execute(
            select(Job).options(selectinload(Job.switch)).where(Job.id == job_id)
        )
        return result.scalar_one_or_none()

    async def list_jobs(self, enabled_only: bool = False) -> list[Job]:
        stmt = select(Job).options(selectinload(Job.switch)).order_by(Job.id)
        if enabled_only:
            stmt = stmt.where(Job.enabled.is_(True))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_job(self, job_id: int, **kwargs) -> Job | None:
        job = await self.get_job(job_id)
        if job is None:
            return None
        for key, value in kwargs.items():
            if value is not None and hasattr(job, key):
                setattr(job, key, value)
        job.updated_at = datetime.utcnow()
        return job

    async def delete_job(self, job_id: int) -> bool:
        job = await self.get_job(job_id)
        if job is None:
            return False
        await self.session.delete(job)
        return True
```

- [ ] **Step 4: Run repository tests**

```bash
rtk python -m pytest app_v4/tests/test_repository.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add -f app_v4/data/repository.py app_v4/tests/test_repository.py
rtk git commit -m "feat: add v4 backup and job repository methods"
```

---

## Task 4: Add DiffService

**Files:**
- Create: `app_v4/service/diff_service.py`
- Test: `app_v4/tests/test_diff_service.py`

- [ ] **Step 1: Write failing tests**

Create `app_v4/tests/test_diff_service.py`:

```python
from app_v4.core.config import Settings
from app_v4.service.diff_service import DiffService


def test_unified_diff_reports_changes():
    service = DiffService(Settings(diff_context_lines=1))

    diff = service.unified_diff("a\nb\nc\n", "a\nB\nc\n", label1="old", label2="new")

    assert "--- old" in diff
    assert "+++ new" in diff
    assert "-b" in diff
    assert "+B" in diff


def test_diff_stats_counts_replace_as_changed():
    service = DiffService(Settings())

    stats = service.get_diff_stats("a\nb\n", "a\nB\nc\n")

    assert stats == {
        "added_lines": 1,
        "removed_lines": 0,
        "changed_lines": 1,
        "total_changes": 2,
    }
```

- [ ] **Step 2: Run tests to verify failure**

```bash
rtk python -m pytest app_v4/tests/test_diff_service.py -v
```

Expected: FAIL with missing `app_v4.service.diff_service`.

- [ ] **Step 3: Create DiffService**

Create `app_v4/service/diff_service.py`:

```python
from __future__ import annotations

import difflib
from pathlib import Path

from app_v4.core.config import Settings


class DiffService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def unified_diff(self, text1: str, text2: str, label1: str = "Before", label2: str = "After") -> str:
        diff = difflib.unified_diff(
            text1.splitlines(keepends=True),
            text2.splitlines(keepends=True),
            fromfile=label1,
            tofile=label2,
            lineterm="",
            n=self.settings.diff_context_lines,
        )
        return "\n".join(diff)

    def get_diff_stats(self, text1: str, text2: str) -> dict[str, int]:
        matcher = difflib.SequenceMatcher(None, text1.splitlines(), text2.splitlines())
        added = 0
        removed = 0
        changed = 0
        for opcode, i1, i2, j1, j2 in matcher.get_opcodes():
            if opcode == "delete":
                removed += i2 - i1
            elif opcode == "insert":
                added += j2 - j1
            elif opcode == "replace":
                changed += max(i2 - i1, j2 - j1)
        return {
            "added_lines": added,
            "removed_lines": removed,
            "changed_lines": changed,
            "total_changes": added + removed + changed,
        }

    def export_diff(self, diff_text: str, file_path: Path) -> None:
        file_path.write_text(diff_text, encoding="utf-8")
```

- [ ] **Step 4: Run diff tests**

```bash
rtk python -m pytest app_v4/tests/test_diff_service.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add app_v4/service/diff_service.py app_v4/tests/test_diff_service.py
rtk git commit -m "feat: add v4 diff service"
```

---

## Task 5: Add SSH/Telnet clients and backup runner

**Files:**
- Create: `app_v4/net/__init__.py`
- Create: `app_v4/net/ssh_client.py`
- Create: `app_v4/net/telnet_client.py`
- Create: `app_v4/net/runner.py`
- Test: `app_v4/tests/test_backup_runner.py`

- [ ] **Step 1: Write tests using fake client factory**

Create `app_v4/tests/test_backup_runner.py`:

```python
import pytest

from app_v4.core.config import Settings
from app_v4.net.runner import BackupRunner, BackupRunResult


class FakeClient:
    def __init__(self, output: str):
        self.output = output
        self.disconnected = False

    async def connect(self):
        return True

    async def enter_enable_mode(self, prompts):
        return True

    async def disable_paging(self, commands):
        return True

    async def get_running_config(self, paging_indicators):
        return self.output

    async def disconnect(self):
        self.disconnected = True


@pytest.mark.asyncio
async def test_backup_runner_normalizes_success_output():
    runner = BackupRunner(
        settings=Settings(network_max_retries=1),
        client_factory=lambda **kwargs: FakeClient("\r\nline1   \r\nline2\r\n"),
    )

    result = await runner.execute_backup(
        protocol="ssh",
        host="10.0.0.1",
        port=22,
        username="admin",
        password="secret",
        enable_password="enable",
    )

    assert result == BackupRunResult(success=True, config_text="line1\nline2", message="Backup completed successfully")


@pytest.mark.asyncio
async def test_backup_runner_rejects_unsupported_protocol():
    runner = BackupRunner(settings=Settings(), client_factory=lambda **kwargs: FakeClient("x"))

    result = await runner.execute_backup("websmart", "host", 80, "u", "p")

    assert result.success is False
    assert "Unsupported protocol" in result.message


@pytest.mark.asyncio
async def test_backup_runner_returns_failure_after_retries():
    attempts = 0

    class FailingClient(FakeClient):
        async def connect(self):
            nonlocal attempts
            attempts += 1
            raise ConnectionError("boom")

    runner = BackupRunner(
        settings=Settings(network_max_retries=2, network_retry_delay=0),
        client_factory=lambda **kwargs: FailingClient(""),
    )

    result = await runner.execute_backup("ssh", "host", 22, "u", "p")

    assert attempts == 2
    assert result.success is False
    assert "boom" in result.message
```

- [ ] **Step 2: Run tests to verify failure**

```bash
rtk python -m pytest app_v4/tests/test_backup_runner.py -v
```

Expected: FAIL with missing `app_v4.net.runner`.

- [ ] **Step 3: Create net package and SSH client**

Create `app_v4/net/__init__.py`:

```python
"""Network clients for v4 backup execution."""
```

Create `app_v4/net/ssh_client.py`:

```python
from __future__ import annotations

import asyncio

import asyncssh


class AsyncSshClient:
    def __init__(self, host: str, port: int, username: str, password: str, enable_password: str = "", timeout: int = 15):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.enable_password = enable_password
        self.timeout = timeout
        self.conn: asyncssh.SSHClientConnection | None = None

    async def connect(self) -> bool:
        self.conn = await asyncio.wait_for(
            asyncssh.connect(
                self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                known_hosts=None,
            ),
            timeout=self.timeout,
        )
        return True

    async def enter_enable_mode(self, prompts: list[str]) -> bool:
        return True

    async def disable_paging(self, commands: list[str]) -> bool:
        if self.conn is None:
            raise RuntimeError("Not connected")
        for command in commands:
            await self.conn.run(command, check=False)
        return True

    async def get_running_config(self, paging_indicators: list[str]) -> str:
        if self.conn is None:
            raise RuntimeError("Not connected")
        result = await self.conn.run("show running-config", check=False)
        if result.exit_status not in (0, None):
            raise RuntimeError(result.stderr or f"show running-config failed with {result.exit_status}")
        return str(result.stdout)

    async def disconnect(self) -> None:
        if self.conn is not None:
            self.conn.close()
            await self.conn.wait_closed()
            self.conn = None
```

- [ ] **Step 4: Create Telnet client**

Create `app_v4/net/telnet_client.py`:

```python
from __future__ import annotations

import asyncio

import telnetlib3


class AsyncTelnetClient:
    def __init__(self, host: str, port: int, username: str, password: str, enable_password: str = "", timeout: int = 15):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.enable_password = enable_password
        self.timeout = timeout
        self.reader = None
        self.writer = None

    async def connect(self) -> bool:
        self.reader, self.writer = await asyncio.wait_for(
            telnetlib3.open_connection(self.host, self.port, connect_minwait=0.5),
            timeout=self.timeout,
        )
        await asyncio.sleep(0.2)
        await self._read_until(["login:", "username:"], timeout=5)
        self.writer.write(self.username + "\n")
        await self._read_until(["password:"], timeout=5)
        self.writer.write(self.password + "\n")
        response = await self._read_available(timeout=2)
        if "failed" in response.lower() or "incorrect" in response.lower():
            raise ConnectionError("Telnet authentication failed")
        return True

    async def enter_enable_mode(self, prompts: list[str]) -> bool:
        if self.enable_password:
            self.writer.write("enable\n")
            await asyncio.sleep(0.2)
            output = await self._read_available(timeout=2)
            if "password" in output.lower():
                self.writer.write(self.enable_password + "\n")
                await asyncio.sleep(0.2)
        return True

    async def disable_paging(self, commands: list[str]) -> bool:
        for command in commands:
            self.writer.write(command + "\n")
            await asyncio.sleep(0.1)
            await self._read_available(timeout=1)
        return True

    async def get_running_config(self, paging_indicators: list[str]) -> str:
        self.writer.write("show running-config\n")
        output = ""
        for _ in range(500):
            chunk = await self._read_available(timeout=1)
            output += chunk
            if any(indicator in chunk for indicator in paging_indicators):
                self.writer.write(" ")
                continue
            tail = output.splitlines()[-3:] if output else []
            if any((line.strip().endswith("#") or line.strip().endswith(">")) and len(line.strip()) < 50 for line in tail):
                break
            if not chunk and len(output) > 100:
                break
        return self._clean_output(output, paging_indicators)

    async def disconnect(self) -> None:
        if self.writer is not None:
            self.writer.close()

    async def _read_until(self, prompts: list[str], timeout: int) -> str:
        output = ""
        end = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < end:
            try:
                chunk = await asyncio.wait_for(self.reader.read(1024), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            output += chunk
            if any(prompt.lower() in output.lower() for prompt in prompts):
                return output
        return output

    async def _read_available(self, timeout: int) -> str:
        output = ""
        while True:
            try:
                chunk = await asyncio.wait_for(self.reader.read(4096), timeout=timeout)
            except asyncio.TimeoutError:
                break
            if not chunk:
                break
            output += chunk
            if len(chunk) < 4096:
                break
        return output

    def _clean_output(self, output: str, paging_indicators: list[str]) -> str:
        lines = []
        for line in output.split("\n"):
            stripped = line.strip()
            if stripped == "show running-config":
                continue
            if any(indicator in line for indicator in paging_indicators):
                continue
            if (stripped.endswith("#") or stripped.endswith(">")) and len(stripped) < 50:
                continue
            lines.append(line)
        return "\n".join(lines)
```

- [ ] **Step 5: Create runner**

Create `app_v4/net/runner.py`:

```python
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Callable, Protocol

from app_v4.core.config import Settings
from app_v4.core.network_config import load_network_config
from app_v4.net.ssh_client import AsyncSshClient
from app_v4.net.telnet_client import AsyncTelnetClient


class BackupClient(Protocol):
    async def connect(self) -> bool: ...
    async def enter_enable_mode(self, prompts: list[str]) -> bool: ...
    async def disable_paging(self, commands: list[str]) -> bool: ...
    async def get_running_config(self, paging_indicators: list[str]) -> str: ...
    async def disconnect(self) -> None: ...


@dataclass(frozen=True)
class BackupRunResult:
    success: bool
    config_text: str
    message: str


class BackupRunner:
    def __init__(self, settings: Settings, client_factory: Callable[..., BackupClient] | None = None):
        self.settings = settings
        self.config = load_network_config(settings)
        self.client_factory = client_factory

    async def execute_backup(
        self,
        protocol: str,
        host: str,
        port: int,
        username: str,
        password: str,
        enable_password: str = "",
    ) -> BackupRunResult:
        protocol = protocol.lower()
        if protocol not in {"ssh", "telnet"}:
            return BackupRunResult(False, "", f"Unsupported protocol in Phase 1: {protocol}")

        last_error = "Backup failed"
        for attempt in range(self.config.max_retries):
            if attempt > 0:
                delay = self.config.retry_delay * (self.config.backoff_multiplier ** (attempt - 1))
                await asyncio.sleep(delay)
            client = self._make_client(protocol, host, port, username, password, enable_password)
            try:
                await client.connect()
                await client.enter_enable_mode(self.config.prompts)
                await client.disable_paging(self.config.paging_disable_commands)
                config_text = await client.get_running_config(self.config.paging_indicators)
                config_text = self._normalize_output(config_text)
                if len(config_text) < 1:
                    raise ValueError("Retrieved configuration is empty")
                return BackupRunResult(True, config_text, "Backup completed successfully")
            except Exception as exc:
                last_error = str(exc)
            finally:
                try:
                    await client.disconnect()
                except Exception:
                    pass
        return BackupRunResult(False, "", f"Backup failed after {self.config.max_retries} attempts: {last_error}")

    def _make_client(self, protocol: str, host: str, port: int, username: str, password: str, enable_password: str) -> BackupClient:
        if self.client_factory is not None:
            return self.client_factory(
                protocol=protocol,
                host=host,
                port=port,
                username=username,
                password=password,
                enable_password=enable_password,
                timeout=self.config.connect_timeout,
            )
        if protocol == "ssh":
            return AsyncSshClient(host, port, username, password, enable_password, self.config.connect_timeout)
        return AsyncTelnetClient(host, port, username, password, enable_password, self.config.connect_timeout)

    def _normalize_output(self, text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = [line.rstrip() for line in text.split("\n")]
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        return "\n".join(lines)
```

- [ ] **Step 6: Run runner tests**

```bash
rtk python -m pytest app_v4/tests/test_backup_runner.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
rtk git add app_v4/net/__init__.py app_v4/net/ssh_client.py app_v4/net/telnet_client.py app_v4/net/runner.py app_v4/tests/test_backup_runner.py
rtk git commit -m "feat: add v4 SSH and Telnet backup runner"
```

---

## Task 6: Add BackupService

**Files:**
- Create: `app_v4/service/backup_service.py`
- Modify: `app_v4/service/runtime.py`
- Test: `app_v4/tests/test_backup_service.py`

- [ ] **Step 1: Write backup service tests**

Create `app_v4/tests/test_backup_service.py`:

```python
from dataclasses import dataclass
from pathlib import Path

import pytest

from app_v4.data.repository import Repository
from app_v4.net.runner import BackupRunResult
from app_v4.service.backup_service import BackupService
from app_v4.service.diff_service import DiffService


@dataclass
class FakeRunner:
    result: BackupRunResult

    async def execute_backup(self, protocol, host, port, username, password, enable_password=""):
        return self.result


@pytest.mark.asyncio
async def test_backup_service_creates_success_record_and_file(test_settings, session_factory, crypto_service):
    service = BackupService(
        settings=test_settings,
        session_factory=session_factory,
        crypto_service=crypto_service,
        runner=FakeRunner(BackupRunResult(True, "config text", "Backup completed successfully")),
        diff_service=DiffService(test_settings),
    )
    async with session_factory() as session:
        repo = Repository(session)
        blob = crypto_service.encrypt_credential("admin", "secret", "enable")
        cred = await repo.create_credential("cred", blob)
        switch = await repo.create_switch("sw01", "10.0.0.1", "ssh", 22, cred.id)
        await session.commit()
        switch_id = switch.id

    result = await service.execute_backup(switch_id=switch_id, backup_type="manual", triggered_by_user_id=None)

    assert result["success"] is True
    assert result["backup_id"]
    assert Path(result["file_path"]).exists()
    assert Path(result["file_path"]).read_text(encoding="utf-8") == "config text"


@pytest.mark.asyncio
async def test_backup_service_creates_failed_record(test_settings, session_factory, crypto_service):
    service = BackupService(
        settings=test_settings,
        session_factory=session_factory,
        crypto_service=crypto_service,
        runner=FakeRunner(BackupRunResult(False, "", "boom")),
        diff_service=DiffService(test_settings),
    )
    async with session_factory() as session:
        repo = Repository(session)
        blob = crypto_service.encrypt_credential("admin", "secret", "")
        cred = await repo.create_credential("cred", blob)
        switch = await repo.create_switch("sw01", "10.0.0.1", "ssh", 22, cred.id)
        await session.commit()
        switch_id = switch.id

    result = await service.execute_backup(switch_id=switch_id, backup_type="manual", triggered_by_user_id=None)

    assert result["success"] is False
    assert result["message"] == "boom"
    async with session_factory() as session:
        repo = Repository(session)
        backup = await repo.get_backup(result["backup_id"])
    assert backup.success is False
```

- [ ] **Step 2: Run tests to verify failure**

```bash
rtk python -m pytest app_v4/tests/test_backup_service.py -v
```

Expected: FAIL with missing `app_v4.service.backup_service`.

- [ ] **Step 3: Create BackupService**

Create `app_v4/service/backup_service.py`:

```python
from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app_v4.core.config import Settings
from app_v4.core.crypto_service import CryptoService
from app_v4.core.paths import resolve_paths
from app_v4.data.repository import Repository
from app_v4.net.runner import BackupRunner, BackupRunResult
from app_v4.service.diff_service import DiffService


class BackupService:
    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        crypto_service: CryptoService,
        runner: BackupRunner | None = None,
        diff_service: DiffService | None = None,
    ):
        self.settings = settings
        self.session_factory = session_factory
        self.crypto_service = crypto_service
        self.runner = runner or BackupRunner(settings)
        self.diff_service = diff_service or DiffService(settings)

    async def execute_backup(
        self,
        switch_id: int,
        backup_type: str = "manual",
        job_id: int | None = None,
        triggered_by_user_id: int | None = None,
    ) -> dict:
        async with self.session_factory() as session:
            repo = Repository(session)
            switch = await repo.get_switch(switch_id)
            if switch is None:
                raise ValueError(f"Switch ID {switch_id} not found")
            switch_name = switch.name
            protocol = switch.protocol
            host = switch.ip
            port = switch.port
            enc_blob = switch.credential.enc_blob

        credentials = self.crypto_service.decrypt_credential(enc_blob)
        run_result = await self.runner.execute_backup(
            protocol=protocol,
            host=host,
            port=port,
            username=credentials["username"],
            password=credentials["password"],
            enable_password=credentials.get("enable_password", ""),
        )

        if not run_result.success:
            return await self._record_failed_backup(
                switch_id=switch_id,
                message=run_result.message,
                backup_type=backup_type,
                job_id=job_id,
                triggered_by_user_id=triggered_by_user_id,
            )

        content_hash = hashlib.sha256(run_result.config_text.encode("utf-8")).hexdigest()
        changed = False
        diff_stats = None
        previous_text = None
        async with self.session_factory() as session:
            repo = Repository(session)
            previous = await repo.get_latest_backup(switch_id)
            if previous is not None:
                changed = previous.content_hash != content_hash
                if previous.file_path:
                    previous_path = Path(previous.file_path)
                    if previous_path.exists():
                        previous_text = previous_path.read_text(encoding="utf-8")

        file_path = self._save_config_file(switch_name, run_result.config_text, changed)
        if changed and previous_text is not None:
            diff_text = self.diff_service.unified_diff(previous_text, run_result.config_text, "Previous", "Current")
            diff_stats = self.diff_service.get_diff_stats(previous_text, run_result.config_text)
            self.diff_service.export_diff(diff_text, Path(str(file_path).rsplit(".txt", 1)[0] + ".diff"))

        if changed:
            if diff_stats:
                message = f"Perubahan konfigurasi terdeteksi: +{diff_stats['added_lines']}/-{diff_stats['removed_lines']}/~{diff_stats['changed_lines']} baris"
            else:
                message = "Perubahan konfigurasi terdeteksi"
        else:
            message = "Tidak ada perubahan konfigurasi"

        async with self.session_factory() as session:
            repo = Repository(session)
            backup = await repo.create_backup(
                switch_id=switch_id,
                file_path=str(file_path),
                content_hash=content_hash,
                size_bytes=len(run_result.config_text.encode("utf-8")),
                success=True,
                message=message,
                backup_type=backup_type,
                job_id=job_id,
                triggered_by_user_id=triggered_by_user_id,
            )
            await session.commit()
            backup_id = backup.id

        return {
            "success": True,
            "message": message,
            "file_path": str(file_path),
            "size_kb": len(run_result.config_text.encode("utf-8")) / 1024,
            "backup_id": backup_id,
        }

    async def _record_failed_backup(
        self,
        switch_id: int,
        message: str,
        backup_type: str,
        job_id: int | None,
        triggered_by_user_id: int | None,
    ) -> dict:
        async with self.session_factory() as session:
            repo = Repository(session)
            backup = await repo.create_backup(
                switch_id=switch_id,
                file_path="",
                content_hash="",
                size_bytes=0,
                success=False,
                message=message,
                backup_type=backup_type,
                job_id=job_id,
                triggered_by_user_id=triggered_by_user_id,
            )
            await session.commit()
            backup_id = backup.id
        return {"success": False, "message": message, "file_path": "", "size_kb": 0, "backup_id": backup_id}

    def _save_config_file(self, switch_name: str, config_text: str, changed: bool) -> Path:
        paths = resolve_paths(self.settings)
        now = datetime.now()
        backup_dir = paths.backups_dir / switch_name / now.strftime("%Y-%m-%d")
        backup_dir.mkdir(parents=True, exist_ok=True)
        suffix = " - update config" if changed else ""
        file_path = backup_dir / f"{now.strftime('%H%M%S')}_running-config{suffix}.txt"
        file_path.write_text(config_text, encoding="utf-8")
        return file_path

    def get_backup_content(self, file_path: str) -> str:
        return Path(file_path).read_text(encoding="utf-8")
```

- [ ] **Step 4: Update runtime to include BackupService**

Modify `app_v4/service/runtime.py`:

- Add import:

```python
from app_v4.service.backup_service import BackupService
```

- Add dataclass field:

```python
    backup_service: BackupService | None = None
```

- In `for_tests`, accept parameter and pass through:

```python
        backup_service: BackupService | None = None,
```

and:

```python
            backup_service=backup_service,
```

- In `build_runtime`, after crypto and session_factory creation, construct service:

```python
    backup_service = BackupService(settings, session_factory, crypto)
```

and pass:

```python
        backup_service=backup_service,
```

- [ ] **Step 5: Run backup service tests**

```bash
rtk python -m pytest app_v4/tests/test_backup_service.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
rtk git add app_v4/service/backup_service.py app_v4/service/runtime.py app_v4/tests/test_backup_service.py
rtk git commit -m "feat: add v4 backup execution service"
```

---

## Task 7: Add backups API

**Files:**
- Create: `app_v4/service/api/backups.py`
- Modify: `app_v4/service/app.py`
- Test: `app_v4/tests/test_backups_api.py`

- [ ] **Step 1: Write API tests**

Create `app_v4/tests/test_backups_api.py`:

```python
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


@pytest.mark.asyncio
async def test_trigger_backup_requires_operator(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(
        test_settings,
        session_factory,
        jwt_secret=b"b" * 32,
        backup_service=FakeBackupService({"success": True, "message": "ok", "backup_id": 9, "file_path": "", "size_kb": 1}),
    )
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
```

- [ ] **Step 2: Run tests to verify failure**

```bash
rtk python -m pytest app_v4/tests/test_backups_api.py -v
```

Expected: FAIL with 404.

- [ ] **Step 3: Create backups router**

Create `app_v4/service/api/backups.py`:

```python
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app_v4.core.auth_service import AccessClaims
from app_v4.data.repository import Repository
from app_v4.service.deps import get_db, get_runtime, require_role
from app_v4.service.problem import problem
from app_v4.service.runtime import ServiceRuntime

router = APIRouter(tags=["backups"])


class BackupOut(BaseModel):
    id: int
    switch_id: int
    file_path: str
    content_hash: str
    size_bytes: int
    success: bool
    message: str | None
    backup_type: str


class BackupRunResponse(BaseModel):
    success: bool
    message: str
    file_path: str
    size_kb: float
    backup_id: int


def _to_out(backup) -> BackupOut:
    return BackupOut(
        id=backup.id,
        switch_id=backup.switch_id,
        file_path=backup.file_path,
        content_hash=backup.content_hash,
        size_bytes=backup.size_bytes,
        success=backup.success,
        message=backup.message,
        backup_type=backup.backup_type,
    )


@router.post("/switches/{switch_id}/backups", response_model=BackupRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_backup(
    switch_id: int,
    runtime: ServiceRuntime = Depends(get_runtime),
    user: AccessClaims = Depends(require_role("admin", "operator")),
) -> BackupRunResponse:
    if runtime.backup_service is None:
        raise problem(503, "Service Unavailable", "Backup service is not initialized")
    result = await runtime.backup_service.execute_backup(
        switch_id=switch_id,
        backup_type="manual",
        triggered_by_user_id=user.user_id,
    )
    return BackupRunResponse(**result)


@router.get("/backups", response_model=list[BackupOut])
async def list_backups(
    switch_id: int | None = None,
    limit: int = 100,
    session: AsyncSession = Depends(get_db),
    _user: AccessClaims = Depends(require_role("admin", "operator", "viewer")),
) -> list[BackupOut]:
    repo = Repository(session)
    return [_to_out(b) for b in await repo.list_backups(switch_id=switch_id, limit=limit)]


@router.get("/backups/{backup_id}", response_model=BackupOut)
async def get_backup(
    backup_id: int,
    session: AsyncSession = Depends(get_db),
    _user: AccessClaims = Depends(require_role("admin", "operator", "viewer")),
) -> BackupOut:
    repo = Repository(session)
    backup = await repo.get_backup(backup_id)
    if backup is None:
        raise problem(404, "Not Found", "Backup not found")
    return _to_out(backup)


@router.get("/backups/{backup_id}/content")
async def get_backup_content(
    backup_id: int,
    session: AsyncSession = Depends(get_db),
    _user: AccessClaims = Depends(require_role("admin", "operator", "viewer")),
) -> Response:
    repo = Repository(session)
    backup = await repo.get_backup(backup_id)
    if backup is None:
        raise problem(404, "Not Found", "Backup not found")
    path = Path(backup.file_path)
    if not path.exists():
        raise problem(404, "Not Found", "Backup file not found")
    return Response(path.read_text(encoding="utf-8"), media_type="text/plain")


@router.get("/backups/{backup_id}/diff")
async def get_backup_diff(
    backup_id: int,
    session: AsyncSession = Depends(get_db),
    _user: AccessClaims = Depends(require_role("admin", "operator", "viewer")),
) -> Response:
    repo = Repository(session)
    backup = await repo.get_backup(backup_id)
    if backup is None:
        raise problem(404, "Not Found", "Backup not found")
    diff_path = Path(str(backup.file_path).rsplit(".txt", 1)[0] + ".diff")
    if not diff_path.exists():
        raise problem(404, "Not Found", "Diff file not found")
    return Response(diff_path.read_text(encoding="utf-8"), media_type="text/plain")
```

- [ ] **Step 4: Register router in `app_v4/service/app.py`**

Modify import line:

```python
    from app_v4.service.api import auth, backups, credentials, jobs, switches, system, users, ws
```

Add include before system:

```python
    app.include_router(backups.router, prefix="/api/v1")
    app.include_router(jobs.router, prefix="/api/v1")
```

Create temporary `app_v4/service/api/jobs.py` stub:

```python
from fastapi import APIRouter

router = APIRouter(prefix="/jobs", tags=["jobs"])
```

- [ ] **Step 5: Run backups API tests**

```bash
rtk python -m pytest app_v4/tests/test_backups_api.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
rtk git add app_v4/service/api/backups.py app_v4/service/api/jobs.py app_v4/service/app.py app_v4/tests/test_backups_api.py
rtk git commit -m "feat: add v4 backups API"
```

---

## Task 8: Add jobs CRUD API

**Files:**
- Modify: `app_v4/service/api/jobs.py`
- Test: `app_v4/tests/test_jobs_api.py`

- [ ] **Step 1: Write jobs API tests**

Create `app_v4/tests/test_jobs_api.py`:

```python
import pytest
from fastapi.testclient import TestClient

from app_v4.data.repository import Repository
from app_v4.service.app import create_app
from app_v4.service.runtime import ServiceRuntime


def _operator_token(runtime: ServiceRuntime) -> str:
    return runtime.auth_service.issue_access_token(1, "ops", "operator")


def _viewer_token(runtime: ServiceRuntime) -> str:
    return runtime.auth_service.issue_access_token(2, "viewer", "viewer")


@pytest.mark.asyncio
async def test_jobs_crud(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"j" * 32)
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential("cred", b"x")
        switch = await repo.create_switch("sw", "10.0.0.1", "ssh", 22, cred.id)
        await session.commit()
        switch_id = switch.id

    client = TestClient(create_app(runtime))
    create = client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {_operator_token(runtime)}"},
        json={"switch_id": switch_id, "interval_minutes": 60, "enabled": True, "schedule_hour": 8, "schedule_minute": 30},
    )
    assert create.status_code == 201
    job_id = create.json()["id"]

    list_response = client.get("/api/v1/jobs", headers={"Authorization": f"Bearer {_viewer_token(runtime)}"})
    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == job_id

    patch = client.patch(
        f"/api/v1/jobs/{job_id}",
        headers={"Authorization": f"Bearer {_operator_token(runtime)}"},
        json={"interval_minutes": 120, "enabled": False},
    )
    assert patch.status_code == 200
    assert patch.json()["interval_minutes"] == 120
    assert patch.json()["enabled"] is False

    delete = client.delete(f"/api/v1/jobs/{job_id}", headers={"Authorization": f"Bearer {_operator_token(runtime)}"})
    assert delete.status_code == 204
```

- [ ] **Step 2: Run tests to verify failure**

```bash
rtk python -m pytest app_v4/tests/test_jobs_api.py -v
```

Expected: FAIL because jobs stub has no routes.

- [ ] **Step 3: Replace jobs router**

Replace `app_v4/service/api/jobs.py` with:

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app_v4.core.auth_service import AccessClaims
from app_v4.data.repository import Repository
from app_v4.service.deps import get_db, require_role
from app_v4.service.problem import problem

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobOut(BaseModel):
    id: int
    switch_id: int
    interval_minutes: int
    enabled: bool
    schedule_hour: int
    schedule_minute: int


class JobCreate(BaseModel):
    switch_id: int
    interval_minutes: int = Field(gt=0)
    enabled: bool = True
    schedule_hour: int = Field(default=8, ge=0, le=23)
    schedule_minute: int = Field(default=0, ge=0, le=59)


class JobUpdate(BaseModel):
    interval_minutes: int | None = Field(default=None, gt=0)
    enabled: bool | None = None
    schedule_hour: int | None = Field(default=None, ge=0, le=23)
    schedule_minute: int | None = Field(default=None, ge=0, le=59)


def _to_out(job) -> JobOut:
    return JobOut(
        id=job.id,
        switch_id=job.switch_id,
        interval_minutes=job.interval_minutes,
        enabled=job.enabled,
        schedule_hour=job.schedule_hour,
        schedule_minute=job.schedule_minute,
    )


@router.get("", response_model=list[JobOut])
async def list_jobs(
    session: AsyncSession = Depends(get_db),
    _user: AccessClaims = Depends(require_role("admin", "operator", "viewer")),
) -> list[JobOut]:
    repo = Repository(session)
    return [_to_out(j) for j in await repo.list_jobs()]


@router.post("", response_model=JobOut, status_code=status.HTTP_201_CREATED)
async def create_job(
    payload: JobCreate,
    session: AsyncSession = Depends(get_db),
    _user: AccessClaims = Depends(require_role("admin", "operator")),
) -> JobOut:
    repo = Repository(session)
    if await repo.get_switch(payload.switch_id) is None:
        raise problem(422, "Unprocessable Entity", "Referenced switch does not exist")
    job = await repo.create_job(payload.switch_id, payload.interval_minutes, payload.enabled, payload.schedule_hour, payload.schedule_minute)
    await session.commit()
    return _to_out(job)


@router.patch("/{job_id}", response_model=JobOut)
async def update_job(
    job_id: int,
    payload: JobUpdate,
    session: AsyncSession = Depends(get_db),
    _user: AccessClaims = Depends(require_role("admin", "operator")),
) -> JobOut:
    repo = Repository(session)
    job = await repo.update_job(job_id, **payload.model_dump(exclude_none=True))
    if job is None:
        raise problem(404, "Not Found", "Job not found")
    await session.commit()
    return _to_out(job)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: int,
    session: AsyncSession = Depends(get_db),
    _user: AccessClaims = Depends(require_role("admin", "operator")),
) -> Response:
    repo = Repository(session)
    deleted = await repo.delete_job(job_id)
    if not deleted:
        raise problem(404, "Not Found", "Job not found")
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 4: Run jobs tests**

```bash
rtk python -m pytest app_v4/tests/test_jobs_api.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add app_v4/service/api/jobs.py app_v4/tests/test_jobs_api.py
rtk git commit -m "feat: add v4 jobs CRUD API"
```

---

## Task 9: Add AsyncIOScheduler service

**Files:**
- Create: `app_v4/service/scheduler.py`
- Modify: `app_v4/service/runtime.py`
- Test: `app_v4/tests/test_scheduler.py`

- [ ] **Step 1: Write scheduler tests**

Create `app_v4/tests/test_scheduler.py`:

```python
import pytest

from app_v4.data.repository import Repository
from app_v4.service.scheduler import SchedulerService


class FakeBackupService:
    def __init__(self):
        self.calls = []

    async def execute_backup(self, switch_id, backup_type="automatic", job_id=None, triggered_by_user_id=None):
        self.calls.append((switch_id, backup_type, job_id, triggered_by_user_id))
        return {"success": True, "message": "ok", "backup_id": 1, "file_path": "", "size_kb": 0}


@pytest.mark.asyncio
async def test_scheduler_sync_registers_enabled_jobs(test_settings, session_factory):
    backup_service = FakeBackupService()
    scheduler = SchedulerService(test_settings, session_factory, backup_service)
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential("cred", b"x")
        switch = await repo.create_switch("sw", "10.0.0.1", "ssh", 22, cred.id)
        job = await repo.create_job(switch.id, 60, True, 8, 30)
        await session.commit()
        job_id = job.id

    await scheduler.sync_once()

    assert job_id in scheduler.job_map
    await scheduler.stop()


@pytest.mark.asyncio
async def test_scheduler_execute_job_runs_backup_and_updates_last_run(test_settings, session_factory):
    backup_service = FakeBackupService()
    scheduler = SchedulerService(test_settings, session_factory, backup_service)
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential("cred", b"x")
        switch = await repo.create_switch("sw", "10.0.0.1", "ssh", 22, cred.id)
        job = await repo.create_job(switch.id, 60, True, 8, 30)
        await session.commit()
        job_id = job.id
        switch_id = switch.id

    await scheduler.execute_scheduled_backup(job_id, switch_id)

    assert backup_service.calls == [(switch_id, "automatic", job_id, None)]
    async with session_factory() as session:
        repo = Repository(session)
        loaded = await repo.get_job(job_id)
    assert loaded.last_ran_at is not None
```

- [ ] **Step 2: Run tests to verify failure**

```bash
rtk python -m pytest app_v4/tests/test_scheduler.py -v
```

Expected: FAIL with missing scheduler service.

- [ ] **Step 3: Create SchedulerService**

Create `app_v4/service/scheduler.py`:

```python
from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app_v4.core.config import Settings
from app_v4.core.paths import resolve_paths
from app_v4.data.repository import Repository
from app_v4.service.backup_service import BackupService


class SchedulerService:
    def __init__(self, settings: Settings, session_factory: async_sessionmaker[AsyncSession], backup_service: BackupService):
        self.settings = settings
        self.session_factory = session_factory
        self.backup_service = backup_service
        self.scheduler = AsyncIOScheduler(job_defaults={"coalesce": False, "max_instances": 3})
        self.job_map: dict[int, str] = {}
        self.job_interval_map: dict[int, int] = {}
        self.job_time_map: dict[int, tuple[int, int]] = {}
        self._sync_task: asyncio.Task | None = None
        self._lock_acquired = False
        self._lock_file = resolve_paths(settings).scheduler_lock_file

    async def start(self) -> bool:
        if not self._acquire_lock():
            return False
        self.scheduler.start()
        await self.sync_once()
        self._sync_task = asyncio.create_task(self._sync_loop())
        return True

    async def stop(self) -> None:
        if self._sync_task is not None:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
            self._sync_task = None
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        self._release_lock()

    async def sync_once(self) -> None:
        async with self.session_factory() as session:
            repo = Repository(session)
            jobs = await repo.list_jobs()
        enabled_ids = {job.id for job in jobs if job.enabled}
        for job_id in list(self.job_map):
            if job_id not in enabled_ids:
                self.remove_job(job_id)
        for job in jobs:
            if not job.enabled:
                continue
            time_pair = (job.schedule_hour, job.schedule_minute)
            if job.id not in self.job_map:
                self.add_job(job.id, job.switch_id, job.interval_minutes, job.schedule_hour, job.schedule_minute)
            elif self.job_interval_map.get(job.id) != job.interval_minutes or self.job_time_map.get(job.id) != time_pair:
                self.remove_job(job.id)
                self.add_job(job.id, job.switch_id, job.interval_minutes, job.schedule_hour, job.schedule_minute)

    def add_job(self, job_id: int, switch_id: int, interval_minutes: int, schedule_hour: int, schedule_minute: int) -> None:
        aps_id = f"backup_job_{job_id}"
        self.scheduler.add_job(
            self.execute_scheduled_backup,
            trigger=self._build_trigger(interval_minutes, schedule_hour, schedule_minute),
            id=aps_id,
            args=[job_id, switch_id],
            replace_existing=True,
            name=f"Backup Job {job_id}",
        )
        self.job_map[job_id] = aps_id
        self.job_interval_map[job_id] = interval_minutes
        self.job_time_map[job_id] = (schedule_hour, schedule_minute)

    def remove_job(self, job_id: int) -> None:
        aps_id = self.job_map.pop(job_id, None)
        self.job_interval_map.pop(job_id, None)
        self.job_time_map.pop(job_id, None)
        if aps_id and self.scheduler.get_job(aps_id):
            self.scheduler.remove_job(aps_id)

    async def execute_scheduled_backup(self, job_id: int, switch_id: int) -> None:
        started_at = datetime.utcnow()
        await self.backup_service.execute_backup(
            switch_id=switch_id,
            backup_type="automatic",
            job_id=job_id,
            triggered_by_user_id=None,
        )
        async with self.session_factory() as session:
            repo = Repository(session)
            await repo.update_job(job_id, last_ran_at=started_at)
            await session.commit()

    def _build_trigger(self, interval_minutes: int, schedule_hour: int, schedule_minute: int):
        if interval_minutes == 1440:
            return CronTrigger(hour=schedule_hour, minute=schedule_minute)
        if interval_minutes == 10080:
            return CronTrigger(day_of_week="mon", hour=schedule_hour, minute=schedule_minute)
        if interval_minutes == 43200:
            return CronTrigger(day=1, hour=schedule_hour, minute=schedule_minute)
        return IntervalTrigger(minutes=interval_minutes)

    async def _sync_loop(self) -> None:
        while True:
            await asyncio.sleep(30)
            await self.sync_once()
            if self._lock_acquired and self._lock_file.exists():
                os.utime(self._lock_file, None)

    def _acquire_lock(self) -> bool:
        self._lock_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(self._lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w") as handle:
                handle.write(f"{os.getpid()} {int(time.time())}\n")
            self._lock_acquired = True
            return True
        except FileExistsError:
            age = time.time() - self._lock_file.stat().st_mtime
            if age > self.settings.scheduler_lock_seconds:
                self._lock_file.unlink()
                return self._acquire_lock()
            return False

    def _release_lock(self) -> None:
        if self._lock_acquired and self._lock_file.exists():
            self._lock_file.unlink()
        self._lock_acquired = False
```

- [ ] **Step 4: Update runtime to include scheduler field**

Modify `app_v4/service/runtime.py`:

- Add import:

```python
from app_v4.service.scheduler import SchedulerService
```

- Add dataclass field:

```python
    scheduler_service: SchedulerService | None = None
```

- In `for_tests`, accept and pass optional scheduler:

```python
        scheduler_service: SchedulerService | None = None,
```

and:

```python
            scheduler_service=scheduler_service,
```

- In `build_runtime`, after `backup_service`:

```python
    scheduler_service = SchedulerService(settings, session_factory, backup_service)
    await scheduler_service.start()
```

and pass:

```python
        scheduler_service=scheduler_service,
```

- [ ] **Step 5: Run scheduler tests**

```bash
rtk python -m pytest app_v4/tests/test_scheduler.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
rtk git add app_v4/service/scheduler.py app_v4/service/runtime.py app_v4/tests/test_scheduler.py
rtk git commit -m "feat: add v4 async backup scheduler"
```

---

## Task 10: Final verification

**Files:**
- Test: all `app_v4/tests/*.py`

- [ ] **Step 1: Run full suite**

```bash
rtk python -m pytest app_v4/tests -v
```

Expected: all tests pass.

- [ ] **Step 2: Smoke import services and routers**

```bash
rtk python -c "from app_v4.service.backup_service import BackupService; from app_v4.service.scheduler import SchedulerService; from app_v4.net.runner import BackupRunner; print('ok')"
```

Expected:

```text
ok
```

- [ ] **Step 3: Check git status**

```bash
rtk git status
```

Expected: no uncommitted changes except existing unrelated untracked plan/production files.

---

## Handoff Notes

After Phase 1:

- SSH and Telnet backup execution available via `BackupRunner`
- `BackupService` stores configs under `backups/<switch>/<YYYY-MM-DD>/HHMMSS_running-config.txt`
- Diff files are created when a successful config changes from previous backup
- `POST /api/v1/switches/{id}/backups` runs a manual backup
- `/api/v1/backups` lists backups and exposes content/diff readers
- `/api/v1/jobs` manages schedules
- `SchedulerService` registers enabled jobs and runs automatic backups through APScheduler

Phase 2 will add async WebSmart/HTTP clients for `http`, `https`, `websmart`, and `websmart-v2`, including login probing and config extraction.
