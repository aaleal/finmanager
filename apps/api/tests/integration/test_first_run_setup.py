"""Protects: M10 — first-run setup on a clean installation.

The load-bearing property is that this is the *only* unauthenticated write in the
API and that it closes permanently. A regression here either locks a fresh NAS
out of its own installation, or leaves a live household open to a stranger
creating a second owner.
"""

from __future__ import annotations

import pytest
from app.core.redis_client import get_redis
from app.models import Entity, Household, HouseholdMember, User
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

PAYLOAD = {
    "household_name": "Casa dos Testes",
    "display_name": "Ana",
    "email": "Ana@Exemplo.PT",
    "password": "uma-palavra-passe-longa",
}


@pytest.fixture(autouse=True)
def _reset_rate_limit() -> None:
    """The limiter lives in Redis, which outlives the database fixture."""
    for key in get_redis().scan_iter("ratelimit:/api/setup*"):
        get_redis().delete(key)


def test_a_clean_install_reports_that_it_needs_setup(api_client: TestClient) -> None:
    assert api_client.get("/api/setup/status").json() == {"needs_setup": True}


def test_setup_creates_household_owner_and_entity_then_signs_in(
    api_client: TestClient, db: Session
) -> None:
    response = api_client.post("/api/setup", json=PAYLOAD)
    assert response.status_code == 201

    body = response.json()
    assert body["role"] == "OWNER"
    assert body["household_name"] == "Casa dos Testes"
    assert body["user"]["email"] == "ana@exemplo.pt"
    # Nothing to rotate: the owner chose this password seconds ago.
    assert body["user"]["must_change_password"] is False
    assert "fm_session" in response.cookies

    user = db.scalar(select(User).where(User.email == "ana@exemplo.pt"))
    assert user is not None and user.password_hash and user.password_hash != PAYLOAD["password"]
    assert db.scalar(select(func.count()).select_from(Household)) == 1
    assert db.scalar(select(func.count()).select_from(HouseholdMember)) == 1
    # FR-7.7: the first owner gets their single-member entity like everybody else.
    entity = db.scalar(select(Entity))
    assert entity is not None and entity.member_ids == [user.id]

    # The session that came back is immediately usable.
    assert api_client.get("/api/auth/me").json()["user"]["display_name"] == "Ana"


def test_setup_closes_itself_once_a_user_exists(api_client: TestClient) -> None:
    assert api_client.post("/api/setup", json=PAYLOAD).status_code == 201
    assert api_client.get("/api/setup/status").json() == {"needs_setup": False}

    again = api_client.post("/api/setup", json={**PAYLOAD, "email": "intruso@exemplo.pt"})
    assert again.status_code == 409


def test_setup_refuses_a_short_password(api_client: TestClient) -> None:
    response = api_client.post("/api/setup", json={**PAYLOAD, "password": "curta"})
    assert response.status_code == 422
