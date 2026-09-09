"""Protects: the M1c exit criterion — *«€/kg trends render across merchants,
shrinkflation fires on a seeded case, and an Fs article changes
`notional_total_eur` without touching `total_eur`»* — plus the rubric bullets on
immutable price observations and the €/kg variants.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from app.models import Entity, Merchant, User
from app.models.prices import ProductPriceHistory
from app.models.products import MasterProduct
from app.models.supermarket import SupermarketReceipt, SupermarketReceiptItem
from app.services.supermarket import ledger, prices_service, products_service
from app.services.supermarket import service as receipts
from app.services.supermarket.normalize import extract_pack_weight_kg
from sqlalchemy import func, select
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


@pytest.fixture
def merchants(db: Session) -> dict[str, Merchant]:
    made = {}
    for name in ("Continente", "Lidl"):
        row = Merchant(name=name, kind="RETAIL", aliases=[])
        db.add(row)
        made[name] = row
    db.flush()
    return made


@pytest.fixture
def coffee(db: Session) -> MasterProduct:
    return products_service.create_product(
        db, canonical_name="Café Moído Delta", sold_by_weight=False
    )


def make_receipt(
    db: Session,
    entity: Entity,
    merchant: Merchant,
    *,
    on: dt.date,
    total: str,
) -> SupermarketReceipt:
    receipt = SupermarketReceipt(
        entity_id=entity.id,
        merchant_id=merchant.id,
        purchase_date=on,
        purchased_at=dt.datetime.combine(on, dt.time(12, 0)),
        total_eur=Decimal(total),
        status="PARSING",
    )
    db.add(receipt)
    db.flush()
    return receipt


def add_line(
    db: Session,
    receipt: SupermarketReceipt,
    product: MasterProduct,
    *,
    price: str,
    weight: str | None,
    is_fs: bool = False,
) -> SupermarketReceiptItem:
    item = SupermarketReceiptItem(
        receipt_id=receipt.id,
        entity_id=receipt.entity_id,
        line_no=None if is_fs else 1,
        description_raw="CAFE MOIDO DELTA 250G",
        description_norm="CAFE MOIDO DELTA 250G",
        master_product_id=product.id,
        unit_price_pvp_eur=Decimal(price),
        paid_price_eur=Decimal("0.00") if is_fs else Decimal(price),
        weight_observed_kg=Decimal(weight) if weight else None,
        is_fs=is_fs,
        notional_value_source="MANUAL" if is_fs else None,
    )
    db.add(item)
    db.flush()
    db.refresh(receipt)
    return item


# --- Observations --------------------------------------------------------------


def test_confirming_a_receipt_freezes_one_observation_per_resolved_line(
    db: Session, entity: Entity, owner: User, merchants: dict[str, Merchant], coffee: MasterProduct
) -> None:
    receipt = make_receipt(
        db, entity, merchants["Continente"], on=dt.date(2026, 1, 5), total="3.49"
    )
    add_line(db, receipt, coffee, price="3.49", weight="0.250")

    assert prices_service.record_observations(db, receipt) == 1
    row = db.scalars(select(ProductPriceHistory)).one()
    assert row.list_price_eur == Decimal("3.49")
    assert row.weight_kg == Decimal("0.2500")
    assert row.is_fs is False


def test_recording_twice_writes_nothing_the_second_time(
    db: Session, entity: Entity, merchants: dict[str, Merchant], coffee: MasterProduct
) -> None:
    receipt = make_receipt(db, entity, merchants["Lidl"], on=dt.date(2026, 1, 5), total="3.49")
    add_line(db, receipt, coffee, price="3.49", weight="0.250")

    prices_service.record_observations(db, receipt)
    assert prices_service.record_observations(db, receipt) == 0
    assert (db.scalar(select(func.count()).select_from(ProductPriceHistory)) or 0) == 1


def test_a_correction_appends_a_new_row_and_never_rewrites_the_past(
    db: Session, entity: Entity, merchants: dict[str, Merchant], coffee: MasterProduct
) -> None:
    receipt = make_receipt(db, entity, merchants["Lidl"], on=dt.date(2026, 1, 5), total="3.49")
    item = add_line(db, receipt, coffee, price="3.49", weight="0.250")
    prices_service.record_observations(db, receipt)

    item.unit_price_pvp_eur = Decimal("3.99")
    item.paid_price_eur = Decimal("3.99")
    db.flush()
    assert prices_service.record_observations(db, receipt) == 1

    rows = db.scalars(select(ProductPriceHistory).order_by(ProductPriceHistory.created_at)).all()
    assert [row.list_price_eur for row in rows] == [Decimal("3.49"), Decimal("3.99")]


def test_an_fs_observation_carries_the_notional_value_in_both_price_columns(
    db: Session, entity: Entity, merchants: dict[str, Merchant], coffee: MasterProduct
) -> None:
    """A literal 0,00 would drag every paid-price trend for the product to zero."""
    receipt = make_receipt(db, entity, merchants["Lidl"], on=dt.date(2026, 2, 1), total="0.00")
    add_line(db, receipt, coffee, price="4.50", weight="0.250", is_fs=True)

    prices_service.record_observations(db, receipt)
    row = db.scalars(select(ProductPriceHistory)).one()
    assert row.is_fs is True
    assert row.list_price_eur == Decimal("4.50")
    assert row.paid_price_eur == Decimal("4.50")


# --- Trends --------------------------------------------------------------------


def test_price_per_kg_trends_render_across_merchants(
    db: Session, entity: Entity, merchants: dict[str, Merchant], coffee: MasterProduct
) -> None:
    for merchant, price in ((merchants["Continente"], "3.49"), (merchants["Lidl"], "2.99")):
        receipt = make_receipt(db, entity, merchant, on=dt.date(2026, 1, 10), total=price)
        add_line(db, receipt, coffee, price=price, weight="0.250")
        prices_service.record_observations(db, receipt)

    points = prices_service.price_history(db, master_product_id=coffee.id, entity_ids=[entity.id])
    assert {point.merchant_name for point in points} == {"Continente", "Lidl"}
    assert sorted(point.list_price_per_kg_eur for point in points) == [
        Decimal("11.9600"),
        Decimal("13.9600"),
    ]


def test_the_fs_filter_redraws_the_series(
    db: Session, entity: Entity, merchants: dict[str, Merchant], coffee: MasterProduct
) -> None:
    paid = make_receipt(db, entity, merchants["Lidl"], on=dt.date(2026, 1, 10), total="3.49")
    add_line(db, paid, coffee, price="3.49", weight="0.250")
    prices_service.record_observations(db, paid)

    given = make_receipt(db, entity, merchants["Lidl"], on=dt.date(2026, 1, 20), total="0.00")
    add_line(db, given, coffee, price="4.50", weight="0.250", is_fs=True)
    prices_service.record_observations(db, given)

    def count(fs: str) -> int:
        return len(
            prices_service.price_history(
                db,
                master_product_id=coffee.id,
                entity_ids=[entity.id],
                fs=fs,  # type: ignore[arg-type]
            )
        )

    assert count("all") == 2
    assert count("only") == 1
    assert count("exclude") == 1


def test_a_missing_weight_leaves_price_per_kg_null_rather_than_guessing(
    db: Session, entity: Entity, merchants: dict[str, Merchant], coffee: MasterProduct
) -> None:
    receipt = make_receipt(db, entity, merchants["Lidl"], on=dt.date(2026, 1, 10), total="3.49")
    add_line(db, receipt, coffee, price="3.49", weight=None)
    prices_service.record_observations(db, receipt)

    point = prices_service.price_history(db, master_product_id=coffee.id, entity_ids=[entity.id])[0]
    assert point.weight_kg is None
    assert point.list_price_per_kg_eur is None


def test_the_last_known_price_pre_fills_manual_entry(
    db: Session, entity: Entity, merchants: dict[str, Merchant], coffee: MasterProduct
) -> None:
    for day, price in ((5, "3.49"), (20, "3.99")):
        receipt = make_receipt(db, entity, merchants["Lidl"], on=dt.date(2026, 3, day), total=price)
        add_line(db, receipt, coffee, price=price, weight="0.250")
        prices_service.record_observations(db, receipt)

    latest = prices_service.last_known_price(db, coffee.id)
    assert latest is not None
    assert latest.last_pvp_eur == Decimal("3.99")
    assert latest.last_price_per_kg_eur == Decimal("15.9600")
    assert latest.last_observed_on == dt.date(2026, 3, 20)


# --- Shrinkflation --------------------------------------------------------------


def test_shrinkflation_fires_when_the_pack_shrinks_faster_than_the_price_falls(
    db: Session, entity: Entity, merchants: dict[str, Merchant], coffee: MasterProduct
) -> None:
    today = dt.date(2026, 6, 1)
    # Four 250 g observations at €3,49, then a 200 g pack at the same price.
    for month in (1, 2, 3, 4):
        receipt = make_receipt(
            db, entity, merchants["Lidl"], on=dt.date(2026, month, 5), total="3.49"
        )
        add_line(db, receipt, coffee, price="3.49", weight="0.250")
        prices_service.record_observations(db, receipt)

    shrunk = make_receipt(db, entity, merchants["Lidl"], on=dt.date(2026, 5, 5), total="3.49")
    add_line(db, shrunk, coffee, price="3.49", weight="0.200")
    prices_service.record_observations(db, shrunk)

    signals = prices_service.shrinkflation(db, entity_ids=[entity.id], today=today)
    assert len(signals) == 1
    assert signals[0].canonical_name == "Café Moído Delta"
    # 0,200/0,250 - 3,49/3,49 = -0,2000
    assert signals[0].margin_signal == Decimal("-0.2000")


def test_a_stable_pack_raises_no_shrinkflation_signal(
    db: Session, entity: Entity, merchants: dict[str, Merchant], coffee: MasterProduct
) -> None:
    for month in (1, 2, 3, 4, 5):
        receipt = make_receipt(
            db, entity, merchants["Lidl"], on=dt.date(2026, month, 5), total="3.49"
        )
        add_line(db, receipt, coffee, price="3.49", weight="0.250")
        prices_service.record_observations(db, receipt)

    assert prices_service.shrinkflation(db, entity_ids=[entity.id], today=dt.date(2026, 6, 1)) == []


def test_too_few_observations_raise_no_signal(
    db: Session, entity: Entity, merchants: dict[str, Merchant], coffee: MasterProduct
) -> None:
    """Fewer than three priors is not a trend, however dramatic the change."""
    for month, weight in ((1, "0.250"), (2, "0.100")):
        receipt = make_receipt(
            db, entity, merchants["Lidl"], on=dt.date(2026, month, 5), total="3.49"
        )
        add_line(db, receipt, coffee, price="3.49", weight=weight)
        prices_service.record_observations(db, receipt)

    assert prices_service.shrinkflation(db, entity_ids=[entity.id], today=dt.date(2026, 6, 1)) == []


# --- Spend, loyalty and the ledger ----------------------------------------------


def test_an_fs_article_moves_the_notional_measure_and_nothing_else(
    db: Session, entity: Entity, owner: User, merchants: dict[str, Merchant], coffee: MasterProduct
) -> None:
    receipt = make_receipt(db, entity, merchants["Lidl"], on=dt.date(2026, 4, 1), total="3.49")
    add_line(db, receipt, coffee, price="3.49", weight="0.250")

    before = prices_service.category_spend(db, entity_ids=[entity.id])
    total_before = receipt.total_eur

    receipts.append_fs_item(
        db,
        receipt,
        description_raw="Café oferecido",
        unit_price_pvp_eur=Decimal("4.50"),
        actor_user_id=owner.id,
    )
    after = prices_service.category_spend(db, entity_ids=[entity.id])

    assert receipt.total_eur == total_before
    assert sum(row["paid_eur"] for row in after) == sum(row["paid_eur"] for row in before)
    assert sum(row["notional_eur"] for row in after) == sum(
        row["notional_eur"] for row in before
    ) + Decimal("4.50")


def test_two_pack_sizes_of_one_product_yield_comparable_price_per_kg(
    db: Session, entity: Entity, merchants: dict[str, Merchant]
) -> None:
    """A 500 g and a 1 kg bag are **one** product — that is what makes €/kg
    comparable across them (Decision #15). What differs is the weight, and the
    size token in the description is what picks the variant."""
    coffee = products_service.create_product(
        db,
        canonical_name="Café Moído Delta",
        pack_variants=[
            {"label": "500 g", "weight_kg": "0.500"},
            {"label": "1 kg", "weight_kg": "1.000"},
        ],
    )

    for description, price, weight in (
        ("CAFE MOIDO DELTA 500G", "6.98", "0.500"),
        ("CAFE MOIDO DELTA 1KG", "13.60", "1.000"),
    ):
        receipt = make_receipt(
            db, entity, merchants["Continente"], on=dt.date(2026, 4, 1), total=price
        )
        item = add_line(db, receipt, coffee, price=price, weight=weight)
        item.description_raw = description
        # The weight the parser proposes comes from the printed size token.
        item.weight_listed_kg = extract_pack_weight_kg(description)
        db.flush()
        prices_service.record_observations(db, receipt)

    points = prices_service.price_history(db, master_product_id=coffee.id, entity_ids=[entity.id])
    assert [point.weight_kg for point in points] == [Decimal("0.5000"), Decimal("1.0000")]
    # 6,98/0,5 = 13,96 and 13,60/1 = 13,60 — directly comparable.
    assert [point.list_price_per_kg_eur for point in points] == [
        Decimal("13.9600"),
        Decimal("13.6000"),
    ]


def test_loyalty_is_a_group_by_over_receipts_not_a_table(
    db: Session, entity: Entity, merchants: dict[str, Merchant]
) -> None:
    for day, discount in ((1, "4.00"), (8, "0.29")):
        receipt = make_receipt(
            db, entity, merchants["Continente"], on=dt.date(2026, 5, day), total="36.56"
        )
        receipt.loyalty_scheme = "Cartão Continente"
        receipt.loyalty_card_masked = "XXXXXXXX3394X"
        receipt.loyalty_discount_eur = Decimal(discount)
        receipt.loyalty_accrued_eur = Decimal("1.00")
    db.flush()

    groups = prices_service.loyalty_summary(db, entity_ids=[entity.id])
    assert len(groups) == 1
    assert groups[0]["card_masked"] == "XXXXXXXX3394X"
    assert groups[0]["discount_eur"] == Decimal("4.29")
    assert groups[0]["receipt_count"] == 2


def test_the_ledger_link_degrades_honestly_until_banking_exists(
    db: Session, entity: Entity, owner: User, merchants: dict[str, Merchant]
) -> None:
    """Ship the contract, defer the constraint — the same posture as ADR-0005."""
    receipt = make_receipt(db, entity, merchants["Lidl"], on=dt.date(2026, 5, 1), total="8.06")
    assert ledger.is_available() is False
    assert ledger.propose_link(db, receipt, actor_user_id=owner.id) is None
    assert ledger.existing_link(db, receipt.id) is None

    # Manual linking still works end to end, so the picker is not a dead end.
    link = ledger.link_manually(db, receipt, transaction_id=receipt.id, actor_user_id=owner.id)
    assert link.link_type == "RECEIPT_TRANSACTION"
    assert link.status == "CONFIRMED"
    ledger.unlink(db, receipt.id)
    assert ledger.existing_link(db, receipt.id) is None
