"""Request-scoped auth context and the single RBAC gate (FR-7.3).

Entity is an attribution/filter dimension, not a permission boundary: every
authenticated household member reads everything. Roles govern write power only.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.core.db import get_db
from app.core.errors import Forbidden, Unauthorized
from app.core.security import constant_time_equals
from app.models.household import Entity, Household, HouseholdMember, Role, Session, User
from app.services import auth

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@dataclass(slots=True)
class AuthContext:
    user: User
    session: Session
    role: Role
    household_id: uuid.UUID
    active_entity_id: uuid.UUID | None

    @property
    def can_write(self) -> bool:
        return self.role in ("OWNER", "MEMBER")

    @property
    def is_owner(self) -> bool:
        return self.role == "OWNER"


def get_auth(
    request: Request,
    db: Annotated[DbSession, Depends(get_db)],
) -> AuthContext:
    token = request.cookies.get(auth.SESSION_COOKIE)
    if not token:
        raise Unauthorized()

    session = auth.resolve_session(db, token)

    if request.method not in SAFE_METHODS:
        supplied = request.headers.get(auth.CSRF_HEADER, "")
        if not supplied or not constant_time_equals(supplied, session.csrf_token):
            raise Forbidden("Token CSRF em falta ou inválido.")

    user = db.get(User, session.user_id)
    if user is None or user.is_deleted:
        raise Unauthorized()

    membership = db.scalar(
        select(HouseholdMember).where(
            HouseholdMember.user_id == user.id, HouseholdMember.left_at.is_(None)
        )
    )
    if membership is None:
        raise Unauthorized("Já não pertence a este agregado.")

    return AuthContext(
        user=user,
        session=session,
        role=membership.role,
        household_id=membership.household_id,
        active_entity_id=session.entity_id,
    )


CurrentAuth = Annotated[AuthContext, Depends(get_auth)]
Db = Annotated[DbSession, Depends(get_db)]


def require_write(ctx: CurrentAuth) -> AuthContext:
    if not ctx.can_write:
        raise Forbidden("A sua função é apenas de leitura.")
    return ctx


def require_owner(ctx: CurrentAuth) -> AuthContext:
    if not ctx.is_owner:
        raise Forbidden("Apenas o titular do agregado pode executar esta operação.")
    return ctx


Writer = Annotated[AuthContext, Depends(require_write)]
Owner = Annotated[AuthContext, Depends(require_owner)]


def current_household(db: DbSession, ctx: AuthContext) -> Household:
    household = db.get(Household, ctx.household_id)
    if household is None:  # pragma: no cover - referential integrity guarantees this
        raise Unauthorized()
    return household


def resolve_write_entity(db: DbSession, ctx: AuthContext, entity_id: uuid.UUID | None) -> uuid.UUID:
    """Pick the entity a new record is attributed to.

    Explicit ``entity_id`` wins; otherwise the active selector value; otherwise the
    write is ambiguous and must be refused rather than guessed.
    """
    target = entity_id or ctx.active_entity_id
    if target is None:
        raise Forbidden(
            "Selecione uma entidade específica (não «todas») antes de criar um registo."
        )
    entity = db.get(Entity, target)
    if entity is None or entity.is_deleted or entity.household_id != ctx.household_id:
        raise Forbidden("Entidade desconhecida.")
    if entity.is_readonly:
        raise Forbidden("Esta entidade está em modo de leitura.")
    return entity.id


def household_entity_ids(db: DbSession, ctx: AuthContext) -> list[uuid.UUID]:
    return list(
        db.scalars(
            select(Entity.id).where(
                Entity.household_id == ctx.household_id, Entity.is_deleted.is_(False)
            )
        ).all()
    )
