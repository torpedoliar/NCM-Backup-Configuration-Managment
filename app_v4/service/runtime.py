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
