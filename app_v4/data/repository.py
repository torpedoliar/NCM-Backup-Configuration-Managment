from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app_v4.data.models import AuditLog, Backup, Credential, Job, Session, Switch, User


NULLABLE_FIELDS = {"day_of_week", "day_of_month"}


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
        result = await self.session.execute(
            select(Credential).options(selectinload(Credential.switches)).where(Credential.id == cred_id)
        )
        cred = result.scalar_one_or_none()
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

    async def list_switches(self, include_inactive: bool = False) -> list[Switch]:
        stmt = select(Switch).options(selectinload(Switch.credential))
        if not include_inactive:
            stmt = stmt.where(Switch.is_active.is_(True))
        stmt = stmt.order_by(Switch.name)
        result = await self.session.execute(stmt)
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

    async def deactivate_switch(self, switch_id: int) -> Switch | None:
        switch = await self.get_switch(switch_id)
        if switch is None:
            return None
        switch.is_active = False
        switch.deactivated_at = datetime.utcnow()
        switch.updated_at = datetime.utcnow()
        return switch

    async def activate_switch(self, switch_id: int) -> Switch | None:
        switch = await self.get_switch(switch_id)
        if switch is None:
            return None
        switch.is_active = True
        switch.deactivated_at = None
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

    def _apply_audit_filters(
        self,
        stmt,
        *,
        action_prefix: str | None,
        user_id: int | None,
        from_ts: datetime | None,
        to_ts: datetime | None,
    ):
        if action_prefix is not None:
            stmt = stmt.where(AuditLog.action.like(f"{action_prefix}%"))
        if user_id is not None:
            stmt = stmt.where(AuditLog.user_id == user_id)
        if from_ts is not None:
            stmt = stmt.where(AuditLog.ts >= from_ts)
        if to_ts is not None:
            stmt = stmt.where(AuditLog.ts <= to_ts)
        return stmt

    async def list_audit(
        self,
        limit: int = 100,
        offset: int = 0,
        action_prefix: str | None = None,
        user_id: int | None = None,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
    ) -> list[AuditLog]:
        stmt = select(AuditLog).order_by(AuditLog.ts.desc()).limit(limit).offset(offset)
        stmt = self._apply_audit_filters(
            stmt,
            action_prefix=action_prefix,
            user_id=user_id,
            from_ts=from_ts,
            to_ts=to_ts,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_audit(
        self,
        action_prefix: str | None = None,
        user_id: int | None = None,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
    ) -> int:
        stmt = select(func.count(AuditLog.id))
        stmt = self._apply_audit_filters(
            stmt,
            action_prefix=action_prefix,
            user_id=user_id,
            from_ts=from_ts,
            to_ts=to_ts,
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def delete_audit_older_than(self, cutoff: datetime) -> int:
        result = await self.session.execute(delete(AuditLog).where(AuditLog.ts < cutoff))
        return int(result.rowcount or 0)

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
        success: bool | None = None,
        backup_type: str | None = None,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
        q: str | None = None,
    ) -> list[Backup]:
        stmt = select(Backup).order_by(Backup.taken_at.desc())
        if switch_id is not None:
            stmt = stmt.where(Backup.switch_id == switch_id)
        if success is not None:
            stmt = stmt.where(Backup.success.is_(success))
        if backup_type is not None:
            stmt = stmt.where(Backup.backup_type == backup_type)
        if from_ts is not None:
            stmt = stmt.where(Backup.taken_at >= from_ts)
        if to_ts is not None:
            stmt = stmt.where(Backup.taken_at <= to_ts)
        if q:
            stmt = stmt.where(Backup.message.ilike(f"%{q}%"))
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
        day_of_week: str | None = None,
        day_of_month: int | None = None,
    ) -> Job:
        job = Job(
            switch_id=switch_id,
            interval_minutes=interval_minutes,
            enabled=enabled,
            schedule_hour=schedule_hour,
            schedule_minute=schedule_minute,
            day_of_week=day_of_week,
            day_of_month=day_of_month,
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
            if hasattr(job, key) and (value is not None or key in NULLABLE_FIELDS):
                setattr(job, key, value)
        job.updated_at = datetime.utcnow()
        return job

    async def delete_job(self, job_id: int) -> bool:
        job = await self.get_job(job_id)
        if job is None:
            return False
        await self.session.delete(job)
        return True

    # ----- system -----

    async def system_metrics(self) -> dict[str, int]:
        row = (
            await self.session.execute(
                select(
                    select(func.count(Switch.id)).scalar_subquery().label("switches"),
                    select(func.count(Backup.id)).scalar_subquery().label("backups"),
                    select(func.count(Job.id)).scalar_subquery().label("jobs"),
                    select(func.count(Backup.id))
                    .where(Backup.success.is_(False))
                    .scalar_subquery()
                    .label("failed_backups"),
                )
            )
        ).one()
        return {
            "switches": int(row.switches),
            "backups": int(row.backups),
            "jobs": int(row.jobs),
            "failed_backups": int(row.failed_backups),
        }


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
