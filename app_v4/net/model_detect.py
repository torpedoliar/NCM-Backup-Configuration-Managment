from __future__ import annotations

import re

# Conservative model hints read from the raw config text. The first hit wins.
# Kept deliberately vendor-prefixed so a wrong guess never labels a device.
_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bAT-?[A-Z0-9/]+\b", re.IGNORECASE),               # Allied Telesis
    re.compile(r"\bDell\s+(?:Networking\s+)?(N[A-Z0-9]+)", re.IGNORECASE),
    re.compile(r"\bAruba\s+([A-Z0-9-]+)", re.IGNORECASE),
    re.compile(r"\bCatalyst\s+([A-Z0-9]+)", re.IGNORECASE),
    re.compile(r"\bJuniper\s+([A-Z0-9.-]+)", re.IGNORECASE),
    re.compile(r"\b(N1548P|GS-?[0-9]+|DES-?[0-9]+|SL-?[0-9]+|XS-?[0-9]+)\b", re.IGNORECASE),
]


def detect_model(text: str, dialect: str) -> str | None:
    """Best-effort device model, or None when unrecognisable.

    Only fires on explicit, vendor-prefixed model tokens. When nothing matches,
    the caller leaves the manually-set ``Switch.model`` untouched.
    """
    if not text:
        return None
    for pattern in _PATTERNS:
        m = pattern.search(text)
        if m:
            return (m.group(1) if m.groups() else m.group(0)).strip()
    return None
