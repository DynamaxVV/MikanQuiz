"""Migration and server-only administrator CLI checks."""

import argparse
import sqlite3

import pytest

from app.admin_cli import run_command
from app.config import load_settings


def test_empty_database_migration_has_integrity_and_seed(database_url: str) -> None:
    """Prove Alembic upgrades an empty SQLite file to a readable valid schema."""
    path = database_url.removeprefix("sqlite:///")
    connection = sqlite3.connect(path)
    try:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "20260722_0002"
        assert connection.execute("SELECT question_count FROM quiz_settings WHERE id = 1").fetchone()[0] == 10
    finally:
        connection.close()


def test_cli_refuses_to_disable_the_last_active_admin(
    database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise the actual CLI service path instead of only testing a policy helper."""
    monkeypatch.setenv("QUIZ_DATABASE_URL", database_url)
    assert run_command(argparse.Namespace(command="add", username="operator", password="correct-password")) == "管理员账号已创建"
    with pytest.raises(ValueError, match="最后一个有效管理员"):
        run_command(argparse.Namespace(command="disable", username="operator"))


def test_cli_lists_admin_accounts(database_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the recovery-oriented account listing command directly testable."""
    monkeypatch.setenv("QUIZ_DATABASE_URL", database_url)
    run_command(
        argparse.Namespace(
            command="add", username="operator", password="correct-password"
        )
    )
    listed = run_command(argparse.Namespace(command="list"))
    assert listed == "operator\t启用"


def test_settings_load_dotenv_without_overriding_process_values(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Read local secrets from a file while preserving deployment environment overrides."""
    config = tmp_path / ".env"
    config.write_text(
        "QUIZ_R2_BUCKET=file-bucket\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("QUIZ_R2_BUCKET", raising=False)
    monkeypatch.setenv("QUIZ_R2_PUBLIC_BASE_URL", "https://override.example.test")
    settings = load_settings(config)
    assert settings.r2_bucket == "file-bucket"
    assert settings.r2_public_base_url == "https://override.example.test"
