"""Receipt arithmetic — the part that is easy to get subtly wrong.

Three quantities must never be collapsed into one another:

``unit_price_pvp_eur``
    the line's gross value before any discount;
``promo_discount_eur``
    a promotion attached to *that line*;
``invoice_allocated_discount_eur``
    the invoice-level (cartão/global) credit, **prorated** onto the line.

Only ``pvp - promo - invoice_allocated`` reconciles. Summing per-item promos and
forgetting the invoice-level credit is the classic bug in this domain.

One deliberate asymmetry, called out because it looks like an inconsistency:
on a parsed line ``unit_price_pvp_eur`` holds the *line* gross (that is what the
formula above needs), while on an **Fs** article — typed by hand, never printed —
it holds the value of *one* article and the notional worth is
``pvp * quantity``. See docs/decisions/0015-fs-articles-are-appended-not-flagged.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.core.money import CENT, ZERO, to_eur

# Mass → kg, volume → L, count → un. The three families never convert between
# each other (FR-1.13).
_UNIT_FAMILY: dict[str, tuple[str, Decimal]] = {
    "KG": ("KG", Decimal("1")),
    "G": ("KG", Decimal("0.001")),
    "L": ("L", Decimal("1")),
    "ML": ("L", Decimal("0.001")),
    "UN": ("UN", Decimal("1")),
    "PACK": ("UN", Decimal("1")),
}

QUANTITY_PLACES = Decimal("0.0001")


def canonical_quantity(quantity: Decimal, unit: str) -> tuple[Decimal, str]:
    """Normalize ``(quantity, unit)`` into ``(quantity_canonical, KG|L|UN)``."""
    canonical_unit, factor = _UNIT_FAMILY.get(unit.upper(), ("UN", Decimal("1")))
    value = (Decimal(quantity) * factor).quantize(QUANTITY_PLACES, rounding=ROUND_HALF_UP)
    return value, canonical_unit


# --- Per-item derivations ----------------------------------------------------


@dataclass(frozen=True, slots=True)
class PricePerKg:
    """The three €/kg variants the household uses, plus why they are missing."""

    weight_kg: Decimal | None
    pvp: Decimal | None
    promo: Decimal | None
    final: Decimal | None
    unavailable_reason: str | None


_PER_KG_PLACES = Decimal("0.0001")


def price_per_kg(
    *,
    unit_price_pvp_eur: Decimal,
    promo_discount_eur: Decimal,
    paid_price_eur: Decimal,
    weight_observed_kg: Decimal | None,
    weight_listed_kg: Decimal | None,
    is_fs: bool = False,
) -> PricePerKg:
    """All three variants, or ``None`` with a stated reason — never a guess."""
    weight = weight_observed_kg if weight_observed_kg is not None else weight_listed_kg
    if weight is None:
        return PricePerKg(None, None, None, None, "sem_peso")
    weight = Decimal(weight)
    if weight <= 0:
        return PricePerKg(weight, None, None, None, "peso_invalido")

    pvp = Decimal(unit_price_pvp_eur)
    promo = Decimal(promo_discount_eur)
    # An Fs article was never paid for, so its "final" €/kg is its notional worth;
    # dividing 0,00 by a weight would drag every trend towards zero (Decision #33).
    paid = pvp if is_fs else Decimal(paid_price_eur)

    def divide(numerator: Decimal) -> Decimal:
        return (numerator / weight).quantize(_PER_KG_PLACES, rounding=ROUND_HALF_UP)

    return PricePerKg(weight, divide(pvp), divide(pvp - promo), divide(paid), None)


def notional_value_eur(
    *,
    is_fs: bool,
    unit_price_pvp_eur: Decimal,
    quantity: Decimal,
    paid_price_eur: Decimal,
) -> Decimal:
    """What the article was *worth*, as opposed to what was spent on it.

    Identical to ``paid_price_eur`` on every non-Fs row — which is exactly what
    lets Fs articles join any dashboard without a special case.
    """
    if not is_fs:
        return to_eur(paid_price_eur) or ZERO
    return (Decimal(unit_price_pvp_eur) * Decimal(quantity)).quantize(CENT, rounding=ROUND_HALF_UP)


def paid_from_components(
    *,
    unit_price_pvp_eur: Decimal,
    promo_discount_eur: Decimal,
    invoice_allocated_discount_eur: Decimal,
) -> Decimal:
    return (
        Decimal(unit_price_pvp_eur)
        - Decimal(promo_discount_eur)
        - Decimal(invoice_allocated_discount_eur)
    ).quantize(CENT, rounding=ROUND_HALF_UP)


# --- Invoice-level discount proration ----------------------------------------


@dataclass(frozen=True, slots=True)
class ProrationInput:
    """Just enough of a line to spread an invoice-level credit across it."""

    unit_price_pvp_eur: Decimal
    promo_discount_eur: Decimal
    is_fs: bool = False


def prorate_invoice_discount(
    lines: list[ProrationInput], total_discount_eur: Decimal
) -> list[Decimal]:
    """Spread the invoice/loyalty credit over the lines it applied to.

    Allocation is largest-remainder so the parts sum to the whole **exactly** —
    a per-line ``round()`` would leave a cent adrift and break reconciliation on
    long receipts. Fs articles never receive an allocation: they were not on the
    invoice being discounted (FR-1.10).
    """
    credit = to_eur(total_discount_eur) or ZERO
    allocations = [ZERO] * len(lines)
    if credit <= ZERO:
        return allocations

    bases = [
        (Decimal(line.unit_price_pvp_eur) - Decimal(line.promo_discount_eur))
        if not line.is_fs
        else ZERO
        for line in lines
    ]
    eligible = sum((b for b in bases if b > ZERO), ZERO)
    if eligible <= ZERO:
        return allocations

    remainders: list[tuple[Decimal, int]] = []
    running = ZERO
    for index, base in enumerate(bases):
        if base <= ZERO:
            continue
        exact = credit * base / eligible
        floored = exact.quantize(CENT, rounding="ROUND_DOWN")
        allocations[index] = floored
        running += floored
        remainders.append((exact - floored, index))

    # Hand the leftover cents to the largest remainders, biggest base breaking ties.
    leftover = int(((credit - running) / CENT).to_integral_value(rounding=ROUND_HALF_UP))
    remainders.sort(key=lambda pair: (pair[0], bases[pair[1]]), reverse=True)
    for offset in range(max(leftover, 0)):
        if not remainders:
            break
        _, index = remainders[offset % len(remainders)]
        allocations[index] += CENT

    return allocations


# --- Per-receipt derivations --------------------------------------------------


@dataclass(frozen=True, slots=True)
class ItemTotalsInput:
    paid_price_eur: Decimal
    unit_price_pvp_eur: Decimal
    promo_discount_eur: Decimal
    quantity: Decimal
    is_fs: bool


@dataclass(frozen=True, slots=True)
class ReceiptTotals:
    computed_total_eur: Decimal
    subtotal_eur: Decimal
    fs_value_eur: Decimal
    fs_item_count: int
    fs_share_pct: Decimal | None
    notional_total_eur: Decimal
    printed_item_count: int
    refund_item_count: int
    is_return: bool
    is_reconciled: bool
    reconciliation_delta_eur: Decimal
    invoice_discount_ratio: Decimal | None


DEFAULT_TOLERANCE_EUR = Decimal("0.02")


def receipt_totals(
    items: list[ItemTotalsInput],
    *,
    total_eur: Decimal,
    total_discount_eur: Decimal = ZERO,
    tolerance_eur: Decimal = DEFAULT_TOLERANCE_EUR,
) -> ReceiptTotals:
    """Everything a receipt derives. Nothing here is persisted.

    Fs rows contribute ``0.00`` to ``computed_total_eur`` and are excluded from
    the printed-count check, which is what guarantees that appending one leaves
    every printed figure byte-identical.
    """
    printed = [i for i in items if not i.is_fs]
    fs = [i for i in items if i.is_fs]

    computed_total = sum((Decimal(i.paid_price_eur) for i in items), ZERO).quantize(CENT)
    claimed_total = to_eur(total_eur) or ZERO
    fs_value = sum(
        (
            notional_value_eur(
                is_fs=True,
                unit_price_pvp_eur=i.unit_price_pvp_eur,
                quantity=i.quantity,
                paid_price_eur=i.paid_price_eur,
            )
            for i in fs
        ),
        ZERO,
    ).quantize(CENT)

    net_base = sum(
        (Decimal(i.unit_price_pvp_eur) - Decimal(i.promo_discount_eur) for i in printed), ZERO
    )
    delta = (computed_total - claimed_total).copy_abs()

    return ReceiptTotals(
        computed_total_eur=computed_total,
        subtotal_eur=(claimed_total + (to_eur(total_discount_eur) or ZERO)).quantize(CENT),
        fs_value_eur=fs_value,
        fs_item_count=len(fs),
        # Fs value against what was actually *paid*: €10 of Fs on a €10 invoice
        # reads as 100 %, not 50 % (Decision #31).
        fs_share_pct=(
            (fs_value / claimed_total * Decimal(100)).quantize(CENT)
            if claimed_total != ZERO
            else None
        ),
        notional_total_eur=(claimed_total + fs_value).quantize(CENT),
        printed_item_count=len(printed),
        refund_item_count=sum(1 for i in items if Decimal(i.quantity) < 0),
        is_return=bool(items) and all(Decimal(i.quantity) < 0 for i in items),
        is_reconciled=delta <= Decimal(tolerance_eur),
        reconciliation_delta_eur=delta,
        invoice_discount_ratio=(
            (Decimal(total_discount_eur) / net_base).quantize(Decimal("0.000001"))
            if net_base > ZERO
            else None
        ),
    )
