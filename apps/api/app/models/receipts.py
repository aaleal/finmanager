"""Module 1 — Supermarket & Receipt Processing.

Slice M1a ships the ingestion spine: what the invoice claimed (``Receipt``), what
its lines sum to (``ReceiptItem``), and how one merchant's layout is read
(``MerchantParserProfile``). Products, aliases and price history arrive with the
later slices and are never redefined here.

Money is ``NUMERIC(10,2)`` decimal EUR everywhere — never float, never cents.
"""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, uuid_pk
from app.models.core import _check

# --- Enum-ish string domains (VARCHAR + CHECK, per §3 Backend/data) ----------

RECEIPT_STATUSES = (
    "UPLOADED",
    "PARSING",
    "AUTO_ACCEPTED",
    "NEEDS_REVIEW",
    "CONFIRMED",
    "VOID",
    "FAILED",
)
#: Legal transitions of the receipt state machine. Anything else is rejected.
RECEIPT_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "UPLOADED": ("PARSING", "FAILED"),
    "PARSING": ("AUTO_ACCEPTED", "NEEDS_REVIEW", "FAILED"),
    "AUTO_ACCEPTED": ("CONFIRMED", "NEEDS_REVIEW", "PARSING", "VOID"),
    "NEEDS_REVIEW": ("CONFIRMED", "PARSING", "VOID"),
    "CONFIRMED": ("VOID",),
    "FAILED": ("PARSING",),
    "VOID": (),
}

UNITS = ("KG", "G", "L", "ML", "UN", "PACK")
CANONICAL_UNITS = ("KG", "L", "UN")
PROMO_TYPES = ("ABSOLUTE", "PERCENTAGE", "BOGO")
PRODUCT_FLAGS = ("REFUND", "DEPOSIT_RETURN", "SEASONAL", "OTHER")
NOTIONAL_SOURCES = ("PRICE_HISTORY", "MANUAL")
DOCUMENT_KINDS = ("PDF_DIGITAL", "IMAGE_SCAN")


class MerchantParserProfile(Base, TimestampMixin, SoftDeleteMixin):
    """How one merchant's layout is read. Exactly one row is the generic fallback."""

    __tablename__ = "merchant_parser_profiles"
    __table_args__ = (
        # The generic fallback is unique and undeletable: a new merchant is never
        # a dead end (FR-1.15).
        Index(
            "uq_merchant_parser_profiles_generic",
            "merchant_id",
            unique=True,
            postgresql_where=text("merchant_id IS NULL AND is_deleted = false"),
        ),
        Index("ix_merchant_parser_profiles_merchant_id", "merchant_id"),
        CheckConstraint(
            "success_rate IS NULL OR (success_rate >= 0 AND success_rate <= 1)",
            name="success_rate_range",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    merchant_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("merchants.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    parser_key: Mapped[str] = mapped_column(String(64), nullable=False)
    document_kinds: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    detection_patterns: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    field_hints: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    success_rate: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    @property
    def is_generic(self) -> bool:
        return self.merchant_id is None


class Receipt(Base, TimestampMixin, SoftDeleteMixin):
    """One payment transaction at one merchant.

    ``total_eur`` / ``total_discount_eur`` / ``item_count`` are what the invoice
    *printed* — independent extracted facts. The item rows are what we *parsed*.
    Reconciling the two is a confidence signal, never a silent correction of
    either side (Decision #12).
    """

    __tablename__ = "receipts"
    __table_args__ = (
        _check("status", RECEIPT_STATUSES, "status"),
        # The ATCUD *is* the fiscal document identity, so a duplicate is made
        # impossible rather than merely detectable (Decision #35).
        Index(
            "uq_receipts_entity_atcud",
            "entity_id",
            "atcud_code",
            unique=True,
            postgresql_where=text("atcud_code IS NOT NULL AND is_deleted = false"),
        ),
        Index(
            "uq_receipts_entity_document",
            "entity_id",
            "document_id",
            unique=True,
            postgresql_where=text("document_id IS NOT NULL AND is_deleted = false"),
        ),
        # The shape of every list and dashboard query (Performance NFR).
        Index("ix_receipts_entity_purchase_date_id", "entity_id", "purchase_date", "id"),
        Index("ix_receipts_merchant_id", "merchant_id"),
        Index("ix_receipts_status", "status"),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="confidence_range",
        ),
        CheckConstraint(
            "status <> 'VOID' OR void_reason IS NOT NULL",
            name="void_needs_reason",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    entity_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("entities.id"), nullable=False
    )
    merchant_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("merchants.id"), nullable=True
    )
    purchased_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Local Europe/Lisbon calendar date — never UTC-shifted (§3 Domain).
    purchase_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("documents.id"), nullable=True
    )
    parser_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("merchant_parser_profiles.id"), nullable=True
    )
    import_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("import_batches.id"), nullable=True
    )
    processing_job_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("processing_jobs.id"), nullable=True
    )

    total_eur: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00"), server_default="0"
    )
    total_discount_eur: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00"), server_default="0"
    )
    item_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="UPLOADED")
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    decision_reasons: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    # Provider output. Never selected in list queries (Performance NFR).
    raw_ocr_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    atcud_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    atcud_valid: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    atcud_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)

    parsed_payment_methods: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)

    loyalty_scheme: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Merchants print this already masked, so nothing sensitive ever arrives
    # (Decision #4).
    loyalty_card_masked: Mapped[str | None] = mapped_column(String(64), nullable=True)
    loyalty_accrued_eur: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00"), server_default="0"
    )
    loyalty_discount_eur: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00"), server_default="0"
    )

    tags: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(PgUUID(as_uuid=True)), nullable=False, default=list, server_default="{}"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    items: Mapped[list[ReceiptItem]] = relationship(
        "ReceiptItem",
        back_populates="receipt",
        lazy="selectin",
        order_by="ReceiptItem.is_fs, ReceiptItem.line_no, ReceiptItem.created_at",
        cascade="all, delete-orphan",
    )


