"""Stable error objects and FastAPI exception handlers."""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import logging

from app.logging import log_event


class ApiError(Exception):
    """An expected API failure with a stable public error code."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        """Save the HTTP status and Chinese user-displayable message."""
        self.status_code = status_code
        self.code = code
        self.message = message


async def api_error_handler(request: Request, error: ApiError) -> JSONResponse:
    """Render an expected domain error in the public response envelope."""
    log_event(
        "api_error",
        logging.WARNING,
        status_code=error.status_code,
        error_code=error.code,
        path=request.url.path,
    )
    return JSONResponse(
        status_code=error.status_code,
        content={"error": {"code": error.code, "message": error.message}},
    )


async def validation_error_handler(
    request: Request, _: RequestValidationError
) -> JSONResponse:
    """Avoid exposing Pydantic internals while preserving a stable error code."""
    log_event(
        "api_error",
        logging.WARNING,
        status_code=422,
        error_code="VALIDATION_ERROR",
        path=request.url.path,
    )
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "VALIDATION_ERROR", "message": "请求参数不正确"}},
    )
