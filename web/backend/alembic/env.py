"""Alembic environment configured from the same database URL as the API."""

from logging.config import fileConfig
from pathlib import Path
import sys

from alembic import context
from sqlalchemy import engine_from_config, pool


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import load_settings  # noqa: E402
from app.database import ensure_sqlite_parent  # noqa: E402
from app.models import Base  # noqa: E402


config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
configured_url = config.get_main_option("sqlalchemy.url")
default_url = "sqlite:///./var/quiz.db"
database_url = configured_url if configured_url != default_url else load_settings().database_url
config.set_main_option("sqlalchemy.url", database_url)
ensure_sqlite_parent(database_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Generate SQL without connecting when Alembic is run in offline mode."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run upgrades against the configured local database in one connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
