"""HTTP test server for the DG<->NCM contract (ticket 07).

Builds the real FastAPI app (create_app) over a throwaway SQLite dir with a
FakeRunner-backed BackupService, then serves it with uvicorn on 127.0.0.1.

    python -m app_v4.tests.e2e_server --port <port>

Prints "READY <port>" on stdout once serving. Test scripts hit it with plain
HTTP — no mocks on either side of the seam.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import tempfile
from pathlib import Path

import uvicorn

from app_v4.core.config import Settings
from app_v4.core.crypto_service import CryptoService
from app_v4.data.db import create_session_factory, init_db
from app_v4.data.repository import Repository
from app_v4.net.runner import BackupRunResult
from app_v4.service.app import create_app
from app_v4.service.backup_service import BackupService
from app_v4.service.diff_service import DiffService
from app_v4.service.events import EventHub
from app_v4.service.review_service import ReviewService
from app_v4.service.runtime import ServiceRuntime


class FakeRunner:
    """Returns a rotating config sequence so drift can be demonstrated live.

    The first ``stable_rounds`` backups return ``config_text``; every backup
    after that appends ``drift_suffix`` — enough to open a pending review
    against a previously snapshotted baseline (the contract's drift step).
    """

    def __init__(self, config_text: str, drift_suffix: str = "\nvlan 99 name DRIFTED\n", stable_rounds: int = 1) -> None:
        self._config_text = config_text
        self._drift_suffix = drift_suffix
        self._stable_rounds = stable_rounds
        self._calls = 0

    async def execute_backup(self, protocol, host, port, username, password, enable_password=""):
        self._calls += 1
        text = self._config_text if self._calls <= self._stable_rounds else self._config_text + self._drift_suffix
        return BackupRunResult(True, text, "Backup completed successfully")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NCM contract test server")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--config-text", default="hostname dg-contract\nvlan 10 name MGMT\n")
    return parser.parse_args(argv)


async def _build_app(base_dir: Path, config_text: str):
    settings = Settings(base_dir=base_dir)
    crypto = CryptoService(settings=settings, passphrase="contract-passphrase")
    engine, session_factory = create_session_factory(settings)
    await init_db(engine)

    runtime = ServiceRuntime.for_tests(
        settings,
        session_factory,
        jwt_secret=b"c" * 32,
        crypto_service=crypto,
        backup_service=BackupService(
            settings=settings,
            session_factory=session_factory,
            crypto_service=crypto,
            runner=FakeRunner(config_text),
            diff_service=DiffService(settings),
            event_hub=EventHub(),
            review_service=ReviewService(settings, session_factory),
        ),
        review_service=ReviewService(settings, session_factory),
    )

    # Seed the admin through the runtime's own hasher (argon2), so /auth/login
    # works on the live server too.
    async with session_factory() as session:
        repo = Repository(session)
        if await repo.get_user_by_username("admin") is None:
            password_hash = runtime.auth_service.hash_password("ContractAdmin1!")
            await repo.create_user("admin", password_hash, "admin")
            await session.commit()

    return create_app(runtime)


def main() -> None:
    args = parse_args()
    base_dir = Path(tempfile.mkdtemp(prefix="ncm_contract_"))
    app = asyncio.run(_build_app(base_dir, args.config_text))
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=args.port, log_level="warning")
    )
    print(f"READY {args.port}", flush=True)
    server.run()


if __name__ == "__main__":
    sys.exit(main())
