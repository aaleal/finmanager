"""Module 1 HTTP surface. Business rules live in ``app/services/supermarket``."""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal
from typing import Annotated, Any, NamedTuple

from fastapi import APIRouter, File, Header, Query, UploadFile
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session as DbSession

from app.api.deps import CurrentAuth, Db, Writer, household_entity_ids, resolve_write_entity
from app.core.errors import NotFound, ValidationError
from app.core.security import signed_document_url
from app.models.core import Document, Merchant, ProcessingJob
from app.models.products import MasterProduct
from app.models.supermarket import MerchantParserProfile, SupermarketReceipt, SupermarketReceiptItem
from app.schemas.common import Ok, Page
from app.schemas.supermarket import (
    FsFilter,
    FsItemCreate,
    ItemProductAssignment,
    ParserOption,
    ParserProfileIn,
    ParserProfileOut,
    ParserProfileUpdate,
    ProductSummary,
    ProfileTestResult,
    QueueEntry,
    ReceiptDerived,
    ReceiptDetail,
    ReceiptItemOut,
    ReceiptItemUpdate,
    ReceiptSummary,
    ReceiptUpdate,
    StatusBoard,
    UploadedReceipt,
    UploadResponse,
    VoidRequest,
)
from app.services import documents
from app.services.supermarket import arithmetic, parsers, pipeline, products_service
from app.services.supermarket import service as supermarket

router = APIRouter(prefix="/supermarket", tags=["supermarket"])
profiles_router = APIRouter(prefix="/parser-profiles", tags=["supermarket"])
# NOT nested under /supermarket: that prefix already hosts GET /supermarket/{receipt_id}
# on `router` (a different APIRouter, registered first in `routers` below), and Starlette
# matches routes in registration order — `/supermarket/items` would be swallowed by
# `{receipt_id}` (treating "items" as the id) before ever reaching this router.
items_router = APIRouter(prefix="/supermarket-items", tags=["supermarket"])


# --- Serialization ------------------------------------------------------------


