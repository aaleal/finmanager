"""Protects: an entities archive recreates, by name, whatever this household
does not already have — the prerequisite step that lets every other module's
archive (LEGO's own resolves a row's owning entity by name) resolve cleanly on
a fresh installation.
"""

from __future__ import annotations

import io
import json
import zipfile

import pytest
from app.core.errors import ValidationError
from app.models import Entity, Household, User
from app.services import entity_backup
from sqlalchemy import select
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


def test_the_archive_carries_name_colour_and_a_members_reference(
    db: Session, entity: Entity, owner: User
) -> None:
    entity.color = "#336699"
    db.flush()

    payload = entity_backup.build_archive(db, [entity.id])

    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        manifest = json.loads(archive.read(entity_backup.MANIFEST_NAME))
        body = json.loads(archive.read(entity_backup.COLLECTION_NAME))

    assert manifest["format"] == entity_backup.FORMAT
    assert manifest["counts"]["entities"] == 1
    assert body["entities"] == [
        {
            "name": "Ana",
            "color": "#336699",
            "members": [{"display_name": owner.display_name, "email": owner.email}],
        }
    ]


def test_restoring_creates_a_missing_entity_by_name(
    db: Session, household: Household, entity: Entity, owner: User
) -> None:
    payload = entity_backup.build_archive(db, [entity.id])

    other_household = Household(name="Outra casa")
    db.add(other_household)
    db.flush()

    report = entity_backup.restore_archive(
        db, payload, household_id=other_household.id, actor_user_id=owner.id
    )

    assert (report.entities, report.skipped_entities) == (1, 0)
    created = db.scalar(
        select(Entity).where(Entity.household_id == other_household.id, Entity.name == "Ana")
    )
    assert created is not None
    assert created.member_ids == []


def test_restoring_never_creates_a_user_or_a_password(
    db: Session, household: Household, entity: Entity, owner: User
) -> None:
    """The members reference is read-only (ADR-0011, ADR-0014): a restore, which
    only requires Writer, must never be a way to grant anyone a login."""
    payload = entity_backup.build_archive(db, [entity.id])
    users_before = set(db.scalars(select(User.id)).all())

    other_household = Household(name="Outra casa")
    db.add(other_household)
    db.flush()

    entity_backup.restore_archive(
        db, payload, household_id=other_household.id, actor_user_id=owner.id
    )

    assert set(db.scalars(select(User.id)).all()) == users_before


def test_restoring_the_same_archive_twice_skips_the_second_time(
    db: Session, household: Household, entity: Entity, owner: User
) -> None:
    payload = entity_backup.build_archive(db, [entity.id])

    report = entity_backup.restore_archive(
        db, payload, household_id=household.id, actor_user_id=owner.id
    )

    # "Ana" already exists in this household — matched, not duplicated.
    assert (report.entities, report.skipped_entities) == (0, 1)
    assert (
        db.scalar(
            select(Entity.id).where(Entity.household_id == household.id, Entity.name == "Ana")
        )
        == entity.id
    )


def test_a_foreign_archive_is_refused(db: Session, entity: Entity, owner: User) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(entity_backup.MANIFEST_NAME, json.dumps({"format": "outra.coisa"}))

    with pytest.raises(ValidationError):
        entity_backup.restore_archive(
            db, buffer.getvalue(), household_id=entity.household_id, actor_user_id=owner.id
        )


def test_something_that_is_not_a_zip_is_refused(db: Session, entity: Entity, owner: User) -> None:
    with pytest.raises(ValidationError):
        entity_backup.restore_archive(
            db, b"nao sou um zip", household_id=entity.household_id, actor_user_id=owner.id
        )
