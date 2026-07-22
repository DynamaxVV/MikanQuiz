"""Password and opaque token helpers."""

from hashlib import sha256
import secrets

from pwdlib import PasswordHash


_PASSWORD_HASH = PasswordHash.recommended()
_DUMMY_HASH = _PASSWORD_HASH.hash("unused-invalid-password")


def hash_password(password: str) -> str:
    """Return the configured Argon2 password hash for a new credential."""
    return _PASSWORD_HASH.hash(password)


def verify_password(password: str, encoded_hash: str) -> bool:
    """Verify a password without returning or logging its hash."""
    return _PASSWORD_HASH.verify(password, encoded_hash)


def verify_invalid_password(password: str) -> None:
    """Spend comparable work for a nonexistent username to reduce enumeration."""
    _PASSWORD_HASH.verify(password, _DUMMY_HASH)


def new_token() -> str:
    """Return a high-entropy URL-safe bearer token for client-side storage."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Return a fixed SHA-256 digest so database rows never hold raw tokens."""
    return sha256(token.encode("utf-8")).hexdigest()
