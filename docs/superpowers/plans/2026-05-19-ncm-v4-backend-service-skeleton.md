# NCM v4 Backend Service Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first working v4 backend foundation in `app_v4/`: FastAPI service, async SQLite database, DPAPI-protected key envelope, JWT auth, RBAC dependencies, WebSocket event hub, and tests.

**Architecture:** Keep v3 code in `app/` untouched. Build v4 in a new `app_v4/` package with clear boundaries: `core/` for security and config, `data/` for async SQLAlchemy, `service/` for FastAPI and runtime, `tests/` for v4 tests. Plan 1 creates a runnable backend skeleton; backup execution endpoints and UI pages come in later plans.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, SQLAlchemy 2 async, aiosqlite, Pydantic Settings, PyJWT, argon2-cffi, pywin32 DPAPI, pytest, pytest-asyncio, httpx/TestClient.

---

## File Structure

Create these files:

```text
app_v4/
├── __init__.py                         # v4 package version marker
├── core/
│   ├── __init__.py
│   ├── config.py                       # Settings dataclass via pydantic-settings
│   ├── paths.py                        # base/data/log/static path helpers
│   ├── dpapi.py                        # Windows DPAPI provider + test memory provider
│   ├── key_envelope.py                 # encrypted master passphrase + JWT secret storage
│   ├── crypto_service.py               # Fernet credential encryption using v3-compatible salt format
│   └── auth_service.py                 # argon2id password hashing + JWT issue/verify
├── data/
│   ├── __init__.py
│   ├── models.py                       # async SQLAlchemy ORM models for v3 + new auth/audit tables
│   ├── db.py                           # async engine/session factory/init/migration
│   └── repository.py                   # focused async repository for auth/bootstrap/system metrics
├── service/
│   ├── __init__.py
│   ├── app.py                          # FastAPI app factory
│   ├── runtime.py                      # service container lifecycle used by app and Windows service
│   ├── problem.py                      # RFC 7807-style error helper
│   ├── deps.py                         # FastAPI dependency injection + RBAC helpers
│   ├── events.py                       # EventHub for WebSocket clients
│   ├── main.py                         # uvicorn CLI entry
│   ├── windows_service.py              # Windows SCM wrapper for v4 backend service
│   └── api/
│       ├── __init__.py
│       ├── auth.py                     # login/refresh/logout/me endpoints
│       ├── system.py                   # status/metrics endpoints
│       └── ws.py                       # authenticated WebSocket endpoint
├── tests/
│   ├── __init__.py
│   ├── conftest.py                     # temp settings + async DB fixture
│   ├── test_db_init.py                 # schema + migration tests
│   ├── test_key_envelope.py            # DPAPI envelope tests using memory provider
│   ├── test_auth_service.py            # hash/JWT tests
│   ├── test_auth_api.py                # FastAPI auth route tests
│   ├── test_system_api.py              # system status/metrics tests
│   └── test_websocket.py               # WebSocket auth + broadcast tests
└── requirements-v4.txt                 # v4-only dependencies for development and CI
```

Modify these files:

```text
.gitignore                              # ignore app_v4 local DB/log/runtime files if needed
```

Do not modify `app/` in this plan.

---

## Task 1: Create v4 package scaffold and dependencies

**Files:**
- Create: `app_v4/__init__.py`
- Create: `app_v4/core/__init__.py`
- Create: `app_v4/data/__init__.py`
- Create: `app_v4/service/__init__.py`
- Create: `app_v4/service/api/__init__.py`
- Create: `app_v4/tests/__init__.py`
- Create: `app_v4/requirements-v4.txt`

- [ ] **Step 1: Write the dependency file**

Create `app_v4/requirements-v4.txt` with this content:

```text
fastapi>=0.128.0
uvicorn[standard]>=0.34.0
sqlalchemy>=2.0.36
aiosqlite>=0.20.0
pydantic>=2.10.0
pydantic-settings>=2.7.0
cryptography>=41.0.7
pyjwt>=2.10.0
argon2-cffi>=23.1.0
pywin32>=306
httpx>=0.28.0
pytest>=8.3.0
pytest-asyncio>=0.25.0
```

- [ ] **Step 2: Create package markers**

Create `app_v4/__init__.py`:

```python
"""NCM v4 backend, desktop, and web package."""

__version__ = "4.0.0-dev"
```

Create these empty marker files:

```text
app_v4/core/__init__.py
app_v4/data/__init__.py
app_v4/service/__init__.py
app_v4/service/api/__init__.py
app_v4/tests/__init__.py
```

- [ ] **Step 3: Run import smoke test**

Run:

```bash
rtk python -c "import app_v4; print(app_v4.__version__)"
```

Expected output contains:

```text
4.0.0-dev
```

- [ ] **Step 4: Commit**

```bash
rtk git add app_v4/__init__.py app_v4/core/__init__.py app_v4/data/__init__.py app_v4/service/__init__.py app_v4/service/api/__init__.py app_v4/tests/__init__.py app_v4/requirements-v4.txt
rtk git commit -m "chore: scaffold v4 backend package"
```

---

## Task 2: Add settings and path helpers

**Files:**
- Create: `app_v4/core/config.py`
- Create: `app_v4/core/paths.py`
- Test: `app_v4/tests/test_config_paths.py`

- [ ] **Step 1: Write failing tests**

Create `app_v4/tests/test_config_paths.py`:

```python
from pathlib import Path

from app_v4.core.config import Settings
from app_v4.core.paths import resolve_paths


def test_settings_defaults_to_local_backend_bind(tmp_path: Path):
    settings = Settings(base_dir=tmp_path)

    assert settings.service_host == "127.0.0.1"
    assert settings.service_port == 8443
    assert settings.database_url.endswith("/data/app.db")


def test_resolve_paths_creates_expected_locations(tmp_path: Path):
    settings = Settings(base_dir=tmp_path)
    paths = resolve_paths(settings)

    assert paths.base_dir == tmp_path
    assert paths.data_dir == tmp_path / "data"
    assert paths.logs_dir == tmp_path / "logs"
    assert paths.backups_dir == tmp_path / "backups"
    assert paths.static_dir == tmp_path / "app_v4" / "service" / "static"
    assert paths.master_envelope_file == tmp_path / "data" / "master.dpapi"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
rtk python -m pytest app_v4/tests/test_config_paths.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app_v4.core.config'`.

- [ ] **Step 3: Implement settings**

Create `app_v4/core/config.py`:

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

    @property
    def database_url(self) -> str:
        db_path = self.base_dir / "data" / "app.db"
        return f"sqlite+aiosqlite:///{db_path.as_posix()}"

    @property
    def service_url(self) -> str:
        return f"https://{self.service_host}:{self.service_port}"
