"""Pydantic request and response schemas for the versioned HTTP API."""

from datetime import datetime
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


Mode = Literal["beginner", "proficient", "challenge"]
Answer = int


class ApiModel(BaseModel):
    """Use snake_case JSON and reject silently ignored request fields."""

    model_config = ConfigDict(extra="forbid")


class OptionGroupWrite(ApiModel):
    """One complete editable option group and its options."""

    id: int | None = None
    name: str = Field(min_length=1, max_length=100)
    sort_order: int = Field(ge=0, le=10000)
    options: list["FontOptionWrite"] = Field(default_factory=list)


class FontOptionWrite(ApiModel):
    """One editable font option nested beneath a group."""

    id: int | None = None
    name: str = Field(min_length=1, max_length=500)
    font_url: str | None = Field(default=None, max_length=2048)
    minimum_difficulty: int = Field(ge=1, le=3)
    sort_order: int = Field(ge=0, le=10000)

    @field_validator("font_url", mode="after")
    @classmethod
    def validate_font_url(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        value = value.strip()
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("字体地址必须是 HTTPS URL")
        return value


class OptionCatalogUpdate(ApiModel):
    """The complete catalogue, saved as one independent settings domain."""

    groups: list[OptionGroupWrite] = Field(min_length=1, max_length=50)


class FontOptionResponse(ApiModel):
    id: int
    name: str
    font_url: str | None = None
    minimum_difficulty: int
    sort_order: int


class OptionGroupResponse(ApiModel):
    id: int
    name: str
    sort_order: int
    options: list[FontOptionResponse]


class QuestionWrite(ApiModel):
    """The complete editable representation of a catalogue-backed question."""

    text: str = Field(min_length=1, max_length=500)
    image_url: str = Field(min_length=1, max_length=2048)
    difficulty: int = Field(ge=1, le=3)
    correct_option_id: int = Field(gt=0)
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
    def validate_image_url(cls, value: str) -> str:
        """Require HTTPS, with loopback HTTP reserved for local image storage."""
        value = value.strip()
        if not value:
            raise ValueError("请上传题图")
        parsed = urlparse(value)
        local_http = parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if (parsed.scheme != "https" and not local_http) or not parsed.netloc:
            raise ValueError("图片地址必须是 HTTPS URL")
        return value


class QuestionCreate(QuestionWrite):
    client_request_id: str | None = Field(default=None, min_length=1, max_length=64,
                                         pattern=r"^[a-zA-Z0-9_-]+$")


class QuestionPatch(ApiModel):
    """A partial question update, validated as a whole after merging server data."""

    text: str | None = Field(default=None, min_length=1, max_length=500)
    image_url: str | None = Field(default=None, max_length=2048)
    difficulty: int | None = Field(default=None, ge=1, le=3)
    correct_option_id: int | None = Field(default=None, gt=0)
    explanation: str | None = Field(default=None, min_length=1, max_length=1000)


class QuestionResponse(ApiModel):
    """A full question returned only to authenticated administrators."""

    id: int
    text: str
    image_url: str | None
    difficulty: int
    correct_option_id: int | None
    correct_option: FontOptionResponse | None
    correct_group: OptionGroupResponse | None
    configuration_error: str | None = None
    answer: str | None = None
    explanation: str
    created_at: datetime
    updated_at: datetime


class QuestionExportItem(ApiModel):
    """One question in a portable JSON dump."""

    text: str
    image_url: str | None
    difficulty: int
    correct_option_id: int | None
    explanation: str


class QuestionImportItem(ApiModel):
    """One question accepted during bulk import.  id is ignored."""

    model_config = ConfigDict(extra="ignore")

    id: int | None = None
    text: str = Field(min_length=1, max_length=500)
    image_url: str | None = None
    difficulty: int = Field(ge=1, le=3)
    correct_option_id: int | None = None
    explanation: str = Field(min_length=1, max_length=1000)


class QuestionImportPayload(ApiModel):
    """The top-level file structure read by the import endpoint."""

    version: int
    exported_at: str | None = None
    questions: list[QuestionImportItem]


class QuestionImportResult(ApiModel):
    """Import summary returned after a successful bulk-create pass."""

    total: int
    created: int
    failed: int
    errors: list[str] = Field(default_factory=list)


class ImageUploadResponse(ApiModel):
    """The public image URL produced by the server-side R2 upload."""

    image_url: str


class FontReferenceWrite(ApiModel):
    """One administrator-maintained public font comparison card."""

    id: int | None = None
    title: str = Field(min_length=1, max_length=100)
    image_url: str = Field(min_length=1, max_length=2048)
    note: str = Field(default="", max_length=500)
    difficulty: int = Field(default=1, ge=1, le=3)
    sort_order: int = Field(ge=0, le=10000)

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
    """A public-safe font comparison card record."""

    id: int
    title: str
    image_url: str
    note: str
    difficulty: int
    sort_order: int
    created_at: datetime


class FontReferenceSectionWrite(ApiModel):
    """One editable section and its cards."""

    id: int | None = None
    name: str = Field(min_length=1, max_length=100)
    sort_order: int = Field(ge=0, le=10000)
    cards: list[FontReferenceWrite] = Field(default_factory=list)


class FontReferenceSectionResponse(ApiModel):
    id: int
    name: str
    sort_order: int
    cards: list[FontReferenceResponse]


class FontReferenceCatalogUpdate(ApiModel):
    """The complete font reference catalogue, saved as one atomic operation."""

    sections: list[FontReferenceSectionWrite] = Field(min_length=0, max_length=50)


class ConfigFontOption(ApiModel):
    """Portable font option identified independently from its local database ID."""

    config_key: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=500)
    font_url: str | None = Field(default=None, max_length=2048)
    minimum_difficulty: int = Field(ge=1, le=3)
    sort_order: int = Field(ge=0, le=10000)

    @field_validator("config_key", "name", mode="after")
    @classmethod
    def strip_required_values(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("配置项不能为空")
        return value

    @field_validator("font_url", mode="after")
    @classmethod
    def validate_font_url(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        value = value.strip()
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("字体地址必须是 HTTPS URL")
        return value


class ConfigOptionGroup(ApiModel):
    """Portable option group with stable keys for all nested options."""

    config_key: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=100)
    sort_order: int = Field(ge=0, le=10000)
    options: list[ConfigFontOption] = Field(default_factory=list, max_length=500)

    @field_validator("config_key", "name", mode="after")
    @classmethod
    def strip_group_values(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("配置分区不能为空")
        return value


class ConfigOptionCatalog(ApiModel):
    """The complete portable font option catalogue."""

    groups: list[ConfigOptionGroup] = Field(min_length=1, max_length=50)


class ConfigQuestion(ApiModel):
    """Portable question with a stable answer-option reference."""

    config_key: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=500)
    image_url: str | None = Field(default=None, max_length=2048)
    difficulty: int = Field(ge=1, le=3)
    correct_option_key: str | None = Field(default=None, max_length=64)
    explanation: str = Field(min_length=1, max_length=1000)

    @field_validator("config_key", "text", "explanation", mode="after")
    @classmethod
    def strip_question_values(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("题目配置内容不能为空")
        return value

    @field_validator("image_url", mode="after")
    @classmethod
    def validate_optional_image_url(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        value = value.strip()
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("图片地址必须是 HTTPS URL")
        return value

    @field_validator("correct_option_key", mode="after")
    @classmethod
    def strip_option_key(cls, value: str | None) -> str | None:
        return value.strip() if value is not None and value.strip() else None


class ConfigReferenceCard(ApiModel):
    """Portable font-reference card, including cards without a section."""

    config_key: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=100)
    image_url: str = Field(min_length=1, max_length=2048)
    note: str = Field(default="", max_length=500)
    difficulty: int = Field(default=1, ge=1, le=3)
    sort_order: int = Field(ge=0, le=10000)

    @field_validator("config_key", "title", mode="after")
    @classmethod
    def strip_card_values(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("笔记配置内容不能为空")
        return value

    @field_validator("note", mode="after")
    @classmethod
    def strip_card_note(cls, value: str) -> str:
        return value.strip()

    @field_validator("image_url", mode="after")
    @classmethod
    def validate_card_image_url(cls, value: str) -> str:
        value = value.strip()
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("图片地址必须是 HTTPS URL")
        return value


class ConfigReferenceSection(ApiModel):
    """Portable font-reference section."""

    config_key: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=100)
    sort_order: int = Field(ge=0, le=10000)
    cards: list[ConfigReferenceCard] = Field(default_factory=list, max_length=5000)

    @field_validator("config_key", "name", mode="after")
    @classmethod
    def strip_section_values(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("笔记分区不能为空")
        return value


class ConfigReferences(ApiModel):
    """Portable notes, including explicitly unassigned cards."""

    sections: list[ConfigReferenceSection] = Field(default_factory=list, max_length=50)
    unassigned_cards: list[ConfigReferenceCard] = Field(default_factory=list, max_length=5000)


class SettingsResponse(ApiModel):
    """Question count, weighted modes and editable font shortcut strings."""

    question_count: int = Field(ge=1, le=50)
    modes: dict[Mode, list[int]]
    font_presets: list[str]

    @model_validator(mode="after")
    def validate_modes(self) -> "SettingsResponse":
        """Ensure all modes have three non-negative weights and a selectable star."""
        expected = {"beginner", "proficient", "challenge"}
        if set(self.modes) != expected:
            raise ValueError("必须提供三种难度的权重")
        for weights in self.modes.values():
            if len(weights) != 3 or any(weight < 0 for weight in weights):
                raise ValueError("每种难度需要三个非负权重")
            if not any(weight > 0 for weight in weights):
                raise ValueError("每种难度至少一个权重大于零")
        if len(self.font_presets) > 100 or any(
            not item.strip() or len(item.strip()) > 50 for item in self.font_presets
        ):
            raise ValueError("字体快捷项格式不正确")
        self.font_presets = [item.strip() for item in self.font_presets]
        return self


class ConfigManifest(ApiModel):
    """The single versioned JSON document used for full admin configuration transfer."""

    format: Literal["mikanquiz-admin-config"]
    version: Literal[1]
    exported_at: str | None = None
    option_catalog: ConfigOptionCatalog
    questions: list[ConfigQuestion] = Field(max_length=10000)
    settings: SettingsResponse
    font_references: ConfigReferences


class ConfigImportRequest(ApiModel):
    """Preview or commit request for a complete configuration replacement."""

    manifest: ConfigManifest
    mode: Literal["replace"] = "replace"
    expected_current_hash: str | None = Field(default=None, min_length=64, max_length=64)
    expected_incoming_hash: str | None = Field(default=None, min_length=64, max_length=64)
    confirm: bool = False


class ConfigImportPreview(ApiModel):
    """Read-only diff and hash result shown before destructive replacement."""

    current_hash: str
    incoming_hash: str
    mode: Literal["replace"]
    diff: dict[str, int]
    warnings: list[str] = Field(default_factory=list)
    can_import: bool


class ConfigImportResult(ApiModel):
    """Result returned after the replacement transaction and outbox enqueue."""

    current_hash: str
    imported_hash: str
    mode: Literal["replace"]
    diff: dict[str, int]
    warnings: list[str] = Field(default_factory=list)


class PublicQuestion(ApiModel):
    """A question without answer or explanation, safe for anonymous clients."""

    id: int
    text: str
    image_url: str | None
    difficulty: int
    option_groups: list[OptionGroupResponse]


class QuestionPage(ApiModel):
    """A bounded page of admin questions."""

    items: list[QuestionResponse]
    page: int
    page_size: int
    total: int


class QuestionNavigation(ApiModel):
    """The adjacent questions within one filtered, sorted admin result set."""

    previous_id: int | None = None
    next_id: int | None = None
    position: int = Field(ge=1)
    total: int = Field(ge=1)


class DifficultyStat(ApiModel):
    difficulty: int
    count: int


class FontStat(ApiModel):
    option_id: int
    option_name: str
    count: int


class QuestionStats(ApiModel):
    total: int
    by_difficulty: list[DifficultyStat]
    by_font: list[FontStat]


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
    answers: dict[int, int]

    @field_validator("display_name", mode="after")
    @classmethod
    def strip_display_name(cls, value: str) -> str:
        """Keep anonymous names short and plain without storing identifiers."""
        return value.strip()


class SubmissionDetail(ApiModel):
    """One immutable answer record revealed only after scoring."""

    question_id: int | None
    question_text: str
    difficulty: int
    image_url: str | None
    options: list[str]
    option_groups: list[OptionGroupResponse] | None = None
    selected: str | None
    correct_answer: str
    selected_option_id: int | None = None
    correct_option_id: int | None = None
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
