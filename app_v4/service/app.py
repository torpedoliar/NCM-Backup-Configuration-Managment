from __future__ import annotations

from fastapi import FastAPI

from app_v4.service.runtime import ServiceRuntime


def create_app(runtime: ServiceRuntime) -> FastAPI:
    app = FastAPI(title="NCM v4 Backend", version="4.0.0-dev")
    app.state.runtime = runtime

    from app_v4.service.api import auth, backups, credentials, jobs, switches, system, users, ws

    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(users.router, prefix="/api/v1")
    app.include_router(credentials.router, prefix="/api/v1")
    app.include_router(switches.router, prefix="/api/v1")
    app.include_router(backups.router, prefix="/api/v1")
    app.include_router(jobs.router, prefix="/api/v1")
    app.include_router(system.router, prefix="/api/v1")
    app.include_router(ws.router)
    return app