```

Create `app_v4/core/paths.py`:

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


def resolve_paths(settings: Settings) -> AppPaths:
    base_dir = settings.base_dir
    return AppPaths(
        base_dir=base_dir,
        data_dir=base_dir / "data",
        logs_dir=base_dir / "logs",
        backups_dir=base_dir / "backups",
        static_dir=base_dir / "app_v4" / "service" / "static",
        master_envelope_file=base_dir / "data" / "master.dpapi",
        master_key_file=base_dir / "data" / "master.key",
    )
```

- [ ] **Step 4: Run tests**

```bash
rtk python -m pytest app_v4/tests/test_config_paths.py -v
```

Expected: PASS, 2 tests.

- [ ] **Step 5: Commit**

```bash
rtk git add app_v4/core/config.py app_v4/core/paths.py app_v4/tests/test_config_paths.py
rtk git commit -m "feat: add v4 settings and path helpers"
```

---

## Task 3: Add async SQLAlchemy models and database initialization

**Files:**
- Create: `app_v4/data/models.py`
- Create: `app_v4/data/db.py`
- Test: `app_v4/tests/test_db_init.py`

- [ ] **Step 1: Write failing database tests**

Create `app_v4/tests/test_db_init.py`:

```python
from pathlib import Path

import pytest
from sqlalchemy import text

from app_v4.core.config import Settings
from app_v4.data.db import create_session_factory, init_db


@pytest.mark.asyncio
async def test_init_db_creates_v3_and_v4_tables(tmp_path: Path):
    settings = Settings(base_dir=tmp_path)
    engine, session_factory = create_session_factory(settings)

    await init_db(engine)

    async with session_factory() as session:
        rows = await session.execute(
            text("select name from sqlite_master where type='table' order by name")
        )
        table_names = {row[0] for row in rows}

    await engine.dispose()

    assert "credentials" in table_names
    assert "switches" in table_names
    assert "backups" in table_names
    assert "jobs" in table_names
    assert "users" in table_names
    assert "sessions" in table_names
    assert "audit_log" in table_names


@pytest.mark.asyncio
async def test_init_db_adds_triggered_by_user_id_to_existing_backups(tmp_path: Path):
    settings = Settings(base_dir=tmp_path)
    engine, session_factory = create_session_factory(settings)

    async with engine.begin() as conn:
        await conn.execute(text("create table backups (id integer primary key, switch_id integer not null)"))

    await init_db(engine)

    async with session_factory() as session:
        rows = await session.execute(text("pragma table_info(backups)"))
        columns = {row[1] for row in rows}

    await engine.dispose()

    assert "triggered_by_user_id" in columns
```

- [ ] **Step 2: Run tests to verify failure**

```bash
rtk python -m pytest app_v4/tests/test_db_init.py -v
```

Expected: FAIL with missing `app_v4.data.db` or missing `create_session_factory`.

- [ ] **Step 3: Implement ORM models**

Create `app_v4/data/models.py`:

```python
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, LargeBinary, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Credential(Base):
    __tablename__ = "credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    enc_blob: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    switches: Mapped[list["Switch"]] = relationship(back_populates="credential")


class Switch(Base):
    __tablename__ = "switches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    ip: Mapped[str] = mapped_column(String(255), nullable=False)
    protocol: Mapped[str] = mapped_column(String(20), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    credential_id: Mapped[int] = mapped_column(ForeignKey("credentials.id"), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    credential: Mapped[Credential] = relationship(back_populates="switches")
    backups: Mapped[list["Backup"]] = relationship(back_populates="switch", cascade="all, delete-orphan")
    jobs: Mapped[list["Job"]] = relationship(back_populates="switch", cascade="all, delete-orphan")


class Backup(Base):
    __tablename__ = "backups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    switch_id: Mapped[int] = mapped_column(ForeignKey("switches.id"), nullable=False, index=True)
    taken_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    backup_type: Mapped[str] = mapped_column(String(20), default="manual", nullable=False)
    job_id: Mapped[Optional[int]] = mapped_column(ForeignKey("jobs.id"), nullable=True, index=True)
    triggered_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)

    switch: Mapped[Switch] = relationship(back_populates="backups")
    job: Mapped[Optional["Job"]] = relationship(foreign_keys=[job_id])
    triggered_by: Mapped[Optional["User"]] = relationship(foreign_keys=[triggered_by_user_id])


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    switch_id: Mapped[int] = mapped_column(ForeignKey("switches.id"), nullable=False, index=True)
    interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_ran_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    schedule_hour: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    schedule_minute: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    switch: Mapped[Switch] = relationship(back_populates="jobs")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    sessions: Mapped[list["Session"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped[User] = relationship(back_populates="sessions")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    target_type: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    target_id: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    ts: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False, index=True)
    detail_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
```

- [ ] **Step 4: Implement database helpers**

Create `app_v4/data/db.py`:

```python
from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app_v4.core.config import Settings
from app_v4.data.models import Base


def create_session_factory(settings: Settings) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        echo=False,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    return engine, session_factory


async def init_db(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _run_sqlite_migrations(conn)
        await conn.execute(text("pragma journal_mode=WAL"))
        await conn.execute(text("pragma foreign_keys=ON"))


async def _run_sqlite_migrations(conn) -> None:
    await _add_column_if_missing(conn, "backups", "triggered_by_user_id", "INTEGER")
    await conn.execute(text("create index if not exists ix_backups_triggered_by_user_id on backups (triggered_by_user_id)"))


async def _add_column_if_missing(conn, table_name: str, column_name: str, column_sql: str) -> None:
    rows = await conn.execute(text(f"pragma table_info({table_name})"))
    existing = {row[1] for row in rows}
    if column_name not in existing:
        await conn.execute(text(f"alter table {table_name} add column {column_name} {column_sql}"))


async def get_session(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session
```

- [ ] **Step 5: Run database tests**

```bash
rtk python -m pytest app_v4/tests/test_db_init.py -v
```

Expected: PASS, 2 tests.

- [ ] **Step 6: Commit**

```bash
rtk git add app_v4/data/models.py app_v4/data/db.py app_v4/tests/test_db_init.py
rtk git commit -m "feat: add async v4 database schema"
```

---

## Task 4: Add DPAPI key envelope storage

**Files:**
- Create: `app_v4/core/dpapi.py`
- Create: `app_v4/core/key_envelope.py`
- Test: `app_v4/tests/test_key_envelope.py`

- [ ] **Step 1: Write failing key envelope tests**

