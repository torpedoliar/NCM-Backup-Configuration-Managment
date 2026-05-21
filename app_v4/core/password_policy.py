from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PasswordPolicy:
    min_length: int = 8
    require_upper: bool = True
    require_lower: bool = True
    require_digit: bool = True
    require_symbol: bool = False


def validate_password(password: str, policy: PasswordPolicy) -> str | None:
    if len(password) < policy.min_length:
        return f"Password must be at least {policy.min_length} characters"
    if policy.require_upper and not any(c.isupper() for c in password):
        return "Password must include an upper-case letter"
    if policy.require_lower and not any(c.islower() for c in password):
        return "Password must include a lower-case letter"
    if policy.require_digit and not any(c.isdigit() for c in password):
        return "Password must include a digit"
    if policy.require_symbol and password.isalnum():
        return "Password must include a symbol"
    return None
