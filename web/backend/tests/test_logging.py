"""Tests for JSON logs, request correlation and sensitive-data boundaries."""

import json
import logging
from subprocess import TimeoutExpired
from uuid import UUID

from fastapi.testclient import TestClient
import pytest

from app.config import AppSettings
from app.logging import JsonFormatter, LOGGER_NAME, log_event
from app.services import images as image_service
from tests.conftest import admin_headers


class JsonCapture(logging.Handler):
    """Collect formatted application events without depending on pytest logging."""

    def __init__(self) -> None:
        """Create an in-memory handler using the production JSON formatter."""
        super().__init__()
        self.events: list[dict] = []
        self.setFormatter(JsonFormatter())

    def emit(self, record: logging.LogRecord) -> None:
        """Parse each production-formatted JSON line for exact assertions."""
        self.events.append(json.loads(self.format(record)))


def install_capture() -> JsonCapture:
    """Attach one test-only handler to the named application logger."""
    capture = JsonCapture()
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG)
    logger.disabled = False
    logger.addHandler(capture)
    return capture


def remove_capture(capture: JsonCapture) -> None:
    """Avoid leaking the test handler into later tests."""
    logging.getLogger(LOGGER_NAME).removeHandler(capture)


def test_access_log_has_generated_request_id_and_client_ip(client: TestClient) -> None:
    """Every API request has a correlated access event and response header."""
    capture = install_capture()
    try:
        response = client.get("/api/v1/quiz/settings", headers={"User-Agent": "LogTest/1"})
    finally:
        remove_capture(capture)
    assert response.status_code == 200
    request_id = response.headers["x-request-id"]
    assert str(UUID(request_id)) == request_id
    access = next(event for event in capture.events if event["event"] == "http_request")
    assert access["request_id"] == request_id
    assert access["client_ip"]
    assert access["user_agent"] == "LogTest/1"
    assert access["path"] == "/api/v1/quiz/settings"
    assert access["status_code"] == 200


def test_error_logging_never_includes_bearer_token_or_password(client: TestClient) -> None:
    """Error and access events retain useful context without credential leakage."""
    capture = install_capture()
    bearer = "secret-bearer-token"
    password = "secret-password"
    try:
        denied = client.get(
            "/api/v1/admin/session", headers={"Authorization": f"Bearer {bearer}"}
        )
        failed_login = client.post(
            "/api/v1/admin/miniprogram/login",
            json={"username": "operator", "password": password},
        )
    finally:
        remove_capture(capture)
    assert denied.status_code == 401
    assert failed_login.status_code == 401
    payload = json.dumps(capture.events, ensure_ascii=False)
    assert bearer not in payload
    assert password not in payload
    assert any(event["event"] == "admin_session_invalid" for event in capture.events)
    assert any(event["event"] == "admin_login_failed" for event in capture.events)


def test_admin_login_and_logout_are_audited(client: TestClient) -> None:
    """Successful administrator session changes retain the actor for later review."""
    capture = install_capture()
    try:
        login = client.post(
            "/api/v1/admin/web/login",
            json={"username": "operator", "password": "correct-password"},
        )
        logout = client.post("/api/v1/admin/logout")
    finally:
        remove_capture(capture)
    assert login.status_code == 200
    assert logout.status_code == 204
    audited = {
        event["event"]: event
        for event in capture.events
        if event["event"] in {"admin_login_succeeded", "admin_logout"}
    }
    assert audited["admin_login_succeeded"]["admin_username"] == "operator"
    assert audited["admin_logout"]["admin_username"] == "operator"


def test_r2_upload_failure_has_safe_audit_event(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R2 diagnostics retain a failure class but never upload credentials."""
    def fail_upload(*args: object, **kwargs: object) -> None:
        raise TimeoutExpired("node", 30)

    client.app.state.settings = AppSettings(
        database_url=client.app.state.settings.database_url,
        cookie_secure=False,
        r2_endpoint="https://account.r2.cloudflarestorage.com",
        r2_access_key_id="test-access-key",
        r2_secret_access_key="test-secret-key",
        r2_bucket="images",
        r2_public_base_url="https://images.example.test",
    )
    monkeypatch.setattr(image_service, "run", fail_upload)
    capture = install_capture()
    try:
        response = client.post(
            "/api/v1/admin/images",
            headers=admin_headers(client),
            files={"image": ("sample.png", b"\x89PNG\r\n\x1a\ncontent", "image/png")},
        )
    finally:
        remove_capture(capture)
    assert response.status_code == 502
    assert any(event["event"] == "r2_uploader_error" for event in capture.events)
    failed = next(event for event in capture.events if event["event"] == "r2_upload_failed")
    assert failed["admin_username"] == "operator"
    assert failed["error_code"] == "IMAGE_UPLOAD_FAILED"
    payload = json.dumps(capture.events, ensure_ascii=False)
    assert "test-access-key" not in payload
    assert "test-secret-key" not in payload


def test_unhandled_exception_event_includes_traceback() -> None:
    """The JSON formatter preserves traceback data for unexpected failures."""
    capture = install_capture()
    try:
        try:
            raise RuntimeError("test failure")
        except RuntimeError:
            log_event("unhandled_exception", logging.ERROR, exc_info=True)
    finally:
        remove_capture(capture)
    assert capture.events[0]["event"] == "unhandled_exception"
    assert "RuntimeError: test failure" in capture.events[0]["traceback"]
