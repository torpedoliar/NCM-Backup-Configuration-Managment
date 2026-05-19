from __future__ import annotations

from fastapi import HTTPException


def problem(status_code: int, title: str, detail: str, type_: str = "about:blank") -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "type": type_,
            "title": title,
            "status": status_code,
            "detail": detail,
        },
    )
