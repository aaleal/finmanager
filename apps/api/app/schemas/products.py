"""Contracts for the product catalogue, the taxonomy and the legacy import."""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import ApiModel

# --- Products -----------------------------------------------------------------


class PackVariant(BaseModel):
    """One pack size. A 500 g and a 1 kg bag are one product with two variants."""

    label: str | None = None
    weight_kg: Decimal | None = None
    #: Accepted but read by nothing today: receipts never print one (Decision #23).
    barcode: str | None = None


class PackVariantAdd(BaseModel):
    """Append one format to a product. Idempotent on the weight, so the review
    pane can add what it just read off a line without knowing the other formats."""

    weight_kg: Decimal = Field(gt=0)
    label: str | None = Field(default=None, max_length=60)
    barcode: str | None = None


class LastKnownPrice(BaseModel):
    """Derived from the newest price observation; never stored, never a second truth."""

    last_pvp_eur: Decimal | None = None
    last_price_per_kg_eur: Decimal | None = None
    last_weight_kg: Decimal | None = None
    last_observed_on: dt.date | None = None


class MasterProductOut(ApiModel):
    id: uuid.UUID
    canonical_name: str
    brand: str | None
    is_own_brand: bool
    category_id: uuid.UUID | None
    category_l1_id: uuid.UUID | None
    category_l2_id: uuid.UUID | None
    category_l3_id: uuid.UUID | None
    category_status: str
    category_confidence: Decimal | None
    pack_variants: list[Any]
    sold_by_weight: bool
    conservation: str | None
    presentation: str | None
    dietary_attributes: list[Any]
    allergen_list: list[Any]
    seasonal_flags: list[Any]
    expected_shelf_life_days: int | None
    deposit_value_eur: Decimal | None
    created_at: dt.datetime

    category_path: str | None = None
    alias_count: int = 0
    occurrence_count: int = 0
    last_known_price: LastKnownPrice | None = None


class MasterProductCreate(BaseModel):
    canonical_name: str = Field(min_length=1, max_length=250)
    brand: str | None = Field(default=None, max_length=120)
    is_own_brand: bool = False
    category_id: uuid.UUID | None = None
    sold_by_weight: bool = False
    pack_variants: list[PackVariant] = Field(default_factory=list)
    conservation: str | None = None
    presentation: str | None = None
    dietary_attributes: list[str] = Field(default_factory=list)
    allergen_list: list[str] = Field(default_factory=list)
    seasonal_flags: list[str] = Field(default_factory=list)
    expected_shelf_life_days: int | None = None
    deposit_value_eur: Decimal | None = None


class MasterProductUpdate(BaseModel):
    canonical_name: str | None = Field(default=None, max_length=250)
    brand: str | None = Field(default=None, max_length=120)
    is_own_brand: bool | None = None
    category_id: uuid.UUID | None = None
    sold_by_weight: bool | None = None
    pack_variants: list[PackVariant] | None = None
    conservation: str | None = None
    presentation: str | None = None
    dietary_attributes: list[str] | None = None
    allergen_list: list[str] | None = None
    seasonal_flags: list[str] | None = None
    expected_shelf_life_days: int | None = None
    deposit_value_eur: Decimal | None = None


class ProductSearchResult(BaseModel):
    """What every picker pre-fills from: identity, category and last known price."""

    id: uuid.UUID
    canonical_name: str
    brand: str | None
    category_id: uuid.UUID | None
    category_path: str | None
    sold_by_weight: bool
    score: float
    last_known_price: LastKnownPrice | None = None


class AttributeOption(BaseModel):
    """One accepted spelling of an attribute: what is stored, and how it reads."""

    value: str
    label: str


class ProductAttributeVocabularyOut(BaseModel):
    """The controlled vocabulary the pickers offer and the API enforces.

    Served rather than hard-coded in the client so the dictionary has exactly one
    home: adding a cut is an edit to the JSON, not a release on both sides.
    """

    conservation: list[AttributeOption]
    presentation: list[AttributeOption]
    dietary: list[AttributeOption]


class ProductAliasOut(ApiModel):
    id: uuid.UUID
    master_product_id: uuid.UUID
    merchant_id: uuid.UUID
    merchant_name: str | None = None
    merchant_description: str
    confidence: Decimal
    correction_count: int
    last_used_at: dt.datetime | None


class LearnAliasRequest(BaseModel):
    master_product_id: uuid.UUID
    merchant_id: uuid.UUID
    merchant_description: str = Field(min_length=1, max_length=300)


