from pathlib import Path

import pytest

from app_v4.core.dpapi import MemoryProtectionProvider
from app_v4.core.key_envelope import KeyEnvelopeStore


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

    with pytest.raises(ValueError, match="Unable to decrypt master key envelope"):
        KeyEnvelopeStore(tmp_path / "master.dpapi", bad_provider).load()
