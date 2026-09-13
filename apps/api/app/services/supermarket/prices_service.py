"""Money over time: price observations, €/kg trends, shrinkflation and loyalty.

Two measures, one grammar. Every analytic here is expressible over
``paid_price_eur`` ("what did I spend") or ``notional_value_eur`` ("what was it
worth"), and the two are **identical on non-Fs rows** — which is exactly what lets
Fs articles join any view without a special case. Combined with the ``fs`` filter
(``only`` | ``exclude`` | ``all``, default ``all``), the household can ask "what
did I pay?", "what was I given?" or "what did I consume?" from one query.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Literal

from sqlalchemy import Select, case, func, null, select, true
from sqlalchemy.orm import Session as DbSession

from app.core.money import ZERO
from app.models.core import Merchant
from app.models.prices import ProductPriceHistory
from app.models.products import MasterProduct
from app.models.supermarket import SupermarketReceipt, SupermarketReceiptItem
from app.services.supermarket import arithmetic, attributes, products_service

FsFilter = Literal["all", "only", "exclude"]
#: Axes the spend aggregate can be cut along. Each one partitions spend exactly
#: once — dietary tags do not, so they get their own function.
SpendDimension = Literal["category", "brand", "own_brand", "conservation", "presentation"]

#: A product nobody has annotated yet is a real answer, not a gap to hide
#: (ADR-0035's rule, applied to attributes).
UNSET_LABELS: dict[str, str] = {
    "brand": "Sem marca",
    "own_brand": "Produto por resolver",
    "conservation": "Conservação por indicar",
    "presentation": "Corte por indicar",
}

SHRINKFLATION_WINDOW_DAYS = 365
SHRINKFLATION_MIN_OBSERVATIONS = 3
#: The pack shrank faster than the price fell.
SHRINKFLATION_THRESHOLD = Decimal("-0.05")
SIGNAL_PLACES = Decimal("0.0001")
PER_KG_PLACES = Decimal("0.0001")


def _apply_fs(stmt: Select[Any], column: Any, fs: FsFilter) -> Select[Any]:
    if fs == "all":
        return stmt
    return stmt.where(column.is_(fs == "only"))


# --- Writing observations -----------------------------------------------------


def record_observations(db: DbSession, receipt: SupermarketReceipt) -> int:
    """Freeze one observation per resolved line on this receipt.

    Append-only: correcting a line later writes a **new** row beside the old one
    and never rewrites the past. Re-confirming an unchanged receipt writes
    nothing, which is what keeps the operation idempotent without a unique index
    that would forbid the correction in the first place.
    """
    if receipt.merchant_id is None or receipt.purchase_date is None:
        return 0

    written = 0
    for item in receipt.items:
        if item.is_deleted or item.master_product_id is None:
            continue

        # An Fs snapshot carries the notional value in **both** price columns.
        # A literal 0,00 would pull every paid-price trend for the product down.
        notional = arithmetic.notional_value_eur(
            is_fs=item.is_fs,
            unit_price_pvp_eur=item.unit_price_pvp_eur,
            quantity=item.quantity,
            paid_price_eur=item.paid_price_eur,
        )
        list_price = item.unit_price_pvp_eur if not item.is_fs else notional
        paid_price = item.paid_price_eur if not item.is_fs else notional
        weight = (
            item.weight_observed_kg
            if item.weight_observed_kg is not None
            else item.weight_listed_kg
        )
        weight = weight if weight and weight > 0 else None

        already_recorded = db.scalar(
            select(ProductPriceHistory.id).where(
                ProductPriceHistory.source_receipt_item_id == item.id,
                ProductPriceHistory.observed_on == receipt.purchase_date,
                ProductPriceHistory.list_price_eur == list_price,
                ProductPriceHistory.paid_price_eur == paid_price,
                ProductPriceHistory.weight_kg.is_(weight)
                if weight is None
                else ProductPriceHistory.weight_kg == weight,
            )
        )
        if already_recorded is not None:
            continue

        db.add(
            ProductPriceHistory(
                master_product_id=item.master_product_id,
                merchant_id=receipt.merchant_id,
                entity_id=receipt.entity_id,
                observed_on=receipt.purchase_date,
                is_fs=item.is_fs,
                weight_kg=weight,
                list_price_eur=list_price,
                paid_price_eur=paid_price,
                source_receipt_item_id=item.id,
            )
        )
        written += 1
    db.flush()
    return written


# --- Last known price ----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LastPrice:
    last_pvp_eur: Decimal | None
    last_price_per_kg_eur: Decimal | None
    last_weight_kg: Decimal | None
    last_observed_on: dt.date | None


def last_known_price(db: DbSession, master_product_id: uuid.UUID) -> LastPrice | None:
    """Derived from the newest observation — never stored, so it cannot drift.

    This is what pre-fills manual entry and Fs valuation: the pack price for
    packaged goods, the €/kg for anything sold by weight.
    """
    row = db.scalar(
        select(ProductPriceHistory)
        .where(ProductPriceHistory.master_product_id == master_product_id)
        .order_by(ProductPriceHistory.observed_on.desc(), ProductPriceHistory.created_at.desc())
        .limit(1)
    )
    if row is None:
        return None
    per_kg = (
        (row.list_price_eur / row.weight_kg).quantize(PER_KG_PLACES, rounding=ROUND_HALF_UP)
        if row.weight_kg
        else None
    )
    return LastPrice(
        last_pvp_eur=row.list_price_eur,
        last_price_per_kg_eur=per_kg,
        last_weight_kg=row.weight_kg,
        last_observed_on=row.observed_on,
    )


# --- Price evolution -----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PricePoint:
    observed_on: dt.date
    merchant_id: uuid.UUID
    merchant_name: str | None
    is_fs: bool
    weight_kg: Decimal | None
    list_price_eur: Decimal
    paid_price_eur: Decimal
    list_price_per_kg_eur: Decimal | None
    paid_price_per_kg_eur: Decimal | None


def price_history(
    db: DbSession,
    *,
    master_product_id: uuid.UUID,
    entity_ids: list[uuid.UUID],
    fs: FsFilter = "all",
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
) -> list[PricePoint]:
    stmt = (
        select(ProductPriceHistory, Merchant.name)
        .outerjoin(Merchant, Merchant.id == ProductPriceHistory.merchant_id)
        .where(
            ProductPriceHistory.master_product_id == master_product_id,
            ProductPriceHistory.entity_id.in_(entity_ids),
        )
        .order_by(ProductPriceHistory.observed_on)
    )
    stmt = _apply_fs(stmt, ProductPriceHistory.is_fs, fs)
    if date_from:
        stmt = stmt.where(ProductPriceHistory.observed_on >= date_from)
    if date_to:
        stmt = stmt.where(ProductPriceHistory.observed_on <= date_to)

    points: list[PricePoint] = []
    for row, merchant_name in db.execute(stmt).all():
        weight = row.weight_kg

        def per_kg(value: Decimal, weight: Decimal | None = weight) -> Decimal | None:
            if not weight:
                return None
            return (Decimal(value) / weight).quantize(PER_KG_PLACES, rounding=ROUND_HALF_UP)

        points.append(
            PricePoint(
                observed_on=row.observed_on,
                merchant_id=row.merchant_id,
                merchant_name=merchant_name,
                is_fs=row.is_fs,
                weight_kg=weight,
                list_price_eur=row.list_price_eur,
                paid_price_eur=row.paid_price_eur,
                list_price_per_kg_eur=per_kg(row.list_price_eur),
                paid_price_per_kg_eur=per_kg(row.paid_price_eur),
            )
        )
    return points


# --- Shrinkflation --------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ShrinkflationSignal:
    master_product_id: uuid.UUID
    canonical_name: str
    merchant_id: uuid.UUID
    merchant_name: str | None
    observations: int
    current_weight_kg: Decimal
    average_weight_kg: Decimal
    current_price_eur: Decimal
    average_price_eur: Decimal
    margin_signal: Decimal
    observed_on: dt.date


def shrinkflation(
    db: DbSession,
    *,
    entity_ids: list[uuid.UUID],
    fs: FsFilter = "all",
    today: dt.date | None = None,
    threshold: Decimal = SHRINKFLATION_THRESHOLD,
) -> list[ShrinkflationSignal]:
    """``(current_weight / avg_weight_12m) - (current_price / avg_price_12m)``.

    A score, not money, but decimal for reproducibility. Fires over a rolling
    12-month window with at least three prior observations of the same
    ``(product, merchant)`` pair.
    """
    reference = today or dt.date.today()
    window_start = reference - dt.timedelta(days=SHRINKFLATION_WINDOW_DAYS)

    stmt = (
        select(ProductPriceHistory, MasterProduct.canonical_name, Merchant.name)
        .join(MasterProduct, MasterProduct.id == ProductPriceHistory.master_product_id)
        .outerjoin(Merchant, Merchant.id == ProductPriceHistory.merchant_id)
        .where(
            ProductPriceHistory.entity_id.in_(entity_ids),
            ProductPriceHistory.observed_on >= window_start,
            ProductPriceHistory.weight_kg.is_not(None),
        )
        .order_by(ProductPriceHistory.observed_on)
    )
    stmt = _apply_fs(stmt, ProductPriceHistory.is_fs, fs)

    grouped: dict[tuple[uuid.UUID, uuid.UUID], list[tuple[Any, str, str | None]]] = {}
    for row, product_name, merchant_name in db.execute(stmt).all():
        grouped.setdefault((row.master_product_id, row.merchant_id), []).append(
            (row, product_name, merchant_name)
        )

    signals: list[ShrinkflationSignal] = []
    for (product_id, merchant_id), observations in grouped.items():
        if len(observations) <= SHRINKFLATION_MIN_OBSERVATIONS:
            continue
        *history, latest = observations
        current, product_name, merchant_name = latest

        average_weight = sum((Decimal(row.weight_kg) for row, _, _ in history), ZERO) / len(history)
        average_price = sum((Decimal(row.list_price_eur) for row, _, _ in history), ZERO) / len(
            history
        )
        if average_weight <= 0 or average_price <= 0:
            continue

        signal = (
            Decimal(current.weight_kg) / average_weight
            - Decimal(current.list_price_eur) / average_price
        ).quantize(SIGNAL_PLACES, rounding=ROUND_HALF_UP)
        if signal > threshold:
            continue

        signals.append(
            ShrinkflationSignal(
                master_product_id=product_id,
                canonical_name=product_name,
                merchant_id=merchant_id,
                merchant_name=merchant_name,
                observations=len(observations),
                current_weight_kg=Decimal(current.weight_kg),
                average_weight_kg=average_weight.quantize(Decimal("0.0001")),
                current_price_eur=Decimal(current.list_price_eur),
                average_price_eur=average_price.quantize(Decimal("0.01")),
                margin_signal=signal,
                observed_on=current.observed_on,
            )
        )
    signals.sort(key=lambda item: item.margin_signal)
    return signals


# --- Spend analytics ------------------------------------------------------------


def category_spend(
    db: DbSession,
    *,
    entity_ids: list[uuid.UUID],
    level: int = 1,
    dimension: SpendDimension = "category",
    fs: FsFilter = "all",
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    is_own_brand: bool | None = None,
    brand: str | None = None,
    conservation: str | None = None,
    presentation: str | None = None,
    dietary: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Spend by one axis of the product, over both measures.

    ``category`` is the original axis and keeps its ``category_id``; the others
    are product attributes and report ``None`` there, so one response shape
    serves every dimension and no client has to learn a second one. The point of
    the extra axes is that «€/kg da amêndoa» stops silently averaging laminada
    with palitada (ADR-0058).
    """
    from app.models.core import Category

    column = {
        1: MasterProduct.category_l1_id,
        2: MasterProduct.category_l2_id,
        3: MasterProduct.category_l3_id,
    }[level]

    paid = func.sum(SupermarketReceiptItem.paid_price_eur)
    # The two measures are identical on every non-Fs row, which is what lets Fs
    # articles join this view without a special case.
    notional = func.sum(
        case(
            (
                SupermarketReceiptItem.is_fs,
                SupermarketReceiptItem.unit_price_pvp_eur * SupermarketReceiptItem.quantity,
            ),
            else_=SupermarketReceiptItem.paid_price_eur,
        )
    )

    if dimension == "category":
        label: Any = Category.display_name_pt
    else:
        label = {
            "brand": MasterProduct.brand,
            # Three-way on purpose: a line that never resolved to a product has
            # no answer here, and calling it a manufacturer's brand would invent
            # one. It falls through to the unset label instead.
            "own_brand": case(
                (MasterProduct.is_own_brand.is_(True), "Marca branca"),
                (MasterProduct.is_own_brand.is_(False), "Marca de fabricante"),
                else_=null(),
            ),
            "conservation": MasterProduct.conservation,
            "presentation": MasterProduct.presentation,
        }[dimension]

    stmt = (
        select(
            column if dimension == "category" else null(),
            label,
            paid,
            notional,
            func.count(),
        )
        .join(SupermarketReceipt, SupermarketReceipt.id == SupermarketReceiptItem.receipt_id)
        # Outer, deliberately: a line that has not resolved to a product yet still
        # cost money, and dropping it would silently under-report spend.
        .outerjoin(MasterProduct, MasterProduct.id == SupermarketReceiptItem.master_product_id)
        .outerjoin(Category, Category.id == column)
        .where(
            SupermarketReceiptItem.entity_id.in_(entity_ids),
            SupermarketReceiptItem.is_deleted.is_(False),
            SupermarketReceipt.is_deleted.is_(False),
            SupermarketReceipt.status != "VOID",
        )
        .group_by(*((column, Category.display_name_pt) if dimension == "category" else (label,)))
        .order_by(paid.desc())
    )
    stmt = _apply_fs(stmt, SupermarketReceiptItem.is_fs, fs)
    stmt = products_service.apply_attribute_filters(
        stmt,
        is_own_brand=is_own_brand,
        brand=brand,
        conservation=conservation,
        presentation=presentation,
        dietary=dietary,
    )
    if date_from:
        stmt = stmt.where(SupermarketReceipt.purchase_date >= date_from)
    if date_to:
        stmt = stmt.where(SupermarketReceipt.purchase_date <= date_to)

    fallback = "Sem categoria" if dimension == "category" else UNSET_LABELS[dimension]
    return [
        {
            "category_id": row[0],
            "display_name_pt": attributes.label_for(dimension, row[1]) or fallback,
            "paid_eur": row[2] or ZERO,
            "notional_eur": row[3] or ZERO,
            "item_count": row[4],
        }
        for row in db.execute(stmt).all()
    ]


