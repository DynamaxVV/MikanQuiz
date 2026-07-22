"""FastAPI application factory and process entry point."""

import logging
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI
from fastapi import Request

from app.api import router
from app.config import AppSettings, load_settings
from app.database import Database
from app.errors import ApiError, api_error_handler, validation_error_handler
from app.logging import bind_context, configure_logging, log_event, reset_context
from app.schemas import HealthResponse


def create_app(settings: AppSettings | None = None) -> FastAPI:
    """Create an API app without changing production database schema on startup."""
    settings = settings or load_settings()
    configure_logging(settings.log_level)
    app = FastAPI(title="砂糖字形课堂 API", version="1.0.0", docs_url="/api/docs")
    app.state.database = Database(settings.database_url)
    app.state.settings = settings
    app.add_exception_handler(ApiError, api_error_handler)
    from fastapi.exceptions import RequestValidationError

    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.include_router(router)
    add_request_logging(app)
    add_health_route(app)
    return app


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
