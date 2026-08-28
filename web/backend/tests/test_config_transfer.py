"""Acceptance tests for the single-file configuration transfer contract."""

from fastapi.testclient import TestClient

from app.config import AppSettings
from app.main import create_app
from app.models import SyncOutbox, SyncScopeState
from app.services.admin import add_admin
from app.services import sync as sync_service
from tests.test_api import configure_two_question_quiz, create_attempt


def test_export_preview_import_round_trip_uses_stable_keys(client: TestClient) -> None:
    """Exported data contains no local IDs and can be imported after an edit."""
    headers, _ = configure_two_question_quiz(client)
    exported = client.get("/api/v1/admin/config/export", headers=headers)
    assert exported.status_code == 200
    manifest = exported.json()
    assert manifest["format"] == "mikanquiz-admin-config"
    assert manifest["version"] == 1
    assert all("config_key" in group for group in manifest["option_catalog"]["groups"])
    assert all("id" not in group for group in manifest["option_catalog"]["groups"])
    assert all("config_key" in question for question in manifest["questions"])
    assert "created_at" not in manifest["questions"][0]

    manifest["questions"][0]["text"] = "从完整配置导入的题目"
    preview = client.post(
        "/api/v1/admin/config/import/validate",
        headers=headers,
        json={"manifest": manifest, "mode": "replace"},
    )
    assert preview.status_code == 200, preview.text
    data = preview.json()
    assert data["incoming_hash"] != data["current_hash"]
    result = client.post(
        "/api/v1/admin/config/import",
        headers=headers,
        json={
            "manifest": manifest,
            "mode": "replace",
            "expected_current_hash": data["current_hash"],
            "expected_incoming_hash": data["incoming_hash"],
            "confirm": True,
        },
    )
    assert result.status_code == 200, result.text
    current = client.get("/api/v1/admin/questions", headers=headers).json()
    assert any(item["text"] == "从完整配置导入的题目" for item in current["items"])
    assert current["total"] == 2


def test_question_bank_export_and_import_appends_questions(client: TestClient) -> None:
    """The standalone question dump can be imported without replacing existing rows."""
    headers, questions = configure_two_question_quiz(client)
    exported = client.get("/api/v1/admin/questions/export", headers=headers)
    assert exported.status_code == 200, exported.text
    payload = exported.json()
    assert payload["version"] == 1
    assert len(payload["questions"]) == 2
    assert payload["questions"][0]["id"] == questions[0]["id"]
    assert payload["questions"][0]["created_at"]

    payload["questions"][0]["text"] = "从题库文件追加的题目"
    imported = client.post(
        "/api/v1/admin/questions/import",
        headers=headers,
        json=payload,
    )
    assert imported.status_code == 200, imported.text
    assert imported.json() == {"total": 2, "created": 2, "failed": 0, "errors": []}

    current = client.get("/api/v1/admin/questions", headers=headers).json()
    assert current["total"] == 4
    assert sum(item["text"] == "从题库文件追加的题目" for item in current["items"]) == 1


