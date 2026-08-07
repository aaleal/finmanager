"""Module 7 service layer — members, entities and the guards around them."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.core import audit
from app.core.errors import Conflict, NotFound, ValidationError
from app.core.security import hash_password
from app.models.household import Entity, Household, HouseholdMember, User
from app.schemas.household import (
    EntityCreate,
    EntityOut,
    EntityUpdate,
    MemberCreate,
    MemberOut,
    MemberUpdate,
)
from app.services import auth

ENTITY_PALETTE = ["#2563eb", "#0d9488", "#c026d3", "#ea580c", "#65a30d", "#7c3aed"]


# --- Members -----------------------------------------------------------------
def list_members(db: DbSession, household_id: uuid.UUID) -> list[MemberOut]:
    rows = db.scalars(
        select(HouseholdMember)
        .where(HouseholdMember.household_id == household_id)
        .order_by(HouseholdMember.joined_at)
    ).all()
    return [
        MemberOut(
            id=m.id,
            user_id=m.user_id,
            role=m.role,
            joined_at=m.joined_at,
            left_at=m.left_at,
            display_name=m.user.display_name,
            email=m.user.email,
            is_dependent=m.user.is_dependent,
            is_active=m.left_at is None and not m.user.is_deleted,
        )
        for m in rows
    ]


def _active_owner_count(db: DbSession, household_id: uuid.UUID) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(HouseholdMember)
            .where(
                HouseholdMember.household_id == household_id,
                HouseholdMember.role == "OWNER",
                HouseholdMember.left_at.is_(None),
            )
        )
        or 0
    )


def create_member(
    db: DbSession,
    household: Household,
    payload: MemberCreate,
    *,
    actor_user_id: uuid.UUID,
) -> HouseholdMember:
    if payload.is_dependent:
        if payload.temporary_password:
            raise ValidationError("Um dependente não tem palavra-passe.")
        email = None
        password_hash = None
        role = "VIEWER"
    else:
        if not payload.email:
            raise ValidationError("Indique um email para um membro com acesso.")
        if not payload.temporary_password:
            raise ValidationError("Indique uma palavra-passe temporária.")
        email = str(payload.email).strip().lower()
        if db.scalar(select(User).where(User.email == email)):
            raise Conflict("Já existe um utilizador com este email.")
        password_hash = hash_password(payload.temporary_password)
        role = payload.role

    user = User(
        email=email,
        display_name=payload.display_name.strip(),
        password_hash=password_hash,
        role=role,
        is_dependent=payload.is_dependent,
        must_change_password=not payload.is_dependent,
    )
    db.add(user)
    db.flush()

    member = HouseholdMember(household_id=household.id, user_id=user.id, role=role)
    db.add(member)
    db.flush()

    # FR-7.7: one single-member entity per new user, created automatically.
    entity_count = (
        db.scalar(
            select(func.count()).select_from(Entity).where(Entity.household_id == household.id)
        )
        or 0
    )
    entity = Entity(
        household_id=household.id,
        name=user.display_name,
        member_ids=[user.id],
        color=ENTITY_PALETTE[entity_count % len(ENTITY_PALETTE)],
    )
    db.add(entity)
    db.flush()

    audit.record(
        db,
        action="CREATE",
        table_name="users",
        record_id=user.id,
        actor_user_id=actor_user_id,
        after=audit.snapshot(user, ["id", "email", "display_name", "role", "is_dependent"]),
    )
    return member


def update_member(
    db: DbSession,
    member: HouseholdMember,
    payload: MemberUpdate,
    *,
    actor_user_id: uuid.UUID,
) -> HouseholdMember:
    user = member.user
    before = audit.snapshot(user, ["email", "display_name", "role", "is_dependent"])
    changes = payload.model_dump(exclude_unset=True)

    if "role" in changes and changes["role"] is not None:
        demoting_last_owner = (
            member.role == "OWNER"
            and changes["role"] != "OWNER"
            and _active_owner_count(db, member.household_id) <= 1
        )
        if demoting_last_owner:
            raise Conflict("O agregado tem de manter pelo menos um titular (OWNER).")
        member.role = changes["role"]
        user.role = changes["role"]

    if changes.get("display_name"):
        user.display_name = changes["display_name"].strip()

    if "email" in changes and changes["email"] is not None:
        email = str(changes["email"]).strip().lower()
        clash = db.scalar(select(User).where(User.email == email, User.id != user.id))
        if clash is not None:
            raise Conflict("Já existe um utilizador com este email.")
        user.email = email

    if "is_dependent" in changes and changes["is_dependent"] is not None:
        # A child ageing into login keeps their entity and history (M7 edge cases).
        user.is_dependent = changes["is_dependent"]
        if user.is_dependent:
            user.password_hash = None
            auth.revoke_all_for_user(db, user.id)

    if changes.get("new_password"):
        if user.is_dependent:
            raise ValidationError("Um dependente não tem palavra-passe.")
        user.password_hash = hash_password(changes["new_password"])
        user.must_change_password = True
        auth.revoke_all_for_user(db, user.id)

    db.flush()
    audit.record(
        db,
        action="UPDATE",
        table_name="users",
        record_id=user.id,
        actor_user_id=actor_user_id,
        before=before,
        after=audit.snapshot(user, ["email", "display_name", "role", "is_dependent"]),
    )
    return member


def remove_member(db: DbSession, member: HouseholdMember, *, actor_user_id: uuid.UUID) -> None:
    if member.role == "OWNER" and _active_owner_count(db, member.household_id) <= 1:
        raise Conflict("O agregado tem de manter pelo menos um titular (OWNER).")

    member.left_at = dt.datetime.now(dt.UTC)
    member.user.is_deleted = True
    member.user.deleted_at = dt.datetime.now(dt.UTC)
    auth.revoke_all_for_user(db, member.user_id)

    # FR-7.6: entities where they were the only member become read-only.
    entities = db.scalars(
        select(Entity).where(
            Entity.household_id == member.household_id, Entity.is_deleted.is_(False)
        )
    ).all()
    for entity in entities:
        if entity.member_ids == [member.user_id]:
            entity.is_readonly = True

    db.flush()
    audit.record(
        db,
        action="DELETE",
        table_name="household_members",
        record_id=member.id,
        actor_user_id=actor_user_id,
        before=audit.snapshot(member, ["household_id", "user_id", "role"]),
        reason="member departure",
    )


# --- Entities ----------------------------------------------------------------
def list_entities(db: DbSession, household_id: uuid.UUID) -> list[EntityOut]:
    rows = db.scalars(
        select(Entity)
        .where(Entity.household_id == household_id, Entity.is_deleted.is_(False))
        .order_by(Entity.created_at)
    ).all()
    return [EntityOut.model_validate(row) for row in rows]


def get_entity(db: DbSession, household_id: uuid.UUID, entity_id: uuid.UUID) -> Entity:
    entity = db.get(Entity, entity_id)
    if entity is None or entity.is_deleted or entity.household_id != household_id:
        raise NotFound("Entidade não encontrada.")
    return entity


def create_entity(
    db: DbSession,
    household: Household,
    payload: EntityCreate,
    *,
    actor_user_id: uuid.UUID,
) -> Entity:
    if db.scalar(
        select(Entity).where(
            Entity.household_id == household.id,
            Entity.name == payload.name.strip(),
            Entity.is_deleted.is_(False),
        )
    ):
        raise Conflict("Já existe uma entidade com este nome.")

    known = set(
        db.scalars(
            select(HouseholdMember.user_id).where(HouseholdMember.household_id == household.id)
        ).all()
    )
    unknown = [str(m) for m in payload.member_ids if m not in known]
    if unknown:
        raise ValidationError(f"Membros desconhecidos: {', '.join(unknown)}")

    count = (
        db.scalar(
            select(func.count()).select_from(Entity).where(Entity.household_id == household.id)
        )
        or 0
    )
    entity = Entity(
        household_id=household.id,
        name=payload.name.strip(),
        member_ids=list(payload.member_ids),
        color=payload.color or ENTITY_PALETTE[count % len(ENTITY_PALETTE)],
    )
    db.add(entity)
    db.flush()
    audit.record(
        db,
        action="CREATE",
        table_name="entities",
        record_id=entity.id,
        entity_id=entity.id,
        actor_user_id=actor_user_id,
        after=audit.snapshot(entity),
    )
    return entity


def update_entity(
    db: DbSession, entity: Entity, payload: EntityUpdate, *, actor_user_id: uuid.UUID
) -> Entity:
    before = audit.snapshot(entity)
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("name"):
        entity.name = changes["name"].strip()
    if changes.get("member_ids") is not None:
        if not changes["member_ids"]:
            raise ValidationError("Uma entidade tem de ter pelo menos um membro.")
        entity.member_ids = list(changes["member_ids"])
    if "color" in changes:
        entity.color = changes["color"]

    db.flush()
    audit.record(
        db,
        action="UPDATE",
        table_name="entities",
        record_id=entity.id,
        entity_id=entity.id,
        actor_user_id=actor_user_id,
        before=before,
        after=audit.snapshot(entity),
    )
    return entity
