"""FastAPI application factory and process entry point."""

import logging
import json
from pathlib import Path
from time import perf_counter
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import FastAPI
from fastapi import Request
from fastapi.staticfiles import StaticFiles
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api import router
from app.config import AppSettings, load_settings
from app.database import Database
from app.errors import ApiError, api_error_handler, validation_error_handler
from app.logging import bind_context, configure_logging, log_event, reset_context
from app.schemas import HealthResponse
from app.services.feedback import FeedbackRateLimiter, MAX_REQUEST_BODY_BYTES


def create_app(settings: AppSettings | None = None) -> FastAPI:
    """Create an API app without changing production database schema on startup."""
    settings = settings or load_settings()
    configure_logging(
        settings.log_level,
        access_log_path=settings.access_log_path,
        access_log_max_bytes=settings.access_log_max_bytes,
        access_log_backup_count=settings.access_log_backup_count,
    )
    app = FastAPI(title="砂糖字形课堂 API", version="1.0.6", docs_url="/api/docs")
    app.state.database = Database(settings.database_url)
    app.state.settings = settings
    app.state.feedback_rate_limiter = FeedbackRateLimiter(settings.feedback_rate_limit_per_hour)
    if settings.storage_backend == "local":
        local_url = urlparse(settings.local_public_base_url)
        Path(settings.local_storage_path).mkdir(parents=True, exist_ok=True)
        app.mount(
            local_url.path.rstrip("/") or "/uploads",
            StaticFiles(directory=settings.local_storage_path),
            name="local-uploads",
        )
    app.add_exception_handler(ApiError, api_error_handler)
    from fastapi.exceptions import RequestValidationError

    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.include_router(router)
    app.add_middleware(
        RequestBodySizeLimitMiddleware,
        limit=settings.config_max_bytes,
        feedback_limit=MAX_REQUEST_BODY_BYTES,
    )
    add_request_logging(app)
    add_health_route(app)
    return app


class RequestBodySizeLimitMiddleware:
    """Bound config-import bodies before FastAPI parses JSON or Pydantic models."""

    def __init__(self, app: ASGIApp, limit: int, feedback_limit: int) -> None:
        self.app = app
        self.limit = limit
        self.feedback_limit = feedback_limit

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if scope.get("type") != "http" or scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return
        if path in {"/api/v1/admin/config/import", "/api/v1/admin/config/import/validate"}:
            limit = self.limit
        elif path == "/api/v1/feedback":
            limit = self.feedback_limit
        else:
            await self.app(scope, receive, send)
            return
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        declared = headers.get(b"content-length")
        if declared:
            try:
                if int(declared) > limit:
                    await self._reject(send)
                    return
            except ValueError:
                pass
        total = 0
        chunks: list[bytes] = []
        while True:
            message = await receive()
            if message.get("type") != "http.request":
                await self.app(scope, self._replay(chunks, message), send)
                return
            body = message.get("body", b"")
            total += len(body)
            if total > limit:
                await self._reject(send)
                return
            chunks.append(body)
            if not message.get("more_body", False):
                break
        await self.app(scope, self._replay(chunks), send)

    async def _reject(self, send: Send) -> None:
        body = json.dumps(
            {"error": {"code": "CONFIG_BODY_TOO_LARGE", "message": "配置文件过大"}},
            ensure_ascii=False,
        ).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})

    def _replay(self, chunks: list[bytes], terminal: Message | None = None) -> Receive:
        messages = [
            {
                "type": "http.request",
                "body": chunk,
                "more_body": index < len(chunks) - 1,
            }
            for index, chunk in enumerate(chunks)
        ]
        if not messages:
            messages = [{"type": "http.request", "body": b"", "more_body": False}]
        if terminal is not None:
            messages.append(terminal)
        iterator = iter(messages)

        async def replay() -> Message:
            try:
                return next(iterator)
            except StopIteration:
                return {"type": "http.disconnect"}

        return replay


def add_request_logging(app: FastAPI) -> None:
    """Attach access, request ID and uncaught-exception logging to every API call."""
    @app.middleware("http")
    async def log_request(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = str(uuid4())
        client_ip = request.client.host if request.client else "unknown"
        token = bind_context(
            request_id=request_id,
            client_ip=client_ip,
            user_agent=request.headers.get("user-agent", "")[:512],
        )
        started_at = perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception:
            log_event("unhandled_exception", logging.ERROR, exc_info=True)
            raise
        finally:
            if request.url.path != "/api/health" or status_code >= 400:
                route = request.scope.get("route")
                log_event(
                    "http_request",
                    logging.WARNING if status_code >= 400 else logging.INFO,
                    method=request.method,
                    path=request.url.path,
                    route=getattr(route, "path", request.url.path),
                    status_code=status_code,
                    duration_ms=round((perf_counter() - started_at) * 1000, 2),
                )
            reset_context(token)


def add_health_route(app: FastAPI) -> None:
    """Register the non-sensitive process and database readiness endpoint."""
    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        """Confirm the database is reachable without exposing configuration data."""
        try:
            app.state.database.check_health()
        except Exception as error:
            raise ApiError(503, "DATABASE_UNAVAILABLE", "数据库暂时不可用") from error
        return HealthResponse(status="ok", database="ok")


app = create_app()
