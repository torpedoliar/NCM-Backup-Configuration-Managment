from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
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
