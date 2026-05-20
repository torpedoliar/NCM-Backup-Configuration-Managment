# NCM v4 Backend CRUD Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add bootstrap CLI, audit logging, and CRUD endpoints for users, credentials, and switches so the v4 backend can be initialized and managed end-to-end via API.

**Architecture:** Build on the existing `app_v4/` skeleton. Add a CLI entrypoint that generates the master envelope, master.key, and the first admin user. Add an audit log writer used by mutating endpoints. Add three resource APIs (users, credentials, switches) with role-based access via `require_role`. Reuse `Repository` for data access, extending it with new methods. The `CryptoService` is required for credentials work — tests construct one with a fixed passphrase via a fixture, while the runtime constructs it from the envelope passphrase as it does today.

**Tech Stack:** FastAPI, async SQLAlchemy 2, Pydantic v2, argon2-cffi, Fernet via `app_v4.core.crypto_service`, pytest-asyncio, pytest, click (CLI). All new code lives under `app_v4/`. Plan does not modify `app/`.

---

## File Structure

Create these files:

```text
app_v4/
├── cli.py                                # `python -m app_v4 init`
├── __main__.py                           # entrypoint forwarding to cli.main
├── service/
│   ├── audit.py                          # AuditWriter helper
│   └── api/
│       ├── users.py                      # /api/v1/users
│       ├── credentials.py                # /api/v1/credentials
│       └── switches.py                   # /api/v1/switches
└── tests/
    ├── test_cli_init.py                  # init command behavior
    ├── test_audit.py                     # audit writer
    ├── test_users_api.py
    ├── test_credentials_api.py
    └── test_switches_api.py
```

Modify these files:

```text
app_v4/data/repository.py                 # add credentials, switches, audit methods
app_v4/service/app.py                     # register new routers
app_v4/service/runtime.py                 # for_tests accepts crypto_service
app_v4/tests/conftest.py                  # crypto_service fixture
```

Do not modify `app/`.

---

## Task 1: Add Repository methods for credentials, switches, and audit

**Files:**
- Modify: `app_v4/data/repository.py`
- Test: `app_v4/tests/test_repository.py` (extend existing)

- [ ] **Step 1: Write failing tests for credential and switch repo methods**

Append to `app_v4/tests/test_repository.py`:

```python
import pytest as _pytest


@_pytest.mark.asyncio
async def test_credential_crud(session_factory):
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential(name="lab-ssh", enc_blob=b"ciphertext")
        await session.commit()
        cred_id = cred.id

    async with session_factory() as session:
        repo = Repository(session)
        loaded = await repo.get_credential_by_name("lab-ssh")
        listed = await repo.list_credentials()
        assert loaded is not None
        assert loaded.id == cred_id
        assert len(listed) == 1

        await repo.update_credential(cred_id, name="lab-ssh-renamed", enc_blob=b"new")
        await session.commit()

    async with session_factory() as session:
        repo = Repository(session)
        loaded = await repo.get_credential(cred_id)
        assert loaded is not None
        assert loaded.name == "lab-ssh-renamed"
        assert loaded.enc_blob == b"new"
        await repo.delete_credential(cred_id)
        await session.commit()

    async with session_factory() as session:
        repo = Repository(session)
        assert await repo.get_credential(cred_id) is None


@_pytest.mark.asyncio
async def test_switch_crud(session_factory):
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential(name="c1", enc_blob=b"x")
        switch = await repo.create_switch(
            name="sw01",
            ip="10.0.0.1",
            protocol="ssh",
            port=22,
            credential_id=cred.id,
            notes="rack 1",
        )
        await session.commit()
        switch_id = switch.id

    async with session_factory() as session:
        repo = Repository(session)
        loaded = await repo.get_switch(switch_id)
        listed = await repo.list_switches()
        assert loaded is not None
        assert loaded.name == "sw01"
        assert loaded.credential.name == "c1"
        assert len(listed) == 1

        await repo.update_switch(switch_id, ip="10.0.0.2", port=2222)
        await session.commit()

    async with session_factory() as session:
        repo = Repository(session)
        loaded = await repo.get_switch(switch_id)
        assert loaded is not None
        assert loaded.ip == "10.0.0.2"
        assert loaded.port == 2222
        await repo.delete_switch(switch_id)
        await session.commit()


@_pytest.mark.asyncio
async def test_delete_credential_in_use_raises(session_factory):
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential(name="busy", enc_blob=b"x")
        await repo.create_switch(
            name="sw", ip="10.0.0.5", protocol="ssh", port=22, credential_id=cred.id
        )
        await session.commit()
        cred_id = cred.id

    async with session_factory() as session:
        repo = Repository(session)
        with _pytest.raises(ValueError, match="in use"):
            await repo.delete_credential(cred_id)


@_pytest.mark.asyncio
async def test_list_users_and_update_user(session_factory):
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_user("admin", "h1", "admin")
        await repo.create_user("ops", "h2", "operator")
        await session.commit()

    async with session_factory() as session:
        repo = Repository(session)
        users = await repo.list_users()
        assert {u.username for u in users} == {"admin", "ops"}

        ops = await repo.get_user_by_username("ops")
        await repo.update_user(ops.id, role="viewer", is_active=False)
        await session.commit()

    async with session_factory() as session:
        repo = Repository(session)
        ops = await repo.get_user_by_username("ops")
        assert ops.role == "viewer"
        assert ops.is_active is False


@_pytest.mark.asyncio
async def test_audit_write(session_factory):
    async with session_factory() as session:
        repo = Repository(session)
        user = await repo.create_user("admin", "h", "admin")
        await repo.write_audit(
            user_id=user.id,
            action="user.create",
            target_type="user",
            target_id=str(user.id),
            ip="127.0.0.1",
            detail_json='{"username":"admin"}',
        )
        await session.commit()

    async with session_factory() as session:
        repo = Repository(session)
        rows = await repo.list_audit(limit=10)
        assert len(rows) == 1
        assert rows[0].action == "user.create"
        assert rows[0].target_id == str(user.id)
```

- [ ] **Step 2: Run tests to verify failures**

```bash
rtk python -m pytest app_v4/tests/test_repository.py -v
```

Expected: 5 new tests FAIL with `AttributeError: ... has no attribute 'create_credential'` etc. Existing 2 tests still PASS.

- [ ] **Step 3: Extend Repository with the missing methods**

Replace `app_v4/data/repository.py` with:

