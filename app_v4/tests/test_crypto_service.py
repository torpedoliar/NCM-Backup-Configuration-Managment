from pathlib import Path

from app_v4.core.config import Settings
from app_v4.core.crypto_service import CryptoService


def test_crypto_service_round_trips_credentials(tmp_path: Path):
    settings = Settings(base_dir=tmp_path)
    crypto = CryptoService(settings=settings, passphrase="correct horse battery staple")

    blob = crypto.encrypt_credential("admin", "secret", "enable")
    decrypted = crypto.decrypt_credential(blob)

    assert decrypted == {
        "username": "admin",
        "password": "secret",
        "enable_password": "enable",
    }


def test_crypto_service_rejects_wrong_passphrase(tmp_path: Path):
    settings = Settings(base_dir=tmp_path)
    CryptoService(settings=settings, passphrase="first passphrase")

    try:
        CryptoService(settings=settings, passphrase="second passphrase")
    except ValueError as exc:
        assert "Invalid master passphrase" in str(exc)
    else:
        raise AssertionError("wrong passphrase accepted")
