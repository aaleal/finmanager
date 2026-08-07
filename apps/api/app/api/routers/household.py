from __future__ import annotations

import uuid

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentAuth, Db, Owner, Writer, current_household
from app.core.errors import NotFound
from app.models.household import HouseholdMember
from app.schemas.common import Ok
from app.schemas.household import (
    EntityCreate,
    EntityOut,
    EntitySwitch,
    EntitySwitchResult,
    EntityUpdate,
    MemberCreate,
    MemberOut,
    MemberUpdate,
)
from app.services import auth, household_service

router = APIRouter(tags=["household"])


# --- Members -----------------------------------------------------------------
@router.get("/members", response_model=list[MemberOut])
def list_members(ctx: CurrentAuth, db: Db) -> list[MemberOut]:
    return household_service.list_members(db, ctx.household_id)


@router.post("/members", response_model=MemberOut, status_code=201)
def create_member(payload: MemberCreate, ctx: Owner, db: Db) -> MemberOut:
    household = current_household(db, ctx)
    member = household_service.create_member(db, household, payload, actor_user_id=ctx.user.id)
    db.flush()
    return _member_out(db, ctx.household_id, member.id)


@router.patch("/members/{member_id}", response_model=MemberOut)
def update_member(member_id: uuid.UUID, payload: MemberUpdate, ctx: Owner, db: Db) -> MemberOut:
    member = _get_member(db, ctx.household_id, member_id)
    household_service.update_member(db, member, payload, actor_user_id=ctx.user.id)
    return _member_out(db, ctx.household_id, member_id)


@router.delete("/members/{member_id}", response_model=Ok)
def remove_member(member_id: uuid.UUID, ctx: Owner, db: Db) -> Ok:
    member = _get_member(db, ctx.household_id, member_id)
    household_service.remove_member(db, member, actor_user_id=ctx.user.id)
    return Ok(message="Membro removido.")


def _get_member(db: Db, household_id: uuid.UUID, member_id: uuid.UUID) -> HouseholdMember:
    member = db.scalar(
        select(HouseholdMember).where(
            HouseholdMember.id == member_id, HouseholdMember.household_id == household_id
        )
    )
    if member is None:
        raise NotFound("Membro não encontrado.")
    return member


def _member_out(db: Db, household_id: uuid.UUID, member_id: uuid.UUID) -> MemberOut:
    for row in household_service.list_members(db, household_id):
        if row.id == member_id:
            return row
    raise NotFound("Membro não encontrado.")


# --- Entities ----------------------------------------------------------------
@router.get("/entities", response_model=list[EntityOut])
def list_entities(ctx: CurrentAuth, db: Db) -> list[EntityOut]:
    return household_service.list_entities(db, ctx.household_id)


@router.post("/entities", response_model=EntityOut, status_code=201)
def create_entity(payload: EntityCreate, ctx: Owner, db: Db) -> EntityOut:
    household = current_household(db, ctx)
    entity = household_service.create_entity(db, household, payload, actor_user_id=ctx.user.id)
    return EntityOut.model_validate(entity)


@router.patch("/entities/{entity_id}", response_model=EntityOut)
def update_entity(entity_id: uuid.UUID, payload: EntityUpdate, ctx: Writer, db: Db) -> EntityOut:
    entity = household_service.get_entity(db, ctx.household_id, entity_id)
    household_service.update_entity(db, entity, payload, actor_user_id=ctx.user.id)
    return EntityOut.model_validate(entity)


# --- Active entity selector --------------------------------------------------
@router.post("/sessions/entity", response_model=EntitySwitchResult)
def switch_entity(payload: EntitySwitch, ctx: CurrentAuth, db: Db) -> EntitySwitchResult:
    if payload.entity_id is not None:
        household_service.get_entity(db, ctx.household_id, payload.entity_id)
    csrf_token = auth.set_active_entity(db, ctx.session, payload.entity_id)
    return EntitySwitchResult(active_entity_id=payload.entity_id, csrf_token=csrf_token)
