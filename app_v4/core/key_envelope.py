from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path

from app_v4.core.dpapi import ProtectionProvider


@dataclass(frozen=True)
class KeyEnvelope:
    master_passphrase: str
    jwt_secret: bytes
    version: int = 1


class KeyEnvelopeStore:
    def __init__(self, path: Path, provider: ProtectionProvider):
        self.path = path
        self.provider = provider

    def create(self, master_passphrase: str) -> KeyEnvelope:
        envelope = KeyEnvelope(master_passphrase=master_passphrase, jwt_secret=os.urandom(32))
        self.save(envelope)
        return envelope

    def save(self, envelope: KeyEnvelope) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": envelope.version,
            "master_passphrase": envelope.master_passphrase,
            "jwt_secret_b64": base64.urlsafe_b64encode(envelope.jwt_secret).decode("ascii"),
        }
        plaintext = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        ciphertext = self.provider.protect(plaintext)
        self.path.write_bytes(ciphertext)

    def load(self) -> KeyEnvelope:
        try:
            ciphertext = self.path.read_bytes()
            plaintext = self.provider.unprotect(ciphertext)
            payload = json.loads(plaintext.decode("utf-8"))
            return KeyEnvelope(
                version=int(payload["version"]),
                master_passphrase=str(payload["master_passphrase"]),
                jwt_secret=base64.urlsafe_b64decode(payload["jwt_secret_b64"].encode("ascii")),
            )
        except Exception as exc:
            raise ValueError("Unable to decrypt master key envelope") from exc
