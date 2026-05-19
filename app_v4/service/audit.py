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
