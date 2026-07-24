"""Versioned FastAPI routes for anonymous quiz and administrator workflows."""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
from time import perf_counter
from typing import Annotated

import httpx
from fastapi import APIRouter, Cookie, Depends, File, Header, Query, Request, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import AppSettings
from app.database import get_session
from app.errors import ApiError
from app.logging import log_event
from app.models import Admin, AdminSession, FontOption, FontReference, Question, Submission, as_utc, utc_now
from app.schemas import (
    AdminCredentials,
    AdminSessionResponse,
    AdminStatus,
    AttemptCreate,
    AttemptCreated,
    AttemptCurrent,
    AttemptSubmit,
    FontReferenceResponse,
    FontReferenceUpdate,
    FontReferenceWrite,
    OptionCatalogUpdate,
    OptionGroupResponse,
    HealthResponse,
    ImageUploadResponse,
    QuestionExportItem,
    QuestionImportPayload,
    QuestionImportResult,
    QuestionPage,
    QuestionPatch,
    QuestionResponse,
    QuestionWrite,
    SettingsResponse,
    StrategyUpdate,
    SubmissionPage,
    SubmissionResult,
)
from app.services import admin as admin_service
from app.services import images as image_service
from app.services import questions as question_service
from app.services import quiz as quiz_service
from app.services.serializers import (
    admin_question,
    catalogue,
    settings_response,
    submission_list_item,
)


router = APIRouter(prefix="/api/v1")


@dataclass(frozen=True)
class AdminAuth:
    """A validated administrator and the session used to authenticate it."""

    admin: Admin
    session: AdminSession
    token: str


def get_admin_token(
    authorization: str | None = Header(default=None),
    quiz_admin_session: str | None = Cookie(default=None),
) -> str:
    """Prefer a Bearer token, otherwise accept the Web HttpOnly session cookie."""
    token = ""
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
    elif quiz_admin_session:
        token = quiz_admin_session
    if not token:
        raise ApiError(401, "ADMIN_AUTH_REQUIRED", "请先登录管理员账号")
    return token


def require_admin(
    token: str = Depends(get_admin_token), session: Session = Depends(get_session)
) -> AdminAuth:
    """Resolve the currently enabled account behind a protected route."""
    try:
        admin, admin_session = admin_service.authenticated_admin(session, token)
    except ApiError as error:
        if error.code == "ADMIN_SESSION_INVALID":
            log_event("admin_session_invalid", logging.WARNING, error_code=error.code)
        raise
    return AdminAuth(admin=admin, session=admin_session, token=token)


def attempt_token(x_quiz_attempt: str | None = Header(default=None)) -> str:
    """Require the documented opaque anonymous attempt-token header."""
    if not x_quiz_attempt:
        raise ApiError(401, "ATTEMPT_TOKEN_REQUIRED", "缺少答题会话")
    return x_quiz_attempt


def get_app_settings(request: Request) -> AppSettings:
    """Read immutable runtime settings stored by the application factory."""
    return request.app.state.settings


@router.get("/quiz/settings", response_model=SettingsResponse)
def public_settings(session: Session = Depends(get_session)) -> SettingsResponse:
    """Return public draw metadata without any current question answers."""
    return settings_response(question_service.get_settings(session))


@router.get("/fonts/stream")
async def stream_font(
    url: str = Query(...),
    settings: AppSettings = Depends(get_app_settings),
) -> Response:
    """Proxy a font file from R2 with CORS headers so @font-face can load cross-origin."""
    base = settings.r2_public_base_url.rstrip("/")
    if not url.startswith(base + "/") and url != base:
        raise ApiError(400, "INVALID_FONT_URL", "字体地址无效")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        content_type = resp.headers.get("content-type", "font/ttf")
        return Response(
            content=resp.content,
            media_type=content_type,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "public, max-age=31536000, immutable",
            },
        )


def font_reference_response(item: FontReference) -> FontReferenceResponse:
    """Serialize a persisted comparison card for public and admin clients."""
    return FontReferenceResponse(
        id=item.id,
        title=item.title,
        image_url=item.image_url,
        note=item.note,
        difficulty=item.difficulty,
        created_at=as_utc(item.created_at),
    )