```python
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app_v4.data.models import AuditLog, Backup, Credential, Job, Session, Switch, User


class Repository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ----- users -----

    async def create_user(self, username: str, password_hash: str, role: str) -> User:
        user = User(username=username, password_hash=password_hash, role=role, is_active=True)
        self.session.add(user)
        await self.session.flush()
        return user

    async def get_user_by_username(self, username: str) -> User | None:
        result = await self.session.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: int) -> User | None:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def list_users(self) -> list[User]:
        result = await self.session.execute(select(User).order_by(User.username))
        return list(result.scalars().all())

    async def update_user(
        self,
        user_id: int,
        role: str | None = None,
        is_active: bool | None = None,
        password_hash: str | None = None,
    ) -> User | None:
        user = await self.get_user_by_id(user_id)
        if user is None:
            return None
        if role is not None:
            user.role = role
        if is_active is not None:
            user.is_active = is_active
        if password_hash is not None:
            user.password_hash = password_hash
        return user

    async def delete_user(self, user_id: int) -> bool:
        user = await self.get_user_by_id(user_id)
        if user is None:
            return False
        await self.session.delete(user)
        return True

    async def mark_user_login(self, user_id: int) -> None:
        user = await self.get_user_by_id(user_id)
        if user is not None:
            user.last_login_at = datetime.utcnow()

    async def count_users(self) -> int:
        result = await self.session.execute(select(func.count(User.id)))
        return int(result.scalar_one())

    # ----- sessions -----

    async def create_session(
        self,
        user_id: int,
        refresh_token_hash: str,
        ip: str | None,
        user_agent: str | None,
        days_valid: int,
    ) -> Session:
        row = Session(
            user_id=user_id,
            refresh_token_hash=refresh_token_hash,
            ip=ip,
            user_agent=user_agent,
            expires_at=datetime.utcnow() + timedelta(days=days_valid),
            revoked=False,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def get_session_by_refresh_hash(self, refresh_token_hash: str) -> Session | None:
        result = await self.session.execute(
            select(Session).where(Session.refresh_token_hash == refresh_token_hash)
        )
        return result.scalar_one_or_none()

    async def revoke_session(self, session_id: int) -> None:
        row = await self.session.get(Session, session_id)
        if row is not None:
            row.revoked = True

    # ----- credentials -----

    async def create_credential(self, name: str, enc_blob: bytes) -> Credential:
        cred = Credential(name=name, enc_blob=enc_blob)
        self.session.add(cred)
        await self.session.flush()
        return cred

    async def get_credential(self, cred_id: int) -> Credential | None:
        return await self.session.get(Credential, cred_id)

    async def get_credential_by_name(self, name: str) -> Credential | None:
        result = await self.session.execute(select(Credential).where(Credential.name == name))
        return result.scalar_one_or_none()

    async def list_credentials(self) -> list[Credential]:
        result = await self.session.execute(select(Credential).order_by(Credential.name))
        return list(result.scalars().all())

    async def update_credential(
        self, cred_id: int, name: str | None = None, enc_blob: bytes | None = None
    ) -> Credential | None:
        cred = await self.get_credential(cred_id)
        if cred is None:
            return None
        if name is not None:
            cred.name = name
        if enc_blob is not None:
            cred.enc_blob = enc_blob
        cred.updated_at = datetime.utcnow()
        return cred

    async def delete_credential(self, cred_id: int) -> bool:
        cred = await self.session.execute(
            select(Credential).options(selectinload(Credential.switches)).where(Credential.id == cred_id)
        )
        cred = cred.scalar_one_or_none()
        if cred is None:
            return False
        if cred.switches:
            raise ValueError("Credential is in use by switches")
        await self.session.delete(cred)
        return True

    # ----- switches -----

    async def create_switch(
        self,
        name: str,
        ip: str,
        protocol: str,
        port: int,
        credential_id: int,
        notes: str | None = None,
    ) -> Switch:
        switch = Switch(
            name=name,
            ip=ip,
            protocol=protocol,
            port=port,
            credential_id=credential_id,
            notes=notes,
        )
        self.session.add(switch)
        await self.session.flush()
        return switch

    async def get_switch(self, switch_id: int) -> Switch | None:
        result = await self.session.execute(
            select(Switch).options(selectinload(Switch.credential)).where(Switch.id == switch_id)
        )
        return result.scalar_one_or_none()

    async def get_switch_by_name(self, name: str) -> Switch | None:
        result = await self.session.execute(select(Switch).where(Switch.name == name))
        return result.scalar_one_or_none()

    async def list_switches(self) -> list[Switch]:
        result = await self.session.execute(
            select(Switch).options(selectinload(Switch.credential)).order_by(Switch.name)
        )
        return list(result.scalars().all())

    async def update_switch(self, switch_id: int, **kwargs) -> Switch | None:
        switch = await self.get_switch(switch_id)
        if switch is None:
            return None
        for key, value in kwargs.items():
            if value is not None and hasattr(switch, key):
                setattr(switch, key, value)
        switch.updated_at = datetime.utcnow()
        return switch

    async def delete_switch(self, switch_id: int) -> bool:
        switch = await self.get_switch(switch_id)
        if switch is None:
            return False
        await self.session.delete(switch)
        return True

    # ----- audit -----

    async def write_audit(
        self,
        user_id: int | None,
        action: str,
        target_type: str | None = None,
        target_id: str | None = None,
        ip: str | None = None,
        detail_json: str | None = None,
    ) -> AuditLog:
        row = AuditLog(
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            ip=ip,
            detail_json=detail_json,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def list_audit(
        self,
        user_id: int | None = None,
        action: str | None = None,
        limit: int = 100,
    ) -> list[AuditLog]:
        stmt = select(AuditLog)
        if user_id is not None:
            stmt = stmt.where(AuditLog.user_id == user_id)
        if action is not None:
            stmt = stmt.where(AuditLog.action == action)
        stmt = stmt.order_by(AuditLog.ts.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ----- system -----

    async def system_metrics(self) -> dict[str, int]:
        switches = await self.session.execute(select(func.count(Switch.id)))
        backups = await self.session.execute(select(func.count(Backup.id)))
        jobs = await self.session.execute(select(func.count(Job.id)))
        failed = await self.session.execute(
            select(func.count(Backup.id)).where(Backup.success.is_(False))
        )
        return {
            "switches": int(switches.scalar_one()),
            "backups": int(backups.scalar_one()),
            "jobs": int(jobs.scalar_one()),
            "failed_backups": int(failed.scalar_one()),
        }


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Run all repository tests**

```bash
rtk python -m pytest app_v4/tests/test_repository.py -v
```

Expected: PASS, 7 tests (2 original + 5 new).

- [ ] **Step 5: Run full test suite to confirm no regressions**

```bash
rtk python -m pytest app_v4/tests -q
```

Expected: PASS, 29 tests (24 original + 5 new).

- [ ] **Step 6: Commit**

```bash
rtk git add -f app_v4/data/repository.py
rtk git add app_v4/tests/test_repository.py
rtk git commit -m "feat: extend v4 repository with credentials/switches/users/audit methods"
```

---

## Task 2: Add bootstrap CLI for envelope and admin user

**Files:**
- Create: `app_v4/cli.py`
- Create: `app_v4/__main__.py`
- Test: `app_v4/tests/test_cli_init.py`

- [ ] **Step 1: Write failing CLI test**

Create `app_v4/tests/test_cli_init.py`:

```python
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app_v4.cli import init_command
from app_v4.core.config import Settings
from app_v4.core.dpapi import MemoryProtectionProvider
from app_v4.core.key_envelope import KeyEnvelopeStore
from app_v4.core.paths import resolve_paths


