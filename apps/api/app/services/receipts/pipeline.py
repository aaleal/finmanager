"""The ingestion pipeline.

Fixed order. Text comes off the document first because merchant detection needs
something to read; from there, **merchant detection precedes field extraction,
because it is what selects the parser**::

    read text ─▶ detect merchant ─▶ select MerchantParserProfile (or generic)
              ─▶ extract fields ─▶ normalize ─▶ resolve product ─▶ classify
              ─▶ reconcile arithmetic ─▶ score confidence

Every stage has a local engine that works offline and unsubscribed. Product
resolution and classification are seams here: they report *not run* until the
slice that owns the catalogue fills them in, which the confidence engine handles
honestly rather than by scoring them zero.
"""

from __future__ import annotations

import datetime as dt
import re
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.core.money import ZERO, to_eur
from app.models.core import Merchant
from app.models.receipts import MerchantParserProfile, Receipt, ReceiptItem
from app.services.receipts import arithmetic, catalogue, extraction, fiscal, merchants, parsers
from app.services.receipts.arithmetic import ProrationInput
from app.services.receipts.confidence import DecisionReason, ReceiptSignals, item_confidence, score
from app.services.receipts.normalize import (
    extract_pack_weight_kg,
    normalize_description,
)
from app.services.receipts.parsers.base import ParsedItem, ParsedReceipt


class ProductResolver(Protocol):
    """Filled in by the slice that owns ``MasterProduct``.

    Returns ``(master_product_id, match_score, reasons)``; a ``match_score`` of
    ``None`` means the stage did not run at all.
    """

    def resolve(
        self, db: DbSession, *, merchant_id: uuid.UUID | None, item: ReceiptItem
    ) -> tuple[uuid.UUID | None, Decimal | None, list[dict[str, Any]]]: ...


#: The catalogue slice fills the seam. Set to ``None`` to run the pipeline without
#: product resolution at all, which the confidence engine reports as *not run*
#: rather than as a failure (ADR-0018).
_product_resolver: ProductResolver | None = catalogue.CatalogueResolver()


def register_product_resolver(resolver: ProductResolver | None) -> None:
    """Swap the catalogue stage without touching the pipeline."""
    global _product_resolver
    _product_resolver = resolver


@dataclass(slots=True)
class PipelineResult:
    status: str
    confidence: Decimal
    decision_reasons: list[dict[str, Any]]
    parsed: ParsedReceipt
    profile: MerchantParserProfile | None
    merchant_id: uuid.UUID | None
    anchor: fiscal.FiscalAnchor
    engine: str
    document_kind: str
    warnings: list[str] = field(default_factory=list)


# --- Profile selection --------------------------------------------------------


def select_profile(db: DbSession, *, text: str, document_kind: str) -> MerchantParserProfile | None:
    """Highest-priority active profile whose patterns and document kinds match."""
    profiles = db.scalars(
        select(MerchantParserProfile)
        .where(
            MerchantParserProfile.is_active.is_(True),
            MerchantParserProfile.is_deleted.is_(False),
        )
        .order_by(MerchantParserProfile.priority.desc())
    ).all()

    generic: MerchantParserProfile | None = None
    for profile in profiles:
        if profile.is_generic:
            generic = generic or profile
            continue
        kinds = [str(k) for k in (profile.document_kinds or [])]
        if kinds and document_kind not in kinds:
            continue
        patterns = [str(p) for p in (profile.detection_patterns or [])]
        if patterns and any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns):
            return profile
    return generic


# --- Item construction --------------------------------------------------------


def _build_items(
    parsed: ParsedReceipt, *, entity_id: uuid.UUID, receipt_id: uuid.UUID
) -> list[ReceiptItem]:
    allocations = arithmetic.prorate_invoice_discount(
        [
            ProrationInput(
                unit_price_pvp_eur=item.unit_price_pvp_eur,
                promo_discount_eur=item.promo_discount_eur,
            )
            for item in parsed.items
        ],
        parsed.total_discount_eur,
    )

    rows: list[ReceiptItem] = []
    for parsed_item, allocated in zip(parsed.items, allocations, strict=True):
        rows.append(_to_row(parsed_item, allocated, entity_id=entity_id, receipt_id=receipt_id))
    return rows


