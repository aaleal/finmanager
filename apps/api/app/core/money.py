"""Money helpers. EUR only, ``Decimal`` only — floats never touch a money value."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def to_eur(value: Decimal | int | str | None) -> Decimal | None:
    """Coerce to a 2-decimal EUR amount. ``float`` is rejected outright."""
    if value is None:
        return None
    if isinstance(value, float):
        raise TypeError("money must never be a float; use Decimal or str")
    try:
        return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:  # pragma: no cover - defensive
        raise ValueError(f"invalid monetary value: {value!r}") from exc


def eur_sum(values: object) -> Decimal:
    """Sum an iterable of optional EUR amounts, skipping ``None``."""
    total = ZERO
    for value in values:  # type: ignore[attr-defined]
        if value is not None:
            total += Decimal(value)
    return total.quantize(CENT, rounding=ROUND_HALF_UP)


def roi_pct(cost_eur: Decimal | None, current_value_eur: Decimal | None) -> Decimal | None:
    """Unrealized ROI %.

    ``None`` when there is no cost basis (gifts, ``0.00``) or no current value —
    the UI renders that as an em dash, never as ``0%`` (M9 edge cases).
    """
    if cost_eur is None or current_value_eur is None:
        return None
    if Decimal(cost_eur) == ZERO:
        return None
    appreciation = Decimal(current_value_eur) - Decimal(cost_eur)
    return (appreciation / Decimal(cost_eur) * Decimal(100)).quantize(CENT, rounding=ROUND_HALF_UP)


def appreciation_eur(cost_eur: Decimal | None, current_value_eur: Decimal | None) -> Decimal | None:
    """Unrealized gain. ``None`` when the model has no current value set."""
    if current_value_eur is None or cost_eur is None:
        return None
    return (Decimal(current_value_eur) - Decimal(cost_eur)).quantize(CENT, rounding=ROUND_HALF_UP)
