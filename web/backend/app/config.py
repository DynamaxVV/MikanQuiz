"""Runtime configuration for the quiz API."""

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class AppSettings:
    """Settings loaded from environment variables.

    Attributes:
        database_url: SQLAlchemy database URL. SQLite is the production default.
        admin_session_hours: Lifetime for an administrator session.
        cookie_secure: Whether browser session cookies require HTTPS transport.
        r2_endpoint: Cloudflare R2 S3 API endpoint.
        r2_bucket: Bucket receiving private server-side uploads.
        r2_public_base_url: HTTPS delivery domain mapped to the bucket.
        log_level: Application and Uvicorn JSON logging threshold.
        access_log_path: Optional JSONL file for key request and audit events.
        access_log_max_bytes: Maximum size of the active key-access log before rotation.
        access_log_backup_count: Number of rotated key-access files to retain.
    """

    database_url: str = "sqlite:///./var/quiz.db"
    admin_session_hours: int = 8
    cookie_secure: bool = True
    r2_endpoint: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = ""
    r2_public_base_url: str = ""
    log_level: str = "INFO"
    access_log_path: str = ""
    access_log_max_bytes: int = 20 * 1024 * 1024
    access_log_backup_count: int = 14


def _parse_log_int(value: str, default: int, minimum: int) -> int:
    """Parse a bounded logging integer without making startup fail on bad config."""
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed >= minimum else default


def load_settings(env_file: Path | None = None) -> AppSettings:
    """Load .env defaults without overriding explicit process environment values."""
    values = load_env_file(env_file or default_env_file())
    get = lambda key, default="": os.getenv(key, values.get(key, default))
    database_url = get("QUIZ_DATABASE_URL", "sqlite:///./var/quiz.db")
    session_hours = int(get("QUIZ_ADMIN_SESSION_HOURS", "8"))
    cookie_secure = get("QUIZ_COOKIE_SECURE", "true").lower() not in {"0", "false", "no"}
    log_level = get("QUIZ_LOG_LEVEL", "INFO").upper()
    access_log_path = get("QUIZ_ACCESS_LOG_PATH").strip()
    access_log_max_bytes = _parse_log_int(
        get("QUIZ_ACCESS_LOG_MAX_BYTES", str(20 * 1024 * 1024)),
        20 * 1024 * 1024,
        1,
    )
    access_log_backup_count = _parse_log_int(
        get("QUIZ_ACCESS_LOG_BACKUP_COUNT", "14"),
        14,
        1,
    )
    if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
        log_level = "INFO"
    return AppSettings(
        database_url=database_url,
        admin_session_hours=session_hours,
        cookie_secure=cookie_secure,
        r2_endpoint=get("QUIZ_R2_ENDPOINT"),
        r2_access_key_id=get("QUIZ_R2_ACCESS_KEY_ID"),
        r2_secret_access_key=get("QUIZ_R2_SECRET_ACCESS_KEY"),
        r2_bucket=get("QUIZ_R2_BUCKET"),
        r2_public_base_url=get("QUIZ_R2_PUBLIC_BASE_URL"),
        log_level=log_level,
        access_log_path=access_log_path,
        access_log_max_bytes=access_log_max_bytes,
        access_log_backup_count=access_log_backup_count,
    )


def default_env_file() -> Path:
    """Return the local configuration file, allowing a deployment override."""
    configured = os.getenv("QUIZ_ENV_FILE")
    if configured:
        return Path(configured).expanduser()
    return Path(__file__).resolve().parents[1] / ".env"


def load_env_file(path: Path) -> dict[str, str]:
    """Read a deliberately small KEY=VALUE file without logging its contents."""
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key and key.replace("_", "").isalnum():
            values[key] = value.strip().strip("\"'").strip()
    return values