@router.get("/font-references", response_model=list[FontReferenceResponse])
def list_font_references(
    session: Session = Depends(get_session),
) -> list[FontReferenceResponse]:
    """Return public font comparison cards in stable creation order."""
    items = session.scalars(
        select(FontReference).order_by(FontReference.created_at.desc(), FontReference.id.desc())
    ).all()
    return [font_reference_response(item) for item in items]


@router.post("/quiz/attempts", response_model=AttemptCreated, status_code=201)
def create_quiz_attempt(
    data: AttemptCreate, session: Session = Depends(get_session)
) -> AttemptCreated:
    """Create and return a token-bound clean question set for a chosen mode."""
    try:
        token, attempt, questions = quiz_service.create_attempt(session, data.mode)
    except ApiError as error:
        log_event(
            "quiz_business_error", logging.WARNING, error_code=error.code, mode=data.mode
        )
        raise
    log_event(
        "quiz_attempt_created",
        mode=attempt.mode,
        attempt_id=attempt.id,
        question_count=len(questions),
    )
    return AttemptCreated(
        attempt_token=token,
        mode=attempt.mode,
        expires_at=as_utc(attempt.expires_at),
        questions=questions,
    )


@router.get("/quiz/attempts/current", response_model=AttemptCurrent)
def resume_quiz_attempt(
    token: str = Depends(attempt_token), session: Session = Depends(get_session)
) -> AttemptCurrent:
    """Resume exactly the same unanswered question set for the current device."""
    attempt, questions = quiz_service.current_attempt(session, token)
    return AttemptCurrent(
        mode=attempt.mode, expires_at=as_utc(attempt.expires_at), questions=questions
    )


@router.post("/quiz/attempts/submit", response_model=SubmissionResult)
def submit_quiz_attempt(
    data: AttemptSubmit,
    token: str = Depends(attempt_token),
    session: Session = Depends(get_session),
) -> SubmissionResult:
    """Grade exactly one bound attempt and return a retry-stable result."""
    try:
        attempt = quiz_service.get_attempt(session, token)
        replayed = attempt.submitted_at is not None
        try:
            result = quiz_service.submit_attempt(session, token, data)
        except IntegrityError:
            session.rollback()
            attempt = quiz_service.get_attempt(session, token)
            submission = quiz_service.submission_for_attempt(session, attempt.id)
            if submission is None:
                raise
            result = quiz_service.stored_result(session, submission)
            replayed = True
    except ApiError as error:
        log_event("quiz_business_error", logging.WARNING, error_code=error.code)
        raise
    log_event(
        "quiz_submission_replayed" if replayed else "quiz_submitted",
        submission_id=result.submission_id,
        attempt_id=attempt.id,
        display_name=result.display_name,
        mode=result.mode,
        score=result.score,
        correct_count=result.correct_count,
        total=result.total,
    )
    return result


@router.post("/admin/web/login", response_model=AdminStatus)
def web_login(
    data: AdminCredentials,
    response: Response,
    session: Session = Depends(get_session),
    settings: AppSettings = Depends(get_app_settings),
) -> AdminStatus:
    """Set an HttpOnly Web cookie while never exposing its token to JavaScript."""
    token, admin_session, admin = login_admin(session, data, settings)
    response.set_cookie(
        key="quiz_admin_session",
        value=token,
        max_age=settings.admin_session_hours * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/api/v1/admin",
    )
    return AdminStatus(username=admin.username, expires_at=as_utc(admin_session.expires_at))


@router.post("/admin/miniprogram/login", response_model=AdminSessionResponse)
def miniprogram_login(
    data: AdminCredentials,
    session: Session = Depends(get_session),
    settings: AppSettings = Depends(get_app_settings),
) -> AdminSessionResponse:
    """Create the same bearer session contract for the Mini Program client."""
    token, admin_session, admin = login_admin(session, data, settings)
    return AdminSessionResponse(
        token=token, expires_at=as_utc(admin_session.expires_at), username=admin.username
    )