@pytest.mark.asyncio
async def test_init_creates_envelope_admin_and_db(tmp_path: Path):
    settings = Settings(base_dir=tmp_path)
    provider = MemoryProtectionProvider(secret=b"unit-test")

    result = await init_command(
        settings=settings,
        master_passphrase="master-pass-1",
        admin_username="admin",
        admin_password="StrongAdmin1!",
        protection_provider=provider,
    )

    paths = resolve_paths(settings)
    envelope = KeyEnvelopeStore(paths.master_envelope_file, provider).load()

    assert envelope.master_passphrase == "master-pass-1"
    assert len(envelope.jwt_secret) == 32
    assert paths.master_key_file.exists()

    engine = create_async_engine(settings.database_url)
    async with engine.connect() as conn:
        rows = await conn.execute(text("select username, role, is_active from users"))
        users = list(rows)
    await engine.dispose()

    assert users == [("admin", "admin", 1)]
    assert result["created_admin"] is True
    assert result["created_envelope"] is True


@pytest.mark.asyncio
async def test_init_is_idempotent_when_envelope_and_admin_exist(tmp_path: Path):
    settings = Settings(base_dir=tmp_path)
    provider = MemoryProtectionProvider(secret=b"unit-test")

    await init_command(
        settings=settings,
        master_passphrase="master-pass-1",
        admin_username="admin",
        admin_password="StrongAdmin1!",
        protection_provider=provider,
    )

    second = await init_command(
        settings=settings,
        master_passphrase="master-pass-1",
        admin_username="admin",
        admin_password="StrongAdmin1!",
        protection_provider=provider,
    )

    assert second["created_envelope"] is False
    assert second["created_admin"] is False


@pytest.mark.asyncio
async def test_init_rejects_passphrase_mismatch_on_existing_envelope(tmp_path: Path):
    settings = Settings(base_dir=tmp_path)
    provider = MemoryProtectionProvider(secret=b"unit-test")

    await init_command(
        settings=settings,
        master_passphrase="master-pass-1",
        admin_username="admin",
        admin_password="StrongAdmin1!",
        protection_provider=provider,
    )

    with pytest.raises(ValueError, match="passphrase does not match"):
        await init_command(
            settings=settings,
            master_passphrase="different-pass",
            admin_username="admin",
            admin_password="StrongAdmin1!",
            protection_provider=provider,
        )
```

- [ ] **Step 2: Run tests to verify failure**

```bash
rtk python -m pytest app_v4/tests/test_cli_init.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app_v4.cli'`.

- [ ] **Step 3: Implement init_command**

Create `app_v4/cli.py`:

```python
from __future__ import annotations

import argparse
import asyncio
import getpass
import sys
from pathlib import Path

from app_v4.core.auth_service import AuthService
from app_v4.core.config import Settings
from app_v4.core.crypto_service import CryptoService
from app_v4.core.dpapi import ProtectionProvider, WindowsDpapiProvider
from app_v4.core.key_envelope import KeyEnvelopeStore
from app_v4.core.paths import resolve_paths
from app_v4.data.db import create_session_factory, init_db
from app_v4.data.repository import Repository


async def init_command(
    settings: Settings,
    master_passphrase: str,
    admin_username: str,
    admin_password: str,
    protection_provider: ProtectionProvider | None = None,
) -> dict:
    provider = protection_provider or WindowsDpapiProvider()
    paths = resolve_paths(settings)
    paths.data_dir.mkdir(parents=True, exist_ok=True)

    store = KeyEnvelopeStore(paths.master_envelope_file, provider)
    if paths.master_envelope_file.exists():
        existing = store.load()
        if existing.master_passphrase != master_passphrase:
            raise ValueError(
                "Master passphrase does not match the existing envelope"
            )
        envelope = existing
        created_envelope = False
    else:
        envelope = store.create(master_passphrase=master_passphrase)
        created_envelope = True

    CryptoService(settings=settings, passphrase=envelope.master_passphrase)

    engine, session_factory = create_session_factory(settings)
    await init_db(engine)
    auth = AuthService(settings=settings, jwt_secret=envelope.jwt_secret)

    created_admin = False
    try:
        async with session_factory() as session:
            repo = Repository(session)
            existing_user = await repo.get_user_by_username(admin_username)
            if existing_user is None:
                password_hash = auth.hash_password(admin_password)
                await repo.create_user(admin_username, password_hash, "admin")
                await session.commit()
                created_admin = True
    finally:
        await engine.dispose()

    return {
        "created_envelope": created_envelope,
        "created_admin": created_admin,
        "base_dir": str(paths.base_dir),
        "envelope_file": str(paths.master_envelope_file),
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="app_v4", description="NCM v4 backend CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    init_parser = sub.add_parser("init", help="Initialize key envelope and first admin user")
    init_parser.add_argument("--passphrase", help="Master passphrase (prompted if omitted)")
    init_parser.add_argument("--admin-username", default="admin")
    init_parser.add_argument(
        "--admin-password",
        help="Admin password (prompted if omitted)",
    )

    return parser.parse_args(argv)


def _prompt_secret(prompt: str) -> str:
    secret = getpass.getpass(prompt)
    if not secret:
        raise SystemExit("empty value not allowed")
    return secret


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.command != "init":
        raise SystemExit(f"unknown command: {args.command}")

    passphrase = args.passphrase or _prompt_secret("Master passphrase: ")
    admin_password = args.admin_password or _prompt_secret(
        f"Password for admin user '{args.admin_username}': "
    )

    settings = Settings()
    result = asyncio.run(
        init_command(
            settings=settings,
            master_passphrase=passphrase,
            admin_username=args.admin_username,
            admin_password=admin_password,
        )
    )

    print(f"base_dir: {result['base_dir']}")
    print(f"envelope: {result['envelope_file']}")
    print(f"envelope created: {result['created_envelope']}")
    print(f"admin created: {result['created_admin']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Create `app_v4/__main__.py`:

```python
from app_v4.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run CLI tests**

```bash
rtk python -m pytest app_v4/tests/test_cli_init.py -v
```

Expected: PASS, 3 tests.

- [ ] **Step 5: Commit**

```bash
rtk git add app_v4/cli.py app_v4/__main__.py app_v4/tests/test_cli_init.py
rtk git commit -m "feat: add v4 bootstrap init CLI"
```

---

## Task 3: Add audit log writer helper and inject into runtime

