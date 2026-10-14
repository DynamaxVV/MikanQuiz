"""Durable publication of question and notes projections to R2 JSON files."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
from time import monotonic
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.config import AppSettings
from app.database import Database
from app.logging import log_event
from app.models import (
    FontOption,
    FontReference,
    FontReferenceSection,
    OptionGroup,
    Question,
    SyncOutbox,
    SyncScopeState,
    as_utc,
    utc_now,
)


LEASE_SECONDS = 60
HEARTBEAT_SECONDS = 15
MAX_ATTEMPTS = 10
RETRY_DELAYS = (1, 5, 30, 300)
SCOPES = {"questions", "notes"}


class SyncOwnershipLost(RuntimeError):
    """Raised when a worker no longer owns a claimed scope fence."""


def enqueue_scope(
    session: Session,
    scope: str,
    removed_local_ids: set[int] | None = None,
    removed_config_keys: set[str] | None = None,
    force: bool = False,
) -> SyncOutbox | None:
    """Record a deduplicated publication task after a config-domain mutation."""
    if scope not in SCOPES:
        raise ValueError(f"unknown sync scope: {scope}")
    state_hash = scope_state_hash(session, scope)
    state = session.get(SyncScopeState, scope)
    if state is None:
        state = SyncScopeState(scope=scope, fence=0)
        session.add(state)
        session.flush()
    state.current_state_hash = state_hash
    now = utc_now()
    unfinished = session.scalars(
        select(SyncOutbox).where(
            SyncOutbox.scope == scope,
            SyncOutbox.status.in_(["pending", "running", "failed"]),
        )
    ).all()
    tombstone_ids = set(removed_local_ids or ())
    tombstone_keys = set(removed_config_keys or ())
    for item in unfinished:
        payload = item.payload_json or {}
        tombstone_ids.update(payload.get("removed_local_ids", []))
        tombstone_keys.update(payload.get("removed_config_keys", []))

    payload = _task_payload(scope, tombstone_ids, tombstone_keys)
    existing = session.scalar(
        select(SyncOutbox).where(
            SyncOutbox.scope == scope, SyncOutbox.state_hash == state_hash
        )
    )
    if existing is not None:
        if force or existing.status in {"superseded", "failed"}:
            existing.status = "pending"
            existing.available_at = now
            existing.lease_until = None
            existing.lock_token = None
            existing.last_error = None
        if existing.status == "pending" or force:
            existing.payload_json = payload
        return existing

    for item in unfinished:
        if item.status == "pending":
            item.status = "superseded"
            item.updated_at = now
    task = SyncOutbox(
        scope=scope,
        state_hash=state_hash,
        payload_json=payload,
        status="pending",
        attempts=0,
        available_at=now,
        scope_fence=0,
    )
    session.add(task)
    session.flush()
    return task


def scope_state_hash(session: Session, scope: str) -> str:
    """Hash the current derived projection without transport timestamps."""
    projection = _scope_projection(session, scope)
    encoded = json.dumps(
        projection, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def run_once(
    database: Database, settings: AppSettings, outbox_id: int | None = None
) -> bool:
    """Claim and publish at most one task; return whether work was completed."""
    claim = _claim(database, outbox_id)
    if claim is None:
        return False
    task_id, scope, state_hash, token, fence, payload = claim
    try:
        _publish(database, settings, task_id, scope, state_hash, token, fence, payload)
    except SyncOwnershipLost as error:
        _requeue_after_ownership_loss(
            database, task_id, scope, token, fence, str(error)
        )
        log_event(
            "sync_ownership_lost", logging.ERROR, scope=scope, outbox_id=task_id
        )
    except Exception as error:
        _mark_failed(database, task_id, token, fence, str(error))
        log_event(
            "sync_failed", logging.WARNING, scope=scope, outbox_id=task_id, error=str(error)
        )
    return True


def _claim(database: Database, outbox_id: int | None) -> tuple | None:
    """Claim under a short SQLite write lock and release it before network I/O."""
    connection = database.engine.connect()
    session: Session | None = None
    try:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        session = Session(bind=connection, expire_on_commit=False)
        now = utc_now()
        _requeue_expired(session, now)
        statement = select(SyncOutbox).order_by(SyncOutbox.available_at, SyncOutbox.id)
        if outbox_id is not None:
            statement = statement.where(SyncOutbox.id == outbox_id)
        else:
            statement = statement.where(
                SyncOutbox.status == "pending", SyncOutbox.available_at <= now
            )
        candidates = session.scalars(statement).all()
        for task in candidates:
            if outbox_id is not None and task.status not in {"pending", "failed"}:
                continue
            running = session.scalar(
                select(SyncOutbox).where(
                    SyncOutbox.scope == task.scope,
                    SyncOutbox.status == "running",
                    SyncOutbox.lease_until > now,
                    SyncOutbox.id != task.id,
                )
            )
            if running is not None:
                continue
            state = session.get(SyncScopeState, task.scope)
            if state is None:
                state = SyncScopeState(scope=task.scope, fence=0)
                session.add(state)
            state.fence = (state.fence or 0) + 1
            task.scope_fence = state.fence
            task.status = "running"
            task.attempts += 1
            task.lease_until = now + timedelta(seconds=LEASE_SECONDS)
            task.lock_token = str(uuid4())
            task.updated_at = now
            session.commit()
            connection.commit()
            return (
                task.id,
                task.scope,
                task.state_hash,
                task.lock_token,
                task.scope_fence,
                task.payload_json,
            )
        session.rollback()
        return None
    except OperationalError:
        if session is not None:
            session.rollback()
        return None
    finally:
        if session is not None:
            session.close()
        connection.close()


def _requeue_expired(session: Session, now: datetime) -> None:
    """Make abandoned leases eligible without allowing two live owners."""
    session.execute(
        update(SyncOutbox)
        .where(SyncOutbox.status == "running", SyncOutbox.lease_until <= now)
        .values(
            status="pending",
            available_at=now,
            lease_until=None,
            lock_token=None,
            last_error="worker lease expired",
            updated_at=now,
        )
    )


def _publish(
    database: Database,
    settings: AppSettings,
    task_id: int,
    scope: str,
    state_hash: str,
    token: str,
    fence: int,
    payload: dict,
) -> None:
    """Publish all entity files and the full snapshot outside the database lock."""
    started = monotonic()
    last_heartbeat = 0.0
    with database.sessions() as session:
        if scope == "questions":
            rows = session.scalars(select(Question).order_by(Question.id)).all()
            files = [
                (f"sync/questions/{question.id}.json", _serialize_question(session, question))
                for question in rows
            ]
            snapshot = {
                "version": 1,
                "synced_at": datetime.now(timezone.utc).isoformat(),
                "questions": [data for _, data in files],
            }
            prefix = "sync/questions/"
            all_key = "sync/questions/all.json"
        else:
            sections, unassigned = _notes_projection(session)
            files = [
                (f"sync/notes/{section['id']}.json", section) for section in sections
            ]
            snapshot = {
                "version": 1,
                "synced_at": datetime.now(timezone.utc).isoformat(),
                "sections": sections,
                "unassigned_cards": unassigned,
            }
            prefix = "sync/notes/"
            all_key = "sync/notes/all.json"
        current_ids = {key.rsplit("/", 1)[-1].removesuffix(".json") for key, _ in files}
        for local_id in payload.get("removed_local_ids", []):
            if str(int(local_id)) not in current_ids:
                last_heartbeat = _heartbeat_if_due(
                    database, task_id, token, fence, last_heartbeat
                )
                _delete_json_strict(settings, f"{prefix}{int(local_id)}.json")
        for key, data in files:
            last_heartbeat = _heartbeat_if_due(
                database, task_id, token, fence, last_heartbeat
            )
            _upload_json_strict(settings, key, data)
        _heartbeat_if_due(database, task_id, token, fence, last_heartbeat)
        _upload_json_strict(settings, all_key, snapshot)
        _assert_owner(database, task_id, token, fence)
    _finish_success(database, task_id, scope, state_hash, token, fence)
    log_event(
        "sync_succeeded",
        scope=scope,
        outbox_id=task_id,
        duration_ms=round((monotonic() - started) * 1000, 2),
    )


def _heartbeat_if_due(
    database: Database, task_id: int, token: str, fence: int, last: float
) -> float:
    now = monotonic()
    if now - last >= HEARTBEAT_SECONDS:
        _renew_lease(database, task_id, token, fence)
        return now
    return last


def _renew_lease(database: Database, task_id: int, token: str, fence: int) -> None:
    now = utc_now()
    with database.engine.begin() as connection:
        result = connection.execute(
            update(SyncOutbox)
            .where(
                SyncOutbox.id == task_id,
                SyncOutbox.status == "running",
                SyncOutbox.lock_token == token,
                SyncOutbox.scope_fence == fence,
            )
            .values(lease_until=now + timedelta(seconds=LEASE_SECONDS), updated_at=now)
        )
        if result.rowcount != 1:
            raise SyncOwnershipLost("sync lease no longer belongs to this worker")


def _assert_owner(database: Database, task_id: int, token: str, fence: int) -> None:
    with database.sessions() as session:
        owner = session.scalar(
            select(SyncOutbox.id).where(
                SyncOutbox.id == task_id,
                SyncOutbox.status == "running",
                SyncOutbox.lock_token == token,
                SyncOutbox.scope_fence == fence,
            )
        )
        if owner is None:
            raise SyncOwnershipLost("sync ownership changed after external write")


def _finish_success(
    database: Database,
    task_id: int,
    scope: str,
    state_hash: str,
    token: str,
    fence: int,
) -> None:
    connection = database.engine.connect()
    session: Session | None = None
    try:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        session = Session(bind=connection, expire_on_commit=False)
        task = session.scalar(
            select(SyncOutbox).where(
                SyncOutbox.id == task_id,
                SyncOutbox.status == "running",
                SyncOutbox.lock_token == token,
                SyncOutbox.scope_fence == fence,
            )
        )
        if task is None:
            raise SyncOwnershipLost("sync task was changed before completion")
        state = session.get(SyncScopeState, scope)
        if state is None:
            raise SyncOwnershipLost("sync scope state disappeared")
        task.status = "succeeded"
        task.lease_until = None
        task.lock_token = None
        task.last_error = None
        task.updated_at = utc_now()
        if state.current_state_hash == state_hash:
            state.published_state_hash = state_hash
        else:
            enqueue_scope(session, scope)
        session.commit()
        connection.commit()
    finally:
        if session is not None:
            session.close()
        connection.close()


def _mark_failed(
    database: Database, task_id: int, token: str, fence: int, error: str
) -> None:
    now = utc_now()
    with database.engine.begin() as connection:
        task = connection.execute(
            select(SyncOutbox).where(SyncOutbox.id == task_id)
        ).mappings().first()
        if task is None:
            return
        attempts = int(task["attempts"] or 0)
        terminal = attempts >= MAX_ATTEMPTS
        delay = RETRY_DELAYS[min(max(attempts - 1, 0), len(RETRY_DELAYS) - 1)]
        connection.execute(
            update(SyncOutbox)
            .where(
                SyncOutbox.id == task_id,
                SyncOutbox.status == "running",
                SyncOutbox.lock_token == token,
                SyncOutbox.scope_fence == fence,
            )
            .values(
                status="failed" if terminal else "pending",
                available_at=now + timedelta(seconds=delay),
                lease_until=None,
                lock_token=None,
                last_error=error[:2000],
                updated_at=now,
            )
        )


def _requeue_after_ownership_loss(
    database: Database,
    task_id: int,
    scope: str,
    token: str,
    fence: int,
    error: str,
) -> None:
    """Requeue the current hash even if a late owner wrote or marked it succeeded."""
    connection = database.engine.connect()
    session: Session | None = None
    try:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        result = connection.execute(
            update(SyncOutbox)
            .where(
                SyncOutbox.id == task_id,
                SyncOutbox.status == "running",
                SyncOutbox.lock_token == token,
                SyncOutbox.scope_fence == fence,
            )
            .values(
                status="superseded",
                lease_until=None,
                lock_token=None,
                last_error=error[:2000],
                updated_at=utc_now(),
            )
        )
        session = Session(bind=connection, expire_on_commit=False)
        try:
            if result.rowcount == 1:
                enqueue_scope(session, scope)
            session.commit()
        finally:
            session.close()
        connection.commit()
    finally:
        if session is not None:
            session.close()
        connection.close()


def retry_outbox(database: Database, outbox_id: int) -> None:
    """Make one terminal task manually eligible for a bounded operator retry."""
    with database.engine.begin() as connection:
        connection.execute(
            update(SyncOutbox)
            .where(SyncOutbox.id == outbox_id, SyncOutbox.status == "failed")
            .values(status="pending", available_at=utc_now(), last_error=None)
        )


def _task_payload(scope: str, removed_local_ids: set[int], removed_config_keys: set[str]) -> dict:
    if scope == "questions":
        snapshot_key, prefix = "sync/questions/all.json", "sync/questions/"
    else:
        snapshot_key, prefix = "sync/notes/all.json", "sync/notes/"
    return {
        "version": 1,
        "scope": scope,
        "rebuild_all_entities": True,
        "snapshot_key": snapshot_key,
        "entity_prefix": prefix,
        "removed_local_ids": sorted(int(item) for item in removed_local_ids),
        "removed_config_keys": sorted(removed_config_keys),
    }


def _scope_projection(session: Session, scope: str) -> dict:
    if scope == "questions":
        rows = session.scalars(select(Question).order_by(Question.id)).all()
        return {"version": 1, "questions": [_serialize_question(session, item) for item in rows]}
    sections, unassigned = _notes_projection(session)
    return {"version": 1, "sections": sections, "unassigned_cards": unassigned}


def _notes_projection(session: Session) -> tuple[list[dict], list[dict]]:
    sections = session.scalars(
        select(FontReferenceSection).order_by(
            FontReferenceSection.sort_order, FontReferenceSection.id
        )
    ).all()
    cards = session.scalars(
        select(FontReference).order_by(FontReference.sort_order, FontReference.id)
    ).all()
    by_section: dict[int, list[FontReference]] = {section.id: [] for section in sections}
    unassigned: list[FontReference] = []
    for card in cards:
        if card.section_id is None:
            unassigned.append(card)
        else:
            by_section.setdefault(card.section_id, []).append(card)

    def card_data(card: FontReference) -> dict:
        return {
            "id": card.id,
            "config_key": card.config_key,
            "title": card.title,
            "image_url": card.image_url,
            "pdf_url": card.pdf_url,
            "pdf_name": card.pdf_name,
            "pdf_size_bytes": card.pdf_size_bytes,
            "note": card.note,
            "difficulty": card.difficulty,
            "sort_order": card.sort_order,
            "created_at": as_utc(card.created_at).isoformat(),
        }

    data = []
    for section in sections:
        section_cards = sorted(
            by_section.get(section.id, []), key=lambda item: (item.sort_order, item.id)
        )
        data.append(
            {
                "id": section.id,
                "config_key": section.config_key,
                "name": section.name,
                "sort_order": section.sort_order,
                "cards": [card_data(card) for card in section_cards],
            }
        )
    return data, [
        card_data(card)
        for card in sorted(unassigned, key=lambda item: (item.sort_order, item.id))
    ]


def _serialize_question(session: Session, question: Question) -> dict:
    option = (
        session.get(FontOption, question.correct_option_id)
        if question.correct_option_id
        else None
    )
    group = session.get(OptionGroup, option.group_id) if option else None
    return {
        "id": question.id,
        "config_key": question.config_key,
        "text": question.text,
        "image_url": question.image_url,
        "difficulty": question.difficulty,
        "correct_option_id": question.correct_option_id,
        "answer": option.name if option else None,
        "group_name": group.name if group else None,
        "explanation": question.explanation,
        "created_at": as_utc(question.created_at).isoformat(),
        "updated_at": as_utc(question.updated_at).isoformat(),
    }


def _upload_json_strict(settings: AppSettings, key: str, data: dict | list) -> None:
    from app.services.images import upload_json

    upload_json(settings, key, data)


def _delete_json_strict(settings: AppSettings, key: str) -> None:
    from app.services.images import delete_r2_object_strict

    delete_r2_object_strict(settings, _derived_url(settings, key))


def _derived_url(settings: AppSettings, key: str) -> str:
    base = (
        settings.local_public_base_url
        if settings.storage_backend == "local"
        else settings.r2_public_base_url
    ).rstrip("/")
    return f"{base}/{key}"
