from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Current UTC time as a naive datetime, exactly like ``datetime.utcnow()``.

    Legacy code writes these values into SQLite ``DateTime`` columns that are
    read back as naive datetimes; comparisons later mix them with naive
    ``datetime`` values (e.g. session ``expires_at`` vs ``now`` in the auth
    flow). Keeping this helper naive preserves that storage and comparison
    behaviour while avoiding the deprecated ``datetime.utcnow()`` call.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
