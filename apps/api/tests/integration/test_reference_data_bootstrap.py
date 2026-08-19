"""Reference data is a property of the release, not of the seed (ADR-0029)."""

from __future__ import annotations

import pytest
from app.models.core import Category, Merchant
from app.models.receipts import MerchantParserProfile
from app.services import reference_data
from sqlalchemy import func, select
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


def test_clean_database_gets_the_taxonomy_and_the_parser_profiles(db: Session) -> None:
    created = reference_data.ensure_all(db)

    assert created["categories"] > 0
    assert created["parser_profiles"] == len(reference_data.PARSER_PROFILES)
    assert created["merchants"] == len(reference_data.PORTUGUESE_MERCHANTS)

    levels = dict(
        db.execute(
            select(Category.level, func.count())
            .where(Category.domain == "GROCERY")
            .group_by(Category.level)
        ).all()
    )
    assert set(levels) == {1, 2, 3}

    # Every per-merchant profile resolved its merchant, and the fallback did not.
    profiles = db.scalars(select(MerchantParserProfile)).all()
    assert {p.parser_key for p in profiles} == {
        spec["parser_key"] for spec in reference_data.PARSER_PROFILES
    }
    generic = next(p for p in profiles if p.parser_key == "generic_v1")
    assert generic.merchant_id is None
    assert all(p.merchant_id is not None for p in profiles if p.parser_key != "generic_v1")


def test_second_boot_writes_nothing(db: Session) -> None:
    reference_data.ensure_all(db)

    assert reference_data.ensure_all(db) == {
        "merchants": 0,
        "categories": 0,
        "parser_profiles": 0,
    }


def test_a_new_release_adds_only_what_is_missing(db: Session) -> None:
    reference_data.ensure_all(db)
    before = db.scalar(select(func.count()).select_from(Category))

    dropped = db.scalars(
        select(Category).where(Category.domain == "GROCERY", Category.level == 3).limit(3)
    ).all()
    renamed = db.scalar(select(Category).where(Category.domain == "GROCERY", Category.level == 1))
    assert renamed is not None
    renamed.display_name_pt = "Nome escolhido pelo agregado"
    for row in dropped:
        db.delete(row)
    db.flush()

    assert reference_data.ensure_categories(db) == len(dropped)
    assert db.scalar(select(func.count()).select_from(Category)) == before
    # What the household renamed stays renamed.
    db.refresh(renamed)
    assert renamed.display_name_pt == "Nome escolhido pelo agregado"


def test_a_retired_profile_stays_retired(db: Session) -> None:
    reference_data.ensure_all(db)

    profile = db.scalar(
        select(MerchantParserProfile).where(MerchantParserProfile.parser_key == "lidl_v1")
    )
    assert profile is not None
    profile.is_deleted = True
    db.flush()

    assert reference_data.ensure_parser_profiles(db) == 0


def test_a_merchant_keeps_the_fiscal_details_it_was_given(db: Session) -> None:
    db.add(Merchant(name="Lidl", kind="RETAIL", aliases=["Lidl da esquina"]))
    db.flush()

    reference_data.ensure_merchants(db)

    merchant = db.scalar(select(Merchant).where(Merchant.name == "Lidl"))
    assert merchant is not None
    assert merchant.aliases == ["Lidl da esquina"]
    assert merchant.nif == "503340855"
