"""Fixtures that exercise Alembic and the FastAPI app against fresh SQLite files."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
import pytest

from app.config import AppSettings
from app.database import Database
from app.main import create_app
from app.services.admin import add_admin


BACKEND_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def database_url(tmp_path: Path) -> str:
    """Upgrade a brand-new SQLite file through Alembic before each API test."""
    database_path = tmp_path / "quiz.db"
    url = f"sqlite:///{database_path}"
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    return url


@pytest.fixture()
def client(database_url: str) -> TestClient:
    """Create a migrated app with exactly one CLI-managed test administrator."""
    database_path = Path(database_url.removeprefix("sqlite:///"))
    app = create_app(
        AppSettings(
            database_url=database_url,
            cookie_secure=False,
            access_log_path=str(database_path.parent / "quiz-access.jsonl"),
        )
    )
    with app.state.database.sessions() as session:
        add_admin(session, "operator", "correct-password")
    return TestClient(app)


@pytest.fixture()
def database(database_url: str) -> Database:
    """Return an independent short-session connection helper for controlled setup."""
    return Database(database_url)


def admin_headers(client: TestClient) -> dict[str, str]:
    """Log in through the real HTTP route and make its Bearer header."""
    response = client.post(
        "/api/v1/admin/miniprogram/login",
        json={"username": "operator", "password": "correct-password"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}
