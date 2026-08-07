from __future__ import annotations

from fastapi import APIRouter, Response
from sqlalchemy import select

from app.api.deps import CurrentAuth, Db
from app.core.config import settings
from app.core.errors import Unauthorized, ValidationError
from app.core.security import verify_password
from app.models.household import Household, HouseholdMember
from app.schemas.common import Ok
from app.schemas.household import (
    LoginRequest,
    PasswordChange,
    ProfileUpdate,
    SessionOut,
    UserOut,
)
from app.services import auth

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        auth.SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.session_ttl_days * 24 * 3600,
        path="/",
    )


@router.post("/login", response_model=SessionOut)
def login(payload: LoginRequest, response: Response, db: Db) -> SessionOut:
    user = auth.authenticate(db, payload.email, payload.password)
    session, token = auth.create_session(db, user)
    _set_session_cookie(response, token)

    membership = db.scalar(
        select(HouseholdMember).where(
            HouseholdMember.user_id == user.id, HouseholdMember.left_at.is_(None)
        )
    )
    household = db.get(Household, membership.household_id) if membership else None
    if membership is None or household is None:
        raise Unauthorized("Credenciais inválidas.")

    return SessionOut(
        user=UserOut.model_validate(user),
        household_id=household.id,
        household_name=household.name,
        role=membership.role,
        active_entity_id=session.entity_id,
        csrf_token=session.csrf_token,
        expires_at=session.expires_at,
    )


@router.post("/logout", response_model=Ok)
def logout(ctx: CurrentAuth, response: Response, db: Db) -> Ok:
    auth.revoke_session(db, ctx.session)
    response.delete_cookie(auth.SESSION_COOKIE, path="/")
    return Ok(message="Sessão terminada.")


@router.get("/me", response_model=SessionOut)
def me(ctx: CurrentAuth, db: Db) -> SessionOut:
    household = db.get(Household, ctx.household_id)
    if household is None:
        raise Unauthorized()
    return SessionOut(
        user=UserOut.model_validate(ctx.user),
        household_id=household.id,
        household_name=household.name,
        role=ctx.role,
        active_entity_id=ctx.active_entity_id,
        csrf_token=ctx.session.csrf_token,
        expires_at=ctx.session.expires_at,
    )


@router.post("/password", response_model=Ok)
def change_password(payload: PasswordChange, ctx: CurrentAuth, response: Response, db: Db) -> Ok:
    if not verify_password(payload.current_password, ctx.user.password_hash):
        raise Unauthorized("Palavra-passe atual incorreta.")
    if payload.current_password == payload.new_password:
        raise ValidationError("A nova palavra-passe tem de ser diferente da atual.")
    auth.change_password(db, ctx.user, payload.new_password)
    response.delete_cookie(auth.SESSION_COOKIE, path="/")
    return Ok(message="Palavra-passe alterada. Inicie sessão novamente.")


@router.patch("/profile", response_model=UserOut)
def update_profile(payload: ProfileUpdate, ctx: CurrentAuth, db: Db) -> UserOut:
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(ctx.user, field, value)
    db.flush()
    return UserOut.model_validate(ctx.user)
