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
from app_v4.service.backup_service import BackupService
from app_v4.service.events import EventHub
from app_v4.service.scheduler import SchedulerService


@dataclass
class ServiceRuntime:
    settings: Settings
    session_factory: async_sessionmaker[AsyncSession]
    auth_service: AuthService
    event_hub: EventHub
    audit_writer: AuditWriter
    crypto_service: CryptoService | None = None
    backup_service: BackupService | None = None
    scheduler_service: SchedulerService | None = None
    started_at: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def for_tests(
        cls,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        jwt_secret: bytes,
        crypto_service: CryptoService | None = None,
        backup_service: BackupService | None = None,
        scheduler_service: SchedulerService | None = None,
    ) -> "ServiceRuntime":
        return cls(
            settings=settings,
            session_factory=session_factory,
            auth_service=AuthService(settings=settings, jwt_secret=jwt_secret),
            event_hub=EventHub(),
            audit_writer=AuditWriter(session_factory),
            crypto_service=crypto_service,
            backup_service=backup_service,
            scheduler_service=scheduler_service,
        )


async def build_runtime(settings: Settings) -> tuple[ServiceRuntime, object]:
    paths = resolve_paths(settings)
    envelope = KeyEnvelopeStore(paths.master_envelope_file, WindowsDpapiProvider()).load()
    crypto = CryptoService(settings=settings, passphrase=envelope.master_passphrase)
    engine, session_factory = create_session_factory(settings)
    await init_db(engine)
    backup_service = BackupService(settings, session_factory, crypto)
    scheduler_service = SchedulerService(settings, session_factory, backup_service)
    await scheduler_service.start()
    runtime = ServiceRuntime(
        settings=settings,
        session_factory=session_factory,
        auth_service=AuthService(settings=settings, jwt_secret=envelope.jwt_secret),
        event_hub=EventHub(),
        audit_writer=AuditWriter(session_factory),
        crypto_service=crypto,
        backup_service=backup_service,
        scheduler_service=scheduler_service,
    )
    return runtime, engine
