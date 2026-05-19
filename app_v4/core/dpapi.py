from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol


class ProtectionProvider(Protocol):
    def protect(self, plaintext: bytes) -> bytes:
        raise NotImplementedError

    def unprotect(self, ciphertext: bytes) -> bytes:
        raise NotImplementedError


class WindowsDpapiProvider:
    def protect(self, plaintext: bytes) -> bytes:
        import win32crypt

        return win32crypt.CryptProtectData(
            plaintext,
            "ncm-v4-master-envelope",
            None,
            None,
            None,
            0,
        )

    def unprotect(self, ciphertext: bytes) -> bytes:
        import win32crypt

        _description, plaintext = win32crypt.CryptUnprotectData(ciphertext, None, None, None, 0)
        return plaintext


@dataclass(frozen=True)
class MemoryProtectionProvider:
    secret: bytes

    def protect(self, plaintext: bytes) -> bytes:
        mask = self._mask(len(plaintext))
        return bytes(value ^ mask[index] for index, value in enumerate(plaintext))

    def unprotect(self, ciphertext: bytes) -> bytes:
        mask = self._mask(len(ciphertext))
        return bytes(value ^ mask[index] for index, value in enumerate(ciphertext))

    def _mask(self, length: int) -> bytes:
        chunks: list[bytes] = []
        counter = 0
        while sum(len(chunk) for chunk in chunks) < length:
            chunks.append(hashlib.sha256(self.secret + counter.to_bytes(4, "big")).digest())
            counter += 1
        return b"".join(chunks)[:length]
