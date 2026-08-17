"""Module 1 slice M1c - the immutable price observation.

**Append-only.** Correcting a receipt item later writes a *new* row and never
rewrites the past. €/kg is not stored here: price and weight sit on the same row,
so the division cannot drift, and storing the quotient would only add a column to
keep in step. ``shrinkflation_indicator`` is likewise computed over the 12-month
window at query time, not frozen onto a row that cannot know its own future.
"""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk


class ProductPriceHistory(Base):
    """One price observation, frozen at the moment it was made."""

    __tablename__ = "product_price_history"
    __table_args__ = (
        # `is_fs` lives on the row so the Fs filter never forces a join back to
        # `receipt_items` (Performance NFR).
        Index(
            "ix_product_price_history_product_merchant_observed",
            "master_product_id",
            "merchant_id",
            "observed_on",
        ),
        # Append-only, so this is deliberately **not** unique: a correction adds a
        # new row beside the old one rather than replacing it.
        Index("ix_product_price_history_source_item", "source_receipt_item_id"),
        CheckConstraint("weight_kg IS NULL OR weight_kg > 0", name="weight_positive"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    master_product_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("master_products.id"), nullable=False
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("merchants.id"), nullable=False
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("entities.id"), nullable=False
    )
    observed_on: Mapped[dt.date] = mapped_column(Date, nullable=False)
    #: Snapshot of the source line's Fs status, so price analysis can filter
    #: without a join. Trusted and included, never excluded (Decision #33).
    is_fs: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    list_price_eur: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    #: On an Fs row this carries the **notional value**, never ``0.00`` — writing
    #: the literal zero would drag every paid-price trend towards zero.
    paid_price_eur: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    source_receipt_item_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("receipt_items.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


__all__ = ["ProductPriceHistory"]
