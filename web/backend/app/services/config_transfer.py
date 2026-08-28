"""Portable full-configuration manifests and transactional replacement logic."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Iterable
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import AppSettings
from app.errors import ApiError
from app.models import (
    FontOption,
    FontReference,
    FontReferenceSection,
    OptionGroup,
    Question,
    QuizAttempt,
    QuizSettings,
    as_utc,
)
from app.schemas import ConfigImportPreview, ConfigImportResult, ConfigManifest


FORMAT = "mikanquiz-admin-config"
VERSION = 1
SYSTEM_GROUP_KEYS = {
    "system.option-group.black",
    "system.option-group.song",
    "system.option-group.round",
}


def export_manifest(session: Session) -> ConfigManifest:
    """Project all editable configuration domains into one portable manifest."""
    groups = session.scalars(
        select(OptionGroup).order_by(OptionGroup.sort_order, OptionGroup.config_key)
    ).all()
    options = session.scalars(
        select(FontOption).order_by(FontOption.sort_order, FontOption.config_key)
    ).all()
    options_by_group: dict[int, list[FontOption]] = {group.id: [] for group in groups}
    for option in options:
        options_by_group.setdefault(option.group_id, []).append(option)

    option_catalog = {
        "groups": [
            {
                "config_key": group.config_key,
                "name": group.name,
                "sort_order": group.sort_order,
                "options": [
                    {
                        "config_key": option.config_key,
                        "name": option.name,
                        "font_url": option.font_url,
                        "minimum_difficulty": option.minimum_difficulty,
                        "sort_order": option.sort_order,
                    }
                    for option in sorted(
                        options_by_group.get(group.id, []),
                        key=lambda item: (item.sort_order, item.config_key),
                    )
                ],
            }
            for group in groups
        ]
    }

    option_keys = {option.id: option.config_key for option in options}
    questions = session.scalars(select(Question).order_by(Question.config_key)).all()
    question_data = [
        {
            "config_key": question.config_key,
            "text": question.text,
            "image_url": question.image_url,
            "difficulty": question.difficulty,
            "correct_option_key": option_keys.get(question.correct_option_id),
            "explanation": question.explanation,
        }
        for question in questions
    ]

    settings = session.get(QuizSettings, 1)
    if settings is None:
        raise ApiError(503, "SETTINGS_UNAVAILABLE", "题目设置尚未初始化")
    settings_data = {
        "question_count": settings.question_count,
        "modes": settings.modes,
        "font_presets": settings.font_presets,
    }

    sections = session.scalars(
        select(FontReferenceSection).order_by(
            FontReferenceSection.sort_order, FontReferenceSection.config_key
        )
    ).all()
    cards = session.scalars(
        select(FontReference).order_by(FontReference.sort_order, FontReference.config_key)
    ).all()
    cards_by_section: dict[int, list[FontReference]] = {section.id: [] for section in sections}
    unassigned: list[FontReference] = []
    for card in cards:
        if card.section_id is None:
            unassigned.append(card)
        else:
            cards_by_section.setdefault(card.section_id, []).append(card)

    def card_data(card: FontReference) -> dict[str, Any]:
        return {
            "config_key": card.config_key,
            "title": card.title,
            "image_url": card.image_url,
            "note": card.note,
            "difficulty": card.difficulty,
            "sort_order": card.sort_order,
        }

    references = {
        "sections": [
            {
                "config_key": section.config_key,
                "name": section.name,
                "sort_order": section.sort_order,
                "cards": [
                    card_data(card)
                    for card in sorted(
                        cards_by_section.get(section.id, []),
                        key=lambda item: (item.sort_order, item.config_key),
                    )
                ],
            }
            for section in sections
        ],
        "unassigned_cards": [
            card_data(card)
            for card in sorted(unassigned, key=lambda item: (item.sort_order, item.config_key))
        ],
    }
    return ConfigManifest.model_validate(
        {
            "format": FORMAT,
            "version": VERSION,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "option_catalog": option_catalog,
            "questions": question_data,
            "settings": settings_data,
            "font_references": references,
        }
    )


def canonical_projection(manifest: ConfigManifest | dict[str, Any]) -> dict[str, Any]:
    """Remove transport metadata before comparing or hashing a manifest."""
    data = (
        manifest.model_dump(mode="json")
        if isinstance(manifest, ConfigManifest)
        else ConfigManifest.model_validate(manifest).model_dump(mode="json")
    )
    data.pop("exported_at", None)
    return data


def manifest_hash(manifest: ConfigManifest | dict[str, Any]) -> str:
    """Hash the deterministic UTF-8 JSON projection used for stale-preview checks."""
    canonical = json.dumps(
        canonical_projection(manifest),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def preview(
    session: Session, settings: AppSettings, manifest: ConfigManifest
) -> ConfigImportPreview:
    """Validate without writing and return stable hashes plus a human-readable diff."""
    validate_manifest(settings, manifest)
    current = export_manifest(session)
    warnings = manifest_warnings(manifest)
    return ConfigImportPreview(
        current_hash=manifest_hash(current),
        incoming_hash=manifest_hash(manifest),
        mode="replace",
        diff=diff_manifests(current, manifest),
        warnings=warnings,
        can_import=True,
    )


def validate_manifest(settings: AppSettings, manifest: ConfigManifest) -> None:
    """Apply cross-record and source-origin checks not expressible in Pydantic."""
    details: list[dict[str, Any]] = []
    seen: dict[str, str] = {}

    def remember(key: str, path: str) -> None:
        previous = seen.get(key)
        if previous is not None:
            details.append({"path": path, "message": f"config_key 与 {previous} 重复"})
        else:
            seen[key] = path

    option_keys: set[str] = set()
    for group_index, group in enumerate(manifest.option_catalog.groups):
        group_path = f"option_catalog.groups[{group_index}]"
        remember(group.config_key, f"{group_path}.config_key")
        for option_index, option in enumerate(group.options):
            option_path = f"{group_path}.options[{option_index}]"
            remember(option.config_key, f"{option_path}.config_key")
            option_keys.add(option.config_key)
            if option.font_url and not font_url_allowed(settings, option.font_url):
                details.append(
                    {
                        "path": f"{option_path}.font_url",
                        "message": "字体地址不在当前 R2 公共地址或允许来源中",
                        "code": "FONT_ORIGIN_NOT_ALLOWED",
                    }
                )
    for required in SYSTEM_GROUP_KEYS:
        if required not in {
            group.config_key for group in manifest.option_catalog.groups
        }:
            details.append(
                {
                    "path": "option_catalog.groups",
                    "message": f"缺少系统保留分区 {required}",
                    "code": "OPTION_GROUP_PROTECTED",
                }
            )

    for index, question in enumerate(manifest.questions):
        path = f"questions[{index}]"
        remember(question.config_key, f"{path}.config_key")
        if question.correct_option_key and question.correct_option_key not in option_keys:
            details.append(
                {
                    "path": f"{path}.correct_option_key",
                    "message": "正确字体 config_key 不存在",
                }
            )

    for section_index, section in enumerate(manifest.font_references.sections):
        section_path = f"font_references.sections[{section_index}]"
        remember(section.config_key, f"{section_path}.config_key")
        for card_index, card in enumerate(section.cards):
            card_path = f"{section_path}.cards[{card_index}]"
            remember(card.config_key, f"{card_path}.config_key")
    for card_index, card in enumerate(manifest.font_references.unassigned_cards):
        card_path = f"font_references.unassigned_cards[{card_index}]"
        remember(card.config_key, f"{card_path}.config_key")

    if details:
        code = next(
            (item.get("code") for item in details if item.get("code")),
            "CONFIG_INVALID",
        )
        raise ApiError(422, str(code), "配置文件校验失败", details)


def font_url_allowed(settings: AppSettings, url: str) -> bool:
    """Allow only the configured R2 path or explicitly configured HTTPS origins."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        return False
    base = settings.r2_public_base_url.strip().rstrip("/")
    if base:
        base_parsed = urlparse(base)
        base_path = base_parsed.path.rstrip("/")
        if (
            parsed.scheme == base_parsed.scheme
            and parsed.netloc == base_parsed.netloc
            and (parsed.path == base_path or parsed.path.startswith(f"{base_path}/"))
        ):
            return True
    origin = f"{parsed.scheme}://{parsed.netloc}"
    return origin in {item.rstrip("/") for item in settings.font_source_origins}