Create `app_v4/tests/test_key_envelope.py`:

```python
from pathlib import Path

import pytest

from app_v4.core.dpapi import MemoryProtectionProvider
from app_v4.core.key_envelope import KeyEnvelopeStore


def test_key_envelope_round_trip(tmp_path: Path):
    provider = MemoryProtectionProvider(secret=b"test-secret")
    store = KeyEnvelopeStore(path=tmp_path / "master.dpapi", provider=provider)

    created = store.create(master_passphrase="correct horse battery staple")
    loaded = store.load()

    assert created.master_passphrase == "correct horse battery staple"
    assert len(created.jwt_secret) == 32
    assert loaded.master_passphrase == created.master_passphrase
    assert loaded.jwt_secret == created.jwt_secret


def test_key_envelope_rejects_wrong_provider(tmp_path: Path):
    good_provider = MemoryProtectionProvider(secret=b"good")
    bad_provider = MemoryProtectionProvider(secret=b"bad")
    KeyEnvelopeStore(tmp_path / "master.dpapi", good_provider).create("passphrase")

    with pytest.raises(ValueError, match="Unable to decrypt master key envelope"):
        KeyEnvelopeStore(tmp_path / "master.dpapi", bad_provider).load()
```

- [ ] **Step 2: Run tests to verify failure**

```bash
rtk python -m pytest app_v4/tests/test_key_envelope.py -v
```

Expected: FAIL with missing `MemoryProtectionProvider`.

- [ ] **Step 3: Implement protection providers**

Create `app_v4/core/dpapi.py`:

```python
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol


class ProtectionProvider(Protocol):
    def protect(self, plaintext: bytes) -> bytes:
        raise NotImplementedError

    def unprotect(self, ciphertext: bytes) -> bytes:
        raise NotImplementedError


class WindowsDpapiProvider:
    def protect(self, plaintext: bytes) -> bytes:
        import win32crypt

        return win32crypt.CryptProtectData(
            plaintext,
            "ncm-v4-master-envelope",
            None,
            None,
            None,
            0,
        )

    def unprotect(self, ciphertext: bytes) -> bytes:
        import win32crypt

        _description, plaintext = win32crypt.CryptUnprotectData(ciphertext, None, None, None, 0)
        return plaintext


@dataclass(frozen=True)
class MemoryProtectionProvider:
    secret: bytes

    def protect(self, plaintext: bytes) -> bytes:
        mask = self._mask(len(plaintext))
        return bytes(value ^ mask[index] for index, value in enumerate(plaintext))

    def unprotect(self, ciphertext: bytes) -> bytes:
        mask = self._mask(len(ciphertext))
        return bytes(value ^ mask[index] for index, value in enumerate(ciphertext))

    def _mask(self, length: int) -> bytes:
        chunks: list[bytes] = []
        counter = 0
        while sum(len(chunk) for chunk in chunks) < length:
            chunks.append(hashlib.sha256(self.secret + counter.to_bytes(4, "big")).digest())
            counter += 1
        return b"".join(chunks)[:length]
```

- [ ] **Step 4: Implement key envelope store**

Create `app_v4/core/key_envelope.py`:

```python
from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path

from app_v4.core.dpapi import ProtectionProvider


@dataclass(frozen=True)
class KeyEnvelope:
    master_passphrase: str
    jwt_secret: bytes
    version: int = 1


class KeyEnvelopeStore:
    def __init__(self, path: Path, provider: ProtectionProvider):
        self.path = path
        self.provider = provider

    def create(self, master_passphrase: str) -> KeyEnvelope:
        envelope = KeyEnvelope(master_passphrase=master_passphrase, jwt_secret=os.urandom(32))
        self.save(envelope)
        return envelope

    def save(self, envelope: KeyEnvelope) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": envelope.version,
            "master_passphrase": envelope.master_passphrase,
            "jwt_secret_b64": base64.urlsafe_b64encode(envelope.jwt_secret).decode("ascii"),
        }
        plaintext = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        ciphertext = self.provider.protect(plaintext)
        self.path.write_bytes(ciphertext)

    def load(self) -> KeyEnvelope:
        try:
            ciphertext = self.path.read_bytes()
            plaintext = self.provider.unprotect(ciphertext)
            payload = json.loads(plaintext.decode("utf-8"))
            return KeyEnvelope(
                version=int(payload["version"]),
                master_passphrase=str(payload["master_passphrase"]),
                jwt_secret=base64.urlsafe_b64decode(payload["jwt_secret_b64"].encode("ascii")),
            )
        except Exception as exc:
            raise ValueError("Unable to decrypt master key envelope") from exc
```

- [ ] **Step 5: Run key envelope tests**

```bash
rtk python -m pytest app_v4/tests/test_key_envelope.py -v
```

Expected: PASS, 2 tests.

- [ ] **Step 6: Commit**

```bash
rtk git add app_v4/core/dpapi.py app_v4/core/key_envelope.py app_v4/tests/test_key_envelope.py
rtk git commit -m "feat: add DPAPI-backed key envelope"
```

---

## Task 5: Add v4 CryptoService compatible with v3 credentials

**Files:**
- Create: `app_v4/core/crypto_service.py`
- Test: `app_v4/tests/test_crypto_service.py`

- [ ] **Step 1: Write failing crypto tests**

Create `app_v4/tests/test_crypto_service.py`:

```python
from pathlib import Path

from app_v4.core.config import Settings
from app_v4.core.crypto_service import CryptoService


def test_crypto_service_round_trips_credentials(tmp_path: Path):
    settings = Settings(base_dir=tmp_path)
    crypto = CryptoService(settings=settings, passphrase="correct horse battery staple")

    blob = crypto.encrypt_credential("admin", "secret", "enable")
    decrypted = crypto.decrypt_credential(blob)

    assert decrypted == {
        "username": "admin",
        "password": "secret",
        "enable_password": "enable",
    }


def test_crypto_service_rejects_wrong_passphrase(tmp_path: Path):
    settings = Settings(base_dir=tmp_path)
    CryptoService(settings=settings, passphrase="first passphrase")

    try:
        CryptoService(settings=settings, passphrase="second passphrase")
    except ValueError as exc:
        assert "Invalid master passphrase" in str(exc)
    else:
        raise AssertionError("wrong passphrase accepted")
```

- [ ] **Step 2: Run tests to verify failure**

```bash
rtk python -m pytest app_v4/tests/test_crypto_service.py -v
```

Expected: FAIL with missing `app_v4.core.crypto_service`.

- [ ] **Step 3: Implement CryptoService**

Create `app_v4/core/crypto_service.py`:

