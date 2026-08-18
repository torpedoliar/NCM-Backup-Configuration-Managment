"""Entry point for switch-config parsing.

The stored protocol (``ssh`` / ``telnet``) does not distinguish AlliedWare Plus
from Dell, so the dialect is sniffed from the config text itself.

Detection is by per-dialect markers matched as substrings of the whole text.
None of the four fixtures contains another dialect's marker, so for them the
check order does not change the outcome -- but the order *is* load-bearing in
general: a config that merely quotes a rival marker inside a description or
banner is decided by whichever check runs first. Misrouting is therefore
possible in principle, which is why ``parse_config`` warns when a recognised
dialect yields no ports.
"""

from __future__ import annotations

from app_v4.net.config_parsers import awplus, dell, websmart_snmp
from app_v4.net.config_parsers.types import ParsedConfig, PortDoc, VlanDoc

__all__ = ["parse_config", "detect_dialect", "ParsedConfig", "PortDoc", "VlanDoc"]


def detect_dialect(text: str) -> str:
    """Name the config dialect of ``text``, or ``"unknown"``."""
    if "interface port1.0." in text:
        return "awplus"
    if "interface range ethernet g(" in text or "interface ethernet g" in text:
        return "dell"
    # An SNMP dump opens with its first ``@`` group marker; requiring that marker
    # near the top keeps a CLI config that merely mentions an OID from matching.
    if "@" in text[:200] and "1.3.6.1" in text:
        return "websmart"
    return "unknown"


def parse_config(text: str) -> ParsedConfig:
    """Parse a switch config of any supported dialect.

    Never raises: an unrecognised dialect yields an empty ``ParsedConfig``
    carrying an explanatory warning, so one odd device never fails a batch.

    A recognised dialect that yields no ports is also warned about. Without it,
    a genuinely portless device and a config routed to the wrong parser look
    identical to the caller -- the delegates warn about rows they fail to read,
    but a wrong parser reads nothing and so has nothing to warn about.
    """
    dialect = detect_dialect(text)
    if dialect == "awplus":
        cfg = awplus.parse(text)
    elif dialect == "dell":
        cfg = dell.parse(text)
    elif dialect == "websmart":
        cfg = websmart_snmp.parse(text)
    else:
        return ParsedConfig(warnings=["unknown switch config dialect; nothing parsed"])

    if not cfg.ports:
        cfg.warnings.append(f"detected dialect {dialect!r} but parsed no ports")
    return cfg