def login_admin(
    session: Session,
    data: AdminCredentials,
    settings: AppSettings | None,
) -> tuple[str, AdminSession, Admin]:
    """Keep both client login routes backed by one password/session workflow."""
    hours = settings.admin_session_hours if settings else 8
    try:
        token, admin_session, admin = admin_service.login_admin(
            session, data.username, data.password, hours
        )
    except ApiError:
        log_event("admin_login_failed", logging.WARNING, admin_username=data.username)
        raise
    log_event("admin_login_succeeded", admin_username=admin.username)
    return token, admin_session, admin


@router.post("/admin/logout", status_code=204)
def logout(
    response: Response,
    auth: AdminAuth = Depends(require_admin),
    session: Session = Depends(get_session),
    settings: AppSettings = Depends(get_app_settings),
) -> Response:
    """Revoke the current bearer token without affecting other administrators."""
    auth.session.revoked_at = utc_now()
    session.commit()
    log_event("admin_logout", admin_username=auth.admin.username)
    response.delete_cookie(
        key="quiz_admin_session",
        path="/api/v1/admin",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )
    response.status_code = 204
    return response


@router.get("/admin/session", response_model=AdminStatus)
def admin_session_status(auth: AdminAuth = Depends(require_admin)) -> AdminStatus:
    """Confirm a client-held token still belongs to an active administrator."""
    return AdminStatus(
        username=auth.admin.username, expires_at=as_utc(auth.session.expires_at)
    )


