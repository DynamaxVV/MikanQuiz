"""Validation helpers, rate limiting, and SMTP notifications for public feedback."""

from collections import defaultdict, deque
from dataclasses import dataclass
from email.message import EmailMessage
import json
import re
import smtplib
from threading import Lock
from time import monotonic
from typing import Any

from app.config import AppSettings


MAX_MESSAGE_LENGTH = 2000
MAX_CONTACT_QQ_LENGTH = 20
MAX_CLIENT_URL_LENGTH = 2048
MAX_CONTEXT_BYTES = 5000
MAX_ATTACHMENTS = 3
MAX_IMAGE_BYTES = 3 * 1024 * 1024
MAX_REQUEST_BODY_BYTES = MAX_ATTACHMENTS * MAX_IMAGE_BYTES + 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
QQ_PATTERN = re.compile(r"^\d{5,20}$")


class FeedbackEmailError(RuntimeError):
    """Raised when an enabled SMTP notification cannot be delivered."""


class FeedbackRateLimiter:
    """Keep a small process-local submission window without persisting client IPs."""

    def __init__(self, limit: int, window_seconds: int = 3600) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, client_key: str) -> bool:
        now = monotonic()
        with self._lock:
            events = self._events[client_key]
            while events and now - events[0] >= self.window_seconds:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(now)
            return True


@dataclass(frozen=True)
class FeedbackNotification:
    """Safe, already-normalized values rendered into one notification email."""

    feedback_id: int
    message: str
    contact_qq: str | None
    source: str
    client_url: str
    context: dict[str, Any]
    image_urls: tuple[str, ...]
    created_at: str


def normalize_text(value: str | None, field: str, maximum: int) -> str:
    normalized = (value or "").strip()
    if len(normalized) > maximum:
        raise ValueError(f"{field}不能超过 {maximum} 个字符")
    return normalized


def validate_contact_qq(value: str) -> str | None:
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > MAX_CONTACT_QQ_LENGTH or not QQ_PATTERN.fullmatch(normalized):
        raise ValueError("联系 QQ 号格式不正确")
    return normalized


def validate_context(raw: str | None) -> dict[str, Any]:
    if not raw or not raw.strip():
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError("反馈上下文格式不正确") from error
    if not isinstance(value, dict):
        raise ValueError("反馈上下文格式不正确")
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > MAX_CONTEXT_BYTES:
        raise ValueError("反馈上下文过大")
    return value


def send_feedback_email(settings: AppSettings, notification: FeedbackNotification) -> str:
    """Send one notification, returning disabled when SMTP is intentionally unset."""
    recipients = tuple(item.strip() for item in settings.feedback_email_to.split(",") if item.strip())
    if not recipients:
        return "disabled"
    if not settings.feedback_smtp_host:
        raise FeedbackEmailError("SMTP 主机未配置")
    sender = settings.feedback_email_from or settings.feedback_smtp_username
    if not sender:
        raise FeedbackEmailError("反馈发件地址未配置")
    if bool(settings.feedback_smtp_username) != bool(settings.feedback_smtp_password):
        raise FeedbackEmailError("SMTP 账号配置不完整")

    lines = [
        f"反馈编号：{notification.feedback_id}",
        f"提交时间：{notification.created_at}",
        f"来源页面：{notification.source}",
        f"页面地址：{notification.client_url or '未提供'}",
        f"联系 QQ 号：{notification.contact_qq or '未提供'}",
        "",
        "反馈内容：",
        notification.message,
    ]
    if notification.context:
        lines.extend(["", "答题上下文：", json.dumps(notification.context, ensure_ascii=False, indent=2)])
    if notification.image_urls:
        lines.extend(["", "图片：", *notification.image_urls])
    body = "\n".join(lines)
    email = EmailMessage()
    email["Subject"] = f"MikanQuiz 用户反馈 #{notification.feedback_id}"
    email["From"] = sender
    email["To"] = ", ".join(recipients)
    email.set_content(body)

    try:
        smtp_class = smtplib.SMTP if settings.feedback_smtp_starttls or settings.feedback_smtp_port != 465 else smtplib.SMTP_SSL
        with smtp_class(settings.feedback_smtp_host, settings.feedback_smtp_port, timeout=10) as smtp:
            if settings.feedback_smtp_starttls:
                smtp.starttls()
            if settings.feedback_smtp_username:
                smtp.login(settings.feedback_smtp_username, settings.feedback_smtp_password)
            smtp.send_message(email)
    except (OSError, smtplib.SMTPException) as error:
        raise FeedbackEmailError("SMTP 投递失败") from error
    return "sent"