**Files:**
- Create: `app_v4/service/audit.py`
- Modify: `app_v4/service/runtime.py`
- Modify: `app_v4/tests/conftest.py`
- Test: `app_v4/tests/test_audit.py`

- [ ] **Step 1: Write failing audit writer test**

Create `app_v4/tests/test_audit.py`:

```python
import pytest

from app_v4.data.repository import Repository
from app_v4.service.audit import AuditWriter


@pytest.mark.asyncio
async def test_audit_writer_records_event(session_factory):
    writer = AuditWriter(session_factory)

    await writer.record(
        user_id=None,
        action="auth.login",
        target_type="user",
        target_id="42",
        ip="127.0.0.1",
        detail={"username": "admin"},
    )

    async with session_factory() as session:
        repo = Repository(session)
        rows = await repo.list_audit(limit=10)

    assert len(rows) == 1
    assert rows[0].action == "auth.login"
    assert rows[0].target_id == "42"
    assert rows[0].detail_json is not None
    assert "admin" in rows[0].detail_json


@pytest.mark.asyncio
async def test_audit_writer_handles_no_detail(session_factory):
    writer = AuditWriter(session_factory)

    await writer.record(user_id=None, action="auth.logout")

    async with session_factory() as session:
        repo = Repository(session)
        rows = await repo.list_audit(limit=10)

    assert rows[0].detail_json is None
```

- [ ] **Step 2: Run tests to verify failure**

```bash
rtk python -m pytest app_v4/tests/test_audit.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app_v4.service.audit'`.

- [ ] **Step 3: Implement AuditWriter**

Create `app_v4/service/audit.py`:

```python
from __future__ import annotations

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app_v4.data.repository import Repository


class AuditWriter:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self.session_factory = session_factory

    async def record(
        self,
        action: str,
        user_id: int | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        ip: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        detail_json = json.dumps(detail, separators=(",", ":")) if detail else None
        async with self.session_factory() as session:
            repo = Repository(session)
            await repo.write_audit(
                user_id=user_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                ip=ip,
                detail_json=detail_json,
            )
            await session.commit()
```

- [ ] **Step 4: Inject AuditWriter into runtime**

Replace `app_v4/service/runtime.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app_v4.core.auth_service import AuthService
from app_v4.core.config import Settings
from app_v4.core.crypto_service import CryptoService
from app_v4.core.dpapi import WindowsDpapiProvider
from app_v4.core.key_envelope import KeyEnvelopeStore
from app_v4.core.paths import resolve_paths
from app_v4.data.db import create_session_factory, init_db
from app_v4.service.audit import AuditWriter
from app_v4.service.events import EventHub


@dataclass
class ServiceRuntime:
    settings: Settings
    session_factory: async_sessionmaker[AsyncSession]
    auth_service: AuthService
    event_hub: EventHub
    audit_writer: AuditWriter
    crypto_service: CryptoService | None = None
    started_at: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def for_tests(
        cls,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        jwt_secret: bytes,
        crypto_service: CryptoService | None = None,
    ) -> "ServiceRuntime":
        return cls(
            settings=settings,
            session_factory=session_factory,
            auth_service=AuthService(settings=settings, jwt_secret=jwt_secret),
            event_hub=EventHub(),
            audit_writer=AuditWriter(session_factory),
            crypto_service=crypto_service,
        )


async def build_runtime(settings: Settings) -> tuple[ServiceRuntime, object]:
    paths = resolve_paths(settings)
    envelope = KeyEnvelopeStore(paths.master_envelope_file, WindowsDpapiProvider()).load()
    crypto = CryptoService(settings=settings, passphrase=envelope.master_passphrase)
    engine, session_factory = create_session_factory(settings)
    await init_db(engine)
    runtime = ServiceRuntime(
        settings=settings,
        session_factory=session_factory,
        auth_service=AuthService(settings=settings, jwt_secret=envelope.jwt_secret),
        event_hub=EventHub(),
        audit_writer=AuditWriter(session_factory),
        crypto_service=crypto,
    )
    return runtime, engine
```

- [ ] **Step 5: Run all tests to confirm runtime change is backward-compatible**

```bash
rtk python -m pytest app_v4/tests -q
```

Expected: PASS, 32 tests (29 + 2 audit + 1 already-passing-but-renamed-or-still-passing).

- [ ] **Step 6: Commit**

```bash
rtk git add app_v4/service/audit.py app_v4/service/runtime.py app_v4/tests/test_audit.py
rtk git commit -m "feat: add v4 audit writer and inject into runtime"
```

---

## Task 4: Add crypto_service fixture for tests that need credential encryption

**Files:**
- Modify: `app_v4/tests/conftest.py`

- [ ] **Step 1: Extend conftest with crypto_service fixture**

Replace `app_v4/tests/conftest.py` with:

```python
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app_v4.core.config import Settings
from app_v4.core.crypto_service import CryptoService
from app_v4.data.db import create_session_factory, init_db


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    return Settings(base_dir=tmp_path)


@pytest_asyncio.fixture
async def session_factory(test_settings: Settings) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine, factory = create_session_factory(test_settings)
    await init_db(engine)
    yield factory
    await engine.dispose()


@pytest.fixture
def crypto_service(test_settings: Settings) -> CryptoService:
    return CryptoService(settings=test_settings, passphrase="test-passphrase")
```

- [ ] **Step 2: Run all tests to confirm no regressions**

```bash
rtk python -m pytest app_v4/tests -q
```

Expected: PASS, all tests still green (no new tests yet, fixture is additive).

- [ ] **Step 3: Commit**

```bash
rtk git add app_v4/tests/conftest.py
rtk git commit -m "test: add crypto_service fixture for v4 tests"
```

---

## Task 5: Add users CRUD API

**Files:**
- Create: `app_v4/service/api/users.py`
- Modify: `app_v4/service/app.py`
- Test: `app_v4/tests/test_users_api.py`

- [ ] **Step 1: Write failing users API tests**

Create `app_v4/tests/test_users_api.py`:

