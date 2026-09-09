"""Protects: *«PVP vs paid … €/kg has three distinct variants — don't collapse
them»* and *«the invoice-level discount is prorated, not a per-item promo»*
(brief §3 Domain), plus the M1 rubric bullet that summing per-item promos alone
does not reconcile.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from app.services.supermarket import arithmetic


def test_only_pvp_minus_promo_minus_allocated_reconciles() -> None:
    """The classic bug: sum the per-item promos and miss the invoice credit."""
    lines = [
        arithmetic.ProrationInput(Decimal("10.00"), Decimal("1.00")),
        arithmetic.ProrationInput(Decimal("30.00"), Decimal("0.00")),
    ]
    allocations = arithmetic.prorate_invoice_discount(lines, Decimal("3.90"))

    naive = sum(line.unit_price_pvp_eur - line.promo_discount_eur for line in lines)
    correct = sum(
        arithmetic.paid_from_components(
            unit_price_pvp_eur=line.unit_price_pvp_eur,
            promo_discount_eur=line.promo_discount_eur,
            invoice_allocated_discount_eur=allocated,
        )
        for line, allocated in zip(lines, allocations, strict=True)
    )
    assert naive == Decimal("39.00")
    assert correct == Decimal("35.10")


def test_allocation_sums_to_the_whole_credit_exactly() -> None:
    """A per-line round() leaves a cent adrift and breaks a long receipt."""
    lines = [arithmetic.ProrationInput(Decimal("1.00"), Decimal("0.00")) for _ in range(7)]
    allocations = arithmetic.prorate_invoice_discount(lines, Decimal("1.00"))
    assert sum(allocations) == Decimal("1.00")


def test_no_invoice_credit_allocates_nothing() -> None:
    lines = [arithmetic.ProrationInput(Decimal("5.00"), Decimal("0.50"))]
    assert arithmetic.prorate_invoice_discount(lines, Decimal("0.00")) == [Decimal("0.00")]


def test_three_price_per_kg_variants_are_distinct() -> None:
    """A fixture carrying both a per-item promo *and* an invoice-level discount."""
    per_kg = arithmetic.price_per_kg(
        unit_price_pvp_eur=Decimal("4.00"),
        promo_discount_eur=Decimal("1.00"),
        paid_price_eur=Decimal("2.50"),
        weight_observed_kg=Decimal("0.500"),
        weight_listed_kg=Decimal("0.400"),
    )
    assert per_kg.weight_kg == Decimal("0.500")  # observed wins over listed
    assert per_kg.pvp == Decimal("8.0000")
    assert per_kg.promo == Decimal("6.0000")
    assert per_kg.final == Decimal("5.0000")
    assert len({per_kg.pvp, per_kg.promo, per_kg.final}) == 3


def test_missing_weight_suppresses_price_per_kg_with_a_reason() -> None:
    """Never fabricate a weight — an item sold by count has no meaningful €/kg."""
    per_kg = arithmetic.price_per_kg(
        unit_price_pvp_eur=Decimal("1.00"),
        promo_discount_eur=Decimal("0.00"),
        paid_price_eur=Decimal("1.00"),
        weight_observed_kg=None,
        weight_listed_kg=None,
    )
    assert (per_kg.pvp, per_kg.promo, per_kg.final) == (None, None, None)
    assert per_kg.unavailable_reason == "sem_peso"


@pytest.mark.parametrize(
    ("quantity", "unit", "expected", "canonical"),
    [
        ("500", "G", Decimal("0.5000"), "KG"),
        ("1.5", "KG", Decimal("1.5000"), "KG"),
        ("330", "ML", Decimal("0.3300"), "L"),
        ("2", "PACK", Decimal("2.0000"), "UN"),
    ],
)
def test_units_normalize_within_their_family_only(
    quantity: str, unit: str, expected: Decimal, canonical: str
) -> None:
    value, family = arithmetic.canonical_quantity(Decimal(quantity), unit)
    assert (value, family) == (expected, canonical)


def test_reconciliation_tolerance_is_a_signal_not_a_gate() -> None:
    items = [
        arithmetic.ItemTotalsInput(
            paid_price_eur=Decimal("9.99"),
            unit_price_pvp_eur=Decimal("9.99"),
            promo_discount_eur=Decimal("0.00"),
            quantity=Decimal("1"),
            is_fs=False,
        )
    ]
    within = arithmetic.receipt_totals(items, total_eur=Decimal("10.00"))
    outside = arithmetic.receipt_totals(items, total_eur=Decimal("10.50"))
    assert within.is_reconciled is True
    assert outside.is_reconciled is False
    assert outside.reconciliation_delta_eur == Decimal("0.51")


def test_refunds_carry_negative_quantities_and_derive_the_counts() -> None:
    refund = arithmetic.ItemTotalsInput(
        paid_price_eur=Decimal("-2.00"),
        unit_price_pvp_eur=Decimal("-2.00"),
        promo_discount_eur=Decimal("0.00"),
        quantity=Decimal("-1"),
        is_fs=False,
    )
    totals = arithmetic.receipt_totals([refund], total_eur=Decimal("-2.00"))
    assert totals.refund_item_count == 1
    assert totals.is_return is True
