"""Public feedback persistence, upload, rate-limit, and notification checks."""

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import AppSettings
from app.models import Feedback, FeedbackAttachment
from app.services import feedback as feedback_service


def local_settings(client: TestClient, tmp_path: Path, **overrides: object) -> None:
    values = {
        "database_url": client.app.state.settings.database_url,
        "cookie_secure": False,
        "storage_backend": "local",
        "local_storage_path": str(tmp_path / "uploads"),
        "local_public_base_url": "http://127.0.0.1:8000/uploads",
        **overrides,
    }
    client.app.state.settings = AppSettings(**values)


def test_feedback_accepts_anonymous_text_and_three_images(
    client: TestClient, database, tmp_path: Path
) -> None:
    local_settings(client, tmp_path)
    files = [
        ("images", (f"shot-{index}.png", b"\x89PNG\r\n\x1a\nfixture", "image/png"))
        for index in range(3)
    ]
    response = client.post(
        "/api/v1/feedback",
        data={
            "message": "结果页的题图在手机上有点小。",
            "contact_qq": "123456789",
            "source": "result",
            "client_url": "https://example.test/result/12",
            "context": '{"mode":"proficient","score":80,"totalCount":10,"submissionId":"12"}',
        },
        files=files,
    )
    assert response.status_code == 201, response.text
    assert response.json()["email_status"] == "disabled"
    with database.sessions() as session:
        feedback = session.scalar(select(Feedback))
        assert feedback is not None
        assert feedback.contact_qq == "123456789"
        assert feedback.context["submissionId"] == "12"
        assert len(session.scalars(select(FeedbackAttachment)).all()) == 3


def test_feedback_rejects_fourth_image_and_empty_message(client: TestClient, tmp_path: Path) -> None:
    local_settings(client, tmp_path)
    files = [("images", (f"{index}.png", b"\x89PNG\r\n\x1a\nfixture", "image/png")) for index in range(4)]
    too_many = client.post("/api/v1/feedback", data={"message": "反馈"}, files=files)
    assert too_many.status_code == 422
    assert too_many.json()["error"]["code"] == "TOO_MANY_FEEDBACK_IMAGES"

    empty = client.post("/api/v1/feedback", data={"message": "   "})
    assert empty.status_code == 422
    assert empty.json()["error"]["code"] == "FEEDBACK_MESSAGE_REQUIRED"

    invalid_qq = client.post("/api/v1/feedback", data={"message": "反馈", "contact_qq": "not-a-qq"})
    assert invalid_qq.status_code == 422
    assert invalid_qq.json()["error"]["code"] == "INVALID_FEEDBACK"

    oversized = client.post(
        "/api/v1/feedback",
        data={"message": "反馈"},
        files=[("images", ("large.jpg", b"\xff\xd8\xff" + b"0" * feedback_service.MAX_IMAGE_BYTES, "image/jpeg"))],
    )
    assert oversized.status_code == 422
    assert oversized.json()["error"]["code"] == "FEEDBACK_IMAGE_TOO_LARGE"


def test_feedback_keeps_record_when_email_delivery_fails(
    client: TestClient, database, tmp_path: Path, monkeypatch
) -> None:
    local_settings(
        client,
        tmp_path,
        feedback_smtp_host="smtp.example.test",
        feedback_email_from="quiz@example.test",
        feedback_email_to="owner@example.test",
    )

    def fail(_: AppSettings, __: feedback_service.FeedbackNotification) -> str:
        raise feedback_service.FeedbackEmailError("SMTP 投递失败")

    monkeypatch.setattr(feedback_service, "send_feedback_email", fail)
    response = client.post("/api/v1/feedback", data={"message": "邮件失败也应该保留。"})
    assert response.status_code == 201
    assert response.json()["email_status"] == "failed"
    with database.sessions() as session:
        feedback = session.scalar(select(Feedback))
        assert feedback is not None
        assert feedback.email_status == "failed"
        assert feedback.email_error == "SMTP 投递失败"


def test_feedback_email_renders_context_and_image_links(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeSMTP:
        def __init__(self, host: str, port: int, timeout: int) -> None:
            captured.update(host=host, port=port, timeout=timeout)

        def __enter__(self):
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def starttls(self) -> None:
            captured["starttls"] = True

        def login(self, username: str, password: str) -> None:
            captured["login"] = (username, password)

        def send_message(self, message) -> None:
            captured["message"] = message

    monkeypatch.setattr(feedback_service.smtplib, "SMTP", FakeSMTP)
    status = feedback_service.send_feedback_email(
        AppSettings(
            feedback_smtp_host="smtp.example.test",
            feedback_smtp_username="sender@example.test",
            feedback_smtp_password="secret",
            feedback_email_from="sender@example.test",
            feedback_email_to="owner@example.test",
        ),
        feedback_service.FeedbackNotification(
            feedback_id=7,
            message="图片显示异常",
            contact_qq="123456789",
            source="result",
            client_url="https://example.test/result/7",
            context={"score": 80, "submissionId": "7"},
            image_urls=("https://images.example.test/feedback/shot.png",),
            created_at="2026-09-22T00:00:00+00:00",
        ),
    )
    assert status == "sent"
    assert captured["starttls"] is True
    assert captured["login"] == ("sender@example.test", "secret")
    email = captured["message"]
    assert "图片显示异常" in email.get_content()
    assert "联系 QQ 号：123456789" in email.get_content()
    assert "https://images.example.test/feedback/shot.png" in email.get_content()


def test_feedback_rate_limit_is_process_local_and_bounded(client: TestClient, tmp_path: Path) -> None:
    local_settings(client, tmp_path)
    responses = [client.post("/api/v1/feedback", data={"message": f"反馈 {index}"}) for index in range(6)]
    assert [response.status_code for response in responses] == [201, 201, 201, 201, 201, 429]
    assert responses[-1].json()["error"]["code"] == "FEEDBACK_RATE_LIMITED"
