from __future__ import annotations

import asyncio
import threading
from typing import TypeVar

import uvicorn
from fastapi import FastAPI

from app_v4.core.config import Settings
from app_v4.service.app import create_app
from app_v4.service.runtime import build_runtime

T = TypeVar("T")
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


def _run_async_from_sync(coro) -> T:
    result: list[T] = []
    errors: list[BaseException] = []

    def runner() -> None:
        try:
            result.append(asyncio.run(coro))
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=runner)
    thread.start()
    thread.join()
    if errors:
        raise errors[0]
    return result[0]


async def _create_runtime_app_async() -> FastAPI:
    global _runtime_engine
    settings = Settings()
    runtime, engine = await build_runtime(settings)
    _runtime_engine = engine
    return create_app(runtime)


def create_runtime_app() -> FastAPI:
    return _run_async_from_sync(_create_runtime_app_async())


def main() -> None:
    settings = Settings()
    uvicorn.run(**uvicorn_kwargs(settings))


if __name__ == "__main__":
    main()
