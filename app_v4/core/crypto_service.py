from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app_v4.core.config import Settings
from app_v4.core.paths import resolve_paths


class CryptoService:
    def __init__(self, settings: Settings, passphrase: str):
        self.settings = settings
        self.paths = resolve_paths(settings)
        self.salt = self._get_or_create_salt()
        self.cipher = self._derive_cipher(passphrase)
        self._validate_passphrase()

    def encrypt_credential(self, username: str, password: str, enable_password: str = "") -> bytes:
        payload = {
            "username": username,
            "password": password,
            "enable_password": enable_password,
        }
        return self.cipher.encrypt(json.dumps(payload, separators=(",", ":")).encode("utf-8"))

    def decrypt_credential(self, enc_blob: bytes) -> dict[str, str]:
        try:
            plaintext = self.cipher.decrypt(enc_blob)
            payload: dict[str, Any] = json.loads(plaintext.decode("utf-8"))
            return {
                "username": str(payload["username"]),
                "password": str(payload["password"]),
                "enable_password": str(payload.get("enable_password", "")),
            }
        except Exception as exc:
            raise ValueError("Invalid credentials or wrong passphrase") from exc

    def _get_or_create_salt(self) -> bytes:
        self.paths.data_dir.mkdir(parents=True, exist_ok=True)
        key_file = self.paths.master_key_file
        if key_file.exists():
            return key_file.read_bytes()[:16]
        salt = os.urandom(16)
        key_file.write_bytes(salt)
        return salt

    def _derive_cipher(self, passphrase: str) -> Fernet:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            iterations=100_000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))
        return Fernet(key)

    def _validate_passphrase(self) -> None:
        key_file = self.paths.master_key_file
        test_token = b"VALID_PASSPHRASE_TEST_TOKEN"
        content = key_file.read_bytes()
        if len(content) > 16:
            encrypted_token = content[16:]
            try:
                decrypted = self.cipher.decrypt(encrypted_token)
            except Exception as exc:
                raise ValueError("Invalid master passphrase") from exc
            if decrypted != test_token:
                raise ValueError("Invalid master passphrase")
            return
        encrypted_token = self.cipher.encrypt(test_token)
        key_file.write_bytes(self.salt + encrypted_token)
