from datetime import datetime, timedelta, timezone

import pytest

from app_v4.core.auth_service import AuthService, TokenError
from app_v4.core.config import Settings


def test_password_hash_verification():
    service = AuthService(settings=Settings(), jwt_secret=b"x" * 32)

    password_hash = service.hash_password("StrongPassword123!")

    assert password_hash != "StrongPassword123!"
    assert service.verify_password("StrongPassword123!", password_hash) is True
    assert service.verify_password("wrong", password_hash) is False


def test_access_token_round_trip():
    service = AuthService(settings=Settings(), jwt_secret=b"y" * 32)

    token = service.issue_access_token(user_id=7, username="admin", role="admin")
    claims = service.verify_access_token(token)

    assert claims.user_id == 7
    assert claims.username == "admin"
    assert claims.role == "admin"


def test_invalid_token_raises_token_error():
    service = AuthService(settings=Settings(), jwt_secret=b"z" * 32)

    with pytest.raises(TokenError):
        service.verify_access_token("not-a-token")