class ReceiptItem(Base, TimestampMixin, SoftDeleteMixin):
    """One purchased article.

    An **Fs article was never on the invoice**: the household appends it by hand
    and values it notionally. It therefore has no ``line_no``, no
    ``merchant_section`` and no ``iva_class_raw``, and its ``paid_price_eur`` is
    always ``0.00`` so adding one cannot disturb a reconciliation that already
    passed (Decision #31).
    """

    __tablename__ = "receipt_items"
    __table_args__ = (
        _check("unit", UNITS, "unit"),
        _check("unit_canonical", CANONICAL_UNITS, "unit_canonical"),
        CheckConstraint(
            f"promo_type IS NULL OR promo_type IN ({', '.join(repr(v) for v in PROMO_TYPES)})",
            name="promo_type",
        ),
        CheckConstraint(
            f"product_flag IS NULL OR product_flag IN "
            f"({', '.join(repr(v) for v in PRODUCT_FLAGS)})",
            name="product_flag",
        ),
        CheckConstraint(
            f"notional_value_source IS NULL OR notional_value_source IN "
            f"({', '.join(repr(v) for v in NOTIONAL_SOURCES)})",
            name="notional_value_source",
        ),
        # No money moved on an Fs row, so no arithmetic can be disturbed by one.
        CheckConstraint("is_fs = false OR paid_price_eur = 0", name="fs_pays_nothing"),
        # An Fs article without a value is meaningless.
        CheckConstraint("is_fs = false OR unit_price_pvp_eur > 0", name="fs_needs_notional_value"),
        # Nothing the *document* supplied can exist on a row the document never had.
        CheckConstraint(
            "is_fs = false OR (line_no IS NULL AND merchant_section IS NULL "
            "AND iva_class_raw IS NULL)",
            name="fs_has_no_document_fields",
        ),
        Index("ix_receipt_items_receipt_id_line_no", "receipt_id", "line_no"),
        Index("ix_receipt_items_master_product_id", "master_product_id"),
        Index("ix_receipt_items_entity_id", "entity_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    receipt_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("receipts.id", ondelete="CASCADE"), nullable=False
    )
    # Denormalized from the parent so analytics stay single-table (Decision #8).
    entity_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("entities.id"), nullable=False
    )

    line_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    merchant_section: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description_raw: Mapped[str] = mapped_column(String(300), nullable=False)
    # A matching key, never displayed. The user sees the product's canonical name.
    description_norm: Mapped[str] = mapped_column(String(300), nullable=False)
    # The category comes with the product, never with the line (Decision #34).
    master_product_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("master_products.id"), nullable=True
    )

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 4), nullable=False, default=Decimal("1"), server_default="1"
    )
    unit: Mapped[str] = mapped_column(String(8), nullable=False, default="UN")
    quantity_canonical: Mapped[Decimal] = mapped_column(
        Numeric(14, 4), nullable=False, default=Decimal("1"), server_default="1"
    )
    unit_canonical: Mapped[str] = mapped_column(String(8), nullable=False, default="UN")

    weight_listed_kg: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    weight_observed_kg: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    is_bulk_weighed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    unit_price_pvp_eur: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00"), server_default="0"
    )
    promo_discount_eur: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00"), server_default="0"
    )
    promo_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    invoice_allocated_discount_eur: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00"), server_default="0"
    )
    paid_price_eur: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00"), server_default="0"
    )

    # Captured exactly as printed and interpreted by nobody (Decision #38).
    iva_class_raw: Mapped[str | None] = mapped_column(String(4), nullable=True)

    is_fs: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    notional_value_source: Mapped[str | None] = mapped_column(String(20), nullable=True)
    product_flag: Mapped[str | None] = mapped_column(String(20), nullable=True)

    tags: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(PgUUID(as_uuid=True)), nullable=False, default=list, server_default="{}"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    legacy_row_ref: Mapped[int | None] = mapped_column(Integer, nullable=True)

    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    decision_reasons: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)

    receipt: Mapped[Receipt] = relationship("Receipt", back_populates="items")


__all__ = [
    "CANONICAL_UNITS",
    "DOCUMENT_KINDS",
    "NOTIONAL_SOURCES",
    "PRODUCT_FLAGS",
    "PROMO_TYPES",
    "RECEIPT_STATUSES",
    "RECEIPT_TRANSITIONS",
    "UNITS",
    "MerchantParserProfile",
    "Receipt",
    "ReceiptItem",
]
