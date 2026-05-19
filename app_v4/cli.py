from __future__ import annotations

import argparse
import asyncio
import getpass
import sys

from app_v4.core.auth_service import AuthService
from app_v4.core.config import Settings
from app_v4.core.crypto_service import CryptoService
from app_v4.core.dpapi import ProtectionProvider, WindowsDpapiProvider
from app_v4.core.key_envelope import KeyEnvelopeStore
from app_v4.core.paths import resolve_paths
from app_v4.data.db import create_session_factory, init_db
from app_v4.data.repository import Repository


async def init_command(
    settings: Settings,
    master_passphrase: str,
    admin_username: str,
    admin_password: str,
    protection_provider: ProtectionProvider | None = None,
) -> dict:
    provider = protection_provider or WindowsDpapiProvider()
    paths = resolve_paths(settings)
    paths.data_dir.mkdir(parents=True, exist_ok=True)

    store = KeyEnvelopeStore(paths.master_envelope_file, provider)
    if paths.master_envelope_file.exists():
        existing = store.load()
        if existing.master_passphrase != master_passphrase:
            raise ValueError(
                "Master passphrase does not match the existing envelope"
            )
        envelope = existing
        created_envelope = False
    else:
        envelope = store.create(master_passphrase=master_passphrase)
        created_envelope = True

    CryptoService(settings=settings, passphrase=envelope.master_passphrase)

    engine, session_factory = create_session_factory(settings)
    await init_db(engine)
    auth = AuthService(settings=settings, jwt_secret=envelope.jwt_secret)

    created_admin = False
    try:
        async with session_factory() as session:
            repo = Repository(session)
            existing_user = await repo.get_user_by_username(admin_username)
            if existing_user is None:
                password_hash = auth.hash_password(admin_password)
                await repo.create_user(admin_username, password_hash, "admin")
                await session.commit()
                created_admin = True
    finally:
        await engine.dispose()

    return {
        "created_envelope": created_envelope,
        "created_admin": created_admin,
        "base_dir": str(paths.base_dir),
        "envelope_file": str(paths.master_envelope_file),
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="app_v4", description="NCM v4 backend CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    init_parser = sub.add_parser("init", help="Initialize key envelope and first admin user")
    init_parser.add_argument("--passphrase", help="Master passphrase (prompted if omitted)")
    init_parser.add_argument("--admin-username", default="admin")
    init_parser.add_argument(
        "--admin-password",
        help="Admin password (prompted if omitted)",
    )

    return parser.parse_args(argv)


def _prompt_secret(prompt: str) -> str:
    secret = getpass.getpass(prompt)
    if not secret:
        raise SystemExit("empty value not allowed")
    return secret


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.command != "init":
        raise SystemExit(f"unknown command: {args.command}")

    passphrase = args.passphrase or _prompt_secret("Master passphrase: ")
    admin_password = args.admin_password or _prompt_secret(
        f"Password for admin user '{args.admin_username}': "
    )

    settings = Settings()
    result = asyncio.run(
        init_command(
            settings=settings,
            master_passphrase=passphrase,
            admin_username=args.admin_username,
            admin_password=admin_password,
        )
    )

    print(f"base_dir: {result['base_dir']}")
    print(f"envelope: {result['envelope_file']}")
    print(f"envelope created: {result['created_envelope']}")
    print(f"admin created: {result['created_admin']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
