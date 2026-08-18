"""Entry point for switch-config parsing.

The stored protocol (``ssh`` / ``telnet``) does not distinguish AlliedWare Plus
from Dell, so the dialect is sniffed from the config text itself. Detection is
by unambiguous per-dialect markers; the fixtures share none of them, so the
check order is not load-bearing -- only the specificity of each marker is.
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
    """
    dialect = detect_dialect(text)
    if dialect == "awplus":
        return awplus.parse(text)
    if dialect == "dell":
        return dell.parse(text)
    if dialect == "websmart":
        return websmart_snmp.parse(text)
    return ParsedConfig(warnings=["unknown switch config dialect; nothing parsed"])