def test_import_rejects_stale_preview(client: TestClient) -> None:
    """A changed database cannot be overwritten by an old confirmation hash."""
    headers, _ = configure_two_question_quiz(client)
    manifest = client.get("/api/v1/admin/config/export", headers=headers).json()
    preview = client.post(
        "/api/v1/admin/config/import/validate",
        headers=headers,
        json={"manifest": manifest, "mode": "replace"},
    ).json()
    changed = client.put(
        "/api/v1/admin/settings/strategy",
        headers=headers,
        json={
            "question_count": 3,
            "modes": {
                "beginner": [100, 0, 0],
                "proficient": [100, 0, 0],
                "challenge": [100, 0, 0],
            },
        },
    )
    assert changed.status_code == 200
    response = client.post(
        "/api/v1/admin/config/import",
        headers=headers,
        json={
            "manifest": manifest,
            "mode": "replace",
            "expected_current_hash": preview["current_hash"],
            "expected_incoming_hash": preview["incoming_hash"],
            "confirm": True,
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFIG_PREVIEW_STALE"


def test_import_rejects_active_attempt_question_deletion(client: TestClient) -> None:
    """Replace is blocked while an unfinished attempt still references a removed question."""
    headers, _ = configure_two_question_quiz(client)
    attempt = create_attempt(client)
    # Resolve the portable key instead of assuming a database integer is portable.
    manifest = client.get("/api/v1/admin/config/export", headers=headers).json()
    exported_questions = manifest["questions"]
    removed_key = exported_questions[0]["config_key"]
    manifest["questions"] = [item for item in exported_questions if item["config_key"] != removed_key]
    preview = client.post(
        "/api/v1/admin/config/import/validate",
        headers=headers,
        json={"manifest": manifest, "mode": "replace"},
    )
    assert preview.status_code == 200, preview.text
    data = preview.json()
    response = client.post(
        "/api/v1/admin/config/import",
        headers=headers,
        json={
            "manifest": manifest,
            "mode": "replace",
            "expected_current_hash": data["current_hash"],
            "expected_incoming_hash": data["incoming_hash"],
            "confirm": True,
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ACTIVE_ATTEMPT_CONFLICT"
    assert response.json()["error"]["details"]
    assert attempt["questions"]


def test_legacy_question_delete_also_rejects_active_attempt(client: TestClient) -> None:
    """The old integer-ID delete route shares the same active-attempt guard."""
    headers, questions = configure_two_question_quiz(client)
    create_attempt(client)
    response = client.delete(
        f"/api/v1/admin/questions/{questions[0]['id']}", headers=headers
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ACTIVE_ATTEMPT_CONFLICT"


def test_legacy_font_reference_write_rejects_unassigned_cards(client: TestClient) -> None:
    """Unassigned cards can be represented by the full manifest but not hidden by legacy PUT."""
    headers, _ = configure_two_question_quiz(client)
    manifest = client.get("/api/v1/admin/config/export", headers=headers).json()
    manifest["font_references"]["unassigned_cards"] = [
        {
            "config_key": "unassigned-note",
            "title": "未归类笔记",
            "image_url": "https://pan.yurucamp.cn/note.png",
            "note": "等待归档",
            "difficulty": 1,
            "sort_order": 0,
        }
    ]
    preview = client.post(
        "/api/v1/admin/config/import/validate",
        headers=headers,
        json={"manifest": manifest, "mode": "replace"},
    ).json()
    imported = client.post(
        "/api/v1/admin/config/import",
        headers=headers,
        json={
            "manifest": manifest,
            "mode": "replace",
            "expected_current_hash": preview["current_hash"],
            "expected_incoming_hash": preview["incoming_hash"],
            "confirm": True,
        },
    )
    assert imported.status_code == 200
    legacy = client.put(
        "/api/v1/admin/font-reference-sections",
        headers=headers,
        json={"sections": []},
    )
    assert legacy.status_code == 409
    assert legacy.json()["error"]["code"] == "FONT_REFERENCE_ORPHANED"


def test_import_rejects_unapproved_font_origin(client: TestClient) -> None:
    """A manifest cannot authorize a new font host merely by mentioning it."""
    headers, _ = configure_two_question_quiz(client)
    manifest = client.get("/api/v1/admin/config/export", headers=headers).json()
    option = next(
        option
        for group in manifest["option_catalog"]["groups"]
        for option in group["options"]
    )
    option["font_url"] = "https://evil.example.test/font.woff2"
    response = client.post(
        "/api/v1/admin/config/import/validate",
        headers=headers,
        json={"manifest": manifest, "mode": "replace"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "FONT_ORIGIN_NOT_ALLOWED"
    assert response.json()["error"]["details"]


def test_config_body_limit_runs_before_json_parser(database_url: str) -> None:
    """Oversized import bodies receive the stable 413 envelope before validation."""
    app = create_app(
        AppSettings(database_url=database_url, cookie_secure=False, config_max_bytes=128)
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/admin/config/import/validate",
            content=b"{" + b"x" * 256,
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "CONFIG_BODY_TOO_LARGE"


def test_outbox_worker_claims_publishes_and_marks_hash(monkeypatch, client: TestClient) -> None:
    """Publication is durable and testable without contacting an external R2 service."""
    headers, _ = configure_two_question_quiz(client)
    published: list[str] = []
    monkeypatch.setattr(
        sync_service,
        "_upload_json_strict",
        lambda settings, key, data: published.append(key),
    )
    assert sync_service.run_once(client.app.state.database, client.app.state.settings)
    with client.app.state.database.sessions() as session:
        task = session.query(SyncOutbox).filter(
            SyncOutbox.scope == "questions", SyncOutbox.status == "succeeded"
        ).one()
        state = session.get(SyncScopeState, "questions")
        assert task.status == "succeeded"
        assert task.attempts == 1
        assert state is not None and state.published_state_hash == task.state_hash
    assert "sync/questions/all.json" in published


def test_late_worker_cannot_clobber_a_new_scope_owner(client: TestClient) -> None:
    """A stale worker cannot fail or supersede a task after its lease is reclaimed."""
    configure_two_question_quiz(client)
    claim = sync_service._claim(client.app.state.database, None)
    assert claim is not None
    task_id, scope, _, old_token, old_fence, _ = claim
    with client.app.state.database.sessions() as session:
        task = session.get(SyncOutbox, task_id)
        assert task is not None
        task.status = "running"
        task.lock_token = "new-owner"
        task.scope_fence = old_fence + 1
        session.commit()

    sync_service._mark_failed(
        client.app.state.database, task_id, old_token, old_fence, "late failure"
    )
    sync_service._requeue_after_ownership_loss(
        client.app.state.database,
        task_id,
        scope,
        old_token,
        old_fence,
        "late ownership loss",
    )

    with client.app.state.database.sessions() as session:
        task = session.get(SyncOutbox, task_id)
        assert task is not None
        assert task.status == "running"
        assert task.lock_token == "new-owner"
