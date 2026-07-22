"""Administrator accounts, Argon2 verification and revocable sessions."""

from datetime import timedelta
import re

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import Admin, AdminSession, utc_now
from app.security import (
    hash_password,
    hash_token,
    new_token,
    verify_invalid_password,
    verify_password,
)


_USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{2,63}$")


def validate_username(username: str) -> str:
    """Validate the deliberately small CLI-managed administrator username format."""
    username = username.strip()
    if not _USERNAME_RE.fullmatch(username):
        raise ValueError("用户名应为 3-64 位字母、数字、点、下划线或连字符")
    return username


def add_admin(session: Session, username: str, password: str) -> Admin:
    """Create an enabled Argon2-protected account and commit it."""
    username = validate_username(username)
    if len(password) < 8:
        raise ValueError("密码至少需要 8 个字符")
    if session.scalar(select(Admin).where(Admin.username == username)):
        raise ValueError("管理员账号已存在")
    admin = Admin(username=username, password_hash=hash_password(password))
    session.add(admin)
    session.commit()
    return admin


def list_admins(session: Session) -> list[Admin]:
    """Return administrator accounts without exposing password data."""
    return list(session.scalars(select(Admin).order_by(Admin.username)).all())


def change_password(session: Session, username: str, password: str) -> None:
    """Replace one administrator password and revoke all existing sessions."""
    admin = get_admin_by_username(session, username)
    if len(password) < 8:
        raise ValueError("密码至少需要 8 个字符")
    admin.password_hash = hash_password(password)
    revoke_admin_sessions(session, admin.id)
    session.commit()


def set_admin_active(session: Session, username: str, is_active: bool) -> None:
    """Enable or disable an account while preserving the final active account."""
    admin = get_admin_by_username(session, username)
    if not is_active and admin.is_active and active_admin_count(session) <= 1:
        raise ValueError("不能停用最后一个有效管理员")
    admin.is_active = is_active
    if not is_active:
        revoke_admin_sessions(session, admin.id)
    session.commit()


def get_admin_by_username(session: Session, username: str) -> Admin:
    """Look up a CLI-targeted account or explain that it does not exist."""
    admin = session.scalar(select(Admin).where(Admin.username == username.strip()))
    if admin is None:
        raise ValueError("管理员账号不存在")
    return admin


def active_admin_count(session: Session) -> int:
    """Count enabled accounts for the last-administrator safety guard."""
    return int(
        session.scalar(
            select(func.count()).select_from(Admin).where(Admin.is_active.is_(True))
        )
    )


def revoke_admin_sessions(session: Session, admin_id: int) -> None:
    """Revoke active sessions without retaining raw credentials or tokens."""
    session.execute(
        update(AdminSession)
        .where(AdminSession.admin_id == admin_id, AdminSession.revoked_at.is_(None))
        .values(revoked_at=utc_now())
    )


def login_admin(
    session: Session, username: str, password: str, session_hours: int
) -> tuple[str, AdminSession, Admin]:
    """Verify credentials and create one bearer session shared by both clients."""
    admin = session.scalar(select(Admin).where(Admin.username == username.strip()))
    if admin is None:
        verify_invalid_password(password)
        raise ApiError(401, "ADMIN_LOGIN_FAILED", "账号或密码错误")
    if not admin.is_active or not verify_password(password, admin.password_hash):
        raise ApiError(401, "ADMIN_LOGIN_FAILED", "账号或密码错误")
    token = new_token()
    expires_at = utc_now() + timedelta(hours=session_hours)
    admin_session = AdminSession(
        admin_id=admin.id, token_hash=hash_token(token), expires_at=expires_at
    )
    session.add(admin_session)
    session.commit()
    return token, admin_session, admin


def authenticated_admin(session: Session, token: str) -> tuple[Admin, AdminSession]:
    """Return a currently enabled administrator for a supplied bearer token."""
    now = utc_now()
    row = session.execute(
        select(Admin, AdminSession)
        .join(AdminSession, AdminSession.admin_id == Admin.id)
        .where(
            AdminSession.token_hash == hash_token(token),
            AdminSession.revoked_at.is_(None),
            AdminSession.expires_at > now,
            Admin.is_active.is_(True),
        )
    ).one_or_none()
    if row is None:
        raise ApiError(401, "ADMIN_SESSION_INVALID", "管理员登录已失效")
    return row[0], row[1]


def logout_admin(session: Session, token: str) -> None:
    """Revoke exactly the supplied valid session."""
    _, admin_session = authenticated_admin(session, token)
    admin_session.revoked_at = utc_now()
    session.commit()
