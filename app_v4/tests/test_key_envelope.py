from pathlib import Path

import pytest

from app_v4.core.dpapi import MemoryProtectionProvider
from app_v4.core.key_envelope import KeyEnvelopeStore, MasterKeyUnavailableError


def test_key_envelope_round_trip(tmp_path: Path):
    provider = MemoryProtectionProvider(secret=b"test-secret")
    store = KeyEnvelopeStore(path=tmp_path / "master.dpapi", provider=provider)

    created = store.create(master_passphrase="correct horse battery staple")
    loaded = store.load()

    assert created.master_passphrase == "correct horse battery staple"
    assert len(created.jwt_secret) == 32
    assert loaded.master_passphrase == created.master_passphrase
    assert loaded.jwt_secret == created.jwt_secret


def test_key_envelope_rejects_wrong_provider(tmp_path: Path):
    good_provider = MemoryProtectionProvider(secret=b"good")
    bad_provider = MemoryProtectionProvider(secret=b"bad")
    KeyEnvelopeStore(tmp_path / "master.dpapi", good_provider).create("passphrase")

    with pytest.raises(MasterKeyUnavailableError, match="MASTER_KEY_UNAVAILABLE"):
        KeyEnvelopeStore(tmp_path / "master.dpapi", bad_provider).load()


def test_key_envelope_raises_master_key_unavailable_on_dpapi_failure(tmp_path: Path):
    class BrokenProvider:
        def protect(self, plaintext: bytes) -> bytes:
            return b"bad"

        def unprotect(self, ciphertext: bytes) -> bytes:
            raise RuntimeError("dpapi failed")

    store = KeyEnvelopeStore(tmp_path / "master.dpapi", BrokenProvider())
    (tmp_path / "master.dpapi").write_bytes(b"bad")

    with pytest.raises(MasterKeyUnavailableError) as exc:
        store.load()
    assert "MASTER_KEY_UNAVAILABLE" in str(exc.value)