def _to_row(
    parsed_item: ParsedItem,
    allocated: Decimal,
    *,
    entity_id: uuid.UUID,
    receipt_id: uuid.UUID,
) -> ReceiptItem:
    quantity_canonical, unit_canonical = arithmetic.canonical_quantity(
        parsed_item.quantity, parsed_item.unit
    )
    paid = arithmetic.paid_from_components(
        unit_price_pvp_eur=parsed_item.unit_price_pvp_eur,
        promo_discount_eur=parsed_item.promo_discount_eur,
        invoice_allocated_discount_eur=allocated,
    )
    confidence, reasons = item_confidence(
        text_quality=parsed_item.text_confidence,
        has_price=parsed_item.unit_price_pvp_eur != ZERO,
        product_match=None,
    )
    return ReceiptItem(
        receipt_id=receipt_id,
        entity_id=entity_id,
        line_no=parsed_item.line_no,
        merchant_section=parsed_item.merchant_section,
        description_raw=parsed_item.description_raw[:300],
        description_norm=normalize_description(parsed_item.description_raw)[:300],
        quantity=parsed_item.quantity,
        unit=parsed_item.unit,
        quantity_canonical=quantity_canonical,
        unit_canonical=unit_canonical,
        weight_observed_kg=parsed_item.weight_observed_kg,
        weight_listed_kg=extract_pack_weight_kg(parsed_item.description_raw),
        is_bulk_weighed=parsed_item.is_bulk_weighed,
        unit_price_pvp_eur=to_eur(parsed_item.unit_price_pvp_eur) or ZERO,
        promo_discount_eur=to_eur(parsed_item.promo_discount_eur) or ZERO,
        promo_type=parsed_item.promo_type,
        invoice_allocated_discount_eur=allocated,
        paid_price_eur=paid,
        iva_class_raw=parsed_item.iva_class_raw,
        product_flag=parsed_item.product_flag,
        confidence=confidence,
        decision_reasons=reasons,
    )


# --- The pipeline -------------------------------------------------------------


