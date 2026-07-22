"""Versioned FastAPI routes for anonymous quiz and administrator workflows."""

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, File, Header, Query, Request, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import AppSettings
from app.database import get_session
from app.errors import ApiError
from app.models import Admin, AdminSession, FontReference, Submission, as_utc, utc_now
from app.schemas import (
    AdminCredentials,
    AdminSessionResponse,
    AdminStatus,
    AttemptCreate,
    AttemptCreated,
    AttemptCurrent,
    AttemptSubmit,
    FontReferenceResponse,
    FontReferenceWrite,
    FontPresetsUpdate,
    HealthResponse,
    ImageUploadResponse,
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
    admin, admin_session = admin_service.authenticated_admin(session, token)
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


def font_reference_response(item: FontReference) -> FontReferenceResponse:
    """Serialize a persisted comparison image for public and admin clients."""
    return FontReferenceResponse(
        id=item.id,
        title=item.title,
        image_url=item.image_url,
        note=item.note,
        created_at=as_utc(item.created_at),
    )


@router.get("/font-references", response_model=list[FontReferenceResponse])
def list_font_references(
    session: Session = Depends(get_session),
) -> list[FontReferenceResponse]:
    """Return public font comparison images in stable creation order."""
    items = session.scalars(
        select(FontReference).order_by(FontReference.created_at.desc(), FontReference.id.desc())
    ).all()
    return [font_reference_response(item) for item in items]


@router.post("/quiz/attempts", response_model=AttemptCreated, status_code=201)
def create_quiz_attempt(
    data: AttemptCreate, session: Session = Depends(get_session)
) -> AttemptCreated:
    """Create and return a token-bound clean question set for a chosen mode."""
    token, attempt, questions = quiz_service.create_attempt(session, data.mode)
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
        return quiz_service.submit_attempt(session, token, data)
    except IntegrityError:
        session.rollback()
        attempt = quiz_service.get_attempt(session, token)
        submission = quiz_service.submission_for_attempt(session, attempt.id)
        if submission is None:
            raise
        return quiz_service.stored_result(session, submission)


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
    session: Session, data: AdminCredentials, settings: AppSettings | None
) -> tuple[str, AdminSession, Admin]:
    """Keep both client login routes backed by one password/session workflow."""
    hours = settings.admin_session_hours if settings else 8
    return admin_service.login_admin(session, data.username, data.password, hours)


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
    difficulty: list[Annotated[int, Query(ge=1, le=5)]] | None = Query(default=None),
    _: AdminAuth = Depends(require_admin),
    session: Session = Depends(get_session),
) -> QuestionPage:
    """List current questions through server-side filters and bounded pagination."""
    items, total = question_service.list_questions(
        session, page, page_size, query, difficulty
    )
    return QuestionPage(
        items=[admin_question(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("/admin/questions", response_model=QuestionResponse, status_code=201)
def create_admin_question(
    data: QuestionWrite,
    _: AdminAuth = Depends(require_admin),
    session: Session = Depends(get_session),
) -> QuestionResponse:
    """Create one validated question from the PC editor form."""
    return admin_question(question_service.create_question(session, data))


@router.get("/admin/questions/{question_id}", response_model=QuestionResponse)
def get_admin_question(
    question_id: int,
    _: AdminAuth = Depends(require_admin),
    session: Session = Depends(get_session),
) -> QuestionResponse:
    """Return a complete question for editing or read-only preview."""
    return admin_question(question_service.get_question(session, question_id))


@router.post("/admin/images", response_model=ImageUploadResponse, status_code=201)
async def upload_admin_image(
    image: UploadFile = File(...),
    _: AdminAuth = Depends(require_admin),
    settings: AppSettings = Depends(get_app_settings),
) -> ImageUploadResponse:
    """Upload a bounded administrator image through server-side WebDAV credentials."""
    content = await image.read(image_service.MAX_IMAGE_BYTES + 1)
    content_type = image.content_type or ""
    return ImageUploadResponse(
        image_url=image_service.upload_image(settings, content, content_type)
    )


@router.post(
    "/admin/font-references",
    response_model=FontReferenceResponse,
    status_code=201,
)
def create_font_reference(
    data: FontReferenceWrite,
    _: AdminAuth = Depends(require_admin),
    session: Session = Depends(get_session),
) -> FontReferenceResponse:
    """Create one public comparison image after administrator upload."""
    item = FontReference(title=data.title, image_url=data.image_url, note=data.note)
    session.add(item)
    session.commit()
    session.refresh(item)
    return font_reference_response(item)


@router.delete("/admin/font-references/{reference_id}", status_code=204)
def delete_font_reference(
    reference_id: int,
    _: AdminAuth = Depends(require_admin),
    session: Session = Depends(get_session),
) -> Response:
    """Unpublish and remove one comparison image record."""
    item = session.get(FontReference, reference_id)
    if item is None:
        raise ApiError(404, "FONT_REFERENCE_NOT_FOUND", "字体对照图不存在")
    session.delete(item)
    session.commit()
    return Response(status_code=204)


@router.patch("/admin/questions/{question_id}", response_model=QuestionResponse)
def patch_admin_question(
    question_id: int,
    data: QuestionPatch,
    _: AdminAuth = Depends(require_admin),
    session: Session = Depends(get_session),
) -> QuestionResponse:
    """Apply a validated partial edit while preserving fixed option invariants."""
    question = question_service.get_question(session, question_id)
    return admin_question(question_service.update_question(session, question, data))


@router.delete("/admin/questions/{question_id}", status_code=204)
def delete_admin_question(
    question_id: int,
    _: AdminAuth = Depends(require_admin),
    session: Session = Depends(get_session),
) -> Response:
    """Remove a current question without erasing immutable historical snapshots."""
    question_service.delete_question(session, question_service.get_question(session, question_id))
    return Response(status_code=204)


@router.get("/admin/settings", response_model=SettingsResponse)
def get_admin_settings(
    _: AdminAuth = Depends(require_admin), session: Session = Depends(get_session)
) -> SettingsResponse:
    """Return editable strategy and font shortcut settings."""
    return settings_response(question_service.get_settings(session))


@router.put("/admin/settings/strategy", response_model=SettingsResponse)
def put_admin_strategy(
    data: StrategyUpdate,
    _: AdminAuth = Depends(require_admin),
    session: Session = Depends(get_session),
) -> SettingsResponse:
    """Save validated question count and star-weight strategy settings."""
    settings = question_service.update_strategy(
        session, data, question_service.get_settings(session)
    )
    return settings_response(settings)


@router.put("/admin/settings/font-presets", response_model=SettingsResponse)
def put_admin_font_presets(
    data: FontPresetsUpdate,
    _: AdminAuth = Depends(require_admin),
    session: Session = Depends(get_session),
) -> SettingsResponse:
    """Save validated font shortcut strings independently from draw settings."""
    settings = question_service.update_font_presets(
        session, data, question_service.get_settings(session)
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
