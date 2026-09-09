"""Protects: *«the Fs rules are proven by unit tests»* (brief §4 Ingestion quality)
and the M1 rubric bullets on Fs valuation.

An **Fs article was never on the invoice**. Appending one must leave every
printed figure byte-identical — that is the single guarantee the whole Fs design
exists to provide, and it is the easiest thing in this module to break by
accident.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from app.services.supermarket import arithmetic


def paid(value: str, quantity: str = "1") -> arithmetic.ItemTotalsInput:
    return arithmetic.ItemTotalsInput(
        paid_price_eur=Decimal(value),
        unit_price_pvp_eur=Decimal(value),
        promo_discount_eur=Decimal("0.00"),
        quantity=Decimal(quantity),
        is_fs=False,
    )


def fs(value: str, quantity: str = "1") -> arithmetic.ItemTotalsInput:
    return arithmetic.ItemTotalsInput(
        paid_price_eur=Decimal("0.00"),
        unit_price_pvp_eur=Decimal(value),
        promo_discount_eur=Decimal("0.00"),
        quantity=Decimal(quantity),
        is_fs=True,
    )


def test_worked_example_from_the_module_spec() -> None:
    """10 paid articles totalling €10 plus 2 Fs articles worth €5 each."""
    items = [paid("1.00") for _ in range(10)] + [fs("5.00"), fs("5.00")]
    totals = arithmetic.receipt_totals(items, total_eur=Decimal("10.00"))

    assert totals.computed_total_eur == Decimal("10.00")
    assert totals.fs_value_eur == Decimal("10.00")
    assert totals.notional_total_eur == Decimal("20.00")
    # Fs value against what was actually *paid*: 100 %, not 50 % (Decision #31).
    assert totals.fs_share_pct == Decimal("100.00")
    assert totals.fs_item_count == 2
    assert totals.printed_item_count == 10


def test_appending_an_fs_article_moves_no_printed_figure() -> None:
    printed = [paid("4.00"), paid("6.00")]
    before = arithmetic.receipt_totals(printed, total_eur=Decimal("10.00"))
    after = arithmetic.receipt_totals([*printed, fs("5.00")], total_eur=Decimal("10.00"))

    assert after.computed_total_eur == before.computed_total_eur
    assert after.is_reconciled is before.is_reconciled is True
    assert after.printed_item_count == before.printed_item_count == 2
    # …and only the notional side moves.
    assert after.notional_total_eur == before.notional_total_eur + Decimal("5.00")


def test_fs_article_never_receives_an_invoice_discount_allocation() -> None:
    lines = [
        arithmetic.ProrationInput(Decimal("10.00"), Decimal("0.00")),
        arithmetic.ProrationInput(Decimal("5.00"), Decimal("0.00"), is_fs=True),
    ]
    allocations = arithmetic.prorate_invoice_discount(lines, Decimal("1.00"))
    assert allocations == [Decimal("1.00"), Decimal("0.00")]


def test_notional_value_equals_paid_on_every_non_fs_row() -> None:
    """What lets Fs articles join any dashboard without a special case."""
    assert arithmetic.notional_value_eur(
        is_fs=False,
        unit_price_pvp_eur=Decimal("9.99"),
        quantity=Decimal("3"),
        paid_price_eur=Decimal("7.50"),
    ) == Decimal("7.50")


def test_fs_price_per_kg_uses_the_notional_value_not_a_literal_zero() -> None:
    """Writing 0,00 would drag every paid-price trend for the product to zero."""
    per_kg = arithmetic.price_per_kg(
        unit_price_pvp_eur=Decimal("2.00"),
        promo_discount_eur=Decimal("0.00"),
        paid_price_eur=Decimal("0.00"),
        weight_observed_kg=Decimal("0.5"),
        weight_listed_kg=None,
        is_fs=True,
    )
    assert per_kg.final == Decimal("4.0000")


def test_fs_share_is_none_rather_than_infinite_on_a_zero_total() -> None:
    totals = arithmetic.receipt_totals([fs("5.00")], total_eur=Decimal("0.00"))
    assert totals.fs_share_pct is None
    assert totals.notional_total_eur == Decimal("5.00")


@pytest.mark.parametrize("quantity", ["1", "2", "3"])
def test_fs_notional_value_scales_with_quantity(quantity: str) -> None:
    value = arithmetic.notional_value_eur(
        is_fs=True,
        unit_price_pvp_eur=Decimal("2.50"),
        quantity=Decimal(quantity),
        paid_price_eur=Decimal("0.00"),
    )
    assert value == Decimal("2.50") * Decimal(quantity)
