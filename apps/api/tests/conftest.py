"""Shared pytest fixtures.

Integration tests run inside the api container against a dedicated
``finmanager_test`` database, created and torn down here.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from app.core.config import settings
from app.core.security import hash_password
from app.models import Base, Entity, Household, HouseholdMember, User
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

TEST_DB = "finmanager_test"


def _admin_url() -> str:
    return (
        f"postgresql+psycopg://{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/postgres"
    )


def _test_url() -> str:
    return (
        f"postgresql+psycopg://{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/{TEST_DB}"
    )


@pytest.fixture(scope="session")
def engine():  # type: ignore[no-untyped-def]
    admin = create_engine(_admin_url(), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)'))
        connection.execute(text(f'CREATE DATABASE "{TEST_DB}"'))
    admin.dispose()

    test_engine = create_engine(_test_url(), future=True)
    Base.metadata.create_all(test_engine)
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def db(engine) -> Iterator[Session]:  # type: ignore[no-untyped-def]
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    session = factory()
    try:
        yield session
        session.rollback()
    finally:
        # Leave a clean slate for the next test.
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(text(f'TRUNCATE TABLE "{table.name}" CASCADE'))
        session.commit()
        session.close()


@pytest.fixture
def household(db: Session) -> Household:
    row = Household(name="Casa de Teste")
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def owner(db: Session, household: Household) -> User:
    user = User(
        email="teste@finmanager.local",
        display_name="Ana",
        password_hash=hash_password("finmanager"),
        role="OWNER",
    )
    db.add(user)
    db.flush()
    db.add(HouseholdMember(household_id=household.id, user_id=user.id, role="OWNER"))
    db.flush()
    return user


@pytest.fixture
def entity(db: Session, household: Household, owner: User) -> Entity:
    row = Entity(household_id=household.id, name="Ana", member_ids=[owner.id])
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def api_client(engine, db: Session) -> Iterator[TestClient]:  # type: ignore[no-untyped-def]
    from app.core.db import get_db
    from app.main import app

    def override() -> Iterator[Session]:
        yield db

    app.dependency_overrides[get_db] = override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def actor_id() -> uuid.UUID:
    return uuid.uuid4()