```python
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app_v4.core.config import Settings
from app_v4.core.paths import resolve_paths


class CryptoService:
    def __init__(self, settings: Settings, passphrase: str):
        self.settings = settings
        self.paths = resolve_paths(settings)
        self.salt = self._get_or_create_salt()
        self.cipher = self._derive_cipher(passphrase)
        self._validate_passphrase()

    def encrypt_credential(self, username: str, password: str, enable_password: str = "") -> bytes:
        payload = {
            "username": username,
            "password": password,
            "enable_password": enable_password,
        }
        return self.cipher.encrypt(json.dumps(payload, separators=(",", ":")).encode("utf-8"))

    def decrypt_credential(self, enc_blob: bytes) -> dict[str, str]:
        try:
            plaintext = self.cipher.decrypt(enc_blob)
            payload: dict[str, Any] = json.loads(plaintext.decode("utf-8"))
            return {
                "username": str(payload["username"]),
                "password": str(payload["password"]),
                "enable_password": str(payload.get("enable_password", "")),
            }
        except Exception as exc:
            raise ValueError("Invalid credentials or wrong passphrase") from exc

    def _get_or_create_salt(self) -> bytes:
        self.paths.data_dir.mkdir(parents=True, exist_ok=True)
        key_file = self.paths.master_key_file
        if key_file.exists():
            return key_file.read_bytes()[:16]
        salt = os.urandom(16)
        key_file.write_bytes(salt)
        return salt

    def _derive_cipher(self, passphrase: str) -> Fernet:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            iterations=100_000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))
        return Fernet(key)

    def _validate_passphrase(self) -> None:
        key_file = self.paths.master_key_file
        test_token = b"VALID_PASSPHRASE_TEST_TOKEN"
        content = key_file.read_bytes()
        if len(content) > 16:
            encrypted_token = content[16:]
            try:
                decrypted = self.cipher.decrypt(encrypted_token)
            except Exception as exc:
                raise ValueError("Invalid master passphrase") from exc
            if decrypted != test_token:
                raise ValueError("Invalid master passphrase")
            return
        encrypted_token = self.cipher.encrypt(test_token)
        key_file.write_bytes(self.salt + encrypted_token)
```

- [ ] **Step 4: Run crypto tests**

```bash
rtk python -m pytest app_v4/tests/test_crypto_service.py -v
```

Expected: PASS, 2 tests.

- [ ] **Step 5: Commit**

```bash
rtk git add app_v4/core/crypto_service.py app_v4/tests/test_crypto_service.py
rtk git commit -m "feat: add v4 credential crypto service"
```

---

## Task 6: Add repository bootstrap for users and sessions

**Files:**
- Create: `app_v4/data/repository.py`
- Test: `app_v4/tests/conftest.py`
- Test: `app_v4/tests/test_repository.py`

- [ ] **Step 1: Create shared test fixtures**

Create `app_v4/tests/conftest.py`:

```python
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app_v4.core.config import Settings
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
```

- [ ] **Step 2: Write failing repository tests**

Create `app_v4/tests/test_repository.py`:

```python
import pytest

from app_v4.data.repository import Repository


@pytest.mark.asyncio
async def test_bootstrap_admin_creates_first_user(session_factory):
    async with session_factory() as session:
        repo = Repository(session)
        user = await repo.create_user(username="admin", password_hash="hashed", role="admin")
        await session.commit()

    async with session_factory() as session:
        repo = Repository(session)
        loaded = await repo.get_user_by_username("admin")

    assert user.id is not None
    assert loaded is not None
    assert loaded.username == "admin"
    assert loaded.role == "admin"


@pytest.mark.asyncio
async def test_session_lifecycle(session_factory):
    async with session_factory() as session:
        repo = Repository(session)
        user = await repo.create_user("operator", "hash", "operator")
        session_row = await repo.create_session(
            user_id=user.id,
            refresh_token_hash="refresh-hash",
            ip="10.0.0.5",
            user_agent="pytest",
            days_valid=7,
        )
        await session.commit()

    async with session_factory() as session:
        repo = Repository(session)
        loaded = await repo.get_session_by_refresh_hash("refresh-hash")
        await repo.revoke_session(session_row.id)
        await session.commit()

    assert loaded is not None
    assert loaded.user_id == user.id
```

- [ ] **Step 3: Run tests to verify failure**

```bash
rtk python -m pytest app_v4/tests/test_repository.py -v
```

Expected: FAIL with missing `Repository`.

- [ ] **Step 4: Implement repository**

Create `app_v4/data/repository.py`:

```python
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app_v4.data.models import Backup, Job, Session, Switch, User


class Repository:
    def __init__(self, session: AsyncSession):
        self.session = session

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

    async def mark_user_login(self, user_id: int) -> None:
        user = await self.get_user_by_id(user_id)
        if user is not None:
            user.last_login_at = datetime.utcnow()

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

    async def count_users(self) -> int:
        result = await self.session.execute(select(func.count(User.id)))
        return int(result.scalar_one())

    async def system_metrics(self) -> dict[str, int]:
        switches = await self.session.execute(select(func.count(Switch.id)))
        backups = await self.session.execute(select(func.count(Backup.id)))
        jobs = await self.session.execute(select(func.count(Job.id)))
        failed = await self.session.execute(select(func.count(Backup.id)).where(Backup.success.is_(False)))
        return {
            "switches": int(switches.scalar_one()),
            "backups": int(backups.scalar_one()),
            "jobs": int(jobs.scalar_one()),
            "failed_backups": int(failed.scalar_one()),
        }


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
```

- [ ] **Step 5: Run repository tests**

```bash
rtk python -m pytest app_v4/tests/test_repository.py -v
```

Expected: PASS, 2 tests.

- [ ] **Step 6: Commit**

```bash
rtk git add app_v4/tests/conftest.py app_v4/tests/test_repository.py app_v4/data/repository.py
rtk git commit -m "feat: add v4 async repository"
```

---

## Task 7: Add AuthService password hashing and JWT support

**Files:**
- Create: `app_v4/core/auth_service.py`
- Test: `app_v4/tests/test_auth_service.py`

- [ ] **Step 1: Write failing auth service tests**

Create `app_v4/tests/test_auth_service.py`:

