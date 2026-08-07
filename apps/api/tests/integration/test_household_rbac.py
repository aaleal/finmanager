"""Protects: M7 Definition of Done — «RBAC middleware enforced on every endpoint:
writes require OWNER/MEMBER, VIEWER is read-only» and «Last-OWNER safeguard».
"""

from __future__ import annotations

import pytest
from app.api.deps import AuthContext, require_owner, require_write, resolve_write_entity
from app.core.errors import Conflict, Forbidden
from app.core.security import hash_password
from app.models import Entity, Household, HouseholdMember, User
from app.models.household import Session as SessionRow
from app.schemas.household import MemberUpdate
from app.services import household_service
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


def _context(user: User, role: str, household: Household, entity_id=None) -> AuthContext:
    return AuthContext(
        user=user,
        session=SessionRow(  # not persisted; only the shape matters for the guard
            token_hash="x",
            csrf_token="y",
            user_id=user.id,
            expires_at=None,  # type: ignore[arg-type]
        ),
        role=role,
        household_id=household.id,
        active_entity_id=entity_id,
    )


def test_viewer_cannot_write_but_owner_and_member_can(
    db: Session, household: Household, owner: User
) -> None:
    viewer_ctx = _context(owner, "VIEWER", household)
    with pytest.raises(Forbidden):
        require_write(viewer_ctx)

    assert require_write(_context(owner, "MEMBER", household)).can_write is True
    assert require_write(_context(owner, "OWNER", household)).can_write is True


def test_only_owner_passes_the_owner_gate(db: Session, household: Household, owner: User) -> None:
    with pytest.raises(Forbidden):
        require_owner(_context(owner, "MEMBER", household))
    assert require_owner(_context(owner, "OWNER", household)).is_owner is True


def test_writing_with_the_selector_on_todas_is_refused_not_guessed(
    db: Session, household: Household, owner: User, entity: Entity
) -> None:
    ctx = _context(owner, "OWNER", household, entity_id=None)
    with pytest.raises(Forbidden):
        resolve_write_entity(db, ctx, None)

    assert resolve_write_entity(db, ctx, entity.id) == entity.id


def test_readonly_entity_refuses_new_records(
    db: Session, household: Household, owner: User, entity: Entity
) -> None:
    entity.is_readonly = True
    db.flush()
    ctx = _context(owner, "OWNER", household, entity_id=entity.id)
    with pytest.raises(Forbidden):
        resolve_write_entity(db, ctx, entity.id)


def test_the_last_owner_cannot_be_demoted_or_removed(
    db: Session, household: Household, owner: User
) -> None:
    membership = db.query(HouseholdMember).filter(HouseholdMember.user_id == owner.id).one()

    with pytest.raises(Conflict):
        household_service.update_member(
            db, membership, MemberUpdate(role="MEMBER"), actor_user_id=owner.id
        )
    with pytest.raises(Conflict):
        household_service.remove_member(db, membership, actor_user_id=owner.id)


def test_a_second_owner_unblocks_demotion(db: Session, household: Household, owner: User) -> None:
    other = User(
        email="bruno@finmanager.local",
        display_name="Bruno",
        password_hash=hash_password("finmanager"),
        role="OWNER",
    )
    db.add(other)
    db.flush()
    db.add(HouseholdMember(household_id=household.id, user_id=other.id, role="OWNER"))
    db.flush()

    membership = db.query(HouseholdMember).filter(HouseholdMember.user_id == owner.id).one()
    household_service.update_member(
        db, membership, MemberUpdate(role="MEMBER"), actor_user_id=owner.id
    )
    assert membership.role == "MEMBER"


def test_departure_flips_a_sole_member_entity_to_readonly(
    db: Session, household: Household, owner: User, entity: Entity
) -> None:
    other = User(
        email="bruno@finmanager.local",
        display_name="Bruno",
        password_hash=hash_password("finmanager"),
        role="OWNER",
    )
    db.add(other)
    db.flush()
    db.add(HouseholdMember(household_id=household.id, user_id=other.id, role="OWNER"))
    joint = Entity(household_id=household.id, name="Ana & Bruno", member_ids=[owner.id, other.id])
    db.add(joint)
    db.flush()

    membership = db.query(HouseholdMember).filter(HouseholdMember.user_id == owner.id).one()
    household_service.remove_member(db, membership, actor_user_id=other.id)

    assert entity.is_readonly is True  # sole-member entity
    assert joint.is_readonly is False  # multi-member entity keeps working