```python
import pytest
from fastapi.testclient import TestClient

from app_v4.data.repository import Repository
from app_v4.service.app import create_app
from app_v4.service.runtime import ServiceRuntime


def _admin_token(runtime: ServiceRuntime) -> str:
    return runtime.auth_service.issue_access_token(1, "admin", "admin")


def _viewer_token(runtime: ServiceRuntime) -> str:
    return runtime.auth_service.issue_access_token(2, "viewer", "viewer")


@pytest.mark.asyncio
async def test_list_users_requires_admin(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"u" * 32)
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_user("admin", "h1", "admin")
        await repo.create_user("viewer", "h2", "viewer")
        await session.commit()

    client = TestClient(create_app(runtime))
    viewer_resp = client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {_viewer_token(runtime)}"},
    )
    admin_resp = client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {_admin_token(runtime)}"},
    )

    assert viewer_resp.status_code == 403
    assert admin_resp.status_code == 200
    assert {u["username"] for u in admin_resp.json()} == {"admin", "viewer"}


@pytest.mark.asyncio
async def test_create_user_hashes_password_and_audits(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"u" * 32)
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_user("admin", "h1", "admin")
        await session.commit()

    client = TestClient(create_app(runtime))
    response = client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {_admin_token(runtime)}"},
        json={"username": "ops1", "password": "OpsPass1!", "role": "operator"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "ops1"
    assert body["role"] == "operator"
    assert body["is_active"] is True

    async with session_factory() as session:
        repo = Repository(session)
        created = await repo.get_user_by_username("ops1")
        audits = await repo.list_audit(limit=10)
    assert created is not None
    assert created.password_hash != "OpsPass1!"
    assert any(a.action == "user.create" and a.target_id == str(created.id) for a in audits)


@pytest.mark.asyncio
async def test_update_user_changes_role_and_active(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"u" * 32)
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_user("admin", "h1", "admin")
        target = await repo.create_user("ops1", "h2", "operator")
        await session.commit()
        target_id = target.id

    client = TestClient(create_app(runtime))
    response = client.patch(
        f"/api/v1/users/{target_id}",
        headers={"Authorization": f"Bearer {_admin_token(runtime)}"},
        json={"role": "viewer", "is_active": False},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "viewer"
    assert body["is_active"] is False


@pytest.mark.asyncio
async def test_delete_user_returns_204(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"u" * 32)
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_user("admin", "h1", "admin")
        target = await repo.create_user("ops1", "h2", "operator")
        await session.commit()
        target_id = target.id

    client = TestClient(create_app(runtime))
    response = client.delete(
        f"/api/v1/users/{target_id}",
        headers={"Authorization": f"Bearer {_admin_token(runtime)}"},
    )

    assert response.status_code == 204
    async with session_factory() as session:
        repo = Repository(session)
        assert await repo.get_user_by_id(target_id) is None
```

- [ ] **Step 2: Run tests to verify failure**

```bash
rtk python -m pytest app_v4/tests/test_users_api.py -v
```

Expected: FAIL with 404 because `/api/v1/users` is not registered.

- [ ] **Step 3: Implement users router**

Create `app_v4/service/api/users.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app_v4.core.auth_service import AccessClaims
from app_v4.data.repository import Repository
from app_v4.service.deps import get_db, get_runtime, require_role
from app_v4.service.problem import problem
from app_v4.service.runtime import ServiceRuntime

router = APIRouter(prefix="/users", tags=["users"])


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(pattern="^(admin|operator|viewer)$")


class UserUpdate(BaseModel):
    role: str | None = Field(default=None, pattern="^(admin|operator|viewer)$")
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


def _to_out(user) -> UserOut:
    return UserOut(id=user.id, username=user.username, role=user.role, is_active=user.is_active)


@router.get("", response_model=list[UserOut])
async def list_users(
    session: AsyncSession = Depends(get_db),
    _user: AccessClaims = Depends(require_role("admin")),
) -> list[UserOut]:
    repo = Repository(session)
    users = await repo.list_users()
    return [_to_out(u) for u in users]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    actor: AccessClaims = Depends(require_role("admin")),
) -> UserOut:
    repo = Repository(session)
    if await repo.get_user_by_username(payload.username) is not None:
        raise problem(409, "Conflict", "Username already exists")
    password_hash = runtime.auth_service.hash_password(payload.password)
    user = await repo.create_user(payload.username, password_hash, payload.role)
    await session.commit()

    await runtime.audit_writer.record(
        user_id=actor.user_id,
        action="user.create",
        target_type="user",
        target_id=str(user.id),
        ip=request.client.host if request.client else None,
        detail={"username": user.username, "role": user.role},
    )
    return _to_out(user)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    actor: AccessClaims = Depends(require_role("admin")),
) -> UserOut:
    repo = Repository(session)
    password_hash = (
        runtime.auth_service.hash_password(payload.password) if payload.password else None
    )
    user = await repo.update_user(
        user_id,
        role=payload.role,
        is_active=payload.is_active,
        password_hash=password_hash,
    )
    if user is None:
        raise problem(404, "Not Found", "User not found")
    await session.commit()

    await runtime.audit_writer.record(
        user_id=actor.user_id,
        action="user.update",
        target_type="user",
        target_id=str(user.id),
        ip=request.client.host if request.client else None,
        detail={
            "role": payload.role,
            "is_active": payload.is_active,
            "password_changed": payload.password is not None,
        },
    )
    return _to_out(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    actor: AccessClaims = Depends(require_role("admin")),
) -> Response:
    repo = Repository(session)
    deleted = await repo.delete_user(user_id)
    if not deleted:
        raise problem(404, "Not Found", "User not found")
    await session.commit()

    await runtime.audit_writer.record(
        user_id=actor.user_id,
        action="user.delete",
        target_type="user",
        target_id=str(user_id),
        ip=request.client.host if request.client else None,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 4: Register users router in app factory**

Replace `app_v4/service/app.py` with:

```python
from __future__ import annotations

from fastapi import FastAPI

from app_v4.service.runtime import ServiceRuntime


def create_app(runtime: ServiceRuntime) -> FastAPI:
    app = FastAPI(title="NCM v4 Backend", version="4.0.0-dev")
    app.state.runtime = runtime

    from app_v4.service.api import auth, credentials, switches, system, users, ws

    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(users.router, prefix="/api/v1")
    app.include_router(credentials.router, prefix="/api/v1")
    app.include_router(switches.router, prefix="/api/v1")
    app.include_router(system.router, prefix="/api/v1")
    app.include_router(ws.router)
    return app
```

(`credentials` and `switches` modules will be created in tasks 6-7. To avoid an `ImportError` between tasks, also create stub files now.)

Create `app_v4/service/api/credentials.py`:

```python
from fastapi import APIRouter

router = APIRouter(prefix="/credentials", tags=["credentials"])
```

Create `app_v4/service/api/switches.py`:

```python
from fastapi import APIRouter

router = APIRouter(prefix="/switches", tags=["switches"])
```

- [ ] **Step 5: Run users API tests**

```bash
rtk python -m pytest app_v4/tests/test_users_api.py -v
```

Expected: PASS, 4 tests.

- [ ] **Step 6: Run full suite**

```bash
rtk python -m pytest app_v4/tests -q
```

Expected: PASS, 36 tests.

- [ ] **Step 7: Commit**

```bash
rtk git add app_v4/service/api/users.py app_v4/service/api/credentials.py app_v4/service/api/switches.py app_v4/service/app.py app_v4/tests/test_users_api.py
rtk git commit -m "feat: add v4 users CRUD API with audit"
```

---

## Task 6: Add credentials CRUD API

**Files:**
- Modify: `app_v4/service/api/credentials.py`
- Test: `app_v4/tests/test_credentials_api.py`

- [ ] **Step 1: Write failing credentials API tests**

Create `app_v4/tests/test_credentials_api.py`:

```python
import pytest
from fastapi.testclient import TestClient

