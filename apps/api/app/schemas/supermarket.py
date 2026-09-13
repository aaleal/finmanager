"""Request/response contracts for Module 1.

Money crosses the wire as a decimal string and is formatted pt-PT in exactly one
place on the client — it is never parsed into a float on the way.
"""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import ApiModel

FsFilter = Literal["all", "only", "exclude"]


# --- Items --------------------------------------------------------------------


class ReceiptItemOut(ApiModel):
    id: uuid.UUID
    receipt_id: uuid.UUID
    line_no: int | None
    merchant_section: str | None
    description_raw: str
    master_product_id: uuid.UUID | None
    quantity: Decimal
    unit: str
    quantity_canonical: Decimal
    unit_canonical: str
    weight_listed_kg: Decimal | None
    weight_observed_kg: Decimal | None
    is_bulk_weighed: bool
    unit_price_pvp_eur: Decimal
    promo_discount_eur: Decimal
    promo_type: str | None
    invoice_allocated_discount_eur: Decimal
    paid_price_eur: Decimal
    iva_class_raw: str | None
    is_fs: bool
    notional_value_source: str | None
    product_flag: str | None
    notes: str | None
    confidence: Decimal | None
    decision_reasons: list[Any]

    # Derived on read; nothing here is persisted.
    weight_kg: Decimal | None = None
    price_per_kg_pvp_eur: Decimal | None = None
    price_per_kg_promo_eur: Decimal | None = None
    price_per_kg_final_eur: Decimal | None = None
    price_per_kg_unavailable_reason: str | None = None
    notional_value_eur: Decimal | None = None
    display_name: str | None = None
    #: The rest of the identity. The brand lives outside ``canonical_name`` by
    #: design (ADR-0058), so a line showing only the name cannot say which of
    #: three «Batata Frita Azeite» it resolved to; the cut and the conservation
    #: state separate products whose names differ by one word.
    brand: str | None = None
    presentation: str | None = None
    conservation: str | None = None
    #: ``L1 › L2 › L3`` off the resolved product — a category lives on
    #: ``MasterProduct`` and nowhere else (Decision #34), so an unresolved line
    #: has none and that is the truth.
    category_path: str | None = None
    #: ``AUTO`` means a machine proposed this category and nobody has confirmed it.
    category_status: str | None = None
    #: Priced per kg at the counter, so the printed quantity is meaningless.
    sold_by_weight: bool = False
    #: Is ``weight_listed_kg`` already one of the product's curated formats?
    #: ``None`` when the question does not apply — no product, no listed weight,
    #: or sold by weight, where the scale answers and no format exists.
    pack_weight_is_known: bool | None = None


class ProductSummary(BaseModel):
    """One row per product across every invoice in scope.

    ``price_per_kg_eur`` is weighted by weight, not an average of the per-line
    quotients: averaging rates would let a 200 g purchase count as much as a 5 kg
    one. Lines with no weight are left out of it entirely rather than guessed.
    """

    master_product_id: uuid.UUID
    canonical_name: str
    brand: str | None
    is_own_brand: bool = False
    category_path: str | None
    sold_by_weight: bool
    conservation: str | None = None
    presentation: str | None = None
    dietary_attributes: list[str] = Field(default_factory=list)
    line_count: int
    receipt_count: int
    total_quantity: Decimal
    total_weight_kg: Decimal | None
    total_paid_eur: Decimal
    #: Fs articles were never paid for, so they carry their notional worth here.
    total_notional_eur: Decimal
    price_per_kg_eur: Decimal | None
    first_purchase_on: dt.date | None
    last_purchase_on: dt.date | None


class ReceiptItemUpdate(BaseModel):
    #: Where the line sits on the paper. The grid orders by it, so correcting it
    #: is how a hand-added line takes its real place.
    line_no: int | None = Field(default=None, ge=1)
    description_raw: str | None = Field(default=None, max_length=300)
    quantity: Decimal | None = None
    unit: str | None = None
    unit_price_pvp_eur: Decimal | None = None
    promo_discount_eur: Decimal | None = None
    promo_type: str | None = None
    weight_observed_kg: Decimal | None = None
    weight_listed_kg: Decimal | None = None
    is_bulk_weighed: bool | None = None
    product_flag: str | None = None
    notes: str | None = None


class ItemProductAssignment(BaseModel):
    """Re-resolve a line to another product; the correction is learned per merchant."""

    master_product_id: uuid.UUID


class FsItemCreate(BaseModel):
    """An article added by hand during review.

    ``is_fs`` false means the parser missed a line that **is** on the paper; the
    reconciliation against the printed total is what judges the correction.
    """

    description_raw: str = Field(min_length=1, max_length=300)
    unit_price_pvp_eur: Decimal = Field(gt=0)
    quantity: Decimal = Decimal("1")
    unit: str = "UN"
    is_fs: bool = True
    #: Only meaningful on a printed line: an Fs row was never on the paper.
    line_no: int | None = Field(default=None, ge=1)
    promo_discount_eur: Decimal = Decimal("0")
    notional_value_source: Literal["PRICE_HISTORY", "MANUAL"] = "MANUAL"
    notes: str | None = None