```python
from datetime import datetime, timedelta, timezone

import pytest

from app_v4.core.auth_service import AuthService, TokenError
from app_v4.core.config import Settings


def test_password_hash_verification():
    service = AuthService(settings=Settings(), jwt_secret=b"x" * 32)

    password_hash = service.hash_password("StrongPassword123!")

    assert password_hash != "StrongPassword123!"
    assert service.verify_password("StrongPassword123!", password_hash) is True
    assert service.verify_password("wrong", password_hash) is False


def test_access_token_round_trip():
    service = AuthService(settings=Settings(), jwt_secret=b"y" * 32)

    token = service.issue_access_token(user_id=7, username="admin", role="admin")
    claims = service.verify_access_token(token)

    assert claims.user_id == 7
    assert claims.username == "admin"
    assert claims.role == "admin"


def test_invalid_token_raises_token_error():
    service = AuthService(settings=Settings(), jwt_secret=b"z" * 32)

    with pytest.raises(TokenError):
        service.verify_access_token("not-a-token")
```

- [ ] **Step 2: Run tests to verify failure**

```bash
rtk python -m pytest app_v4/tests/test_auth_service.py -v
```

Expected: FAIL with missing `AuthService`.

- [ ] **Step 3: Implement AuthService**

Create `app_v4/core/auth_service.py`:

```python
from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError

from app_v4.core.config import Settings


class TokenError(ValueError):
    pass


@dataclass(frozen=True)
class AccessClaims:
    user_id: int
    username: str
    role: str
    expires_at: datetime


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AuthService:
    def __init__(self, settings: Settings, jwt_secret: bytes):
        self.settings = settings
        self.jwt_secret = jwt_secret
        self.password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)

    def hash_password(self, password: str) -> str:
        return self.password_hasher.hash(password)

    def verify_password(self, password: str, password_hash: str) -> bool:
        try:
            return bool(self.password_hasher.verify(password_hash, password))
        except (VerifyMismatchError, VerificationError):
            return False

    def issue_access_token(self, user_id: int, username: str, role: str) -> str:
        now = datetime.now(timezone.utc)
        exp = now + timedelta(minutes=self.settings.jwt_access_minutes)
        payload = {
            "sub": str(user_id),
            "username": username,
            "role": role,
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
            "typ": "access",
        }
        return jwt.encode(payload, self.jwt_secret, algorithm="HS256")

    def verify_access_token(self, token: str) -> AccessClaims:
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
        except jwt.PyJWTError as exc:
            raise TokenError("Invalid access token") from exc
        if payload.get("typ") != "access":
            raise TokenError("Invalid token type")
        return AccessClaims(
            user_id=int(payload["sub"]),
            username=str(payload["username"]),
            role=str(payload["role"]),
            expires_at=datetime.fromtimestamp(int(payload["exp"]), tz=timezone.utc),
        )

    def issue_token_pair(self, user_id: int, username: str, role: str) -> TokenPair:
        return TokenPair(
            access_token=self.issue_access_token(user_id, username, role),
            refresh_token=secrets.token_urlsafe(48),
        )
```

- [ ] **Step 4: Run auth service tests**

```bash
rtk python -m pytest app_v4/tests/test_auth_service.py -v
```

Expected: PASS, 3 tests.

- [ ] **Step 5: Commit**

```bash
rtk git add app_v4/core/auth_service.py app_v4/tests/test_auth_service.py
rtk git commit -m "feat: add v4 auth service"
```

---

## Task 8: Add FastAPI runtime, dependency injection, and problem responses

**Files:**
- Create: `app_v4/service/runtime.py`
- Create: `app_v4/service/problem.py`
- Create: `app_v4/service/deps.py`
- Create: `app_v4/service/app.py`
- Test: `app_v4/tests/test_app_factory.py`

- [ ] **Step 1: Write failing app factory test**

Create `app_v4/tests/test_app_factory.py`:

```python
import pytest
from fastapi.testclient import TestClient

from app_v4.service.app import create_app
from app_v4.service.runtime import ServiceRuntime


@pytest.mark.asyncio
async def test_app_factory_exposes_openapi(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory=session_factory, jwt_secret=b"a" * 32)
    app = create_app(runtime)
    client = TestClient(app)

    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"] == "NCM v4 Backend"
```

- [ ] **Step 2: Run test to verify failure**

```bash
rtk python -m pytest app_v4/tests/test_app_factory.py -v
```

Expected: FAIL with missing `create_app` or `ServiceRuntime`.

- [ ] **Step 3: Implement problem response helper**

Create `app_v4/service/problem.py`:

```python
from __future__ import annotations

from fastapi import HTTPException


def problem(status_code: int, title: str, detail: str, type_: str = "about:blank") -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "type": type_,
            "title": title,
            "status": status_code,
            "detail": detail,
        },
    )
```

- [ ] **Step 4: Create event hub skeleton for runtime imports**

Create `app_v4/service/events.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fastapi import WebSocket


@dataclass
class EventMessage:
    type: str
    payload: dict[str, Any]
    ts: str


class EventHub:
    def __init__(self):
        self._clients: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._clients.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._clients.discard(websocket)

    async def send(self, websocket: WebSocket, event_type: str, payload: dict[str, Any]) -> None:
        await websocket.send_json(self._message(event_type, payload).__dict__)

    async def broadcast(self, event_type: str, payload: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        message = self._message(event_type, payload).__dict__
        for websocket in list(self._clients):
            try:
                await websocket.send_json(message)
            except Exception:
                dead.append(websocket)
        for websocket in dead:
            self.disconnect(websocket)

    def _message(self, event_type: str, payload: dict[str, Any]) -> EventMessage:
        return EventMessage(type=event_type, payload=payload, ts=datetime.utcnow().isoformat() + "Z")
```

- [ ] **Step 5: Implement runtime container**

Create `app_v4/service/runtime.py`:

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
from app_v4.service.events import EventHub


@dataclass
class ServiceRuntime:
    settings: Settings
    session_factory: async_sessionmaker[AsyncSession]
    auth_service: AuthService
    event_hub: EventHub
    crypto_service: CryptoService | None = None
    started_at: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def for_tests(
        cls,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        jwt_secret: bytes,
    ) -> "ServiceRuntime":
        return cls(
            settings=settings,
            session_factory=session_factory,
            auth_service=AuthService(settings=settings, jwt_secret=jwt_secret),
            event_hub=EventHub(),
            crypto_service=None,
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
        crypto_service=crypto,
    )
    return runtime, engine
```

- [ ] **Step 6: Implement dependency helpers**

Create `app_v4/service/deps.py`:

```python
from __future__ import annotations

from collections.abc import AsyncIterator, Callable

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app_v4.core.auth_service import AccessClaims, TokenError
from app_v4.service.problem import problem
from app_v4.service.runtime import ServiceRuntime

bearer = HTTPBearer(auto_error=False)


def get_runtime(request: Request) -> ServiceRuntime:
    return request.app.state.runtime


