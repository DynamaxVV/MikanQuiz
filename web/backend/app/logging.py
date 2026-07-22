"""Structured, request-correlated application logging."""

from contextvars import ContextVar, Token
from datetime import date, datetime, timezone
import json
import logging
import sys
from typing import Any


LOGGER_NAME = "mikan_quiz"
_context: ContextVar[dict[str, Any]] = ContextVar("log_context", default={})


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


def configure_logging(level: str) -> None:
    """Configure JSON output for app and Uvicorn logs without external packages."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    for name in (LOGGER_NAME, "uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers = [handler]
        logger.propagate = False
        logger.setLevel(level)


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
