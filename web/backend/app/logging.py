"""Structured, request-correlated application logging."""

from contextvars import ContextVar, Token
from datetime import date, datetime, timezone
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys
from typing import Any


LOGGER_NAME = "mikan_quiz"
_context: ContextVar[dict[str, Any]] = ContextVar("log_context", default={})
KEY_ACCESS_EVENTS = frozenset(
    {
        "http_request",
        "quiz_attempt_created",
        "quiz_submitted",
        "quiz_submission_replayed",
        "quiz_business_error",
        "admin_login_succeeded",
        "admin_login_failed",
        "admin_session_invalid",
        "admin_logout",
        "config_exported",
        "config_import_validated",
        "config_imported",
    }
)


class JsonFormatter(logging.Formatter):
    """Render application and Uvicorn records as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        """Serialize stable metadata without interpolating sensitive arguments."""
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
        }
        payload.update(_context.get())
        payload.update(getattr(record, "log_fields", {}))
        payload.setdefault("event", getattr(record, "event", record.name))
        if record.exc_info:
            payload["traceback"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=_json_default)


def _json_default(value: Any) -> str:
    """Keep logging available when a safe field is a date or an enum-like object."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


class AccessLogFilter(logging.Filter):
    """Keep only request and security/quiz audit events in the dedicated file."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Accept events whose fields are safe and useful for access review."""
        return getattr(record, "event", "") in KEY_ACCESS_EVENTS


def configure_logging(
    level: str,
    access_log_path: str = "",
    access_log_max_bytes: int = 20 * 1024 * 1024,
    access_log_backup_count: int = 14,
) -> None:
    """Configure JSON stdout logging and an optional rotating access-log file."""
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(JsonFormatter())
    stdout_handler.setLevel(level)
    stdout_handler._mikan_quiz_owned = True  # type: ignore[attr-defined]
    handlers: list[logging.Handler] = [stdout_handler]
    if access_log_path:
        path = Path(access_log_path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        access_handler = RotatingFileHandler(
            path,
            maxBytes=access_log_max_bytes,
            backupCount=access_log_backup_count,
            encoding="utf-8",
            delay=True,
        )
        access_handler.setFormatter(JsonFormatter())
        access_handler.setLevel(logging.INFO)
        access_handler.addFilter(AccessLogFilter())
        access_handler._mikan_quiz_owned = True  # type: ignore[attr-defined]
        handlers.append(access_handler)

    logger_names = (LOGGER_NAME, "uvicorn", "uvicorn.error", "uvicorn.access")
    old_handlers: dict[int, logging.Handler] = {}
    for name in logger_names:
        for old_handler in logging.getLogger(name).handlers:
            if getattr(old_handler, "_mikan_quiz_owned", False):
                old_handlers[id(old_handler)] = old_handler
    for old_handler in old_handlers.values():
        old_handler.close()

    for name in logger_names:
        logger = logging.getLogger(name)
        logger.handlers = handlers if name == LOGGER_NAME else [stdout_handler]
        logger.propagate = False
        logger.disabled = False
        # Keep INFO access events flowing to the dedicated file even when the
        # general stdout threshold is WARNING or ERROR.
        logger.setLevel(
            ("DEBUG" if level == "DEBUG" else "INFO") if name == LOGGER_NAME else level
        )


def bind_context(**fields: Any) -> Token[dict[str, Any]]:
    """Add request-scoped safe fields and return a token for later reset."""
    return _context.set({**_context.get(), **fields})


def reset_context(token: Token[dict[str, Any]]) -> None:
    """Remove request fields after the current request finishes."""
    _context.reset(token)


def log_event(
    event: str, level: int = logging.INFO, exc_info: bool = False, **fields: Any
) -> None:
    """Write one structured event; callers must pass only approved safe fields."""
    logging.getLogger(LOGGER_NAME).log(
        level,
        event,
        extra={"event": event, "log_fields": fields},
        exc_info=exc_info,
    )
