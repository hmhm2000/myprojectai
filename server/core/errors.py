"""Application errors returned to the client.

Every error carries a stable machine-readable ``code`` (e.g. ``"sale.exceeds_available"``)
plus optional ``params``. The frontend translates the code using its locale files, so no
user-facing wording lives in the backend. ``detail`` is an English description for logs,
API docs and debugging.

Response body::

    {"detail": "Cannot sell more than ...", "code": "sale.exceeds_available", "params": {...}}
"""
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, status_code: int, code: str, detail: str, headers: dict | None = None, **params: Any):
        super().__init__(detail)
        self.status_code = status_code
        self.code = code
        self.detail = detail
        self.params = params
        self.headers = headers


class NotFound(AppError):
    def __init__(self, code: str, detail: str, **params: Any):
        super().__init__(404, code, detail, **params)


class BadRequest(AppError):
    def __init__(self, code: str, detail: str, **params: Any):
        super().__init__(400, code, detail, **params)


async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": exc.code, "params": exc.params},
        headers=exc.headers,
    )
