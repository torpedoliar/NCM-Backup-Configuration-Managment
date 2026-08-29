from __future__ import annotations

from datetime import datetime, timezone

from app_v4.core.utcdatetime import utc_now as _utc_now

__all__ = ["to_aware_utc", "utc_now"]


def utc_now() -> datetime:
    """Current UTC time, exactly like the deprecated ``datetime.utcnow()``."""
    return _utc_now()


def to_aware_utc(value: datetime | None) -> datetime | None:
    """Tag a naive datetime as UTC.

    The legacy code uses ``datetime.utcnow()`` which produces naive datetimes.
    Pydantic serialises those without a timezone marker, so JS clients call
    ``new Date(...)`` and the browser assumes local time — which is wrong by
    7 hours for users in Asia/Jakarta. Routing every API timestamp through
    this helper produces ISO strings that end with ``+00:00`` so the client
    converts them with ``Intl.DateTimeFormat({ timeZone: ... })`` correctly.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
