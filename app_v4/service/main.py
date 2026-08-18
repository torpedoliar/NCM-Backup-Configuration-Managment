from __future__ import annotations

import asyncio
import threading

import uvicorn
from fastapi import FastAPI

from app_v4.core.config import Settings
from app_v4.service.app import create_app
from app_v4.service.runtime import build_runtime

_runtime_engine = None


def app_import_string() -> str:
    return "app_v4.service.main:create_runtime_app"


def uvicorn_kwargs(settings: Settings) -> dict[str, object]:
    return {
        "app": app_import_string(),
        "host": settings.service_host,
        "port": settings.service_port,
        "factory": True,
        "log_level": "info",
    }


_runtime_loop: asyncio.AbstractEventLoop | None = None
_runtime_thread: threading.Thread | None = None


def _persistent_loop() -> asyncio.AbstractEventLoop:
    """Return a long-lived event loop for the backend runtime.

    The scheduler (AsyncIOScheduler) binds itself to the loop it is started on.
    Building the runtime with a throwaway loop (e.g. asyncio.run) leaves the
    scheduler pointing at a closed loop, so later job additions fail with
    "Event loop is closed" and scheduled backups silently never fire.
    """
    global _runtime_loop, _runtime_thread
    if _runtime_loop is None or _runtime_loop.is_closed():
        _runtime_loop = asyncio.new_event_loop()
        _runtime_thread = threading.Thread(
            target=_runtime_loop.run_forever, daemon=True, name="ncm-v4-runtime"
        )
        _runtime_thread.start()
    return _runtime_loop


async def _create_runtime_app_async() -> FastAPI:
    global _runtime_engine
    settings = Settings()
    runtime, engine = await build_runtime(settings)
    _runtime_engine = engine
    return create_app(runtime)


def create_runtime_app() -> FastAPI:
    loop = _persistent_loop()
    future = asyncio.run_coroutine_threadsafe(_create_runtime_app_async(), loop)
    return future.result()


def main() -> None:
    from app_v4.core.logging import configure_file_logger
    from app_v4.core.paths import resolve_paths
    settings = Settings()
    configure_file_logger(resolve_paths(settings).logs_dir)
    uvicorn.run(**uvicorn_kwargs(settings))


if __name__ == "__main__":
    main()
