"""Protects: rubric «Correctness — no float money anywhere».

Money is a ``Decimal`` EUR amount at every layer. A float must never be silently
accepted, because binary rounding is exactly the failure mode this project cannot
tolerate in a ledger.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from app.core.money import ZERO, eur_sum, to_eur


def test_float_money_is_rejected_outright() -> None:
    with pytest.raises(TypeError):
        to_eur(19.99)  # type: ignore[arg-type]


def test_decimal_and_string_are_quantized_to_cents() -> None:
    assert to_eur("19.994") == Decimal("19.99")
    assert to_eur("19.995") == Decimal("20.00")  # half-up, not banker's rounding
    assert to_eur(Decimal("7")) == Decimal("7.00")
    assert to_eur(None) is None


def test_sum_skips_missing_values_without_coercing_to_zero_semantics() -> None:
    assert eur_sum([Decimal("10.10"), None, Decimal("0.90")]) == Decimal("11.00")
    assert eur_sum([]) == ZERO


def test_repeated_addition_stays_exact() -> None:
    # 0.1 + 0.2 != 0.3 in binary floating point; it must here.
    assert eur_sum([Decimal("0.10"), Decimal("0.20")]) == Decimal("0.30")