def dietary_spend(
    db: DbSession,
    *,
    entity_ids: list[uuid.UUID],
    fs: FsFilter = "all",
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
) -> list[dict[str, Any]]:
    """Spend per dietary tag, one row per tag.

    Its own function rather than a ``dimension`` of ``category_spend``: a product
    carries *several* tags, so the rows deliberately **do not** sum to the total
    — a Bio *and* vegan yoghurt is counted under both. Folding that into a view
    whose other axes partition spend would make the difference invisible.
    """
    # `render_derived` is what emits the `AS alias(tag)` column list; without it
    # Postgres never learns the name the GROUP BY refers to.
    tags = (
        func.jsonb_array_elements_text(MasterProduct.dietary_attributes)
        .table_valued("tag")
        .render_derived()
    )
    tag = tags.c.tag
    paid = func.sum(SupermarketReceiptItem.paid_price_eur)
    notional = func.sum(
        case(
            (
                SupermarketReceiptItem.is_fs,
                SupermarketReceiptItem.unit_price_pvp_eur * SupermarketReceiptItem.quantity,
            ),
            else_=SupermarketReceiptItem.paid_price_eur,
        )
    )
    stmt = (
        select(null(), tag, paid, notional, func.count())
        .select_from(SupermarketReceiptItem)
        .join(SupermarketReceipt, SupermarketReceipt.id == SupermarketReceiptItem.receipt_id)
        .join(MasterProduct, MasterProduct.id == SupermarketReceiptItem.master_product_id)
        .join(tags, true())
        .where(
            SupermarketReceiptItem.entity_id.in_(entity_ids),
            SupermarketReceiptItem.is_deleted.is_(False),
            SupermarketReceipt.is_deleted.is_(False),
            SupermarketReceipt.status != "VOID",
        )
        .group_by(tag)
        .order_by(paid.desc())
    )
    stmt = _apply_fs(stmt, SupermarketReceiptItem.is_fs, fs)
    if date_from:
        stmt = stmt.where(SupermarketReceipt.purchase_date >= date_from)
    if date_to:
        stmt = stmt.where(SupermarketReceipt.purchase_date <= date_to)

    return [
        {
            "category_id": None,
            "display_name_pt": row[1],
            "paid_eur": row[2] or ZERO,
            "notional_eur": row[3] or ZERO,
            "item_count": row[4],
        }
        for row in db.execute(stmt).all()
    ]


