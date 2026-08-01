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
            "beginner": [100, 0, 0],
            "proficient": [100, 0, 0],
            "challenge": [100, 0, 0],
        },
    }
    assert client.put("/api/v1/admin/settings/strategy", json=strategy, headers=headers).status_code == 200
    catalog = client.get("/api/v1/admin/option-groups", headers=headers).json()
    other = next(group for group in catalog if group["name"] == "其他")
    other["options"] = [
        {"name": name, "minimum_difficulty": 1, "sort_order": index}
        for index, name in enumerate(("甲", "乙", "丙", "丁"))
    ]
    catalog = client.put("/api/v1/admin/option-groups", json={"groups": catalog}, headers=headers).json()
    option_ids = {item["name"]: item["id"] for group in catalog for item in group["options"]}
    questions = []
    for index, answer in enumerate(("B", "D"), start=1):
        response = client.post(
            "/api/v1/admin/questions",
            headers=headers,
            json={
                "text": f"题目 {index}",
                "image_url": "https://pan.yurucamp.cn/image.png",
                "difficulty": 1,
                    "correct_option_id": option_ids[{"B": "乙", "D": "丁"}[answer]],
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
    answers = {str(question["id"]): question["correct_option_id"] for question in questions}
    invalid = client.post(
        "/api/v1/quiz/attempts/submit",
        headers=attempt_headers,
        json={"display_name": "小明", "answers": {**answers, "999": 1}},
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
        json={"explanation": "新解析"},
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
    assert snapshot["correct_option_id"] == questions[0]["correct_option_id"]
    assert snapshot["image_url"].endswith("image.png")
    assert snapshot["option_groups"]


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
    answers = {str(question["id"]): question["correct_option_id"] for question in questions}
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


def test_font_references_with_sections(client: TestClient) -> None:
    """Cover catalogue save and public grouped listing."""
    headers = admin_headers(client)
    denied = client.put(
        "/api/v1/admin/font-reference-sections",
        json={"sections": [{"name": "空节", "sort_order": 0, "cards": []}]},
    )
    assert denied.status_code == 401
    payload = {
        "sections": [
            {
                "name": "宋体",
                "sort_order": 0,
                "cards": [
                    {
                        "title": "宋体与仿宋对照",
                        "image_url": "https://images.example.test/font-ref.png",
                        "note": "用于观察横竖笔画",
                        "difficulty": 2,
                        "sort_order": 0,
                    }
                ],
            },
            {
                "name": "黑体",
                "sort_order": 1,
                "cards": [],
            },
        ]
    }
    saved = client.put("/api/v1/admin/font-reference-sections", headers=headers, json=payload)
    assert saved.status_code == 200, saved.text
    saved_data = saved.json()
    assert len(saved_data) == 2
    assert saved_data[0]["name"] == "宋体"
    assert len(saved_data[0]["cards"]) == 1
    assert saved_data[0]["cards"][0]["title"] == "宋体与仿宋对照"
    assert saved_data[0]["cards"][0]["sort_order"] == 0
    assert saved_data[1]["name"] == "黑体"
    assert saved_data[1]["cards"] == []

    public = client.get("/api/v1/font-references")
    assert public.status_code == 200
    public_data = public.json()
    assert len(public_data) == 2
    assert public_data[0]["name"] == "宋体"
    assert len(public_data[0]["cards"]) == 1

    edited = {
        "sections": [
            {
                "id": saved_data[0]["id"],
                "name": "宋体类",
                "sort_order": 0,
                "cards": [
                    {
                        "id": saved_data[0]["cards"][0]["id"],
                        "title": "宋体与仿宋对照（已编辑）",
                        "image_url": "https://images.example.test/font-ref.png",
                        "note": "已更新说明",
                        "difficulty": 3,
                        "sort_order": 0,
                    }
                ],
            }
        ]
    }
    updated = client.put("/api/v1/admin/font-reference-sections", headers=headers, json=edited)
    assert updated.status_code == 200, updated.text
    updated_data = updated.json()
    assert len(updated_data) == 1
    assert updated_data[0]["name"] == "宋体类"
    assert updated_data[0]["cards"][0]["title"] == "宋体与仿宋对照（已编辑）"

    empty = client.put("/api/v1/admin/font-reference-sections", headers=headers, json={"sections": []})
    assert empty.status_code == 200
    assert client.get("/api/v1/font-references").json() == []


def test_admin_questions_accept_multiple_difficulty_filters(client: TestClient) -> None:
    """Keep multi-select difficulty tags backed by one filtered server query."""
    headers = admin_headers(client)
    catalog = client.get("/api/v1/admin/option-groups", headers=headers).json()
    other = next(group for group in catalog if group["name"] == "其他")
    other["options"] = [{"name": "甲", "minimum_difficulty": 1, "sort_order": 0}]
    catalog = client.put("/api/v1/admin/option-groups", json={"groups": catalog}, headers=headers).json()
    option_id = next(item["id"] for group in catalog for item in group["options"] if item["name"] == "甲")
    missing_image = client.post(
        "/api/v1/admin/questions",
        headers=headers,
        json={"text": "缺少题图", "difficulty": 1, "correct_option_id": option_id, "explanation": "解析"},
    )
    assert missing_image.status_code == 422
    for difficulty in (1, 2, 3):
        response = client.post(
            "/api/v1/admin/questions",
            headers=headers,
            json={
                "text": f"{difficulty} 星题目",
                "image_url": "https://images.example.test/question.png",
                "difficulty": difficulty,
                "correct_option_id": option_id,
                "explanation": "解析",
            },
        )
        assert response.status_code == 201, response.text
    listed = client.get(
        "/api/v1/admin/questions?difficulty=1&difficulty=3", headers=headers
    )
    assert listed.status_code == 200, listed.text
    assert {item["difficulty"] for item in listed.json()["items"]} == {1, 3}


def test_admin_question_font_filter_and_navigation(client: TestClient) -> None:
    """Keep pagination and detail navigation in the same filtered result set."""
    headers = admin_headers(client)
    catalog = client.get("/api/v1/admin/option-groups", headers=headers).json()
    other = next(group for group in catalog if group["name"] == "其他")
    other["options"] = [
        {"name": "甲", "minimum_difficulty": 1, "sort_order": 0},
        {"name": "乙", "minimum_difficulty": 1, "sort_order": 1},
    ]
    catalog = client.put("/api/v1/admin/option-groups", json={"groups": catalog}, headers=headers).json()
    options = {item["name"]: item["id"] for group in catalog for item in group["options"]}
    created: list[int] = []
    for text, option_id in (("第一题", options["甲"]), ("第二题", options["甲"]), ("第三题", options["甲"]), ("其他题", options["乙"])):
        response = client.post("/api/v1/admin/questions", headers=headers, json={
            "text": text, "image_url": "https://images.example.test/question.png",
            "difficulty": 1, "correct_option_id": option_id, "explanation": "解析",
        })
        assert response.status_code == 201, response.text
        created.append(response.json()["id"])
    filtered = client.get(f"/api/v1/admin/questions?page=2&page_size=2&correct_option_id={options['甲']}&sort_by=id&sort_order=asc", headers=headers)
    assert filtered.status_code == 200, filtered.text
    assert filtered.json()["total"] == 3
    assert [item["id"] for item in filtered.json()["items"]] == [created[2]]
    middle = client.get(f"/api/v1/admin/questions/{created[1]}/navigation?correct_option_id={options['甲']}&sort_by=id&sort_order=asc", headers=headers)
    assert middle.status_code == 200, middle.text
    assert middle.json() == {"previous_id": created[0], "next_id": created[2], "position": 2, "total": 3}


def test_font_stream_rejects_bad_upstream_content(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Do not return an HTML error page as a seemingly successful font file."""
    class FakeResponse:
        headers = {"content-type": "text/html"}
        content = b"<html>missing</html>"

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def get(self, _: str) -> FakeResponse:
            return FakeResponse()

    client.app.state.settings = AppSettings(
        database_url=client.app.state.settings.database_url,
        cookie_secure=False,
        r2_public_base_url="https://images.example.test",
    )
    monkeypatch.setattr("app.api.httpx.AsyncClient", lambda **_: FakeClient())
    response = client.get("/api/v1/fonts/stream?url=https%3A%2F%2Fimages.example.test%2Ffont.ttf")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_FONT"


def test_deleting_font_marks_question_for_repair(client: TestClient) -> None:
    """A removed correct font leaves the question editable and blocks new attempts."""
    headers, questions = configure_two_question_quiz(client)
    catalog = client.get("/api/v1/admin/option-groups", headers=headers).json()
    for group in catalog:
        group["options"] = [option for option in group["options"] if option["id"] != questions[0]["correct_option_id"]]
    assert client.put("/api/v1/admin/option-groups", json={"groups": catalog}, headers=headers).status_code == 200
    question = client.get(f"/api/v1/admin/questions/{questions[0]['id']}", headers=headers)
    assert question.status_code == 200
    assert question.json()["configuration_error"] == "正确字体已被删除，请重新选择后保存题目"
    attempt = client.post("/api/v1/quiz/attempts", json={"mode": "beginner"})
    assert (attempt.status_code, attempt.json()["error"]["code"]) == (409, "QUESTION_FONT_MISSING")


def test_catalog_rejects_deleting_a_nonempty_group(client: TestClient) -> None:
    """Keep group deletion safe even when a client bypasses the management page."""
    headers = admin_headers(client)
    catalog = client.get("/api/v1/admin/option-groups", headers=headers).json()
    other = next(group for group in catalog if group["name"] == "其他")
    other["options"] = [{"name": "甲", "minimum_difficulty": 1, "sort_order": 0}]
    catalog = client.put("/api/v1/admin/option-groups", json={"groups": catalog}, headers=headers).json()
    response = client.put(
        "/api/v1/admin/option-groups",
        json={"groups": [group for group in catalog if group["id"] != other["id"]]},
        headers=headers,
    )
    assert (response.status_code, response.json()["error"]["code"]) == (409, "OPTION_GROUP_NOT_EMPTY")


def test_catalog_rejects_deleting_protected_groups(client: TestClient) -> None:
    """类黑, 类宋, 类圆 are system-reserved and cannot be deleted even when empty."""
    headers = admin_headers(client)
    catalog = client.get("/api/v1/admin/option-groups", headers=headers).json()
    for group in catalog:
        group["options"] = []
    catalog = client.put("/api/v1/admin/option-groups", json={"groups": catalog}, headers=headers).json()
    for name in ["类黑体", "类宋体", "类圆体"]:
        response = client.put(
            "/api/v1/admin/option-groups",
            json={"groups": [group for group in catalog if group["name"] != name]},
            headers=headers,
        )
        assert (response.status_code, response.json()["error"]["code"]) == (403, "OPTION_GROUP_PROTECTED"), f"{name} should be protected"
