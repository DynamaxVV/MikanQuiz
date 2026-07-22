"""Deterministic HTTP acceptance tests for the documented backend boundaries."""

from datetime import timedelta

from fastapi.testclient import TestClient
import pytest

from app.config import AppSettings
from app.database import Database
from app.models import Admin, AdminSession, QuizAttempt, utc_now
from app.services import admin as admin_service
from app.services import images as image_service
from tests.conftest import admin_headers


def configure_two_question_quiz(client: TestClient) -> tuple[dict[str, str], list[dict]]:
    """Create a reproducible two-question beginner quiz through admin HTTP APIs."""
    headers = admin_headers(client)
    strategy = {
        "question_count": 2,
        "modes": {
            "beginner": [100, 0, 0, 0, 0],
            "proficient": [100, 0, 0, 0, 0],
            "challenge": [100, 0, 0, 0, 0],
        },
    }
    assert client.put("/api/v1/admin/settings/strategy", json=strategy, headers=headers).status_code == 200
    questions = []
    for index, answer in enumerate(("B", "D"), start=1):
        response = client.post(
            "/api/v1/admin/questions",
            headers=headers,
            json={
                "text": f"题目 {index}",
                "image_url": "https://pan.yurucamp.cn/image.png",
                "difficulty": 1,
                "options": ["甲", "乙", "丙", "丁"],
                "answer": answer,
                "explanation": f"旧解析 {index}",
            },
        )
        assert response.status_code == 201, response.text
        questions.append(response.json())
    return headers, questions


def create_attempt(client: TestClient) -> dict:
    """Create one beginner attempt through the public route."""
    response = client.post("/api/v1/quiz/attempts", json={"mode": "beginner"})
    assert response.status_code == 201, response.text
    return response.json()


