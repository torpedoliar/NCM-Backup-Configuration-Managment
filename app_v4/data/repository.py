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
