"""Pydantic request and response schemas for the versioned HTTP API."""

from datetime import datetime
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


Mode = Literal["beginner", "proficient", "challenge"]
Answer = Literal["A", "B", "C", "D"]


class ApiModel(BaseModel):
    """Use snake_case JSON and reject silently ignored request fields."""

    model_config = ConfigDict(extra="forbid")


class QuestionWrite(ApiModel):
    """The complete editable representation of one fixed-option question."""

    text: str = Field(min_length=1, max_length=500)
    image_url: str | None = Field(default=None, max_length=2048)
    difficulty: int = Field(ge=1, le=5)
    options: list[str]
    answer: Answer
    explanation: str = Field(min_length=1, max_length=1000)

    @field_validator("text", "explanation", mode="after")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        """Reject whitespace-only required text before it reaches the database."""
        value = value.strip()
        if not value:
            raise ValueError("内容不能为空")
        return value

    @field_validator("image_url", mode="after")
    @classmethod
    def validate_image_url(cls, value: str | None) -> str | None:
        """Permit only external HTTPS image references in this first release."""
        if value is None or not value.strip():
            return None
        value = value.strip()
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("图片地址必须是 HTTPS URL")
        return value

    @field_validator("options", mode="after")
    @classmethod
    def validate_options(cls, values: list[str]) -> list[str]:
        """Require exactly four non-empty options with safe display lengths."""
        if len(values) != 4:
            raise ValueError("必须填写选项")
        cleaned = [value.strip() for value in values]
        if any(not value or len(value) > 500 for value in cleaned):
            raise ValueError("选项不能为空且不能超过 500 字")
        return cleaned


class QuestionPatch(ApiModel):
    """A partial question update, validated as a whole after merging server data."""

    text: str | None = Field(default=None, min_length=1, max_length=500)
    image_url: str | None = Field(default=None, max_length=2048)
    difficulty: int | None = Field(default=None, ge=1, le=5)
    options: list[str] | None = None
    answer: Answer | None = None
    explanation: str | None = Field(default=None, min_length=1, max_length=1000)


class QuestionResponse(ApiModel):
    """A full question returned only to authenticated administrators."""

    id: int
    text: str
    image_url: str | None
    difficulty: int
    options: list[str]
    answer: Answer
    explanation: str
    created_at: datetime
    updated_at: datetime


class ImageUploadResponse(ApiModel):
    """The public image URL produced by the server-side R2 upload."""

    image_url: str


class FontReferenceWrite(ApiModel):
    """One administrator-maintained public font comparison image."""

    title: str = Field(min_length=1, max_length=100)
    image_url: str = Field(min_length=1, max_length=2048)
    note: str = Field(default="", max_length=500)

    @field_validator("title", mode="after")
    @classmethod
    def strip_title(cls, value: str) -> str:
        """Normalize and require a visible title."""
        value = value.strip()
        if not value:
            raise ValueError("标题不能为空")
        return value

    @field_validator("note", mode="after")
    @classmethod
    def strip_note(cls, value: str) -> str:
        """Normalize an optional note without making it required."""
        return value.strip()

    @field_validator("image_url", mode="after")
    @classmethod
    def validate_image_url(cls, value: str) -> str:
        """Only allow externally deliverable HTTPS image URLs."""
        value = value.strip()
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("图片地址必须是 HTTPS URL")
        return value


class FontReferenceResponse(ApiModel):
    """A public-safe font comparison image record."""

    id: int
    title: str
    image_url: str
    note: str
    created_at: datetime


class PublicQuestion(ApiModel):
    """A question without answer or explanation, safe for anonymous clients."""

    id: int
    text: str
    image_url: str | None
    difficulty: int
    options: list[str]


class QuestionPage(ApiModel):
    """A bounded page of admin questions."""

    items: list[QuestionResponse]
    page: int
    page_size: int
    total: int


