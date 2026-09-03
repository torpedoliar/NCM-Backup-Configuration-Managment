from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app_v4.core.auth_service import AuthService
from app_v4.core.config import Settings
from app_v4.core.crypto_service import CryptoService
from app_v4.core.dpapi import WindowsDpapiProvider
from app_v4.core.key_envelope import KeyEnvelopeStore
from app_v4.core.paths import resolve_paths
from app_v4.core.runtime_settings import AuthSettings, RuntimeSettings, load_runtime_settings
from app_v4.core.utcdatetime import utc_now
from app_v4.data.db import create_session_factory, init_db
from app_v4.service.audit import AuditWriter
from app_v4.service.backup_service import BackupService
from app_v4.service.events import EventHub
from app_v4.service.retention_service import RetentionService
from app_v4.service.scheduler import SchedulerService


AuthSettingsProvider = Callable[[], AuthSettings]


def apply_runtime_settings(settings: Settings, runtime_settings: RuntimeSettings) -> Settings:
    backup_root = runtime_settings.backup_location.backup_root_folder
    if backup_root:
        return settings.model_copy(update={"backup_root_folder": backup_root})
    return settings


@dataclass
class ServiceRuntime:
    settings: Settings
    session_factory: async_sessionmaker[AsyncSession]
    auth_service: AuthService
    event_hub: EventHub
    audit_writer: AuditWriter
    auth_settings_provider: AuthSettingsProvider = field(
        default_factory=lambda: lambda: AuthSettings()
    )
    runtime_settings_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    crypto_service: CryptoService | None = None
    backup_service: BackupService | None = None
    scheduler_service: SchedulerService | None = None
    retention_service: RetentionService | None = None
    review_service: object | None = None
    notify: object | None = None
    started_at: datetime = field(default_factory=utc_now)

    async def shutdown(self) -> None:
        if self.scheduler_service is not None:
            await self.scheduler_service.stop()

    @classmethod
    def for_tests(
        cls,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        jwt_secret: bytes,
        crypto_service: CryptoService | None = None,
        backup_service: BackupService | None = None,
        scheduler_service: SchedulerService | None = None,
        retention_service: RetentionService | None = None,
        review_service=None,
        auth_settings: AuthSettings | None = None,
    ) -> "ServiceRuntime":
        provider: AuthSettingsProvider = lambda: auth_settings or AuthSettings()
        return cls(
            settings=settings,
            session_factory=session_factory,
            auth_service=AuthService(jwt_secret=jwt_secret, settings_provider=provider),
            event_hub=EventHub(),
            audit_writer=AuditWriter(session_factory),
            auth_settings_provider=provider,
            crypto_service=crypto_service,
            backup_service=backup_service,
            scheduler_service=scheduler_service,
            retention_service=retention_service,
            review_service=review_service,
        )


async def build_runtime(settings: Settings) -> tuple[ServiceRuntime, object]:
    paths = resolve_paths(settings)
    runtime_settings_path = paths.data_dir / "runtime_settings.json"
    settings = apply_runtime_settings(settings, load_runtime_settings(runtime_settings_path))
    paths = resolve_paths(settings)
    envelope = KeyEnvelopeStore(paths.master_envelope_file, WindowsDpapiProvider()).load()
    crypto = CryptoService(settings=settings, passphrase=envelope.master_passphrase)
    engine, session_factory = create_session_factory(settings)
    await init_db(engine)
    event_hub = EventHub()

    def auth_settings_provider() -> AuthSettings:
        return load_runtime_settings(runtime_settings_path).auth

    retention_service = RetentionService(
        settings,
        session_factory,
        runtime_settings_path=runtime_settings_path,
    )
    from app_v4.service.notify import Notifier
    from app_v4.service.review_service import ReviewService

    notify = Notifier(runtime_settings_path)
    review_service = ReviewService(settings, session_factory, notifier=notify)
    backup_service = BackupService(
        settings,
        session_factory,
        crypto,
        event_hub=event_hub,
        review_service=review_service,
        notifier=notify,
    )
    scheduler_service = SchedulerService(
        settings,
        session_factory,
        backup_service,
        event_hub=event_hub,
        retention_service=retention_service,
        review_service=review_service,
        notify=notify,
    )
    await scheduler_service.start()
    runtime = ServiceRuntime(
        settings=settings,
        session_factory=session_factory,
        auth_service=AuthService(
            jwt_secret=envelope.jwt_secret,
            settings_provider=auth_settings_provider,
        ),
        event_hub=event_hub,
        audit_writer=AuditWriter(session_factory),
        auth_settings_provider=auth_settings_provider,
        crypto_service=crypto,
        backup_service=backup_service,
        scheduler_service=scheduler_service,
        retention_service=retention_service,
        review_service=review_service,
        notify=notify,
    )
    return runtime, engine
