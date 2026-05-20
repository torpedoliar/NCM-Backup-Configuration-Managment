from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app_v4.core.paths import resolve_paths
from app_v4.service.problem_handlers import register_problem_handlers
from app_v4.service.runtime import ServiceRuntime


def create_app(runtime: ServiceRuntime) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await runtime.shutdown()

    app = FastAPI(title="NCM v4 Backend", version="4.0.0-dev", lifespan=lifespan)
    app.state.runtime = runtime
    register_problem_handlers(app)
    paths = resolve_paths(runtime.settings)

    from app_v4.service.api import audit, auth, backups, credentials, jobs, switches, system, users, ws

    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(audit.router, prefix="/api/v1")
    app.include_router(users.router, prefix="/api/v1")
    app.include_router(credentials.router, prefix="/api/v1")
    app.include_router(switches.router, prefix="/api/v1")
    app.include_router(backups.router, prefix="/api/v1")
    app.include_router(jobs.router, prefix="/api/v1")
    app.include_router(system.router, prefix="/api/v1")
    app.include_router(ws.router)

    assets_dir = paths.static_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def web_fallback(full_path: str):
        index = paths.static_dir / "index.html"
        if index.exists() and not full_path.startswith("api/") and full_path != "ws":
            return FileResponse(index)
        raise HTTPException(status_code=404, detail="Not Found")

    return app