async def get_db(runtime: ServiceRuntime = Depends(get_runtime)) -> AsyncIterator[AsyncSession]:
    async with runtime.session_factory() as session:
        yield session


def require_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    runtime: ServiceRuntime = Depends(get_runtime),
) -> AccessClaims:
    if credentials is None:
        raise problem(401, "Unauthorized", "Missing bearer token")
    try:
        return runtime.auth_service.verify_access_token(credentials.credentials)
    except TokenError:
        raise problem(401, "Unauthorized", "Invalid bearer token")


def require_role(*allowed_roles: str) -> Callable[[AccessClaims], AccessClaims]:
    def dependency(user: AccessClaims = Depends(require_user)) -> AccessClaims:
        if user.role not in allowed_roles:
            raise problem(403, "Forbidden", "User role is not permitted for this operation")
        return user

    return dependency
```

- [ ] **Step 7: Implement app factory**

Create `app_v4/service/app.py`:

```python
from __future__ import annotations

from fastapi import FastAPI

from app_v4.service.runtime import ServiceRuntime


def create_app(runtime: ServiceRuntime) -> FastAPI:
    app = FastAPI(title="NCM v4 Backend", version="4.0.0-dev")
    app.state.runtime = runtime

    from app_v4.service.api import auth, system, ws

    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(system.router, prefix="/api/v1")
    app.include_router(ws.router)
    return app
```

- [ ] **Step 8: Add temporary empty routers so app factory imports**

Create `app_v4/service/api/auth.py`:

```python
from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])
```

Create `app_v4/service/api/system.py`:

```python
from fastapi import APIRouter

router = APIRouter(prefix="/system", tags=["system"])
```

Create `app_v4/service/api/ws.py`:

```python
from fastapi import APIRouter

router = APIRouter(tags=["websocket"])
```

- [ ] **Step 9: Run app factory test**

```bash
rtk python -m pytest app_v4/tests/test_app_factory.py -v
```

Expected: PASS, 1 test.

- [ ] **Step 10: Commit**

```bash
rtk git add app_v4/service/events.py app_v4/service/runtime.py app_v4/service/problem.py app_v4/service/deps.py app_v4/service/app.py app_v4/service/api/auth.py app_v4/service/api/system.py app_v4/service/api/ws.py app_v4/tests/test_app_factory.py
rtk git commit -m "feat: add v4 FastAPI app factory"
```

---

## Task 9: Add auth API endpoints

**Files:**
- Modify: `app_v4/service/api/auth.py`
- Test: `app_v4/tests/test_auth_api.py`

- [ ] **Step 1: Write failing auth API tests**

Create `app_v4/tests/test_auth_api.py`:

```python
import pytest
from fastapi.testclient import TestClient

from app_v4.data.repository import Repository, hash_refresh_token
from app_v4.service.app import create_app
from app_v4.service.runtime import ServiceRuntime


@pytest.mark.asyncio
async def test_login_returns_token_pair(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"b" * 32)
    password_hash = runtime.auth_service.hash_password("StrongPassword123!")
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_user("admin", password_hash, "admin")
        await session.commit()

    client = TestClient(create_app(runtime))
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "StrongPassword123!"},
        headers={"user-agent": "pytest"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]


@pytest.mark.asyncio
async def test_me_requires_bearer_token(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"c" * 32)
    token = runtime.auth_service.issue_access_token(user_id=1, username="viewer", role="viewer")
    client = TestClient(create_app(runtime))

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {"user_id": 1, "username": "viewer", "role": "viewer"}


@pytest.mark.asyncio
async def test_refresh_rotates_refresh_token(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"h" * 32)
    password_hash = runtime.auth_service.hash_password("StrongPassword123!")
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_user("admin", password_hash, "admin")
        await session.commit()

    client = TestClient(create_app(runtime))
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "StrongPassword123!"},
    )
    refresh_token = login_response.json()["refresh_token"]

    refresh_response = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})

    assert refresh_response.status_code == 200
    body = refresh_response.json()
    assert body["access_token"]
    assert body["refresh_token"] != refresh_token


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"i" * 32)
    password_hash = runtime.auth_service.hash_password("StrongPassword123!")
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_user("admin", password_hash, "admin")
        await session.commit()

    client = TestClient(create_app(runtime))
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "StrongPassword123!"},
    )
    refresh_token = login_response.json()["refresh_token"]

    logout_response = client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})

    assert logout_response.status_code == 204
    async with session_factory() as session:
        repo = Repository(session)
        session_row = await repo.get_session_by_refresh_hash(hash_refresh_token(refresh_token))
    assert session_row is not None
    assert session_row.revoked is True
```

- [ ] **Step 2: Run tests to verify failure**

```bash
rtk python -m pytest app_v4/tests/test_auth_api.py -v
```

Expected: FAIL because `/api/v1/auth/login` returns 404.

- [ ] **Step 3: Implement auth routes**

Replace `app_v4/service/api/auth.py` with:

```python
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel
from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app_v4.core.auth_service import AccessClaims, TokenPair
from app_v4.data.repository import Repository, hash_refresh_token
from app_v4.service.deps import get_db, get_runtime, require_user
from app_v4.service.problem import problem
from app_v4.service.runtime import ServiceRuntime

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class MeResponse(BaseModel):
    user_id: int
    username: str
    role: str


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
) -> LoginResponse:
    repo = Repository(session)
    user = await repo.get_user_by_username(payload.username)
    if user is None or not user.is_active:
        raise problem(401, "Unauthorized", "Invalid username or password")
    if not runtime.auth_service.verify_password(payload.password, user.password_hash):
        raise problem(401, "Unauthorized", "Invalid username or password")

    tokens: TokenPair = runtime.auth_service.issue_token_pair(user.id, user.username, user.role)
    await repo.create_session(
        user_id=user.id,
        refresh_token_hash=hash_refresh_token(tokens.refresh_token),
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        days_valid=runtime.settings.jwt_refresh_days,
    )
    await repo.mark_user_login(user.id)
    await session.commit()
    return LoginResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
    )


