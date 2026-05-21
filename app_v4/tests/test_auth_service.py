from datetime import datetime, timedelta, timezone

import pytest

from app_v4.core.auth_service import AuthService, TokenError
from app_v4.core.runtime_settings import AuthSettings


def test_password_hash_verification():
    service = AuthService(jwt_secret=b"x" * 32, settings_provider=lambda: AuthSettings())

    password_hash = service.hash_password("StrongPassword123!")

    assert password_hash != "StrongPassword123!"
    assert service.verify_password("StrongPassword123!", password_hash) is True
    assert service.verify_password("wrong", password_hash) is False


def test_access_token_round_trip():
    service = AuthService(jwt_secret=b"y" * 32, settings_provider=lambda: AuthSettings())

    token = service.issue_access_token(user_id=7, username="admin", role="admin")
    claims = service.verify_access_token(token)

    assert claims.user_id == 7
    assert claims.username == "admin"
    assert claims.role == "admin"


def test_invalid_token_raises_token_error():
    service = AuthService(jwt_secret=b"z" * 32, settings_provider=lambda: AuthSettings())

    with pytest.raises(TokenError):
        service.verify_access_token("not-a-token")


def test_access_token_uses_provider_for_minutes():
    minutes_holder = {"value": 15}

    def provider() -> AuthSettings:
        return AuthSettings(access_token_minutes=minutes_holder["value"])

    svc = AuthService(jwt_secret=b"x" * 32, settings_provider=provider)
    token = svc.issue_access_token(user_id=1, username="admin", role="admin")
    claims = svc.verify_access_token(token)

    issued_at = datetime.fromtimestamp(
        claims.expires_at.timestamp() - minutes_holder["value"] * 60, tz=timezone.utc
    )
    assert (claims.expires_at - issued_at).total_seconds() == minutes_holder["value"] * 60

    minutes_holder["value"] = 30
    token2 = svc.issue_access_token(user_id=1, username="admin", role="admin")
    claims2 = svc.verify_access_token(token2)
    assert (claims2.expires_at - claims.expires_at).total_seconds() >= 60
