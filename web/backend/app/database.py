"""SQLAlchemy database creation and SQLite connection settings."""

from collections.abc import Generator

from fastapi import Request
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


class Database:
    """Own an engine and short-lived synchronous sessions for one API app."""

    def __init__(self, url: str) -> None:
        """Create an engine configured for a single-host SQLite deployment."""
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        self.engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)
        if url.startswith("sqlite"):
            event.listen(self.engine, "connect", _configure_sqlite)

    def check_health(self) -> None:
        """Raise if the database cannot execute a trivial read."""
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))


def _configure_sqlite(dbapi_connection: object, _: object) -> None:
    """Enable the SQLite settings required by the documented deployment."""
    cursor = dbapi_connection.cursor()  # type: ignore[union-attr]
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


def get_session(request: Request) -> Generator[Session, None, None]:
    """Yield one session per request and always close it afterwards."""
    session = request.app.state.database.sessions()
    try:
        yield session
    finally:
        session.close()
