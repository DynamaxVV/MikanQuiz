"""Incremental JSON sync of questions and notes to R2.

Each mutation uploads:
  - the individual entity file (by ID)
  - a full snapshot of the entire dataset

All operations are fire-and-forget: failures are logged as warnings and never
propagate to the caller so that normal API responses are unaffected.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import AppSettings
from app.logging import log_event
from app.models import FontOption, FontReference, FontReferenceSection, OptionGroup, Question, as_utc


def sync_question(session: Session, settings: AppSettings, question_id: int) -> None:
    """Sync one question to R2, then refresh the full snapshot."""
    try:
        q = session.get(Question, question_id)
        if q is None:
            return
        data = _serialize_question(session, q)
        _upload_json(settings, f"sync/questions/{question_id}.json", data)
        sync_question_snapshot(session, settings)
    except Exception as exc:
        log_event("sync_failed", logging.WARNING, entity="question", entity_id=question_id, error=str(exc))


def sync_question_snapshot(session: Session, settings: AppSettings) -> None:
    """Upload the full questions snapshot to R2."""
    try:
        items = session.scalars(select(Question).order_by(Question.id)).all()
        snapshot = {
            "version": 1,
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "questions": [_serialize_question(session, q) for q in items],
        }
        _upload_json(settings, "sync/questions/all.json", snapshot)
    except Exception as exc:
        log_event("sync_failed", logging.WARNING, entity="question_snapshot", error=str(exc))


def delete_question_sync(settings: AppSettings, question_id: int) -> None:
    """Delete one question file from R2, then refresh the snapshot."""
    try:
        _delete_json(settings, f"sync/questions/{question_id}.json")
    except Exception as exc:
        log_event("sync_failed", logging.WARNING, entity="question_delete", entity_id=question_id, error=str(exc))


def sync_notes(session: Session, settings: AppSettings) -> None:
    """Sync all note sections to R2 (per-section + full snapshot)."""
    try:
        sections = session.scalars(
            select(FontReferenceSection).order_by(FontReferenceSection.sort_order, FontReferenceSection.id)
        ).all()
        all_sections = []
        for section in sections:
            cards = session.scalars(
                select(FontReference)
                .where(FontReference.section_id == section.id)
                .order_by(FontReference.sort_order, FontReference.id)
            ).all()
            section_data = {
                "id": section.id,
                "name": section.name,
                "sort_order": section.sort_order,
                "cards": [
                    {
                        "id": c.id,
                        "title": c.title,
                        "image_url": c.image_url,
                        "note": c.note,
                        "difficulty": c.difficulty,
                        "sort_order": c.sort_order,
                        "created_at": as_utc(c.created_at).isoformat(),
                    }
                    for c in cards
                ],
            }
            _upload_json(settings, f"sync/notes/{section.id}.json", section_data)
            all_sections.append(section_data)
        snapshot = {
            "version": 1,
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "sections": all_sections,
        }
        _upload_json(settings, "sync/notes/all.json", snapshot)
    except Exception as exc:
        log_event("sync_failed", logging.WARNING, entity="notes", error=str(exc))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _serialize_question(session: Session, q: Question) -> dict:
    option = session.get(FontOption, q.correct_option_id) if q.correct_option_id else None
    group = session.get(OptionGroup, option.group_id) if option else None
    return {
        "id": q.id,
        "text": q.text,
        "image_url": q.image_url,
        "difficulty": q.difficulty,
        "correct_option_id": q.correct_option_id,
        "answer": option.name if option else None,
        "group_name": group.name if group else None,
        "explanation": q.explanation,
        "created_at": as_utc(q.created_at).isoformat(),
        "updated_at": as_utc(q.updated_at).isoformat(),
    }


def _upload_json(settings: AppSettings, key: str, data: dict | list) -> None:
    from app.services.images import upload_json

    upload_json(settings, key, data)


def _delete_json(settings: AppSettings, key: str) -> None:
    from app.services.images import delete_r2_object

    base = settings.r2_public_base_url.rstrip("/")
    url = f"{base}/{key}"
    delete_r2_object(settings, url)