# --- Receipts -----------------------------------------------------------------


class ReceiptDerived(BaseModel):
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
    item_count_matches: bool
    is_complete: bool


class ReceiptSummary(ApiModel):
    id: uuid.UUID
    entity_id: uuid.UUID
    merchant_id: uuid.UUID | None
    merchant_name: str | None = None
    purchase_date: dt.date | None
    purchased_at: dt.datetime | None
    total_eur: Decimal
    total_discount_eur: Decimal
    item_count: int | None
    status: str
    confidence: Decimal | None
    atcud_code: str | None
    document_id: uuid.UUID | None
    loyalty_scheme: str | None
    fs_value_eur: Decimal = Decimal("0.00")
    fs_item_count: int = 0
    #: Counted over non-Fs rows only — the figure the printed ``item_count`` is
    #: checked against, and the left-hand side of the `5/2` reading in the list.
    printed_item_count: int = 0
    notional_total_eur: Decimal = Decimal("0.00")
    is_reconciled: bool = True
    parser_profile_id: uuid.UUID | None = None
    parser_profile_name: str | None = None


class ReceiptDetail(ReceiptSummary):
    processing_job_id: uuid.UUID | None
    import_batch_id: uuid.UUID | None
    atcud_valid: bool | None
    atcud_reason: str | None
    parsed_payment_methods: list[Any]
    loyalty_card_masked: str | None
    loyalty_accrued_eur: Decimal
    loyalty_discount_eur: Decimal
    decision_reasons: list[Any]
    notes: str | None
    void_reason: str | None
    #: Signed and time-limited — an `<img>`/`<iframe>` cannot send a CSRF header,
    #: so the HMAC signature *is* the authorisation (ADR-0004).
    document_url: str | None = None
    document_mime_type: str | None = None
    document_filename: str | None = None
    items: list[ReceiptItemOut]
    derived: ReceiptDerived


class ReceiptUpdate(BaseModel):
    merchant_id: uuid.UUID | None = None
    purchase_date: dt.date | None = None
    total_eur: Decimal | None = None
    total_discount_eur: Decimal | None = None
    item_count: int | None = None
    loyalty_scheme: str | None = None
    loyalty_discount_eur: Decimal | None = None
    loyalty_accrued_eur: Decimal | None = None
    notes: str | None = None


class VoidRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


# --- Upload & queue -----------------------------------------------------------


class UploadedReceipt(BaseModel):
    receipt_id: uuid.UUID
    processing_job_id: uuid.UUID
    filename: str | None
    created: bool
    message: str | None = None


class UploadResponse(BaseModel):
    items: list[UploadedReceipt]


class QueueEntry(BaseModel):
    receipt_id: uuid.UUID | None
    processing_job_id: uuid.UUID
    status: str
    job_status: str
    attempts: int
    max_attempts: int
    last_error: str | None
    parser_profile_name: str | None
    merchant_name: str | None
    filename: str | None
    confidence: Decimal | None
    created_at: dt.datetime
    completed_at: dt.datetime | None


class StatusBoard(BaseModel):
    """UX-1.5 «Estado» — every figure links to the list that resolves it."""

    total_receipts: int
    to_process: int
    failed_jobs: int
    to_validate: int
    total_lines: int
    unresolved_lines: int
    resolved_lines: int
    uncategorized_products: int
    total_products: int
    merge_candidates: int
    #: Reported as a trend and labelled *observed, never targeted* (Decision #41).
    observed_auto_accept_rate: float | None
    decided_receipts: int


# --- Parser profiles ----------------------------------------------------------


class ParserProfileOut(ApiModel):
    id: uuid.UUID
    merchant_id: uuid.UUID | None
    merchant_name: str | None = None
    name: str
    parser_key: str
    document_kinds: list[Any]
    detection_patterns: list[Any]
    field_hints: dict[str, Any]
    priority: int
    success_rate: Decimal | None
    is_active: bool
    is_generic: bool = False


class ParserProfileIn(BaseModel):
    merchant_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=160)
    parser_key: str = Field(min_length=1, max_length=64)
    document_kinds: list[str] = Field(default_factory=lambda: ["PDF_DIGITAL"])
    detection_patterns: list[str] = Field(default_factory=list)
    field_hints: dict[str, Any] = Field(default_factory=dict)
    priority: int = 0
    is_active: bool = True


class ParserProfileUpdate(BaseModel):
    name: str | None = None
    parser_key: str | None = None
    document_kinds: list[str] | None = None
    detection_patterns: list[str] | None = None
    field_hints: dict[str, Any] | None = None
    priority: int | None = None
    is_active: bool | None = None


class ParserOption(BaseModel):
    parser_key: str
    display_name: str


class ProfileTestResult(BaseModel):
    """Re-parse a stored document with a chosen profile and diff the result."""

    parser_key: str
    item_count: int
    total_eur: Decimal | None
    computed_total_eur: Decimal
    is_reconciled: bool
    confidence: Decimal
    decision_reasons: list[Any]
    items: list[dict[str, Any]]
    diff_vs_current: dict[str, Any]