@router.get("/admin/questions", response_model=QuestionPage)
def list_admin_questions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    query: str | None = Query(default=None, max_length=500),
    difficulty: list[Annotated[int, Query(ge=1, le=3)]] | None = Query(default=None),
    sort_by: str = Query(default="updated_at", pattern="^(id|difficulty|text|updated_at)$"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    _: AdminAuth = Depends(require_admin),
    session: Session = Depends(get_session),
) -> QuestionPage:
    """List current questions through server-side filters and bounded pagination."""
    items, total = question_service.list_questions(
        session, page, page_size, query, difficulty, sort_by, sort_order
    )
    return QuestionPage(
        items=[admin_question(session, item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("/admin/questions", response_model=QuestionResponse, status_code=201)
def create_admin_question(
    data: QuestionWrite,
    auth: AdminAuth = Depends(require_admin),
    session: Session = Depends(get_session),
) -> QuestionResponse:
    """Create one validated question from the PC editor form."""
    question = question_service.create_question(session, data)
    log_event(
        "question_created", admin_username=auth.admin.username, question_id=question.id
    )
    return admin_question(session, question)


@router.get("/admin/questions/{question_id:int}", response_model=QuestionResponse)
def get_admin_question(
    question_id: int,
    _: AdminAuth = Depends(require_admin),
    session: Session = Depends(get_session),
) -> QuestionResponse:
    """Return a complete question for editing or read-only preview."""
    return admin_question(session, question_service.get_question(session, question_id))


@router.post("/admin/images", response_model=ImageUploadResponse, status_code=201)
async def upload_admin_image(
    image: UploadFile = File(...),
    auth: AdminAuth = Depends(require_admin),
    settings: AppSettings = Depends(get_app_settings),
) -> ImageUploadResponse:
    """Upload a bounded administrator image through server-side WebDAV credentials."""
    content = await image.read(image_service.MAX_IMAGE_BYTES + 1)
    content_type = image.content_type or ""
    started_at = perf_counter()
    try:
        image_url = image_service.upload_image(settings, content, content_type)
    except ApiError as error:
        log_event(
            "r2_upload_failed",
            logging.WARNING,
            admin_username=auth.admin.username,
            content_type=content_type,
            byte_count=len(content),
            duration_ms=round((perf_counter() - started_at) * 1000, 2),
            error_code=error.code,
        )
        raise
    log_event(
        "r2_upload_succeeded",
        admin_username=auth.admin.username,
        content_type=content_type,
        byte_count=len(content),
        duration_ms=round((perf_counter() - started_at) * 1000, 2),
    )
    return ImageUploadResponse(image_url=image_url)


@router.post("/admin/fonts", response_model=ImageUploadResponse, status_code=201)
async def upload_admin_font(
    font: UploadFile = File(...),
    auth: AdminAuth = Depends(require_admin),
    settings: AppSettings = Depends(get_app_settings),
) -> ImageUploadResponse:
    """Upload a font file (TTF/OTF/WOFF/WOFF2) through the R2 adapter."""
    content = await font.read(image_service.MAX_FONT_BYTES + 1)
    content_type = font.content_type or ""
    started_at = perf_counter()
    try:
        font_url = image_service.upload_font(settings, content, content_type, font.filename or "font")
    except ApiError as error:
        log_event(
            "r2_font_upload_failed",
            logging.WARNING,
            admin_username=auth.admin.username,
            content_type=content_type,
            byte_count=len(content),
            duration_ms=round((perf_counter() - started_at) * 1000, 2),
            error_code=error.code,
        )
        raise
    log_event(
        "r2_font_upload_succeeded",
        admin_username=auth.admin.username,
        content_type=content_type,
        byte_count=len(content),
        duration_ms=round((perf_counter() - started_at) * 1000, 2),
    )
    return ImageUploadResponse(image_url=font_url)


@router.post(
    "/admin/font-references",
    response_model=FontReferenceResponse,
    status_code=201,
)
def create_font_reference(
    data: FontReferenceWrite,
    auth: AdminAuth = Depends(require_admin),
    session: Session = Depends(get_session),
) -> FontReferenceResponse:
    """Create one public comparison card after administrator upload."""
    item = FontReference(title=data.title, image_url=data.image_url, note=data.note, difficulty=data.difficulty)
    session.add(item)
    session.commit()
    session.refresh(item)
    log_event(
        "font_reference_created",
        admin_username=auth.admin.username,
        reference_id=item.id,
    )
    return font_reference_response(item)


@router.patch(
    "/admin/font-references/{reference_id}",
    response_model=FontReferenceResponse,
)
def update_font_reference(
    reference_id: int,
    data: FontReferenceUpdate,
    auth: AdminAuth = Depends(require_admin),
    session: Session = Depends(get_session),
) -> FontReferenceResponse:
    """Update one comparison card's fields."""
    item = session.get(FontReference, reference_id)
    if item is None:
        raise ApiError(404, "FONT_REFERENCE_NOT_FOUND", "字体对照图不存在")
    if data.title is not None:
        item.title = data.title
    if data.image_url is not None:
        item.image_url = data.image_url
    if data.note is not None:
        item.note = data.note
    if data.difficulty is not None:
        item.difficulty = data.difficulty
    session.commit()
    session.refresh(item)
    log_event(
        "font_reference_updated",
        admin_username=auth.admin.username,
        reference_id=item.id,
    )
    return font_reference_response(item)


@router.delete("/admin/font-references/{reference_id}", status_code=204)
def delete_font_reference(
    reference_id: int,
    auth: AdminAuth = Depends(require_admin),
    session: Session = Depends(get_session),
) -> Response:
    """Unpublish and remove one comparison image record."""
    item = session.get(FontReference, reference_id)
    if item is None:
        raise ApiError(404, "FONT_REFERENCE_NOT_FOUND", "字体对照图不存在")
    session.delete(item)
    session.commit()
    log_event(
        "font_reference_deleted",
        admin_username=auth.admin.username,
        reference_id=reference_id,
    )
    return Response(status_code=204)


@router.patch("/admin/questions/{question_id:int}", response_model=QuestionResponse)
def patch_admin_question(
    question_id: int,
    data: QuestionPatch,
    auth: AdminAuth = Depends(require_admin),
    session: Session = Depends(get_session),
) -> QuestionResponse:
    """Apply a validated partial edit while preserving fixed option invariants."""
    question = question_service.get_question(session, question_id)
    updated = question_service.update_question(session, question, data)
    log_event(
        "question_updated", admin_username=auth.admin.username, question_id=updated.id
    )
    return admin_question(session, updated)


@router.delete("/admin/questions/{question_id:int}", status_code=204)
def delete_admin_question(
    question_id: int,
    auth: AdminAuth = Depends(require_admin),
    session: Session = Depends(get_session),
) -> Response:
    """Remove a current question without erasing immutable historical snapshots."""
    question = question_service.get_question(session, question_id)
    question_service.delete_question(session, question)
    log_event(
        "question_deleted", admin_username=auth.admin.username, question_id=question_id
    )
    return Response(status_code=204)


@router.get("/admin/questions/export")
def export_admin_questions(
    auth: AdminAuth = Depends(require_admin),
    session: Session = Depends(get_session),
) -> Response:
    """Export all questions as a downloadable JSON file."""
    items = session.scalars(
        select(Question).order_by(Question.id)
    ).all()
    payload = {
        "version": 1,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "questions": [
            {
                "id": q.id,
                "text": q.text,
                "image_url": q.image_url,
                "difficulty": q.difficulty,
                "correct_option_id": q.correct_option_id,
                "explanation": q.explanation,
                "created_at": as_utc(q.created_at).isoformat(),
                "updated_at": as_utc(q.updated_at).isoformat(),
            }
            for q in items
        ],
    }
    json_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    log_event(
        "questions_exported",
        admin_username=auth.admin.username,
        count=len(items),
    )
    return Response(
        content=json_bytes,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=questions.json"},
    )


@router.post("/admin/questions/import", response_model=QuestionImportResult)
def import_admin_questions(
    data: QuestionImportPayload,
    auth: AdminAuth = Depends(require_admin),
    session: Session = Depends(get_session),
) -> QuestionImportResult:
    """Bulk-import questions from a JSON file exported by the same endpoint."""
    created = 0
    failed = 0
    errors: list[str] = []

    for idx, item in enumerate(data.questions):
        n = idx + 1

        if item.correct_option_id is not None:
            option = session.get(FontOption, item.correct_option_id)
            if option is None:
                failed += 1
                errors.append(f"第 {n} 题「{item.text[:20]}」：字体 ID {item.correct_option_id} 不存在")
                continue

        question = Question(
            text=item.text.strip(),
            image_url=item.image_url.strip() if item.image_url else None,
            difficulty=item.difficulty,
            correct_option_id=item.correct_option_id,
            explanation=item.explanation.strip(),
        )
        session.add(question)
        created += 1

    session.commit()
    log_event(
        "questions_imported",
        admin_username=auth.admin.username,
        created=created,
        failed=failed,
    )
    return QuestionImportResult(
        total=len(data.questions),
        created=created,
        failed=failed,
        errors=errors,
    )


@router.get("/admin/settings", response_model=SettingsResponse)
def get_admin_settings(
    _: AdminAuth = Depends(require_admin), session: Session = Depends(get_session)
) -> SettingsResponse:
    """Return editable strategy and font shortcut settings."""
    return settings_response(question_service.get_settings(session))


@router.get("/admin/option-groups", response_model=list[OptionGroupResponse])
def get_option_catalog(
    _: AdminAuth = Depends(require_admin), session: Session = Depends(get_session)
) -> list[OptionGroupResponse]:
    """Return the catalogue used by both the editor and public quiz snapshots."""
    return catalogue(session)


def _collect_font_urls(session: Session) -> set[str]:
    """Collect every non-null font_url currently in the database."""
    rows = session.execute(select(FontOption.font_url).where(FontOption.font_url.isnot(None))).all()
    return {row[0] for row in rows if row[0]}


@router.put("/admin/option-groups", response_model=list[OptionGroupResponse])
def put_option_catalog(
    data: OptionCatalogUpdate,
    auth: AdminAuth = Depends(require_admin),
    session: Session = Depends(get_session),
    settings: AppSettings = Depends(get_app_settings),
) -> list[OptionGroupResponse]:
    """Save groups and options independently from draw strategy settings."""
    old_urls = _collect_font_urls(session)
    question_service.replace_option_catalog(session, data)
    new_urls = _collect_font_urls(session)
    orphaned = old_urls - new_urls
    for url in orphaned:
        image_service.delete_r2_object(settings, url)
    log_event(
        "option_catalog_replaced",
        admin_username=auth.admin.username,
        group_count=len(data.groups),
        option_count=sum(len(group.options) for group in data.groups),
    )
    return catalogue(session)


@router.get("/admin/option-groups/export")
def export_option_catalog(
    auth: AdminAuth = Depends(require_admin),
    session: Session = Depends(get_session),
) -> Response:
    """Export the complete font catalogue including font_url as a downloadable JSON file."""
    groups = catalogue(session)
    payload = {
        "version": 1,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "groups": [
            {
                "name": g.name,
                "sort_order": g.sort_order,
                "options": [
                    {"name": o.name, "minimum_difficulty": o.minimum_difficulty, "sort_order": o.sort_order, "font_url": o.font_url}
                    for o in g.options
                ],
            }
            for g in groups
        ],
    }
    json_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    log_event(
        "option_catalog_exported",
        admin_username=auth.admin.username,
        group_count=len(groups),
        option_count=sum(len(g.options) for g in groups),
    )
    return Response(
        content=json_bytes,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=font-catalog.json"},
    )


@router.post("/admin/option-groups/import", response_model=list[OptionGroupResponse])
def import_option_catalog(
    data: OptionCatalogUpdate,
    auth: AdminAuth = Depends(require_admin),
    session: Session = Depends(get_session),
) -> list[OptionGroupResponse]:
    """Import a font catalogue from an exported JSON file."""
    question_service.replace_option_catalog(session, data)
    log_event(
        "option_catalog_imported",
        admin_username=auth.admin.username,
        group_count=len(data.groups),
        option_count=sum(len(group.options) for group in data.groups),
    )
    return catalogue(session)


@router.put("/admin/settings/strategy", response_model=SettingsResponse)
def put_admin_strategy(
    data: StrategyUpdate,
    auth: AdminAuth = Depends(require_admin),
    session: Session = Depends(get_session),
) -> SettingsResponse:
    """Save validated question count and star-weight strategy settings."""
    settings = question_service.update_strategy(
        session, data, question_service.get_settings(session)
    )
    log_event(
        "strategy_updated",
        admin_username=auth.admin.username,
        question_count=data.question_count,
        modes=data.modes,
    )
    return settings_response(settings)


@router.get("/admin/submissions", response_model=SubmissionPage)
def list_admin_submissions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    display_name: str | None = Query(default=None, max_length=20),
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
    _: AdminAuth = Depends(require_admin),
    session: Session = Depends(get_session),
) -> SubmissionPage:
    """List permanent score records without returning all history at once."""
    statement = select(Submission)
    count_statement = select(func.count()).select_from(Submission)
    statement, count_statement = filter_submissions(
        statement, count_statement, display_name, from_, to
    )
    total = int(session.scalar(count_statement))
    items = session.scalars(
        statement.order_by(Submission.submitted_at.desc(), Submission.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return SubmissionPage(
        items=[submission_list_item(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/admin/submissions/{submission_id}", response_model=SubmissionResult)
def get_admin_submission(
    submission_id: int,
    _: AdminAuth = Depends(require_admin),
    session: Session = Depends(get_session),
) -> SubmissionResult:
    """Return the immutable historical scoring snapshot for one submission."""
    submission = session.get(Submission, submission_id)
    if submission is None:
        raise ApiError(404, "SUBMISSION_NOT_FOUND", "提交记录不存在")
    return quiz_service.stored_result(session, submission)


def filter_submissions(
    statement: object,
    count_statement: object,
    display_name: str | None,
    start: datetime | None,
    end: datetime | None,
) -> tuple[object, object]:
    """Apply optional submission table filters to both rows and count queries."""
    if display_name:
        statement = statement.where(Submission.display_name.contains(display_name.strip()))
        count_statement = count_statement.where(
            Submission.display_name.contains(display_name.strip())
        )
    if start:
        statement = statement.where(Submission.submitted_at >= start)
        count_statement = count_statement.where(Submission.submitted_at >= start)
    if end:
        statement = statement.where(Submission.submitted_at <= end)
        count_statement = count_statement.where(Submission.submitted_at <= end)
    return statement, count_statement
