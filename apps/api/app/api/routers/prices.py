"""Money over time: €/kg trends, shrinkflation, category spend, loyalty and the
receipt↔transaction link.

Every endpoint here accepts the ``fs`` filter (``all`` | ``only`` | ``exclude``),
so the household can ask "what did I pay?", "what was I given?" or "what did I
consume?" from the same surface.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import uuid
from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Query, Response
from sqlalchemy import select

from app.api.deps import CurrentAuth, Db, Writer, household_entity_ids
from app.core.errors import NotFound
from app.models.core import Merchant
from app.models.receipts import Receipt
from app.schemas.common import Ok
from app.schemas.prices import (
    CategorySpendOut,
    LinkRequest,
    LoyaltyAllocationOut,
    LoyaltyGroupOut,
    PriceHistoryOut,
    PricePointOut,
    ReceiptLinkOut,
    ShrinkflationOut,
    TagsUpdate,
)
from app.schemas.products import FsFilter
from app.services.receipts import ledger, prices_service, products_service
from app.services.receipts import service as receipts

router = APIRouter(prefix="/receipts/analytics", tags=["receipts"])
price_router = APIRouter(prefix="/master-products", tags=["receipts"])
link_router = APIRouter(prefix="/receipts", tags=["receipts"])

LEDGER_ABSENT_MESSAGE = (
    "O livro-razão bancário chega com o módulo de Banca. "
    "Até lá, a fatura fica registada sem ligação ao extrato."
)


def _scope(db: Db, ctx: CurrentAuth) -> list[uuid.UUID]:
    return [ctx.active_entity_id] if ctx.active_entity_id else household_entity_ids(db, ctx)


# --- Price evolution (UX-1.9) --------------------------------------------------


@price_router.get("/{product_id}/price-history", response_model=PriceHistoryOut)
def price_history(
    product_id: uuid.UUID,
    ctx: CurrentAuth,
    db: Db,
    fs: FsFilter = "all",
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
) -> PriceHistoryOut:
    product = products_service.get_product(db, product_id)
    scope = _scope(db, ctx)
    points = prices_service.price_history(
        db,
        master_product_id=product_id,
        entity_ids=scope,
        fs=fs,
        date_from=date_from,
        date_to=date_to,
    )
    signals = [
        signal
        for signal in prices_service.shrinkflation(db, entity_ids=scope, fs=fs)
        if signal.master_product_id == product_id
    ]
    return PriceHistoryOut(
        master_product_id=product.id,
        canonical_name=product.canonical_name,
        sold_by_weight=product.sold_by_weight,
        points=[PricePointOut(**asdict(point)) for point in points],
        shrinkflation=[ShrinkflationOut(**asdict(signal)) for signal in signals],
    )


@price_router.get("/{product_id}/price-history.csv")
def price_history_csv(
    product_id: uuid.UUID,
    ctx: CurrentAuth,
    db: Db,
    fs: FsFilter = "all",
) -> Response:
    product = products_service.get_product(db, product_id)
    points = prices_service.price_history(
        db, master_product_id=product_id, entity_ids=_scope(db, ctx), fs=fs
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(
        [
            "data",
            "comerciante",
            "fs",
            "peso_kg",
            "preco_tabela_eur",
            "preco_pago_eur",
            "eur_por_kg_tabela",
            "eur_por_kg_pago",
        ]
    )
    for point in points:
        writer.writerow(
            [
                point.observed_on.isoformat(),
                point.merchant_name or "",
                "sim" if point.is_fs else "nao",
                point.weight_kg or "",
                point.list_price_eur,
                point.paid_price_eur,
                point.list_price_per_kg_eur or "",
                point.paid_price_per_kg_eur or "",
            ]
        )
    filename = f"precos-{product.canonical_name[:40].replace(' ', '-')}.csv"
    return Response(
        content=buffer.getvalue().encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --- Analytics -----------------------------------------------------------------


@router.get("/shrinkflation", response_model=list[ShrinkflationOut])
def shrinkflation(
    ctx: CurrentAuth,
    db: Db,
    fs: FsFilter = "all",
) -> list[ShrinkflationOut]:
    """Products whose pack shrank faster than their price fell."""
    return [
        ShrinkflationOut(**asdict(signal))
        for signal in prices_service.shrinkflation(db, entity_ids=_scope(db, ctx), fs=fs)
    ]


@router.get("/category-spend", response_model=list[CategorySpendOut])
def category_spend(
    ctx: CurrentAuth,
    db: Db,
    level: Annotated[int, Query(ge=1, le=3)] = 1,
    fs: FsFilter = "all",
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
) -> list[CategorySpendOut]:
    return [
        CategorySpendOut(**row)
        for row in prices_service.category_spend(
            db,
            entity_ids=_scope(db, ctx),
            level=level,
            fs=fs,
            date_from=date_from,
            date_to=date_to,
        )
    ]


@router.get("/loyalty", response_model=list[LoyaltyGroupOut])
def loyalty(
    ctx: CurrentAuth,
    db: Db,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
) -> list[LoyaltyGroupOut]:
    return [
        LoyaltyGroupOut(**row)
        for row in prices_service.loyalty_summary(
            db, entity_ids=_scope(db, ctx), date_from=date_from, date_to=date_to
        )
    ]


@router.get("/loyalty/receipts", response_model=list[LoyaltyAllocationOut])
def loyalty_receipts(
    ctx: CurrentAuth,
    db: Db,
    scheme: str | None = None,
    card_masked: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[LoyaltyAllocationOut]:
    """The per-receipt allocation behind a scheme's totals."""
    stmt = (
        select(Receipt, Merchant.name)
        .outerjoin(Merchant, Merchant.id == Receipt.merchant_id)
        .where(
            Receipt.entity_id.in_(_scope(db, ctx)),
            Receipt.is_deleted.is_(False),
            Receipt.status != "VOID",
            Receipt.loyalty_scheme.is_not(None),
        )
        .order_by(Receipt.purchase_date.desc().nullslast())
        .limit(limit)
    )
    if scheme:
        stmt = stmt.where(Receipt.loyalty_scheme == scheme)
    if card_masked:
        stmt = stmt.where(Receipt.loyalty_card_masked == card_masked)

    rows = []
    for receipt, merchant_name in db.execute(stmt).all():
        allocated = sum(
            (item.invoice_allocated_discount_eur for item in receipt.items if not item.is_deleted),
            receipt.total_eur * 0,
        )
        rows.append(
            LoyaltyAllocationOut(
                receipt_id=receipt.id,
                purchase_date=receipt.purchase_date,
                merchant_name=merchant_name,
                total_eur=receipt.total_eur,
                loyalty_discount_eur=receipt.loyalty_discount_eur,
                loyalty_accrued_eur=receipt.loyalty_accrued_eur,
                allocated_across_items_eur=allocated,
            )
        )
    return rows


