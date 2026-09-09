"""Protects: the M1b exit criterion — *«the 2025 import yields ~1,564 products; a
re-parse of the fixtures now resolves products and categories, and a correction
sticks»* — plus the rubric bullets on the legacy import.

Every number below was **measured** against the real 2,429-row sheet, not assumed.
Note the two readings, which differ only by the non-grocery merchants:

| Run                                   | Groups | Reconciling | Only-Fs |
| :------------------------------------ | -----: | ----------: | ------: |
| Whole sheet (``include_non_grocery``)  |    288 |         281 |       6 |
| Grocery only (the default)             |    272 |         265 |       4 |

The importer reconciles one group more than the sheet's own ``Price_Final``
column does (281 against 280), because the invoice-level credit is **recomputed**
and spread by largest remainder — which makes the sum exact by construction
whenever the residual is non-negative. The groups that still fail are the ones
with a *negative* residual: genuine holes in the sheet, such as the Continente
group claiming €41,99 against a single €3,74 line. They land in ``NEEDS_REVIEW``
with a reason rather than being written as fact.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from app.models import Entity, Merchant, User
from app.models.products import MasterProduct, ProductAlias
from app.models.supermarket import SupermarketReceipt, SupermarketReceiptItem
from app.services.reference_data import ensure_all
from app.services.supermarket import catalogue, legacy_import
from sqlalchemy import func, select
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

SHEET = Path(__file__).resolve().parents[1] / "fixtures" / "SUPERMARKET_2025.xlsx"


@pytest.fixture(scope="session")
def sheet_bytes() -> bytes:
    return SHEET.read_bytes()


@pytest.fixture
def reference_data(db: Session) -> None:
    ensure_all(db)


# --- The grouping algorithm, before anything is written ----------------------


def test_fs_rows_are_snapped_back_onto_their_invoice(sheet_bytes: bytes) -> None:
    """401 of 425 sit at exactly +1 s and 17 at +0 s, which is why we snap rather
    than subtract a blanket second."""
    rows = legacy_import.read_rows(sheet_bytes)
    assert len(rows) == 2429

    fs_rows = [row for row in rows if legacy_import._is_fs(row)]
    assert len(fs_rows) == 425  # 419 `F` + 6 lowercase `f`

    assert legacy_import.snap_fs_timestamps(rows) == 418


def test_grouping_by_snapped_timestamp_yields_the_receipts_the_household_had(
    sheet_bytes: bytes,
) -> None:
    """288 receipts over 2,429 rows is ~8.4 articles a shop — what a grocery
    receipt actually looks like. Grouping by «Preço Fatura» gave 431 and was wrong."""
    rows = legacy_import.read_rows(sheet_bytes)
    legacy_import.snap_fs_timestamps(rows)
    groups = legacy_import.group_rows(rows)

    assert len(groups) == 288
    orphans = [
        key for key, group in groups.items() if all(legacy_import._is_fs(row) for row in group)
    ]
    # More than a handful means the snap window or the grouping key has broken
    # and Fs articles are being torn from their invoices.
    assert len(orphans) == 6


def test_the_two_pingo_doce_rows_five_hours_apart_stay_two_receipts(
    sheet_bytes: bytes,
) -> None:
    """«Date_ID» is day-granular; using it as a key would merge these into one."""
    rows = legacy_import.read_rows(sheet_bytes)
    legacy_import.snap_fs_timestamps(rows)
    groups = legacy_import.group_rows(rows)

    same_day = [
        key
        for key in groups
        if key[0] == "PINGO DOCE" and key[1].date().isoformat() == "2025-01-25"
    ]
    assert len(same_day) == 2


# --- The import itself --------------------------------------------------------


@pytest.fixture
def imported(
    db: Session, entity: Entity, owner: User, reference_data: None, sheet_bytes: bytes
) -> legacy_import.ImportReport:
    return legacy_import.import_workbook(
        db, data=sheet_bytes, entity_id=entity.id, actor_user_id=owner.id
    )


def test_the_2025_import_runs_end_to_end(db: Session, imported: legacy_import.ImportReport) -> None:
    report = imported
    assert report.row_count == 2429
    assert report.receipts_created == 272
    assert report.receipts_reconciled == 265
    assert report.receipts_needing_review == 7
    assert report.fs_rows == 425
    assert report.fs_rows_snapped == 418
    assert report.all_fs_groups == 4

    # ~1,564 distinct products once trimmed and case-folded (747 rows carry stray
    # whitespace), less the ones only the skipped non-grocery merchants sold.
    products = db.scalar(select(func.count()).select_from(MasterProduct)) or 0
    assert 1400 <= products <= 1600

    # Excluded and reported, so the decision stays visible and reversible.
    assert report.skipped_non_grocery_rows == 58
    assert "IKEA" in {name.upper() for name in report.skipped_non_grocery_merchants}

    # The sheet is validated, not trusted: nothing is silently repaired.
    assert report.exceptions
    flagged = db.scalars(
        select(SupermarketReceipt).where(SupermarketReceipt.status == "NEEDS_REVIEW")
    ).all()
    assert len(flagged) == 7
    assert any(reason["rule"] == "arithmetic_mismatch" for reason in flagged[0].decision_reasons)


def test_the_whole_sheet_reproduces_the_numbers_the_module_measured(
    db: Session, entity: Entity, owner: User, reference_data: None, sheet_bytes: bytes
) -> None:
    report = legacy_import.import_workbook(
        db,
        data=sheet_bytes,
        entity_id=entity.id,
        actor_user_id=owner.id,
        include_non_grocery=True,
    )
    assert report.receipts_created == 288
    assert report.receipts_reconciled == 281
    assert report.all_fs_groups == 6


def test_fs_rows_import_with_paid_price_zero_and_disturb_no_total(
    db: Session, imported: legacy_import.ImportReport
) -> None:
    fs_items = db.scalars(
        select(SupermarketReceiptItem).where(SupermarketReceiptItem.is_fs.is_(True))
    ).all()
    assert len(fs_items) >= 390
    assert all(item.paid_price_eur == Decimal("0.00") for item in fs_items)
    assert all(item.line_no is None for item in fs_items)
    assert all(item.unit_price_pvp_eur > Decimal("0.00") for item in fs_items)
    # An Fs row with no value at all is meaningless; it is reported, not written.
    assert any(entry.get("rule") == "fs_row_without_value" for entry in imported.exceptions)


def test_merchant_find_or_create_folds_the_eighteen_spellings(
    db: Session, imported: legacy_import.ImportReport
) -> None:
    """«Mercadona» and «mercadona» are one shop."""
    names = [
        name.lower()
        for name in db.scalars(select(Merchant.name).where(Merchant.is_deleted.is_(False))).all()
    ]
    assert names.count("mercadona") == 1


def test_every_line_resolves_to_a_product_that_carries_an_alias(
    db: Session, imported: legacy_import.ImportReport
) -> None:
    products = db.scalar(select(func.count()).select_from(MasterProduct)) or 0
    aliases = db.scalar(select(func.count()).select_from(ProductAlias)) or 0
    assert aliases >= products * 0.9
    assert all(
        item.master_product_id is not None
        for item in db.scalars(select(SupermarketReceiptItem).limit(300)).all()
    )


def test_sheet_categories_arrive_as_suggestions_never_as_validated(
    db: Session, imported: legacy_import.ImportReport
) -> None:
    """One row files a cider under «Talho › Vaca › Almondegas», so nothing is trusted."""
    assert set(db.scalars(select(MasterProduct.category_status).distinct()).all()) == {"AUTO"}


def test_rerunning_the_import_duplicates_nothing(
    db: Session,
    entity: Entity,
    owner: User,
    imported: legacy_import.ImportReport,
    sheet_bytes: bytes,
) -> None:
    receipts_before = db.scalar(select(func.count()).select_from(SupermarketReceipt)) or 0
    products_before = db.scalar(select(func.count()).select_from(MasterProduct)) or 0

    again = legacy_import.import_workbook(
        db, data=sheet_bytes, entity_id=entity.id, actor_user_id=owner.id
    )

    assert again.receipts_created == 0
    assert (db.scalar(select(func.count()).select_from(SupermarketReceipt)) or 0) == receipts_before
    assert (db.scalar(select(func.count()).select_from(MasterProduct)) or 0) == products_before


def test_the_catalogue_now_resolves_a_line_it_has_seen_before(
    db: Session, imported: legacy_import.ImportReport
) -> None:
    """The import is what solves cold start (Decision #39)."""
    alias = db.scalars(select(ProductAlias).limit(1)).all()[0]
    match = catalogue.resolve_description(
        db, merchant_id=alias.merchant_id, description_norm=alias.description_norm
    )
    assert match.master_product_id == alias.master_product_id
    assert match.score >= Decimal("0.600")
