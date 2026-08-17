"""Contracts for price evolution, shrinkflation, spend and loyalty."""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class PricePointOut(BaseModel):
    observed_on: dt.date
    merchant_id: uuid.UUID
    merchant_name: str | None
    is_fs: bool
    weight_kg: Decimal | None
    list_price_eur: Decimal
    paid_price_eur: Decimal
    #: ``NULL`` when the line carries no weight — never defaulted to zero.
    list_price_per_kg_eur: Decimal | None
    paid_price_per_kg_eur: Decimal | None


class PriceHistoryOut(BaseModel):
    master_product_id: uuid.UUID
    canonical_name: str
    sold_by_weight: bool
    points: list[PricePointOut]
    shrinkflation: list[ShrinkflationOut]


class ShrinkflationOut(BaseModel):
    """``(current_weight / avg_weight_12m) - (current_price / avg_price_12m)``."""

    master_product_id: uuid.UUID
    canonical_name: str
    merchant_id: uuid.UUID
    merchant_name: str | None
    observations: int
    current_weight_kg: Decimal
    average_weight_kg: Decimal
    current_price_eur: Decimal
    average_price_eur: Decimal
    #: A score, not money — decimal for reproducibility.
    margin_signal: Decimal
    observed_on: dt.date


class CategorySpendOut(BaseModel):
    category_id: uuid.UUID | None
    display_name_pt: str
    #: "What did I spend" and "what was it worth". Identical on every non-Fs row.
    paid_eur: Decimal
    notional_eur: Decimal
    item_count: int


class LoyaltyGroupOut(BaseModel):
    scheme: str | None
    card_masked: str | None
    receipt_count: int
    accrued_eur: Decimal
    discount_eur: Decimal
    first_purchase: dt.date | None
    last_purchase: dt.date | None


class LoyaltyAllocationOut(BaseModel):
    receipt_id: uuid.UUID
    purchase_date: dt.date | None
    merchant_name: str | None
    total_eur: Decimal
    loyalty_discount_eur: Decimal
    loyalty_accrued_eur: Decimal
    allocated_across_items_eur: Decimal


class ReceiptLinkOut(BaseModel):
    """The receipt↔transaction edge, and whether a ledger exists to link to."""

    ledger_available: bool
    message: str | None = None
    link_id: uuid.UUID | None = None
    transaction_id: uuid.UUID | None = None
    status: str | None = None
    confidence: Decimal | None = None
    decision_reasons: list[Any] = Field(default_factory=list)


class LinkRequest(BaseModel):
    transaction_id: uuid.UUID


class TagsUpdate(BaseModel):
    """Open user labels with **no effect on any total** (FR-1.5)."""

    tags: list[uuid.UUID]
