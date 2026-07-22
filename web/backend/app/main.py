"""FastAPI application factory and process entry point."""

from fastapi import FastAPI

from app.api import router
from app.config import AppSettings, load_settings
from app.database import Database
from app.errors import ApiError, api_error_handler, validation_error_handler
from app.schemas import HealthResponse


def create_app(settings: AppSettings | None = None) -> FastAPI:
    """Create an API app without changing production database schema on startup."""
    settings = settings or load_settings()
    app = FastAPI(title="砂糖字形课堂 API", version="1.0.0", docs_url="/api/docs")
    app.state.database = Database(settings.database_url)
    app.state.settings = settings
    app.add_exception_handler(ApiError, api_error_handler)
    from fastapi.exceptions import RequestValidationError

    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.include_router(router)
    add_health_route(app)
    return app


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
