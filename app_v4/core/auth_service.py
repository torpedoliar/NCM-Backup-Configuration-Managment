from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError

from app_v4.core.config import Settings


class TokenError(ValueError):
    pass


@dataclass(frozen=True)
class AccessClaims:
    user_id: int
    username: str
    role: str
    expires_at: datetime


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AuthService:
    def __init__(self, settings: Settings, jwt_secret: bytes):
        self.settings = settings
        self.jwt_secret = jwt_secret
        self.password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)

    def hash_password(self, password: str) -> str:
        return self.password_hasher.hash(password)

    def verify_password(self, password: str, password_hash: str) -> bool:
        try:
            return bool(self.password_hasher.verify(password_hash, password))
        except (VerifyMismatchError, VerificationError):
            return False

    def issue_access_token(self, user_id: int, username: str, role: str) -> str:
        now = datetime.now(timezone.utc)
        exp = now + timedelta(minutes=self.settings.jwt_access_minutes)
        payload = {
            "sub": str(user_id),
            "username": username,
            "role": role,
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
            "typ": "access",
        }
        return jwt.encode(payload, self.jwt_secret, algorithm="HS256")

    def verify_access_token(self, token: str) -> AccessClaims:
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
        except jwt.PyJWTError as exc:
            raise TokenError("Invalid access token") from exc
        if payload.get("typ") != "access":
            raise TokenError("Invalid token type")
        return AccessClaims(
            user_id=int(payload["sub"]),
            username=str(payload["username"]),
            role=str(payload["role"]),
            expires_at=datetime.fromtimestamp(int(payload["exp"]), tz=timezone.utc),
        )

    def issue_token_pair(self, user_id: int, username: str, role: str) -> TokenPair:
        return TokenPair(
            access_token=self.issue_access_token(user_id, username, role),
            refresh_token=secrets.token_urlsafe(48),
        )