def manifest_warnings(manifest: ConfigManifest) -> list[str]:
    """Return non-blocking conditions that deserve explicit confirmation in the UI."""
    warnings: list[str] = []
    if manifest.font_references.unassigned_cards:
        warnings.append(f"有 {len(manifest.font_references.unassigned_cards)} 张嵌字笔记未归入分区")
    if any(question.correct_option_key is None for question in manifest.questions):
        warnings.append("存在尚未绑定正确字体的题目，导入后仍需在题库中修复")
    return warnings


def diff_manifests(current: ConfigManifest, incoming: ConfigManifest) -> dict[str, int]:
    """Count additions, removals and content changes by stable-key entity."""
    current_data = canonical_projection(current)
    incoming_data = canonical_projection(incoming)

    def index(items: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        return {item["config_key"]: item for item in items}

    current_groups = index(current_data["option_catalog"]["groups"])
    incoming_groups = index(incoming_data["option_catalog"]["groups"])
    current_options = index(
        option
        for group in current_data["option_catalog"]["groups"]
        for option in group["options"]
    )
    incoming_options = index(
        option
        for group in incoming_data["option_catalog"]["groups"]
        for option in group["options"]
    )
    current_questions = index(current_data["questions"])
    incoming_questions = index(incoming_data["questions"])
    current_sections = index(current_data["font_references"]["sections"])
    incoming_sections = index(incoming_data["font_references"]["sections"])
    current_cards = index(
        card
        for section in current_data["font_references"]["sections"]
        for card in section["cards"]
    ) | index(current_data["font_references"]["unassigned_cards"])
    incoming_cards = index(
        card
        for section in incoming_data["font_references"]["sections"]
        for card in section["cards"]
    ) | index(incoming_data["font_references"]["unassigned_cards"])

    def counts(prefix: str, old: dict[str, Any], new: dict[str, Any]) -> dict[str, int]:
        old_keys, new_keys = set(old), set(new)
        return {
            f"{prefix}_added": len(new_keys - old_keys),
            f"{prefix}_deleted": len(old_keys - new_keys),
            f"{prefix}_updated": sum(
                1 for key in old_keys & new_keys if old[key] != new[key]
            ),
        }

    result: dict[str, int] = {}
    for prefix, old, new in (
        ("option_groups", current_groups, incoming_groups),
        ("font_options", current_options, incoming_options),
        ("questions", current_questions, incoming_questions),
        ("reference_sections", current_sections, incoming_sections),
        ("reference_cards", current_cards, incoming_cards),
    ):
        result.update(counts(prefix, old, new))
    result["settings_changed"] = int(current_data["settings"] != incoming_data["settings"])
    return result


def replace_database(
    session: Session,
    settings: AppSettings,
    manifest: ConfigManifest,
    current: ConfigManifest,
) -> ConfigImportResult:
    """Replace config entities in one already-exclusive transaction."""
    validate_manifest(settings, manifest)
    deleted_question_ids = _deleted_question_ids(session, manifest)
    if deleted_question_ids:
        _raise_active_attempt_conflict(session, deleted_question_ids)

    old_questions = session.scalars(select(Question)).all()
    old_sections = session.scalars(select(FontReferenceSection)).all()
    old_question_ids = {question.id for question in old_questions}
    old_question_keys = {question.config_key for question in old_questions}
    old_section_ids = {section.id for section in old_sections}
    old_section_keys = {section.config_key for section in old_sections}
    diff = diff_manifests(current, manifest)
    _replace_options(session, manifest)
    _replace_questions(session, manifest)
    _replace_settings(session, manifest)
    _replace_references(session, manifest)
    session.flush()

    from app.services import sync as sync_service

    sync_service.enqueue_scope(
        session,
        "questions",
        removed_local_ids=old_question_ids - {item.id for item in session.scalars(select(Question)).all()},
        removed_config_keys=old_question_keys
        - {item.config_key for item in session.scalars(select(Question)).all()},
    )
    sync_service.enqueue_scope(
        session,
        "notes",
        removed_local_ids=old_section_ids
        - {item.id for item in session.scalars(select(FontReferenceSection)).all()},
        removed_config_keys=old_section_keys
        - {item.config_key for item in session.scalars(select(FontReferenceSection)).all()},
    )
    imported_hash = manifest_hash(manifest)
    return ConfigImportResult(
        current_hash=imported_hash,
        imported_hash=imported_hash,
        mode="replace",
        diff=diff,
        warnings=manifest_warnings(manifest),
    )


def _replace_options(session: Session, manifest: ConfigManifest) -> None:
    groups = {item.config_key: item for item in session.scalars(select(OptionGroup)).all()}
    options = {item.config_key: item for item in session.scalars(select(FontOption)).all()}
    incoming_groups = {item.config_key: item for item in manifest.option_catalog.groups}
    incoming_options = {
        option.config_key: (group, option)
        for group in manifest.option_catalog.groups
        for option in group.options
    }
    for key, data in incoming_groups.items():
        group = groups.get(key)
        if group is None:
            group = OptionGroup(config_key=key, name=data.name, sort_order=data.sort_order)
            session.add(group)
            session.flush()
        else:
            group.name, group.sort_order = data.name, data.sort_order
    for key, (group_data, data) in incoming_options.items():
        group = groups.get(group_data.config_key)
        if group is None:
            group = session.scalar(select(OptionGroup).where(OptionGroup.config_key == group_data.config_key))
        if group is None:
            raise ApiError(422, "CONFIG_INVALID", "字体分区不存在")
        option = options.get(key)
        if option is None:
            option = FontOption(config_key=key)
            session.add(option)
        option.group_id = group.id
        option.name = data.name
        option.pinyin = option.pinyin or ""
        from app.models import to_pinyin

        option.pinyin = to_pinyin(data.name)
        option.font_url = data.font_url
        option.minimum_difficulty = data.minimum_difficulty
        option.sort_order = data.sort_order
    session.flush()
    missing_options = set(options) - set(incoming_options)
    if missing_options:
        missing_ids = [options[key].id for key in missing_options]
        session.query(Question).filter(Question.correct_option_id.in_(missing_ids)).update(
            {Question.correct_option_id: None}, synchronize_session=False
        )
        for key in missing_options:
            session.delete(options[key])
    for key in set(groups) - set(incoming_groups):
        session.delete(groups[key])
    session.flush()


def _replace_questions(session: Session, manifest: ConfigManifest) -> None:
    questions = {item.config_key: item for item in session.scalars(select(Question)).all()}
    options = {item.config_key: item.id for item in session.scalars(select(FontOption)).all()}
    incoming_keys = {item.config_key for item in manifest.questions}
    for data in manifest.questions:
        question = questions.get(data.config_key)
        if question is None:
            question = Question(config_key=data.config_key)
            session.add(question)
        question.text = data.text
        question.image_url = data.image_url
        question.difficulty = data.difficulty
        question.correct_option_id = options.get(data.correct_option_key) if data.correct_option_key else None
        question.explanation = data.explanation
    for key in set(questions) - incoming_keys:
        session.delete(questions[key])
    session.flush()


def _replace_settings(session: Session, manifest: ConfigManifest) -> None:
    settings = session.get(QuizSettings, 1)
    if settings is None:
        settings = QuizSettings(id=1)
        session.add(settings)
    settings.question_count = manifest.settings.question_count
    settings.modes = manifest.settings.modes
    settings.font_presets = manifest.settings.font_presets


def _replace_references(session: Session, manifest: ConfigManifest) -> None:
    sections = {item.config_key: item for item in session.scalars(select(FontReferenceSection)).all()}
    cards = {item.config_key: item for item in session.scalars(select(FontReference)).all()}
    incoming_sections = {item.config_key: item for item in manifest.font_references.sections}
    incoming_cards: dict[str, tuple[int | None, Any]] = {}
    for section in manifest.font_references.sections:
        for card in section.cards:
            incoming_cards[card.config_key] = (None, card)
    for card in manifest.font_references.unassigned_cards:
        incoming_cards[card.config_key] = (None, card)

    section_ids: dict[str, int] = {}
    for key, data in incoming_sections.items():
        section = sections.get(key)
        if section is None:
            section = FontReferenceSection(config_key=key)
            session.add(section)
            session.flush()
        section.name, section.sort_order = data.name, data.sort_order
        section_ids[key] = section.id
    for section in manifest.font_references.sections:
        for card_data in section.cards:
            _upsert_card(session, cards, card_data, section_ids[section.config_key])
    for card_data in manifest.font_references.unassigned_cards:
        _upsert_card(session, cards, card_data, None)
    for key in set(cards) - set(incoming_cards):
        session.delete(cards[key])
    for key in set(sections) - set(incoming_sections):
        session.delete(sections[key])
    session.flush()


def _upsert_card(
    session: Session,
    cards: dict[str, FontReference],
    data: Any,
    section_id: int | None,
) -> None:
    card = cards.get(data.config_key)
    if card is None:
        card = FontReference(config_key=data.config_key)
        session.add(card)
    card.title = data.title
    card.image_url = data.image_url
    card.note = data.note
    card.difficulty = data.difficulty
    card.section_id = section_id
    card.sort_order = data.sort_order


def _deleted_question_ids(session: Session, manifest: ConfigManifest) -> set[int]:
    incoming = {question.config_key for question in manifest.questions}
    return {
        question.id
        for question in session.scalars(select(Question)).all()
        if question.config_key not in incoming
    }


def _raise_active_attempt_conflict(session: Session, question_ids: set[int]) -> None:
    now = datetime.now(timezone.utc)
    details: list[dict[str, Any]] = []
    attempts = session.scalars(
        select(QuizAttempt).where(
            QuizAttempt.submitted_at.is_(None), QuizAttempt.expires_at > now
        )
    ).all()
    for attempt in attempts:
        referenced = sorted(set(attempt.question_ids or []) & question_ids)
        if referenced:
            details.append(
                {
                    "attempt_id": attempt.id,
                    "question_ids": referenced,
                    "expires_at": as_utc(attempt.expires_at).isoformat(),
                }
            )
    if details:
        raise ApiError(409, "ACTIVE_ATTEMPT_CONFLICT", "有未完成答题会话引用将被删除的题目", details)
