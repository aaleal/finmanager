"""Receipt lifecycle, arithmetic upkeep and the status dashboard.

The guarantee this file exists to protect: **adding an Fs article changes no
printed figure.** ``total_eur``, ``computed_total_eur``, ``is_reconciled`` and
the printed-count check are byte-identical before and after, because an Fs row
pays ``0.00`` and never receives an invoice-discount allocation.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import uuid
from dataclasses import asdict
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.core import audit
from app.core.errors import Conflict, NotFound, ValidationError
from app.core.money import ZERO, to_eur
from app.models.core import Document, ProcessingJob, ReviewTask
from app.models.products import MasterProduct
from app.models.receipts import (
    RECEIPT_TRANSITIONS,
    MerchantParserProfile,
    Receipt,
    ReceiptItem,
)
from app.services import documents, settings_service
from app.services.receipts import (
    arithmetic,
    catalogue,
    ledger,
    parsers,
    pipeline,
    prices_service,
    products_service,
)
from app.services.receipts.normalize import extract_pack_weight_kg, normalize_description

MODULE = "receipts"
ARITHMETIC_TOLERANCE = "receipts.arithmetic_tolerance_eur"
RECEIPT_TABLE = "receipts"
ITEM_TABLE = "receipt_items"


def tolerance_eur(db: DbSession) -> Decimal:
    raw = settings_service.get(db, ARITHMETIC_TOLERANCE, default="0.02")
    return Decimal(str(raw))


def thresholds(db: DbSession) -> tuple[Decimal, Decimal]:
    return (
        Decimal(str(settings_service.get(db, settings_service.CONFIDENCE_AUTO_ACCEPT))),
        Decimal(str(settings_service.get(db, settings_service.CONFIDENCE_REVIEW))),
    )


# --- Derived view -------------------------------------------------------------


def totals_for(db: DbSession, receipt: Receipt) -> arithmetic.ReceiptTotals:
    return arithmetic.receipt_totals(
        [
            arithmetic.ItemTotalsInput(
                paid_price_eur=item.paid_price_eur,
                unit_price_pvp_eur=item.unit_price_pvp_eur,
                promo_discount_eur=item.promo_discount_eur,
                quantity=item.quantity,
                is_fs=item.is_fs,
            )
            for item in receipt.items
            if not item.is_deleted
        ],
        total_eur=receipt.total_eur,
        total_discount_eur=receipt.total_discount_eur,
        tolerance_eur=tolerance_eur(db),
    )


def derived(db: DbSession, receipt: Receipt) -> dict[str, Any]:
    totals = totals_for(db, receipt)
    payload = asdict(totals)
    payload["item_count_matches"] = (
        receipt.item_count is None or receipt.item_count == totals.printed_item_count
    )
    payload["is_complete"] = bool(receipt.items) and all(
        item.master_product_id is not None for item in receipt.items if not item.is_deleted
    )
    return payload


def item_derived(item: ReceiptItem) -> dict[str, Any]:
    per_kg = arithmetic.price_per_kg(
        unit_price_pvp_eur=item.unit_price_pvp_eur,
        promo_discount_eur=item.promo_discount_eur,
        paid_price_eur=item.paid_price_eur,
        weight_observed_kg=item.weight_observed_kg,
        weight_listed_kg=item.weight_listed_kg,
        is_fs=item.is_fs,
    )
    return {
        "weight_kg": per_kg.weight_kg,
        "price_per_kg_pvp_eur": per_kg.pvp,
        "price_per_kg_promo_eur": per_kg.promo,
        "price_per_kg_final_eur": per_kg.final,
        "price_per_kg_unavailable_reason": per_kg.unavailable_reason,
        "notional_value_eur": arithmetic.notional_value_eur(
            is_fs=item.is_fs,
            unit_price_pvp_eur=item.unit_price_pvp_eur,
            quantity=item.quantity,
            paid_price_eur=item.paid_price_eur,
        ),
    }


# --- Arithmetic upkeep --------------------------------------------------------


def recompute(receipt: Receipt) -> None:
    """Re-spread the invoice discount and recompute every paid price.

    Fs rows are excluded from the spread and keep ``paid_price_eur = 0.00``, so
    calling this after appending one is a no-op on every printed figure.
    """
    live = [item for item in receipt.items if not item.is_deleted]
    allocations = arithmetic.prorate_invoice_discount(
        [
            arithmetic.ProrationInput(
                unit_price_pvp_eur=item.unit_price_pvp_eur,
                promo_discount_eur=item.promo_discount_eur,
                is_fs=item.is_fs,
            )
            for item in live
        ],
        receipt.total_discount_eur,
    )
    for item, allocated in zip(live, allocations, strict=True):
        if item.is_fs:
            item.invoice_allocated_discount_eur = ZERO
            item.paid_price_eur = ZERO
            continue
        item.invoice_allocated_discount_eur = allocated
        item.paid_price_eur = arithmetic.paid_from_components(
            unit_price_pvp_eur=item.unit_price_pvp_eur,
            promo_discount_eur=item.promo_discount_eur,
            invoice_allocated_discount_eur=allocated,
        )
        quantity_canonical, unit_canonical = arithmetic.canonical_quantity(item.quantity, item.unit)
        item.quantity_canonical = quantity_canonical
        item.unit_canonical = unit_canonical


# --- Status machine -----------------------------------------------------------


def transition(
    db: DbSession,
    receipt: Receipt,
    to_status: str,
    *,
    actor_user_id: uuid.UUID | None,
    reason: str | None = None,
) -> None:
    if to_status == receipt.status:
        return
    allowed = RECEIPT_TRANSITIONS.get(receipt.status, ())
    if to_status not in allowed:
        raise Conflict(
            f"Transição inválida: {receipt.status} → {to_status}.",
            allowed=list(allowed),
        )
    before = receipt.status
    receipt.status = to_status
    audit.record(
        db,
        action="STATUS_CHANGE",
        table_name=RECEIPT_TABLE,
        record_id=receipt.id,
        entity_id=receipt.entity_id,
        actor_user_id=actor_user_id,
        before={"status": before},
        after={"status": to_status},
        reason=reason,
    )


def _sync_review_task(db: DbSession, receipt: Receipt) -> None:
    """Exactly one open task per receipt in ``NEEDS_REVIEW``."""
    existing = db.scalar(
        select(ReviewTask).where(
            ReviewTask.subject_type == "Receipt",
            ReviewTask.subject_id == receipt.id,
            ReviewTask.status == "PENDING",
        )
    )
    if receipt.status == "NEEDS_REVIEW":
        if existing is None:
            db.add(
                ReviewTask(
                    entity_id=receipt.entity_id,
                    module=MODULE,
                    subject_type="Receipt",
                    subject_id=receipt.id,
                    confidence=receipt.confidence,
                    suggested_payload={"receipt_id": str(receipt.id)},
                    decision_reasons=receipt.decision_reasons,
                    title=f"Fatura de {receipt.purchase_date or 'data desconhecida'}",
                )
            )
        else:
            existing.confidence = receipt.confidence
            existing.decision_reasons = receipt.decision_reasons
    elif existing is not None:
        existing.status = "CONFIRMED"
        existing.resolved_at = dt.datetime.now(dt.UTC)


# --- Ingestion ----------------------------------------------------------------


def _existing_by_hash(db: DbSession, entity_id: uuid.UUID, sha256_hash: str) -> Receipt | None:
    document = db.scalar(select(Document).where(Document.sha256_hash == sha256_hash))
    if document is None:
        return None
    return db.scalar(
        select(Receipt).where(
            Receipt.entity_id == entity_id,
            Receipt.document_id == document.id,
            Receipt.is_deleted.is_(False),
        )
    )


def create_from_upload(
    db: DbSession,
    *,
    data: bytes,
    filename: str | None,
    entity_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    idempotency_key: str,
) -> tuple[Receipt, ProcessingJob, bool]:
    """Store the document and queue a parse. Re-uploading the same bytes is a no-op."""
    sha256_hash = hashlib.sha256(data).hexdigest()
    existing = _existing_by_hash(db, entity_id, sha256_hash)
    if existing is not None:
        job = (
            db.get(ProcessingJob, existing.processing_job_id)
            if existing.processing_job_id
            else None
        )
        if job is None:
            job = _job_for(db, existing, idempotency_key)
        return existing, job, False

    document = documents.store_bytes(db, data, source="UPLOAD", original_filename=filename)
    receipt = Receipt(entity_id=entity_id, document_id=document.id, status="UPLOADED")
    db.add(receipt)
    db.flush()

    job = _job_for(db, receipt, idempotency_key)
    receipt.processing_job_id = job.id
    audit.record(
        db,
        action="CREATE",
        table_name=RECEIPT_TABLE,
        record_id=receipt.id,
        entity_id=entity_id,
        actor_user_id=actor_user_id,
        after=audit.snapshot(receipt),
    )
    db.flush()
    return receipt, job, True


def _job_for(db: DbSession, receipt: Receipt, idempotency_key: str) -> ProcessingJob:
    key = f"{idempotency_key}:{receipt.id}"
    job = db.scalar(select(ProcessingJob).where(ProcessingJob.idempotency_key == key))
    if job is None:
        job = ProcessingJob(
            idempotency_key=key,
            job_type="receipts.parse",
            entity_id=receipt.entity_id,
            status="QUEUED",
            payload={"receipt_id": str(receipt.id)},
        )
        db.add(job)
        db.flush()
    return job


def parse_receipt(
    db: DbSession,
    receipt: Receipt,
    *,
    actor_user_id: uuid.UUID | None = None,
    forced_profile_id: uuid.UUID | None = None,
) -> Receipt:
    """Run the pipeline from the **stored document** — never from a re-upload."""
    if receipt.document_id is None:
        raise ValidationError("Esta fatura não tem documento associado para reprocessar.")
    document = db.get(Document, receipt.document_id)
    if document is None:
        raise NotFound("Documento original não encontrado.")

    if receipt.status not in ("UPLOADED", "FAILED"):
        transition(db, receipt, "PARSING", actor_user_id=actor_user_id, reason="reprocessamento")
    else:
        transition(db, receipt, "PARSING", actor_user_id=actor_user_id)

    job = db.get(ProcessingJob, receipt.processing_job_id) if receipt.processing_job_id else None
    if job is not None:
        job.status = "RUNNING"
        job.attempts += 1
        job.started_at = dt.datetime.now(dt.UTC)

    data = documents.absolute_path(document).read_bytes()
    auto_accept, review = thresholds(db)
    try:
        result = pipeline.run(
            db,
            data=data,
            mime_type=document.mime_type,
            entity_id=receipt.entity_id,
            receipt=receipt,
            forced_profile_id=forced_profile_id,
            auto_accept_threshold=auto_accept,
            review_threshold=review,
        )
    except Exception as exc:  # a failure is a FAILED job row, never a silent loss
        receipt.status = "FAILED"
        receipt.decision_reasons = [
            {"rule": "parse_failed", "detail": str(exc)[:400], "score": None}
        ]
        if job is not None:
            job.status = "FAILED"
            job.last_error = str(exc)[:1000]
            job.completed_at = dt.datetime.now(dt.UTC)
        db.flush()
        return receipt

    _guard_duplicate_atcud(db, receipt)

    receipt.confidence = result.confidence
    receipt.decision_reasons = result.decision_reasons
    receipt.status = result.status
    db.flush()

    recompute(receipt)
    _sync_review_task(db, receipt)
    _record_profile_outcome(db, result.profile, result.status)
    # Observations are frozen as soon as the receipt has a decision, so a trend
    # exists before anyone confirms anything.
    prices_service.record_observations(db, receipt)
    ledger.propose_link(db, receipt, actor_user_id=actor_user_id)

    if job is not None:
        job.status = "SUCCEEDED"
        job.completed_at = dt.datetime.now(dt.UTC)

    audit.record(
        db,
        action="UPDATE",
        table_name=RECEIPT_TABLE,
        record_id=receipt.id,
        entity_id=receipt.entity_id,
        actor_user_id=actor_user_id,
        after={"status": receipt.status, "confidence": str(receipt.confidence)},
        reason="parse",
    )
    db.flush()
    return receipt


def _guard_duplicate_atcud(db: DbSession, receipt: Receipt) -> None:
    """The ATCUD is the fiscal document identity — a second one cannot exist."""
    if not receipt.atcud_code:
        return
    clash = db.scalar(
        select(Receipt).where(
            Receipt.entity_id == receipt.entity_id,
            Receipt.atcud_code == receipt.atcud_code,
            Receipt.id != receipt.id,
            Receipt.is_deleted.is_(False),
        )
    )
    if clash is not None:
        raise Conflict(
            "Esta fatura já existe (mesmo ATCUD).",
            existing_receipt_id=str(clash.id),
            atcud_code=receipt.atcud_code,
        )


def _record_profile_outcome(
    db: DbSession, profile: MerchantParserProfile | None, status: str
) -> None:
    """``success_rate`` is observed, not configured, so a failing profile is visible."""
    if profile is None:
        return
    outcome = Decimal("1") if status == "AUTO_ACCEPTED" else Decimal("0")
    previous = profile.success_rate
    profile.success_rate = (
        outcome
        if previous is None
        else ((Decimal(previous) * 4 + outcome) / 5).quantize(Decimal("0.001"))
    )


# --- Editing ------------------------------------------------------------------


def get_receipt(db: DbSession, receipt_id: uuid.UUID) -> Receipt:
    receipt = db.get(Receipt, receipt_id)
    if receipt is None or receipt.is_deleted:
        raise NotFound("Fatura não encontrada.")
    return receipt


def get_item(db: DbSession, item_id: uuid.UUID) -> ReceiptItem:
    item = db.get(ReceiptItem, item_id)
    if item is None or item.is_deleted:
        raise NotFound("Linha não encontrada.")
    return item


def append_item(
    db: DbSession,
    receipt: Receipt,
    *,
    description_raw: str,
    unit_price_pvp_eur: Decimal,
    quantity: Decimal = Decimal("1"),
    unit: str = "UN",
    is_fs: bool = True,
    line_no: int | None = None,
    promo_discount_eur: Decimal = ZERO,
    notional_value_source: str = "MANUAL",
    notes: str | None = None,
    actor_user_id: uuid.UUID | None = None,
) -> ReceiptItem:
    """Append an article by hand, Fs or printed.

    Only *document parsing* is skipped, not automation: the article goes through
    the same product picker as any other line. What it cannot have is anything
    the document would have supplied — ``line_no``, ``merchant_section``,
    ``iva_class_raw``.

    A **printed** line added here is not a new purchase: it is a line the parser
    failed to read, and the reconciliation against the printed total is what says
    whether the correction was right.
    """
    value = to_eur(unit_price_pvp_eur) or ZERO
    if is_fs and value <= ZERO:
        raise ValidationError("Um artigo Fs precisa de um valor nocional superior a zero.")

    quantity_canonical, unit_canonical = arithmetic.canonical_quantity(quantity, unit)
    description_norm = normalize_description(description_raw)[:300]
    receipt_merchant_id = receipt.merchant_id

    # Only *document parsing* is skipped, not automation: an Fs article goes
    # through the same catalogue as any other line, so once it resolves it
    # inherits that product's category and weights.
    match = catalogue.resolve_description(
        db, merchant_id=receipt_merchant_id, description_norm=description_norm
    )

    item = ReceiptItem(
        receipt_id=receipt.id,
        entity_id=receipt.entity_id,
        line_no=None if is_fs else line_no,
        description_raw=description_raw[:300],
        description_norm=description_norm,
        master_product_id=match.master_product_id,
        quantity=quantity,
        unit=unit,
        quantity_canonical=quantity_canonical,
        unit_canonical=unit_canonical,
        unit_price_pvp_eur=value,
        promo_discount_eur=ZERO if is_fs else (to_eur(promo_discount_eur) or ZERO),
        invoice_allocated_discount_eur=ZERO,
        paid_price_eur=ZERO,
        weight_listed_kg=extract_pack_weight_kg(description_raw),
        is_fs=is_fs,
        notional_value_source=notional_value_source if is_fs else None,
        notes=notes,
        confidence=Decimal("1.000"),
        decision_reasons=[
            {
                "rule": "manual_entry",
                "detail": "Artigo Fs introduzido à mão."
                if is_fs
                else "Linha introduzida à mão durante a revisão.",
                "score": "1.000",
            },
            *match.reasons,
        ],
    )
    db.add(item)
    receipt.items.append(item)
    db.flush()
    # A printed line joins the proration; an Fs row is excluded from it, so this
    # leaves every printed figure untouched either way.
    recompute(receipt)
    audit.record(
        db,
        action="CREATE",
        table_name=ITEM_TABLE,
        record_id=item.id,
        entity_id=receipt.entity_id,
        actor_user_id=actor_user_id,
        after=audit.snapshot(item),
        reason="artigo Fs" if is_fs else "linha acrescentada na revisão",
    )
    return item


def append_fs_item(
    db: DbSession,
    receipt: Receipt,
    *,
    description_raw: str,
    unit_price_pvp_eur: Decimal,
    quantity: Decimal = Decimal("1"),
    unit: str = "UN",
    notional_value_source: str = "MANUAL",
    notes: str | None = None,
    actor_user_id: uuid.UUID | None = None,
) -> ReceiptItem:
    return append_item(
        db,
        receipt,
        description_raw=description_raw,
        unit_price_pvp_eur=unit_price_pvp_eur,
        quantity=quantity,
        unit=unit,
        is_fs=True,
        notional_value_source=notional_value_source,
        notes=notes,
        actor_user_id=actor_user_id,
    )


def update_item(
    db: DbSession,
    item: ReceiptItem,
    changes: dict[str, Any],
    *,
    actor_user_id: uuid.UUID | None = None,
) -> ReceiptItem:
    before = audit.snapshot(item)
    for field_name, value in changes.items():
        if value is not None or field_name in {"notes", "promo_type", "product_flag", "line_no"}:
            setattr(item, field_name, value)
    db.flush()
    receipt = db.get(Receipt, item.receipt_id)
    if receipt is not None:
        recompute(receipt)
    audit.record(
        db,
        action="UPDATE",
        table_name=ITEM_TABLE,
        record_id=item.id,
        entity_id=item.entity_id,
        actor_user_id=actor_user_id,
        before=before,
        after=audit.snapshot(item),
    )
    db.flush()
    return item


def delete_item(db: DbSession, item: ReceiptItem, *, actor_user_id: uuid.UUID | None) -> None:
    item.is_deleted = True
    item.deleted_at = dt.datetime.now(dt.UTC)
    receipt = db.get(Receipt, item.receipt_id)
    if receipt is not None:
        recompute(receipt)
    audit.record(
        db,
        action="DELETE",
        table_name=ITEM_TABLE,
        record_id=item.id,
        entity_id=item.entity_id,
        actor_user_id=actor_user_id,
        before=audit.snapshot(item),
    )
    db.flush()


def update_receipt(
    db: DbSession,
    receipt: Receipt,
    changes: dict[str, Any],
    *,
    actor_user_id: uuid.UUID | None = None,
) -> Receipt:
    before = audit.snapshot(receipt)
    for field_name, value in changes.items():
        setattr(receipt, field_name, value)
    recompute(receipt)
    db.flush()
    audit.record(
        db,
        action="UPDATE",
        table_name=RECEIPT_TABLE,
        record_id=receipt.id,
        entity_id=receipt.entity_id,
        actor_user_id=actor_user_id,
        before=before,
        after=audit.snapshot(receipt),
    )
    return receipt


def confirm(db: DbSession, receipt: Receipt, *, actor_user_id: uuid.UUID | None) -> Receipt:
    transition(db, receipt, "CONFIRMED", actor_user_id=actor_user_id)
    _sync_review_task(db, receipt)
    # A correction made during review appends a fresh observation; the superseded
    # one is left exactly where it was.
    prices_service.record_observations(db, receipt)
    db.flush()
    return receipt


def reopen(db: DbSession, receipt: Receipt, *, actor_user_id: uuid.UUID | None) -> Receipt:
    """Send a confirmed receipt back to review.

    Not an undo: the price observations frozen on confirmation are append-only
    and stay exactly where they are. A correction made now writes a new one.
    """
    transition(db, receipt, "NEEDS_REVIEW", actor_user_id=actor_user_id, reason="reaberta")
    _sync_review_task(db, receipt)
    db.flush()
    return receipt


def confirm_categories(db: DbSession, receipt: Receipt, *, actor_user_id: uuid.UUID | None) -> int:
    """Promote every ``AUTO`` classification on this receipt to ``VALIDATED``.

    Confirmed once per *product*, so the same click also settles every past and
    future line that resolves to it (Decision #17).
    """
    confirmed = 0
    seen: set[uuid.UUID] = set()
    for item in receipt.items:
        if item.is_deleted or item.master_product_id is None:
            continue
        if item.master_product_id in seen:
            continue
        seen.add(item.master_product_id)
        product = db.get(MasterProduct, item.master_product_id)
        if product is None or product.category_status != "AUTO" or product.category_id is None:
            continue
        products_service.validate_category(db, product, actor_user_id=actor_user_id)
        confirmed += 1
    db.flush()
    return confirmed


def reassign_item_product(
    db: DbSession,
    item: ReceiptItem,
    *,
    master_product_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
) -> ReceiptItem:
    """Re-resolve a line to a different product; the category follows, and the
    correction feeds ``ProductAlias`` so the same line resolves itself next time."""
    product = products_service.get_product(db, master_product_id)
    before = audit.snapshot(item)
    item.master_product_id = product.id
    item.decision_reasons = [
        *item.decision_reasons,
        {"rule": "manual_product", "detail": "Produto corrigido a mão.", "score": "1.000"},
    ]
    item.confidence = Decimal("1.000")

    receipt = db.get(Receipt, item.receipt_id)
    if receipt is not None and receipt.merchant_id is not None:
        catalogue.learn(
            db,
            master_product_id=product.id,
            merchant_id=receipt.merchant_id,
            merchant_description=item.description_raw,
        )
    audit.record(
        db,
        action="UPDATE",
        table_name=ITEM_TABLE,
        record_id=item.id,
        entity_id=item.entity_id,
        actor_user_id=actor_user_id,
        before=before,
        after=audit.snapshot(item),
        reason="correção de produto",
    )
    db.flush()
    return item


def void(
    db: DbSession, receipt: Receipt, *, reason: str, actor_user_id: uuid.UUID | None
) -> Receipt:
    if not reason.strip():
        raise ValidationError("Anular uma fatura exige um motivo.")
    receipt.void_reason = reason.strip()
    transition(db, receipt, "VOID", actor_user_id=actor_user_id, reason=reason)
    _sync_review_task(db, receipt)
    db.flush()
    return receipt


# --- Status dashboard (UX-1.5) -------------------------------------------------


def status_counts(db: DbSession, entity_ids: list[uuid.UUID]) -> dict[str, Any]:
    """Every figure links to the list that resolves it, so every figure is a count."""
    if not entity_ids:
        entity_ids = []

    def count(stmt: Any) -> int:
        return int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)

    live = Receipt.is_deleted.is_(False)
    in_scope = Receipt.entity_id.in_(entity_ids)

    total_receipts = count(select(Receipt.id).where(in_scope, live))
    queued = count(
        select(ProcessingJob.id).where(
            ProcessingJob.job_type.like("receipts.%"),
            ProcessingJob.status.in_(("QUEUED", "RUNNING", "RETRYING")),
        )
    )
    failed = count(
        select(ProcessingJob.id).where(
            ProcessingJob.job_type.like("receipts.%"), ProcessingJob.status == "FAILED"
        )
    )
    to_validate = count(select(Receipt.id).where(in_scope, live, Receipt.status == "NEEDS_REVIEW"))
    unresolved_lines = count(
        select(ReceiptItem.id).where(
            ReceiptItem.entity_id.in_(entity_ids),
            ReceiptItem.is_deleted.is_(False),
            ReceiptItem.master_product_id.is_(None),
        )
    )
    resolved_lines = count(
        select(ReceiptItem.id).where(
            ReceiptItem.entity_id.in_(entity_ids),
            ReceiptItem.is_deleted.is_(False),
            ReceiptItem.master_product_id.is_not(None),
        )
    )

    decided = db.execute(
        select(Receipt.status, func.count())
        .where(in_scope, live, Receipt.status.in_(("AUTO_ACCEPTED", "NEEDS_REVIEW", "CONFIRMED")))
        .group_by(Receipt.status)
    ).all()
    by_status = {row[0]: row[1] for row in decided}
    total_decided = sum(by_status.values())
    auto_accepted = by_status.get("AUTO_ACCEPTED", 0)

    return {
        "total_receipts": total_receipts,
        "to_process": queued,
        "failed_jobs": failed,
        "to_validate": to_validate,
        "total_lines": unresolved_lines + resolved_lines,
        "unresolved_lines": unresolved_lines,
        "resolved_lines": resolved_lines,
        "uncategorized_products": products_service.uncategorized_count(db),
        "total_products": products_service.total_count(db),
        "merge_candidates": products_service.merge_candidate_count(db),
        # Observed, never targeted (Decision #41).
        "observed_auto_accept_rate": (
            round(auto_accepted / total_decided, 3) if total_decided else None
        ),
        "decided_receipts": total_decided,
    }


def dashboard_summary(db: DbSession, entity_ids: list[uuid.UUID]) -> tuple[Decimal, int]:
    """What the home tile shows: money spent, and over how many *faturas*.

    Voided receipts are excluded — an annulled *talão* never happened.
    """
    if not entity_ids:
        return ZERO, 0
    total, receipts = db.execute(
        select(func.coalesce(func.sum(Receipt.total_eur), 0), func.count(Receipt.id)).where(
            Receipt.entity_id.in_(entity_ids),
            Receipt.is_deleted.is_(False),
            Receipt.status != "VOID",
        )
    ).one()
    return to_eur(Decimal(total)) or ZERO, int(receipts)


# --- Parser profiles ----------------------------------------------------------


def get_profile(db: DbSession, profile_id: uuid.UUID) -> MerchantParserProfile:
    profile = db.get(MerchantParserProfile, profile_id)
    if profile is None or profile.is_deleted:
        raise NotFound("Perfil de leitura não encontrado.")
    return profile


def delete_profile(
    db: DbSession, profile: MerchantParserProfile, *, actor_user_id: uuid.UUID | None
) -> None:
    if profile.is_generic:
        raise Conflict("O perfil genérico não pode ser eliminado: é a rede de segurança.")
    profile.is_deleted = True
    profile.deleted_at = dt.datetime.now(dt.UTC)
    audit.record(
        db,
        action="DELETE",
        table_name="merchant_parser_profiles",
        record_id=profile.id,
        actor_user_id=actor_user_id,
        before=audit.snapshot(profile),
    )
    db.flush()


def available_parsers() -> list[dict[str, str]]:
    return parsers.available()