from app_v4.data.repository import Repository
from app_v4.service.app import create_app
from app_v4.service.runtime import ServiceRuntime


def _admin_token(runtime: ServiceRuntime) -> str:
    return runtime.auth_service.issue_access_token(1, "admin", "admin")


def _viewer_token(runtime: ServiceRuntime) -> str:
    return runtime.auth_service.issue_access_token(2, "viewer", "viewer")


@pytest.mark.asyncio
async def test_create_credential_encrypts_payload(
    test_settings, session_factory, crypto_service
):
    runtime = ServiceRuntime.for_tests(
        test_settings, session_factory, jwt_secret=b"k" * 32, crypto_service=crypto_service
    )
    client = TestClient(create_app(runtime))

    response = client.post(
        "/api/v1/credentials",
        headers={"Authorization": f"Bearer {_admin_token(runtime)}"},
        json={
            "name": "lab-ssh",
            "username": "admin",
            "password": "switchpass",
            "enable_password": "enablepass",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "lab-ssh"
    assert "password" not in body

    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.get_credential_by_name("lab-ssh")
        assert cred is not None
        decrypted = crypto_service.decrypt_credential(cred.enc_blob)
    assert decrypted == {
        "username": "admin",
        "password": "switchpass",
        "enable_password": "enablepass",
    }


@pytest.mark.asyncio
async def test_list_credentials_requires_operator_or_admin(
    test_settings, session_factory, crypto_service
):
    runtime = ServiceRuntime.for_tests(
        test_settings, session_factory, jwt_secret=b"k" * 32, crypto_service=crypto_service
    )
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_credential(name="lab", enc_blob=b"x")
        await session.commit()
    client = TestClient(create_app(runtime))

    viewer_resp = client.get(
        "/api/v1/credentials",
        headers={"Authorization": f"Bearer {_viewer_token(runtime)}"},
    )
    admin_resp = client.get(
        "/api/v1/credentials",
        headers={"Authorization": f"Bearer {_admin_token(runtime)}"},
    )

    assert viewer_resp.status_code == 403
    assert admin_resp.status_code == 200
    assert [c["name"] for c in admin_resp.json()] == ["lab"]


@pytest.mark.asyncio
async def test_update_credential_re_encrypts(
    test_settings, session_factory, crypto_service
):
    runtime = ServiceRuntime.for_tests(
        test_settings, session_factory, jwt_secret=b"k" * 32, crypto_service=crypto_service
    )
    async with session_factory() as session:
        repo = Repository(session)
        old_blob = crypto_service.encrypt_credential("u", "p", "")
        cred = await repo.create_credential(name="lab", enc_blob=old_blob)
        await session.commit()
        cred_id = cred.id

    client = TestClient(create_app(runtime))
    response = client.patch(
        f"/api/v1/credentials/{cred_id}",
        headers={"Authorization": f"Bearer {_admin_token(runtime)}"},
        json={"username": "u2", "password": "p2", "enable_password": "e2"},
    )

    assert response.status_code == 200
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.get_credential(cred_id)
        decrypted = crypto_service.decrypt_credential(cred.enc_blob)
    assert decrypted == {"username": "u2", "password": "p2", "enable_password": "e2"}


@pytest.mark.asyncio
async def test_delete_credential_in_use_returns_409(
    test_settings, session_factory, crypto_service
):
    runtime = ServiceRuntime.for_tests(
        test_settings, session_factory, jwt_secret=b"k" * 32, crypto_service=crypto_service
    )
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential(name="lab", enc_blob=b"x")
        await repo.create_switch(
            name="sw01",
            ip="10.0.0.1",
            protocol="ssh",
            port=22,
            credential_id=cred.id,
        )
        await session.commit()
        cred_id = cred.id

    client = TestClient(create_app(runtime))
    response = client.delete(
        f"/api/v1/credentials/{cred_id}",
        headers={"Authorization": f"Bearer {_admin_token(runtime)}"},
    )

    assert response.status_code == 409
```

- [ ] **Step 2: Run tests to verify failure**

```bash
rtk python -m pytest app_v4/tests/test_credentials_api.py -v
```

Expected: FAIL with 404 (stub router has no routes).

- [ ] **Step 3: Implement credentials router**

Replace `app_v4/service/api/credentials.py` with:

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app_v4.core.auth_service import AccessClaims
from app_v4.data.repository import Repository
from app_v4.service.deps import get_db, get_runtime, require_role
from app_v4.service.problem import problem
from app_v4.service.runtime import ServiceRuntime

router = APIRouter(prefix="/credentials", tags=["credentials"])


class CredentialOut(BaseModel):
    id: int
    name: str


class CredentialCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)
    enable_password: str = Field(default="", max_length=256)


class CredentialUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    username: str | None = Field(default=None, min_length=1, max_length=128)
    password: str | None = Field(default=None, min_length=1, max_length=256)
    enable_password: str | None = Field(default=None, max_length=256)


def _require_crypto(runtime: ServiceRuntime):
    if runtime.crypto_service is None:
        raise problem(503, "Service Unavailable", "CryptoService is not initialized")
    return runtime.crypto_service


@router.get("", response_model=list[CredentialOut])
async def list_credentials(
    session: AsyncSession = Depends(get_db),
    _user: AccessClaims = Depends(require_role("admin", "operator")),
) -> list[CredentialOut]:
    repo = Repository(session)
    return [CredentialOut(id=c.id, name=c.name) for c in await repo.list_credentials()]


@router.post("", response_model=CredentialOut, status_code=status.HTTP_201_CREATED)
async def create_credential(
    payload: CredentialCreate,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    actor: AccessClaims = Depends(require_role("admin", "operator")),
) -> CredentialOut:
    crypto = _require_crypto(runtime)
    repo = Repository(session)
    if await repo.get_credential_by_name(payload.name) is not None:
        raise problem(409, "Conflict", "Credential name already exists")
    enc_blob = crypto.encrypt_credential(payload.username, payload.password, payload.enable_password)
    cred = await repo.create_credential(name=payload.name, enc_blob=enc_blob)
    await session.commit()

    await runtime.audit_writer.record(
        user_id=actor.user_id,
        action="credential.create",
        target_type="credential",
        target_id=str(cred.id),
        ip=request.client.host if request.client else None,
        detail={"name": cred.name},
    )
    return CredentialOut(id=cred.id, name=cred.name)


@router.patch("/{cred_id}", response_model=CredentialOut)
async def update_credential(
    cred_id: int,
    payload: CredentialUpdate,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    actor: AccessClaims = Depends(require_role("admin", "operator")),
) -> CredentialOut:
    crypto = _require_crypto(runtime)
    repo = Repository(session)
    existing = await repo.get_credential(cred_id)
    if existing is None:
        raise problem(404, "Not Found", "Credential not found")

    new_blob = existing.enc_blob
    if (
        payload.username is not None
        or payload.password is not None
        or payload.enable_password is not None
    ):
        decrypted = crypto.decrypt_credential(existing.enc_blob)
        new_blob = crypto.encrypt_credential(
            username=payload.username if payload.username is not None else decrypted["username"],
            password=payload.password if payload.password is not None else decrypted["password"],
            enable_password=(
                payload.enable_password
                if payload.enable_password is not None
                else decrypted["enable_password"]
            ),
        )

    updated = await repo.update_credential(cred_id, name=payload.name, enc_blob=new_blob)
    await session.commit()

    await runtime.audit_writer.record(
        user_id=actor.user_id,
        action="credential.update",
        target_type="credential",
        target_id=str(cred_id),
        ip=request.client.host if request.client else None,
        detail={
            "name_changed": payload.name is not None,
            "secret_changed": new_blob is not existing.enc_blob,
        },
    )
    return CredentialOut(id=updated.id, name=updated.name)


@router.delete("/{cred_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential(
    cred_id: int,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    actor: AccessClaims = Depends(require_role("admin", "operator")),
) -> Response:
    repo = Repository(session)
    try:
        deleted = await repo.delete_credential(cred_id)
    except ValueError:
        raise problem(409, "Conflict", "Credential is in use by switches")
    if not deleted:
        raise problem(404, "Not Found", "Credential not found")
    await session.commit()

    await runtime.audit_writer.record(
        user_id=actor.user_id,
        action="credential.delete",
        target_type="credential",
        target_id=str(cred_id),
        ip=request.client.host if request.client else None,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 4: Run credentials API tests**

```bash
rtk python -m pytest app_v4/tests/test_credentials_api.py -v
```

Expected: PASS, 4 tests.

- [ ] **Step 5: Run full suite**

```bash
rtk python -m pytest app_v4/tests -q
```

Expected: PASS, 40 tests.

- [ ] **Step 6: Commit**

```bash
rtk git add app_v4/service/api/credentials.py app_v4/tests/test_credentials_api.py
rtk git commit -m "feat: add v4 credentials CRUD API"
```

---

## Task 7: Add switches CRUD API

**Files:**
- Modify: `app_v4/service/api/switches.py`
- Test: `app_v4/tests/test_switches_api.py`

- [ ] **Step 1: Write failing switches API tests**

Create `app_v4/tests/test_switches_api.py`:

```python
import pytest
from fastapi.testclient import TestClient

from app_v4.data.repository import Repository
from app_v4.service.app import create_app
from app_v4.service.runtime import ServiceRuntime


def _admin_token(runtime: ServiceRuntime) -> str:
    return runtime.auth_service.issue_access_token(1, "admin", "admin")


def _viewer_token(runtime: ServiceRuntime) -> str:
    return runtime.auth_service.issue_access_token(2, "viewer", "viewer")


@pytest.mark.asyncio
async def test_create_switch(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s" * 32)
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential(name="lab", enc_blob=b"x")
        await session.commit()
        cred_id = cred.id

    client = TestClient(create_app(runtime))
    response = client.post(
        "/api/v1/switches",
        headers={"Authorization": f"Bearer {_admin_token(runtime)}"},
        json={
            "name": "sw01",
            "ip": "10.0.0.1",
            "protocol": "ssh",
            "port": 22,
            "credential_id": cred_id,
            "notes": "rack1",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "sw01"
    assert body["protocol"] == "ssh"
    assert body["credential"]["name"] == "lab"


@pytest.mark.asyncio
async def test_list_switches_visible_to_viewer(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s" * 32)
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential(name="lab", enc_blob=b"x")
        await repo.create_switch(name="sw01", ip="10.0.0.1", protocol="ssh", port=22, credential_id=cred.id)
        await session.commit()

    client = TestClient(create_app(runtime))
    response = client.get(
        "/api/v1/switches",
        headers={"Authorization": f"Bearer {_viewer_token(runtime)}"},
    )

    assert response.status_code == 200
    assert [s["name"] for s in response.json()] == ["sw01"]


@pytest.mark.asyncio
async def test_update_switch(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s" * 32)
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential(name="lab", enc_blob=b"x")
        sw = await repo.create_switch(name="sw01", ip="10.0.0.1", protocol="ssh", port=22, credential_id=cred.id)
        await session.commit()
        sw_id = sw.id

    client = TestClient(create_app(runtime))
    response = client.patch(
        f"/api/v1/switches/{sw_id}",
        headers={"Authorization": f"Bearer {_admin_token(runtime)}"},
        json={"ip": "10.0.0.99", "port": 2222, "notes": "updated"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ip"] == "10.0.0.99"
    assert body["port"] == 2222
    assert body["notes"] == "updated"


@pytest.mark.asyncio
async def test_delete_switch(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s" * 32)
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential(name="lab", enc_blob=b"x")
        sw = await repo.create_switch(name="sw01", ip="10.0.0.1", protocol="ssh", port=22, credential_id=cred.id)
        await session.commit()
        sw_id = sw.id

    client = TestClient(create_app(runtime))
    response = client.delete(
        f"/api/v1/switches/{sw_id}",
        headers={"Authorization": f"Bearer {_admin_token(runtime)}"},
    )

    assert response.status_code == 204
    async with session_factory() as session:
        repo = Repository(session)
        assert await repo.get_switch(sw_id) is None
```

- [ ] **Step 2: Run tests to verify failure**

```bash
rtk python -m pytest app_v4/tests/test_switches_api.py -v
```

Expected: FAIL with 404 (stub router).

- [ ] **Step 3: Implement switches router**

Replace `app_v4/service/api/switches.py` with:

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app_v4.core.auth_service import AccessClaims
from app_v4.data.repository import Repository
from app_v4.service.deps import get_db, get_runtime, require_role
from app_v4.service.problem import problem
from app_v4.service.runtime import ServiceRuntime

router = APIRouter(prefix="/switches", tags=["switches"])

VALID_PROTOCOLS = {"ssh", "telnet", "http", "https", "websmart", "websmart-v2"}


class CredentialRef(BaseModel):
    id: int
    name: str


class SwitchOut(BaseModel):
    id: int
    name: str
    ip: str
    protocol: str
    port: int
    notes: str | None
    credential: CredentialRef


class SwitchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    ip: str = Field(min_length=1, max_length=255)
    protocol: str = Field(min_length=1, max_length=20)
    port: int = Field(ge=1, le=65535)
    credential_id: int
    notes: str | None = None


class SwitchUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    ip: str | None = Field(default=None, min_length=1, max_length=255)
    protocol: str | None = Field(default=None, min_length=1, max_length=20)
    port: int | None = Field(default=None, ge=1, le=65535)
    credential_id: int | None = None
    notes: str | None = None


def _to_out(switch) -> SwitchOut:
    return SwitchOut(
        id=switch.id,
        name=switch.name,
        ip=switch.ip,
        protocol=switch.protocol,
        port=switch.port,
        notes=switch.notes,
        credential=CredentialRef(id=switch.credential.id, name=switch.credential.name),
    )


def _validate_protocol(protocol: str) -> None:
    if protocol not in VALID_PROTOCOLS:
        raise problem(
            422,
            "Unprocessable Entity",
            f"Unsupported protocol '{protocol}'. Must be one of {sorted(VALID_PROTOCOLS)}",
        )


@router.get("", response_model=list[SwitchOut])
async def list_switches(
    session: AsyncSession = Depends(get_db),
    _user: AccessClaims = Depends(require_role("admin", "operator", "viewer")),
) -> list[SwitchOut]:
    repo = Repository(session)
    return [_to_out(s) for s in await repo.list_switches()]


@router.post("", response_model=SwitchOut, status_code=status.HTTP_201_CREATED)
async def create_switch(
    payload: SwitchCreate,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    actor: AccessClaims = Depends(require_role("admin", "operator")),
) -> SwitchOut:
    _validate_protocol(payload.protocol)
    repo = Repository(session)
    if await repo.get_switch_by_name(payload.name) is not None:
        raise problem(409, "Conflict", "Switch name already exists")
    if await repo.get_credential(payload.credential_id) is None:
        raise problem(422, "Unprocessable Entity", "Referenced credential does not exist")

    switch = await repo.create_switch(
        name=payload.name,
        ip=payload.ip,
        protocol=payload.protocol,
        port=payload.port,
        credential_id=payload.credential_id,
        notes=payload.notes,
    )
    await session.commit()

    fresh = await repo.get_switch(switch.id)

    await runtime.audit_writer.record(
        user_id=actor.user_id,
        action="switch.create",
        target_type="switch",
        target_id=str(switch.id),
        ip=request.client.host if request.client else None,
        detail={"name": switch.name, "ip": switch.ip, "protocol": switch.protocol},
    )
    return _to_out(fresh)


@router.patch("/{switch_id}", response_model=SwitchOut)
async def update_switch(
    switch_id: int,
    payload: SwitchUpdate,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    actor: AccessClaims = Depends(require_role("admin", "operator")),
) -> SwitchOut:
    if payload.protocol is not None:
        _validate_protocol(payload.protocol)
    repo = Repository(session)
    if payload.credential_id is not None and await repo.get_credential(payload.credential_id) is None:
        raise problem(422, "Unprocessable Entity", "Referenced credential does not exist")

    updated = await repo.update_switch(
        switch_id,
        name=payload.name,
        ip=payload.ip,
        protocol=payload.protocol,
        port=payload.port,
        credential_id=payload.credential_id,
        notes=payload.notes,
    )
    if updated is None:
        raise problem(404, "Not Found", "Switch not found")
    await session.commit()
    fresh = await repo.get_switch(switch_id)

    await runtime.audit_writer.record(
        user_id=actor.user_id,
        action="switch.update",
        target_type="switch",
        target_id=str(switch_id),
        ip=request.client.host if request.client else None,
        detail=payload.model_dump(exclude_none=True),
    )
    return _to_out(fresh)


@router.delete("/{switch_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_switch(
    switch_id: int,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    actor: AccessClaims = Depends(require_role("admin", "operator")),
) -> Response:
    repo = Repository(session)
    deleted = await repo.delete_switch(switch_id)
    if not deleted:
        raise problem(404, "Not Found", "Switch not found")
    await session.commit()

    await runtime.audit_writer.record(
        user_id=actor.user_id,
        action="switch.delete",
        target_type="switch",
        target_id=str(switch_id),
        ip=request.client.host if request.client else None,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 4: Run switches API tests**

```bash
rtk python -m pytest app_v4/tests/test_switches_api.py -v
```

Expected: PASS, 4 tests.

- [ ] **Step 5: Run full suite**

```bash
rtk python -m pytest app_v4/tests -q
```

Expected: PASS, 44 tests.

- [ ] **Step 6: Commit**

```bash
rtk git add app_v4/service/api/switches.py app_v4/tests/test_switches_api.py
rtk git commit -m "feat: add v4 switches CRUD API"
```

---

## Task 8: Final verification

**Files:**
- Test: all `app_v4/tests/*.py`

- [ ] **Step 1: Run focused full suite**

```bash
rtk python -m pytest app_v4/tests -v
```

Expected: PASS, 44 tests across 13 test files.

- [ ] **Step 2: Smoke import all routers**

```bash
rtk python -c "from app_v4.service.app import create_app; from app_v4.cli import init_command; print('ok')"
```

Expected output:

```text
ok
```

- [ ] **Step 3: Smoke run init CLI in temp dir to confirm it works end-to-end**

```bash
rtk python -c "import asyncio, tempfile, pathlib; from app_v4.core.config import Settings; from app_v4.cli import init_command; from app_v4.core.dpapi import MemoryProtectionProvider; tmp = pathlib.Path(tempfile.mkdtemp()); res = asyncio.run(init_command(Settings(base_dir=tmp), 'mp', 'admin', 'AdminPass1!', MemoryProtectionProvider(secret=b'x'))); print(res['created_envelope'], res['created_admin'])"
```

Expected output:

```text
True True
```

- [ ] **Step 4: Confirm git state**

```bash
rtk git log --oneline main..HEAD
rtk git status
```

Expected: 7 new commits since branch start; no uncommitted changes other than possibly tracked test artifacts.

---

## Handoff Notes

After this plan, v4 backend has:

- `python -m app_v4 init --passphrase ... --admin-username ... --admin-password ...` to bootstrap envelope, master.key, and first admin user
- `AuditWriter` available on `ServiceRuntime.audit_writer` for endpoints to record changes
- Users CRUD: `GET/POST /api/v1/users`, `PATCH/DELETE /api/v1/users/{id}` (admin-only)
- Credentials CRUD: `GET/POST /api/v1/credentials`, `PATCH/DELETE /api/v1/credentials/{id}` (admin/operator); secrets encrypted via `CryptoService`
- Switches CRUD: `GET /api/v1/switches` (any role), `POST/PATCH/DELETE /api/v1/switches/{id}` (admin/operator)
- All mutating endpoints write `audit_log` rows

Plan B (next) should add:

- v3-compatible network configuration loader (paging indicators, prompts, retries)
- Async SSH (asyncssh), Telnet (asyncio streams), HTTP/WebSmart (aiohttp) clients
- Async backup runner with retry
- Backup execution endpoints, jobs CRUD
- APScheduler `AsyncIOScheduler` lifecycle + sync watcher
- Diff service port
