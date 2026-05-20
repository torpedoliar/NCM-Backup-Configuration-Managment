from pathlib import Path

from app_v4.tools.migrate_v3 import MigrationResult, migrate_v3_install


class FakeEnvelopeStore:
    def __init__(self):
        self.saved = None

    def save(self, master_passphrase: str, jwt_secret: bytes):
        self.saved = (master_passphrase, jwt_secret)


def test_migrate_v3_copies_database_backups_and_passphrase(tmp_path):
    source = tmp_path / "v3"
    target = tmp_path / "v4"
    source.mkdir()
    (source / "ncm.db").write_bytes(b"sqlite")
    (source / "backups").mkdir()
    (source / "backups" / "sw01.txt").write_text("config", encoding="utf-8")
    (source / ".service_passphrase").write_text("legacy-secret", encoding="utf-8")
    store = FakeEnvelopeStore()

    result = migrate_v3_install(source, target, envelope_store=store, jwt_secret=b"1" * 32)

    assert result == MigrationResult(database_copied=True, backups_copied=1, legacy_passphrase_migrated=True)
    assert (target / "data" / "ncm.db").read_bytes() == b"sqlite"
    assert (target / "backups" / "sw01.txt").read_text(encoding="utf-8") == "config"
    assert store.saved == ("legacy-secret", b"1" * 32)
    assert not (source / ".service_passphrase").exists()
