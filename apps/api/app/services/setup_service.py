"""First-run setup (FR-7.9).

A freshly installed stack has an empty database and no way in: the demo seed is
opt-in and there are no default credentials. This module turns that empty state
into the only moment the API accepts an unauthenticated write — creating the
household, its first OWNER and that owner's entity — and closes the door
permanently as soon as one user exists.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.core import audit
from app.core.errors import Conflict
from app.core.security import hash_password
from app.models.household import Entity, Household, HouseholdMember, User
from app.schemas.setup import SetupRequest
from app.services import household_service, settings_service


def needs_setup(db: DbSession) -> bool:
    """True while the installation has never had a user."""
    return not db.scalar(select(func.count()).select_from(User).where(User.is_deleted.is_(False)))


def bootstrap(db: DbSession, payload: SetupRequest) -> User:
    # Checked again inside the transaction: the status probe is advisory only.
    if not needs_setup(db):
        raise Conflict("Esta instalação já está configurada. Inicie sessão.")

    household = db.scalar(select(Household).limit(1))
    if household is None:
        household = Household(name=payload.household_name.strip())
        db.add(household)
        db.flush()

    user = User(
        email=str(payload.email).strip().lower(),
        display_name=payload.display_name.strip(),
        password_hash=hash_password(payload.password),
        role="OWNER",
        is_dependent=False,
        # The person is choosing the password right now — nothing to rotate.
        must_change_password=False,
    )
    db.add(user)
    db.flush()

    household.created_by = user.id
    db.add(HouseholdMember(household_id=household.id, user_id=user.id, role="OWNER"))

    # FR-7.7: every user gets a single-member entity, the first owner included.
    db.add(
        Entity(
            household_id=household.id,
            name=user.display_name,
            member_ids=[user.id],
            color=household_service.ENTITY_PALETTE[0],
        )
    )

    for key, value in settings_service.DEFAULTS.items():
        settings_service.set_value(db, key, value)

    db.flush()
    audit.record(
        db,
        action="CREATE",
        table_name="users",
        record_id=user.id,
        actor_user_id=user.id,
        after=audit.snapshot(user, ["id", "email", "display_name", "role"]),
    )
    return user