# --- The ledger link (FR-1.14) --------------------------------------------------


@link_router.get("/{receipt_id}/link", response_model=ReceiptLinkOut)
def get_link(receipt_id: uuid.UUID, ctx: CurrentAuth, db: Db) -> ReceiptLinkOut:
    receipts.get_receipt(db, receipt_id)
    link = ledger.existing_link(db, receipt_id)
    return ReceiptLinkOut(
        ledger_available=ledger.is_available(),
        message=None if ledger.is_available() else LEDGER_ABSENT_MESSAGE,
        link_id=link.id if link else None,
        transaction_id=link.to_id if link else None,
        status=link.status if link else None,
        confidence=link.confidence if link else None,
        decision_reasons=link.decision_reasons if link else [],
    )


@link_router.post("/{receipt_id}/link", response_model=ReceiptLinkOut)
def create_link(receipt_id: uuid.UUID, payload: LinkRequest, ctx: Writer, db: Db) -> ReceiptLinkOut:
    """Manual linking, reusing the shared transaction picker on the client."""
    receipt = receipts.get_receipt(db, receipt_id)
    link = ledger.link_manually(
        db, receipt, transaction_id=payload.transaction_id, actor_user_id=ctx.user.id
    )
    return ReceiptLinkOut(
        ledger_available=ledger.is_available(),
        link_id=link.id,
        transaction_id=link.to_id,
        status=link.status,
        confidence=link.confidence,
        decision_reasons=link.decision_reasons,
    )


@link_router.delete("/{receipt_id}/link", response_model=Ok)
def delete_link(receipt_id: uuid.UUID, ctx: Writer, db: Db) -> Ok:
    receipts.get_receipt(db, receipt_id)
    ledger.unlink(db, receipt_id)
    return Ok(message="Ligação removida.")


# --- Tags (FR-1.5) ---------------------------------------------------------------


@link_router.put("/{receipt_id}/tags", response_model=Ok)
def set_receipt_tags(receipt_id: uuid.UUID, payload: TagsUpdate, ctx: Writer, db: Db) -> Ok:
    """Open labels. They change no total — that is what separates them from ``is_fs``."""
    receipt = receipts.get_receipt(db, receipt_id)
    receipts.update_receipt(db, receipt, {"tags": payload.tags}, actor_user_id=ctx.user.id)
    return Ok(message="Etiquetas atualizadas.")


@link_router.put("/{receipt_id}/items/{item_id}/tags", response_model=Ok)
def set_item_tags(
    receipt_id: uuid.UUID, item_id: uuid.UUID, payload: TagsUpdate, ctx: Writer, db: Db
) -> Ok:
    item = receipts.get_item(db, item_id)
    if item.receipt_id != receipt_id:
        raise NotFound("Linha não pertence a esta fatura.")
    receipts.update_item(db, item, {"tags": payload.tags}, actor_user_id=ctx.user.id)
    return Ok(message="Etiquetas atualizadas.")


routers = (router, price_router, link_router)