class ProductOccurrence(BaseModel):
    receipt_item_id: uuid.UUID
    receipt_id: uuid.UUID
    purchase_date: dt.date | None
    merchant_name: str | None
    description_raw: str
    quantity: Decimal
    unit: str
    unit_price_pvp_eur: Decimal
    paid_price_eur: Decimal
    price_per_kg_final_eur: Decimal | None
    is_fs: bool


class MergeRequest(BaseModel):
    source_id: uuid.UUID


class MergeCandidateProduct(BaseModel):
    id: uuid.UUID
    canonical_name: str
    brand: str | None = None


class MergeCandidate(BaseModel):
    key: str
    products: list[MergeCandidateProduct]


class ReassignProductRequest(BaseModel):
    master_product_id: uuid.UUID


# --- Categories ---------------------------------------------------------------


class CategoryNode(ApiModel):
    id: uuid.UUID
    code_en: str
    display_name_pt: str
    domain: str
    level: int
    parent_id: uuid.UUID | None
    brand_axis: bool
    path: str | None = None
    product_count: int = 0
    children: list[CategoryNode] = Field(default_factory=list)


class CategorySearchResult(BaseModel):
    id: uuid.UUID
    display_name_pt: str
    level: int
    #: The full ``L1 › L2 › L3`` path, so the same leaf under two parents is never
    #: ambiguous in a picker.
    path: str


class CategoryTreeNode(BaseModel):
    """One node of the whole GROCERY tree, flat, for the taxonomy editor."""

    id: uuid.UUID
    display_name_pt: str
    level: int
    parent_id: uuid.UUID | None
    brand_axis: bool
    path: str
    product_count: int


class CategoryCreate(BaseModel):
    display_name_pt: str = Field(min_length=1, max_length=160)
    parent_id: uuid.UUID | None = None
    brand_axis: bool = False


class CategoryRename(BaseModel):
    display_name_pt: str = Field(min_length=1, max_length=160)


class CategoryReparent(BaseModel):
    parent_id: uuid.UUID | None = None


class CategoryMerge(BaseModel):
    target_id: uuid.UUID


class CategoryImpactOut(BaseModel):
    category_id: uuid.UUID
    descendants: int
    master_products: int
    receipt_items: int
    in_use: bool


class CategoryOperationResult(BaseModel):
    ok: bool = True
    affected_products: int = 0
    message: str | None = None


class CategoryImportRowError(BaseModel):
    row_number: int
    message: str


class CategoryImportOut(BaseModel):
    """Additive only, like `ensure_categories` at boot: a name already in the
    tree is left alone, never renamed or moved by re-importing (Decision #56)."""

    created: int
    existing: int
    errors: list[CategoryImportRowError]


class CategoryDefaultsLoadOut(BaseModel):
    """What loading the shipped default taxonomy just created (Decision #57)."""

    created: int


# --- Legacy import ------------------------------------------------------------


class LegacyImportResult(BaseModel):
    """The sheet is validated, not trusted: every exception is reported, not repaired."""

    import_batch_id: uuid.UUID
    row_count: int
    skipped_non_grocery_rows: int
    skipped_non_grocery_merchants: list[str]
    receipts_created: int
    receipts_reconciled: int
    receipts_needing_review: int
    fs_rows: int
    fs_rows_snapped: int
    all_fs_groups: int
    products_created: int
    aliases_created: int
    merchants_created: int
    exceptions: list[dict[str, Any]]


# --- Bulk import (curated product log) -----------------------------------------


class BulkProductImportRow(BaseModel):
    """One resolved spreadsheet row. ``category_id``/``existing_product_id`` are
    resolved by the preview step, never by the client, so the review table only
    ever shows what the server already checked. ``errors`` is keyed by field
    name, so the review table can highlight just that cell."""

    row_number: int
    canonical_name: str | None = None
    brand: str | None = None
    category_path: str | None = None
    category_id: uuid.UUID | None = None
    sold_by_weight: bool = False
    pack_weights_kg: list[Decimal] = Field(default_factory=list)
    is_own_brand: bool = False
    conservation: str | None = None
    presentation: str | None = None
    dietary_attributes: list[str] = Field(default_factory=list)
    #: Set when a product with this exact name+brand already exists — the
    #: commit skips it rather than raising a duplicate-name error.
    existing_product_id: uuid.UUID | None = None
    errors: dict[str, str] = Field(default_factory=dict)


class BulkProductImportPreviewOut(BaseModel):
    rows: list[BulkProductImportRow]


class BulkProductImportCommitIn(BaseModel):
    rows: list[BulkProductImportRow]


class BulkProductImportRowResult(BaseModel):
    row_number: int
    ok: bool
    skipped: bool = False
    message: str
    master_product_id: uuid.UUID | None = None


FsFilter = Literal["all", "only", "exclude"]