def test_public_attempt_boundary_idempotency_and_snapshot(client: TestClient) -> None:
    """Prove public payload secrecy, strict scoring, retry idempotency and snapshots."""
    headers, questions = configure_two_question_quiz(client)
    attempt = create_attempt(client)
    assert {"answer", "explanation"}.isdisjoint(attempt["questions"][0])
    attempt_headers = {"X-Quiz-Attempt": attempt["attempt_token"]}
    resumed = client.get("/api/v1/quiz/attempts/current", headers=attempt_headers)
    assert resumed.status_code == 200
    assert {"answer", "explanation"}.isdisjoint(resumed.json()["questions"][0])
    answers = {str(question["id"]): question["answer"] for question in questions}
    invalid = client.post(
        "/api/v1/quiz/attempts/submit",
        headers=attempt_headers,
        json={"display_name": "小明", "answers": {**answers, "999": "A"}},
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "INVALID_ANSWERS"
    invalid_choice = client.post(
        "/api/v1/quiz/attempts/submit",
        headers=attempt_headers,
        json={"display_name": "小明", "answers": {str(questions[0]["id"]): "Z"}},
    )
    assert invalid_choice.status_code == 422
    assert invalid_choice.json()["error"]["code"] == "VALIDATION_ERROR"
    response = client.post(
        "/api/v1/quiz/attempts/submit",
        headers=attempt_headers,
        json={"display_name": "小明", "answers": answers},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert (result["score"], result["correct_count"], result["total"]) == (100, 2, 2)
    retry = client.post(
        "/api/v1/quiz/attempts/submit",
        headers=attempt_headers,
        json={"display_name": "小明", "answers": answers},
    )
    assert retry.status_code == 200
    assert retry.json() == result
    changed = client.patch(
        f"/api/v1/admin/questions/{questions[0]['id']}",
        headers=headers,
        json={"answer": "A", "explanation": "新解析"},
    )
    assert changed.status_code == 200
    historical = client.get(
        f"/api/v1/admin/submissions/{result['submission_id']}", headers=headers
    )
    assert historical.status_code == 200
    detail_by_question = {
        item["question_id"]: item for item in historical.json()["details"]
    }
    snapshot = detail_by_question[questions[0]["id"]]
    assert snapshot["explanation"] == "旧解析 1"
    assert snapshot["correct_answer"] == "B"
    assert snapshot["image_url"].endswith("image.png")
    assert snapshot["options"] == ["甲", "乙", "丙", "丁"]


def test_expired_attempt_cannot_resume_or_submit(
    client: TestClient, database: Database
) -> None:
    """Prove the 24-hour expiry boundary applies before the first submission."""
    _, questions = configure_two_question_quiz(client)
    attempt = create_attempt(client)
    with database.sessions() as session:
        row = session.query(QuizAttempt).one()
        row.expires_at = utc_now() - timedelta(seconds=1)
        session.commit()
    attempt_headers = {"X-Quiz-Attempt": attempt["attempt_token"]}
    resumed = client.get("/api/v1/quiz/attempts/current", headers=attempt_headers)
    assert (resumed.status_code, resumed.json()["error"]["code"]) == (410, "ATTEMPT_EXPIRED")
    answers = {str(question["id"]): question["answer"] for question in questions}
    submitted = client.post(
        "/api/v1/quiz/attempts/submit",
        headers=attempt_headers,
        json={"answers": answers},
    )
    assert (submitted.status_code, submitted.json()["error"]["code"]) == (410, "ATTEMPT_EXPIRED")


def test_admin_login_session_expiry_and_logout(
    client: TestClient, database: Database
) -> None:
    """Exercise Argon2 login and rejection of an expired administrator session."""
    headers = admin_headers(client)
    assert client.get("/api/v1/admin/session", headers=headers).status_code == 200
    with database.sessions() as session:
        assert session.query(Admin).one().password_hash.startswith("$argon2")
        row = session.query(AdminSession).one()
        row.expires_at = utc_now() - timedelta(seconds=1)
        session.commit()
    expired = client.get("/api/v1/admin/session", headers=headers)
    assert (expired.status_code, expired.json()["error"]["code"]) == (401, "ADMIN_SESSION_INVALID")


def test_web_login_uses_http_only_cookie_and_logout_clears_it(client: TestClient) -> None:
    """Web session transport is cookie-only while Mini Program retains Bearer tokens."""
    response = client.post(
        "/api/v1/admin/web/login",
        json={"username": "operator", "password": "correct-password"},
    )
    assert response.status_code == 200
    assert "token" not in response.json()
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    assert client.get("/api/v1/admin/session").status_code == 200
    logout = client.post("/api/v1/admin/logout")
    assert logout.status_code == 204
    assert "max-age=0" in logout.headers["set-cookie"].lower()


def test_disabled_administrator_immediately_loses_existing_session(
    client: TestClient, database: Database
) -> None:
    """Show a disabled account cannot use a token that was issued moments earlier."""
    headers = admin_headers(client)
    with database.sessions() as session:
        admin_service.add_admin(session, "backup", "correct-password")
        admin_service.set_admin_active(session, "operator", False)
    response = client.get("/api/v1/admin/session", headers=headers)
    assert (response.status_code, response.json()["error"]["code"]) == (401, "ADMIN_SESSION_INVALID")


def test_admin_image_upload_uses_r2_adapter_and_returns_public_url(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Keep WebDAV credentials server-side while the browser receives only a URL."""
    captured: dict[str, object] = {}

    def fake_run(settings: AppSettings, path: str, content_type: str) -> str:
        captured["content_type"] = content_type
        return "https://images.example.test/demo.png"

    client.app.state.settings = AppSettings(
        database_url=client.app.state.settings.database_url,
        cookie_secure=False,
        r2_endpoint="https://account.r2.cloudflarestorage.com",
        r2_access_key_id="key",
        r2_secret_access_key="secret",
        r2_bucket="images",
        r2_public_base_url="https://images.example.test",
    )
    monkeypatch.setattr(image_service, "run_uploader", fake_run)
    response = client.post(
        "/api/v1/admin/images",
        headers=admin_headers(client),
        files={"image": ("sample.png", b"\x89PNG\r\n\x1a\ncontent", "image/png")},
    )
    assert response.status_code == 201, response.text
    assert response.json()["image_url"] == "https://images.example.test/demo.png"
    assert captured["content_type"] == "image/png"


def test_admin_image_upload_rejects_unsupported_content(client: TestClient) -> None:
    """Reject malformed uploads before checking or using WebDAV configuration."""
    response = client.post(
        "/api/v1/admin/images",
        headers=admin_headers(client),
        files={"image": ("sample.txt", b"not an image", "text/plain")},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_IMAGE"


def test_font_references_are_public_and_admin_managed(client: TestClient) -> None:
    """Cover the public list plus authenticated creation and removal boundaries."""
    headers = admin_headers(client)
    denied = client.post(
        "/api/v1/admin/font-references",
        json={"title": "未登录", "image_url": "https://images.example.test/no.png"},
    )
    assert denied.status_code == 401
    created = client.post(
        "/api/v1/admin/font-references",
        headers=headers,
        json={
            "title": "宋体与仿宋对照",
            "image_url": "https://images.example.test/font-reference.png",
            "note": "用于观察横竖笔画差异。",
        },
    )
    assert created.status_code == 201, created.text
    item = created.json()
    public = client.get("/api/v1/font-references")
    assert public.status_code == 200
    assert public.json() == [item]
    deleted = client.delete(
        f"/api/v1/admin/font-references/{item['id']}", headers=headers
    )
    assert deleted.status_code == 204
    assert client.get("/api/v1/font-references").json() == []


def test_admin_questions_accept_multiple_difficulty_filters(client: TestClient) -> None:
    """Keep multi-select difficulty tags backed by one filtered server query."""
    headers = admin_headers(client)
    for difficulty in (1, 3, 5):
        response = client.post(
            "/api/v1/admin/questions",
            headers=headers,
            json={
                "text": f"{difficulty} 星题目",
                "difficulty": difficulty,
                "options": ["甲", "乙", "丙", "丁"],
                "answer": "A",
                "explanation": "解析",
            },
        )
        assert response.status_code == 201, response.text
    listed = client.get(
        "/api/v1/admin/questions?difficulty=1&difficulty=5", headers=headers
    )
    assert listed.status_code == 200, listed.text
    assert {item["difficulty"] for item in listed.json()["items"]} == {1, 5}
