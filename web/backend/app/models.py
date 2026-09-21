"""Persistent SQLAlchemy models for the quiz system."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy import Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON


def to_pinyin(name: str) -> str:
    """Convert a Chinese name to its pinyin representation for sorting."""
    from pypinyin import lazy_pinyin

    return "".join(lazy_pinyin(name))


def utc_now() -> datetime:
    """Return an aware UTC timestamp suitable for model defaults."""
    return datetime.now(timezone.utc)


def new_config_key() -> str:
    """Return an opaque stable identifier used by portable configuration files."""
    return str(uuid4())


def as_utc(value: datetime) -> datetime:
    """Normalize SQLite's naive timestamp reads to the API's UTC contract."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class Base(DeclarativeBase):
    """Base class shared by all database models."""


class OptionGroup(Base):
    """An administrator-managed display section for font options."""

    __tablename__ = "option_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    config_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, default=new_config_key)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class FontOption(Base):
    """One font selectable from a group at and above its unlock difficulty."""

    __tablename__ = "font_options"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    config_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, default=new_config_key)
    group_id: Mapped[int] = mapped_column(ForeignKey("option_groups.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    pinyin: Mapped[str | None] = mapped_column(String(500), nullable=True)
    font_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    minimum_difficulty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        CheckConstraint("minimum_difficulty BETWEEN 1 AND 3", name="ck_font_option_difficulty"),
    )


class Question(Base):
    """A question whose correct response is one reusable font option."""

    __tablename__ = "questions"
    __table_args__ = (CheckConstraint("difficulty BETWEEN 1 AND 3", name="ck_question_difficulty"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    config_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, default=new_config_key)
    legacy_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    text: Mapped[str] = mapped_column(String(500), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False)
    correct_option_id: Mapped[int | None] = mapped_column(
        ForeignKey("font_options.id", ondelete="SET NULL"), nullable=True
    )
    explanation: Mapped[str] = mapped_column(String(1000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class QuestionRequest(Base):
    """Creation receipts survive question deletion and make batch retries safe."""

    __tablename__ = "question_requests"
    admin_id: Mapped[int] = mapped_column(ForeignKey("admins.id"), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    question_key: Mapped[str | None] = mapped_column(String(64), nullable=True)


class QuizSettings(Base):
    """The single configurable draw strategy and font preset list."""

    __tablename__ = "quiz_settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_settings_singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    question_count: Mapped[int] = mapped_column(Integer, nullable=False)
    modes: Mapped[dict[str, list[int]]] = mapped_column(JSON, nullable=False)
    font_presets: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class FontReference(Base):
    """An administrator-maintained public font comparison card."""

    __tablename__ = "font_references"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    config_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, default=new_config_key)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    image_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    note: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    section_id: Mapped[int | None] = mapped_column(ForeignKey("font_reference_sections.id"), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class FontReferenceSection(Base):
    """An administrator-managed display section for font reference cards."""

    __tablename__ = "font_reference_sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    config_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, default=new_config_key)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Admin(Base):
    """An account managed exclusively by the server-side CLI."""

    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class AdminSession(Base):
    """A revocable, hash-only administrator session token."""

    __tablename__ = "admin_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("admins.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class QuizAttempt(Base):
    """A 24-hour server-bound collection of selected question IDs."""

    __tablename__ = "quiz_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    question_ids: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    question_snapshots: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Submission(Base):
    """The immutable score belonging to one completed quiz attempt."""

    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("quiz_attempts.id"), nullable=False)
    display_name: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total: Mapped[int] = mapped_column(Integer, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    __table_args__ = (UniqueConstraint("attempt_id", name="uq_submission_attempt"),)


class SubmissionAnswer(Base):
    """An answer snapshot that survives later question edits or deletion."""

    __tablename__ = "submission_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[int] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[int | None] = mapped_column(
        ForeignKey("questions.id", ondelete="SET NULL"), nullable=True
    )
    question_text: Mapped[str] = mapped_column(String(500), nullable=False)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    options: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    selected: Mapped[str] = mapped_column(String(64), nullable=False)
    correct_answer: Mapped[str] = mapped_column(String(64), nullable=False)
    option_groups: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    selected_option_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    correct_option_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    explanation: Mapped[str] = mapped_column(String(1000), nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)


class Feedback(Base):
    """A public user report retained independently from email delivery."""

    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    nickname: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    contact_qq: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    client_url: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    context: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    email_status: Mapped[str] = mapped_column(String(16), nullable=False, default="disabled")
    email_error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class FeedbackAttachment(Base):
    """One user-selected image belonging to a feedback record."""

    __tablename__ = "feedback_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    feedback_id: Mapped[int] = mapped_column(ForeignKey("feedback.id", ondelete="CASCADE"), nullable=False)
    image_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SyncOutbox(Base):
    """Durable, retryable publication work for derived R2 JSON documents."""

    __tablename__ = "sync_outbox"
    __table_args__ = (UniqueConstraint("scope", "state_hash", name="uq_sync_outbox_scope_hash"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    state_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lock_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scope_fence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class SyncScopeState(Base):
    """Current and last-published hashes for one derived-data scope."""

    __tablename__ = "sync_scope_state"

    scope: Mapped[str] = mapped_column(String(32), primary_key=True)
    current_state_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    published_state_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
