from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def _body(status: int, title: str, detail: str, type_: str = "about:blank") -> dict:
    return {"type": type_, "title": title, "status": status, "detail": detail}


def register_problem_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        detail = exc.detail
        if isinstance(detail, dict) and {"type", "title", "status", "detail"}.issubset(detail):
            body = detail
        else:
            body = _body(exc.status_code, exc.__class__.__name__, str(detail))
        return JSONResponse(body, status_code=exc.status_code, media_type="application/problem+json")

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            _body(422, "Validation Error", str(exc), "validation_error"),
            status_code=422,
            media_type="application/problem+json",
        )