def _merchant_names(db: DbSession, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not ids:
        return {}
    rows = db.execute(select(Merchant.id, Merchant.name).where(Merchant.id.in_(ids))).all()
    return {row[0]: row[1] for row in rows}


def _profile_names(db: DbSession, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not ids:
        return {}
    rows = db.execute(
        select(MerchantParserProfile.id, MerchantParserProfile.name).where(
            MerchantParserProfile.id.in_(ids)
        )
    ).all()
    return {row[0]: row[1] for row in rows}


class ProductDisplay(NamedTuple):
    """What a line shows once it has resolved: the name, the path, the pricing basis."""

    canonical_name: str
    brand: str | None
    category_path: str | None
    category_status: str
    sold_by_weight: bool
    pack_weights: frozenset[Decimal]


def item_out(
    item: SupermarketReceiptItem, *, products: dict[uuid.UUID, ProductDisplay] | None = None
) -> ReceiptItemOut:
    payload = ReceiptItemOut.model_validate(item)
    for key, value in supermarket.item_derived(item).items():
        setattr(payload, key, value)
    # The user sees the product's canonical name; `description_raw` is the audit
    # trail against paper, and `description_norm` is never displayed at all.
    product = (products or {}).get(item.master_product_id) if item.master_product_id else None
    payload.display_name = product.canonical_name if product else item.description_raw
    payload.category_path = product.category_path if product else None
    payload.category_status = product.category_status if product else None
    payload.sold_by_weight = bool(product and product.sold_by_weight)

    # Matched by value, at the gram: with unique weights per product there is
    # exactly one format a line can mean, so no reference has to be stored.
    listed = products_service.round_to_the_gram(item.weight_listed_kg)
    if product is not None and listed is not None and not product.sold_by_weight:
        payload.pack_weight_is_known = listed in product.pack_weights
    return payload


def _product_display(db: DbSession, ids: set[uuid.UUID]) -> dict[uuid.UUID, ProductDisplay]:
    """One pass over the products a page of lines resolved to, paths memoized."""
    if not ids:
        return {}
    paths: dict[uuid.UUID, str | None] = {}
    display: dict[uuid.UUID, ProductDisplay] = {}
    for product in db.scalars(select(MasterProduct).where(MasterProduct.id.in_(ids))):
        category_id = product.category_id
        if category_id is not None and category_id not in paths:
            paths[category_id] = products_service.category_path(db, category_id)
        display[product.id] = ProductDisplay(
            canonical_name=product.canonical_name,
            brand=product.brand,
            category_path=paths.get(category_id) if category_id is not None else None,
            category_status=product.category_status,
            sold_by_weight=product.sold_by_weight,
            pack_weights=frozenset(products_service.pack_weights(product)),
        )
    return display


def _purchase_span(
    db: DbSession, ids: set[uuid.UUID]
) -> dict[uuid.UUID, tuple[dt.date | None, dt.date | None]]:
    if not ids:
        return {}
    rows = db.execute(
        select(
            SupermarketReceiptItem.master_product_id,
            func.min(SupermarketReceipt.purchase_date),
            func.max(SupermarketReceipt.purchase_date),
        )
        .join(SupermarketReceipt, SupermarketReceipt.id == SupermarketReceiptItem.receipt_id)
        .where(
            SupermarketReceiptItem.master_product_id.in_(ids),
            SupermarketReceiptItem.is_deleted.is_(False),
        )
        .group_by(SupermarketReceiptItem.master_product_id)
    ).all()
    return {row[0]: (row[1], row[2]) for row in rows}


def summary_out(
    db: DbSession,
    receipt: SupermarketReceipt,
    *,
    names: dict[uuid.UUID, str] | None = None,
    profiles: dict[uuid.UUID, str] | None = None,
) -> ReceiptSummary:
    totals = supermarket.totals_for(db, receipt)
    payload = ReceiptSummary.model_validate(receipt)
    payload.merchant_name = (names or {}).get(receipt.merchant_id) if receipt.merchant_id else None
    payload.parser_profile_name = (
        (profiles or {}).get(receipt.parser_profile_id) if receipt.parser_profile_id else None
    )
    payload.fs_value_eur = totals.fs_value_eur
    payload.fs_item_count = totals.fs_item_count
    payload.printed_item_count = totals.printed_item_count
    payload.notional_total_eur = totals.notional_total_eur
    payload.is_reconciled = totals.is_reconciled
    return payload


def detail_out(
    db: DbSession, receipt: SupermarketReceipt, *, fs: FsFilter = "all"
) -> ReceiptDetail:
    names = _merchant_names(db, {receipt.merchant_id} if receipt.merchant_id else set())
    profiles = _profile_names(
        db, {receipt.parser_profile_id} if receipt.parser_profile_id else set()
    )
    base = summary_out(db, receipt, names=names, profiles=profiles)
    items = [
        item
        for item in receipt.items
        if not item.is_deleted and (fs == "all" or (fs == "only") == item.is_fs)
    ]
    document = db.get(Document, receipt.document_id) if receipt.document_id else None
    products = _product_display(db, {i.master_product_id for i in items if i.master_product_id})
    return ReceiptDetail(
        **base.model_dump(),
        processing_job_id=receipt.processing_job_id,
        import_batch_id=receipt.import_batch_id,
        atcud_valid=receipt.atcud_valid,
        atcud_reason=receipt.atcud_reason,
        parsed_payment_methods=receipt.parsed_payment_methods,
        loyalty_card_masked=receipt.loyalty_card_masked,
        loyalty_accrued_eur=receipt.loyalty_accrued_eur,
        loyalty_discount_eur=receipt.loyalty_discount_eur,
        decision_reasons=receipt.decision_reasons,
        notes=receipt.notes,
        void_reason=receipt.void_reason,
        document_url=signed_document_url(document.id) if document else None,
        document_mime_type=document.mime_type if document else None,
        document_filename=document.original_filename if document else None,
        items=[item_out(item, products=products) for item in items],
        derived=ReceiptDerived(**supermarket.derived(db, receipt)),
    )


def _scope(db: DbSession, ctx: CurrentAuth) -> list[uuid.UUID]:
    return [ctx.active_entity_id] if ctx.active_entity_id else household_entity_ids(db, ctx)


# --- Upload & queue -----------------------------------------------------------


@router.post("", response_model=UploadResponse, status_code=201)
def upload(
    ctx: Writer,
    db: Db,
    files: Annotated[list[UploadFile], File()],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    entity_id: uuid.UUID | None = None,
    parser_profile_id: uuid.UUID | None = None,
) -> UploadResponse:
    """Accept **one or many** invoices; each becomes its own job and receipt.

    One bad scan never blocks the batch — the failure is recorded on its own job
    row and is retryable from the stored document, without a re-upload.

    ``parser_profile_id`` forces a profile instead of letting detection choose;
    either way the profile that actually ran is recorded on the receipt and shown
    in the queue (UX-1.1).
    """
    target_entity = resolve_write_entity(db, ctx, entity_id)
    if parser_profile_id is not None:
        supermarket.get_profile(db, parser_profile_id)
    key = idempotency_key or uuid.uuid4().hex
    results: list[UploadedReceipt] = []

    for index, upload_file in enumerate(files):
        data = upload_file.file.read()
        try:
            receipt, job, created = supermarket.create_from_upload(
                db,
                data=data,
                filename=upload_file.filename,
                entity_id=target_entity,
                actor_user_id=ctx.user.id,
                idempotency_key=f"{key}:{index}",
            )
        except ValidationError as exc:
            results.append(
                UploadedReceipt(
                    receipt_id=uuid.UUID(int=0),
                    processing_job_id=uuid.UUID(int=0),
                    filename=upload_file.filename,
                    created=False,
                    message=exc.detail,
                )
            )
            continue

        if created:
            supermarket.parse_receipt(
                db, receipt, actor_user_id=ctx.user.id, forced_profile_id=parser_profile_id
            )
        results.append(
            UploadedReceipt(
                receipt_id=receipt.id,
                processing_job_id=job.id,
                filename=upload_file.filename,
                created=created,
                message=None if created else "Esta fatura já tinha sido carregada.",
            )
        )

    return UploadResponse(items=results)


@router.get("/queue", response_model=list[QueueEntry])
def queue(ctx: CurrentAuth, db: Db, status: str | None = None) -> list[QueueEntry]:
    scope = _scope(db, ctx)
    stmt = (
        select(ProcessingJob)
        .where(ProcessingJob.job_type.like("supermarket.%"), ProcessingJob.entity_id.in_(scope))
        .order_by(ProcessingJob.created_at.desc())
        .limit(200)
    )
    if status:
        stmt = stmt.where(ProcessingJob.status == status)
    jobs = db.scalars(stmt).all()

    receipt_ids = {
        uuid.UUID(job.payload["receipt_id"]) for job in jobs if job.payload.get("receipt_id")
    }
    rows = (
        db.scalars(select(SupermarketReceipt).where(SupermarketReceipt.id.in_(receipt_ids))).all()
        if receipt_ids
        else []
    )
    by_id = {row.id: row for row in rows}
    names = _merchant_names(db, {r.merchant_id for r in rows if r.merchant_id})
    profile_names = _profile_names(db, {r.parser_profile_id for r in rows if r.parser_profile_id})
    document_names = (
        {
            row[0]: row[1]
            for row in db.execute(
                select(Document.id, Document.original_filename).where(
                    Document.id.in_({r.document_id for r in rows if r.document_id})
                )
            ).all()
        }
        if rows
        else {}
    )

    entries: list[QueueEntry] = []
    for job in jobs:
        raw_id = job.payload.get("receipt_id")
        receipt = by_id.get(uuid.UUID(raw_id)) if raw_id else None
        entries.append(
            QueueEntry(
                receipt_id=receipt.id if receipt else None,
                processing_job_id=job.id,
                status=receipt.status if receipt else "UPLOADED",
                job_status=job.status,
                attempts=job.attempts,
                max_attempts=job.max_attempts,
                last_error=job.last_error,
                parser_profile_name=(
                    profile_names.get(receipt.parser_profile_id)
                    if receipt and receipt.parser_profile_id
                    else None
                ),
                merchant_name=(
                    names.get(receipt.merchant_id) if receipt and receipt.merchant_id else None
                ),
                filename=(
                    document_names.get(receipt.document_id)
                    if receipt and receipt.document_id
                    else None
                ),
                confidence=receipt.confidence if receipt else None,
                created_at=job.created_at,
                completed_at=job.completed_at,
            )
        )
    return entries


@router.get("/status", response_model=StatusBoard)
def status_board(ctx: CurrentAuth, db: Db) -> StatusBoard:
    return StatusBoard(**supermarket.status_counts(db, _scope(db, ctx)))


# --- Listing ------------------------------------------------------------------


@router.get("", response_model=Page[ReceiptSummary])
def list_receipts(
    ctx: CurrentAuth,
    db: Db,
    search: str | None = None,
    merchant_id: uuid.UUID | None = None,
    status: str | None = None,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    fs: FsFilter = "all",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 25,
) -> Page[ReceiptSummary]:
    stmt = select(SupermarketReceipt).where(
        SupermarketReceipt.entity_id.in_(_scope(db, ctx)), SupermarketReceipt.is_deleted.is_(False)
    )
    if merchant_id:
        stmt = stmt.where(SupermarketReceipt.merchant_id == merchant_id)
    if status:
        stmt = stmt.where(SupermarketReceipt.status == status)
    if date_from:
        stmt = stmt.where(SupermarketReceipt.purchase_date >= date_from)
    if date_to:
        stmt = stmt.where(SupermarketReceipt.purchase_date <= date_to)
    if search:
        stmt = stmt.where(
            or_(
                SupermarketReceipt.atcud_code.ilike(f"%{search}%"),
                SupermarketReceipt.notes.ilike(f"%{search}%"),
            )
        )
    if fs != "all":
        exists = select(SupermarketReceiptItem.id).where(
            SupermarketReceiptItem.receipt_id == SupermarketReceipt.id,
            SupermarketReceiptItem.is_fs.is_(True),
            SupermarketReceiptItem.is_deleted.is_(False),
        )
        stmt = stmt.where(exists.exists() if fs == "only" else ~exists.exists())

    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = db.scalars(
        stmt.order_by(
            SupermarketReceipt.purchase_date.desc().nullslast(), SupermarketReceipt.id.desc()
        )
        .limit(page_size)
        .offset((page - 1) * page_size)
    ).all()
    names = _merchant_names(db, {r.merchant_id for r in rows if r.merchant_id})
    profile_names = _profile_names(db, {r.parser_profile_id for r in rows if r.parser_profile_id})
    return Page(
        items=[summary_out(db, row, names=names, profiles=profile_names) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{receipt_id}", response_model=ReceiptDetail)
def get_receipt(
    receipt_id: uuid.UUID, ctx: CurrentAuth, db: Db, fs: FsFilter = "all"
) -> ReceiptDetail:
    return detail_out(db, supermarket.get_receipt(db, receipt_id), fs=fs)


# --- Editing ------------------------------------------------------------------


@router.patch("/{receipt_id}", response_model=ReceiptDetail)
def update_receipt(
    receipt_id: uuid.UUID, payload: ReceiptUpdate, ctx: Writer, db: Db
) -> ReceiptDetail:
    receipt = supermarket.get_receipt(db, receipt_id)
    supermarket.update_receipt(
        db,
        receipt,
        payload.model_dump(exclude_unset=True, exclude_none=True),
        actor_user_id=ctx.user.id,
    )
    return detail_out(db, receipt)


@router.patch("/{receipt_id}/items/{item_id}", response_model=ReceiptDetail)
def update_item(
    receipt_id: uuid.UUID, item_id: uuid.UUID, payload: ReceiptItemUpdate, ctx: Writer, db: Db
) -> ReceiptDetail:
    item = supermarket.get_item(db, item_id)
    if item.receipt_id != receipt_id:
        raise NotFound("Linha não pertence a esta fatura.")
    supermarket.update_item(
        db, item, payload.model_dump(exclude_unset=True), actor_user_id=ctx.user.id
    )
    return detail_out(db, supermarket.get_receipt(db, receipt_id))


@router.post("/{receipt_id}/items", response_model=ReceiptDetail, status_code=201)
def add_item(receipt_id: uuid.UUID, payload: FsItemCreate, ctx: Writer, db: Db) -> ReceiptDetail:
    """Append an article by hand. An Fs row leaves every printed figure unchanged."""
    receipt = supermarket.get_receipt(db, receipt_id)
    supermarket.append_item(
        db,
        receipt,
        description_raw=payload.description_raw,
        unit_price_pvp_eur=payload.unit_price_pvp_eur,
        quantity=payload.quantity,
        unit=payload.unit,
        is_fs=payload.is_fs,
        line_no=payload.line_no,
        promo_discount_eur=payload.promo_discount_eur,
        notional_value_source=payload.notional_value_source,
        notes=payload.notes,
        actor_user_id=ctx.user.id,
    )
    return detail_out(db, receipt)


@router.delete("/{receipt_id}/items/{item_id}", response_model=ReceiptDetail)
def delete_item(receipt_id: uuid.UUID, item_id: uuid.UUID, ctx: Writer, db: Db) -> ReceiptDetail:
    item = supermarket.get_item(db, item_id)
    if item.receipt_id != receipt_id:
        raise NotFound("Linha não pertence a esta fatura.")
    supermarket.delete_item(db, item, actor_user_id=ctx.user.id)
    return detail_out(db, supermarket.get_receipt(db, receipt_id))


# --- Lifecycle ----------------------------------------------------------------


@router.post("/{receipt_id}/reparse", response_model=ReceiptDetail)
def reparse(
    receipt_id: uuid.UUID,
    ctx: Writer,
    db: Db,
    parser_profile_id: uuid.UUID | None = None,
) -> ReceiptDetail:
    receipt = supermarket.get_receipt(db, receipt_id)
    supermarket.parse_receipt(
        db, receipt, actor_user_id=ctx.user.id, forced_profile_id=parser_profile_id
    )
    return detail_out(db, receipt)


@router.post("/{receipt_id}/confirm", response_model=ReceiptDetail)
def confirm(receipt_id: uuid.UUID, ctx: Writer, db: Db) -> ReceiptDetail:
    receipt = supermarket.get_receipt(db, receipt_id)
    supermarket.confirm(db, receipt, actor_user_id=ctx.user.id)
    return detail_out(db, receipt)


@router.post("/{receipt_id}/reopen", response_model=ReceiptDetail)
def reopen(receipt_id: uuid.UUID, ctx: Writer, db: Db) -> ReceiptDetail:
    """Back to review. The observations already frozen are left untouched."""
    receipt = supermarket.get_receipt(db, receipt_id)
    supermarket.reopen(db, receipt, actor_user_id=ctx.user.id)
    return detail_out(db, receipt)


@router.post("/{receipt_id}/confirm-categories", response_model=ReceiptDetail)
def confirm_categories(receipt_id: uuid.UUID, ctx: Writer, db: Db) -> ReceiptDetail:
    """Promote every ``AUTO`` classification on this receipt to ``VALIDATED``."""
    receipt = supermarket.get_receipt(db, receipt_id)
    supermarket.confirm_categories(db, receipt, actor_user_id=ctx.user.id)
    return detail_out(db, receipt)


@router.post("/{receipt_id}/void", response_model=ReceiptDetail)
def void(receipt_id: uuid.UUID, payload: VoidRequest, ctx: Writer, db: Db) -> ReceiptDetail:
    receipt = supermarket.get_receipt(db, receipt_id)
    supermarket.void(db, receipt, reason=payload.reason, actor_user_id=ctx.user.id)
    return detail_out(db, receipt)


# --- Level 2: one row per purchased article (UX-1.4) --------------------------


def _item_scope(
    db: DbSession,
    ctx: CurrentAuth,
    *,
    search: str | None,
    merchant_id: uuid.UUID | None,
    date_from: dt.date | None,
    date_to: dt.date | None,
    fs: FsFilter,
    product_flag: str | None,
    master_product_id: uuid.UUID | None = None,
) -> Any:
    """The filters both article views share, so the two can never disagree."""
    stmt = (
        select(SupermarketReceiptItem)
        .join(SupermarketReceipt, SupermarketReceipt.id == SupermarketReceiptItem.receipt_id)
        .where(
            SupermarketReceiptItem.entity_id.in_(_scope(db, ctx)),
            SupermarketReceiptItem.is_deleted.is_(False),
            SupermarketReceipt.is_deleted.is_(False),
            SupermarketReceipt.status != "VOID",
        )
    )
    if search:
        stmt = stmt.where(SupermarketReceiptItem.description_norm.ilike(f"%{search.upper()}%"))
    if merchant_id:
        stmt = stmt.where(SupermarketReceipt.merchant_id == merchant_id)
    if date_from:
        stmt = stmt.where(SupermarketReceipt.purchase_date >= date_from)
    if date_to:
        stmt = stmt.where(SupermarketReceipt.purchase_date <= date_to)
    if fs != "all":
        stmt = stmt.where(SupermarketReceiptItem.is_fs.is_(fs == "only"))
    if product_flag:
        stmt = stmt.where(SupermarketReceiptItem.product_flag == product_flag)
    if master_product_id:
        stmt = stmt.where(SupermarketReceiptItem.master_product_id == master_product_id)
    return stmt


@items_router.get("", response_model=Page[ReceiptItemOut])
def list_items(
    ctx: CurrentAuth,
    db: Db,
    search: str | None = None,
    merchant_id: uuid.UUID | None = None,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    fs: FsFilter = "all",
    product_flag: str | None = None,
    master_product_id: uuid.UUID | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> Page[ReceiptItemOut]:
    stmt = _item_scope(
        db,
        ctx,
        search=search,
        merchant_id=merchant_id,
        date_from=date_from,
        date_to=date_to,
        fs=fs,
        product_flag=product_flag,
        master_product_id=master_product_id,
    )

    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = db.scalars(
        stmt.order_by(
            SupermarketReceipt.purchase_date.desc().nullslast(), SupermarketReceiptItem.line_no
        )
        .limit(page_size)
        .offset((page - 1) * page_size)
    ).all()
    products = _product_display(db, {r.master_product_id for r in rows if r.master_product_id})
    return Page(
        items=[item_out(row, products=products) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@items_router.patch("/{item_id}/product", response_model=ReceiptItemOut)
def reassign_item_product(
    item_id: uuid.UUID, payload: ItemProductAssignment, ctx: Writer, db: Db
) -> ReceiptItemOut:
    """Correcting a line here is also how the merchant's vocabulary is learned."""
    item = supermarket.get_item(db, item_id)
    if item.entity_id not in _scope(db, ctx):
        raise NotFound("Linha não encontrada.")
    supermarket.reassign_item_product(
        db, item, master_product_id=payload.master_product_id, actor_user_id=ctx.user.id
    )
    return item_out(item, products=_product_display(db, {payload.master_product_id}))


@items_router.get("/summary", response_model=Page[ProductSummary])
def summarise_items(
    ctx: CurrentAuth,
    db: Db,
    search: str | None = None,
    merchant_id: uuid.UUID | None = None,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    fs: FsFilter = "all",
    product_flag: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> Page[ProductSummary]:
    """One row per product: how much of it, how often, and at what €/kg."""
    scope = _item_scope(
        db,
        ctx,
        search=search,
        merchant_id=merchant_id,
        date_from=date_from,
        date_to=date_to,
        fs=fs,
        product_flag=product_flag,
    ).subquery()

    weight = func.coalesce(scope.c.weight_observed_kg, scope.c.weight_listed_kg)
    # Only lines that actually carry a weight may enter the €/kg, numerator and
    # denominator alike — a paid price with no weight would skew the quotient.
    weighted_paid = case((weight > 0, scope.c.paid_price_eur), else_=None)
    notional = case(
        (scope.c.is_fs, scope.c.unit_price_pvp_eur * scope.c.quantity),
        else_=scope.c.paid_price_eur,
    )

    stmt = (
        select(
            scope.c.master_product_id,
            func.count().label("line_count"),
            func.count(func.distinct(scope.c.receipt_id)).label("receipt_count"),
            func.sum(scope.c.quantity).label("total_quantity"),
            func.sum(weight).label("total_weight_kg"),
            func.sum(scope.c.paid_price_eur).label("total_paid_eur"),
            func.sum(notional).label("total_notional_eur"),
            func.sum(weighted_paid).label("weighted_paid_eur"),
            func.sum(case((weight > 0, weight), else_=None)).label("weighted_kg"),
        )
        .where(scope.c.master_product_id.is_not(None))
        .group_by(scope.c.master_product_id)
    )

    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = db.execute(
        stmt.order_by(func.sum(notional).desc()).limit(page_size).offset((page - 1) * page_size)
    ).all()

    products = _product_display(db, {row.master_product_id for row in rows})
    dates = _purchase_span(db, {row.master_product_id for row in rows})
    items: list[ProductSummary] = []
    for row in rows:
        display = products.get(row.master_product_id)
        span = dates.get(row.master_product_id, (None, None))
        weighted_kg = row.weighted_kg
        items.append(
            ProductSummary(
                master_product_id=row.master_product_id,
                canonical_name=display.canonical_name if display else "—",
                brand=display.brand if display else None,
                category_path=display.category_path if display else None,
                sold_by_weight=bool(display and display.sold_by_weight),
                line_count=row.line_count,
                receipt_count=row.receipt_count,
                total_quantity=row.total_quantity or Decimal("0"),
                total_weight_kg=row.total_weight_kg,
                total_paid_eur=row.total_paid_eur or Decimal("0"),
                total_notional_eur=row.total_notional_eur or Decimal("0"),
                price_per_kg_eur=(
                    (row.weighted_paid_eur / weighted_kg).quantize(Decimal("0.0001"))
                    if weighted_kg and weighted_kg > 0 and row.weighted_paid_eur is not None
                    else None
                ),
                first_purchase_on=span[0],
                last_purchase_on=span[1],
            )
        )
    return Page(items=items, total=total, page=page, page_size=page_size)


# --- Parser profiles (UX-1.8) --------------------------------------------------


def _profile_out(db: DbSession, profile: MerchantParserProfile) -> ParserProfileOut:
    payload = ParserProfileOut.model_validate(profile)
    payload.is_generic = profile.is_generic
    if profile.merchant_id:
        merchant = db.get(Merchant, profile.merchant_id)
        payload.merchant_name = merchant.name if merchant else None
    return payload


@profiles_router.get("", response_model=list[ParserProfileOut])
def list_profiles(ctx: CurrentAuth, db: Db) -> list[ParserProfileOut]:
    rows = db.scalars(
        select(MerchantParserProfile)
        .where(MerchantParserProfile.is_deleted.is_(False))
        .order_by(MerchantParserProfile.priority.desc(), MerchantParserProfile.name)
    ).all()
    return [_profile_out(db, row) for row in rows]


@profiles_router.get("/parsers", response_model=list[ParserOption])
def list_parsers(ctx: CurrentAuth) -> list[ParserOption]:
    return [ParserOption(**option) for option in parsers.available()]


@profiles_router.post("", response_model=ParserProfileOut, status_code=201)
def create_profile(payload: ParserProfileIn, ctx: Writer, db: Db) -> ParserProfileOut:
    profile = MerchantParserProfile(**payload.model_dump())
    db.add(profile)
    db.flush()
    return _profile_out(db, profile)


@profiles_router.patch("/{profile_id}", response_model=ParserProfileOut)
def update_profile(
    profile_id: uuid.UUID, payload: ParserProfileUpdate, ctx: Writer, db: Db
) -> ParserProfileOut:
    profile = supermarket.get_profile(db, profile_id)
    for key, value in payload.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(profile, key, value)
    db.flush()
    return _profile_out(db, profile)


@profiles_router.delete("/{profile_id}", response_model=Ok)
def delete_profile(profile_id: uuid.UUID, ctx: Writer, db: Db) -> Ok:
    supermarket.delete_profile(
        db, supermarket.get_profile(db, profile_id), actor_user_id=ctx.user.id
    )
    return Ok(message="Perfil eliminado.")


@profiles_router.post("/{profile_id}/test", response_model=ProfileTestResult)
def test_profile(
    profile_id: uuid.UUID, ctx: Writer, db: Db, receipt_id: uuid.UUID
) -> ProfileTestResult:
    """Re-parse a stored document with this profile and diff against the current result."""
    profile = supermarket.get_profile(db, profile_id)
    receipt = supermarket.get_receipt(db, receipt_id)
    if receipt.document_id is None:
        raise ValidationError("Esta fatura não tem documento para testar.")
    document = db.get(Document, receipt.document_id)
    if document is None:
        raise NotFound("Documento original não encontrado.")

    current = supermarket.totals_for(db, receipt)
    data = documents.absolute_path(document).read_bytes()
    extracted = pipeline.extraction.extract(data, document.mime_type)
    parsed = parsers.get(profile.parser_key).parse(extracted, dict(profile.field_hints))

    allocations = arithmetic.prorate_invoice_discount(
        [
            arithmetic.ProrationInput(
                unit_price_pvp_eur=item.unit_price_pvp_eur,
                promo_discount_eur=item.promo_discount_eur,
            )
            for item in parsed.items
        ],
        parsed.total_discount_eur,
    )
    rows: list[dict[str, Any]] = []
    computed = Decimal("0.00")
    for item, allocated in zip(parsed.items, allocations, strict=True):
        paid = arithmetic.paid_from_components(
            unit_price_pvp_eur=item.unit_price_pvp_eur,
            promo_discount_eur=item.promo_discount_eur,
            invoice_allocated_discount_eur=allocated,
        )
        computed += paid
        rows.append(
            {
                "line_no": item.line_no,
                "description_raw": item.description_raw,
                "unit_price_pvp_eur": str(item.unit_price_pvp_eur),
                "promo_discount_eur": str(item.promo_discount_eur),
                "paid_price_eur": str(paid),
            }
        )

    tolerance = supermarket.tolerance_eur(db)
    reconciled = parsed.total_eur is not None and abs(computed - parsed.total_eur) <= tolerance
    return ProfileTestResult(
        parser_key=profile.parser_key,
        item_count=len(rows),
        total_eur=parsed.total_eur,
        computed_total_eur=computed,
        is_reconciled=reconciled,
        confidence=receipt.confidence or Decimal("0.000"),
        decision_reasons=[{"rule": "parser_warning", "detail": w} for w in parsed.warnings],
        items=rows,
        diff_vs_current={
            "item_count": len(rows) - current.printed_item_count,
            "computed_total_eur": str(computed - current.computed_total_eur),
            "current_is_reconciled": current.is_reconciled,
        },
    )


#: Registered alongside ``router`` in ``app.main`` — all three are Module 1's surface.
routers = (router, profiles_router, items_router)