def loyalty_summary(
    db: DbSession,
    *,
    entity_ids: list[uuid.UUID],
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
) -> list[dict[str, Any]]:
    """A ``GROUP BY`` over ``SupermarketReceipt``, not a screen of its own to manage
    (Decision #37)."""
    stmt = (
        select(
            SupermarketReceipt.loyalty_scheme,
            SupermarketReceipt.loyalty_card_masked,
            func.count(),
            func.sum(SupermarketReceipt.loyalty_accrued_eur),
            func.sum(SupermarketReceipt.loyalty_discount_eur),
            func.min(SupermarketReceipt.purchase_date),
            func.max(SupermarketReceipt.purchase_date),
        )
        .where(
            SupermarketReceipt.entity_id.in_(entity_ids),
            SupermarketReceipt.is_deleted.is_(False),
            SupermarketReceipt.status != "VOID",
            SupermarketReceipt.loyalty_scheme.is_not(None),
        )
        .group_by(SupermarketReceipt.loyalty_scheme, SupermarketReceipt.loyalty_card_masked)
        .order_by(func.sum(SupermarketReceipt.loyalty_discount_eur).desc())
    )
    if date_from:
        stmt = stmt.where(SupermarketReceipt.purchase_date >= date_from)
    if date_to:
        stmt = stmt.where(SupermarketReceipt.purchase_date <= date_to)

    return [
        {
            "scheme": row[0],
            "card_masked": row[1],
            "receipt_count": row[2],
            "accrued_eur": row[3] or ZERO,
            "discount_eur": row[4] or ZERO,
            "first_purchase": row[5],
            "last_purchase": row[6],
        }
        for row in db.execute(stmt).all()
    ]
