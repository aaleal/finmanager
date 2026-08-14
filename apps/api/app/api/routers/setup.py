"""First-run setup endpoints (FR-7.9).

The only unauthenticated write in the API, and only while the installation has
no users. Once the first OWNER exists both routes are inert: the probe reports
``needs_setup: false`` and the write returns 409.
"""

from __future__ import annotations

from fastapi import APIRouter, Response
from sqlalchemy import select

from app.api.deps import Db
from app.api.routers.auth import set_session_cookie
from app.models.household import Household, HouseholdMember
from app.schemas.household import SessionOut, UserOut
from app.schemas.setup import SetupRequest, SetupStatus
from app.services import auth, setup_service

router = APIRouter(prefix="/setup", tags=["setup"])


@router.get("/status", response_model=SetupStatus)
def status(db: Db) -> SetupStatus:
    return SetupStatus(needs_setup=setup_service.needs_setup(db))


@router.post("", response_model=SessionOut, status_code=201)
def create_first_owner(payload: SetupRequest, response: Response, db: Db) -> SessionOut:
    """Create the household and its first owner, then sign that owner straight in."""
    user = setup_service.bootstrap(db, payload)
    session, token = auth.create_session(db, user)
    set_session_cookie(response, token)

    membership = db.scalar(select(HouseholdMember).where(HouseholdMember.user_id == user.id))
    assert membership is not None  # just created above
    household = db.get(Household, membership.household_id)
    assert household is not None

    return SessionOut(
        user=UserOut.model_validate(user),
        household_id=household.id,
        household_name=household.name,
        role=membership.role,
        active_entity_id=session.entity_id,
        csrf_token=session.csrf_token,
        expires_at=session.expires_at,
    )
