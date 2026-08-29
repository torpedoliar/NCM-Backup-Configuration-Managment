from __future__ import annotations

from datetime import datetime
from typing import Optional

from app_v4.core.utcdatetime import utc_now

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Credential(Base):
    __tablename__ = "credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    enc_blob: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

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
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, server_default="1")
    deactivated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    credential: Mapped[Credential] = relationship(back_populates="switches")
    backups: Mapped[list["Backup"]] = relationship(back_populates="switch", cascade="all, delete-orphan")
    jobs: Mapped[list["Job"]] = relationship(back_populates="switch", cascade="all, delete-orphan")


class Backup(Base):
    __tablename__ = "backups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    switch_id: Mapped[int] = mapped_column(ForeignKey("switches.id"), nullable=False, index=True)
    taken_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False, index=True)
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
    name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_ran_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    schedule_hour: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    schedule_minute: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    day_of_week: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    day_of_month: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    switch: Mapped[Switch] = relationship(back_populates="jobs")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, server_default="0")
    last_failed_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    sessions: Mapped[list["Session"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
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


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ConfigBaseline(Base):
    """Golden configuration for a switch or a model (ISO 27001 config management).

    kind == "switch": applies to one switch (switch_id set).
    kind == "model": template applied to every switch with that ``model`` value.
    """

    __tablename__ = "config_baselines"
    __table_args__ = (
        UniqueConstraint("kind", "switch_id", name="uq_baseline_switch"),
        UniqueConstraint("kind", "model", name="uq_baseline_model"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # "switch" | "model"
    switch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("switches.id"), nullable=True, index=True)
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    backup_id: Mapped[Optional[int]] = mapped_column(ForeignKey("backups.id"), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class ConfigReview(Base):
    """A logged config-change review (evidence for ISO 27001 A.8.9).

    Created when a backup's content differs from the applicable baseline.
    status: pending | approved | flagged | dismissed — reviewed manually.
    """

    __tablename__ = "config_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    switch_id: Mapped[int] = mapped_column(ForeignKey("switches.id"), nullable=False, index=True)
    backup_id: Mapped[int] = mapped_column(ForeignKey("backups.id"), nullable=False, index=True)
    baseline_id: Mapped[Optional[int]] = mapped_column(ForeignKey("config_baselines.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", index=True)
    reviewed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_diff: Mapped[str] = mapped_column(Text, nullable=False, default="")
    diff_summary: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False, index=True)
