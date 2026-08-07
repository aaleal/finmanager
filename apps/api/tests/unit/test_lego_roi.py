"""Protects: M9 Definition of Done — «unrealized ROI math (incl. gift/zero-cost and
no-value-set cases)».

ROI is *always* unrealized: current value versus acquisition cost. It is ``None``
(rendered as an em dash, never 0 %) when there is no cost basis or no value, and
it is never derived from ``sale_price_eur``.
"""

from __future__ import annotations

from decimal import Decimal

from app.core.money import appreciation_eur, roi_pct


def test_positive_appreciation() -> None:
    assert appreciation_eur(Decimal("599.99"), Decimal("689.00")) == Decimal("89.01")
    assert roi_pct(Decimal("599.99"), Decimal("689.00")) == Decimal("14.84")


def test_negative_appreciation_is_reported_not_clamped() -> None:
    assert appreciation_eur(Decimal("100.00"), Decimal("60.00")) == Decimal("-40.00")
    assert roi_pct(Decimal("100.00"), Decimal("60.00")) == Decimal("-40.00")


def test_gift_has_no_roi_and_never_divides_by_zero() -> None:
    # A zero-cost copy still has an appreciation figure, but ROI is undefined.
    assert appreciation_eur(Decimal("0.00"), Decimal("380.00")) == Decimal("380.00")
    assert roi_pct(Decimal("0.00"), Decimal("380.00")) is None


def test_model_without_current_value_has_neither_appreciation_nor_roi() -> None:
    assert appreciation_eur(Decimal("45.00"), None) is None
    assert roi_pct(Decimal("45.00"), None) is None


def test_gift_and_no_value_together() -> None:
    assert roi_pct(Decimal("0.00"), None) is None


def test_rounding_is_half_up_to_two_places() -> None:
    assert roi_pct(Decimal("3.00"), Decimal("4.00")) == Decimal("33.33")
