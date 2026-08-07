"""Password hashing and signed, time-limited document URLs."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from uuid import UUID

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import settings

_hasher = PasswordHasher()


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    try:
        return _hasher.verify(hashed, plain)
    except (VerifyMismatchError, InvalidHashError, ValueError):
        return False


def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


# --- Signed document URLs ----------------------------------------------------
# Attachments live outside any web root and are only ever reachable through a
# short-lived HMAC signature (§1a Document, OWASP rubric).


def sign_document(document_id: UUID, ttl_minutes: int | None = None) -> tuple[str, int]:
    ttl = ttl_minutes if ttl_minutes is not None else settings.document_url_ttl_minutes
    expires_at = int(time.time()) + ttl * 60
    payload = f"{document_id}:{expires_at}".encode()
    digest = hmac.new(settings.secret_key.encode(), payload, hashlib.sha256).digest()
    signature = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return signature, expires_at


def verify_document_signature(document_id: UUID, expires_at: int, signature: str) -> bool:
    if expires_at < int(time.time()):
        return False
    payload = f"{document_id}:{expires_at}".encode()
    digest = hmac.new(settings.secret_key.encode(), payload, hashlib.sha256).digest()
    expected = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return hmac.compare_digest(expected, signature)


def signed_document_url(document_id: UUID) -> str:
    signature, expires_at = sign_document(document_id)
    return f"/api/documents/{document_id}/content?expires={expires_at}&signature={signature}"
