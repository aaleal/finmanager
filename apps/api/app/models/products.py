"""Module 1 slice M1b - the product catalogue.

``MasterProduct`` is what a product *is*; ``ProductAlias`` is what a merchant
*calls* it. Real *talões* print neither an EAN nor an article code, so the alias
table is not an optimisation — it is the load-bearing mechanism by which a
receipt line ever resolves at all (Decision #23).

Both tables are **household-level reference data, not entity-scoped**, for the
same reason ``Merchant`` and ``Category`` are: a product is the same product
whoever bought it, and forking the catalogue per entity would split every €/kg
trend down the middle. See docs/decisions/0019-the-product-catalogue-is-shared.md.
"""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, uuid_pk
from app.models.core import _check

CATEGORY_STATUSES = ("AUTO", "VALIDATED", "MANUAL")
#: How the article is kept. Genuinely closed — a fourth kind would be a new
#: physical state, not a new word, so a CHECK is the right guard here.
CONSERVATION_KINDS = ("AMBIENTE", "REFRIGERADO", "CONGELADO")


class MasterProduct(Base, TimestampMixin, SoftDeleteMixin):
    """Canonical product identity, user-managed.

    **A category lives here and nowhere else** (Decision #34). The module's own
    rule settles it: two items with different categories are, by rule, different
    master products, so a per-line category could only ever drift from this one.
    A receipt line inherits its category by resolving; an unresolved line has
    none, and that is the truth.
    """

    __tablename__ = "master_products"
    __table_args__ = (
        _check("category_status", CATEGORY_STATUSES, "category_status"),
        CheckConstraint(
            "conservation IS NULL OR conservation IN "
            f"({', '.join(repr(v) for v in CONSERVATION_KINDS)})",
            name="conservation",
        ),
        Index("ix_master_products_canonical_name", "canonical_name"),
        # Dietary tags are a filter dimension, and JSONB containment without a
        # GIN index is a sequential scan of the whole catalogue.
        Index(
            "ix_master_products_dietary_attributes",
            "dietary_attributes",
            postgresql_using="gin",
        ),
        # Category spend joins through the product, which is a small table.
        Index(
            "ix_master_products_category_l1_id_l2_id_l3_id",
            "category_l1_id",
            "category_l2_id",
            "category_l3_id",
        ),
        Index(
            "uq_master_products_canonical_name_brand",
            "canonical_name",
            "brand",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
        CheckConstraint(
            "category_confidence IS NULL OR "
            "(category_confidence >= 0 AND category_confidence <= 1)",
            name="category_confidence_range",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    canonical_name: Mapped[str] = mapped_column(String(250), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(120), nullable=True)
    #: Marked by hand once per product, not derived from ``brand``: the retailer's
    #: own-brand markers are deliberately stripped before matching
    #: (``normalize._NOISE_WORDS``), so the name that survives cannot tell us this.
    is_own_brand: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    #: The **deepest assigned** category and the only authoritative one. Nullable
    #: because the household's own taxonomy leaves L3 blank on roughly half its
    #: rows, and an L2-only assignment is a real answer rather than a gap.
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("categories.id"), nullable=True
    )
    #: Maintained ancestors, recomputed on reparent so analytics stay single-table
    #: without a recursive join on the module's hottest query (Decision #16).
    category_l1_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("categories.id"), nullable=True
    )
    category_l2_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("categories.id"), nullable=True
    )
    category_l3_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("categories.id"), nullable=True
    )
    #: Confirmed once per *product*, so the backlog shrinks as the catalogue
    #: matures instead of growing with every shop (Decision #17).
    category_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="AUTO", server_default="'AUTO'"
    )
    category_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)

    #: ``[{label?, weight_kg?, barcode?}]`` - one entry per pack size. A 500 g and
    #: a 1 kg bag of the same coffee are one product; what differs is the weight,
    #: and that is what makes €/kg comparable across them (Decision #15).
    pack_variants: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    sold_by_weight: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    #: Physical state and shape of what was bought. Neither is part of the
    #: product's identity (ADR-0015/0030 keep that at name + brand) — they are
    #: axes a €/kg series can be decomposed along, so laminada and palitada stop
    #: being averaged into one misleading curve.
    conservation: Mapped[str | None] = mapped_column(String(16), nullable=True)
    #: No CHECK on purpose: the household meets a new cut far more often than a
    #: new conservation state, and a CHECK would make each one a migration. The
    #: vocabulary is enforced in the service layer against a JSON dictionary.
    presentation: Mapped[str | None] = mapped_column(String(60), nullable=True)

    dietary_attributes: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    allergen_list: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    seasonal_flags: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    expected_shelf_life_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deposit_value_eur: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)


class ProductAlias(Base, TimestampMixin):
    """Learned merchant vocabulary.

    A table rather than a JSON blob on the product precisely because it is
    *learned*: it carries per-merchant confidence that rises with every
    correction a human confirms (Decision #5).
    """

    __tablename__ = "product_aliases"
    __table_args__ = (
        UniqueConstraint(
            "merchant_id", "description_norm", name="uq_product_aliases_merchant_description"
        ),
        Index("ix_product_aliases_master_product_id", "master_product_id"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    master_product_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("master_products.id", ondelete="CASCADE"), nullable=False
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("merchants.id"), nullable=False
    )
    merchant_description: Mapped[str] = mapped_column(String(300), nullable=False)
    description_norm: Mapped[str] = mapped_column(String(300), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(
        Numeric(4, 3), nullable=False, default=Decimal("0.500"), server_default="0.5"
    )
    correction_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    last_used_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


__all__ = ["CATEGORY_STATUSES", "CONSERVATION_KINDS", "MasterProduct", "ProductAlias"]
