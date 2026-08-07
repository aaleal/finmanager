"""Authentication and server-side sessions (FR-7.8).

The `sessions` row is authoritative; Redis is a read-through cache so the hot
path (every request) does not hit Postgres. Logout, password change and member
departure all invalidate both.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session as DbSession

from app.core.config import settings
from app.core.errors import Unauthorized
from app.core.redis_client import get_redis
from app.core.security import hash_password, new_token, verify_password
from app.models.household import Entity, HouseholdMember, Session, User

SESSION_COOKIE = "fm_session"
CSRF_HEADER = "X-CSRF-Token"
_CACHE_PREFIX = "session:"


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _cache_key(token_hash: str) -> str:
    return f"{_CACHE_PREFIX}{token_hash}"


def authenticate(db: DbSession, email: str, password: str) -> User:
    user = db.scalar(
        select(User).where(
            User.email == email.strip().lower(),
            User.is_deleted.is_(False),
            User.is_dependent.is_(False),
        )
    )
    if user is None or not verify_password(password, user.password_hash):
        # Same message for both cases — no account enumeration.
        raise Unauthorized("Credenciais inválidas.")

    membership = db.scalar(
        select(HouseholdMember).where(
            HouseholdMember.user_id == user.id, HouseholdMember.left_at.is_(None)
        )
    )
    if membership is None:
        raise Unauthorized("Credenciais inválidas.")
    return user


def create_session(db: DbSession, user: User) -> tuple[Session, str]:
    """Returns the row and the raw cookie token (only ever seen here and by the client)."""
    token = new_token()
    last = db.scalar(
        select(Session)
        .where(Session.user_id == user.id)
        .order_by(Session.created_at.desc())
        .limit(1)
    )
    row = Session(
        token_hash=_hash_token(token),
        csrf_token=new_token(24),
        user_id=user.id,
        entity_id=last.entity_id if last else None,  # FR-7.2: last selection wins
        expires_at=dt.datetime.now(dt.UTC) + dt.timedelta(days=settings.session_ttl_days),
    )
    db.add(row)
    db.flush()
    _cache(row)
    return row, token


def _cache(row: Session) -> None:
    ttl = int((row.expires_at - dt.datetime.now(dt.UTC)).total_seconds())
    if ttl <= 0:
        return
    get_redis().hset(
        _cache_key(row.token_hash),
        mapping={
            "session_id": str(row.id),
            "user_id": str(row.user_id),
            "csrf_token": row.csrf_token,
            "entity_id": str(row.entity_id) if row.entity_id else "",
        },
    )
    get_redis().expire(_cache_key(row.token_hash), ttl)


def _uncache(token_hash: str) -> None:
    get_redis().delete(_cache_key(token_hash))


def resolve_session(db: DbSession, token: str) -> Session:
    token_hash = _hash_token(token)
    row = db.scalar(select(Session).where(Session.token_hash == token_hash))
    now = dt.datetime.now(dt.UTC)
    if row is None or row.revoked_at is not None or row.expires_at <= now:
        raise Unauthorized()

    # Sliding expiry: extend at most once a day to avoid a write per request.
    if row.expires_at - now < dt.timedelta(days=settings.session_ttl_days - 1):
        row.expires_at = now + dt.timedelta(days=settings.session_ttl_days)
        _cache(row)
    return row


def revoke_session(db: DbSession, row: Session) -> None:
    row.revoked_at = dt.datetime.now(dt.UTC)
    _uncache(row.token_hash)


def revoke_all_for_user(db: DbSession, user_id: uuid.UUID) -> None:
    rows = db.scalars(
        select(Session).where(Session.user_id == user_id, Session.revoked_at.is_(None))
    ).all()
    for row in rows:
        row.revoked_at = dt.datetime.now(dt.UTC)
        _uncache(row.token_hash)


def set_active_entity(db: DbSession, row: Session, entity_id: uuid.UUID | None) -> str:
    """Switch the "viewing as" filter and rotate the CSRF token."""
    if entity_id is not None:
        entity = db.get(Entity, entity_id)
        if entity is None or entity.is_deleted:
            raise Unauthorized("Entidade desconhecida.")
    row.entity_id = entity_id
    row.csrf_token = new_token(24)
    # Persist the choice for every future session of this user (FR-7.2).
    db.execute(
        update(Session)
        .where(Session.user_id == row.user_id, Session.revoked_at.is_(None))
        .values(entity_id=entity_id)
    )
    _cache(row)
    return row.csrf_token


def change_password(db: DbSession, user: User, new_plain: str) -> None:
    user.password_hash = hash_password(new_plain)
    user.must_change_password = False
    revoke_all_for_user(db, user.id)