@router.post("/refresh", response_model=LoginResponse)
async def refresh(
    payload: RefreshRequest,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
) -> LoginResponse:
    repo = Repository(session)
    current = await repo.get_session_by_refresh_hash(hash_refresh_token(payload.refresh_token))
    if current is None or current.revoked or current.expires_at <= datetime.utcnow():
        raise problem(401, "Unauthorized", "Invalid refresh token")
    user = await repo.get_user_by_id(current.user_id)
    if user is None or not user.is_active:
        raise problem(401, "Unauthorized", "Invalid refresh token")

    await repo.revoke_session(current.id)
    tokens: TokenPair = runtime.auth_service.issue_token_pair(user.id, user.username, user.role)
    await repo.create_session(
        user_id=user.id,
        refresh_token_hash=hash_refresh_token(tokens.refresh_token),
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        days_valid=runtime.settings.jwt_refresh_days,
    )
    await session.commit()
    return LoginResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: LogoutRequest,
    session: AsyncSession = Depends(get_db),
) -> Response:
    repo = Repository(session)
    current = await repo.get_session_by_refresh_hash(hash_refresh_token(payload.refresh_token))
    if current is not None:
        await repo.revoke_session(current.id)
        await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=MeResponse)
async def me(user: AccessClaims = Depends(require_user)) -> MeResponse:
    return MeResponse(user_id=user.user_id, username=user.username, role=user.role)
```

- [ ] **Step 4: Run auth API tests**

```bash
rtk python -m pytest app_v4/tests/test_auth_api.py -v
```

Expected: PASS, 4 tests.

- [ ] **Step 5: Commit**

```bash
rtk git add app_v4/service/api/auth.py app_v4/tests/test_auth_api.py
rtk git commit -m "feat: add v4 auth API"
```

---

## Task 10: Add system status and metrics endpoints

**Files:**
- Modify: `app_v4/service/runtime.py`
- Modify: `app_v4/service/api/system.py`
- Test: `app_v4/tests/test_system_api.py`

- [ ] **Step 1: Write failing system API tests**

Create `app_v4/tests/test_system_api.py`:

```python
import pytest
from fastapi.testclient import TestClient

from app_v4.service.app import create_app
from app_v4.service.runtime import ServiceRuntime


@pytest.mark.asyncio
async def test_system_status_requires_viewer_role(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"d" * 32)
    token = runtime.auth_service.issue_access_token(1, "viewer", "viewer")
    client = TestClient(create_app(runtime))

    response = client.get("/api/v1/system/status", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["service"] == "running"
    assert response.json()["version"] == "4.0.0-dev"


@pytest.mark.asyncio
async def test_system_metrics_requires_auth(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"e" * 32)
    client = TestClient(create_app(runtime))

    response = client.get("/api/v1/system/metrics")

    assert response.status_code == 401
```

- [ ] **Step 2: Run tests to verify failure**

```bash
rtk python -m pytest app_v4/tests/test_system_api.py -v
```

Expected: FAIL because `/api/v1/system/status` returns 404.

- [ ] **Step 3: Confirm runtime start time field exists**

`ServiceRuntime.started_at` was added in Task 8 using `field(default_factory=datetime.utcnow)`. Confirm `app_v4/service/runtime.py` contains this field. No code change is expected in this step.

- [ ] **Step 4: Implement system routes**

Replace `app_v4/service/api/system.py` with:

```python
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app_v4 import __version__
from app_v4.core.auth_service import AccessClaims
from app_v4.data.repository import Repository
from app_v4.service.deps import get_db, get_runtime, require_role
from app_v4.service.runtime import ServiceRuntime

router = APIRouter(prefix="/system", tags=["system"])


class StatusResponse(BaseModel):
    service: str
    version: str
    started_at: datetime
    host: str
    port: int


class MetricsResponse(BaseModel):
    switches: int
    backups: int
    jobs: int
    failed_backups: int


@router.get("/status", response_model=StatusResponse)
async def status(
    runtime: ServiceRuntime = Depends(get_runtime),
    _user: AccessClaims = Depends(require_role("admin", "operator", "viewer")),
) -> StatusResponse:
    return StatusResponse(
        service="running",
        version=__version__,
        started_at=runtime.started_at,
        host=runtime.settings.service_host,
        port=runtime.settings.service_port,
    )


@router.get("/metrics", response_model=MetricsResponse)
async def metrics(
    session: AsyncSession = Depends(get_db),
    _user: AccessClaims = Depends(require_role("admin", "operator", "viewer")),
) -> MetricsResponse:
    repo = Repository(session)
    values = await repo.system_metrics()
    return MetricsResponse(**values)
```

- [ ] **Step 5: Run system API tests**

```bash
rtk python -m pytest app_v4/tests/test_system_api.py -v
```

Expected: PASS, 2 tests.

- [ ] **Step 6: Commit**

```bash
rtk git add app_v4/service/runtime.py app_v4/service/api/system.py app_v4/tests/test_system_api.py
rtk git commit -m "feat: add v4 system API"
```

---

## Task 11: Add WebSocket event hub

**Files:**
- Modify: `app_v4/service/events.py`
- Modify: `app_v4/service/api/ws.py`
- Test: `app_v4/tests/test_websocket.py`

- [ ] **Step 1: Write failing WebSocket tests**

Create `app_v4/tests/test_websocket.py`:

```python
import pytest
from fastapi.testclient import TestClient

from app_v4.service.app import create_app
from app_v4.service.runtime import ServiceRuntime


@pytest.mark.asyncio
async def test_websocket_requires_valid_token(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"f" * 32)
    client = TestClient(create_app(runtime))

    try:
        with client.websocket_connect("/ws?token=bad"):
            raise AssertionError("websocket accepted bad token")
    except Exception as exc:
        assert "1008" in str(exc) or "WebSocketDisconnect" in type(exc).__name__


@pytest.mark.asyncio
async def test_websocket_sends_ready_event(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"g" * 32)
    token = runtime.auth_service.issue_access_token(1, "viewer", "viewer")
    client = TestClient(create_app(runtime))

    with client.websocket_connect(f"/ws?token={token}") as websocket:
        data = websocket.receive_json()

    assert data["type"] == "connected"
    assert data["payload"] == {"user": "viewer", "role": "viewer"}
```

- [ ] **Step 2: Run tests to verify failure**

```bash
rtk python -m pytest app_v4/tests/test_websocket.py -v
```

Expected: FAIL because `/ws` is missing.

- [ ] **Step 3: Confirm event hub already exists**

`app_v4/service/events.py` was created in Task 8 because `ServiceRuntime` imports `EventHub`. Confirm the file still contains `EventHub.connect()`, `EventHub.disconnect()`, `EventHub.send()`, and `EventHub.broadcast()` exactly as added in Task 8. No code change is expected in this step.

- [ ] **Step 4: Implement WebSocket route**

Replace `app_v4/service/api/ws.py` with:

```python
from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app_v4.core.auth_service import TokenError

router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def websocket_events(websocket: WebSocket) -> None:
    runtime = websocket.app.state.runtime
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return
    try:
        claims = runtime.auth_service.verify_access_token(token)
    except TokenError:
        await websocket.close(code=1008)
        return

    await runtime.event_hub.connect(websocket)
    try:
        await runtime.event_hub.send(websocket, "connected", {"user": claims.username, "role": claims.role})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        runtime.event_hub.disconnect(websocket)
```

- [ ] **Step 5: Run WebSocket tests**

```bash
rtk python -m pytest app_v4/tests/test_websocket.py -v
```

Expected: PASS, 2 tests.

- [ ] **Step 6: Commit**

```bash
rtk git add app_v4/service/events.py app_v4/service/api/ws.py app_v4/tests/test_websocket.py
rtk git commit -m "feat: add v4 websocket event hub"
```

---

## Task 12: Add CLI entry and Windows service wrapper

**Files:**
- Create: `app_v4/service/main.py`
- Create: `app_v4/service/windows_service.py`
- Test: `app_v4/tests/test_service_entrypoints.py`

- [ ] **Step 1: Write failing entrypoint tests**

Create `app_v4/tests/test_service_entrypoints.py`:

```python
from app_v4.service.main import app_import_string, uvicorn_kwargs


def test_uvicorn_import_string_is_stable():
    assert app_import_string() == "app_v4.service.main:create_runtime_app"


def test_uvicorn_kwargs_uses_settings(test_settings):
    kwargs = uvicorn_kwargs(test_settings)

    assert kwargs["host"] == "127.0.0.1"
    assert kwargs["port"] == 8443
    assert kwargs["factory"] is True
```

- [ ] **Step 2: Run tests to verify failure**

```bash
rtk python -m pytest app_v4/tests/test_service_entrypoints.py -v
```

Expected: FAIL with missing `app_v4.service.main`.

- [ ] **Step 3: Implement uvicorn entrypoint**

Create `app_v4/service/main.py`:

```python
from __future__ import annotations

import asyncio
import threading
from typing import TypeVar

import uvicorn
from fastapi import FastAPI

from app_v4.core.config import Settings
from app_v4.service.app import create_app
from app_v4.service.runtime import build_runtime

T = TypeVar("T")
_runtime_engine = None


def app_import_string() -> str:
    return "app_v4.service.main:create_runtime_app"


def uvicorn_kwargs(settings: Settings) -> dict[str, object]:
    return {
        "app": app_import_string(),
        "host": settings.service_host,
        "port": settings.service_port,
        "factory": True,
        "log_level": "info",
    }


def _run_async_from_sync(coro) -> T:
    result: list[T] = []
    errors: list[BaseException] = []

    def runner() -> None:
        try:
            result.append(asyncio.run(coro))
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=runner)
    thread.start()
    thread.join()
    if errors:
        raise errors[0]
    return result[0]


