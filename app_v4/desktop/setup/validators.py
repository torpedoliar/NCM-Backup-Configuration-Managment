from __future__ import annotations

import re

_USERNAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]*$")
_HOSTNAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9\-.]*$")


def validate_passphrase(value: str, confirm: str) -> str | None:
    if len(value) < 12:
        return "Passphrase must be at least 12 characters"
    if not re.search(r"[A-Z]", value):
        return "Passphrase must include an upper-case letter"
    if not re.search(r"[a-z]", value):
        return "Passphrase must include a lower-case letter"
    if not re.search(r"\d", value):
        return "Passphrase must include a digit"
    if value != confirm:
        return "Passphrases do not match"
    return None


def validate_username(value: str) -> str | None:
    if len(value) < 3 or len(value) > 64:
        return "Username must be 3 to 64 characters"
    if not _USERNAME_RE.match(value):
        return (
            "Username must start with a letter and contain only "
            "alphanumerics, underscore, or dash"
        )
    return None


def validate_password(value: str, confirm: str) -> str | None:
    if len(value) < 8:
        return "Password must be at least 8 characters"
    if not re.search(r"[A-Z]", value):
        return "Password must include an upper-case letter"
    if not re.search(r"[a-z]", value):
        return "Password must include a lower-case letter"
    if not re.search(r"\d", value):
        return "Password must include a digit"
    if value != confirm:
        return "Passwords do not match"
    return None


def validate_bind_host(value: str) -> str | None:
    text = (value or "").strip()
    if not text:
        return "Bind host is required"
    if " " in text:
        return "Bind host must not contain whitespace"
    if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", text):
        try:
            octets = [int(part) for part in text.split(".")]
        except ValueError:
            return "Bind host octets must be numbers"
        if any(o < 0 or o > 255 for o in octets):
            return "Bind host octets must be between 0 and 255"
        return None
    if not _HOSTNAME_RE.match(text):
        return "Bind host must be an IPv4 address or hostname"
    return None


def validate_bind_port(value: str) -> str | None:
    try:
        port = int(str(value).strip())
    except (TypeError, ValueError):
        return "Bind port must be a number"
    if port < 1024 or port > 65535:
        return "Bind port must be between 1024 and 65535"
    return None