class SettingsResponse(ApiModel):
    """Question count, weighted modes and editable font shortcut strings."""

    question_count: int = Field(ge=1, le=50)
    modes: dict[Mode, list[int]]
    font_presets: list[str]

    @model_validator(mode="after")
    def validate_modes(self) -> "SettingsResponse":
        """Ensure all modes have five non-negative weights and a selectable star."""
        expected = {"beginner", "proficient", "challenge"}
        if set(self.modes) != expected:
            raise ValueError("必须提供三种难度的权重")
        for weights in self.modes.values():
            if len(weights) != 5 or any(weight < 0 for weight in weights):
                raise ValueError("每种难度需要五个非负权重")
            if not any(weight > 0 for weight in weights):
                raise ValueError("每种难度至少一个权重大于零")
        if len(self.font_presets) > 100 or any(
            not item.strip() or len(item.strip()) > 50 for item in self.font_presets
        ):
            raise ValueError("字体快捷项格式不正确")
        self.font_presets = [item.strip() for item in self.font_presets]
        return self


class StrategyUpdate(ApiModel):
    """The subset of settings editable on the draw-strategy screen."""

    question_count: int = Field(ge=1, le=50)
    modes: dict[Mode, list[int]]

    def as_settings(self, font_presets: list[str]) -> SettingsResponse:
        """Validate this update with the preserved font presets included."""
        return SettingsResponse(
            question_count=self.question_count,
            modes=self.modes,
            font_presets=font_presets,
        )


class FontPresetsUpdate(ApiModel):
    """The subset of settings editable on the font shortcuts screen."""

    font_presets: list[str]


class AttemptCreate(ApiModel):
    """Choose a configured public difficulty mode."""

    mode: Mode


class AttemptCreated(ApiModel):
    """A new client-held token and its clean question collection."""

    attempt_token: str
    mode: Mode
    expires_at: datetime
    questions: list[PublicQuestion]


class AttemptCurrent(ApiModel):
    """The resume payload for an unfinished 24-hour attempt."""

    mode: Mode
    expires_at: datetime
    questions: list[PublicQuestion]


class AttemptSubmit(ApiModel):
    """The complete selection map submitted once for one server-bound attempt."""

    display_name: str = Field(default="", max_length=20)
    answers: dict[int, Answer]

    @field_validator("display_name", mode="after")
    @classmethod
    def strip_display_name(cls, value: str) -> str:
        """Keep anonymous names short and plain without storing identifiers."""
        return value.strip()


class SubmissionDetail(ApiModel):
    """One immutable answer record revealed only after scoring."""

    question_id: int | None
    question_text: str
    image_url: str | None
    options: list[str]
    selected: Answer
    correct_answer: Answer
    explanation: str
    is_correct: bool


class SubmissionResult(ApiModel):
    """Stable result returned by both first submission and idempotent retries."""

    submission_id: int
    display_name: str
    mode: Mode
    score: int
    correct_count: int
    total: int
    submitted_at: datetime
    details: list[SubmissionDetail]


class SubmissionListItem(ApiModel):
    """Summary record for a paginated admin history table."""

    id: int
    display_name: str
    mode: Mode
    score: int
    correct_count: int
    total: int
    submitted_at: datetime


class SubmissionPage(ApiModel):
    """A bounded page of permanent, IP-free submission records."""

    items: list[SubmissionListItem]
    page: int
    page_size: int
    total: int


class AdminCredentials(ApiModel):
    """Credentials accepted by both Web and Mini Program login routes."""

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=256)


class AdminSessionResponse(ApiModel):
    """A bearer token returned only after successful administrator login."""

    token: str
    expires_at: datetime
    username: str


class AdminStatus(ApiModel):
    """The safe current-session representation for protected clients."""

    username: str
    expires_at: datetime


class HealthResponse(ApiModel):
    """The intentionally sparse liveness and database readiness response."""

    status: Literal["ok"]
    database: Literal["ok"]