def run(
    db: DbSession,
    *,
    data: bytes,
    mime_type: str,
    entity_id: uuid.UUID,
    receipt: Receipt,
    forced_profile_id: uuid.UUID | None = None,
    auto_accept_threshold: Decimal = Decimal("0.90"),
    review_threshold: Decimal = Decimal("0.60"),
) -> PipelineResult:
    extracted = extraction.extract(data, mime_type)
    text = extracted.text

    anchor = fiscal.read_anchor(data, mime_type, text)
    context: list[DecisionReason] = [
        DecisionReason("engine", f"Motor local: {extracted.engine}."),
        DecisionReason("document_kind", extracted.document_kind),
    ]

    profile = (
        db.get(MerchantParserProfile, forced_profile_id)
        if forced_profile_id
        else select_profile(db, text=text, document_kind=extracted.document_kind)
    )
    parser = parsers.get(profile.parser_key if profile else parsers.GENERIC_PARSER_KEY)
    if profile is not None:
        context.append(DecisionReason("parser_profile", profile.name))

    parsed = parser.parse(extracted, dict(profile.field_hints) if profile else {})
    for warning in parsed.warnings:
        context.append(DecisionReason("parser_warning", warning))

    resolution = merchants.resolve(
        db,
        printed_nif=anchor.issuer_nif or fiscal.merchant_nif(text),
        name_hint=parsed.merchant_name_hint,
        profile_merchant_id=profile.merchant_id if profile else None,
    )
    context.extend(resolution.reasons)

    # The fiscal QR is the highest-confidence anchor there is: when it decodes,
    # its date and gross total become the reference values (FR-1.6).
    if anchor.has_qr:
        context.append(DecisionReason("fiscal_qr", "Código QR da AT lido e validado."))
        if anchor.document_date:
            parsed.purchase_date = anchor.document_date
            parsed.purchased_at = parsed.purchased_at or dt.datetime.combine(
                anchor.document_date, dt.time(0, 0)
            )
        if anchor.gross_total_eur is not None:
            parsed.total_eur = anchor.gross_total_eur
    elif anchor.atcud:
        context.append(DecisionReason("atcud_text", f"ATCUD lido do texto: {anchor.atcud}."))
    else:
        context.append(DecisionReason("atcud_missing", anchor.atcud_reason or "Sem ATCUD legível."))

    items = _build_items(parsed, entity_id=entity_id, receipt_id=receipt.id)
    product_score = _resolve_products(db, resolution.merchant_id, items, context)

    totals = arithmetic.receipt_totals(
        [
            arithmetic.ItemTotalsInput(
                paid_price_eur=row.paid_price_eur,
                unit_price_pvp_eur=row.unit_price_pvp_eur,
                promo_discount_eur=row.promo_discount_eur,
                quantity=row.quantity,
                is_fs=row.is_fs,
            )
            for row in items
        ],
        total_eur=parsed.total_eur or ZERO,
    )
    context.append(
        DecisionReason(
            "arithmetic",
            f"Σ linhas {totals.computed_total_eur} vs total impresso {parsed.total_eur}.",
        )
    )

    signals = ReceiptSignals(
        merchant_match=resolution.score,
        ocr_text=extracted.text_confidence,
        arithmetic_matches=None if parsed.total_eur is None else totals.is_reconciled,
        product_match=product_score,
        context=context,
        force_review=(
            "NIF impresso em conflito com o perfil detetado."
            if resolution.mismatch
            else ("Sem artigos legíveis." if not items else None)
        ),
    )
    status, confidence, reasons = score(
        signals,
        auto_accept_threshold=auto_accept_threshold,
        review_threshold=review_threshold,
    )

    receipt.items = items
    receipt.merchant_id = resolution.merchant_id
    receipt.parser_profile_id = profile.id if profile else None
    receipt.purchased_at = parsed.purchased_at
    receipt.purchase_date = parsed.purchase_date
    receipt.total_eur = to_eur(parsed.total_eur) or ZERO
    receipt.total_discount_eur = to_eur(parsed.total_discount_eur) or ZERO
    receipt.item_count = parsed.item_count
    receipt.atcud_code = anchor.atcud
    receipt.atcud_valid = anchor.atcud_valid
    receipt.atcud_reason = anchor.atcud_reason
    receipt.loyalty_scheme = parsed.loyalty_scheme
    receipt.loyalty_card_masked = parsed.loyalty_card_masked
    receipt.loyalty_accrued_eur = to_eur(parsed.loyalty_accrued_eur) or ZERO
    receipt.loyalty_discount_eur = to_eur(parsed.loyalty_discount_eur) or ZERO
    receipt.parsed_payment_methods = parsed.payment_methods
    receipt.raw_ocr_payload = {
        "engine": extracted.engine,
        "document_kind": extracted.document_kind,
        "text_confidence": str(extracted.text_confidence),
        "fiscal_source": anchor.source,
        "lines": [line.as_golden() for page in extracted.pages for line in page.lines][:400],
        **extracted.raw_payload,
    }

    return PipelineResult(
        status=status,
        confidence=confidence,
        decision_reasons=reasons,
        parsed=parsed,
        profile=profile,
        merchant_id=resolution.merchant_id,
        anchor=anchor,
        engine=extracted.engine,
        document_kind=extracted.document_kind,
        warnings=parsed.warnings,
    )


def _resolve_products(
    db: DbSession,
    merchant_id: uuid.UUID | None,
    items: list[ReceiptItem],
    context: list[DecisionReason],
) -> Decimal | None:
    """Run the catalogue stage if one is registered; report honestly if not."""
    if _product_resolver is None or not items:
        return None

    scores: list[Decimal] = []
    for item in items:
        product_id, match, reasons = _product_resolver.resolve(
            db, merchant_id=merchant_id, item=item
        )
        item.master_product_id = product_id
        if reasons:
            item.decision_reasons = [*item.decision_reasons, *reasons]
        scores.append(match if match is not None else Decimal(0))

    average = (sum(scores, Decimal(0)) / Decimal(len(scores))).quantize(Decimal("0.001"))
    resolved = sum(1 for item in items if item.master_product_id is not None)
    context.append(
        DecisionReason("product_resolution", f"{resolved}/{len(items)} linhas resolvidas.", average)
    )
    return average


def merchant_name(db: DbSession, merchant_id: uuid.UUID | None) -> str | None:
    if merchant_id is None:
        return None
    merchant = db.get(Merchant, merchant_id)
    return merchant.name if merchant else None