async def _create_runtime_app_async() -> FastAPI:
    global _runtime_engine
    settings = Settings()
    runtime, engine = await build_runtime(settings)
    _runtime_engine = engine
    return create_app(runtime)


def create_runtime_app() -> FastAPI:
    return _run_async_from_sync(_create_runtime_app_async())


def main() -> None:
    settings = Settings()
    uvicorn.run(**uvicorn_kwargs(settings))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Implement Windows service wrapper**

Create `app_v4/service/windows_service.py`:

```python
from __future__ import annotations

import logging
import threading

import servicemanager
import uvicorn
import win32event
import win32service
import win32serviceutil

from app_v4.core.config import Settings
from app_v4.service.main import uvicorn_kwargs

logger = logging.getLogger(__name__)


class NcmV4BackendService(win32serviceutil.ServiceFramework):
    _svc_name_ = "NCMv4Backend"
    _svc_display_name_ = "NCM v4 Backend Service"
    _svc_description_ = "NCM v4 FastAPI backend, scheduler host, and web server."

    def __init__(self, args):
        super().__init__(args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.server: uvicorn.Server | None = None
        self.thread: threading.Thread | None = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        if self.server is not None:
            self.server.should_exit = True
        win32event.SetEvent(self.stop_event)

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, ""),
        )
        settings = Settings()
        kwargs = uvicorn_kwargs(settings)
        config = uvicorn.Config(**kwargs)
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()
        win32event.WaitForSingleObject(self.stop_event, win32event.INFINITE)
        if self.thread is not None:
            self.thread.join(timeout=10)


def main() -> None:
    win32serviceutil.HandleCommandLine(NcmV4BackendService)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run entrypoint tests**

```bash
rtk python -m pytest app_v4/tests/test_service_entrypoints.py -v
```

Expected: PASS, 2 tests.

- [ ] **Step 6: Commit**

```bash
rtk git add app_v4/service/main.py app_v4/service/windows_service.py app_v4/tests/test_service_entrypoints.py
rtk git commit -m "feat: add v4 backend service entrypoints"
```

---

## Task 13: Add full backend skeleton verification

**Files:**
- Modify: `.gitignore`
- Test: all `app_v4/tests/*.py`

- [ ] **Step 1: Ignore local v4 runtime artifacts**

Modify `.gitignore`, adding these lines under custom ignores:

```text
# v4 local runtime
app_v4/service/static/
app_v4/**/*.db
app_v4/**/*.db-shm
app_v4/**/*.db-wal
app_v4/**/*.log
```

- [ ] **Step 2: Run focused backend test suite**

```bash
rtk python -m pytest app_v4/tests -v
```

Expected: all tests PASS.

- [ ] **Step 3: Run import smoke tests**

```bash
rtk python -c "from app_v4.service.app import create_app; from app_v4.service.main import uvicorn_kwargs; print('ok')"
```

Expected output:

```text
ok
```

- [ ] **Step 4: Check git diff before final commit**

```bash
rtk git diff
```

Expected: only `app_v4/` files and `.gitignore` changes from this plan.

- [ ] **Step 5: Commit verification cleanup**

```bash
rtk git add .gitignore
rtk git commit -m "chore: ignore v4 runtime artifacts"
```

---

## Handoff Notes

After this plan, v4 backend skeleton has:

- Runnable app factory: `app_v4.service.app:create_app`
- Uvicorn factory entry: `app_v4.service.main:create_runtime_app`
- Async SQLite schema with v3 tables + v4 auth/audit tables
- DPAPI-compatible key envelope abstraction
- Fernet credential crypto compatible with v3 `data/master.key`
- JWT auth with argon2id password hashing
- `/api/v1/auth/login`
- `/api/v1/auth/me`
- `/api/v1/system/status`
- `/api/v1/system/metrics`
- `/ws?token=<access-token>` authenticated WebSocket

Plan 2 should build web foundations using these endpoints: login page, shell layout, dashboard data fetch, WebSocket live feed consumer, and Ops Terminal CSS tokens.
